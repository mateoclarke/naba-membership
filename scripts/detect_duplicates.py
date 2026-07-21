"""
Detect likely duplicate directory profile records.

Usage (from repo root):

    python -m scripts.detect_duplicates
    python -m scripts.detect_duplicates --format json --output data/duplicate_report.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from api.db import SessionLocal
from api.models import DirectoryProfile, Member

SPAM_DOMAINS = {"bylup.com"}


@dataclass(frozen=True)
class MemberRecord:
    member_id: int
    display_name: str
    normalized_name: str
    email: str | None
    email_domain: str | None
    status: str | None
    city: str | None
    state_province: str | None
    location_display: str | None
    visibility_public: bool
    opted_in: bool


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(name.lower().strip().split())


def parse_email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[-1].lower().strip() or None


def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            insertion = curr[j - 1] + 1
            deletion = prev[j] + 1
            substitution = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(insertion, deletion, substitution))
        prev = curr
    return prev[-1]


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(a=a, b=b).ratio()


def is_same_city_state(a: MemberRecord, b: MemberRecord) -> bool:
    city_a = (a.city or "").strip().lower()
    city_b = (b.city or "").strip().lower()
    state_a = (a.state_province or "").strip().lower()
    state_b = (b.state_province or "").strip().lower()
    if not city_a or not state_a or not city_b or not state_b:
        return False
    return city_a == city_b and state_a == state_b


def make_member_record(profile: DirectoryProfile, member: Member | None) -> MemberRecord:
    email = (member.email if member else None) or None
    status = (member.status if member else None) or None
    return MemberRecord(
        member_id=profile.member_id,
        display_name=profile.display_name,
        normalized_name=normalize_name(profile.display_name),
        email=email,
        email_domain=parse_email_domain(email),
        status=status,
        city=profile.city,
        state_province=profile.state_province,
        location_display=profile.location_display,
        visibility_public=bool(profile.visibility_public),
        opted_in=bool(profile.opted_in),
    )


def load_records() -> list[MemberRecord]:
    db = SessionLocal()
    try:
        rows = (
            db.query(DirectoryProfile, Member)
            .outerjoin(Member, Member.id == DirectoryProfile.member_id)
            .all()
        )
    finally:
        db.close()
    return [make_member_record(profile, member) for profile, member in rows]


def build_exact_groups(records: list[MemberRecord]) -> list[list[MemberRecord]]:
    by_name: dict[str, list[MemberRecord]] = defaultdict(list)
    for rec in records:
        if rec.normalized_name:
            by_name[rec.normalized_name].append(rec)
    return [group for group in by_name.values() if len(group) > 1]


def build_fuzzy_pairs(
    records: list[MemberRecord],
    min_similarity: float,
    max_distance: int,
) -> list[dict[str, Any]]:
    exact_name_set = {r.normalized_name for group in build_exact_groups(records) for r in group}
    fuzzy_pairs: list[dict[str, Any]] = []
    sorted_records = sorted(records, key=lambda r: r.member_id)
    for i, a in enumerate(sorted_records):
        if not a.normalized_name or a.normalized_name in exact_name_set:
            continue
        for b in sorted_records[i + 1 :]:
            if not b.normalized_name or b.normalized_name in exact_name_set:
                continue
            sim = similarity(a.normalized_name, b.normalized_name)
            dist = levenshtein_distance(a.normalized_name, b.normalized_name)
            if sim >= min_similarity or dist <= max_distance:
                fuzzy_pairs.append(
                    {
                        "member_ids": [a.member_id, b.member_id],
                        "names": [a.display_name, b.display_name],
                        "similarity": round(sim, 3),
                        "levenshtein_distance": dist,
                        "confidence": "low",
                        "reason": "fuzzy_name_match",
                        "suggested_action": "review",
                    }
                )
    return fuzzy_pairs


def classify_group(group: list[MemberRecord]) -> tuple[str, list[str], str]:
    reasons: list[str] = ["exact_name"]

    domains = {r.email_domain for r in group if r.email_domain}
    has_same_domain = len(domains) < len([r for r in group if r.email_domain])
    if has_same_domain:
        reasons.append("same_email_domain")

    has_same_location = False
    for i, a in enumerate(group):
        for b in group[i + 1 :]:
            if is_same_city_state(a, b):
                has_same_location = True
                break
        if has_same_location:
            break
    if has_same_location:
        reasons.append("same_city_state")

    confidence = "high" if (has_same_domain or has_same_location) else "medium"

    spam_hits = [r for r in group if r.email_domain in SPAM_DOMAINS]
    if spam_hits and len(spam_hits) >= max(2, len(group) // 2):
        action = "flag-spam"
    elif any("admin@" in (r.email or "").lower() for r in group):
        action = "keep-both"
    elif any((r.status or "").lower() == "active" for r in group):
        action = "merge"
    else:
        action = "review"
    return confidence, reasons, action


def build_report(records: list[MemberRecord], min_similarity: float, max_distance: int) -> dict[str, Any]:
    exact_groups = []
    for group in build_exact_groups(records):
        ordered = sorted(group, key=lambda r: r.member_id)
        confidence, reasons, suggested_action = classify_group(ordered)
        exact_groups.append(
            {
                "member_ids": [r.member_id for r in ordered],
                "display_name": ordered[0].display_name,
                "confidence": confidence,
                "reasons": reasons,
                "suggested_action": suggested_action,
                "members": [
                    {
                        "id": r.member_id,
                        "name": r.display_name,
                        "email": r.email,
                        "email_domain": r.email_domain,
                        "status": r.status,
                        "city": r.city,
                        "state_province": r.state_province,
                        "location_display": r.location_display,
                        "visibility_public": r.visibility_public,
                        "opted_in": r.opted_in,
                    }
                    for r in ordered
                ],
            }
        )

    fuzzy_pairs = build_fuzzy_pairs(records, min_similarity=min_similarity, max_distance=max_distance)

    spam_accounts = [
        {
            "id": r.member_id,
            "name": r.display_name,
            "email": r.email,
            "email_domain": r.email_domain,
            "status": r.status,
        }
        for r in sorted(records, key=lambda x: x.member_id)
        if r.email_domain in SPAM_DOMAINS
    ]

    return {
        "summary": {
            "total_records": len(records),
            "exact_duplicate_groups": len(exact_groups),
            "exact_duplicate_members_in_groups": sum(len(g["member_ids"]) for g in exact_groups),
            "fuzzy_name_pairs": len(fuzzy_pairs),
            "spam_accounts": len(spam_accounts),
        },
        "exact_name_groups": exact_groups,
        "fuzzy_name_pairs": fuzzy_pairs,
        "spam_accounts": spam_accounts,
    }


def render_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = report["summary"]
    lines.append("Duplicate detection report")
    lines.append("")
    lines.append(f"Total records:                     {summary['total_records']}")
    lines.append(f"Exact duplicate groups:            {summary['exact_duplicate_groups']}")
    lines.append(
        f"Records in exact duplicate groups: {summary['exact_duplicate_members_in_groups']}"
    )
    lines.append(f"Fuzzy name pairs:                  {summary['fuzzy_name_pairs']}")
    lines.append(f"Spam-flagged accounts:             {summary['spam_accounts']}")
    lines.append("")

    lines.append("Exact-name duplicate groups")
    lines.append("---------------------------")
    for idx, group in enumerate(report["exact_name_groups"], start=1):
        lines.append(
            f"{idx:>2}. {group['display_name']} | "
            f"IDs={group['member_ids']} | "
            f"confidence={group['confidence']} | "
            f"action={group['suggested_action']} | "
            f"reasons={', '.join(group['reasons'])}"
        )
        for m in group["members"]:
            loc = m["location_display"] or "-"
            lines.append(
                f"    - id={m['id']} email={m['email'] or '-'} "
                f"status={m['status'] or '-'} loc={loc}"
            )
    lines.append("")

    lines.append("Fuzzy-name pairs")
    lines.append("----------------")
    for pair in report["fuzzy_name_pairs"]:
        lines.append(
            f"- IDs={pair['member_ids']} names={pair['names']} "
            f"similarity={pair['similarity']} distance={pair['levenshtein_distance']}"
        )
    lines.append("")

    lines.append("Spam-flagged accounts")
    lines.append("---------------------")
    for acct in report["spam_accounts"]:
        lines.append(
            f"- id={acct['id']} name={acct['name']} email={acct['email']} "
            f"status={acct['status'] or '-'}"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect duplicate/similar member records.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional file path for output report. Writes stdout when omitted.",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.85,
        help="Minimum normalized similarity for fuzzy matches.",
    )
    parser.add_argument(
        "--max-distance",
        type=int,
        default=2,
        help="Maximum Levenshtein distance for fuzzy matches.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_records()
    report = build_report(
        records,
        min_similarity=args.min_similarity,
        max_distance=args.max_distance,
    )
    if args.format == "json":
        content = json.dumps(report, indent=2) + "\n"
    else:
        content = render_text(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Wrote report to {out_path}")
        return

    print(content)


if __name__ == "__main__":
    main()
