"""
Dependency wiring.

The service is a process-wide singleton held on `app.state` and handed to
routes via Depends. Keeping it out of module-global state means tests can
build an app with a throwaway cache path and no shared leakage.
"""

from __future__ import annotations

from fastapi import Request

from .service import MacroService


def get_service(request: Request) -> MacroService:
    return request.app.state.service
