"""FastAPI service (Phase 2): /forecast, /skill, /sources, /enso."""

from .app import app, create_app

__all__ = ["app", "create_app"]
