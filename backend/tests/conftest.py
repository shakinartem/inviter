"""
Global test configuration.

Ensures all SQLAlchemy models are imported before any test runs,
so that string-based relationship() references can be resolved.

Also forces eager mapper configuration to prevent lazy configure
failures when test code creates model instances like SiteSettings.
"""
from app.db.models import *  # noqa: F401, F403
from app.db.base import Base

Base.registry.configure()