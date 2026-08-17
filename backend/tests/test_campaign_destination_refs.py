from __future__ import annotations

import unittest
from uuid import uuid4

from telethon.tl.types import InputChannel, InputUser

# SQLAlchemy resolves string relationships lazily when the first mapped object is
# instantiated. Import the application's model registry so isolated unit tests
# see the same complete mapper graph as app startup and Alembic.
from app.db import models as _models  # noqa: F401
from app.features.connectors.telegram import TelegramConnector
from app.features.orchestration.destinations import CampaignDestination


class CampaignDestinationReferenceTests(unittest.TestCase):
    def _destination(self, **kwargs) -> CampaignDestination:
        defaults = {
            "owner_id": uuid4(),
            "campaign_id": uuid4(),
            "parsed_chat_id": uuid4(),
            "platform": "telegram",
            "external_id": "123456789",
            "username": None,
            "title": "Target",
            "community_type": "supergroup",
            "access_hash": "987654321",
        }
        defaults.update(kwargs)
        return CampaignDestination(**defaults)

    def test_public_username_is_preferred(self) -> None:
        destination = self._destination(username="my_group")
        self.assertEqual(destination.connector_ref, "@my_group")

    def test_private_supergroup_uses_channel_access_hash(self) -> None:
        destination = self._destination()
        self.assertEqual(
            destination.connector_ref,
            "channel:123456789:987654321",
        )

    def test_basic_group_uses_chat_reference(self) -> None:
        destination = self._destination(
            community_type="group",
            access_hash=None,
        )
        self.assertEqual(destination.connector_ref, "chat:123456789")

    def test_user_reference_builds_input_user(self) -> None:
        ref = TelegramConnector._target_ref("user:123:456")
        self.assertIsInstance(ref, InputUser)
        self.assertEqual(ref.user_id, 123)
        self.assertEqual(ref.access_hash, 456)

    def test_channel_reference_builds_input_channel(self) -> None:
        kind, ref = TelegramConnector._destination_ref("channel:123:456")
        self.assertEqual(kind, "channel")
        self.assertIsInstance(ref, InputChannel)
        self.assertEqual(ref.channel_id, 123)
        self.assertEqual(ref.access_hash, 456)

    def test_basic_group_reference_is_numeric(self) -> None:
        kind, ref = TelegramConnector._destination_ref("chat:123")
        self.assertEqual(kind, "chat")
        self.assertEqual(ref, 123)


if __name__ == "__main__":
    unittest.main()
