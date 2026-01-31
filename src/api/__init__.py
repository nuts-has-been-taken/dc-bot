"""API Module - FastAPI server for receiving external notifications."""

from .server import create_app

__all__ = ["create_app"]
