"""
Seed opt-in status, badges, logos, and demo business entries.

Idempotent — safe to run multiple times. Only sets values; does not
clear existing enrichment data on other members.

Usage (from repo root):

    python -m scripts.seed_enrichment
"""

from __future__ import annotations

from datetime import datetime

from api.db import SessionLocal, Base, engine
from api.models import BusinessMember, Member, DirectoryProfile

OPTED_IN_DATE = datetime(2026, 3, 21)

NBA_LOGO_BASE = "https://natural-building-alliance.org/wp-content/uploads/2019/03"

OPTIN_AND_BADGES: list[dict] = [
    {"id": 1,   "name": "Jean Lotus",     "opted_in": True, "badges": "staff"},
    {"id": 18,  "name": "David Kaplan",   "opted_in": True, "badges": "board"},
    {"id": 24,  "name": "Mark Jensen",    "opted_in": True, "badges": "board"},
    {"id": 111, "name": "Kenny Fallon",   "opted_in": True, "badges": "former board"},
    {"id": 27,  "name": "Liz Johndrow",   "opted_in": True, "badges": None},
    {"id": 158, "name": "Susan Klinker",  "opted_in": True, "badges": "board"},
    {"id": 93,  "name": "Lindsey Love",   "opted_in": True, "badges": "board"},
    {"id": 372, "name": "Mateo Clarke",   "opted_in": True, "badges": "board"},
    {"id": 545, "name": "Laura Clarke",   "opted_in": True, "badges": None},
    {"id": 259, "name": "Kluane Gorsuch", "opted_in": True, "badges": "board"},
    {
        "id": 364, "name": "Living Craft", "opted_in": True, "badges": None,
        "entry_type": "business",
        "logo_url": f"{NBA_LOGO_BASE}/NBA_Sponsor_Logo-Living-Craft.png",
    },
    {"id": 442, "name": "David Arkin and Anni Tilt", "opted_in": True, "badges": None},
    {"id": 47, "name": "Ian Smith", "opted_in": True, "badges": None},
    {"id": 592, "name": "Lotus Grenier", "opted_in": True, "badges": None},
    {
        "id": 428, "name": "Love Schack Architecture", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Love Schack Architecture", "tags_csv": "sponsor",
    },
    {
        "id": 563, "name": "Durra Panel USA", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Durra Panel USA", "tags_csv": "sponsor",
    },
    {
        "id": 564, "name": "Durra Panel USA", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Durra Panel USA", "tags_csv": "sponsor",
    },
    {
        "id": 162, "name": "Anthony Dente", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Verdant Structural", "tags_csv": "sponsor",
    },
    {
        "id": 599, "name": "Thomas Gibbons", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Hempitecture", "tags_csv": "sponsor",
    },
    {
        "id": 475, "name": "David Rosprim", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Silacote", "tags_csv": "sponsor",
    },
    {
        "id": 462, "name": "Tyler Survant", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Building Bureau", "tags_csv": "sponsor",
    },
    {
        "id": 370, "name": "Enrico Bonilauri", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Emu Passive", "tags_csv": "sponsor",
    },
    {
        "id": 359, "name": "James Henderson", "opted_in": True, "badges": None,
        "entry_type": "business", "organization": "Gold Hill Clay Plaster", "tags_csv": "sponsor",
    },
]

DEMO_BUSINESSES: list[dict] = [
    {
        "id": 9000,
        "display_name": "Elevated Design Build",
        "entry_type": "business",
        "role": "Professional Membership",
        "organization": "Elevated Design Build",
        "website_url": "https://elevateddesignbuild.com",
        "tags_csv": "professional",
        "logo_url": "https://elevateddesignbuild.com/wp-content/uploads/2025/04/Logo.svg",
        "bio": "Eco-friendly custom home design, timber framing, and green building services based in Fort Collins, Colorado.",
    },
    {
        "id": 9001,
        "display_name": "The Last Straw",
        "entry_type": "business",
        "role": "Sponsor",
        "organization": "The Last Straw Journal",
        "logo_url": "https://www.thelaststraw.org/wp-content/uploads/2023/05/logo_egg_2023_dark.png",
        "bio": "The Last Straw is a magazine founded in 1992 focused on natural building and alternative design.",
        "website_url": "https://www.thelaststraw.org",
        "tags_csv": "sponsor",
    },
    {
        "id": 9002,
        "display_name": "Caddis Collaborative",
        "entry_type": "business",
        "role": "Professional Membership",
        "organization": "Caddis Collaborative",
        "website_url": "https://caddispc.com",
        "tags_csv": "professional",
        "logo_url": "https://caddispc.com/wp-content/uploads/2024/04/caddis-logo-horz-spaced.png",
        "bio": "Architecture, urban design, and planning firm focused on sustainable design, net-zero energy buildings, and livable communities.",
    },
    {
        "id": 9003,
        "display_name": "Earthaus Plaster",
        "entry_type": "business",
        "role": "Professional Membership",
        "organization": "Earthaus Plaster",
        "website_url": "https://earthausplaster.com",
        "tags_csv": "professional",
        "logo_url": "https://earthausplaster.com/cdn/shop/files/Earthaus_Logo_Variations_wordmark_charcoal_1200x1200.png",
        "bio": "Natural lime plaster finishes for healthy homes, including interior and exterior mineral-based products and resources.",
    },
    {
        "id": 364,
        "display_name": "Living Craft",
        "entry_type": "business",
        "role": "Professional Membership",
        "organization": "Living Craft",
        "website_url": "https://livingcraft.com",
        "tags_csv": "professional",
        "logo_url": f"{NBA_LOGO_BASE}/NBA_Sponsor_Logo-Living-Craft.png",
        "bio": "Colorado design-build team delivering high-performance, healthy homes and renovations with passive house expertise.",
    },
    {
        "id": 9004,
        "display_name": "475 Supply",
        "entry_type": "business",
        "role": "Sponsor",
        "organization": "475 Supply",
        "website_url": "https://475.supply",
        "tags_csv": "sponsor",
        "phone": "800-995-6329",
        "bio": "Building materials supplier focused on high-performance and resilient enclosures.",
    },
    {
        "id": 9005,
        "display_name": "Faswall",
        "entry_type": "business",
        "role": "Sponsor",
        "organization": "Faswall",
        "website_url": "https://faswall.com",
        "tags_csv": "sponsor",
        "phone": "(541) 908-6903",
    },
    {
        "id": 9006,
        "display_name": "Clearwater Credit Union",
        "entry_type": "business",
        "role": "Sponsor",
        "organization": "Clearwater Credit Union",
        "website_url": "https://clearwatercreditunion.org",
        "tags_csv": "sponsor",
        "phone": "406-493-3357",
    },
    {
        "id": 9007,
        "display_name": "IND HEMP",
        "entry_type": "business",
        "role": "Sponsor",
        "organization": "IND HEMP",
        "website_url": "https://www.indhemp.com",
        "tags_csv": "sponsor",
        "phone": "(406) 622-5680",
    },
    {
        "id": 9008,
        "display_name": "Hempitecture",
        "entry_type": "business",
        "role": "Sponsor",
        "organization": "Hempitecture",
        "website_url": "https://hempitecture.com",
        "tags_csv": "sponsor",
    },
    {
        "id": 9009,
        "display_name": "Thruline Partners",
        "entry_type": "business",
        "role": "Sponsor",
        "organization": "Thruline Partners",
        "website_url": "https://thrulinepartners.com",
        "tags_csv": "sponsor",
        "phone": "(406) 414-7744",
    },
]

BUSINESS_MEMBER_LINKS: list[dict] = [
    {"business_profile_id": 9009, "member_profile_id": 592, "role_in_business": "Owner", "can_edit": True},
    {"business_profile_id": 9008, "member_profile_id": 9102, "role_in_business": None, "can_edit": True},
    {"business_profile_id": 9008, "member_profile_id": 9103, "role_in_business": "Partner", "can_edit": True},
    {"business_profile_id": 9008, "member_profile_id": 9104, "role_in_business": None, "can_edit": True},
]

CONTACT_INDIVIDUALS: list[dict] = [
    {"id": 9102, "display_name": "Thomas Gibbons", "email": "Tommy@hempitecture.com"},
    {"id": 9103, "display_name": "Anthony Dente", "email": "anthony@verdantstructural.com"},
    {"id": 9104, "display_name": "Mattie Mead", "email": "mattie@hempitecture.com"},
]


def _update_existing_profiles(db) -> tuple[int, int]:
    updated = 0
    not_found = 0

    for entry in OPTIN_AND_BADGES:
        profile = db.get(DirectoryProfile, entry["id"])
        if not profile:
            print(f"  SKIP  id={entry['id']} ({entry['name']}) — profile not found")
            not_found += 1
            continue

        changed = []

        if entry["opted_in"] and not profile.opted_in:
            profile.opted_in = True
            profile.opted_in_at = OPTED_IN_DATE
            changed.append("opted_in")
        elif entry["opted_in"] and profile.opted_in:
            changed.append("opted_in (already set)")

        override_type = entry.get("entry_type")
        if override_type and profile.entry_type != override_type:
            profile.entry_type = override_type
            changed.append(f"entry_type={override_type}")
        elif override_type:
            changed.append(f"entry_type={override_type} (already set)")

        badges = entry.get("badges")
        if badges and profile.badges_csv != badges:
            profile.badges_csv = badges
            changed.append(f"badges={badges}")
        elif badges and profile.badges_csv == badges:
            changed.append(f"badges={badges} (already set)")

        logo = entry.get("logo_url")
        organization = entry.get("organization")
        if organization and profile.organization != organization:
            profile.organization = organization
            changed.append("organization")
        elif organization and profile.organization == organization:
            changed.append("organization (already set)")

        tags_csv = entry.get("tags_csv")
        if tags_csv and profile.tags_csv != tags_csv:
            profile.tags_csv = tags_csv
            changed.append("tags_csv")
        elif tags_csv and profile.tags_csv == tags_csv:
            changed.append("tags_csv (already set)")

        if logo and profile.logo_url != logo:
            profile.logo_url = logo
            changed.append("logo_url")
        elif logo and profile.logo_url == logo:
            changed.append("logo_url (already set)")

        status = "UPDATE" if any("already" not in c for c in changed) else "NOOP"
        print(f"  {status:6}  id={entry['id']:<4} {entry['name']:<20} {', '.join(changed)}")
        if status == "UPDATE":
            updated += 1

    return updated, not_found


def _create_demo_businesses(db) -> int:
    created = 0

    for biz in DEMO_BUSINESSES:
        existing_member = db.get(Member, biz["id"])
        existing_profile = db.get(DirectoryProfile, biz["id"])

        if existing_profile:
            changed = []
            if existing_profile.display_name != biz["display_name"]:
                existing_profile.display_name = biz["display_name"]
                changed.append("display_name")
            if existing_profile.entry_type != biz["entry_type"]:
                existing_profile.entry_type = biz["entry_type"]
                changed.append("entry_type")
            if existing_profile.role != biz.get("role"):
                existing_profile.role = biz.get("role")
                changed.append("role")
            if existing_profile.organization != biz.get("organization"):
                existing_profile.organization = biz.get("organization")
                changed.append("organization")
            if existing_profile.website_url != biz.get("website_url"):
                existing_profile.website_url = biz.get("website_url")
                changed.append("website_url")
            if existing_profile.tags_csv != biz.get("tags_csv"):
                existing_profile.tags_csv = biz.get("tags_csv")
                changed.append("tags_csv")
            if existing_profile.phone != biz.get("phone"):
                existing_profile.phone = biz.get("phone")
                changed.append("phone")
            # Do not clear optional fields when omitted from the demo dict.
            if biz.get("logo_url") is not None and existing_profile.logo_url != biz["logo_url"]:
                existing_profile.logo_url = biz["logo_url"]
                changed.append("logo_url")
            if biz.get("bio") is not None and existing_profile.bio != biz["bio"]:
                existing_profile.bio = biz["bio"]
                changed.append("bio")
            if not existing_profile.visibility_public:
                existing_profile.visibility_public = True
                changed.append("visibility_public")
            if not existing_profile.opted_in:
                existing_profile.opted_in = True
                existing_profile.opted_in_at = OPTED_IN_DATE
                changed.append("opted_in")
            if changed:
                print(f"  UPDATE  id={biz['id']:<4} {biz['display_name']:<20} {', '.join(changed)}")
            else:
                print(f"  NOOP    id={biz['id']:<4} {biz['display_name']:<20} (already exists)")
            continue

        if not existing_member:
            member = Member(
                id=biz["id"],
                first_name=biz["display_name"],
                status="active",
            )
            db.add(member)

        profile = DirectoryProfile(
            id=biz["id"],
            member_id=biz["id"],
            display_name=biz["display_name"],
            entry_type=biz["entry_type"],
            role=biz.get("role"),
            organization=biz.get("organization"),
            website_url=biz.get("website_url"),
            tags_csv=biz.get("tags_csv"),
            logo_url=biz.get("logo_url"),
            bio=biz.get("bio"),
            phone=biz.get("phone"),
            visibility_public=True,
            opted_in=True,
            opted_in_at=OPTED_IN_DATE,
        )
        db.add(profile)
        created += 1
        print(f"  CREATE  id={biz['id']:<4} {biz['display_name']:<20} (demo business)")

    return created


def _ensure_contact_individual_profiles(db) -> int:
    created = 0
    for person in CONTACT_INDIVIDUALS:
        member = db.get(Member, person["id"])
        profile = db.get(DirectoryProfile, person["id"])
        if member is None:
            member = Member(
                id=person["id"],
                first_name=person["display_name"],
                email=person.get("email"),
                status="active",
            )
            db.add(member)
        if profile is None:
            profile = DirectoryProfile(
                id=person["id"],
                member_id=person["id"],
                display_name=person["display_name"],
                entry_type="individual",
                role="Member",
                visibility_public=True,
                opted_in=True,
                opted_in_at=OPTED_IN_DATE,
            )
            db.add(profile)
            created += 1
            print(f"  CREATE  id={person['id']:<4} {person['display_name']:<20} (contact individual)")
        else:
            changed = []
            if profile.display_name != person["display_name"]:
                profile.display_name = person["display_name"]
                changed.append("display_name")
            if profile.entry_type != "individual":
                profile.entry_type = "individual"
                changed.append("entry_type")
            if not profile.opted_in:
                profile.opted_in = True
                profile.opted_in_at = OPTED_IN_DATE
                changed.append("opted_in")
            if changed:
                print(f"  UPDATE  id={person['id']:<4} {person['display_name']:<20} {', '.join(changed)}")
            else:
                print(f"  NOOP    id={person['id']:<4} {person['display_name']:<20} (already exists)")
    return created


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        updated, not_found = _update_existing_profiles(db)
        created = _create_demo_businesses(db)
        created_contacts = _ensure_contact_individual_profiles(db)
        db.flush()

        linked = 0
        for link in BUSINESS_MEMBER_LINKS:
            business = db.get(DirectoryProfile, link["business_profile_id"])
            member = db.get(DirectoryProfile, link["member_profile_id"])
            if business is None or member is None:
                print(
                    f"  SKIP  link business={link['business_profile_id']} member={link['member_profile_id']} — profile missing"
                )
                continue
            if business.entry_type != "business":
                print(f"  SKIP  link business={business.id} member={member.id} — business is not entry_type=business")
                continue
            if member.entry_type != "individual":
                print(f"  SKIP  link business={business.id} member={member.id} — member is not entry_type=individual")
                continue
            exists = db.query(BusinessMember).filter(
                BusinessMember.business_profile_id == link["business_profile_id"],
                BusinessMember.member_profile_id == link["member_profile_id"],
            ).first()
            if exists:
                if exists.role_in_business != link.get("role_in_business"):
                    exists.role_in_business = link.get("role_in_business")
                if exists.can_edit != bool(link.get("can_edit")):
                    exists.can_edit = bool(link.get("can_edit"))
                print(f"  NOOP    link business={business.id} member={member.id}")
            else:
                db.add(
                    BusinessMember(
                        business_profile_id=business.id,
                        member_profile_id=member.id,
                        role_in_business=link.get("role_in_business"),
                        can_edit=bool(link.get("can_edit")),
                        created_at=OPTED_IN_DATE,
                    )
                )
                linked += 1
                print(f"  CREATE  link business={business.id} member={member.id}")

        db.commit()
        print(
            f"\nDone. Updated {updated}, created {created} businesses, "
            f"created {created_contacts} contacts, linked {linked}, {not_found} not found."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
