from __future__ import annotations

from app.features.connectors.base import MessengerConnector


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, MessengerConnector] = {}

    def register(self, connector: MessengerConnector) -> None:
        key = connector.platform.strip().lower()
        if not key:
            raise ValueError("Connector platform must not be empty")
        self._connectors[key] = connector

    def get(self, platform: str) -> MessengerConnector:
        key = platform.strip().lower()
        try:
            return self._connectors[key]
        except KeyError as exc:
            raise ValueError(f"Unsupported platform: {platform}") from exc

    def list(self) -> list[dict]:
        return [
            connector.describe()
            for _, connector in sorted(self._connectors.items(), key=lambda item: item[0])
        ]

    def supports(self, platform: str) -> bool:
        return platform.strip().lower() in self._connectors


connector_registry = ConnectorRegistry()
