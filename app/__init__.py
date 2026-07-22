"""Compatibility entry point for hosts configured with `gunicorn app:app`."""

from web_app import app

__all__ = ["app"]
