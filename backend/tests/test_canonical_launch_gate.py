from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from app.features.inviter.api import start_campaign as legacy_start_campaign
from app.features.orchestration.api import start_campaign as direct_orchestration_start
from app.features.orchestration.schemas import CampaignPlanRequest


class _LegacyService:
    def __init__(self, owner_id):
        self.owner_id = owner_id

    async def get_campaign(self, campaign_id):
        return SimpleNamespace(id=campaign_id, owner_id=self.owner_id, status="draft")


class CanonicalLaunchGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_orchestration_start_requires_preflight(self) -> None:
        campaign_id = uuid4()
        with self.assertRaises(HTTPException) as raised:
            await direct_orchestration_start(
                campaign_id=campaign_id,
                payload=CampaignPlanRequest(),
                user=SimpleNamespace(id=uuid4()),
                session=None,
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "PREFLIGHT_REQUIRED")
        self.assertIn("/preflight/start", raised.exception.detail["launch_endpoint"])

    async def test_legacy_start_requires_preflight_before_celery(self) -> None:
        owner_id = uuid4()
        campaign_id = uuid4()
        with self.assertRaises(HTTPException) as raised:
            await legacy_start_campaign(
                campaign_id=campaign_id,
                current_user=SimpleNamespace(id=owner_id),
                service=_LegacyService(owner_id),
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "PREFLIGHT_REQUIRED")
        self.assertIn("/preflight/start", raised.exception.detail["launch_endpoint"])


if __name__ == "__main__":
    unittest.main()
