from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .db import (
    Base,
    engine,
    ensure_directory_profile_categories_materials_columns,
    ensure_directory_profile_geocode_columns,
    ensure_directory_profile_slug_column,
    ensure_member_subscriptions_column,
)
from .routers_admin_connect import router as admin_connect_router
from .routers_admin_business_members import router as admin_business_members_router
from .routers_admin import router as admin_router
from .routers_auth import router as auth_router
from .routers_me import router as member_self_router
from .routers_public_connect import router as public_connect_router
from .routers_public_members import router as public_members_router


def create_app() -> FastAPI:
    app = FastAPI(title="NaBA Membership API", version="0.1.0")

    origins = [o.strip() for o in config.CORS_ORIGINS if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create tables if they do not exist
    Base.metadata.create_all(bind=engine)
    ensure_directory_profile_slug_column(engine)
    ensure_directory_profile_geocode_columns(engine)
    ensure_directory_profile_categories_materials_columns(engine)
    ensure_member_subscriptions_column(engine)

    uploads_root = (
        Path(config.UPLOADS_ROOT).resolve()
        if config.UPLOADS_ROOT
        else Path(__file__).resolve().parent.parent / "uploads"
    )
    uploads_root.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_root)), name="uploads")

    # Routers
    app.include_router(public_members_router)
    app.include_router(public_connect_router)
    app.include_router(auth_router)
    app.include_router(member_self_router)
    app.include_router(admin_router)
    app.include_router(admin_connect_router)
    app.include_router(admin_business_members_router)

    @app.get("/health", tags=["meta"])
    def health():
        return {
            "status": "ok",
            "data_source": config.DATA_SOURCE,
            "wp_api_configured": bool(config.WP_API_URL and config.WP_API_KEY),
        }

    return app


app = create_app()

