"""
Sync the local membership database from the MemberPress REST API.

Uses a merge/upsert strategy: WP-sourced fields are updated, but
locally-managed enrichment fields (badges, bio, opt-in, gallery, etc.)
are preserved across syncs.

Usage (from repo root):

    npx varlock run -- python -m scripts.sync_from_wordpress
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

import requests

from api.db import SessionLocal, Base, engine, ensure_member_subscriptions_column
from api.models import Member, DirectoryProfile

WP_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
PER_PAGE = 100
_LIFETIME_EXPIRES = {"", "0000-00-00", "0000-00-00 00:00:00"}
_TXN_OK_STATUSES = {"complete", "confirmed"}


def build_location_display(
    city: str | None, state: str | None, country: str | None
) -> str | None:
    parts = [p for p in [city, state] if p]
    tail = country or ""
    if parts and tail:
        return f"{', '.join(parts)} ({tail})"
    if parts:
        return ", ".join(parts)
    if tail:
        return tail
    return None


def empty_to_none(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    return value.strip()


def parse_wp_datetime(value: str | None) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, WP_DATETIME_FMT)
    except ValueError:
        return None


def txn_is_real(txn: dict | None) -> bool:
    """A transaction blob with member=0 or missing id is a placeholder."""
    if not txn:
        return False
    try:
        return int(txn.get("member") or 0) > 0
    except (ValueError, TypeError):
        return False


def derive_status(data: dict) -> str:
    try:
        if int(data.get("active_txn_count") or 0) > 0:
            return "active"
    except (ValueError, TypeError):
        pass
    try:
        if int(data.get("expired_txn_count") or 0) > 0:
            return "expired"
    except (ValueError, TypeError):
        pass
    return "none"


def _safe_int(value) -> int | None:
    try:
        n = int(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_expires_at(raw: str | None) -> tuple[str | None, bool]:
    """Return (expires_at ISO-ish string or None, is_lifetime)."""
    value = (raw or "").strip()
    if value in _LIFETIME_EXPIRES:
        return None, True
    dt = parse_wp_datetime(value)
    if not dt:
        return None, False
    return dt.strftime("%Y-%m-%dT%H:%M:%S"), False


def _txn_expires_candidates(
    txns: list[dict],
    *,
    subscription_id: str | None = None,
    membership_id: str | None = None,
) -> list[tuple[str | None, bool]]:
    out: list[tuple[str | None, bool]] = []
    for txn in txns:
        if not isinstance(txn, dict):
            continue
        status = (txn.get("status") or "").strip().lower()
        if status and status not in _TXN_OK_STATUSES:
            continue
        if subscription_id is not None:
            if str(txn.get("subscription") or "") != subscription_id:
                continue
        elif membership_id is not None:
            if str(txn.get("membership") or "") != membership_id:
                continue
        else:
            continue
        out.append(_parse_expires_at(txn.get("expires_at")))
    return out


def _pick_best_expires(
    candidates: list[tuple[str | None, bool]],
) -> tuple[str | None, bool]:
    if not candidates:
        return None, False
    if any(is_life for _, is_life in candidates):
        return None, True
    dated = [exp for exp, is_life in candidates if exp and not is_life]
    if not dated:
        return None, False
    return max(dated), False


def build_subscriptions(data: dict) -> list[dict]:
    """Normalize MemberPress member payload into profile-facing subscription rows."""
    titles: dict[str, str] = {}
    for m in data.get("active_memberships") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "")
        title = (m.get("title") or "").strip()
        if mid and title:
            titles[mid] = title

    txns = [
        t
        for t in (data.get("recent_transactions") or [])
        if isinstance(t, dict)
    ]
    latest = data.get("latest_txn")
    if txn_is_real(latest) and isinstance(latest, dict):
        lid = str(latest.get("id") or "")
        if lid and not any(str(t.get("id") or "") == lid for t in txns):
            txns = [latest] + txns

    items: list[dict] = []
    seen_membership_ids: set[str] = set()

    for sub in data.get("recent_subscriptions") or []:
        if not isinstance(sub, dict):
            continue
        mid = str(sub.get("membership") or "")
        sid = str(sub.get("id") or "")
        expires_at, is_lifetime = _pick_best_expires(
            _txn_expires_candidates(txns, subscription_id=sid or None)
            or _txn_expires_candidates(txns, membership_id=mid or None)
        )
        title = titles.get(mid) or (f"Membership {mid}" if mid else "Membership")
        status = (sub.get("status") or "").strip().lower() or "unknown"
        period = sub.get("period")
        items.append(
            {
                "membership_id": _safe_int(mid),
                "subscription_id": _safe_int(sid),
                "title": title,
                "status": status,
                "period": str(period) if period is not None and str(period) != "" else None,
                "period_type": empty_to_none(str(sub.get("period_type") or "")),
                "created_at": (
                    parse_wp_datetime(sub.get("created_at")).strftime("%Y-%m-%dT%H:%M:%S")
                    if parse_wp_datetime(sub.get("created_at"))
                    else None
                ),
                "expires_at": expires_at,
                "is_lifetime": is_lifetime,
            }
        )
        if mid:
            seen_membership_ids.add(mid)

    for m in data.get("active_memberships") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "")
        if not mid or mid in seen_membership_ids:
            continue
        expires_at, is_lifetime = _pick_best_expires(
            _txn_expires_candidates(txns, membership_id=mid)
        )
        period = m.get("period")
        items.append(
            {
                "membership_id": _safe_int(mid),
                "subscription_id": None,
                "title": (m.get("title") or "").strip() or f"Membership {mid}",
                "status": "active",
                "period": str(period) if period is not None and str(period) != "" else None,
                "period_type": empty_to_none(str(m.get("period_type") or "")),
                "created_at": None,
                "expires_at": expires_at,
                "is_lifetime": is_lifetime,
            }
        )
        seen_membership_ids.add(mid)

    if not items and txn_is_real(latest) and isinstance(latest, dict):
        mid = str(latest.get("membership") or "")
        expires_at, is_lifetime = _parse_expires_at(latest.get("expires_at"))
        member_status = derive_status(data)
        txn_status = (latest.get("status") or "").strip().lower() or "unknown"
        status = member_status if member_status in ("active", "expired") else txn_status
        items.append(
            {
                "membership_id": _safe_int(mid),
                "subscription_id": _safe_int(latest.get("subscription")),
                "title": titles.get(mid) or (f"Membership {mid}" if mid else "Membership"),
                "status": status,
                "period": None,
                "period_type": None,
                "created_at": (
                    parse_wp_datetime(latest.get("created_at")).strftime("%Y-%m-%dT%H:%M:%S")
                    if parse_wp_datetime(latest.get("created_at"))
                    else None
                ),
                "expires_at": expires_at,
                "is_lifetime": is_lifetime,
            }
        )

    return items


def derive_entry_type(membership_titles: list[str]) -> str:
    for title in membership_titles:
        upper = title.upper()
        if "SPONSOR" in upper or "VENDOR" in upper:
            return "business"
    return "individual"


def clean_membership_title(raw_title: str) -> str:
    return raw_title.strip().title()


def derive_tags(membership_titles: list[str], country: str | None) -> str | None:
    tags: list[str] = []
    for title in membership_titles:
        upper = title.upper()
        if "INDIVIDUAL" in upper:
            tags.append("individual")
        elif "PROFESSIONAL" in upper:
            tags.append("professional")
        elif "STUDENT" in upper:
            tags.append("student")
        elif "SPONSOR" in upper:
            tags.append("sponsor")
        elif "VENDOR" in upper:
            tags.append("vendor")
        elif "DONATION" in upper or "COAT" in upper:
            tags.append("donor")
    if country and country.upper() != "US":
        tags.append(country)
    return ", ".join(tags) if tags else None


def looks_like_url(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    v = value.strip()
    if re.match(r"https?://", v, re.IGNORECASE):
        return v
    return None


def fetch_all_members(api_url: str, api_key: str) -> list[dict]:
    """Paginate through the /members endpoint and return all records."""
    members: list[dict] = []
    page = 1
    total = None

    while True:
        resp = requests.get(
            f"{api_url.rstrip('/')}/members",
            params={"per_page": PER_PAGE, "page": page},
            headers={"MEMBERPRESS-API-KEY": api_key},
            timeout=30,
        )
        resp.raise_for_status()

        if total is None:
            total = int(resp.headers.get("X-WP-Total", 0))

        batch = resp.json()
        if not batch:
            break

        members.extend(batch)
        print(f"  Fetched page {page} ({len(batch)} members)")

        if len(members) >= total:
            break
        page += 1

    return members


def map_member(data: dict) -> Member:
    addr = data.get("address") or {}
    subscriptions = build_subscriptions(data)

    return Member(
        id=data["id"],
        first_name=empty_to_none(data.get("first_name")),
        last_name=empty_to_none(data.get("last_name")),
        email=empty_to_none(data.get("email")),
        status=derive_status(data),
        memberships_raw=", ".join(
            m["title"] for m in (data.get("active_memberships") or [])
            if isinstance(m, dict) and m.get("title")
        )
        or None,
        subscriptions_json=json.dumps(subscriptions) if subscriptions else None,
        registered_at=parse_wp_datetime(data.get("registered_at")),
        first_txn_at=(
            parse_wp_datetime(data["first_txn"].get("created_at"))
            if txn_is_real(data.get("first_txn"))
            else None
        ),
        latest_txn_at=(
            parse_wp_datetime(data["latest_txn"].get("created_at"))
            if txn_is_real(data.get("latest_txn"))
            else None
        ),
        city=empty_to_none(addr.get("mepr-address-city")),
        state_province=empty_to_none(addr.get("mepr-address-state")),
        country=empty_to_none(addr.get("mepr-address-country")),
    )


def map_profile(data: dict, member: Member) -> DirectoryProfile:
    active_memberships = data.get("active_memberships") or []
    membership_titles = [m["title"] for m in active_memberships]
    profile_data = data.get("profile") or {}

    first = empty_to_none(data.get("first_name"))
    last = empty_to_none(data.get("last_name"))
    name_parts = [p for p in [first, last] if p]
    display_name = (
        " ".join(name_parts)
        if name_parts
        else (empty_to_none(data.get("display_name")) or "Member")
    )

    role = clean_membership_title(membership_titles[0]) if membership_titles else None
    org = empty_to_none(profile_data.get("mepr_company_name"))

    first_txn_at = (
        parse_wp_datetime(data["first_txn"].get("created_at"))
        if txn_is_real(data.get("first_txn"))
        else None
    )
    registered_at = parse_wp_datetime(data.get("registered_at"))
    ts = first_txn_at or registered_at
    member_since_year = ts.year if ts else None

    location_display = build_location_display(
        member.city, member.state_province, member.country
    )

    return DirectoryProfile(
        id=data["id"],
        member_id=data["id"],
        display_name=display_name,
        entry_type=derive_entry_type(membership_titles),
        role=role,
        organization=org,
        city=member.city,
        state_province=member.state_province,
        country=member.country,
        location_display=location_display,
        website_url=looks_like_url(data.get("url")),
        tags_csv=derive_tags(membership_titles, member.country),
        member_since_year=member_since_year,
        visibility_public=(member.status == "active"),
    )


# ── WP-sourced fields that get overwritten on every sync ──

_MEMBER_WP_FIELDS = [
    "first_name", "last_name", "email", "status", "memberships_raw",
    "subscriptions_json",
    "registered_at", "first_txn_at", "latest_txn_at",
    "city", "state_province", "country",
]

_PROFILE_WP_FIELDS = [
    "display_name", "entry_type", "role",
    "city", "state_province", "country", "location_display",
    "member_since_year", "visibility_public",
]


def upsert_member(db, data: dict) -> tuple[Member, bool]:
    """Insert or update a Member row. Returns (member, is_new)."""
    wp_id = data["id"]
    existing = db.get(Member, wp_id)
    mapped = map_member(data)

    if existing:
        for field in _MEMBER_WP_FIELDS:
            setattr(existing, field, getattr(mapped, field))
        return existing, False

    db.add(mapped)
    return mapped, True


def upsert_profile(db, data: dict, member: Member) -> tuple[DirectoryProfile, bool]:
    """Insert or update a DirectoryProfile row. Returns (profile, is_new).

    Enrichment fields (opted_in, badges_csv, bio, gallery, etc.) are
    preserved on existing rows — only WP-sourced fields are overwritten.
    """
    existing = db.query(DirectoryProfile).filter_by(member_id=member.id).first()
    mapped = map_profile(data, member)

    if existing:
        for field in _PROFILE_WP_FIELDS:
            setattr(existing, field, getattr(mapped, field))

        if existing.organization is None:
            existing.organization = mapped.organization
        if existing.website_url is None:
            existing.website_url = mapped.website_url
        if existing.tags_csv is None:
            existing.tags_csv = mapped.tags_csv

        return existing, False

    db.add(mapped)
    return mapped, True


def main() -> None:
    api_url = os.environ.get("WP_API_URL")
    api_key = os.environ.get("WP_API_KEY")

    if not api_url or not api_key:
        raise SystemExit(
            "WP_API_URL and WP_API_KEY must be set in the environment. "
            "Use Varlock (npx varlock run -- python -m scripts.sync_from_wordpress) "
            "or export them before running."
        )

    print(f"Syncing from {api_url} ...")
    try:
        all_members = fetch_all_members(api_url, api_key)
    except requests.exceptions.ConnectionError as e:
        raise SystemExit(
            f"Could not connect to WordPress MemberPress API at {api_url!r}. "
            f"Check the URL and network. ({e})"
        ) from e
    except requests.exceptions.HTTPError as e:
        resp = e.response
        status = getattr(resp, "status_code", None)
        body = (getattr(resp, "text", None) or "").strip()
        snippet = (body[:400] + "…") if len(body) > 400 else body
        detail = f" HTTP {status}" if status else ""
        if snippet:
            detail += f": {snippet}"
        raise SystemExit(
            "MemberPress API request failed"
            f"{detail}. "
            "Verify WP_API_URL points to the REST base (e.g. …/wp-json/mp/v1) "
            "and WP_API_KEY is a valid MEMBERPRESS-API-KEY."
        ) from e
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"WordPress API request failed: {e}") from e
    print(f"Fetched {len(all_members)} total members from API.\n")

    Base.metadata.create_all(bind=engine)
    ensure_member_subscriptions_column(engine)

    db = SessionLocal()
    try:
        wp_ids: set[int] = set()
        created_members = 0
        updated_members = 0
        created_profiles = 0
        updated_profiles = 0
        skipped = 0

        for data in all_members:
            wp_id = data.get("id")
            if not wp_id:
                skipped += 1
                continue

            wp_ids.add(wp_id)

            member, is_new_member = upsert_member(db, data)
            if is_new_member:
                created_members += 1
            else:
                updated_members += 1

            _, is_new_profile = upsert_profile(db, data, member)
            if is_new_profile:
                created_profiles += 1
            else:
                updated_profiles += 1

        orphaned = 0
        if wp_ids:
            orphans = db.query(DirectoryProfile).filter(
                ~DirectoryProfile.member_id.in_(wp_ids)
            ).all()
            for orphan in orphans:
                if orphan.visibility_public:
                    orphan.visibility_public = False
                    orphaned += 1

        db.commit()

        print("Sync complete.")
        print(f"  Members created:   {created_members}")
        print(f"  Members updated:   {updated_members}")
        print(f"  Profiles created:  {created_profiles}")
        print(f"  Profiles updated:  {updated_profiles}")
        print(f"  Skipped (no ID):   {skipped}")
        if orphaned:
            print(f"  Orphaned (hidden): {orphaned}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
