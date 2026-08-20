from app.features.connectors.discord import DiscordConnector
from app.features.connectors.registry import connector_registry
from app.features.connectors.telegram import TelegramConnector


def register_default_connectors() -> None:
    if not connector_registry.supports("telegram"):
        connector_registry.register(TelegramConnector())
    if not connector_registry.supports("discord"):
        connector_registry.register(DiscordConnector())
