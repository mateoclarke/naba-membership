"""
Dry-run-first duplicate reconciliation helper.

Consumes `data/duplicate_report.json` (from `scripts.detect_duplicates`) and:
- Builds a merge/hide action plan
- Optionally executes updates in `membership.db`
- Transfers enrichment data to the kept primary profile
- Re-links connect messages from merged profile IDs to the kept profile ID

Usage (from repo root):

    # Plan only (default)
    python -m scripts.reconcile_duplicates

    # Execute all non-review actions
    python -m scripts.reconcile_duplicates --execute

    # Execute only spam actions
    python -m scripts.reconcile_duplicates --execute --only-action flag-spam
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.db import SessionLocal
from api.models import ConnectMessage, DirectoryProfile

DEFAULT_REPORT = Path("data/duplicate_report.json")

PRIMARY_ACTIONS = {"merge", "keep-both", "flag-spam"}
NON_REVIEW_ACTIONS = {"merge", "keep-both", "flag-spam"}

ENRICHMENT_FIELDS = [
    "opted_in",
    "opted_in_at",
    "badges_csv",
    "bio",
    "logo_url",
    "gallery_json",
    "phone",
    "social_json",
    "show_city",
    "show_member_since",
    "allow_connect",
    "services_csv",
    "regions_csv",
    "slug",
]


@dataclass(frozen=True)
class GroupAction:
    display_name: str
    confidence: str
    suggested_action: str
    member_ids: list[int]
    keep_id: int | None
    merge_ids: list[int]
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile duplicate profile records.")
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Path to duplicate_report.json",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply updates to the DB. Default is dry-run.",
    )
    parser.add_argument(
        "--only-action",
        choices=["merge", "keep-both", "flag-spam", "review"],
        default=None,
        help="Restrict run to a single suggested_action from report.",
    )
    parser.add_argument(
        "--max-groups",
        type=int,
        default=None,
        help="Limit number of groups processed (for controlled rollouts).",
    )
    return parser.parse_args()


def choose_keep_id(group: dict[str, Any]) -> int | None:
    members = group.get("members") or []
    if not members:
        return None

    # Rank by active status, opted_in, visibility_public, highest ID (newer).
    def rank(m: dict[str, Any]) -> tuple[int, int, int, int]:
        is_active = 1 if (m.get("status") or "").lower() == "active" else 0
        opted_in = 1 if bool(m.get("opted_in")) else 0
        visible = 1 if bool(m.get("visibility_public")) else 0
        return (is_active, opted_in, visible, int(m.get("id") or 0))

    best = sorted(members, key=rank, reverse=True)[0]
    return int(best["id"])


def build_plan(report: dict[str, Any], only_action: str | None, max_groups: int | None) -> list[GroupAction]:
    groups = report.get("exact_name_groups") or []
    planned: list[GroupAction] = []
    for group in groups:
        action = (group.get("suggested_action") or "review").strip()
        if only_action and action != only_action:
            continue
        if action not in PRIMARY_ACTIONS and action != "review":
            continue

        member_ids = [int(mid) for mid in (group.get("member_ids") or [])]
        if len(member_ids) < 2:
            continue

        keep_id = choose_keep_id(group)
        merge_ids = [mid for mid in member_ids if keep_id is not None and mid != keep_id]
        reason = ", ".join(group.get("reasons") or [])
        planned.append(
            GroupAction(
                display_name=group.get("display_name") or "Unknown",
                confidence=group.get("confidence") or "unknown",
                suggested_action=action,
                member_ids=member_ids,
                keep_id=keep_id,
                merge_ids=merge_ids,
                reason=reason,
            )
        )

    if max_groups is not None:
        return planned[:max_groups]
    return planned


def profile_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def transfer_enrichment(primary: DirectoryProfile, secondary: DirectoryProfile) -> int:
    copied = 0
    for field in ENRICHMENT_FIELDS:
        primary_value = getattr(primary, field)
        secondary_value = getattr(secondary, field)
        if profile_is_empty(primary_value) and not profile_is_empty(secondary_value):
            setattr(primary, field, secondary_value)
            copied += 1
    return copied


def apply_group_action(db, action: GroupAction) -> dict[str, int]:
    stats = {
        "profiles_hidden": 0,
        "profiles_opted_out": 0,
        "fields_transferred": 0,
        "messages_relinked": 0,
        "groups_skipped": 0,
    }

    if action.suggested_action == "review":
        stats["groups_skipped"] += 1
        return stats

    if action.keep_id is None:
        stats["groups_skipped"] += 1
        return stats

    primary = db.query(DirectoryProfile).filter_by(member_id=action.keep_id).first()
    if primary is None:
        stats["groups_skipped"] += 1
        return stats

    # keep-both: no hiding/merging, but still keep as reviewed candidate in output.
    if action.suggested_action == "keep-both":
        return stats

    for merge_id in action.merge_ids:
        secondary = db.query(DirectoryProfile).filter_by(member_id=merge_id).first()
        if secondary is None:
            continue

        stats["fields_transferred"] += transfer_enrichment(primary, secondary)

        if secondary.visibility_public:
            secondary.visibility_public = False
            stats["profiles_hidden"] += 1
        if secondary.opted_in:
            secondary.opted_in = False
            stats["profiles_opted_out"] += 1

        relinked = (
            db.query(ConnectMessage)
            .filter(ConnectMessage.recipient_profile_id == merge_id)
            .update({"recipient_profile_id": action.keep_id}, synchronize_session=False)
        )
        stats["messages_relinked"] += int(relinked)

    return stats


def print_plan(plan: list[GroupAction], execute: bool) -> None:
    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"Reconcile duplicates plan ({mode})")
    print("")
    for idx, item in enumerate(plan, start=1):
        print(
            f"{idx:>2}. {item.display_name} | action={item.suggested_action} | "
            f"confidence={item.confidence} | keep={item.keep_id} | merge={item.merge_ids} | "
            f"reason={item.reason}"
        )
    print("")


def main() -> None:
    args = parse_args()
    if not args.report.exists():
        raise SystemExit(f"Report not found: {args.report}")

    report = json.loads(args.report.read_text(encoding="utf-8"))
    plan = build_plan(
        report=report,
        only_action=args.only_action,
        max_groups=args.max_groups,
    )
    print_plan(plan, execute=args.execute)

    total = {
        "groups_total": len(plan),
        "groups_applied": 0,
        "groups_skipped": 0,
        "profiles_hidden": 0,
        "profiles_opted_out": 0,
        "fields_transferred": 0,
        "messages_relinked": 0,
    }

    if not args.execute:
        actionable = [p for p in plan if p.suggested_action in NON_REVIEW_ACTIONS]
        review = [p for p in plan if p.suggested_action == "review"]
        print(f"Actionable groups (non-review): {len(actionable)}")
        print(f"Review groups:                  {len(review)}")
        print("")
        print("Dry-run complete. Re-run with --execute to apply DB changes.")
        return

    db = SessionLocal()
    try:
        for item in plan:
            stats = apply_group_action(db, item)
            if item.suggested_action in NON_REVIEW_ACTIONS:
                total["groups_applied"] += 1
            total["groups_skipped"] += stats["groups_skipped"]
            total["profiles_hidden"] += stats["profiles_hidden"]
            total["profiles_opted_out"] += stats["profiles_opted_out"]
            total["fields_transferred"] += stats["fields_transferred"]
            total["messages_relinked"] += stats["messages_relinked"]
        db.commit()
    finally:
        db.close()

    print("Apply complete.")
    print(f"  Groups processed:     {total['groups_total']}")
    print(f"  Groups applied:       {total['groups_applied']}")
    print(f"  Groups skipped:       {total['groups_skipped']}")
    print(f"  Profiles hidden:      {total['profiles_hidden']}")
    print(f"  Profiles opted out:   {total['profiles_opted_out']}")
    print(f"  Fields transferred:   {total['fields_transferred']}")
    print(f"  Messages re-linked:   {total['messages_relinked']}")


if __name__ == "__main__":
    main()
