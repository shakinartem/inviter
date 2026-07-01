"""
TGStat Discovery Service - keyword-based Telegram source discovery using Playwright.

Finds Telegram channels/chats by keyword via TGStat, analyzes them,
and scores their quality for campaign use.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.features.source_discovery.models import SourceCandidate, SourceScore
from app.features.source_discovery.schemas import (
    SourceCandidateListItem,
    SourceCandidateResponse,
    SourceDiscoverySearchRequest,
    SourceScoreResponse,
)

TGSTAT_BASE_URL = "https://tgstat.ru"
TGSTAT_SEARCH_URL = f"{TGSTAT_BASE_URL}/search"

# Scoring weights
TOPIC_WEIGHT = 0.35
ACTIVITY_WEIGHT = 0.25
AUDIENCE_WEIGHT = 0.25
LIVENESS_WEIGHT = 0.15

_LOGGER = logger.bind(module="tgstat_discovery")


class TgstatDiscoveryService:
    """Service for discovering Telegram sources via TGStat."""

    def __init__(self) -> None:
        self._playwright_initialized = False
        self._browser = None

    async def _ensure_browser(self):
        """Lazy-init Playwright browser."""
        if not self._playwright_initialized:
            try:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                self._playwright_initialized = True
                _LOGGER.info("Playwright browser initialized")
            except Exception as exc:
                _LOGGER.error("Failed to initialize Playwright", error=str(exc))
                raise RuntimeError(
                    "Playwright initialization failed. "
                    "Ensure Chromium is installed: python -m playwright install chromium"
                ) from exc

    async def close(self):
        """Close browser and playwright."""
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_playwright"):
            await self._playwright.stop()

    # ==================== Search ====================

    async def search_sources(
        self,
        request: SourceDiscoverySearchRequest,
        owner_id: UUID,
        db_session: AsyncSession,
    ) -> list[SourceCandidate]:
        """Search TGStat for sources matching the query."""
        await self._ensure_browser()

        _LOGGER.info("Searching TGStat", query=request.query, limit=request.limit)

        # Build search URL
        params = f"?q={request.query}&type=channels"
        if request.category:
            params += f"&category={request.category}"
        search_url = f"{TGSTAT_SEARCH_URL}{params}"

        page = None
        candidates: list[SourceCandidate] = []
        seen_usernames: set[str] = set()

        try:
            context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ru-RU",
            )
            page = await context.new_page()

            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as exc:
                _LOGGER.warning("TGStat page load timeout/error", error=str(exc))
                return candidates

            # Check for captcha
            content = await page.content()
            if "captcha" in content.lower() or "block" in content.lower()[:2000]:
                _LOGGER.warning("TGStat captcha or block detected")
                return candidates

            # Parse search results
            cards = await page.query_selector_all(
                "div.card, div.channel-item, div.search-item, "
                "a[href*='/channel/'], div.channel-card"
            )

            _LOGGER.info(f"Found {len(cards)} potential cards on page")

            for card in cards[: request.limit]:
                try:
                    candidate = await self._parse_search_card(card, request.query)
                    if candidate and candidate.username not in seen_usernames:
                        seen_usernames.add(candidate.username or "")
                        candidates.append(candidate)
                except Exception as parse_err:
                    _LOGGER.debug("Failed to parse card", error=str(parse_err))
                    continue

            # Try next pages if needed
            if len(candidates) < request.limit:
                more = await self._parse_next_pages(
                    page, request, seen_usernames, max_pages=2
                )
                candidates.extend(more)

        except Exception as exc:
            _LOGGER.error("TGStat search error", error=str(exc))
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

        # Save candidates to DB
        saved = await self._save_candidates(candidates, owner_id, db_session)

        _LOGGER.info(
            "TGStat search completed",
            found=len(candidates),
            saved=len(saved),
        )

        return saved

    async def _parse_search_card(
        self, card: Any, query: str
    ) -> Optional[SourceCandidate]:
        """Parse a single search result card with stricter filtering."""
        now = datetime.now(timezone.utc)

        # Title and link
        title_el = await card.query_selector("a")
        if not title_el:
            return None

        title = (await title_el.inner_text()).strip()
        href = await title_el.get_attribute("href") or ""

        # Extract username from href
        username = None
        tgstat_url = None
        url = None

        if "/channel/" in href:
            parts = href.split("/channel/")
            if len(parts) > 1:
                username = parts[1].split("/")[0].lstrip("@")
                tgstat_url = f"{TGSTAT_BASE_URL}{href}" if href.startswith("/") else href
                url = f"https://t.me/{username}"
        elif href.startswith("http"):
            tgstat_url = href
            # Try to extract t.me username from URL
            match = re.search(r"t\.me/([a-zA-Z0-9_]+)", href)
            if match:
                username = match.group(1)
                url = href

        # Must have at least one valid identifier: username or tgstat_url or valid source URL
        has_valid_link = bool(username or tgstat_url or (url and url.startswith("https://t.me/")))

        # Category
        cat_el = await card.query_selector(
            ".category, .channel-category, .tag, a.tag, .badge"
        )
        category = (await cat_el.inner_text()).strip() if cat_el else None

        # Description
        desc_el = await card.query_selector(
            "p.description, .description, .channel-description, .text-muted"
        )
        description = (await desc_el.inner_text()).strip()[:1000] if desc_el else None

        # Subscribers count
        subs_el = await card.query_selector(
            ".subscribers, .members, .channel-members, "
            ".stat-item span, .count, .subscribers-count"
        )
        subscribers = None
        if subs_el:
            subs_text = (await subs_el.inner_text()).strip()
            subscribers = self._parse_count(subs_text)

        # Determine source type
        source_type = "unknown"
        card_text = (await card.inner_text()).lower()
        if "чат" in card_text or "chat" in card_text or "group" in card_text:
            source_type = "chat"
        elif "channel" in card_text or "канал" in card_text:
            source_type = "channel"

        # Reject junk UI/payment/ad/email elements
        junk_titles = {"попробовать", "отправить", "e-mail", "руб", "мес", "тариф", "реклама"}
        title_lower = (title or "").lower()
        if any(junk in title_lower for junk in junk_titles):
            return None

        # Reject if no real link and no meaningful title
        if not has_valid_link and not title:
            return None

        # Reject if title looks like UI button/price
        if title and re.search(r"\d+\s*руб", title_lower):
            return None

        # Reject hyper-short or meaningless titles with no link
        if not has_valid_link and len(title_lower.split()) < 2:
            return None

        # Basic quality validation: title must contain at least 3 letters (Cyrillic/Latin)
        if title and not re.search(r"[a-zA-Zа-яА-ЯёЁ]{3,}", title):
            return None

        raw_data = {
            "query": query,
            "title": title,
            "href": href,
            "category": category,
            "description": description,
            "subscribers_text": (await subs_el.inner_text()).strip() if subs_el else None,
            "card_text_snippet": (await card.inner_text()).strip()[:500],
            "source_type": source_type,
        }

        candidate = SourceCandidate(
            source_type=source_type,
            title=title[:255] if title else None,
            username=username,
            url=url,
            tgstat_url=tgstat_url,
            category=category,
            description=description,
            subscribers_count=subscribers,
            discovered_by_query=query,
            discovered_at=now,
            status="discovered",
            raw_data=raw_data,
        )

        return candidate

    async def _parse_next_pages(
        self,
        page: Any,
        request: SourceDiscoverySearchRequest,
        seen_usernames: set[str],
        max_pages: int = 2,
    ) -> list[SourceCandidate]:
        """Parse pagination results."""
        candidates: list[SourceCandidate] = []

        for page_num in range(max_pages):
            next_btn = await page.query_selector(
                "a[rel='next'], a.next-page, .pagination .next, a:has-text('>')"
            )
            if not next_btn:
                break

            try:
                await next_btn.click()
                await page.wait_for_timeout(2000)
            except Exception:
                break

            cards = await page.query_selector_all(
                "div.card, div.channel-item, div.search-item, "
                "a[href*='/channel/'], div.channel-card"
            )

            for card in cards[: request.limit]:
                try:
                    candidate = await self._parse_search_card(card, request.query)
                    if candidate and candidate.username not in seen_usernames:
                        seen_usernames.add(candidate.username or "")
                        candidates.append(candidate)
                except Exception:
                    continue

            if len(candidates) >= request.limit:
                break

        return candidates

    async def _save_candidates(
        self,
        candidates: list[SourceCandidate],
        owner_id: UUID,
        db_session: AsyncSession,
    ) -> list[SourceCandidate]:
        """Save discovered candidates to DB with deduplication."""
        if not candidates:
            return []

        saved: list[SourceCandidate] = []

        for candidate in candidates:
            candidate.owner_id = owner_id

            # Check for duplicate by username
            existing = None
            if candidate.username:
                result = await db_session.execute(
                    select(SourceCandidate).where(
                        SourceCandidate.username == candidate.username,
                        SourceCandidate.owner_id == owner_id,
                    )
                )
                existing = result.scalar_one_or_none()

            if existing:
                _LOGGER.debug("Skipping duplicate", username=candidate.username)
                saved.append(existing)
                continue

            db_session.add(candidate)
            await db_session.flush()
            saved.append(candidate)

        await db_session.commit()

        for c in saved:
            await db_session.refresh(c)

        return saved

    # ==================== Analyze ====================

    async def analyze_source(
        self,
        candidate_id: UUID,
        owner_id: UUID,
        db_session: AsyncSession,
    ) -> SourceScore:
        """Analyze a source candidate and calculate scores."""
        await self._ensure_browser()

        result = await db_session.execute(
            select(SourceCandidate).where(
                SourceCandidate.id == candidate_id,
                SourceCandidate.owner_id == owner_id,
            )
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise ValueError(f"Source candidate {candidate_id} not found")

        _LOGGER.info("Analyzing source", candidate_id=str(candidate_id), username=candidate.username)

        # Try to get detailed metrics from TGStat page
        metrics = {}
        if candidate.tgstat_url:
            metrics = await self._fetch_source_details(candidate.tgstat_url)

        # Update candidate with fetched metrics
        if metrics.get("subscribers_count"):
            candidate.subscribers_count = metrics["subscribers_count"]
        if metrics.get("avg_post_reach"):
            candidate.avg_post_reach = metrics["avg_post_reach"]
        if metrics.get("posts_per_day"):
            candidate.posts_per_day = metrics["posts_per_day"]
        if metrics.get("comments_enabled") is not None:
            candidate.comments_enabled = metrics["comments_enabled"]
        if metrics.get("linked_chat_url"):
            candidate.linked_chat_url = metrics["linked_chat_url"]
        if metrics.get("raw_data"):
            candidate.raw_data = metrics["raw_data"]

        # Calculate scores
        query = candidate.discovered_by_query or ""
        score = self._calculate_scores(candidate, query)

        # Save score
        score_obj = SourceScore(
            source_candidate_id=candidate.id,
            topic_score=score["topic_score"],
            activity_score=score["activity_score"],
            audience_quality_score=score["audience_quality_score"],
            chat_liveness_score=score["chat_liveness_score"],
            total_score=score["total_score"],
            reasons=score["reasons"],
        )
        db_session.add(score_obj)

        candidate.status = "analyzed"
        candidate.last_analyzed_at = datetime.now(timezone.utc)

        await db_session.commit()
        await db_session.refresh(score_obj)

        _LOGGER.info(
            "Source analysis completed",
            candidate_id=str(candidate_id),
            total_score=score["total_score"],
        )

        return score_obj

    async def _fetch_source_details(self, tgstat_url: str) -> dict[str, Any]:
        """Fetch detailed source metrics from TGStat source page."""
        metrics: dict[str, Any] = {}

        context = None
        page = None

        try:
            context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ru-RU",
            )
            page = await context.new_page()

            try:
                await page.goto(tgstat_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)  # Wait for dynamic content
            except Exception as exc:
                _LOGGER.warning("Failed to load TGStat page", error=str(exc))
                return metrics

            content = await page.content()
            if "captcha" in content.lower()[:3000]:
                _LOGGER.warning("TGStat captcha on source page")
                return metrics

            # Subscribers
            subs_el = await page.query_selector(
                ".subscribers-count, .stat-subscribers, "
                "[class*='subscribers'], [class*='members']"
            )
            if subs_el:
                subs_text = (await subs_el.inner_text()).strip()
                metrics["subscribers_count"] = self._parse_count(subs_text)

            # ER/Reach
            reach_el = await page.query_selector(
                ".reach, .avg-reach, .stat-views, [class*='reach'], [class*='views']"
            )
            if reach_el:
                reach_text = (await reach_el.inner_text()).strip()
                metrics["avg_post_reach"] = self._parse_count(reach_text)

            # Posts per day
            posts_el = await page.query_selector(
                ".posts-per-day, .post-frequency, [class*='posts'], [class*='frequency']"
            )
            if posts_el:
                posts_text = (await posts_el.inner_text()).strip()
                posts_count = self._parse_count(posts_text)
                if posts_count:
                    metrics["posts_per_day"] = min(posts_count, 100)

            # Comments
            comments_el = await page.query_selector(
                ".comments, .discussion, [class*='comment'], [class*='discuss']"
            )
            if comments_el:
                metrics["comments_enabled"] = True

            # Linked chat
            chat_link = await page.query_selector(
                "a[href*='t.me/'], a[href*='tg://']"
            )
            if chat_link:
                href = await chat_link.get_attribute("href") or ""
                if "t.me/" in href or "tg://" in href:
                    metrics["linked_chat_url"] = href

            # Store raw page data
            page_title = await page.title()
            metrics["raw_data"] = {
                "page_title": page_title,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            _LOGGER.warning("Error fetching source details", error=str(exc))
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

        return metrics

    def _calculate_scores(
        self,
        candidate: SourceCandidate,
        query: str,
    ) -> dict[str, Any]:
        """Calculate rule-based scores for a source candidate."""
        reasons: list[str] = []
        query_words = set(query.lower().split())

        # Topic score (0-100)
        topic_score = 50  # Default
        title_lower = (candidate.title or "").lower()
        desc_lower = (candidate.description or "").lower()
        cat_lower = (candidate.category or "").lower()

        # Check title for query words
        title_words = set(title_lower.split())
        matched_words = query_words & title_words
        if matched_words:
            topic_score += min(len(matched_words) * 15, 30)
            reasons.append(f"Title matches query: {', '.join(matched_words)}")

        # Check description for query words
        desc_words = set(desc_lower.split())
        desc_matches = query_words & desc_words
        if desc_matches:
            topic_score += min(len(desc_matches) * 5, 15)
            reasons.append(f"Description matches query: {', '.join(desc_matches)}")

        # Check category
        if cat_lower and any(w in cat_lower for w in query_words):
            topic_score += 10
            reasons.append(f"Category matches query: {candidate.category}")

        # Negative signals
        if "покупка" in desc_lower or "реклама" in desc_lower or "куплю" in desc_lower:
            topic_score -= 15
            reasons.append("Possible ad/purchase channel")

        topic_score = max(0, min(100, topic_score))

        # Activity score (0-100)
        activity_score = 30  # Default

        if candidate.posts_per_day:
            if candidate.posts_per_day >= 5:
                activity_score += 30
                reasons.append("High posting frequency")
                activity_score += 10
            elif candidate.posts_per_day >= 1:
                reasons.append("Regular posting")
                activity_score += 20
            else:
                activity_score += 5
        else:
            activity_score -= 10
            reasons.append("Unknown posting frequency")

        # If we have reach data, the source is likely active
        if candidate.avg_post_reach and candidate.avg_post_reach > 0:
            activity_score += 15
            reasons.append("Has recent post engagement")

        activity_score = max(0, min(100, activity_score))

        # Audience quality score (0-100)
        quality_score = 30  # Default

        if candidate.subscribers_count:
            subs = candidate.subscribers_count
            if subs > 100000:
                quality_score += 10
                reasons.append("Large audience (100k+)")
            elif subs > 10000:
                quality_score += 20
                reasons.append("Medium audience (10k-100k)")
            elif subs > 1000:
                quality_score += 10
            else:
                quality_score -= 10
                reasons.append("Small audience (<1k)")

            # Engagement ratio (views / subscribers)
            if candidate.avg_post_reach and candidate.avg_post_reach > 0:
                ratio = candidate.avg_post_reach / subs
                if ratio > 0.5:
                    quality_score += 20
                    reasons.append("High engagement ratio")
                elif ratio > 0.2:
                    quality_score += 10
                    reasons.append("Good engagement ratio")
                elif ratio < 0.05:
                    quality_score -= 20
                    reasons.append("Very low engagement (likely inflated)")
            else:
                quality_score -= 5
                reasons.append("No engagement data available")
        else:
            quality_score -= 10
            reasons.append("Unknown audience size")

        quality_score = max(0, min(100, quality_score))

        # Chat liveness score (0-100)
        liveness_score = 20  # Default

        if candidate.comments_enabled:
            liveness_score += 30
            reasons.append("Comments/discussion enabled")

        if candidate.linked_chat_url:
            liveness_score += 25
            reasons.append("Has linked discussion chat")

        if candidate.source_type in ("chat", "group"):
            liveness_score += 20
            reasons.append("Is a chat/group (inherently interactive)")

        liveness_score = max(0, min(100, liveness_score))

        # Total score (weighted)
        total_score = int(
            topic_score * TOPIC_WEIGHT
            + activity_score * ACTIVITY_WEIGHT
            + quality_score * AUDIENCE_WEIGHT
            + liveness_score * LIVENESS_WEIGHT
        )

        # Score sentiment
        if total_score < 30:
            reasons.append("Dead or low quality source")
        elif total_score < 50:
            reasons.append("Weak source")
        elif total_score < 75:
            reasons.append("Decent source")
        else:
            reasons.append("Good source")

        return {
            "topic_score": topic_score,
            "activity_score": activity_score,
            "audience_quality_score": quality_score,
            "chat_liveness_score": liveness_score,
            "total_score": total_score,
            "reasons": reasons,
        }

    def _parse_count(self, text: str) -> Optional[int]:
        """Parse count from string like '12 345', '1.2K', '1M'."""
        text = text.strip().lower().replace(" ", "").replace(",", ".")
        if not text:
            return None

        multipliers = {"k": 1000, "m": 1000000, "b": 1000000000}
        multiplier = 1
        for suffix, mult in multipliers.items():
            if text.endswith(suffix):
                multiplier = mult
                text = text[:-1]
                break

        try:
            val = float(text) * multiplier
            return int(val)
        except (ValueError, TypeError):
            digits = re.sub(r"[^\d]", "", text)
            return int(digits) if digits else None

    # ==================== Select / Reject / Delete ====================

    async def select_source(
        self,
        candidate_id: UUID,
        owner_id: UUID,
        db_session: AsyncSession,
    ) -> SourceCandidate:
        """Mark source as selected for campaign use."""
        result = await db_session.execute(
            select(SourceCandidate).where(
                SourceCandidate.id == candidate_id,
                SourceCandidate.owner_id == owner_id,
            )
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise ValueError(f"Source candidate {candidate_id} not found")

        candidate.status = "selected"
        await db_session.commit()
        await db_session.refresh(candidate)

        _LOGGER.info("Source selected", candidate_id=str(candidate_id))
        return candidate

    async def reject_source(
        self,
        candidate_id: UUID,
        owner_id: UUID,
        db_session: AsyncSession,
    ) -> None:
        """Mark source as rejected."""
        result = await db_session.execute(
            select(SourceCandidate).where(
                SourceCandidate.id == candidate_id,
                SourceCandidate.owner_id == owner_id,
            )
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise ValueError(f"Source candidate {candidate_id} not found")

        candidate.status = "rejected"
        await db_session.commit()
        _LOGGER.info("Source rejected", candidate_id=str(candidate_id))

    async def delete_source(
        self,
        candidate_id: UUID,
        owner_id: UUID,
        db_session: AsyncSession,
    ) -> None:
        """Delete a source candidate."""
        result = await db_session.execute(
            select(SourceCandidate).where(
                SourceCandidate.id == candidate_id,
                SourceCandidate.owner_id == owner_id,
            )
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise ValueError(f"Source candidate {candidate_id} not found")

        await db_session.delete(candidate)
        await db_session.commit()
        _LOGGER.info("Source deleted", candidate_id=str(candidate_id))

    # ==================== List ====================

    async def list_sources(
        self,
        owner_id: UUID,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> tuple[list[SourceCandidateListItem], int]:
        """List source candidates with optional status filter."""
        close_session = False
        if db_session is None:
            db_session = AsyncSessionLocal()
            close_session = True

        try:
            stmt = select(SourceCandidate).where(SourceCandidate.owner_id == owner_id)
            count_stmt = select(func.count(SourceCandidate.id)).where(
                SourceCandidate.owner_id == owner_id
            )

            if status:
                stmt = stmt.where(SourceCandidate.status == status)
                count_stmt = count_stmt.where(SourceCandidate.status == status)

            total_result = await db_session.execute(count_stmt)
            total = total_result.scalar() or 0

            stmt = (
                stmt.order_by(SourceCandidate.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await db_session.execute(stmt)
            candidates = list(result.scalars().all())

            # Pre-fetch scores to avoid MissingGreenlet on lazy relationship
            candidate_ids = [c.id for c in candidates]
            scores_by_candidate: dict[UUID, int] = {}
            if candidate_ids:
                scores_stmt = (
                    select(SourceCandidate.id, SourceScore.total_score)
                    .join(SourceScore, SourceScore.source_candidate_id == SourceCandidate.id)
                    .where(SourceCandidate.id.in_(candidate_ids))
                )
                scores_result = await db_session.execute(scores_stmt)
                for cid, total_score in scores_result.all():
                    scores_by_candidate[cid] = total_score

            items = []
            for c in candidates:
                best_score = scores_by_candidate.get(c.id)
                items.append(
                    SourceCandidateListItem(
                        id=c.id,
                        source_type=c.source_type,
                        title=c.title,
                        username=c.username,
                        url=c.url,
                        tgstat_url=c.tgstat_url,
                        category=c.category,
                        subscribers_count=c.subscribers_count,
                        status=c.status,
                        total_score=best_score,
                        discovered_by_query=c.discovered_by_query,
                        discovered_at=c.discovered_at,
                        created_at=c.created_at,
                    )
                )

            return items, total

        finally:
            if close_session:
                await db_session.close()