"""FastAPI application factory for the modular Nestora server."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.constants import CSRF_HEADER_NAME
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging
from app.core.realtime import router as realtime_router
from app.core.storage.router import router as storage_router
from app.db.session import close_database
from app.modules.associations.router import router as associations_router
from app.modules.auth.router import (
    admin_code_router,
    public_router as public_auth_router,
    router as auth_router,
)
from app.modules.bank.router import router as bank_router
from app.modules.board_tasks.router import router as board_tasks_router
from app.modules.amenities.router import router as amenities_router
from app.modules.announcements.router import router as announcements_router
from app.modules.events.router import router as events_router
from app.modules.polls.router import router as polls_router
from app.modules.board_members.router import router as board_members_router
from app.modules.committees.router import router as committees_router
from app.modules.employees.router import router as employees_router
from app.modules.entity_types.router import router as entity_types_router
from app.modules.entities.router import router as entities_router
from app.modules.features.router import router as features_router
from app.modules.financials.router import router as financials_router
from app.modules.documents.router import router as documents_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.chart_of_accounts.router import router as chart_of_accounts_router
from app.modules.health.router import router as health_router
from app.modules.notifications.router import router as notifications_router
from app.modules.meetings.router import router as meetings_router
from app.modules.marketplace.router import router as marketplace_router
from app.modules.visitor_management.router import router as visitor_management_router
from app.modules.wallet.router import router as wallet_router
from app.modules.permissions.router import router as permissions_router
from app.modules.profile.router import router as profile_router
from app.modules.roles.router import router as roles_router
from app.modules.service_requests.router import lookup_router as service_request_lookup_router
from app.modules.service_requests.router import router as service_requests_router
from app.modules.subscriptions.router import router as subscriptions_router
from app.modules.users.router import router as users_router
from app.modules.vendors.router import router as vendors_router
from app.modules.locations.router import router as locations_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage startup/shutdown resources in one place; migrations are never run automatically."""
    settings = get_settings()
    configure_logging(settings.debug)
    yield
    await close_database()


def create_app() -> FastAPI:
    """Build the API once while keeping HTTP wiring out of domain modules."""
    settings = get_settings()
    app = FastAPI(title="Nestora API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", CSRF_HEADER_NAME, "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request, call_next):
        """Attach a safe correlation ID to every response for later logs, metrics, and support tracing."""
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    install_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(locations_router, prefix="/api")
    app.include_router(storage_router, prefix="/api")
    app.include_router(realtime_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(public_auth_router, prefix="/api")
    app.include_router(admin_code_router, prefix="/api")
    app.include_router(entity_types_router, prefix="/api")
    app.include_router(entities_router, prefix="/api")
    app.include_router(features_router, prefix="/api")
    app.include_router(roles_router, prefix="/api")
    app.include_router(permissions_router, prefix="/api")
    app.include_router(subscriptions_router, prefix="/api")
    app.include_router(associations_router, prefix="/api")
    app.include_router(bank_router, prefix="/api")
    app.include_router(board_tasks_router, prefix="/api")
    app.include_router(amenities_router, prefix="/api")
    app.include_router(announcements_router, prefix="/api")
    app.include_router(events_router, prefix="/api")
    app.include_router(polls_router, prefix="/api")
    app.include_router(board_members_router, prefix="/api")
    app.include_router(committees_router, prefix="/api")
    app.include_router(financials_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(chart_of_accounts_router, prefix="/api")
    app.include_router(employees_router, prefix="/api")
    app.include_router(users_router, prefix="/api")
    app.include_router(vendors_router, prefix="/api")
    app.include_router(profile_router, prefix="/api")
    app.include_router(service_requests_router, prefix="/api")
    app.include_router(service_request_lookup_router, prefix="/api")
    app.include_router(notifications_router, prefix="/api")
    app.include_router(meetings_router, prefix="/api")
    app.include_router(marketplace_router, prefix="/api")
    app.include_router(visitor_management_router, prefix="/api")
    app.include_router(wallet_router, prefix="/api")
    return app


app = create_app()
