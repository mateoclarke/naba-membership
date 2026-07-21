"""
Application configuration from environment variables.

Env vars are validated by Varlock (.env.schema) when using:
    npx varlock run -- uvicorn api.main:app --reload
"""

import os

# WordPress API (used by sync script and optional live proxy)
WP_API_URL = os.environ.get("WP_API_URL", "")
WP_API_KEY = os.environ.get("WP_API_KEY", "")

# Data source mode: "sqlite" (default) or "wordpress" (live proxy)
DATA_SOURCE = os.environ.get("DATA_SOURCE", "sqlite")

# CORS origins (comma-separated)
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:4321,http://127.0.0.1:4321",
).split(",")

# Local uploads root (profile logos / gallery). Served at /uploads via StaticFiles.
UPLOADS_ROOT = os.environ.get("UPLOADS_ROOT", "").strip()

# Admin API key for profile image uploads (X-Admin-API-Key or Bearer).
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "").strip()

# Connect form: require Referer to match one of CORS_ORIGINS (set 0 to disable for tests).
CONNECT_REQUIRE_REFERER = os.environ.get("CONNECT_REQUIRE_REFERER", "1").strip() == "1"

# WordPress site origin (optional). Used to derive JWT + REST URLs when overrides are unset.
WP_SITE_URL = os.environ.get("WP_SITE_URL", "").strip().rstrip("/")

# JWT auth plugin: POST username/password, receive token.
# Default endpoint is for Simple JWT Login; override via env var for other plugins.
WP_JWT_TOKEN_URL = os.environ.get("WP_JWT_TOKEN_URL", "").strip() or (
    f"{WP_SITE_URL}/wp-json/simple-jwt-login/v1/auth" if WP_SITE_URL else ""
)

# Validate Bearer token and read current user (must return JSON with numeric id).
WP_REST_USER_ME_URL = os.environ.get("WP_REST_USER_ME_URL", "").strip() or (
    f"{WP_SITE_URL}/wp-json/wp/v2/users/me" if WP_SITE_URL else ""
)

# HS256 secret for API-issued member session tokens (after WP login).
AUTH_JWT_SECRET = os.environ.get("AUTH_JWT_SECRET", "").strip()

AUTH_JWT_EXPIRE_SECONDS = int(os.environ.get("AUTH_JWT_EXPIRE_SECONDS", "604800"))
