"""
Build a book gallery dataset from a spreadsheet, download cover images, and emit
Astro + WordPress outputs.

By default reads the book recommendations Google Sheet (CSV export or Sheets API).
Also supports local CSV/ODS via --source. When no purchase link is provided,
resolves Bookshop.org product URLs like /p/books/{slug}/{id}?ean=…&next=t.
Cover images use Open Library first, then Amazon (direct image URL, product page,
or search scrape).

Usage (from repo root):

    python -m scripts.sync_book_covers
    python -m scripts.sync_book_covers --source "data/Book suggestions for Country Bookshelf.ods"

Optional env:
    BOOKSHOP_AFFILIATE_ID — append affiliate params to Bookshop URLs when set
    GOOGLE_API_KEY — Google Sheets API v4 key (sheet must be viewable by link)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO_ROOT / "data" / "Book suggestions for Country Bookshelf.ods"
DEFAULT_GOOGLE_SHEET_ID = "11fFLkKeqcibt4PuA-IPrP8XxHef1diTUK3tz7W0w2ks"

BOOKS_JSON = REPO_ROOT / "astro-app" / "public" / "data" / "books.json"
COVERS_DIR = REPO_ROOT / "astro-app" / "public" / "images" / "book-covers"
WP_HTML = REPO_ROOT / "data" / "books-wordpress.html"

USER_AGENT = "NaBA-book-gallery/1.0 (+https://natural-building-alliance.org)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30
REQUEST_PAUSE_SEC = 0.35
AMAZON_IMAGE_TMPL = "https://images-na.ssl-images-amazon.com/images/P/{asin}.01._SX500_.jpg"
AMAZON_MIN_COVER_BYTES = 500

_AMAZON_SESSION: requests.Session | None = None
_BOOKSHOP_SESSION: requests.Session | None = None

ISBN_FIELD_RE = re.compile(
    r"(?:isbn(?:\s*(?:10|13))?|asin)\s*[:\-]?\s*([0-9Xx\-]{10,17})",
    re.IGNORECASE,
)
ISBN_LABEL_RE = re.compile(
    r"isbn[\s\-]*(?:10|13)\s*[:\-\s]*([0-9Xx][0-9Xx\-\s]{8,16}[0-9Xx])",
    re.IGNORECASE,
)
DIGITS_RE = re.compile(r"\d{10,13}")
AMAZON_ASIN_RE = re.compile(
    r"amazon\.com/(?:gp/product|[^/]+/dp|dp)/([A-Z0-9]{10})",
    re.IGNORECASE,
)
BOOKSHOP_PATH_RE = re.compile(r"(/p/books/[^?\s\"']+|/book/\d{13})", re.IGNORECASE)

LINK_ALIASES = (
    "ecommerce link",
    "e-commerce link",
    "link",
    "url",
    "purchase link",
    "buy link",
    "bookshop link",
)
ISBN_ALIASES = ("isbn",)
EAN_ALIASES = ("ean/upc", "ean", "upc", "isbn-13", "isbn13")
TITLE_ALIASES = ("title", "book", "book title")
AUTHOR_ALIASES = ("author", "authors")
PUBLISHER_ALIASES = ("publisher", "press")
CONFERENCE_ALIASES = (
    "speaking at conference (y/n)",
    "past conference speaker (y/n)",
    "conference",
    "speaking",
)


@dataclass
class BookRow:
    title: str
    author: str = ""
    publisher: str = ""
    isbn_raw: str = ""
    isbn13: str | None = None
    conference: str = ""
    link: str = ""
    amazon_asin: str = ""
    slug: str = ""
    cover_url: str = ""
    cover_path: str = ""
    purchase_url: str = ""
    purchase_label: str = ""
    warnings: list[str] = field(default_factory=list)


def _normalize_header(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _pick_column(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    normalized = {_normalize_header(h): h for h in headers if h}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "book"


def _clean_isbn_text(raw: str) -> str:
    return re.sub(r"[\u200e\u200f\u202a-\u202e]", "", str(raw).strip())


def _normalize_isbn10_value(digits: str) -> str | None:
    value = re.sub(r"[^0-9Xx]", "", digits).upper()
    if len(value) == 9 and value.isdigit():
        return f"0{value}"
    if len(value) == 10:
        return value
    return None


def _extract_labeled_isbn10(raw: str) -> str | None:
    text = _clean_isbn_text(raw)
    match = re.search(r"isbn[\s\-]*10\s*[:\-\s]*([0-9Xx]{9,10})", text, re.IGNORECASE)
    if not match:
        return None
    return _normalize_isbn10_value(match.group(1))


def _extract_amazon_asin(value: str) -> str | None:
    if not value:
        return None
    match = AMAZON_ASIN_RE.search(value)
    return match.group(1).upper() if match else None


def _extract_isbn(raw: str) -> str | None:
    if not raw or not str(raw).strip():
        return None
    text = _clean_isbn_text(raw)

    labeled10 = _extract_labeled_isbn10(raw)
    if labeled10:
        return labeled10

    labeled = ISBN_LABEL_RE.search(text)
    if labeled:
        digits = re.sub(r"[^0-9Xx]", "", labeled.group(1))
        if len(digits) == 13:
            return digits
        normalized10 = _normalize_isbn10_value(digits)
        if normalized10:
            return normalized10

    match = ISBN_FIELD_RE.search(text)
    if match:
        digits = re.sub(r"[^0-9Xx]", "", match.group(1))
        if len(digits) in (10, 13):
            return digits.upper() if len(digits) == 10 else digits

    if re.search(r"isbn[\s\-]*10", text, re.IGNORECASE):
        tail = re.split(r"isbn[\s\-]*10\s*[:\-\s]*", text, maxsplit=1, flags=re.IGNORECASE)
        if len(tail) > 1:
            normalized10 = _normalize_isbn10_value(tail[1])
            if normalized10:
                return normalized10

    compact = re.sub(r"[^0-9Xx]", "", text.replace("-", ""))
    for pattern in (r"(\d{13})", r"(\d{9}[Xx])", r"(\d{10})"):
        match = re.search(pattern, compact)
        if match:
            value = match.group(1).upper()
            if len(value) == 13:
                return value
            normalized10 = _normalize_isbn10_value(value)
            if normalized10:
                return normalized10

    # ISBN10-1568365330 style: prefer trailing 10/13 digit run
    runs = DIGITS_RE.findall(text.replace("-", ""))
    for candidate in reversed(runs):
        if len(candidate) in (10, 13):
            return candidate.upper() if len(candidate) == 10 else candidate
    return None


def _isbn10_to_isbn13(isbn10: str) -> str:
    core = isbn10[:-1]
    isbn12 = f"978{core}"
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn12))
    check = (10 - (total % 10)) % 10
    return f"{isbn12}{check}"


def _normalize_isbn13(raw: str | None) -> str | None:
    if not raw:
        return None
    isbn = _extract_isbn(raw)
    if not isbn:
        return None
    if len(isbn) == 10:
        return _isbn10_to_isbn13(isbn)
    return isbn


def _isbn13_to_isbn10(isbn13: str) -> str | None:
    if len(isbn13) != 13 or not isbn13.startswith(("978", "979")):
        return None
    core = isbn13[3:12]
    if not core.isdigit():
        return None
    total = sum(int(d) * (10 - i) for i, d in enumerate(core))
    check = (11 - (total % 11)) % 11
    check_char = "X" if check == 10 else str(check)
    return f"{core}{check_char}"


def _isbn_variants(raw: str | None, isbn13: str | None) -> list[str]:
    variants: list[str] = []
    extracted = _extract_isbn(raw or "")
    for candidate in (isbn13, extracted):
        if not candidate or candidate in variants:
            continue
        variants.append(candidate)
        if len(candidate) == 13:
            converted10 = _isbn13_to_isbn10(candidate)
            if converted10 and converted10 not in variants:
                variants.append(converted10)
        elif len(candidate) == 10:
            converted = _isbn10_to_isbn13(candidate)
            if converted not in variants:
                variants.append(converted)
    return variants


def _amazon_asin_candidates(book: BookRow) -> list[str]:
    candidates: list[str] = []
    for value in (
        book.amazon_asin,
        _extract_labeled_isbn10(book.isbn_raw),
        *_isbn_variants(book.isbn_raw, book.isbn13),
    ):
        if not value or len(value) != 10:
            continue
        asin = value.upper() if value.endswith("X") else value
        if asin not in candidates:
            candidates.append(asin)
    return candidates


def _amazon_session() -> requests.Session:
    global _AMAZON_SESSION
    if _AMAZON_SESSION is None:
        _AMAZON_SESSION = requests.Session()
        _AMAZON_SESSION.headers.update(
            {
                "User-Agent": BROWSER_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    return _AMAZON_SESSION


def _amazon_image_is_valid(resp: requests.Response) -> bool:
    content_type = (resp.headers.get("content-type") or "").lower()
    size = len(resp.content)
    if resp.status_code != 200 or size < AMAZON_MIN_COVER_BYTES:
        return False
    if "gif" in content_type and size < 1024:
        return False
    return content_type.startswith("image/")


def _amazon_direct_cover(asin: str) -> str | None:
    url = AMAZON_IMAGE_TMPL.format(asin=asin)
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": BROWSER_USER_AGENT})
    if _amazon_image_is_valid(resp):
        return url
    return None


def _amazon_parse_product_html(html: str) -> str | None:
    patterns = (
        r'data-old-hires="([^"]+)"',
        r'id="imgBlkFront"[^>]*src="([^"]+)"',
        r'"hiRes":"(https://m\.media-amazon\.com/images/I/[^"]+)"',
        r'"landingImageUrl":"(https://m\.media-amazon\.com/images/I/[^"]+)"',
        r'class="a-dynamic-image"[^>]*src="([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    generic = re.search(r"(https://m\.media-amazon\.com/images/I/[^\"']+\.jpg)", html)
    return generic.group(1) if generic else None


def _amazon_page_blocked(html: str) -> bool:
    markers = ("validateCaptcha", "opfcaptcha.amazon.com", "Continue shopping")
    return any(marker in html for marker in markers) and "imgBlkFront" not in html


def _amazon_scrape_product(asin: str) -> str | None:
    session = _amazon_session()
    session.get("https://www.amazon.com/", timeout=REQUEST_TIMEOUT)
    resp = session.get(f"https://www.amazon.com/dp/{asin}", timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200 or _amazon_page_blocked(resp.text):
        return None
    return _amazon_parse_product_html(resp.text)


def _amazon_scrape_search(title: str, author: str) -> str | None:
    query = " ".join(part for part in (title, author) if part).strip()
    if not query:
        return None
    session = _amazon_session()
    session.get("https://www.amazon.com/", timeout=REQUEST_TIMEOUT)
    resp = session.get(
        "https://www.amazon.com/s",
        params={"k": query, "i": "stripbooks"},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200 or _amazon_page_blocked(resp.text):
        return None

    image_match = re.search(
        r'src="(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"',
        resp.text,
    )
    if image_match:
        return image_match.group(1)

    asin_match = re.search(r"/dp/([A-Z0-9]{10})", resp.text)
    if asin_match:
        return _amazon_scrape_product(asin_match.group(1))
    return None


def _amazon_cover_for_book(book: BookRow) -> str | None:
    for asin in _amazon_asin_candidates(book):
        cover = _amazon_direct_cover(asin)
        if cover:
            return cover
        cover = _amazon_scrape_product(asin)
        if cover:
            return cover

    return _amazon_scrape_search(book.title, book.author)


def _read_ods(path: Path) -> list[dict[str, str]]:
    rows: list[list[str]] = []
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    ns = {
        "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    }
    for table in root.findall(".//table:table", ns):
        for row_el in table.findall("table:table-row", ns):
            cells: list[str] = []
            for cell in row_el.findall("table:table-cell", ns):
                repeat = int(
                    cell.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}number-columns-repeated", 1)
                )
                parts = [p.text or "" for p in cell.findall("text:p", ns)]
                value = "\n".join(parts).strip()
                cells.extend([value] * repeat)
            if any(cells):
                rows.append(cells)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    headers = [c.strip() for c in rows[0] + [""] * (width - len(rows[0]))]
    out: list[dict[str, str]] = []
    for raw in rows[1:]:
        padded = raw + [""] * (width - len(raw))
        if not any(v.strip() for v in padded):
            continue
        out.append({headers[i]: padded[i].strip() for i in range(width) if headers[i]})
    return out


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _rows_from_csv_text(text: str) -> list[dict[str, str]]:
    if "sign in" in text.lower()[:800] or "<!doctype html" in text.lower()[:200]:
        raise RuntimeError("Google Sheet response was HTML, not CSV.")
    lines = text.splitlines()
    if not lines:
        return []
    reader = csv.DictReader(lines)
    return [dict(row) for row in reader]


def _fetch_google_sheet_csv_export(sheet_id: str, gid: str) -> list[dict[str, str]]:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
    resp = requests.get(
        url,
        params={"format": "csv", "gid": gid},
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": BROWSER_USER_AGENT},
    )
    resp.raise_for_status()
    return _rows_from_csv_text(resp.text)


def _fetch_google_sheet_gviz(sheet_id: str, gid: str) -> list[dict[str, str]]:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
    resp = requests.get(
        url,
        params={"tqx": "out:csv", "gid": gid},
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": BROWSER_USER_AGENT},
    )
    resp.raise_for_status()
    return _rows_from_csv_text(resp.text)


def _sheet_title_for_gid(sheet_id: str, gid: str, api_key: str) -> str:
    meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    resp = requests.get(meta_url, params={"key": api_key}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    sheets = resp.json().get("sheets") or []
    for sheet in sheets:
        props = sheet.get("properties") or {}
        if str(props.get("sheetId")) == str(gid):
            title = props.get("title")
            if title:
                return title
    if sheets:
        return sheets[0]["properties"]["title"]
    raise RuntimeError(f"No worksheets found in Google Sheet {sheet_id}")


def _fetch_google_sheet_api(sheet_id: str, gid: str, api_key: str) -> list[dict[str, str]]:
    sheet_title = _sheet_title_for_gid(sheet_id, gid, api_key)
    range_name = urllib.parse.quote(f"'{sheet_title}'")
    values_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_name}"
    resp = requests.get(values_url, params={"key": api_key}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    values = resp.json().get("values") or []
    if not values:
        return []
    width = max(len(row) for row in values)
    headers = [(cell or "").strip() for cell in values[0] + [""] * (width - len(values[0]))]
    rows: list[dict[str, str]] = []
    for raw in values[1:]:
        padded = list(raw) + [""] * (width - len(raw))
        if not any(str(v).strip() for v in padded):
            continue
        rows.append({headers[i]: str(padded[i]).strip() for i in range(width) if headers[i]})
    return rows


def _fetch_google_sheet(sheet_id: str, gid: str = "0") -> list[dict[str, str]]:
    errors: list[str] = []
    for name, fetcher in (
        ("CSV export", lambda: _fetch_google_sheet_csv_export(sheet_id, gid)),
        ("gviz CSV", lambda: _fetch_google_sheet_gviz(sheet_id, gid)),
    ):
        try:
            rows = fetcher()
            if rows:
                print(f"Loaded {len(rows)} rows from Google Sheet via {name}")
                return rows
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    api_key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if api_key:
        try:
            rows = _fetch_google_sheet_api(sheet_id, gid, api_key)
            if rows:
                print(f"Loaded {len(rows)} rows from Google Sheet via Sheets API")
                return rows
        except Exception as exc:
            errors.append(f"Sheets API: {exc}")

    message = (
        "Could not read Google Sheet. Share it as 'Anyone with the link' (Viewer) "
        "or set GOOGLE_API_KEY for Sheets API access. "
        f"Sheet ID: {sheet_id}. Errors: {'; '.join(errors)}"
    )
    raise RuntimeError(message)


def load_rows(
    *,
    source: Path | None,
    google_sheet_id: str | None,
    google_sheet_gid: str,
    fallback_source: Path | None = None,
) -> list[dict[str, str]]:
    if source is not None:
        suffix = source.suffix.lower()
        if suffix == ".ods":
            return _read_ods(source)
        if suffix in {".csv", ".tsv"}:
            return _read_csv(source)
        raise ValueError(f"Unsupported source format: {source}")

    sheet_id = google_sheet_id or DEFAULT_GOOGLE_SHEET_ID
    try:
        return _fetch_google_sheet(sheet_id, google_sheet_gid)
    except RuntimeError:
        fallback = fallback_source or DEFAULT_SOURCE
        if fallback.exists():
            print(f"Warning: Google Sheet unavailable; using local file {fallback}")
            suffix = fallback.suffix.lower()
            if suffix == ".ods":
                return _read_ods(fallback)
            if suffix in {".csv", ".tsv"}:
                return _read_csv(fallback)
        raise


def _row_get(row: dict[str, str], aliases: tuple[str, ...]) -> str:
    for key, value in row.items():
        if _normalize_header(key) in aliases:
            return (value or "").strip()
    return ""


def parse_books(rows: list[dict[str, str]]) -> list[BookRow]:
    if not rows:
        return []
    headers = list(rows[0].keys())
    isbn_col = _pick_column(headers, ISBN_ALIASES)
    ean_col = _pick_column(headers, EAN_ALIASES)
    title_col = _pick_column(headers, TITLE_ALIASES)
    author_col = _pick_column(headers, AUTHOR_ALIASES)
    publisher_col = _pick_column(headers, PUBLISHER_ALIASES)
    link_col = _pick_column(headers, LINK_ALIASES)
    conference_col = _pick_column(headers, CONFERENCE_ALIASES)

    books: list[BookRow] = []
    seen_slugs: set[str] = set()

    for row in rows:
        title = (_row_get(row, TITLE_ALIASES) if not title_col else (row.get(title_col) or "")).strip()
        if not title:
            continue

        author = (_row_get(row, AUTHOR_ALIASES) if not author_col else (row.get(author_col) or "")).strip()
        publisher = (
            _row_get(row, PUBLISHER_ALIASES) if not publisher_col else (row.get(publisher_col) or "")
        ).strip()
        link = _normalize_ecommerce_link(
            _row_get(row, LINK_ALIASES) if not link_col else (row.get(link_col) or "")
        )
        isbn_raw, isbn13 = _resolve_isbn_fields(row, isbn_col=isbn_col, ean_col=ean_col, link=link)
        conference = (
            _row_get(row, CONFERENCE_ALIASES) if not conference_col else (row.get(conference_col) or "")
        ).strip()

        amazon_asin = _extract_amazon_asin(link)
        slug_base = _slugify(title)
        slug = slug_base
        n = 2
        while slug in seen_slugs:
            suffix = isbn13[-6:] if isbn13 else str(n)
            slug = f"{slug_base}-{suffix}"
            n += 1
        seen_slugs.add(slug)

        books.append(
            BookRow(
                title=title,
                author=author,
                publisher=publisher,
                isbn_raw=isbn_raw,
                isbn13=isbn13,
                conference=conference,
                link=link,
                amazon_asin=amazon_asin or "",
                slug=slug,
            )
        )
    return books


def _bookshop_session() -> requests.Session:
    global _BOOKSHOP_SESSION
    if _BOOKSHOP_SESSION is None:
        _BOOKSHOP_SESSION = requests.Session()
        _BOOKSHOP_SESSION.headers.update(
            {
                "User-Agent": BROWSER_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    return _BOOKSHOP_SESSION


def _bookshop_primary_author(author: str) -> str:
    return re.split(r"[&,]| and ", author, maxsplit=1, flags=re.IGNORECASE)[0].strip()


def _bookshop_slug(title: str, author: str) -> str:
    primary_author = _bookshop_primary_author(author)
    if primary_author:
        return f"{_slugify(title)}-{_slugify(primary_author)}"
    return _slugify(title)


def _bookshop_finalize_url(path_or_url: str, isbn13: str | None, affiliate_id: str | None) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        url = path_or_url
    else:
        url = f"https://bookshop.org{path_or_url}"

    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    if isbn13 and "ean" not in query:
        query["ean"] = isbn13
    query["next"] = "t"
    if affiliate_id:
        query["aid"] = affiliate_id
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def _bookshop_scrape_product_path(book: BookRow) -> str | None:
    session = _bookshop_session()
    session.get("https://bookshop.org/", timeout=REQUEST_TIMEOUT)
    queries = [q for q in (book.isbn13, f"{book.title} {book.author}".strip()) if q]
    for query in queries:
        resp = session.get(
            "https://bookshop.org/books",
            params={"keywords": query},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            continue
        for pattern in (
            r'href="(/p/books/[^"?]+)"',
            r'href="(https://bookshop\.org/p/books/[^"?]+)"',
            r'href="(/book/\d{13})"',
        ):
            match = re.search(pattern, resp.text)
            if match:
                return match.group(1)
    return None


def _extract_ean_from_url(url: str) -> str | None:
    if not url:
        return None
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    for key in ("ean", "EAN"):
        values = query.get(key) or []
        for value in values:
            normalized = _normalize_isbn13(str(value).strip())
            if normalized:
                return normalized
    return None


def _resolve_isbn_fields(
    row: dict[str, str],
    *,
    isbn_col: str | None,
    ean_col: str | None,
    link: str,
) -> tuple[str, str | None]:
    isbn_raw = (_row_get(row, ISBN_ALIASES) if not isbn_col else (row.get(isbn_col) or "")).strip()
    ean_raw = (_row_get(row, EAN_ALIASES) if not ean_col else (row.get(ean_col) or "")).strip()

    if not isbn_raw and ean_raw:
        isbn_raw = ean_raw

    isbn13 = _normalize_isbn13(isbn_raw)
    if not isbn13:
        isbn13 = _normalize_isbn13(ean_raw)
    if not isbn13:
        isbn13 = _extract_ean_from_url(link)
    if not isbn_raw and (ean_raw or isbn13):
        isbn_raw = ean_raw or isbn13 or ""

    return isbn_raw, isbn13


def _normalize_ecommerce_link(link: str) -> str:
    value = (link or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("www."):
        return f"https://{value}"
    return value


def _is_bookshop_url(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return host == "bookshop.org" or host.endswith(".bookshop.org")


def _purchase_button_label(url: str) -> str:
    if _is_bookshop_url(url):
        return "Buy on Bookshop.org"
    return "Buy online"


def _resolve_purchase_url(book: BookRow, affiliate_id: str | None) -> str:
    link = _normalize_ecommerce_link(book.link)
    if link:
        if _is_bookshop_url(link):
            # Keep ean/next/aid from the sheet link; only fill ean when missing.
            link_ean = _extract_ean_from_url(link)
            return _bookshop_finalize_url(link, link_ean or book.isbn13, affiliate_id)
        return link

    scraped = _bookshop_scrape_product_path(book)
    if scraped:
        return _bookshop_finalize_url(scraped, book.isbn13, affiliate_id)

    slug = _bookshop_slug(book.title, book.author)
    return _bookshop_finalize_url(f"/p/books/{slug}", book.isbn13, affiliate_id)


def _openlibrary_cover_by_isbn(isbn: str) -> str | None:
    url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True, headers={"User-Agent": USER_AGENT})
    try:
        if resp.status_code == 200 and (resp.headers.get("content-type") or "").startswith("image"):
            return url
    finally:
        resp.close()
    return None


def _openlibrary_cover_for_book(raw_isbn: str, isbn13: str | None) -> str | None:
    for isbn in _isbn_variants(raw_isbn, isbn13):
        cover = _openlibrary_cover_by_isbn(isbn)
        if cover:
            return cover
    return None


def _title_search_variants(title: str) -> list[str]:
    variants = [title.strip()]
    short = re.split(r"\s+vol\b|:", title, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if short and short not in variants:
        variants.append(short)
    return variants


def _openlibrary_lookup(title: str, author: str) -> tuple[str | None, str | None]:
    docs: list[dict[str, Any]] = []
    for title_variant in _title_search_variants(title):
        params: dict[str, str] = {"title": title_variant, "limit": "3"}
        if author:
            params["author"] = author
        resp = requests.get(
            "https://openlibrary.org/search.json",
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        docs = resp.json().get("docs") or []
        if docs:
            break
    if not docs:
        return None, None

    doc = docs[0]
    isbn13 = None
    for candidate in doc.get("isbn") or []:
        norm = _normalize_isbn13(candidate)
        if norm:
            isbn13 = norm
            break

    cover_url = None
    cover_id = doc.get("cover_i")
    if cover_id:
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
    elif isbn13:
        cover_url = _openlibrary_cover_for_book("", isbn13)
    return isbn13, cover_url


def resolve_cover(book: BookRow) -> None:
    for asin in _amazon_asin_candidates(book):
        cover = _amazon_direct_cover(asin)
        if cover:
            book.cover_url = cover
            return

    cover = _openlibrary_cover_for_book(book.isbn_raw, book.isbn13)
    if cover:
        book.cover_url = cover
        return

    isbn13, cover = _openlibrary_lookup(book.title, book.author)
    if isbn13 and not book.isbn13:
        book.isbn13 = isbn13
    if cover:
        book.cover_url = cover
        return

    cover = _amazon_cover_for_book(book)
    if cover:
        book.cover_url = cover
        return

    book.warnings.append("cover not found")


def download_cover(book: BookRow, covers_dir: Path, force: bool) -> None:
    if not book.cover_url:
        return
    covers_dir.mkdir(parents=True, exist_ok=True)
    dest = covers_dir / f"{book.slug}.jpg"
    book.cover_path = f"/images/book-covers/{book.slug}.jpg"
    if dest.exists() and not force:
        return
    resp = requests.get(book.cover_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    if resp.status_code != 200 or not (resp.headers.get("content-type") or "").startswith("image"):
        book.warnings.append("cover download failed")
        book.cover_path = ""
        return
    dest.write_bytes(resp.content)


def book_to_json(book: BookRow) -> dict[str, Any]:
    return {
        "slug": book.slug,
        "title": book.title,
        "author": book.author,
        "publisher": book.publisher,
        "isbn": book.isbn13,
        "ean": book.isbn13,
        "isbn_raw": book.isbn_raw,
        "conference_speaker": book.conference,
        "purchase_url": book.purchase_url,
        "purchase_label": book.purchase_label,
        "cover_url": book.cover_url,
        "cover_path": book.cover_path,
        "warnings": book.warnings,
    }


def render_wordpress_html(books: list[BookRow], *, title: str, subtitle: str) -> str:
    cards: list[str] = []
    for book in books:
        img_src = book.cover_url or ""
        img = (
            f'<img src="{img_src}" alt="{_html_escape(book.title)} cover" '
            'loading="lazy" style="width:100%;height:240px;object-fit:contain;background:#f8fafc;" />'
            if img_src
            else '<div style="height:240px;background:#f1f5f9;display:flex;align-items:center;'
            'justify-content:center;color:#64748b;font-size:16px;">Cover unavailable</div>'
        )
        meta_bits = [b for b in (book.author, book.publisher) if b]
        meta = " · ".join(meta_bits)
        link = book.purchase_url
        button = _html_escape(book.purchase_label or _purchase_button_label(link))
        cards.append(
            f"""
<article class="naba-book-card" style="border:1px solid #e2e8f0;border-radius:0.75rem;overflow:hidden;background:#fff;display:flex;flex-direction:column;">
  <a href="{_html_escape(link)}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;color:inherit;">
    {img}
    <div style="padding:1rem 1rem 1.25rem;padding-top:calc(1rem + 10px);">
      <h3 style="margin:0 0 1rem;font-size:19px;line-height:1.35;font-weight:600;color:#0f172a;">{_html_escape(book.title)}</h3>
      <p style="margin:0 0 1rem;color:#64748b;font-size:16px;line-height:1.45;">{_html_escape(meta)}</p>
      <div style="text-align:center;">
        <span style="display:inline-block;background:#0f766e;color:#fff;padding:0.5rem 1.5rem;border-radius:999px;font-size:15px;font-weight:600;">{button}</span>
      </div>
    </div>
  </a>
</article>"""
        )

    return f"""<!-- NaBA book gallery — paste into a WordPress Custom HTML block -->
<div class="naba-books-gallery" style="max-width:1100px;margin:0 auto;font-family:inherit;font-size:18px;line-height:1.5;color:#1e293b;">
  <header style="margin-bottom:1.75rem;">
    <h2 style="margin:0 0 0.5rem;font-size:32px;line-height:1.2;font-weight:700;color:#0f172a;">{_html_escape(title)}</h2>
    <p style="margin:0;color:#64748b;font-size:18px;line-height:1.5;">{_html_escape(subtitle)}</p>
  </header>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1.5rem;">
    {''.join(cards)}
  </div>
  <p style="margin:1.75rem 0 0;font-size:14px;line-height:1.5;color:#94a3b8;">
    Purchase links go to the seller listed for each book. Cover images from Open Library and Amazon.
  </p>
</div>
"""


def _html_escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def sync_books(
    *,
    source: Path | None = None,
    google_sheet_id: str | None = None,
    google_sheet_gid: str = "0",
    force_covers: bool = False,
    skip_download: bool = False,
    no_fallback: bool = False,
    gallery_title: str = "Natural Building Alliance Book Recommendations",
    gallery_subtitle: str = "Books recommended by the Natural Building Alliance community.",
) -> list[BookRow]:
    rows = load_rows(
        source=source,
        google_sheet_id=google_sheet_id,
        google_sheet_gid=google_sheet_gid,
        fallback_source=None if no_fallback else DEFAULT_SOURCE,
    )
    books = parse_books(rows)
    affiliate_id = (os.environ.get("BOOKSHOP_AFFILIATE_ID") or "").strip() or None

    for book in books:
        resolve_cover(book)
        book.purchase_url = _resolve_purchase_url(book, affiliate_id)
        book.purchase_label = _purchase_button_label(book.purchase_url)
        if not skip_download:
            download_cover(book, COVERS_DIR, force_covers)
        time.sleep(REQUEST_PAUSE_SEC)

    payload = {
        "title": gallery_title,
        "subtitle": gallery_subtitle,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "books": [book_to_json(b) for b in books],
    }
    BOOKS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(BOOKS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    WP_HTML.parent.mkdir(parents=True, exist_ok=True)
    WP_HTML.write_text(
        render_wordpress_html(books, title=gallery_title, subtitle=gallery_subtitle),
        encoding="utf-8",
    )

    ok_covers = sum(1 for b in books if b.cover_path or b.cover_url)
    print(f"Processed {len(books)} books")
    print(f"  JSON: {BOOKS_JSON}")
    print(f"  Covers: {COVERS_DIR} ({ok_covers}/{len(books)} with images)")
    print(f"  WordPress HTML: {WP_HTML}")
    for book in books:
        if book.warnings:
            print(f"  warn [{book.title}]: {', '.join(book.warnings)}")
    return books


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync book list, covers, and gallery outputs.")
    parser.add_argument(
        "--source",
        type=Path,
        help="Local CSV or ODS file (skips Google Sheet when set)",
    )
    parser.add_argument(
        "--google-sheet",
        dest="google_sheet_id",
        default=DEFAULT_GOOGLE_SHEET_ID,
        help=f"Google Sheet ID (default: {DEFAULT_GOOGLE_SHEET_ID})",
    )
    parser.add_argument("--gid", default="0", help="Google Sheet tab gid (default: 0)")
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Do not fall back to the local ODS if Google Sheet is unavailable",
    )
    parser.add_argument("--force-covers", action="store_true", help="Re-download cover images")
    parser.add_argument("--skip-download", action="store_true", help="Resolve metadata only")
    parser.add_argument("--title", default="Natural Building Alliance Book Recommendations")
    parser.add_argument("--subtitle", default="Books recommended by the Natural Building Alliance community.")
    args = parser.parse_args()

    sync_books(
        source=args.source,
        google_sheet_id=None if args.source else args.google_sheet_id,
        google_sheet_gid=args.gid,
        force_covers=args.force_covers,
        skip_download=args.skip_download,
        gallery_title=args.title,
        gallery_subtitle=args.subtitle,
        no_fallback=args.no_fallback,
    )


if __name__ == "__main__":
    main()
