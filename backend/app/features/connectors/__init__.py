"""Platform connector abstraction for messenger integrations."""

from app.features.connectors.base import ConnectorCapabilities, MessengerConnector
from app.features.connectors.registry import connector_registry

__all__ = ("ConnectorCapabilities", "MessengerConnector", "connector_registry")
