"""Explicit app layering helpers.

Local-core routers stay mounted by default.
Central / portal adapters are opt-in and mounted only when explicitly enabled.
"""
from fastapi import APIRouter

from backend.routers import (
    admin,
    agent,
    auth,
    backups,
    boards,
    discovery,
    kiosk,
    matches,
    players,
    settings,
    stats,
    updates,
)
from backend.runtime_features import portal_surface_enabled


LOCAL_CORE_ROUTERS = (
    auth.router,
    boards.router,
    kiosk.router,
    settings.router,
    admin.router,
    backups.router,
    updates.router,
    agent.router,
    discovery.router,
    matches.router,
    stats.router,
    players.router,
)


def include_local_core_routes(api_router: APIRouter) -> None:
    for router in LOCAL_CORE_ROUTERS:
        api_router.include_router(router)


def include_optional_adapter_routes(api_router: APIRouter) -> None:
    if not portal_surface_enabled():
        return

    from backend.routers import central_proxy

    api_router.include_router(central_proxy.router)
