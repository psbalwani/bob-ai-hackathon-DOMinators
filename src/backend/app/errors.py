"""Shared API error type + the error-shape convention from
docs/05_api_contracts.md ({"error": {"code", "message"}}).

Split out of main.py so auth.py (a FastAPI dependency, not a route) can
raise the same error shape without main.py <-> auth.py becoming a circular
import.
"""

from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
