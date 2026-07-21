"""
Async client for MemberPress REST API (optional live proxy mode).
"""

from __future__ import annotations

from typing import Optional

import httpx

from .config import WP_API_KEY, WP_API_URL

PER_PAGE = 100


class MemberPressClient:
    """Thin wrapper around the MemberPress `/members` HTTP API."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or WP_API_URL).rstrip("/")
        self.api_key = api_key or WP_API_KEY

    def _headers(self) -> dict[str, str]:
        return {"MEMBERPRESS-API-KEY": self.api_key}

    async def get_members(self, page: int = 1, per_page: int = 50) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/members",
                headers=self._headers(),
                params={"page": page, "per_page": per_page},
            )
            resp.raise_for_status()
            return resp.json()


async def fetch_all_members_async(api_url: str, api_key: str) -> list[dict]:
    """Paginate through `/members` and return every record (for proxy listing)."""
    members: list[dict] = []
    page = 1
    total: Optional[int] = None
    api_url = api_url.rstrip("/")

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(
                f"{api_url}/members",
                headers={"MEMBERPRESS-API-KEY": api_key},
                params={"per_page": PER_PAGE, "page": page},
            )
            resp.raise_for_status()

            if total is None:
                total = int(resp.headers.get("X-WP-Total", 0))

            batch = resp.json()
            if not batch:
                break

            members.extend(batch)

            if len(members) >= total:
                break
            page += 1

    return members
