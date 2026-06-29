"""
Parser module - chat and user parsing by niche.

Models are imported lazily to avoid conflicts with app.features.parsed_chats.models.
"""
from app.features.parser.service import ParserService

__all__ = (
    "ParserService",
)