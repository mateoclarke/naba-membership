"""WordPress JWT login — exchange credentials for WP user id (+ roles).

Supports two plugins:
  - "JWT Authentication for WP REST API" (Tmeister): returns {"token": "..."}
  - "Simple JWT Login" (Nicu Micle): returns {"success": true, "data": {"jwt": "..."}}

Flow: POST credentials → receive WP JWT → resolve WordPress user id and roles.
For Simple JWT Login we prefer POST .../auth/validate (returns user.ID + roles) so
"/wp/v2/users/me" JWT middleware does not need to be enabled.
Tmeister / other plugins fall back to GET /wp/v2/users/me with Bearer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

import httpx
from fastapi import HTTPException

from . import config

WP_ADMIN_ROLE = "administrator"


@dataclass
class WpAuthResult:
    user_id: int
    roles: List[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return WP_ADMIN_ROLE in self.roles


def _extract_token(body: dict) -> Optional[str]:
    """Extract the JWT from either plugin's response format."""
    # Tmeister: {"token": "eyJ..."}
    token = body.get("token")
    if token:
        return token

    # Simple JWT Login: {"success": true, "data": {"jwt": "..."}}
    data = body.get("data")
    if isinstance(data, dict):
        return data.get("jwt") or data.get("token")

    return None


def _jwt_validate_url() -> str:
    """Simple JWT Login validate endpoint (derived from auth URL when possible)."""
    token_url = (config.WP_JWT_TOKEN_URL or "").rstrip("/")
    if token_url.endswith("/auth"):
        return f"{token_url}/validate"
    if config.WP_SITE_URL:
        return f"{config.WP_SITE_URL}/wp-json/simple-jwt-login/v1/auth/validate"
    return ""


def _roles_from_validate_data(data: dict) -> List[str]:
    raw = data.get("roles")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        if isinstance(item, str) and item:
            out.append(item)
    return out


def _parse_validate_body(body: Any) -> Optional[Tuple[int, List[str]]]:
    if not isinstance(body, dict) or not body.get("success"):
        return None
    data = body.get("data")
    if not isinstance(data, dict):
        return None
    roles = _roles_from_validate_data(data)
    user = data.get("user")
    if isinstance(user, dict):
        raw = user.get("ID") or user.get("id")
        try:
            uid = int(raw or 0)
        except (TypeError, ValueError):
            uid = 0
        if uid:
            return uid, roles
    # Fallback: payload.id inside data.jwt[0].payload
    jwt_list = data.get("jwt")
    if isinstance(jwt_list, list) and jwt_list:
        first = jwt_list[0]
        if isinstance(first, dict):
            payload = first.get("payload")
            if isinstance(payload, dict):
                try:
                    uid = int(payload.get("id") or 0)
                except (TypeError, ValueError):
                    uid = 0
                if uid:
                    return uid, roles
    return None


def _user_id_from_validate_body(body: Any) -> Optional[int]:
    parsed = _parse_validate_body(body)
    return parsed[0] if parsed else None


async def _via_simple_jwt_validate(
    client: httpx.AsyncClient, token: str
) -> Optional[Tuple[int, List[str]]]:
    url = _jwt_validate_url()
    if not url:
        return None
    resp = await client.post(
        url,
        json={"JWT": token},
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code != 200:
        return None
    try:
        body = resp.json()
    except ValueError:
        return None
    return _parse_validate_body(body)


async def _via_users_me(
    client: httpx.AsyncClient, token: str
) -> Optional[Tuple[int, List[str]]]:
    if not config.WP_REST_USER_ME_URL:
        return None
    # Prefer Bearer; some Simple JWT setups expect the raw token in Authorization.
    for header_value in (f"Bearer {token}", token):
        resp = await client.get(
            config.WP_REST_USER_ME_URL,
            headers={"Authorization": header_value},
        )
        if resp.status_code != 200:
            continue
        try:
            user = resp.json()
        except ValueError:
            continue
        if not isinstance(user, dict):
            continue
        try:
            uid = int(user.get("id") or 0)
        except (TypeError, ValueError):
            uid = 0
        if not uid:
            continue
        roles: List[str] = []
        raw_roles = user.get("roles")
        if isinstance(raw_roles, list):
            roles = [r for r in raw_roles if isinstance(r, str) and r]
        return uid, roles
    return None


async def authenticate_wp_user(username: str, password: str) -> WpAuthResult:
    """
    POST to WP JWT token endpoint, then resolve WordPress user id and roles
    (user id matches DirectoryProfile.id after sync).
    """
    if not config.WP_JWT_TOKEN_URL:
        raise HTTPException(
            status_code=503,
            detail="WordPress JWT auth is not configured (WP_JWT_TOKEN_URL or WP_SITE_URL)",
        )
    if not _jwt_validate_url() and not config.WP_REST_USER_ME_URL:
        raise HTTPException(
            status_code=503,
            detail="WordPress JWT auth is not configured (WP_JWT_TOKEN_URL / WP_REST_USER_ME_URL or WP_SITE_URL)",
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            config.WP_JWT_TOKEN_URL,
            json={"login": username, "password": password},
            headers={"Content-Type": "application/json"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        body = token_resp.json()
        token = _extract_token(body)
        if not token:
            raise HTTPException(status_code=502, detail="WordPress JWT response missing token")

        parsed = await _via_simple_jwt_validate(client, token)
        if not parsed:
            parsed = await _via_users_me(client, token)
        if not parsed:
            raise HTTPException(
                status_code=502,
                detail="Could not validate WordPress session",
            )
        uid, roles = parsed
        return WpAuthResult(user_id=uid, roles=roles)


async def fetch_wp_user_id(username: str, password: str) -> int:
    """Backward-compatible wrapper: return WordPress user id only."""
    result = await authenticate_wp_user(username, password)
    return result.user_id
