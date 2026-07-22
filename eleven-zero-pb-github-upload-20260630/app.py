from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import smtplib
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


APP_ROOT = Path(__file__).resolve().parent
PADDLE_CATALOG_PATH = APP_ROOT / "paddle-catalog.json"


def paddle_catalog_key(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def paddle_thickness_key(value) -> str:
    try:
        numeric_value = float(str(value or "").strip())
    except (TypeError, ValueError):
        return ""
    if not 5 <= numeric_value <= 30:
        return ""
    return format(numeric_value, "g")


def load_paddle_catalog() -> dict:
    try:
        payload = json.loads(PADDLE_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    raw_brands = payload.get("brands", {}) if isinstance(payload, dict) else {}
    brands = []
    for brand_name, raw_models in raw_brands.items():
        clean_brand = re.sub(r"\s+", " ", str(brand_name or "").strip())
        if not clean_brand or not isinstance(raw_models, list):
            continue
        models = sorted(
            {
                re.sub(r"\s+", " ", str(model or "").strip())
                for model in raw_models
                if str(model or "").strip()
            },
            key=str.casefold,
        )
        if models:
            brands.append({"name": clean_brand, "models": models})

    raw_colors = payload.get("colors", []) if isinstance(payload, dict) else []
    colors = []
    seen_colors = set()
    for raw_color in raw_colors:
        color = re.sub(r"\s+", " ", str(raw_color or "").strip())
        color_key = paddle_catalog_key(color)
        if not color_key or color_key in seen_colors:
            continue
        seen_colors.add(color_key)
        colors.append(color)

    raw_thicknesses = payload.get("thicknesses_mm", []) if isinstance(payload, dict) else []
    thicknesses = sorted(
        {paddle_thickness_key(value) for value in raw_thicknesses if paddle_thickness_key(value)},
        key=float,
    )

    brands.sort(key=lambda item: item["name"].casefold())
    return {
        "version": str(payload.get("version", "")).strip(),
        "brands": brands,
        "colors": colors,
        "thicknessesMm": thicknesses,
    }


PADDLE_CATALOG = load_paddle_catalog()
PADDLE_CATALOG_INDEX = {
    paddle_catalog_key(entry["name"]): {
        "name": entry["name"],
        "models": {paddle_catalog_key(model): model for model in entry["models"]},
    }
    for entry in PADDLE_CATALOG["brands"]
}
PADDLE_COLOR_INDEX = {
    paddle_catalog_key(color): color for color in PADDLE_CATALOG["colors"]
}
PADDLE_THICKNESS_INDEX = {
    paddle_thickness_key(thickness): thickness for thickness in PADDLE_CATALOG["thicknessesMm"]
}


def resolve_paddle_selection(brand, model) -> tuple[str, str] | None:
    brand_entry = PADDLE_CATALOG_INDEX.get(paddle_catalog_key(brand))
    if not brand_entry:
        return None
    canonical_model = brand_entry["models"].get(paddle_catalog_key(model))
    if not canonical_model:
        return None
    return brand_entry["name"], canonical_model


def resolve_paddle_color(color) -> str | None:
    return PADDLE_COLOR_INDEX.get(paddle_catalog_key(color))


def resolve_paddle_thickness(thickness) -> str | None:
    return PADDLE_THICKNESS_INDEX.get(paddle_thickness_key(thickness))


def paddle_catalog_payload() -> dict:
    brands = PADDLE_CATALOG["brands"]
    return {
        "version": PADDLE_CATALOG["version"],
        "brandCount": len(brands),
        "modelCount": sum(len(entry["models"]) for entry in brands),
        "colorCount": len(PADDLE_CATALOG["colors"]),
        "thicknessCount": len(PADDLE_CATALOG["thicknessesMm"]),
        "brands": brands,
        "colors": PADDLE_CATALOG["colors"],
        "thicknessesMm": PADDLE_CATALOG["thicknessesMm"],
    }


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
HOST = os.getenv("HOST", "127.0.0.1" if APP_ENV == "development" else "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DATA_DIR = Path(os.getenv("DATA_DIR", str(APP_ROOT / "data"))).expanduser()
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "eleven_zero_pb.db"))).expanduser()
SESSION_COOKIE = os.getenv("SESSION_COOKIE_NAME", "eleven_zero_session")
SESSION_COOKIE_SECURE = env_flag("SESSION_COOKIE_SECURE", APP_ENV == "production")
ENABLE_DEMO_DATA = env_flag("ENABLE_DEMO_DATA", APP_ENV != "production")
ENABLE_STARTER_LISTINGS = env_flag("ENABLE_STARTER_LISTINGS", APP_ENV != "production")
SITE_URL = os.getenv("SITE_URL", "").strip()
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "").strip()
PRIMARY_OWNER_EMAIL = os.getenv("PRIMARY_OWNER_EMAIL", "11zeropb@gmail.com").strip()
ADMIN_EMAILS_RAW = os.getenv("ADMIN_EMAILS", "").strip()
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "").strip()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
GOOGLE_MAPS_MAP_ID = os.getenv("GOOGLE_MAPS_MAP_ID", "").strip()
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", GOOGLE_MAPS_API_KEY).strip()
SHIPPO_API_KEY = os.getenv("SHIPPO_API_KEY", "").strip()
SHIPPO_LABEL_FILE_TYPE = os.getenv("SHIPPO_LABEL_FILE_TYPE", "PDF").strip().upper() or "PDF"
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_USE_TLS = env_flag("SMTP_USE_TLS", True)
SMTP_USE_SSL = env_flag("SMTP_USE_SSL", False)
EMAIL_FROM = os.getenv("EMAIL_FROM", SUPPORT_EMAIL or PRIMARY_OWNER_EMAIL).strip()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_COUNTRY = os.getenv("STRIPE_COUNTRY", "US").strip().upper() or "US"
STRIPE_PLATFORM_FEE_PERCENT = float(os.getenv("PLATFORM_FEE_PERCENT", "8.5"))
STRIPE_API_BASE = "https://api.stripe.com/v1"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
RATE_LIMIT_LOCK = threading.Lock()
RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}

DEFAULT_PADDLE_PACKAGE = {
    "weight_oz": 24.0,
    "length_in": 20.0,
    "width_in": 10.0,
    "height_in": 4.0,
}

US_STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
}
US_STATE_LOOKUP = {
    **{code: code for code in US_STATE_NAMES},
    **{name.upper(): code for code, name in US_STATE_NAMES.items()},
}
US_STATE_REGION = {
    "CT": "northeast",
    "MA": "northeast",
    "ME": "northeast",
    "NH": "northeast",
    "NJ": "northeast",
    "NY": "northeast",
    "PA": "northeast",
    "RI": "northeast",
    "VT": "northeast",
    "AL": "south",
    "AR": "south",
    "DC": "south",
    "DE": "south",
    "FL": "south",
    "GA": "south",
    "KY": "south",
    "LA": "south",
    "MD": "south",
    "MS": "south",
    "NC": "south",
    "OK": "south",
    "SC": "south",
    "TN": "south",
    "TX": "south",
    "VA": "south",
    "WV": "south",
    "IA": "midwest",
    "IL": "midwest",
    "IN": "midwest",
    "KS": "midwest",
    "MI": "midwest",
    "MN": "midwest",
    "MO": "midwest",
    "ND": "midwest",
    "NE": "midwest",
    "OH": "midwest",
    "SD": "midwest",
    "WI": "midwest",
    "AK": "west",
    "AZ": "west",
    "CA": "west",
    "CO": "west",
    "HI": "west",
    "ID": "west",
    "MT": "west",
    "NM": "west",
    "NV": "west",
    "OR": "west",
    "UT": "west",
    "WA": "west",
    "WY": "west",
    "PR": "territory",
}
ZIP_CODE_RE = re.compile(r"^\d{5}(?:-\d{4})?$")


def cache_control_for_path(path: str) -> str:
    if re.fullmatch(r"/api/listings/\d+/images/\d+", path):
        return "public, max-age=86400"

    if path.startswith("/api/"):
        return "no-store"

    if path in {"", "/", "/index.html"} or path.endswith(".html"):
        return "no-store"

    if path.endswith((".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico")):
        return "public, max-age=86400"

    return "no-store"


def build_content_security_policy() -> str:
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "img-src 'self' data: https://images.pexels.com https://tile.openstreetmap.org https://*.googleapis.com https://*.gstatic.com https://*.googleusercontent.com",
            "script-src 'self' https://www.googletagmanager.com https://maps.googleapis.com",
            "style-src 'self' 'unsafe-inline'",
            "connect-src 'self' https://www.google-analytics.com https://region1.google-analytics.com https://nominatim.openstreetmap.org https://overpass-api.de https://www.openstreetmap.org https://api.stripe.com https://*.googleapis.com https://*.gstatic.com https://*.google.com",
        ]
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rate_limit_allows(key: str, limit: int, window_seconds: int) -> bool:
    """Small in-process guard for abuse-prone account endpoints."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with RATE_LIMIT_LOCK:
        attempts = [stamp for stamp in RATE_LIMIT_BUCKETS.get(key, []) if stamp > cutoff]
        if len(attempts) >= limit:
            RATE_LIMIT_BUCKETS[key] = attempts
            return False
        attempts.append(now)
        RATE_LIMIT_BUCKETS[key] = attempts
    return True


def parse_activity_datetime(value) -> datetime | None:
    clean_value = str(value or "").strip()
    if not clean_value:
        return None

    try:
        parsed = datetime.fromisoformat(clean_value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_sales_analytics(order_rows, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    def row_value(row, key, default=None):
        try:
            value = row[key]
        except (KeyError, IndexError, TypeError):
            value = default
        return default if value is None else value

    def month_at_offset(offset: int) -> tuple[int, int]:
        absolute_month = current.year * 12 + current.month - 1 + offset
        return absolute_month // 12, absolute_month % 12 + 1

    current_quarter_index = current.year * 4 + (current.month - 1) // 3

    period_specs = {
        "day": [
            {
                "key": (current.date() - timedelta(days=offset)).isoformat(),
                "label": f"{(current - timedelta(days=offset)).strftime('%b')} {(current - timedelta(days=offset)).day}",
            }
            for offset in range(13, -1, -1)
        ],
        "month": [
            {
                "key": f"{year:04d}-{month:02d}",
                "label": datetime(year, month, 1).strftime("%b %Y"),
            }
            for year, month in (month_at_offset(offset) for offset in range(-11, 1))
        ],
        "quarter": [
            {
                "key": f"{quarter_index // 4:04d}-Q{quarter_index % 4 + 1}",
                "label": f"Q{quarter_index % 4 + 1} {quarter_index // 4}",
            }
            for quarter_index in range(current_quarter_index - 7, current_quarter_index + 1)
        ],
        "year": [
            {"key": str(year), "label": str(year)}
            for year in range(current.year - 4, current.year + 1)
        ],
    }

    analytics = {}
    for period, specs in period_specs.items():
        buckets = {
            spec["key"]: {
                "label": spec["label"],
                "orders": 0,
                "buyers": set(),
                "revenueCents": 0,
            }
            for spec in specs
        }

        for order in order_rows:
            activity_at = parse_activity_datetime(
                row_value(order, "completed_at") or row_value(order, "created_at")
            )
            if not activity_at:
                continue

            quarter_number = (activity_at.month - 1) // 3 + 1
            key_by_period = {
                "day": activity_at.date().isoformat(),
                "month": f"{activity_at.year:04d}-{activity_at.month:02d}",
                "quarter": f"{activity_at.year:04d}-Q{quarter_number}",
                "year": str(activity_at.year),
            }
            bucket = buckets.get(key_by_period[period])
            if not bucket:
                continue

            bucket["orders"] += 1
            buyer_id = row_value(order, "buyer_user_id")
            if buyer_id:
                bucket["buyers"].add(str(buyer_id))
            bucket["revenueCents"] += int(row_value(order, "amount_total_cents", 0) or 0)

        visible_buckets = []
        summary_buyers = set()
        summary_orders = 0
        summary_revenue = 0
        for spec in specs:
            bucket = buckets[spec["key"]]
            summary_orders += bucket["orders"]
            summary_revenue += bucket["revenueCents"]
            summary_buyers.update(bucket["buyers"])
            visible_buckets.append(
                {
                    "label": bucket["label"],
                    "orders": bucket["orders"],
                    "buyers": len(bucket["buyers"]),
                    "revenueCents": bucket["revenueCents"],
                }
            )

        analytics[period] = {
            "buckets": visible_buckets,
            "summary": {
                "orders": summary_orders,
                "buyers": len(summary_buyers),
                "revenueCents": summary_revenue,
            },
        }

    return analytics


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, digest_hex: str) -> bool:
    _, check_digest = hash_password(password, salt_hex)
    return secrets.compare_digest(check_digest, digest_hex)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def admin_email_set() -> set[str]:
    items = {
        normalize_email(item)
        for item in [PRIMARY_OWNER_EMAIL, SUPPORT_EMAIL, *ADMIN_EMAILS_RAW.split(",")]
        if normalize_email(item)
    }
    return items


ADMIN_EMAILS = admin_email_set()


def email_is_admin(email: str) -> bool:
    return normalize_email(email) in ADMIN_EMAILS


def compact_whitespace(value: str) -> str:
    return " ".join(str(value or "").split())


PROFILE_BLOCKED_TERMS = {
    "asshole",
    "bitch",
    "cunt",
    "dickhead",
    "fag",
    "faggot",
    "fuck",
    "motherfucker",
    "nigger",
    "shit",
    "slut",
    "whore",
}


def profile_name_contains_profanity(value: str) -> bool:
    """Conservatively screen obvious profanity while avoiding substring false positives."""
    normalized = compact_whitespace(value).casefold().translate(
        str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})
    )
    tokens = re.findall(r"[a-z]+", normalized)
    compact_name = "".join(tokens)
    return any(token in PROFILE_BLOCKED_TERMS for token in tokens) or compact_name in PROFILE_BLOCKED_TERMS


def row_value(row: sqlite3.Row | dict | None, key: str, default=None):
    if row is None:
        return default

    if isinstance(row, dict):
        return row.get(key, default)

    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def normalize_us_state(value: str) -> str:
    raw = compact_whitespace(value).upper().replace(".", "")
    return US_STATE_LOOKUP.get(raw, "")


def normalize_compare_text(value: str) -> str:
    return "".join(ch.lower() for ch in compact_whitespace(value) if ch.isalnum())


def extract_city_from_location(location: str) -> str:
    text = compact_whitespace(location)
    if not text:
        return ""
    return compact_whitespace(text.split(",", 1)[0])


def extract_state_from_location(location: str) -> str:
    text = compact_whitespace(location)
    if not text:
        return ""

    parts = [compact_whitespace(part) for part in text.split(",") if compact_whitespace(part)]
    candidates = list(reversed(parts)) or [text]
    for candidate in candidates:
        normalized = normalize_us_state(candidate)
        if normalized:
            return normalized

        for token in reversed(candidate.replace(",", " ").split()):
            normalized = normalize_us_state(token)
            if normalized:
                return normalized

    return ""


def normalize_shipping_address(raw_address) -> dict:
    address = raw_address if isinstance(raw_address, dict) else {}
    country = compact_whitespace(address.get("country", "US")).upper() or "US"

    return {
        "line1": compact_whitespace(address.get("line1", "")),
        "line2": compact_whitespace(address.get("line2", "")),
        "city": compact_whitespace(address.get("city", "")),
        "state": normalize_us_state(address.get("state", "")),
        "postalCode": compact_whitespace(address.get("postalCode", "")).upper(),
        "country": country,
    }


def parse_zip_code(value) -> str:
    zip_code = compact_whitespace(value).upper()
    return zip_code if ZIP_CODE_RE.fullmatch(zip_code) else ""


def parse_whole_dollar_amount(raw_value) -> int:
    digits = "".join(ch for ch in str(raw_value or "").strip() if ch.isdigit())
    return int(digits) if digits else 0


def parse_shipping_weight_oz(raw_value) -> float | None:
    raw = str(raw_value or "").strip()
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == ".")

    if not raw:
        return None

    if not cleaned or cleaned.count(".") > 1:
        return None

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if value < 1 or value > 320:
        return None

    return round(value, 1)


def parse_shipping_dimension_in(raw_value) -> float | None:
    raw = str(raw_value or "").strip()
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == ".")

    if not raw:
        return None

    if not cleaned or cleaned.count(".") > 1:
        return None

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if value < 1 or value > 72:
        return None

    return round(value, 1)


def shippo_is_configured() -> bool:
    return bool(SHIPPO_API_KEY)


def shipping_policy_from_row(row: sqlite3.Row | dict | None) -> dict:
    mode_raw = str(row_value(row, "shipping_mode", "calculated") or "calculated").strip().lower()
    mode = mode_raw if mode_raw in {"calculated", "flat", "free"} else "calculated"
    flat_usd = int(row_value(row, "shipping_flat_usd", 0) or 0)
    origin_zip = parse_zip_code(row_value(row, "shipping_origin_zip", ""))
    origin_street1 = compact_whitespace(row_value(row, "shipping_origin_street1", ""))
    weight_oz = (
        parse_shipping_weight_oz(row_value(row, "shipping_weight_oz", ""))
        or DEFAULT_PADDLE_PACKAGE["weight_oz"]
    )
    length_in = (
        parse_shipping_dimension_in(row_value(row, "shipping_length_in", ""))
        or DEFAULT_PADDLE_PACKAGE["length_in"]
    )
    width_in = (
        parse_shipping_dimension_in(row_value(row, "shipping_width_in", ""))
        or DEFAULT_PADDLE_PACKAGE["width_in"]
    )
    height_in = (
        parse_shipping_dimension_in(row_value(row, "shipping_height_in", ""))
        or DEFAULT_PADDLE_PACKAGE["height_in"]
    )
    note = compact_whitespace(row_value(row, "shipping_note", ""))

    if mode == "free":
        label = "Free shipping"
        explanation = "Seller is covering shipping on this listing."
    elif mode == "flat":
        label = f"Flat shipping · ${flat_usd}"
        explanation = "Seller set one shipping amount for every U.S. destination."
    else:
        label = "Calculated shipping at checkout"
        explanation = (
            "Buyer enters the delivery address first, then Eleven Zero PB calculates the carrier rate."
        )

    return {
        "mode": mode,
        "modeLabel": {
            "calculated": "Calculated",
            "flat": "Flat",
            "free": "Free",
        }.get(mode, "Calculated"),
        "flatUsd": flat_usd,
        "originZip": origin_zip,
        "originStreetReady": bool(origin_street1),
        "weightOz": weight_oz,
        "lengthIn": length_in,
        "widthIn": width_in,
        "heightIn": height_in,
        "note": note,
        "label": label,
        "explanation": explanation,
        "carrierReady": bool(
            origin_zip and origin_street1 and weight_oz and length_in and width_in and height_in
        ),
    }


def build_shippo_rate_quote_for_listing(
    listing_row: sqlite3.Row | dict,
    address: dict,
    shipping_policy: dict,
    price_cents: int,
) -> dict | None:
    if not shippo_is_configured():
        return None

    origin_location = compact_whitespace(row_value(listing_row, "location", "") or "")
    origin_state = extract_state_from_location(origin_location)
    origin_city = extract_city_from_location(origin_location)
    origin_street1 = compact_whitespace(row_value(listing_row, "shipping_origin_street1", ""))
    origin_zip = shipping_policy["originZip"]
    weight_oz = shipping_policy["weightOz"]
    length_in = shipping_policy["lengthIn"]
    width_in = shipping_policy["widthIn"]
    height_in = shipping_policy["heightIn"]

    if not all([origin_street1, origin_city, origin_state, origin_zip, weight_oz, length_in, width_in, height_in]):
        return None

    shipment_payload = {
        "address_from": {
            "name": compact_whitespace(row_value(listing_row, "seller_name", "")) or "Eleven Zero PB seller",
            "street1": origin_street1,
            "city": origin_city,
            "state": origin_state,
            "zip": origin_zip,
            "country": "US",
            "email": SUPPORT_EMAIL or PRIMARY_OWNER_EMAIL,
        },
        "address_to": {
            "name": "Eleven Zero PB buyer",
            "street1": address["line1"],
            "street2": address["line2"],
            "city": address["city"],
            "state": address["state"],
            "zip": address["postalCode"],
            "country": address["country"],
        },
        "parcels": [
            {
                "length": str(length_in),
                "width": str(width_in),
                "height": str(height_in),
                "distance_unit": "in",
                "weight": str(round(float(weight_oz) / 16, 2)),
                "mass_unit": "lb",
            }
        ],
        "async": False,
    }

    shipment = shippo_request("/shipments/", shipment_payload)
    rates = shipment.get("rates") or []

    best_rate = None
    for rate in rates:
        currency = str(rate.get("currency") or rate.get("currency_local") or "").upper()
        if currency and currency != "USD":
            continue
        amount_raw = rate.get("amount") or rate.get("amount_local")
        try:
            amount_value = float(amount_raw)
        except (TypeError, ValueError):
            continue
        if amount_value < 0:
            continue
        if best_rate is None or amount_value < best_rate["amount_value"]:
            best_rate = {
                "amount_value": amount_value,
                "object_id": str(rate.get("object_id") or ""),
                "provider": str(rate.get("provider") or "Carrier"),
                "service_name": (
                    str(rate.get("servicelevel_name") or "").strip()
                    or str((rate.get("servicelevel") or {}).get("name") or "").strip()
                    or "Shipping rate"
                ),
                "estimated_days": rate.get("estimated_days"),
            }

    if not best_rate:
        return None

    amount_cents = int(round(best_rate["amount_value"] * 100))
    estimated_days = best_rate["estimated_days"]
    service_level = best_rate["service_name"]
    if isinstance(estimated_days, int) and estimated_days > 0:
        service_level = f"{service_level} · {estimated_days} day{'s' if estimated_days != 1 else ''}"

    destination_summary = f"{address['city']}, {address['state']} {address['postalCode']}"

    return {
        "amount_cents": amount_cents,
        "amount_usd": round(amount_cents / 100, 2),
        "estimated_total_cents": price_cents + amount_cents,
        "estimated_total_usd": round((price_cents + amount_cents) / 100, 2),
        "service_level": service_level,
        "label": f"Live shipping to {address['city']}, {address['state']}",
        "summary": f"{best_rate['provider']} {service_level} for {destination_summary}",
        "destination_summary": destination_summary,
        "destination_state": address["state"],
        "postal_code": address["postalCode"],
        "address": address,
        "rate_kind": "live",
        "is_estimate": False,
        "provider_label": f"{best_rate['provider']} live rate",
        "policy_label": shipping_policy["label"],
        "shippo_rate_id": best_rate["object_id"],
        "shippo_shipment_id": str(shipment.get("object_id") or ""),
        "carrier": best_rate["provider"],
        "service": best_rate["service_name"],
    }


def build_shipping_quote_for_listing(listing_row: sqlite3.Row | dict, raw_address) -> dict:
    address = normalize_shipping_address(raw_address)
    missing = [
        label
        for label, value in [
            ("street address", address["line1"]),
            ("city", address["city"]),
            ("state", address["state"]),
            ("ZIP code", address["postalCode"]),
        ]
        if not value
    ]

    if missing:
        if len(missing) == 1:
            missing_text = missing[0]
        else:
            missing_text = ", ".join(missing[:-1]) + f", and {missing[-1]}"
        raise ValueError(f"Add your {missing_text} so we can estimate shipping.")

    if address["country"] != "US":
        raise ValueError("Shipping estimates are live for U.S. delivery addresses right now.")

    if not ZIP_CODE_RE.fullmatch(address["postalCode"]):
        raise ValueError("Enter a valid U.S. ZIP code so we can estimate shipping.")

    shipping_policy = shipping_policy_from_row(listing_row)
    price_usd = int(row_value(listing_row, "price_usd", 0) or 0)
    price_cents = max(price_usd, 0) * 100
    destination_summary = f"{address['city']}, {address['state']} {address['postalCode']}"

    if shipping_policy["mode"] == "free":
        return {
            "amount_cents": 0,
            "amount_usd": 0,
            "estimated_total_cents": price_cents,
            "estimated_total_usd": round(price_cents / 100, 2),
            "service_level": "Free shipping",
            "label": "Free shipping",
            "summary": f"Seller included shipping for {destination_summary}",
            "destination_summary": destination_summary,
            "destination_state": address["state"],
            "postal_code": address["postalCode"],
            "address": address,
            "rate_kind": "free",
            "is_estimate": False,
            "provider_label": "Seller included shipping",
            "policy_label": shipping_policy["label"],
        }

    if shipping_policy["mode"] == "flat":
        amount_cents = max(0, shipping_policy["flatUsd"]) * 100
        return {
            "amount_cents": amount_cents,
            "amount_usd": round(amount_cents / 100, 2),
            "estimated_total_cents": price_cents + amount_cents,
            "estimated_total_usd": round((price_cents + amount_cents) / 100, 2),
            "service_level": "Flat shipping",
            "label": "Flat shipping",
            "summary": f"Seller-set flat shipping for {destination_summary}",
            "destination_summary": destination_summary,
            "destination_state": address["state"],
            "postal_code": address["postalCode"],
            "address": address,
            "rate_kind": "flat",
            "is_estimate": False,
            "provider_label": "Seller-set flat shipping",
            "policy_label": shipping_policy["label"],
        }

    try:
        shippo_quote = build_shippo_rate_quote_for_listing(listing_row, address, shipping_policy, price_cents)
    except ValueError:
        shippo_quote = None

    if shippo_quote:
        return shippo_quote

    origin_location = compact_whitespace(row_value(listing_row, "location", "") or "")
    origin_state = extract_state_from_location(origin_location)
    origin_city = extract_city_from_location(origin_location)
    destination_state = address["state"]
    destination_city = address["city"]
    origin_zip = shipping_policy["originZip"]
    origin_zip_prefix = origin_zip[:3] if len(origin_zip) >= 3 else ""
    destination_zip_prefix = address["postalCode"][:3]

    if destination_state in {"AK", "HI", "PR"} or origin_state in {"AK", "HI", "PR"}:
        amount_cents = 3200
        service_level = "Extended U.S. estimate"
    elif origin_zip_prefix and origin_zip_prefix == destination_zip_prefix:
        amount_cents = 700
        service_level = "Nearby estimate"
    elif origin_state and origin_state == destination_state:
        amount_cents = 900
        service_level = "In-state estimate"
        if origin_city and normalize_compare_text(origin_city) == normalize_compare_text(destination_city):
            amount_cents = 700
            service_level = "Local estimate"
    elif origin_state and US_STATE_REGION.get(origin_state) == US_STATE_REGION.get(destination_state):
        amount_cents = 1300
        service_level = "Regional estimate"
    elif origin_state:
        amount_cents = 1800
        service_level = "Domestic estimate"
    else:
        amount_cents = 1500
        service_level = "Standard estimate"

    package_weight_oz = shipping_policy["weightOz"] or 24.0
    if package_weight_oz > 64:
        amount_cents += 900
    elif package_weight_oz > 32:
        amount_cents += 500
    elif package_weight_oz > 16:
        amount_cents += 200

    label = f"Estimated shipping to {destination_city}, {destination_state}"

    return {
        "amount_cents": amount_cents,
        "amount_usd": round(amount_cents / 100, 2),
        "estimated_total_cents": price_cents + amount_cents,
        "estimated_total_usd": round((price_cents + amount_cents) / 100, 2),
        "service_level": service_level,
        "label": label,
        "summary": f"{service_level} for {destination_summary}",
        "destination_summary": destination_summary,
        "destination_state": destination_state,
        "postal_code": address["postalCode"],
        "address": address,
        "rate_kind": "estimate",
        "is_estimate": True,
        "provider_label": "Eleven Zero PB estimate",
        "policy_label": shipping_policy["label"],
    }


def slugify(value: str) -> str:
    return "-".join(part for part in "".join(
        ch.lower() if ch.isalnum() else " " for ch in value
    ).split())


def stripe_mode() -> str:
    if not STRIPE_SECRET_KEY:
        return "disabled"
    if STRIPE_SECRET_KEY.startswith("sk_live_"):
        return "live"
    return "test"


def stripe_is_configured() -> bool:
    return bool(STRIPE_SECRET_KEY)


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def add_column_if_missing(
    connection: sqlite3.Connection,
    table: str,
    column_name: str,
    definition: str,
) -> None:
    if column_name not in table_columns(connection, table):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {definition}")


def bool_to_int(value: bool) -> int:
    return 1 if value else 0


COURT_BUSYNESS_LABELS = {
    1: "Quiet",
    2: "Moderate",
    3: "Busy",
    4: "Packed",
}

COURT_PLAYER_LEVEL_LABELS = {
    "beginner": "Beginner-friendly",
    "intermediate": "Intermediate-heavy",
    "advanced": "Advanced-heavy",
    "mixed": "Mixed levels",
}

DIRECTORY_ACCESS_LABELS = {
    "free": "Free",
    "paid": "Paid",
    "check": "Check access",
}

DIRECTORY_SURFACE_LABELS = {
    "indoor": "Indoor",
    "outdoor": "Outdoor",
}

LISTING_APPROVAL_LABELS = {
    "pending": "Pending review",
    "approved": "Live",
    "rejected": "Needs changes",
}

LISTING_SALE_LABELS = {
    "available": "Available",
    "pending": "Sale pending",
    "sold": "Sold",
}

COURT_APPROVAL_LABELS = {
    "pending": "Pending review",
    "approved": "Live",
    "rejected": "Needs changes",
}


def normalize_listing_approval_status(value: str, default: str = "pending") -> str:
    normalized = compact_whitespace(value).lower()
    if normalized in LISTING_APPROVAL_LABELS:
        return normalized
    return default


def normalize_listing_sale_status(value: str, default: str = "available") -> str:
    normalized = compact_whitespace(value).lower()
    if normalized in LISTING_SALE_LABELS:
        return normalized
    return default


def normalize_court_approval_status(value: str, default: str = "pending") -> str:
    normalized = compact_whitespace(value).lower()
    if normalized in COURT_APPROVAL_LABELS:
        return normalized
    return default


def court_condition_label(average: float) -> str:
    if average >= 4.5:
        return "Excellent shape"
    if average >= 3.5:
        return "Solid shape"
    if average >= 2.5:
        return "Playable, some wear"
    return "Needs attention"


def court_busyness_label(average: float) -> str:
    if average >= 3.5:
        return COURT_BUSYNESS_LABELS[4]
    if average >= 2.5:
        return COURT_BUSYNESS_LABELS[3]
    if average >= 1.5:
        return COURT_BUSYNESS_LABELS[2]
    return COURT_BUSYNESS_LABELS[1]


def dominant_court_player_level(level_counts: dict[str, int]) -> str:
    if not level_counts:
        return "mixed"

    ranked = sorted(level_counts.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "mixed"
    return ranked[0][0]


def serialize_court_report_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    return {
        "id": row["id"],
        "courtId": row["court_id"],
        "courtName": row["court_name"],
        "courtLocation": row["court_location"],
        "reviewerName": row["reviewer_name"],
        "conditionRating": row["condition_rating"],
        "busynessRating": row["busyness_rating"],
        "busynessLabel": COURT_BUSYNESS_LABELS.get(int(row["busyness_rating"]), "Unknown"),
        "playerLevel": row["player_level"],
        "playerLevelLabel": COURT_PLAYER_LEVEL_LABELS.get(row["player_level"], "Mixed levels"),
        "comment": row["comment"],
        "createdAt": row["created_at"],
    }


def summarize_court_reports(rows: list[sqlite3.Row]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}

    for row in rows:
        court_id = row["court_id"]
        court_summary = grouped.setdefault(
            court_id,
            {
                "courtId": court_id,
                "courtName": row["court_name"],
                "courtLocation": row["court_location"],
                "reportCount": 0,
                "conditionTotal": 0,
                "busynessTotal": 0,
                "playerLevelCounts": {},
                "latestReportAt": row["created_at"],
            },
        )
        court_summary["reportCount"] += 1
        court_summary["conditionTotal"] += int(row["condition_rating"])
        court_summary["busynessTotal"] += int(row["busyness_rating"])
        level = row["player_level"]
        court_summary["playerLevelCounts"][level] = court_summary["playerLevelCounts"].get(level, 0) + 1

        if row["created_at"] > court_summary["latestReportAt"]:
            court_summary["latestReportAt"] = row["created_at"]

    normalized: dict[str, dict] = {}

    for court_id, item in grouped.items():
        report_count = item["reportCount"]
        condition_average = round(item["conditionTotal"] / report_count, 1)
        busyness_average = round(item["busynessTotal"] / report_count, 1)
        dominant_level = dominant_court_player_level(item["playerLevelCounts"])
        normalized[court_id] = {
            "courtId": court_id,
            "courtName": item["courtName"],
            "courtLocation": item["courtLocation"],
            "reportCount": report_count,
            "conditionAverage": condition_average,
            "conditionLabel": court_condition_label(condition_average),
            "busynessAverage": busyness_average,
            "busynessLabel": court_busyness_label(busyness_average),
            "playerLevel": dominant_level,
            "playerLevelLabel": COURT_PLAYER_LEVEL_LABELS.get(dominant_level, "Mixed levels"),
            "playerLevelCounts": item["playerLevelCounts"],
            "latestReportAt": item["latestReportAt"],
        }

    return normalized


def serialize_directory_court_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    access_kind = row["access_kind"]
    surface_kind = row["surface_kind"]
    court_count = int(row["court_count"] or 0)
    website = (row_value(row, "website", "") or "").strip()
    affiliate_url = (row_value(row, "affiliate_url", "") or "").strip()
    affiliate_label = (row_value(row, "affiliate_label", "") or "").strip()
    access_note = (row_value(row, "access_note", "") or "").strip()
    amenities = (row_value(row, "amenities", "") or "").strip()

    details = [f"{court_count} court{'s' if court_count != 1 else ''}"]
    if access_note:
        details.append(access_note)
    if amenities:
        details.append(amenities)

    return {
        "id": f"directory-{row['id']}",
        "name": row["name"],
        "location": row["location"],
        "address": (row["address"] or row["location"]).strip(),
        "accessKind": access_kind,
        "accessLabel": DIRECTORY_ACCESS_LABELS.get(access_kind, "Check access"),
        "surfaceKind": surface_kind,
        "surfaceLabel": DIRECTORY_SURFACE_LABELS.get(surface_kind, "Surface not set"),
        "details": details[:3],
        "description": row["description"],
        "tags": [access_kind, surface_kind],
        "source": "directory",
        "website": website,
        "affiliateUrl": affiliate_url,
        "affiliateLabel": affiliate_label,
        "osmUrl": "",
        "lat": row["lat"],
        "lon": row["lon"],
        "createdAt": row["created_at"],
    }


def serialize_admin_listing_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    payload = serialize_listing_row(row) or {}
    payload.update(
        {
            "seller_email": row["seller_email"],
        }
    )
    return payload


def serialize_admin_court_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    approval_status = normalize_court_approval_status(
        row_value(row, "approval_status", "approved"), default="approved"
    )
    payload = serialize_directory_court_row(row) or {}
    payload.update(
        {
            "record_id": row["id"],
            "user_id": row["user_id"],
            "owner_name": row["owner_name"],
            "owner_email": row["owner_email"],
            "court_count": row["court_count"],
            "access_note": row["access_note"],
            "amenities": row["amenities"],
            "website": row["website"],
            "affiliateUrl": row_value(row, "affiliate_url", ""),
            "affiliateLabel": row_value(row, "affiliate_label", ""),
            "approval_status": approval_status,
            "approval_label": COURT_APPROVAL_LABELS.get(approval_status, "Pending review"),
            "reviewed_at": row_value(row, "reviewed_at"),
        }
    )
    return payload


def serialize_admin_trainer_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    approval_status = normalize_listing_approval_status(
        row_value(row, "approval_status", "approved"), default="approved"
    )
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "location": row["location"],
        "format": row["format"],
        "level": row["level"],
        "rate": row["rate"],
        "email": row["email"],
        "verified": bool(row["verified"]),
        "experience": row["experience"],
        "bio": row["bio"],
        "availability": row["availability"],
        "joined_at": row["joined_at"],
        "rating": row["rating"],
        "review_count": row["review_count"],
        "owner_name": row["owner_name"],
        "owner_email": row["owner_email"],
        "approval_status": approval_status,
        "approval_label": LISTING_APPROVAL_LABELS.get(approval_status, "Pending review"),
        "reviewed_at": row_value(row, "reviewed_at"),
    }


def serialize_admin_trainer_review_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    return {
        "id": row["id"],
        "trainer_id": row["trainer_id"],
        "trainer_name": row["trainer_name"],
        "reviewer_name": row["reviewer_name"],
        "rating": row["rating"],
        "comment": row["comment"],
        "created_at": row["created_at"],
    }


def serialize_admin_court_report_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    return {
        "id": row["id"],
        "court_id": row["court_id"],
        "court_name": row["court_name"],
        "court_location": row["court_location"],
        "reviewer_name": row["reviewer_name"],
        "condition_rating": row["condition_rating"],
        "busyness_rating": row["busyness_rating"],
        "player_level": row["player_level"],
        "comment": row["comment"],
        "created_at": row["created_at"],
    }


def serialize_admin_profile_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    pending_action = str(row_value(row, "profile_pending_image_action", "keep") or "keep")
    submitted_at = str(row_value(row, "profile_submitted_at", "") or "")
    pending_image_data = str(row_value(row, "profile_pending_image_data", "") or "").strip()
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "currentImagePresent": bool(str(row_value(row, "profile_image_data", "") or "").strip()),
        "pendingName": str(row_value(row, "profile_pending_name", "") or ""),
        "pendingImageAction": pending_action,
        "pendingImageUrl": (
            f"/api/admin/profiles/{row['id']}/pending-image?v={submitted_at or 'pending'}"
            if pending_action == "replace" and pending_image_data
            else ""
        ),
        "profileReviewStatus": str(row_value(row, "profile_review_status", "approved") or "approved"),
        "profileReviewNote": str(row_value(row, "profile_review_note", "") or ""),
        "profileSubmittedAt": submitted_at,
        "profileReviewedAt": str(row_value(row, "profile_reviewed_at", "") or ""),
        "accountStatus": str(row_value(row, "account_status", "active") or "active"),
        "accountStatusNote": str(row_value(row, "account_status_note", "") or ""),
        "accountStatusUpdatedAt": str(row_value(row, "account_status_updated_at", "") or ""),
    }


def stripe_profile_from_row(row: sqlite3.Row | dict | None) -> dict:
    row = row or {}
    account_id = row.get("stripe_account_id") if isinstance(row, dict) else row["stripe_account_id"]
    details_submitted = bool(
        row.get("stripe_details_submitted", 0) if isinstance(row, dict) else row["stripe_details_submitted"]
    )
    charges_enabled = bool(
        row.get("stripe_charges_enabled", 0) if isinstance(row, dict) else row["stripe_charges_enabled"]
    )
    payouts_enabled = bool(
        row.get("stripe_payouts_enabled", 0) if isinstance(row, dict) else row["stripe_payouts_enabled"]
    )
    onboarding_complete = bool(
        row.get("stripe_onboarding_complete", 0)
        if isinstance(row, dict)
        else row["stripe_onboarding_complete"]
    )
    requirements_due_raw = (
        row.get("stripe_requirements_due_count", 0)
        if isinstance(row, dict)
        else row["stripe_requirements_due_count"]
    )
    requirements_due_count = int(requirements_due_raw or 0)
    status_updated_at = (
        row.get("stripe_account_status_updated_at")
        if isinstance(row, dict)
        else row["stripe_account_status_updated_at"]
    )

    return {
        "connectConfigured": stripe_is_configured(),
        "mode": stripe_mode(),
        "platformFeePercent": STRIPE_PLATFORM_FEE_PERCENT,
        "publishableKeyPresent": bool(STRIPE_PUBLISHABLE_KEY),
        "connectedAccountId": account_id or "",
        "hasAccount": bool(account_id),
        "detailsSubmitted": details_submitted,
        "chargesEnabled": charges_enabled,
        "payoutsEnabled": payouts_enabled,
        "onboardingComplete": onboarding_complete,
        "requirementsDueCount": requirements_due_count,
        "readyForPayouts": bool(account_id and details_submitted and charges_enabled and payouts_enabled),
        "statusUpdatedAt": status_updated_at,
    }


def serialize_user(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None

    payload = {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "isAdmin": email_is_admin(row["email"]),
        "emailVerified": bool(row_value(row, "email_verified", 1)),
    }

    profile_image_data = str(row_value(row, "profile_image_data", "") or "").strip()
    profile_image_updated_at = str(row_value(row, "profile_image_updated_at", "") or "").strip()
    payload["profileImageUrl"] = (
        f"/api/account/profile-image?v={profile_image_updated_at or 'current'}"
        if profile_image_data
        else ""
    )
    profile_review_status = str(row_value(row, "profile_review_status", "approved") or "approved")
    pending_image_action = str(row_value(row, "profile_pending_image_action", "keep") or "keep")
    pending_image_data = str(row_value(row, "profile_pending_image_data", "") or "").strip()
    submitted_at = str(row_value(row, "profile_submitted_at", "") or "")
    payload.update(
        {
            "profileReviewStatus": profile_review_status,
            "profileReviewNote": str(row_value(row, "profile_review_note", "") or ""),
            "profilePendingName": str(row_value(row, "profile_pending_name", "") or ""),
            "profilePendingImageAction": pending_image_action,
            "profilePendingImageUrl": (
                f"/api/account/profile-pending-image?v={submitted_at or 'pending'}"
                if profile_review_status == "pending"
                and pending_image_action == "replace"
                and pending_image_data
                else ""
            ),
            "accountStatus": str(row_value(row, "account_status", "active") or "active"),
        }
    )

    if "created_at" in row.keys():
        payload["created_at"] = row["created_at"]

    stripe_fields = {
        "stripe_account_id",
        "stripe_details_submitted",
        "stripe_charges_enabled",
        "stripe_payouts_enabled",
        "stripe_onboarding_complete",
        "stripe_requirements_due_count",
        "stripe_account_status_updated_at",
    }

    if stripe_fields.issubset(set(row.keys())):
        payload["sellerProfile"] = stripe_profile_from_row(row)

    return payload


def stripe_request(method: str, path: str, data: dict | None = None) -> dict:
    if not stripe_is_configured():
        raise RuntimeError("Stripe is not configured yet. Add your Stripe keys before starting seller onboarding.")

    encoded = urlencode(data or {}, doseq=True)
    url = f"{STRIPE_API_BASE}{path}"
    body = None

    if method.upper() == "GET":
        if encoded:
            url = f"{url}?{encoded}"
    else:
        body = encoded.encode("utf-8")

    request = Request(url, data=body, method=method.upper())
    request.add_header("Authorization", f"Bearer {STRIPE_SECRET_KEY}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {}
        message = payload.get("error", {}).get("message") or raw or "Stripe request failed."
        raise ValueError(message) from exc
    except URLError as exc:
        raise ValueError("Stripe could not be reached right now.") from exc


def shippo_request(path: str, payload: dict) -> dict:
    if not shippo_is_configured():
        raise RuntimeError("Shippo is not configured yet.")

    request = Request(
        f"https://api.goshippo.com{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Authorization", f"ShippoToken {SHIPPO_API_KEY}")
    request.add_header("Content-Type", "application/json")

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError:
            parsed = {}
        detail = parsed.get("detail")
        if isinstance(detail, list):
            message = "; ".join(str(item) for item in detail if item)
        else:
            message = str(detail or raw or "Shippo request failed.")
        raise ValueError(message) from exc
    except URLError as exc:
        raise ValueError("Shippo could not be reached right now.") from exc


def shippo_transaction_error(transaction: dict) -> str:
    messages = transaction.get("messages") or []
    if isinstance(messages, list):
        text = "; ".join(
            compact_whitespace(
                item.get("text") if isinstance(item, dict) else str(item)
            )
            for item in messages
            if item
        )
        if text:
            return text
    return "Shippo did not create a shipping label."


def transactional_email_is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_PORT and SMTP_USERNAME and SMTP_PASSWORD and EMAIL_FROM)


def create_auth_token(user_id: int, purpose: str, lifetime_minutes: int = 60) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=lifetime_minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    with closing(connect_db()) as connection:
        connection.execute(
            "UPDATE auth_tokens SET used_at = ? WHERE user_id = ? AND purpose = ? AND used_at IS NULL",
            (utc_now(), user_id, purpose),
        )
        connection.execute(
            """
            INSERT INTO auth_tokens (user_id, purpose, token_hash, expires_at, used_at, created_at)
            VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (user_id, purpose, token_hash, expires_at, utc_now()),
        )
        connection.commit()
    return token


def send_account_action_email(
    recipient: str,
    subject: str,
    heading: str,
    copy: str,
    button_label: str,
    action_url: str,
) -> None:
    if not transactional_email_is_configured():
        raise RuntimeError("Transactional email is not configured.")

    safe_heading = escape(heading)
    safe_copy = escape(copy)
    safe_label = escape(button_label)
    safe_url = escape(action_url, quote=True)
    safe_support = escape(SUPPORT_EMAIL or EMAIL_FROM)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Eleven Zero PB <{EMAIL_FROM}>"
    message["To"] = recipient
    message.set_content(f"{heading}\n\n{copy}\n\n{action_url}\n\nQuestions? {SUPPORT_EMAIL or EMAIL_FROM}")
    message.add_alternative(
        f"""<!doctype html><html><body style="margin:0;background:#f6f2e8;font-family:Arial,sans-serif;color:#042814;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:28px 14px;">
        <table role="presentation" width="560" style="width:100%;max-width:560px;background:#fff;border-radius:24px;overflow:hidden;">
        <tr><td style="padding:24px 30px;background:#032d17;color:#00ed64;font-size:24px;font-weight:800;">Eleven Zero PB</td></tr>
        <tr><td style="padding:34px 30px;"><h1 style="margin:0 0 14px;font-size:30px;">{safe_heading}</h1>
        <p style="margin:0 0 24px;color:#5d6f64;line-height:1.65;">{safe_copy}</p>
        <a href="{safe_url}" style="display:inline-block;padding:14px 22px;border-radius:999px;background:#00ed64;color:#032d17;font-weight:800;text-decoration:none;">{safe_label}</a>
        <p style="margin:24px 0 0;color:#7b8b82;font-size:12px;line-height:1.6;">If you did not request this, you can ignore this email. Questions? {safe_support}</p>
        </td></tr></table></td></tr></table></body></html>""",
        subtype="html",
    )

    if SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
    else:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
    with server:
        if SMTP_USE_TLS and not SMTP_USE_SSL:
            server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)


def send_verification_email(user_id: int, email: str) -> bool:
    if not transactional_email_is_configured():
        return False
    token = create_auth_token(user_id, "verify_email", lifetime_minutes=24 * 60)
    site_url = (SITE_URL or "http://127.0.0.1:8000").rstrip("/")
    action_url = f"{site_url}/auth.html?mode=verify&token={urlencode({'token': token})[6:]}"
    try:
        send_account_action_email(
            email,
            "Verify your Eleven Zero PB email",
            "Verify your email",
            "Confirm this email address so your account and marketplace activity stay protected.",
            "Verify email",
            action_url,
        )
    except (OSError, RuntimeError, smtplib.SMTPException):
        return False
    return True


def order_email_row(session_id: str) -> sqlite3.Row | None:
    with closing(connect_db()) as connection:
        return connection.execute(
            """
            SELECT
              orders.*,
              listings.brand,
              listings.model,
              buyers.name AS buyer_name,
              buyers.email AS buyer_email,
              sellers.name AS seller_name,
              sellers.email AS seller_email
            FROM orders
            LEFT JOIN listings ON listings.id = orders.listing_id
            LEFT JOIN users AS buyers ON buyers.id = orders.buyer_user_id
            LEFT JOIN users AS sellers ON sellers.id = orders.seller_user_id
            WHERE orders.stripe_checkout_session_id = ?
            """,
            (session_id,),
        ).fetchone()


def build_purchase_confirmation_message(
    order_row: sqlite3.Row,
    title: str,
    total: float,
    shipping: float,
    destination: str,
) -> EmailMessage:
    """Build a branded, email-client-safe receipt with a plain-text fallback."""
    site_url = (SITE_URL or "https://11zeropb.com").rstrip("/")
    account_url = f"{site_url}/account.html"
    logo_path = APP_ROOT / "assets" / "logo-primary.png"
    logo_src = "cid:eleven-zero-logo" if logo_path.exists() else f"{site_url}/assets/logo-primary.png"
    buyer_name = compact_whitespace(order_row["buyer_name"] or "") or "there"
    seller_name = compact_whitespace(order_row["seller_name"] or "") or "Eleven Zero PB seller"
    order_reference = f"EZPB-{order_row['id']}"
    paddle_price = max(total - shipping, 0)

    message = EmailMessage()
    message["Subject"] = f"Order confirmed — {title}"
    message["From"] = f"Eleven Zero PB <{EMAIL_FROM}>"
    message["To"] = compact_whitespace(order_row["buyer_email"] or "")
    message.set_content(
        "\n".join(
            [
                f"Hi {buyer_name},",
                "",
                f"Your purchase of {title} is confirmed.",
                f"Paddle price: ${paddle_price:,.2f}",
                f"Shipping: ${shipping:,.2f}",
                f"Order total: ${total:,.2f}",
                f"Seller: {seller_name}",
                *([f"Shipping to: {destination}"] if destination else []),
                "",
                "What happens next:",
                "1. The seller prepares your prepaid shipping label.",
                "2. Shipping and tracking updates stay connected to your Eleven Zero PB account.",
                f"Order reference: {order_reference}",
                "",
                f"View your account: {account_url}",
                "",
                "Questions? Reply to this email and the Eleven Zero PB team will help.",
                "",
                "Eleven Zero PB",
                site_url,
            ]
        )
    )

    safe_buyer_name = escape(buyer_name)
    safe_title = escape(title)
    safe_seller_name = escape(seller_name)
    safe_destination = escape(destination)
    safe_order_reference = escape(order_reference)
    safe_account_url = escape(account_url, quote=True)
    safe_site_url = escape(site_url, quote=True)
    safe_support_email = escape(SUPPORT_EMAIL or EMAIL_FROM, quote=True)
    shipping_destination_html = ""
    if destination:
        shipping_destination_html = f"""
          <tr>
            <td style="padding:0 0 18px;color:#5d6f64;font-size:14px;line-height:1.5;">Shipping to</td>
            <td align="right" style="padding:0 0 18px;color:#042814;font-size:14px;font-weight:700;line-height:1.5;">{safe_destination}</td>
          </tr>"""

    message.add_alternative(
        f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Order confirmed</title>
  </head>
  <body style="margin:0;padding:0;background:#f6f2e8;color:#042814;font-family:'Avenir Next','Segoe UI',Arial,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">Your {safe_title} purchase is confirmed. Order {safe_order_reference}.</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f6f2e8;">
      <tr>
        <td align="center" style="padding:28px 14px;">
          <table role="presentation" width="620" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:620px;background:#ffffff;border-radius:28px;overflow:hidden;box-shadow:0 18px 48px rgba(3,45,23,.12);">
            <tr>
              <td style="padding:26px 34px;background:#032d17;">
                <a href="{safe_site_url}" style="display:inline-block;text-decoration:none;">
                  <img src="{logo_src}" width="210" alt="Eleven Zero PB" style="display:block;width:210px;max-width:100%;height:auto;border:0;">
                </a>
              </td>
            </tr>
            <tr>
              <td style="padding:38px 34px 18px;">
                <span style="display:inline-block;padding:8px 13px;border-radius:999px;background:#d9ffe5;color:#06552a;font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;">✓ Payment confirmed</span>
                <h1 style="margin:20px 0 12px;color:#042814;font-size:34px;line-height:1.08;letter-spacing:-.025em;">Your order is confirmed.</h1>
                <p style="margin:0;color:#5d6f64;font-size:16px;line-height:1.65;">Hi {safe_buyer_name}, your purchase is confirmed. We’ll keep the shipping process connected to your Eleven Zero PB account.</p>
              </td>
            </tr>
            <tr>
              <td style="padding:12px 34px 8px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;border:1px solid #e4ebe6;border-radius:20px;">
                  <tr>
                    <td colspan="2" style="padding:22px 22px 18px;border-bottom:1px solid #e4ebe6;">
                      <div style="color:#5d6f64;font-size:12px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;">Order summary</div>
                      <div style="margin-top:8px;color:#042814;font-size:21px;font-weight:800;line-height:1.3;">{safe_title}</div>
                    </td>
                  </tr>
                  <tr>
                    <td colspan="2" style="padding:22px 22px 4px;">
                      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                        <tr>
                          <td style="padding:0 0 18px;color:#5d6f64;font-size:14px;">Seller</td>
                          <td align="right" style="padding:0 0 18px;color:#042814;font-size:14px;font-weight:700;">{safe_seller_name}</td>
                        </tr>
                        {shipping_destination_html}
                        <tr>
                          <td style="padding:0 0 18px;color:#5d6f64;font-size:14px;">Paddle price</td>
                          <td align="right" style="padding:0 0 18px;color:#042814;font-size:14px;font-weight:700;">${paddle_price:,.2f}</td>
                        </tr>
                        <tr>
                          <td style="padding:0 0 18px;color:#5d6f64;font-size:14px;">Shipping</td>
                          <td align="right" style="padding:0 0 18px;color:#042814;font-size:14px;font-weight:700;">${shipping:,.2f}</td>
                        </tr>
                        <tr>
                          <td style="padding:17px 0 19px;border-top:1px solid #e4ebe6;color:#042814;font-size:16px;font-weight:800;">Order total</td>
                          <td align="right" style="padding:17px 0 19px;border-top:1px solid #e4ebe6;color:#042814;font-size:22px;font-weight:900;">${total:,.2f}</td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:22px 34px 8px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f3fff6;border-radius:20px;">
                  <tr>
                    <td style="padding:22px;">
                      <div style="color:#042814;font-size:16px;font-weight:800;">What happens next</div>
                      <p style="margin:10px 0 0;color:#5d6f64;font-size:14px;line-height:1.65;">The seller prepares the prepaid shipping label. Tracking updates will remain connected to your account.</p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:26px 34px 34px;">
                <a href="{safe_account_url}" style="display:inline-block;padding:15px 25px;border-radius:999px;background:#00ed64;color:#032d17;font-size:15px;font-weight:900;text-decoration:none;">View your account</a>
                <p style="margin:20px 0 0;color:#7b8b82;font-size:12px;line-height:1.6;">Order reference: <strong style="color:#52645a;">{safe_order_reference}</strong></p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:24px 34px;background:#032d17;color:#b8cabf;font-size:12px;line-height:1.7;">
                Questions? Reply to this email or contact <a href="mailto:{safe_support_email}" style="color:#00ed64;text-decoration:none;">{safe_support_email}</a>.<br>
                Eleven Zero PB · Built for the pickleball community
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>""",
        subtype="html",
    )

    if logo_path.exists():
        html_part = message.get_payload()[-1]
        html_part.add_related(
            logo_path.read_bytes(),
            maintype="image",
            subtype="png",
            cid="<eleven-zero-logo>",
            filename="eleven-zero-pb.png",
            disposition="inline",
        )

    return message


def send_purchase_confirmation_for_order(session_id: str) -> sqlite3.Row | None:
    """Send one branded buyer receipt without allowing an email failure to break checkout."""
    order_row = order_email_row(session_id)
    if not order_row or order_row["status"] != "paid":
        return order_row
    if order_row["buyer_confirmation_sent_at"]:
        return order_row

    buyer_email = compact_whitespace(order_row["buyer_email"] or "")
    if "@" not in buyer_email:
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET buyer_confirmation_status = 'error',
                    buyer_confirmation_error = 'The buyer account does not have a valid email address.'
                WHERE stripe_checkout_session_id = ?
                  AND buyer_confirmation_sent_at IS NULL
                """,
                (session_id,),
            )
            connection.commit()
        return order_email_row(session_id)

    if not transactional_email_is_configured():
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET buyer_confirmation_status = 'not_configured',
                    buyer_confirmation_error = 'Transactional email is not configured.'
                WHERE stripe_checkout_session_id = ?
                  AND buyer_confirmation_sent_at IS NULL
                """,
                (session_id,),
            )
            connection.commit()
        return order_email_row(session_id)

    with closing(connect_db()) as connection:
        claimed = connection.execute(
            """
            UPDATE orders
            SET buyer_confirmation_status = 'sending', buyer_confirmation_error = ''
            WHERE stripe_checkout_session_id = ?
              AND buyer_confirmation_sent_at IS NULL
              AND buyer_confirmation_status IN ('pending', 'error', 'not_configured')
            """,
            (session_id,),
        )
        connection.commit()
        if claimed.rowcount != 1:
            return order_email_row(session_id)

    title = " ".join(
        part for part in [order_row["brand"], order_row["model"]] if compact_whitespace(part)
    ).strip() or "pickleball paddle"
    total = int(order_row["amount_total_cents"] or 0) / 100
    shipping = int(order_row["shipping_amount_cents"] or 0) / 100
    address = {}
    try:
        address = json.loads(order_row["shipping_address_json"] or "{}")
    except json.JSONDecodeError:
        address = {}
    destination = ", ".join(
        part
        for part in [
            compact_whitespace(address.get("city", "")),
            " ".join(
                part
                for part in [
                    compact_whitespace(address.get("state", "")),
                    compact_whitespace(address.get("postalCode", "")),
                ]
                if part
            ),
        ]
        if part
    )

    message = build_purchase_confirmation_message(order_row, title, total, shipping, destination)

    try:
        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        with server:
            if SMTP_USE_TLS and not SMTP_USE_SSL:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET buyer_confirmation_status = 'sent',
                    buyer_confirmation_sent_at = ?,
                    buyer_confirmation_error = ''
                WHERE stripe_checkout_session_id = ?
                """,
                (utc_now(), session_id),
            )
            connection.commit()
    except (OSError, TypeError, ValueError, smtplib.SMTPException) as error:
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET buyer_confirmation_status = 'error', buyer_confirmation_error = ?
                WHERE stripe_checkout_session_id = ?
                """,
                (compact_whitespace(str(error))[:500], session_id),
            )
            connection.commit()

    return order_email_row(session_id)


def build_seller_shipping_label_message(
    order_row: sqlite3.Row,
    title: str,
    destination: str,
) -> EmailMessage:
    """Build the seller's branded label-ready email with packing instructions."""
    site_url = (SITE_URL or "https://11zeropb.com").rstrip("/")
    account_url = f"{site_url}/account.html"
    logo_path = APP_ROOT / "assets" / "logo-primary.png"
    logo_src = "cid:eleven-zero-logo" if logo_path.exists() else f"{site_url}/assets/logo-primary.png"
    seller_name = compact_whitespace(order_row["seller_name"] or "") or "there"
    buyer_name = compact_whitespace(order_row["buyer_name"] or "") or "the buyer"
    label_url = compact_whitespace(order_row["shippo_label_url"] or "")
    tracking_number = compact_whitespace(order_row["tracking_number"] or "")
    tracking_url = compact_whitespace(order_row["tracking_url"] or "")
    carrier = compact_whitespace(order_row["shipping_carrier"] or "")
    service = compact_whitespace(order_row["shipping_service"] or "")
    shipping_service = " · ".join(part for part in [carrier, service] if part) or "Prepaid shipping"
    order_reference = f"EZPB-{order_row['id']}"

    message = EmailMessage()
    message["Subject"] = f"Shipping label ready — {title}"
    message["From"] = f"Eleven Zero PB <{EMAIL_FROM}>"
    message["To"] = compact_whitespace(order_row["seller_email"] or "")
    message.set_content(
        "\n".join(
            [
                f"Hi {seller_name},",
                "",
                f"Your prepaid shipping label for {title} is ready.",
                f"Buyer: {buyer_name}",
                *([f"Ship to: {destination}"] if destination else []),
                f"Shipping service: {shipping_service}",
                *([f"Tracking number: {tracking_number}"] if tracking_number else []),
                f"Order reference: {order_reference}",
                "",
                f"Open and print the prepaid label: {label_url}",
                "",
                "How to ship the paddle:",
                "1. Open the label and print it at 100% or Actual Size.",
                "2. Place the paddle in a rigid box with padding around the face, edges, and handle.",
                "3. Seal the box securely and remove or fully cover every old label and barcode.",
                "4. Attach the new label flat on the largest side. Keep the barcode uncovered.",
                f"5. Drop the package off with {carrier or 'the carrier shown on the label'}.",
                "6. Keep the drop-off receipt until delivery is confirmed.",
                "",
                *([f"Track the package: {tracking_url}"] if tracking_url else []),
                f"Manage this order: {account_url}",
                "",
                "Questions? Reply to this email and the Eleven Zero PB team will help.",
                "",
                "Eleven Zero PB",
                site_url,
            ]
        )
    )

    safe_seller_name = escape(seller_name)
    safe_buyer_name = escape(buyer_name)
    safe_title = escape(title)
    safe_destination = escape(destination)
    safe_shipping_service = escape(shipping_service)
    safe_tracking_number = escape(tracking_number)
    safe_order_reference = escape(order_reference)
    safe_label_url = escape(label_url, quote=True)
    safe_tracking_url = escape(tracking_url, quote=True)
    safe_account_url = escape(account_url, quote=True)
    safe_site_url = escape(site_url, quote=True)
    safe_support_email = escape(SUPPORT_EMAIL or EMAIL_FROM, quote=True)

    destination_html = ""
    if destination:
        destination_html = f"""
                        <tr>
                          <td style="padding:0 0 16px;color:#5d6f64;font-size:14px;">Ship to</td>
                          <td align="right" style="padding:0 0 16px;color:#042814;font-size:14px;font-weight:700;">{safe_destination}</td>
                        </tr>"""
    tracking_html = ""
    if tracking_number:
        tracking_value = safe_tracking_number
        if tracking_url:
            tracking_value = f'<a href="{safe_tracking_url}" style="color:#06552a;text-decoration:underline;">{safe_tracking_number}</a>'
        tracking_html = f"""
                        <tr>
                          <td style="padding:0 0 16px;color:#5d6f64;font-size:14px;">Tracking</td>
                          <td align="right" style="padding:0 0 16px;color:#042814;font-size:14px;font-weight:700;">{tracking_value}</td>
                        </tr>"""

    message.add_alternative(
        f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Shipping label ready</title>
  </head>
  <body style="margin:0;padding:0;background:#f6f2e8;color:#042814;font-family:'Avenir Next','Segoe UI',Arial,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">Print the prepaid label for {safe_title} and prepare order {safe_order_reference} for drop-off.</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f6f2e8;">
      <tr>
        <td align="center" style="padding:28px 14px;">
          <table role="presentation" width="620" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:620px;background:#ffffff;border-radius:28px;overflow:hidden;box-shadow:0 18px 48px rgba(3,45,23,.12);">
            <tr>
              <td style="padding:26px 34px;background:#032d17;">
                <a href="{safe_site_url}" style="display:inline-block;text-decoration:none;">
                  <img src="{logo_src}" width="210" alt="Eleven Zero PB" style="display:block;width:210px;max-width:100%;height:auto;border:0;">
                </a>
              </td>
            </tr>
            <tr>
              <td style="padding:38px 34px 16px;">
                <span style="display:inline-block;padding:8px 13px;border-radius:999px;background:#d9ffe5;color:#06552a;font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;">✓ Ready to ship</span>
                <h1 style="margin:20px 0 12px;color:#042814;font-size:34px;line-height:1.08;letter-spacing:-.025em;">Your shipping label is ready.</h1>
                <p style="margin:0;color:#5d6f64;font-size:16px;line-height:1.65;">Hi {safe_seller_name}, the prepaid label for <strong style="color:#042814;">{safe_title}</strong> is ready to print. Follow the steps below to ship it safely.</p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:16px 34px 22px;">
                <a href="{safe_label_url}" style="display:inline-block;padding:16px 28px;border-radius:999px;background:#00ed64;color:#032d17;font-size:15px;font-weight:900;text-decoration:none;">Open shipping label</a>
                <p style="margin:12px 0 0;color:#7b8b82;font-size:12px;line-height:1.6;">Print at 100% or Actual Size. Do not resize the barcode.</p>
              </td>
            </tr>
            <tr>
              <td style="padding:4px 34px 8px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;border:1px solid #e4ebe6;border-radius:20px;">
                  <tr>
                    <td colspan="2" style="padding:22px 22px 18px;border-bottom:1px solid #e4ebe6;">
                      <div style="color:#5d6f64;font-size:12px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;">Shipment summary</div>
                      <div style="margin-top:8px;color:#042814;font-size:21px;font-weight:800;line-height:1.3;">{safe_title}</div>
                    </td>
                  </tr>
                  <tr>
                    <td colspan="2" style="padding:22px 22px 4px;">
                      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                        <tr>
                          <td style="padding:0 0 16px;color:#5d6f64;font-size:14px;">Buyer</td>
                          <td align="right" style="padding:0 0 16px;color:#042814;font-size:14px;font-weight:700;">{safe_buyer_name}</td>
                        </tr>
                        {destination_html}
                        <tr>
                          <td style="padding:0 0 16px;color:#5d6f64;font-size:14px;">Service</td>
                          <td align="right" style="padding:0 0 16px;color:#042814;font-size:14px;font-weight:700;">{safe_shipping_service}</td>
                        </tr>
                        {tracking_html}
                        <tr>
                          <td style="padding:16px 0 18px;border-top:1px solid #e4ebe6;color:#5d6f64;font-size:14px;">Order reference</td>
                          <td align="right" style="padding:16px 0 18px;border-top:1px solid #e4ebe6;color:#042814;font-size:14px;font-weight:800;">{safe_order_reference}</td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:22px 34px 8px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f3fff6;border-radius:20px;">
                  <tr>
                    <td style="padding:24px;">
                      <div style="color:#042814;font-size:17px;font-weight:900;">Pack and ship in six steps</div>
                      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:14px;">
                        <tr><td valign="top" style="width:26px;padding:0 8px 10px 0;color:#06552a;font-size:14px;font-weight:900;">1.</td><td style="padding:0 0 10px;color:#52645a;font-size:14px;line-height:1.55;">Print the label at 100% or Actual Size.</td></tr>
                        <tr><td valign="top" style="width:26px;padding:0 8px 10px 0;color:#06552a;font-size:14px;font-weight:900;">2.</td><td style="padding:0 0 10px;color:#52645a;font-size:14px;line-height:1.55;">Protect the paddle in a rigid box with padding around the face, edges, and handle.</td></tr>
                        <tr><td valign="top" style="width:26px;padding:0 8px 10px 0;color:#06552a;font-size:14px;font-weight:900;">3.</td><td style="padding:0 0 10px;color:#52645a;font-size:14px;line-height:1.55;">Seal the box securely and remove or cover old labels and barcodes.</td></tr>
                        <tr><td valign="top" style="width:26px;padding:0 8px 10px 0;color:#06552a;font-size:14px;font-weight:900;">4.</td><td style="padding:0 0 10px;color:#52645a;font-size:14px;line-height:1.55;">Attach the label flat on the largest side and keep the barcode uncovered.</td></tr>
                        <tr><td valign="top" style="width:26px;padding:0 8px 10px 0;color:#06552a;font-size:14px;font-weight:900;">5.</td><td style="padding:0 0 10px;color:#52645a;font-size:14px;line-height:1.55;">Drop it off with the carrier shown on the label.</td></tr>
                        <tr><td valign="top" style="width:26px;padding:0 8px 0 0;color:#06552a;font-size:14px;font-weight:900;">6.</td><td style="padding:0;color:#52645a;font-size:14px;line-height:1.55;">Keep the drop-off receipt until delivery is confirmed.</td></tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:26px 34px 34px;">
                <a href="{safe_account_url}" style="display:inline-block;color:#06552a;font-size:14px;font-weight:800;text-decoration:underline;">Manage this order in your account</a>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:24px 34px;background:#032d17;color:#b8cabf;font-size:12px;line-height:1.7;">
                Questions? Reply to this email or contact <a href="mailto:{safe_support_email}" style="color:#00ed64;text-decoration:none;">{safe_support_email}</a>.<br>
                Eleven Zero PB · Built for the pickleball community
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>""",
        subtype="html",
    )

    if logo_path.exists():
        html_part = message.get_payload()[-1]
        html_part.add_related(
            logo_path.read_bytes(),
            maintype="image",
            subtype="png",
            cid="<eleven-zero-logo>",
            filename="eleven-zero-pb.png",
            disposition="inline",
        )

    return message


def send_seller_shipping_label_email_for_order(session_id: str) -> sqlite3.Row | None:
    """Send the prepaid label to the seller once without blocking fulfillment."""
    order_row = order_email_row(session_id)
    if not order_row or order_row["shipping_status"] != "label_ready":
        return order_row
    if not compact_whitespace(order_row["shippo_label_url"] or ""):
        return order_row
    if order_row["seller_label_email_sent_at"]:
        return order_row

    seller_email = compact_whitespace(order_row["seller_email"] or "")
    if "@" not in seller_email:
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET seller_label_email_status = 'error',
                    seller_label_email_error = 'The seller account does not have a valid email address.'
                WHERE stripe_checkout_session_id = ?
                  AND seller_label_email_sent_at IS NULL
                """,
                (session_id,),
            )
            connection.commit()
        return order_email_row(session_id)

    if not transactional_email_is_configured():
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET seller_label_email_status = 'not_configured',
                    seller_label_email_error = 'Transactional email is not configured.'
                WHERE stripe_checkout_session_id = ?
                  AND seller_label_email_sent_at IS NULL
                """,
                (session_id,),
            )
            connection.commit()
        return order_email_row(session_id)

    with closing(connect_db()) as connection:
        claimed = connection.execute(
            """
            UPDATE orders
            SET seller_label_email_status = 'sending', seller_label_email_error = ''
            WHERE stripe_checkout_session_id = ?
              AND seller_label_email_sent_at IS NULL
              AND seller_label_email_status IN ('pending', 'error', 'not_configured')
            """,
            (session_id,),
        )
        connection.commit()
        if claimed.rowcount != 1:
            return order_email_row(session_id)

    title = " ".join(
        part for part in [order_row["brand"], order_row["model"]] if compact_whitespace(part)
    ).strip() or "pickleball paddle"
    address = {}
    try:
        address = json.loads(order_row["shipping_address_json"] or "{}")
    except json.JSONDecodeError:
        address = {}
    destination = ", ".join(
        part
        for part in [
            compact_whitespace(address.get("city", "")),
            " ".join(
                part
                for part in [
                    compact_whitespace(address.get("state", "")),
                    compact_whitespace(address.get("postalCode", "")),
                ]
                if part
            ),
        ]
        if part
    )
    message = build_seller_shipping_label_message(order_row, title, destination)

    try:
        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        with server:
            if SMTP_USE_TLS and not SMTP_USE_SSL:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET seller_label_email_status = 'sent',
                    seller_label_email_sent_at = ?,
                    seller_label_email_error = ''
                WHERE stripe_checkout_session_id = ?
                """,
                (utc_now(), session_id),
            )
            connection.commit()
    except (OSError, TypeError, ValueError, smtplib.SMTPException) as error:
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET seller_label_email_status = 'error', seller_label_email_error = ?
                WHERE stripe_checkout_session_id = ?
                """,
                (compact_whitespace(str(error))[:500], session_id),
            )
            connection.commit()

    return order_email_row(session_id)


def mark_listing_sale_pending_for_order(session_id: str) -> None:
    with closing(connect_db()) as connection:
        connection.execute(
            """
            UPDATE listings
            SET sale_status = 'pending'
            WHERE id = (
              SELECT listing_id
              FROM orders
              WHERE stripe_checkout_session_id = ?
                AND (status = 'paid' OR stripe_payment_status = 'paid')
            )
              AND sale_status = 'available'
            """,
            (session_id,),
        )
        connection.commit()


def refresh_shippo_rate_for_order(session_id: str) -> sqlite3.Row | None:
    """Create a fresh live Shippo rate before a deliberate label retry."""
    with closing(connect_db()) as connection:
        order_row = connection.execute(
            """
            SELECT
              orders.*,
              listings.brand,
              listings.model,
              listings.location,
              listings.price_usd,
              listings.shipping_mode,
              listings.shipping_flat_usd,
              listings.shipping_origin_zip,
              listings.shipping_origin_street1,
              listings.shipping_weight_oz,
              listings.shipping_length_in,
              listings.shipping_width_in,
              listings.shipping_height_in,
              listings.shipping_note,
              sellers.name AS seller_name
            FROM orders
            JOIN listings ON listings.id = orders.listing_id
            LEFT JOIN users AS sellers ON sellers.id = orders.seller_user_id
            WHERE orders.stripe_checkout_session_id = ?
            """,
            (session_id,),
        ).fetchone()

    if not order_row:
        return None
    if order_row["shippo_label_url"] or order_row["shippo_transaction_id"]:
        return order_row

    try:
        address = json.loads(order_row["shipping_address_json"] or "{}")
        quote = build_shipping_quote_for_listing(order_row, address)
        if quote.get("rate_kind") != "live" or not quote.get("shippo_rate_id"):
            raise ValueError("Shippo could not return a new live rate for this order.")
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET shippo_rate_id = ?,
                    shippo_shipment_id = ?,
                    shipping_carrier = ?,
                    shipping_service = ?,
                    shipping_status = 'pending',
                    shipping_error = ''
                WHERE stripe_checkout_session_id = ?
                  AND shippo_transaction_id = ''
                  AND shippo_label_url = ''
                """,
                (
                    quote.get("shippo_rate_id", ""),
                    quote.get("shippo_shipment_id", ""),
                    quote.get("carrier", ""),
                    quote.get("service", ""),
                    session_id,
                ),
            )
            connection.commit()
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET shipping_status = 'attention_needed', shipping_error = ?
                WHERE stripe_checkout_session_id = ?
                """,
                (compact_whitespace(str(error))[:500], session_id),
            )
            connection.commit()

    with closing(connect_db()) as connection:
        return connection.execute(
            "SELECT * FROM orders WHERE stripe_checkout_session_id = ?",
            (session_id,),
        ).fetchone()


def finalize_paid_order(session_id: str) -> sqlite3.Row | None:
    mark_listing_sale_pending_for_order(session_id)
    order_row = purchase_shippo_label_for_order(session_id)
    send_purchase_confirmation_for_order(session_id)
    return order_row


def purchase_shippo_label_for_order(session_id: str) -> sqlite3.Row | None:
    """Purchase one label after payment and persist it for the seller.

    The conditional update claims the order before the external request so repeated
    checkout-status calls do not purchase duplicate labels.
    """
    already_ready = False
    with closing(connect_db()) as connection:
        order_row = connection.execute(
            "SELECT * FROM orders WHERE stripe_checkout_session_id = ?",
            (session_id,),
        ).fetchone()
        if not order_row:
            return None
        if order_row["shippo_label_url"] or order_row["shippo_transaction_id"]:
            already_ready = True
        elif not order_row["shippo_rate_id"]:
            return order_row
        else:
            claimed = connection.execute(
                """
                UPDATE orders
                SET shipping_status = 'purchasing', shipping_error = ''
                WHERE stripe_checkout_session_id = ?
                  AND shippo_transaction_id = ''
                  AND shippo_label_url = ''
                  AND shipping_status = 'pending'
                """,
                (session_id,),
            )
            connection.commit()
            if claimed.rowcount != 1:
                return connection.execute(
                    "SELECT * FROM orders WHERE stripe_checkout_session_id = ?",
                    (session_id,),
                ).fetchone()

    if already_ready:
        return send_seller_shipping_label_email_for_order(session_id)

    try:
        transaction = shippo_request(
            "/transactions/",
            {
                "rate": order_row["shippo_rate_id"],
                "label_file_type": SHIPPO_LABEL_FILE_TYPE,
                "async": False,
                "metadata": f"Eleven Zero PB order {order_row['id']}",
            },
        )
        label_url = str(transaction.get("label_url") or "").strip()
        transaction_id = str(transaction.get("object_id") or "").strip()
        tracking_number = str(transaction.get("tracking_number") or "").strip()
        tracking_url = str(transaction.get("tracking_url_provider") or "").strip()
        transaction_status = str(transaction.get("status") or "").strip().upper()
        if transaction_status == "ERROR" or not label_url:
            raise ValueError(shippo_transaction_error(transaction))

        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET
                  shippo_transaction_id = ?,
                  shippo_label_url = ?,
                  tracking_number = ?,
                  tracking_url = ?,
                  shipping_status = 'label_ready',
                  shipping_error = ''
                WHERE stripe_checkout_session_id = ?
                """,
                (transaction_id, label_url, tracking_number, tracking_url, session_id),
            )
            connection.commit()
        return send_seller_shipping_label_email_for_order(session_id)
    except (RuntimeError, ValueError) as error:
        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET shipping_status = 'attention_needed', shipping_error = ?
                WHERE stripe_checkout_session_id = ?
                """,
                (compact_whitespace(str(error))[:500], session_id),
            )
            connection.commit()
            return connection.execute(
                "SELECT * FROM orders WHERE stripe_checkout_session_id = ?",
                (session_id,),
            ).fetchone()


def google_places_is_configured() -> bool:
    return bool(GOOGLE_PLACES_API_KEY)


def google_places_request(path: str, payload: dict, *, field_mask: str) -> dict:
    if not google_places_is_configured():
        raise RuntimeError("Google Places is not configured yet.")

    request = Request(
        f"https://places.googleapis.com/v1{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Goog-Api-Key", GOOGLE_PLACES_API_KEY)
    request.add_header("X-Goog-FieldMask", field_mask)

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError:
            parsed = {}
        detail = parsed.get("error", {}).get("message") or parsed.get("message") or raw
        raise ValueError(str(detail or "Google Places request failed.")) from exc
    except URLError as exc:
        raise ValueError("Google Places could not be reached right now.") from exc


def google_places_search_courts(query: str, page_size: int = 20) -> list[dict]:
    clean_query = str(query or "").strip()
    if not clean_query:
        raise ValueError("Add a city, state, or zip code first.")

    search_query = (
        clean_query
        if "pickleball" in clean_query.lower()
        else f"pickleball courts in {clean_query}"
    )
    safe_page_size = min(max(int(page_size or 20), 1), 20)
    field_mask = (
        "places.id,"
        "places.displayName,"
        "places.formattedAddress,"
        "places.shortFormattedAddress,"
        "places.location,"
        "places.googleMapsUri,"
        "places.websiteUri,"
        "places.primaryType,"
        "places.primaryTypeDisplayName,"
        "places.types,"
        "nextPageToken"
    )

    collected: list[dict] = []
    seen_ids: set[str] = set()
    next_page_token: str | None = None

    for _ in range(3):
        payload: dict[str, object] = {
            "textQuery": search_query,
            "pageSize": safe_page_size,
        }
        if next_page_token:
            payload["pageToken"] = next_page_token

        response = google_places_request(
            "/places:searchText",
            payload,
            field_mask=field_mask,
        )

        for place in response.get("places", []) or []:
            place_id = str(place.get("id") or "").strip()
            if not place_id or place_id in seen_ids:
                continue
            seen_ids.add(place_id)
            collected.append(place)

        next_page_token = str(response.get("nextPageToken") or "").strip() or None
        if not next_page_token:
            break

    return collected


def init_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with closing(connect_db()) as connection:
      # fmt: off
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE,
              password_salt TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              profile_image_data TEXT NOT NULL DEFAULT '',
              profile_image_updated_at TEXT,
              profile_pending_name TEXT,
              profile_pending_image_data TEXT,
              profile_pending_image_action TEXT NOT NULL DEFAULT 'keep',
              profile_review_status TEXT NOT NULL DEFAULT 'approved',
              profile_review_note TEXT,
              profile_submitted_at TEXT,
              profile_reviewed_at TEXT,
              account_status TEXT NOT NULL DEFAULT 'active',
              account_status_note TEXT,
              account_status_updated_at TEXT,
              email_verified INTEGER NOT NULL DEFAULT 0,
              email_verified_at TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              csrf_token TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_tokens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              purpose TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,
              expires_at TEXT NOT NULL,
              used_at TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS listings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              brand TEXT NOT NULL,
              model TEXT NOT NULL,
              color TEXT NOT NULL DEFAULT '',
              thickness_mm REAL,
              category TEXT NOT NULL,
              condition TEXT NOT NULL,
              price_usd INTEGER NOT NULL,
              location TEXT NOT NULL,
              notes TEXT NOT NULL,
              shipping_mode TEXT NOT NULL DEFAULT 'calculated',
              shipping_flat_usd INTEGER NOT NULL DEFAULT 0,
              shipping_origin_zip TEXT NOT NULL DEFAULT '',
              shipping_origin_street1 TEXT NOT NULL DEFAULT '',
              shipping_weight_oz REAL,
              shipping_length_in REAL,
              shipping_width_in REAL,
              shipping_height_in REAL,
              shipping_note TEXT NOT NULL DEFAULT '',
              image_data_json TEXT NOT NULL DEFAULT '[]',
              approval_status TEXT NOT NULL DEFAULT 'approved',
              sale_status TEXT NOT NULL DEFAULT 'available',
              reviewed_at TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trainers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              name TEXT NOT NULL,
              location TEXT NOT NULL,
              format TEXT NOT NULL,
              level TEXT NOT NULL,
              rate TEXT NOT NULL,
              email TEXT NOT NULL,
              verified INTEGER NOT NULL DEFAULT 0,
              experience TEXT NOT NULL,
              bio TEXT NOT NULL,
              availability TEXT NOT NULL,
              joined_at TEXT NOT NULL,
              rating REAL NOT NULL DEFAULT 0,
              review_count INTEGER NOT NULL DEFAULT 0,
              approval_status TEXT NOT NULL DEFAULT 'approved',
              reviewed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS trainer_reviews (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trainer_id INTEGER NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              reviewer_name TEXT NOT NULL,
              rating INTEGER NOT NULL,
              comment TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              listing_id INTEGER REFERENCES listings(id) ON DELETE SET NULL,
              buyer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              seller_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              stripe_checkout_session_id TEXT NOT NULL UNIQUE,
              stripe_payment_intent_id TEXT,
              amount_total_cents INTEGER NOT NULL,
              shipping_amount_cents INTEGER NOT NULL DEFAULT 0,
              shipping_label TEXT NOT NULL DEFAULT '',
              shipping_address_json TEXT NOT NULL DEFAULT '{}',
              shippo_rate_id TEXT NOT NULL DEFAULT '',
              shippo_shipment_id TEXT NOT NULL DEFAULT '',
              shippo_transaction_id TEXT NOT NULL DEFAULT '',
              shippo_label_url TEXT NOT NULL DEFAULT '',
              shipping_carrier TEXT NOT NULL DEFAULT '',
              shipping_service TEXT NOT NULL DEFAULT '',
              tracking_number TEXT NOT NULL DEFAULT '',
              tracking_url TEXT NOT NULL DEFAULT '',
              shipping_status TEXT NOT NULL DEFAULT 'not_ready',
              shipping_error TEXT NOT NULL DEFAULT '',
              buyer_confirmation_status TEXT NOT NULL DEFAULT 'pending',
              buyer_confirmation_sent_at TEXT,
              buyer_confirmation_error TEXT NOT NULL DEFAULT '',
              seller_label_email_status TEXT NOT NULL DEFAULT 'pending',
              seller_label_email_sent_at TEXT,
              seller_label_email_error TEXT NOT NULL DEFAULT '',
              platform_fee_cents INTEGER NOT NULL,
              stripe_payment_status TEXT NOT NULL DEFAULT 'unpaid',
              stripe_session_status TEXT NOT NULL DEFAULT 'open',
              status TEXT NOT NULL DEFAULT 'open',
              created_at TEXT NOT NULL,
              completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS court_reports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              court_id TEXT NOT NULL,
              court_name TEXT NOT NULL,
              court_location TEXT NOT NULL,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              reviewer_name TEXT NOT NULL,
              condition_rating INTEGER NOT NULL,
              busyness_rating INTEGER NOT NULL,
              player_level TEXT NOT NULL,
              comment TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS courts_directory (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              name TEXT NOT NULL,
              location TEXT NOT NULL,
              address TEXT NOT NULL DEFAULT '',
              access_kind TEXT NOT NULL,
              surface_kind TEXT NOT NULL,
              court_count INTEGER NOT NULL,
              access_note TEXT NOT NULL DEFAULT '',
              amenities TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL,
              website TEXT NOT NULL DEFAULT '',
              affiliate_url TEXT NOT NULL DEFAULT '',
              affiliate_label TEXT NOT NULL DEFAULT '',
              approval_status TEXT NOT NULL DEFAULT 'approved',
              reviewed_at TEXT,
              lat REAL,
              lon REAL,
              created_at TEXT NOT NULL
            );
            """
        )
      # fmt: on

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_court_reports_court_id ON court_reports(court_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_courts_directory_created_at ON courts_directory(created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_tokens_lookup ON auth_tokens(purpose, token_hash, expires_at)"
        )

        add_column_if_missing(connection, "users", "stripe_account_id", "TEXT")
        add_column_if_missing(connection, "users", "profile_image_data", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "users", "profile_image_updated_at", "TEXT")
        add_column_if_missing(connection, "users", "profile_pending_name", "TEXT")
        add_column_if_missing(connection, "users", "profile_pending_image_data", "TEXT")
        add_column_if_missing(connection, "users", "profile_pending_image_action", "TEXT NOT NULL DEFAULT 'keep'")
        add_column_if_missing(connection, "users", "profile_review_status", "TEXT NOT NULL DEFAULT 'approved'")
        add_column_if_missing(connection, "users", "profile_review_note", "TEXT")
        add_column_if_missing(connection, "users", "profile_submitted_at", "TEXT")
        add_column_if_missing(connection, "users", "profile_reviewed_at", "TEXT")
        add_column_if_missing(connection, "users", "account_status", "TEXT NOT NULL DEFAULT 'active'")
        add_column_if_missing(connection, "users", "account_status_note", "TEXT")
        add_column_if_missing(connection, "users", "account_status_updated_at", "TEXT")
        add_column_if_missing(connection, "users", "email_verified", "INTEGER NOT NULL DEFAULT 1")
        add_column_if_missing(connection, "users", "email_verified_at", "TEXT")
        add_column_if_missing(connection, "users", "stripe_details_submitted", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_charges_enabled", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_payouts_enabled", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_onboarding_complete", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_requirements_due_count", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_account_status_updated_at", "TEXT")
        add_column_if_missing(connection, "sessions", "csrf_token", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "listings", "color", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "listings", "thickness_mm", "REAL")
        add_column_if_missing(connection, "listings", "shipping_mode", "TEXT NOT NULL DEFAULT 'calculated'")
        add_column_if_missing(connection, "listings", "shipping_flat_usd", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "listings", "shipping_origin_zip", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "listings", "shipping_origin_street1", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "listings", "shipping_weight_oz", "REAL")
        add_column_if_missing(connection, "listings", "shipping_length_in", "REAL")
        add_column_if_missing(connection, "listings", "shipping_width_in", "REAL")
        add_column_if_missing(connection, "listings", "shipping_height_in", "REAL")
        add_column_if_missing(connection, "listings", "shipping_note", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "listings", "image_data_json", "TEXT NOT NULL DEFAULT '[]'")
        add_column_if_missing(connection, "listings", "approval_status", "TEXT NOT NULL DEFAULT 'approved'")
        add_column_if_missing(connection, "listings", "sale_status", "TEXT NOT NULL DEFAULT 'available'")
        add_column_if_missing(connection, "listings", "reviewed_at", "TEXT")
        add_column_if_missing(connection, "trainers", "approval_status", "TEXT NOT NULL DEFAULT 'approved'")
        add_column_if_missing(connection, "trainers", "reviewed_at", "TEXT")
        add_column_if_missing(connection, "orders", "shipping_amount_cents", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "orders", "shipping_label", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "shipping_address_json", "TEXT NOT NULL DEFAULT '{}'")
        add_column_if_missing(connection, "orders", "shippo_rate_id", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "shippo_shipment_id", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "shippo_transaction_id", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "shippo_label_url", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "shipping_carrier", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "shipping_service", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "tracking_number", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "tracking_url", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "shipping_status", "TEXT NOT NULL DEFAULT 'not_ready'")
        add_column_if_missing(connection, "orders", "shipping_error", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "buyer_confirmation_status", "TEXT NOT NULL DEFAULT 'pending'")
        add_column_if_missing(connection, "orders", "buyer_confirmation_sent_at", "TEXT")
        add_column_if_missing(connection, "orders", "buyer_confirmation_error", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "orders", "seller_label_email_status", "TEXT NOT NULL DEFAULT 'pending'")
        add_column_if_missing(connection, "orders", "seller_label_email_sent_at", "TEXT")
        add_column_if_missing(connection, "orders", "seller_label_email_error", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "courts_directory", "address", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "courts_directory", "affiliate_url", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "courts_directory", "affiliate_label", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "courts_directory", "approval_status", "TEXT NOT NULL DEFAULT 'approved'")
        add_column_if_missing(connection, "courts_directory", "reviewed_at", "TEXT")

        # Keep older paid orders consistent with the current sale-state model.
        # This safely repairs listings created before sale_status existed without
        # purchasing labels or sending email during application startup.
        connection.execute(
            """
            UPDATE listings
            SET sale_status = 'pending'
            WHERE sale_status = 'available'
              AND id IN (
                SELECT listing_id
                FROM orders
                WHERE listing_id IS NOT NULL
                  AND (status = 'paid' OR stripe_payment_status = 'paid')
              )
            """
        )

        # Production never publishes anonymous starter content or known checkout tests.
        # Preserve the rows for audit purposes while removing them from the public catalog.
        if APP_ENV == "production":
            connection.execute(
                """
                UPDATE listings
                SET approval_status = 'rejected', reviewed_at = COALESCE(reviewed_at, ?)
                WHERE user_id IS NULL AND approval_status = 'approved'
                """,
                (utc_now(),),
            )
            connection.execute(
                """
                UPDATE trainers
                SET approval_status = 'rejected', reviewed_at = COALESCE(reviewed_at, ?)
                WHERE user_id IS NULL AND approval_status = 'approved'
                """,
                (utc_now(),),
            )
            connection.execute(
                """
                UPDATE courts_directory
                SET approval_status = 'rejected', reviewed_at = COALESCE(reviewed_at, ?)
                WHERE user_id IS NULL AND approval_status = 'approved'
                """,
                (utc_now(),),
            )
            connection.execute(
                """
                UPDATE listings
                SET approval_status = 'rejected', reviewed_at = COALESCE(reviewed_at, ?)
                WHERE approval_status = 'approved'
                  AND (
                    lower(model) LIKE '%checkout test%'
                    OR (lower(brand) = 'pen' AND lower(model) = 'sharpie')
                  )
                """,
                (utc_now(),),
            )

        listing_count = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        trainer_count = connection.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
        review_count = connection.execute("SELECT COUNT(*) FROM trainer_reviews").fetchone()[0]
        court_report_count = connection.execute("SELECT COUNT(*) FROM court_reports").fetchone()[0]

        if ENABLE_STARTER_LISTINGS and not listing_count:
            connection.executemany(
                """
                INSERT INTO listings (
                  brand, model, color, thickness_mm, category, condition, price_usd, location, notes, image_data_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "Selkirk",
                        "LUXX Control Air",
                        "Sky blue",
                        16.0,
                        "control",
                        "Excellent",
                        165,
                        "Miami, FL",
                        "Edge guard is clean, face has light cosmetic wear, and the handle is freshly wrapped.",
                        "[]",
                        "2026-06-01T12:00:00Z",
                    ),
                    (
                        "JOOLA",
                        "Perseus Shape",
                        "Black",
                        16.0,
                        "power",
                        "Very Good",
                        148,
                        "Austin, TX",
                        "Used for a few sessions, still lively off the face, with a small scuff near the throat.",
                        "[]",
                        "2026-06-03T12:00:00Z",
                    ),
                    (
                        "Six Zero",
                        "Double Black Diamond",
                        "Carbon black",
                        16.0,
                        "hybrid",
                        "Excellent",
                        139,
                        "Naples, FL",
                        "Balanced feel with clean edges, no dead spots reported, and strong all-court control.",
                        "[]",
                        "2026-06-05T12:00:00Z",
                    ),
                    (
                        "Paddletek",
                        "Bantam TKO-C",
                        "Red",
                        14.3,
                        "power",
                        "Good",
                        121,
                        "Scottsdale, AZ",
                        "A strong starter upgrade for players who want more pace without buying brand new.",
                        "[]",
                        "2026-06-07T12:00:00Z",
                    ),
                    (
                        "Vatic Pro",
                        "Prism Flash",
                        "Purple",
                        16.0,
                        "control",
                        "Excellent",
                        111,
                        "Charlotte, NC",
                        "Soft touch at the kitchen, steady resets, and the original cover is included.",
                        "[]",
                        "2026-06-09T12:00:00Z",
                    ),
                    (
                        "Bread & Butter",
                        "Filth",
                        "Neon yellow",
                        14.0,
                        "hybrid",
                        "Very Good",
                        133,
                        "Denver, CO",
                        "Crisp feel with clean cosmetics, lightly broken in and ready for tournament play.",
                        "[]",
                        "2026-06-10T12:00:00Z",
                    ),
                ],
            )

        if ENABLE_DEMO_DATA and not trainer_count:
            connection.executemany(
                """
                INSERT INTO trainers (
                  name, location, format, level, rate, email, verified,
                  experience, bio, availability, joined_at, rating, review_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "Maria Alvarez",
                        "Miami, FL",
                        "private",
                        "beginner",
                        "$85/hr",
                        "maria@elevenzeropb.example",
                        1,
                        "PPR-certified · 7 years coaching",
                        "Best for newer players who want cleaner mechanics, calmer resets, and a simple improvement plan.",
                        "Evenings + weekends",
                        "2025-02-01",
                        4.9,
                        32,
                    ),
                    (
                        "Tyler Brooks",
                        "Austin, TX",
                        "private",
                        "advanced",
                        "$110/hr",
                        "tyler@elevenzeropb.example",
                        1,
                        "Former college tennis coach",
                        "Strong fit for aggressive players working on transition pressure, hand speed, and tournament prep.",
                        "Weekday mornings",
                        "2024-11-01",
                        4.8,
                        19,
                    ),
                    (
                        "Nicole Chen",
                        "San Diego, CA",
                        "group",
                        "beginner",
                        "$72/hr",
                        "nicole@elevenzeropb.example",
                        1,
                        "6 years youth + adult coaching",
                        "Great for fundamentals, consistency, and confidence-building group sessions for newer players.",
                        "Afternoons + Saturdays",
                        "2025-06-01",
                        5.0,
                        24,
                    ),
                    (
                        "Andre Wallace",
                        "Scottsdale, AZ",
                        "clinic",
                        "advanced",
                        "$95/hr",
                        "andre@elevenzeropb.example",
                        1,
                        "Former touring pro sparring coach",
                        "Focused on faster hands, aggressive counters, and helping solid intermediates level up for match play.",
                        "Flexible scheduling",
                        "2024-08-01",
                        4.9,
                        41,
                    ),
                    (
                        "Jamie Patel",
                        "Charlotte, NC",
                        "virtual",
                        "advanced",
                        "$80/hr",
                        "jamie@elevenzeropb.example",
                        0,
                        "Video analyst + on-court coach",
                        "Ideal for players who want remote breakdowns, shot selection feedback, and smarter point construction.",
                        "Remote + selective weekends",
                        "2025-09-01",
                        4.7,
                        14,
                    ),
                    (
                        "Erin Lawson",
                        "Tampa, FL",
                        "group",
                        "intermediate",
                        "$68/hr",
                        "erin@elevenzeropb.example",
                        0,
                        "Community clinic lead",
                        "Good match for players who want approachable coaching, drill reps, and group energy without pressure.",
                        "Tuesdays, Thursdays, Sundays",
                        "2025-04-01",
                        4.8,
                        11,
                    ),
                    (
                        "Marcus Reed",
                        "Denver, CO",
                        "private",
                        "intermediate",
                        "$90/hr",
                        "marcus@elevenzeropb.example",
                        1,
                        "5.0 competitor + drill coach",
                        "Built for players who want faster decision-making, deeper patterns, and more disciplined third-shot choices.",
                        "Mornings + lunch hours",
                        "2025-01-01",
                        4.9,
                        27,
                    ),
                    (
                        "Sofia Ramirez",
                        "Nashville, TN",
                        "clinic",
                        "intermediate",
                        "$78/hr",
                        "sofia@elevenzeropb.example",
                        1,
                        "Clinic host + doubles specialist",
                        "Helps players understand spacing, doubles communication, and how to improve without overcomplicating the game.",
                        "Friday to Sunday",
                        "2024-10-01",
                        4.8,
                        18,
                    ),
                ],
            )

        if ENABLE_DEMO_DATA and not review_count:
            connection.executemany(
                """
                INSERT INTO trainer_reviews (
                  trainer_id, reviewer_name, rating, comment, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        1,
                        "Reese Carter",
                        5,
                        "Super clear fundamentals session. I left with a real plan instead of random advice.",
                        "2026-06-21T12:00:00Z",
                    ),
                    (
                        4,
                        "Noah Bennett",
                        5,
                        "Andre helped me speed up my hands and simplify match decisions fast.",
                        "2026-06-24T12:00:00Z",
                    ),
                    (
                        3,
                        "Lena Ortiz",
                        5,
                        "Nicole is great with newer players and keeps group sessions calm and organized.",
                        "2026-06-27T12:00:00Z",
                    ),
                ],
            )

        if ENABLE_DEMO_DATA and not court_report_count:
            connection.executemany(
                """
                INSERT INTO court_reports (
                  court_id,
                  court_name,
                  court_location,
                  user_id,
                  reviewer_name,
                  condition_rating,
                  busyness_rating,
                  player_level,
                  comment,
                  created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "sample-miami",
                        "Central Park Community Courts",
                        "Miami, FL",
                        None,
                        "Sofia R.",
                        4,
                        3,
                        "mixed",
                        "Courts usually play well and the evening open play gets lively without feeling impossible to jump into.",
                        "2026-06-12T18:30:00Z",
                    ),
                    (
                        "sample-miami",
                        "Central Park Community Courts",
                        "Miami, FL",
                        None,
                        "Daniel P.",
                        5,
                        3,
                        "intermediate",
                        "Good surface, bright lights, and a steady mix of social players plus a few stronger regulars after work.",
                        "2026-06-18T20:10:00Z",
                    ),
                    (
                        "sample-austin",
                        "Northside Pickleball Club",
                        "Austin, TX",
                        None,
                        "Maya T.",
                        5,
                        2,
                        "advanced",
                        "Really clean indoor courts with organized sessions. Most players I saw were solid intermediate to advanced.",
                        "2026-06-15T17:45:00Z",
                    ),
                    (
                        "sample-austin",
                        "Northside Pickleball Club",
                        "Austin, TX",
                        None,
                        "Chris L.",
                        5,
                        2,
                        "advanced",
                        "Condition is excellent and it feels less crowded than public spots because reservation flow spreads people out.",
                        "2026-06-20T19:00:00Z",
                    ),
                    (
                        "sample-charlotte",
                        "West Rec Center Courts",
                        "Charlotte, NC",
                        None,
                        "Amber J.",
                        4,
                        2,
                        "beginner",
                        "Good weather-safe option. Usually approachable for newer players and not too intense during weekday sessions.",
                        "2026-06-16T16:20:00Z",
                    ),
                    (
                        "sample-scottsdale",
                        "Desert Paddle Social Club",
                        "Scottsdale, AZ",
                        None,
                        "Eric M.",
                        4,
                        3,
                        "intermediate",
                        "Nice outdoor setup with organized play blocks. It can feel busy during popular social sessions.",
                        "2026-06-19T21:05:00Z",
                    ),
                    (
                        "sample-nashville",
                        "Lakeview City Courts",
                        "Nashville, TN",
                        None,
                        "Kelsey B.",
                        3,
                        4,
                        "mixed",
                        "Fun public courts, but peak times get packed. Surface is playable, just a little worn in spots.",
                        "2026-06-21T19:40:00Z",
                    ),
                    (
                        "sample-denver",
                        "Elevate Indoor Pickleball",
                        "Denver, CO",
                        None,
                        "Jordan V.",
                        5,
                        2,
                        "advanced",
                        "Very polished facility and strong player pool. Great if you want cleaner games and better competition.",
                        "2026-06-14T18:55:00Z",
                    ),
                    (
                        "sample-sandiego",
                        "Harbor Park Pickleball Lines",
                        "San Diego, CA",
                        None,
                        "Nina C.",
                        3,
                        2,
                        "beginner",
                        "Simple public setup and easy to join in the mornings. Not fancy, but friendly and useful.",
                        "2026-06-17T15:35:00Z",
                    ),
                    (
                        "sample-tampa",
                        "Sunset Racquet & Paddle",
                        "Tampa, FL",
                        None,
                        "Marcus D.",
                        4,
                        3,
                        "intermediate",
                        "Usually busy when events are running, but the courts are in good shape and the player level is strong overall.",
                        "2026-06-22T20:25:00Z",
                    ),
                ],
            )

        connection.commit()


def row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


MAX_LISTING_IMAGE_DATA_URL_LENGTH = 2_000_000
PROFILE_IMAGE_MAX_BYTES = 750_000
PROFILE_IMAGE_MAX_DATA_URL_LENGTH = 1_100_000


def decode_profile_image_data(value: str) -> tuple[str, bytes]:
    image = str(value or "").strip()
    if not image:
        raise ValueError("Choose a profile photo first.")
    if len(image) > PROFILE_IMAGE_MAX_DATA_URL_LENGTH:
        raise ValueError("Profile photo must be smaller than 750 KB.")

    match = re.fullmatch(
        r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)",
        image,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Choose a JPG, PNG, or WebP profile photo.")

    mime_type = match.group(1).lower()
    try:
        payload = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("That profile photo could not be read.") from error

    if not payload or len(payload) > PROFILE_IMAGE_MAX_BYTES:
        raise ValueError("Profile photo must be smaller than 750 KB.")

    has_valid_signature = (
        (mime_type == "image/jpeg" and payload.startswith(b"\xff\xd8\xff"))
        or (mime_type == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n"))
        or (
            mime_type == "image/webp"
            and len(payload) >= 12
            and payload[:4] == b"RIFF"
            and payload[8:12] == b"WEBP"
        )
    )
    if not has_valid_signature:
        raise ValueError("That file is not a valid JPG, PNG, or WebP image.")

    return mime_type, payload


def normalize_profile_image_data(value: str) -> str:
    mime_type, payload = decode_profile_image_data(value)
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def normalize_listing_image_payload(raw_images) -> list[str]:
    if isinstance(raw_images, str):
        raw_images = raw_images.strip()
        if raw_images.startswith("data:image/"):
            candidates = [raw_images]
        else:
            try:
                decoded = json.loads(raw_images or "[]")
                candidates = decoded if isinstance(decoded, list) else []
            except json.JSONDecodeError:
                candidates = []
    elif isinstance(raw_images, list):
        candidates = raw_images
    else:
        candidates = []

    images: list[str] = []

    for candidate in candidates:
        if not isinstance(candidate, str):
            continue

        image = candidate.strip()
        if not image.startswith("data:image/"):
            continue
        if len(image) > MAX_LISTING_IMAGE_DATA_URL_LENGTH:
            continue
        if image in images:
            continue

        images.append(image)
        if len(images) >= 4:
            break

    return images


def public_listing_images(row: sqlite3.Row | dict) -> list[str]:
    """Return lightweight image URLs instead of embedding megabytes in JSON responses."""
    images = normalize_listing_image_payload(row_value(row, "image_data_json", "[]"))
    if images:
        listing_id = int(row_value(row, "id", 0) or 0)
        return [f"/api/listings/{listing_id}/images/{index}" for index in range(len(images))]
    if APP_ENV != "production":
        return demo_listing_images_for_row(row)
    return []


def parse_thickness_mm(raw_value) -> float | None:
    raw = str(raw_value or "").strip()
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == ".")

    if not cleaned or cleaned.count(".") > 1:
        return None

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if value < 8 or value > 25:
        return None

    return round(value, 1)


DEMO_LISTING_IMAGE_MAP = {
    ("selkirk", "luxx control air"): [
        "https://images.pexels.com/photos/17299531/pexels-photo-17299531/free-photo-of-pickleball-paddle-on-blue-background.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/30864598/pexels-photo-30864598/free-photo-of-pickleball-player-on-outdoor-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/29820785/pexels-photo-29820785/free-photo-of-shadow-play-on-a-sunny-pickleball-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
    ],
    ("joola", "perseus shape"): [
        "https://images.pexels.com/photos/30864598/pexels-photo-30864598/free-photo-of-pickleball-player-on-outdoor-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/17333854/pexels-photo-17333854/free-photo-of-young-man-and-woman-standing-on-a-pickleball-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/37143606/pexels-photo-37143606/free-photo-of-aerial-view-of-outdoor-pickleball-courts-in-philadelphia.jpeg?auto=compress&cs=tinysrgb&w=1600",
    ],
    ("six zero", "double black diamond"): [
        "https://images.pexels.com/photos/17333854/pexels-photo-17333854/free-photo-of-young-man-and-woman-standing-on-a-pickleball-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/17299531/pexels-photo-17299531/free-photo-of-pickleball-paddle-on-blue-background.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/32975182/pexels-photo-32975182/free-photo-of-woman-playing-pickleball-in-indoor-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
    ],
    ("paddletek", "bantam tko-c"): [
        "https://images.pexels.com/photos/32975182/pexels-photo-32975182/free-photo-of-woman-playing-pickleball-in-indoor-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/29820785/pexels-photo-29820785/free-photo-of-shadow-play-on-a-sunny-pickleball-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/30864598/pexels-photo-30864598/free-photo-of-pickleball-player-on-outdoor-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
    ],
    ("vatic pro", "prism flash"): [
        "https://images.pexels.com/photos/29820785/pexels-photo-29820785/free-photo-of-shadow-play-on-a-sunny-pickleball-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/37143606/pexels-photo-37143606/free-photo-of-aerial-view-of-outdoor-pickleball-courts-in-philadelphia.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/17299531/pexels-photo-17299531/free-photo-of-pickleball-paddle-on-blue-background.jpeg?auto=compress&cs=tinysrgb&w=1600",
    ],
    ("bread & butter", "filth"): [
        "https://images.pexels.com/photos/37143606/pexels-photo-37143606/free-photo-of-aerial-view-of-outdoor-pickleball-courts-in-philadelphia.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/17299531/pexels-photo-17299531/free-photo-of-pickleball-paddle-on-blue-background.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "https://images.pexels.com/photos/30864598/pexels-photo-30864598/free-photo-of-pickleball-player-on-outdoor-court.jpeg?auto=compress&cs=tinysrgb&w=1600",
    ],
}


def demo_listing_images_for_row(row: sqlite3.Row | dict | None) -> list[str]:
    brand = compact_whitespace(row_value(row, "brand", "")).lower()
    model = compact_whitespace(row_value(row, "model", "")).lower()
    return DEMO_LISTING_IMAGE_MAP.get((brand, model), [])


def listing_checkout_state_from_row(row: sqlite3.Row | dict | None) -> dict:
    row = row or {}
    seller_user_id = row_value(row, "user_id")
    seller_profile = stripe_profile_from_row(row)
    price_usd = int(row_value(row, "price_usd", 0) or 0)
    approval_status = normalize_listing_approval_status(
        row_value(row, "approval_status", "approved"), default="approved"
    )
    sale_status = normalize_listing_sale_status(
        row_value(row, "sale_status", "available"), default="available"
    )

    if sale_status == "pending":
        reason = "A buyer has purchased this paddle. The sale is pending final confirmation."
    elif sale_status == "sold":
        reason = "This paddle has been sold."
    elif approval_status == "pending":
        reason = "This listing is waiting for Eleven Zero PB review before it can go live."
    elif approval_status == "rejected":
        reason = "This listing is paused and needs seller updates before it can go live."
    elif not stripe_is_configured():
        reason = "Platform checkout will turn on after Stripe keys are connected."
    elif not seller_user_id:
        reason = "This sample listing is not attached to a live seller account yet."
    elif not seller_profile["hasAccount"]:
        reason = "Seller still needs to connect payouts before checkout can turn on."
    elif not seller_profile["readyForPayouts"]:
        reason = "Seller is still finishing payout setup."
    else:
        reason = ""

    return {
        "sellerUserId": seller_user_id or None,
        "sellerProfile": seller_profile,
        "priceCents": max(price_usd, 0) * 100,
        "available": bool(
            approval_status == "approved"
            and sale_status == "available"
            and seller_user_id
            and seller_profile["readyForPayouts"]
            and stripe_is_configured()
        ),
        "reason": reason,
    }


def serialize_listing_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    checkout_state = listing_checkout_state_from_row(row)
    color = compact_whitespace(row_value(row, "color", ""))
    thickness_mm = row_value(row, "thickness_mm")
    images = public_listing_images(row)
    shipping_policy = shipping_policy_from_row(row)
    approval_status = normalize_listing_approval_status(
        row_value(row, "approval_status", "approved"), default="approved"
    )
    sale_status = normalize_listing_sale_status(
        row_value(row, "sale_status", "available"), default="available"
    )

    return {
        "id": row["id"],
        "brand": row["brand"],
        "model": row["model"],
        "color": color,
        "thickness_mm": thickness_mm,
        "category": row["category"],
        "condition": row["condition"],
        "price_usd": row["price_usd"],
        "location": row["location"],
        "notes": row["notes"],
        "images": images,
        "primary_image": images[0] if images else "",
        "created_at": row["created_at"],
        "approval_status": approval_status,
        "approval_label": LISTING_APPROVAL_LABELS.get(approval_status, "Pending review"),
        "sale_status": sale_status,
        "sale_label": LISTING_SALE_LABELS.get(sale_status, "Available"),
        "reviewed_at": row_value(row, "reviewed_at"),
        "seller_name": row["seller_name"],
        "seller_joined_at": row_value(row, "seller_joined_at"),
        "shipping": shipping_policy,
        "shipping_policy_label": shipping_policy["label"],
        "seller_user_id": checkout_state["sellerUserId"],
        "seller_has_connected_account": checkout_state["sellerProfile"]["hasAccount"],
        "seller_ready_for_payouts": checkout_state["sellerProfile"]["readyForPayouts"],
        "checkout_available": checkout_state["available"],
        "checkout_reason": checkout_state["reason"],
    }


def site_config_payload() -> dict:
    return {
        "environment": APP_ENV,
        "siteUrl": SITE_URL,
        "supportEmail": SUPPORT_EMAIL,
        "gaMeasurementId": GA_MEASUREMENT_ID,
        "googleMapsEnabled": bool(GOOGLE_MAPS_API_KEY),
        "googleMapsApiKey": GOOGLE_MAPS_API_KEY,
        "googleMapsMapId": GOOGLE_MAPS_MAP_ID,
        "googlePlacesSearchEnabled": google_places_is_configured(),
        "shippoConfigured": bool(SHIPPO_API_KEY),
        "managedShippingEnabled": bool(SHIPPO_API_KEY),
        "stripeConfigured": stripe_is_configured(),
        "stripeWebhookConfigured": bool(STRIPE_WEBHOOK_SECRET),
        "stripeMode": stripe_mode(),
        "stripePublishableKeyPresent": bool(STRIPE_PUBLISHABLE_KEY),
        "platformFeePercent": STRIPE_PLATFORM_FEE_PERCENT,
        "checkoutEnabled": bool(stripe_is_configured() and STRIPE_PUBLISHABLE_KEY),
    }


class ElevenZeroHandler(SimpleHTTPRequestHandler):
    server_version = "ElevenZeroPB"
    sys_version = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return

        if parsed.path in {"", "/"}:
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_post(parsed)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")

    def end_headers(self):
        path = urlparse(self.path).path
        self.send_header("Cache-Control", cache_control_for_path(path))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        self.send_header("Content-Security-Policy", build_content_security_policy())
        if SESSION_COOKIE_SECURE:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        super().end_headers()

    def json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"

        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
            raise ValueError("Invalid JSON")

        return body

    def send_json(self, payload: dict | list, status: int = HTTPStatus.OK, cookie: str | None = None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, content_type: str, status: int = HTTPStatus.OK):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def parse_cookies(self) -> SimpleCookie:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        return cookie

    def current_user(self) -> dict | None:
        cookies = self.parse_cookies()
        morsel = cookies.get(SESSION_COOKIE)
        if not morsel:
            return None

        token = morsel.value
        with closing(connect_db()) as connection:
            row = connection.execute(
                """
                SELECT
                  users.id,
                  users.name,
                  users.email,
                  users.email_verified,
                  users.profile_image_data,
                  users.profile_image_updated_at,
                  users.profile_pending_name,
                  users.profile_pending_image_data,
                  users.profile_pending_image_action,
                  users.profile_review_status,
                  users.profile_review_note,
                  users.profile_submitted_at,
                  users.profile_reviewed_at,
                  users.account_status,
                  users.account_status_note,
                  users.account_status_updated_at,
                  users.created_at,
                  users.stripe_account_id,
                  users.stripe_details_submitted,
                  users.stripe_charges_enabled,
                  users.stripe_payouts_enabled,
                  users.stripe_onboarding_complete,
                  users.stripe_requirements_due_count,
                  users.stripe_account_status_updated_at,
                  sessions.token,
                  sessions.csrf_token,
                  sessions.created_at AS session_created_at
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()

        if not row:
            return None

        if str(row_value(row, "account_status", "active") or "active") == "suspended":
            with closing(connect_db()) as connection:
                connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
                connection.commit()
            return None

        created_at = parse_activity_datetime(row["session_created_at"])
        if not created_at or (datetime.now(timezone.utc) - created_at).total_seconds() > SESSION_MAX_AGE_SECONDS:
            with closing(connect_db()) as connection:
                connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
                connection.commit()
            return None

        return serialize_user(row)

    def require_user(self) -> dict | None:
        user = self.current_user()
        if not user:
            self.send_json(
                {"error": "Please sign in first."},
                status=HTTPStatus.UNAUTHORIZED,
            )
        return user

    def require_admin(self, user: dict | None) -> bool:
        if not user:
            return False

        if user.get("isAdmin"):
            return True

        self.send_json(
            {
                "error": "This area is only for the Eleven Zero PB owner account. Sign in with your moderator email first."
            },
            status=HTTPStatus.FORBIDDEN,
        )
        return False

    def require_verified_user(self, user: dict | None) -> bool:
        if not user:
            return False

        if user.get("emailVerified"):
            return True

        self.send_json(
            {
                "error": "Verify your email from the link we sent before posting marketplace content.",
                "code": "email_verification_required",
                "actionUrl": "./account.html",
            },
            status=HTTPStatus.FORBIDDEN,
        )
        return False

    def session_cookie(self, token: str) -> str:
        secure_flag = "; Secure" if SESSION_COOKIE_SECURE else ""
        return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; Max-Age=2592000; SameSite=Lax{secure_flag}"

    def clear_session_cookie(self) -> str:
        secure_flag = "; Secure" if SESSION_COOKIE_SECURE else ""
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; Max-Age=0; SameSite=Lax{secure_flag}"

    def current_csrf_token(self, create: bool = True) -> str:
        morsel = self.parse_cookies().get(SESSION_COOKIE)
        if not morsel:
            return ""
        with closing(connect_db()) as connection:
            row = connection.execute(
                "SELECT csrf_token FROM sessions WHERE token = ?", (morsel.value,)
            ).fetchone()
            if not row:
                return ""
            csrf_token = str(row["csrf_token"] or "")
            if not csrf_token and create:
                csrf_token = secrets.token_urlsafe(24)
                connection.execute(
                    "UPDATE sessions SET csrf_token = ? WHERE token = ?",
                    (csrf_token, morsel.value),
                )
                connection.commit()
        return csrf_token

    def validate_csrf(self) -> bool:
        expected = self.current_csrf_token(create=False)
        received = self.headers.get("X-CSRF-Token", "").strip()
        if expected and received and hmac.compare_digest(expected, received):
            return True
        self.send_json(
            {"error": "Your secure session expired. Refresh the page and try again."},
            status=HTTPStatus.FORBIDDEN,
        )
        return False

    def validate_request_origin(self) -> bool:
        origin = self.headers.get("Origin", "").strip()
        if not origin:
            return True
        expected = urlparse(self.current_origin())
        received = urlparse(origin)
        if expected.scheme == received.scheme and expected.netloc == received.netloc:
            return True
        self.send_json({"error": "This request came from an untrusted page."}, status=HTTPStatus.FORBIDDEN)
        return False

    def create_session(self, user_id: int) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        with closing(connect_db()) as connection:
            expiration = (datetime.now(timezone.utc) - timedelta(seconds=SESSION_MAX_AGE_SECONDS)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            connection.execute("DELETE FROM sessions WHERE created_at < ?", (expiration,))
            connection.execute(
                "INSERT INTO sessions (token, user_id, csrf_token, created_at) VALUES (?, ?, ?, ?)",
                (token, user_id, csrf_token, utc_now()),
            )
            connection.commit()
        return token, csrf_token

    def destroy_session(self):
        cookies = self.parse_cookies()
        morsel = cookies.get(SESSION_COOKIE)
        if not morsel:
            return

        with closing(connect_db()) as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (morsel.value,))
            connection.commit()

    def current_origin(self) -> str:
        if SITE_URL:
            return SITE_URL.rstrip("/")

        forwarded_proto = self.headers.get("X-Forwarded-Proto", "").strip()
        proto = forwarded_proto or ("https" if SESSION_COOKIE_SECURE else "http")
        host = (
            self.headers.get("X-Forwarded-Host")
            or self.headers.get("Host")
            or f"127.0.0.1:{PORT}"
        )
        return f"{proto}://{host}"

    def stripe_return_url(self) -> str:
        return f"{self.current_origin()}/account.html#seller-payouts"

    def stripe_refresh_url(self) -> str:
        return f"{self.current_origin()}/account.html#seller-payouts"

    def checkout_success_url(self) -> str:
        return f"{self.current_origin()}/shop.html?checkout=success&session_id={{CHECKOUT_SESSION_ID}}#listings"

    def checkout_cancel_url(self) -> str:
        return f"{self.current_origin()}/shop.html?checkout=cancel#listings"

    def handle_api_get(self, parsed):
        if parsed.path == "/api/health":
            self.send_json({"ok": True, "time": utc_now(), "environment": APP_ENV})
            return

        if parsed.path == "/api/site-config":
            self.send_json(site_config_payload())
            return

        if parsed.path == "/api/paddle-catalog":
            self.send_json(paddle_catalog_payload())
            return

        if parsed.path == "/api/auth/session":
            user = self.current_user()
            self.send_json(
                {
                    "authenticated": bool(user),
                    "user": user,
                    "csrfToken": self.current_csrf_token() if user else "",
                }
            )
            return

        if parsed.path == "/api/account/profile-image":
            user = self.require_user()
            if not user:
                return
            self.handle_profile_image(user)
            return

        if parsed.path == "/api/account/profile-pending-image":
            user = self.require_user()
            if not user:
                return
            self.handle_profile_pending_image(user)
            return

        pending_profile_image_match = re.fullmatch(
            r"/api/admin/profiles/(\d+)/pending-image", parsed.path
        )
        if pending_profile_image_match:
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_profile_pending_image(int(pending_profile_image_match.group(1)))
            return

        image_match = re.fullmatch(r"/api/listings/(\d+)/images/(\d+)", parsed.path)
        if image_match:
            self.handle_listing_image(
                int(image_match.group(1)), int(image_match.group(2)), self.current_user()
            )
            return

        if parsed.path.startswith("/api/listings/"):
            listing_id = parsed.path.rsplit("/", 1)[-1].strip()
            if not listing_id.isdigit():
                self.send_json({"error": "That listing could not be found."}, status=HTTPStatus.NOT_FOUND)
                return

            item = self.fetch_listing_by_id(int(listing_id), self.current_user())
            if not item:
                self.send_json({"error": "That listing could not be found."}, status=HTTPStatus.NOT_FOUND)
                return

            self.send_json({"item": item})
            return

        if parsed.path == "/api/listings":
            self.send_json({"items": self.fetch_listings()})
            return

        if parsed.path == "/api/trainers":
            self.send_json({"items": self.fetch_trainers()})
            return

        if parsed.path == "/api/courts-directory":
            self.send_json({"items": self.fetch_directory_courts()})
            return

        if parsed.path == "/api/google-courts-search":
            query = parse_qs(parsed.query or "")
            search_query = str(query.get("query", [""])[0]).strip()
            page_size_raw = str(query.get("pageSize", ["20"])[0]).strip()
            try:
                page_size = int(page_size_raw or "20")
            except ValueError:
                page_size = 20

            try:
                items = google_places_search_courts(search_query, page_size=page_size)
            except RuntimeError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.NOT_IMPLEMENTED)
                return
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return

            self.send_json({"items": items, "provider": "google"})
            return

        if parsed.path == "/api/trainer-reviews":
            query = parse_qs(parsed.query or "")
            trainer_id = query.get("trainerId", [None])[0]
            self.send_json({"items": self.fetch_reviews(trainer_id)})
            return

        if parsed.path == "/api/court-reports":
            query = parse_qs(parsed.query or "")
            court_id = str(query.get("courtId", [""])[0]).strip() or None
            court_ids_param = str(query.get("courtIds", [""])[0]).strip()
            court_ids = [item.strip() for item in court_ids_param.split(",") if item.strip()]
            self.send_json(self.fetch_court_reports(court_id, court_ids))
            return

        if parsed.path == "/api/stripe/connect/status":
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(self.fetch_seller_profile(user["id"]))
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.NOT_FOUND)
            return

        if parsed.path == "/api/dashboard":
            user = self.require_user()
            if not user:
                return
            self.send_json(self.build_dashboard(user["id"]))
            return

        if parsed.path == "/api/admin/dashboard":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.send_json(self.build_admin_dashboard())
            return

        if parsed.path == "/api/checkout/session-status":
            user = self.require_user()
            if not user:
                return
            query = parse_qs(parsed.query or "")
            session_id = str(query.get("sessionId", [""])[0]).strip()
            self.handle_checkout_session_status(user, session_id)
            return

        self.send_json({"error": "Unknown API route."}, status=HTTPStatus.NOT_FOUND)

    def handle_api_post(self, parsed):
        if parsed.path == "/api/stripe/webhook":
            self.handle_stripe_webhook()
            return

        if not self.validate_request_origin():
            return

        public_posts = {
            "/api/auth/signup",
            "/api/auth/signin",
            "/api/auth/password-reset/request",
            "/api/auth/password-reset/confirm",
            "/api/auth/verify-email",
        }
        if parsed.path not in public_posts and self.current_user() and not self.validate_csrf():
            return

        try:
            body = self.json_body()
        except ValueError:
            return

        if parsed.path == "/api/auth/signup":
            self.handle_signup(body)
            return

        if parsed.path == "/api/auth/signin":
            self.handle_signin(body)
            return

        if parsed.path == "/api/auth/password-reset/request":
            self.handle_password_reset_request(body)
            return

        if parsed.path == "/api/auth/password-reset/confirm":
            self.handle_password_reset_confirm(body)
            return

        if parsed.path == "/api/auth/verify-email":
            self.handle_verify_email(body)
            return

        if parsed.path == "/api/auth/resend-verification":
            user = self.require_user()
            if not user:
                return
            self.handle_resend_verification(user)
            return

        if parsed.path == "/api/auth/signout":
            self.destroy_session()
            self.send_json({"ok": True}, cookie=self.clear_session_cookie())
            return

        if parsed.path == "/api/account/profile":
            user = self.require_user()
            if not user:
                return
            self.handle_update_profile(user, body)
            return

        if parsed.path == "/api/listings":
            user = self.require_user()
            if not self.require_verified_user(user):
                return
            self.handle_create_listing(user, body)
            return

        if parsed.path == "/api/trainers":
            user = self.require_user()
            if not self.require_verified_user(user):
                return
            self.handle_create_trainer(user, body)
            return

        if parsed.path == "/api/courts-directory":
            user = self.require_user()
            if not self.require_verified_user(user):
                return
            self.handle_create_directory_court(user, body)
            return

        if parsed.path == "/api/stripe/connect/onboard":
            user = self.require_user()
            if not user:
                return
            self.handle_stripe_onboarding(user)
            return

        if parsed.path == "/api/admin/listings/update":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_listing_update(body)
            return

        if parsed.path == "/api/admin/profiles/review":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_profile_review(user, body)
            return

        if parsed.path == "/api/admin/listings/review":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_listing_review(body)
            return

        if parsed.path == "/api/admin/listings/sale-status":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_listing_sale_status(body)
            return

        if parsed.path == "/api/admin/orders/send-confirmation":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_send_order_confirmation(body)
            return

        if parsed.path == "/api/admin/listings/delete":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_listing_delete(body)
            return

        if parsed.path == "/api/admin/courts/update":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_court_update(body)
            return

        if parsed.path == "/api/admin/courts/review":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_court_review(body)
            return

        if parsed.path == "/api/admin/courts/delete":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_court_delete(body)
            return

        if parsed.path == "/api/admin/trainers/update":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_trainer_update(body)
            return

        if parsed.path == "/api/admin/trainers/review":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_trainer_review(body)
            return

        if parsed.path == "/api/admin/trainers/delete":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_trainer_delete(body)
            return

        if parsed.path == "/api/admin/trainer-reviews/delete":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_trainer_review_delete(body)
            return

        if parsed.path == "/api/admin/court-reports/delete":
            user = self.require_user()
            if not self.require_admin(user):
                return
            self.handle_admin_court_report_delete(body)
            return

        if parsed.path == "/api/stripe/connect/status/refresh":
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(self.fetch_seller_profile(user["id"], force_refresh=True))
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/shipping/quote":
            self.handle_shipping_quote(body)
            return

        if parsed.path == "/api/orders/shipping/retry":
            user = self.require_user()
            if not user:
                return
            self.handle_retry_shipping_label(user, body)
            return

        if parsed.path == "/api/checkout/create-session":
            user = self.require_user()
            if not user:
                return
            self.handle_create_checkout_session(user, body)
            return

        if parsed.path == "/api/trainer-reviews":
            user = self.require_user()
            if not self.require_verified_user(user):
                return
            self.handle_create_review(user, body)
            return

        if parsed.path == "/api/court-reports":
            user = self.require_user()
            if not self.require_verified_user(user):
                return
            self.handle_create_court_report(user, body)
            return

        self.send_json({"error": "Unknown API route."}, status=HTTPStatus.NOT_FOUND)

    def handle_stripe_webhook(self):
        if not STRIPE_WEBHOOK_SECRET:
            self.send_json(
                {"error": "Stripe webhooks are not configured yet."},
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""
        signature_header = self.headers.get("Stripe-Signature", "")
        signature_parts: dict[str, list[str]] = {}
        for part in signature_header.split(","):
            key, separator, value = part.partition("=")
            if separator:
                signature_parts.setdefault(key.strip(), []).append(value.strip())

        timestamp_raw = (signature_parts.get("t") or [""])[0]
        signatures = signature_parts.get("v1") or []
        try:
            timestamp = int(timestamp_raw)
        except ValueError:
            timestamp = 0

        signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
        expected_signature = hmac.new(
            STRIPE_WEBHOOK_SECRET.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        signature_valid = any(
            secrets.compare_digest(expected_signature, signature) for signature in signatures
        )
        timestamp_valid = timestamp > 0 and abs(int(time.time()) - timestamp) <= 300
        if not signature_valid or not timestamp_valid:
            self.send_json(
                {"error": "Stripe webhook signature could not be verified."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            event = json.loads(raw_body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "Invalid Stripe webhook body."}, status=HTTPStatus.BAD_REQUEST)
            return

        event_type = str(event.get("type") or "")
        session = (event.get("data") or {}).get("object") or {}
        session_id = str(session.get("id") or "")
        if not session_id.startswith("cs_"):
            self.send_json({"received": True})
            return

        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            payment_status = str(session.get("payment_status") or "paid")
            order_status = "paid" if payment_status == "paid" else "processing"
            completed_at = utc_now() if order_status == "paid" else None
            with closing(connect_db()) as connection:
                connection.execute(
                    """
                    UPDATE orders
                    SET
                      stripe_payment_intent_id = ?,
                      stripe_payment_status = ?,
                      stripe_session_status = ?,
                      status = ?,
                      completed_at = CASE
                        WHEN ? IS NOT NULL THEN COALESCE(completed_at, ?)
                        ELSE completed_at
                      END
                    WHERE stripe_checkout_session_id = ?
                    """,
                    (
                        str(session.get("payment_intent") or ""),
                        payment_status,
                        str(session.get("status") or "complete"),
                        order_status,
                        completed_at,
                        completed_at,
                        session_id,
                    ),
                )
                connection.commit()
            if order_status == "paid":
                finalize_paid_order(session_id)
        elif event_type in {"checkout.session.expired", "checkout.session.async_payment_failed"}:
            with closing(connect_db()) as connection:
                connection.execute(
                    """
                    UPDATE orders
                    SET stripe_payment_status = ?, stripe_session_status = ?, status = ?
                    WHERE stripe_checkout_session_id = ?
                    """,
                    (
                        str(session.get("payment_status") or "unpaid"),
                        str(session.get("status") or "expired"),
                        "expired" if event_type == "checkout.session.expired" else "payment_failed",
                        session_id,
                    ),
                )
                connection.commit()

        self.send_json({"received": True})

    def fetch_listings(self) -> list[dict]:
        with closing(connect_db()) as connection:
            rows = connection.execute(
                """
                SELECT
                  listings.id,
                  listings.user_id,
                  listings.brand,
                  listings.model,
                  listings.color,
                  listings.thickness_mm,
                  listings.category,
                  listings.condition,
                  listings.price_usd,
                  listings.location,
                  listings.notes,
                  listings.shipping_mode,
                  listings.shipping_flat_usd,
                  listings.shipping_origin_zip,
                  listings.shipping_origin_street1,
                  listings.shipping_weight_oz,
                  listings.shipping_length_in,
                  listings.shipping_width_in,
                  listings.shipping_height_in,
                  listings.shipping_note,
                  listings.image_data_json,
                  listings.approval_status,
                  listings.sale_status,
                  listings.reviewed_at,
                  listings.created_at,
                  users.name AS seller_name,
                  users.created_at AS seller_joined_at,
                  users.stripe_account_id,
                  users.stripe_details_submitted,
                  users.stripe_charges_enabled,
                  users.stripe_payouts_enabled,
                  users.stripe_onboarding_complete,
                  users.stripe_requirements_due_count,
                  users.stripe_account_status_updated_at
                FROM listings
                LEFT JOIN users ON users.id = listings.user_id
                WHERE listings.approval_status = 'approved'
                  AND listings.user_id IS NOT NULL
                ORDER BY
                  CASE listings.sale_status WHEN 'available' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
                  listings.created_at DESC
                """
            ).fetchall()

        return [serialize_listing_row(row) for row in rows]

    def handle_listing_image(self, listing_id: int, image_index: int, viewer: dict | None):
        with closing(connect_db()) as connection:
            row = connection.execute(
                """
                SELECT id, user_id, approval_status, image_data_json
                FROM listings
                WHERE id = ?
                """,
                (listing_id,),
            ).fetchone()

        if not row:
            self.send_json({"error": "That image could not be found."}, status=HTTPStatus.NOT_FOUND)
            return

        viewer_id = int(viewer.get("id") or 0) if viewer else 0
        viewer_is_admin = bool(viewer.get("isAdmin")) if viewer else False
        owner_id = int(row["user_id"] or 0)
        is_public = row["approval_status"] == "approved" and owner_id > 0
        if not is_public and not viewer_is_admin and viewer_id != owner_id:
            self.send_json({"error": "That image could not be found."}, status=HTTPStatus.NOT_FOUND)
            return

        images = normalize_listing_image_payload(row["image_data_json"])
        if image_index < 0 or image_index >= len(images):
            self.send_json({"error": "That image could not be found."}, status=HTTPStatus.NOT_FOUND)
            return

        data_url = images[image_index]
        match = re.fullmatch(r"data:(image/[a-zA-Z0-9.+-]+);base64,(.+)", data_url, re.DOTALL)
        if not match:
            self.send_json({"error": "That image could not be read."}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError):
            self.send_json({"error": "That image could not be read."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_bytes(payload, match.group(1))

    def handle_profile_image(self, user: dict):
        self.handle_stored_profile_image(int(user["id"]), "profile_image_data")

    def handle_profile_pending_image(self, user: dict):
        self.handle_stored_profile_image(int(user["id"]), "profile_pending_image_data")

    def handle_admin_profile_pending_image(self, user_id: int):
        self.handle_stored_profile_image(user_id, "profile_pending_image_data")

    def handle_stored_profile_image(self, user_id: int, column: str):
        if column not in {"profile_image_data", "profile_pending_image_data"}:
            self.send_json({"error": "Profile photo not found."}, status=HTTPStatus.NOT_FOUND)
            return

        with closing(connect_db()) as connection:
            row = connection.execute(
                f"SELECT {column} AS image_data FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

        if not row or not str(row["image_data"] or "").strip():
            self.send_json({"error": "Profile photo not found."}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            mime_type, payload = decode_profile_image_data(row["image_data"])
        except ValueError:
            self.send_json({"error": "Profile photo not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_bytes(payload, mime_type)

    def fetch_listing_by_id(self, listing_id: int, viewer: dict | None = None) -> dict | None:
        with closing(connect_db()) as connection:
            row = connection.execute(
                """
                SELECT
                  listings.id,
                  listings.user_id,
                  listings.brand,
                  listings.model,
                  listings.color,
                  listings.thickness_mm,
                  listings.category,
                  listings.condition,
                  listings.price_usd,
                  listings.location,
                  listings.notes,
                  listings.shipping_mode,
                  listings.shipping_flat_usd,
                  listings.shipping_origin_zip,
                  listings.shipping_origin_street1,
                  listings.shipping_weight_oz,
                  listings.shipping_length_in,
                  listings.shipping_width_in,
                  listings.shipping_height_in,
                  listings.shipping_note,
                  listings.image_data_json,
                  listings.approval_status,
                  listings.sale_status,
                  listings.reviewed_at,
                  listings.created_at,
                  users.name AS seller_name,
                  users.created_at AS seller_joined_at,
                  users.stripe_account_id,
                  users.stripe_details_submitted,
                  users.stripe_charges_enabled,
                  users.stripe_payouts_enabled,
                  users.stripe_onboarding_complete,
                  users.stripe_requirements_due_count,
                  users.stripe_account_status_updated_at
                FROM listings
                LEFT JOIN users ON users.id = listings.user_id
                WHERE listings.id = ?
                """,
                (listing_id,),
            ).fetchone()

        if not row:
            return None

        approval_status = normalize_listing_approval_status(
            row_value(row, "approval_status", "approved"), default="approved"
        )
        viewer_id = int(viewer.get("id") or 0) if viewer else 0
        viewer_is_admin = bool(viewer.get("isAdmin")) if viewer else False
        listing_owner_id = int(row["user_id"] or 0)

        if not listing_owner_id and not viewer_is_admin:
            return None

        if approval_status != "approved" and not viewer_is_admin and viewer_id != listing_owner_id:
            return None

        return serialize_listing_row(row)

    def fetch_trainers(self) -> list[dict]:
        with closing(connect_db()) as connection:
            rows = connection.execute(
                """
                SELECT
                  id,
                  name,
                  location,
                  format,
                  level,
                  rate,
                  email,
                  verified,
                  experience,
                  bio,
                  availability,
                  joined_at,
                  rating,
                  review_count,
                  approval_status,
                  reviewed_at
                FROM trainers
                WHERE approval_status = 'approved'
                  AND user_id IS NOT NULL
                ORDER BY verified DESC, joined_at DESC, id DESC
                """
            ).fetchall()

        return [row_to_dict(row) for row in rows]

    def fetch_directory_courts(self) -> list[dict]:
        with closing(connect_db()) as connection:
            rows = connection.execute(
                """
                SELECT
                  id,
                  user_id,
                  name,
                  location,
                  address,
                  access_kind,
                  surface_kind,
                  court_count,
                  access_note,
                  amenities,
                  description,
                  website,
                  affiliate_url,
                  affiliate_label,
                  lat,
                  lon,
                  created_at
                FROM courts_directory
                WHERE approval_status = 'approved'
                  AND user_id IS NOT NULL
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()

        return [serialize_directory_court_row(row) for row in rows]

    def fetch_reviews(self, trainer_id: str | None = None) -> list[dict]:
        query = """
            SELECT
              trainer_reviews.id,
              trainer_reviews.trainer_id,
              trainers.name AS trainer_name,
              trainer_reviews.reviewer_name,
              trainer_reviews.rating,
              trainer_reviews.comment,
              trainer_reviews.created_at
            FROM trainer_reviews
            JOIN trainers ON trainers.id = trainer_reviews.trainer_id
            WHERE trainers.approval_status = 'approved'
              AND trainers.user_id IS NOT NULL
        """
        params: tuple = ()

        if trainer_id:
            query += " AND trainer_reviews.trainer_id = ?"
            params = (trainer_id,)

        query += " ORDER BY trainer_reviews.created_at DESC LIMIT 24"

        with closing(connect_db()) as connection:
            rows = connection.execute(query, params).fetchall()

        return [row_to_dict(row) for row in rows]

    def fetch_court_reports(self, court_id: str | None = None, court_ids: list[str] | None = None) -> dict:
        requested_ids = [item for item in (court_ids or []) if item]
        query = """
            SELECT
              id,
              court_id,
              court_name,
              court_location,
              reviewer_name,
              condition_rating,
              busyness_rating,
              player_level,
              comment,
              created_at
            FROM court_reports
        """
        params: list[str] = []

        if court_id:
            query += " WHERE court_id = ?"
            params.append(court_id)
        elif requested_ids:
            placeholders = ",".join("?" for _ in requested_ids)
            query += f" WHERE court_id IN ({placeholders})"
            params.extend(requested_ids)

        query += " ORDER BY created_at DESC LIMIT 120"

        with closing(connect_db()) as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        summaries = summarize_court_reports(rows)
        payload = {"summaryByCourt": summaries}

        if court_id:
            payload["summary"] = summaries.get(court_id)
            payload["items"] = [serialize_court_report_row(row) for row in rows]
        else:
            payload["items"] = []

        return payload

    def fetch_user_account_row(self, user_id: int) -> sqlite3.Row | None:
        with closing(connect_db()) as connection:
            return connection.execute(
                """
                SELECT
                  id,
                  name,
                  email,
                  profile_image_data,
                  profile_image_updated_at,
                  profile_pending_name,
                  profile_pending_image_data,
                  profile_pending_image_action,
                  profile_review_status,
                  profile_review_note,
                  profile_submitted_at,
                  profile_reviewed_at,
                  account_status,
                  account_status_note,
                  account_status_updated_at,
                  created_at,
                  stripe_account_id,
                  stripe_details_submitted,
                  stripe_charges_enabled,
                  stripe_payouts_enabled,
                  stripe_onboarding_complete,
                  stripe_requirements_due_count,
                  stripe_account_status_updated_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

    def fetch_listing_checkout_row(self, listing_id: int) -> sqlite3.Row | None:
        with closing(connect_db()) as connection:
            return connection.execute(
                """
                SELECT
                  listings.id,
                  listings.user_id,
                  listings.brand,
                  listings.model,
                  listings.color,
                  listings.thickness_mm,
                  listings.category,
                  listings.condition,
                  listings.price_usd,
                  listings.location,
                  listings.notes,
                  listings.shipping_mode,
                  listings.shipping_flat_usd,
                  listings.shipping_origin_zip,
                  listings.shipping_origin_street1,
                  listings.shipping_weight_oz,
                  listings.shipping_length_in,
                  listings.shipping_width_in,
                  listings.shipping_height_in,
                  listings.shipping_note,
                  listings.image_data_json,
                  listings.approval_status,
                  listings.sale_status,
                  listings.reviewed_at,
                  listings.created_at,
                  users.name AS seller_name,
                  users.stripe_account_id,
                  users.stripe_details_submitted,
                  users.stripe_charges_enabled,
                  users.stripe_payouts_enabled,
                  users.stripe_onboarding_complete,
                  users.stripe_requirements_due_count,
                  users.stripe_account_status_updated_at
                FROM listings
                LEFT JOIN users ON users.id = listings.user_id
                WHERE listings.id = ?
                """,
                (listing_id,),
            ).fetchone()

    def fetch_order_row(self, session_id: str) -> sqlite3.Row | None:
        with closing(connect_db()) as connection:
            return connection.execute(
                """
                SELECT
                  orders.*,
                  listings.brand,
                  listings.model,
                  users.name AS seller_name
                FROM orders
                LEFT JOIN listings ON listings.id = orders.listing_id
                LEFT JOIN users ON users.id = orders.seller_user_id
                WHERE orders.stripe_checkout_session_id = ?
                """,
                (session_id,),
            ).fetchone()

    def update_user_stripe_status(self, user_id: int, account: dict) -> None:
        currently_due = account.get("requirements", {}).get("currently_due") or []
        details_submitted = bool(account.get("details_submitted"))
        charges_enabled = bool(account.get("charges_enabled"))
        payouts_enabled = bool(account.get("payouts_enabled"))
        onboarding_complete = details_submitted or len(currently_due) == 0

        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE users
                SET
                  stripe_account_id = ?,
                  stripe_details_submitted = ?,
                  stripe_charges_enabled = ?,
                  stripe_payouts_enabled = ?,
                  stripe_onboarding_complete = ?,
                  stripe_requirements_due_count = ?,
                  stripe_account_status_updated_at = ?
                WHERE id = ?
                """,
                (
                    account.get("id", ""),
                    bool_to_int(details_submitted),
                    bool_to_int(charges_enabled),
                    bool_to_int(payouts_enabled),
                    bool_to_int(onboarding_complete),
                    len(currently_due),
                    utc_now(),
                    user_id,
                ),
            )
            connection.commit()

    def sync_stripe_account_status(self, user_id: int, account_id: str) -> dict:
        account = stripe_request("GET", f"/accounts/{account_id}")
        self.update_user_stripe_status(user_id, account)
        return account

    def create_connected_account(self, user: dict) -> dict:
        payload = {
            "type": "express",
            "country": STRIPE_COUNTRY,
            "email": user["email"],
            "metadata[platform]": "Eleven Zero PB",
            "metadata[user_id]": str(user["id"]),
            "metadata[user_name]": user["name"],
            "capabilities[card_payments][requested]": "true",
            "capabilities[transfers][requested]": "true",
        }

        if SITE_URL:
            payload["business_profile[url]"] = SITE_URL

        account = stripe_request("POST", "/accounts", payload)
        self.update_user_stripe_status(user["id"], account)
        return account

    def ensure_connected_account(self, user: dict) -> dict:
        user_row = self.fetch_user_account_row(user["id"])
        account_id = user_row["stripe_account_id"] if user_row else ""

        if account_id:
            return self.sync_stripe_account_status(user["id"], account_id)

        return self.create_connected_account(user)

    def fetch_seller_profile(self, user_id: int, force_refresh: bool = False) -> dict:
        user_row = self.fetch_user_account_row(user_id)
        if not user_row:
            raise ValueError("Account not found.")

        if (
            force_refresh
            and stripe_is_configured()
            and user_row["stripe_account_id"]
        ):
            self.sync_stripe_account_status(user_id, user_row["stripe_account_id"])
            user_row = self.fetch_user_account_row(user_id)

        return {"sellerProfile": stripe_profile_from_row(user_row)}

    def handle_stripe_onboarding(self, user: dict):
        if not stripe_is_configured():
            self.send_json(
                {
                    "error": "Stripe is not connected yet in this app. Add your Stripe keys first, then seller onboarding can go live.",
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        try:
            account = self.ensure_connected_account(user)
            seller_profile = stripe_profile_from_row(
                {
                    "stripe_account_id": account.get("id", ""),
                    "stripe_details_submitted": bool_to_int(bool(account.get("details_submitted"))),
                    "stripe_charges_enabled": bool_to_int(bool(account.get("charges_enabled"))),
                    "stripe_payouts_enabled": bool_to_int(bool(account.get("payouts_enabled"))),
                    "stripe_onboarding_complete": bool_to_int(
                        bool(account.get("details_submitted"))
                        or not (account.get("requirements", {}).get("currently_due") or [])
                    ),
                    "stripe_requirements_due_count": len(
                        account.get("requirements", {}).get("currently_due") or []
                    ),
                    "stripe_account_status_updated_at": utc_now(),
                }
            )

            if seller_profile["readyForPayouts"]:
                self.send_json(
                    {
                        "ok": True,
                        "alreadyReady": True,
                        "message": "Your Stripe seller profile is already ready for payouts.",
                        "sellerProfile": seller_profile,
                    }
                )
                return

            link = stripe_request(
                "POST",
                "/account_links",
                {
                    "account": account["id"],
                    "refresh_url": self.stripe_refresh_url(),
                    "return_url": self.stripe_return_url(),
                    "type": "account_onboarding",
                },
            )

            self.send_json(
                {
                    "ok": True,
                    "sellerProfile": seller_profile,
                    "onboardingUrl": link.get("url", ""),
                }
            )
        except (RuntimeError, ValueError) as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.BAD_GATEWAY)

    def handle_create_checkout_session(self, user: dict, body: dict):
        listing_id_raw = str(body.get("listingId", "")).strip()

        if not listing_id_raw.isdigit():
            self.send_json(
                {"error": "Choose a valid listing before starting checkout."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        listing_row = self.fetch_listing_checkout_row(int(listing_id_raw))
        if not listing_row:
            self.send_json({"error": "That listing could not be found."}, status=HTTPStatus.NOT_FOUND)
            return

        listing = serialize_listing_row(listing_row)
        checkout_state = listing_checkout_state_from_row(listing_row)
        seller_user_id = checkout_state["sellerUserId"]
        seller_profile = checkout_state["sellerProfile"]
        total_cents = checkout_state["priceCents"]
        approval_status = normalize_listing_approval_status(
            row_value(listing_row, "approval_status", "approved"), default="approved"
        )
        sale_status = normalize_listing_sale_status(
            row_value(listing_row, "sale_status", "available"), default="available"
        )

        if sale_status != "available":
            self.send_json(
                {
                    "error": (
                        "This paddle has a sale pending and is no longer available."
                        if sale_status == "pending"
                        else "This paddle has already been sold."
                    )
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        if approval_status == "pending":
            self.send_json(
                {"error": "This listing is still waiting for Eleven Zero PB review before checkout can begin."},
                status=HTTPStatus.CONFLICT,
            )
            return

        if approval_status == "rejected":
            self.send_json(
                {"error": "This listing needs seller updates before checkout can begin."},
                status=HTTPStatus.CONFLICT,
            )
            return

        if not stripe_is_configured():
            self.send_json(
                {"error": "Stripe is not connected in this app yet, so live checkout is still turned off."},
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        if not seller_user_id:
            self.send_json(
                {"error": "This sample listing is not attached to a live seller account yet."},
                status=HTTPStatus.CONFLICT,
            )
            return

        if seller_user_id == user["id"]:
            self.send_json(
                {"error": "You can’t purchase your own listing."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if not seller_profile["readyForPayouts"] or not seller_profile["connectedAccountId"]:
            self.send_json(
                {"error": "This seller still needs to finish payout setup before checkout can go live."},
                status=HTTPStatus.CONFLICT,
            )
            return

        if total_cents <= 0:
            self.send_json(
                {"error": "This listing price is not valid for checkout."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            shipping_quote = build_shipping_quote_for_listing(
                listing_row,
                body.get("shippingAddress", {}),
            )
        except ValueError as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return

        shipping_cents = int(shipping_quote["amount_cents"])
        final_total_cents = total_cents + shipping_cents

        if (
            shipping_quote.get("rate_kind") == "estimate"
            or not shipping_quote.get("shippo_rate_id")
        ):
            self.send_json(
                {
                    "error": (
                        "Prepaid shipping is temporarily unavailable for this paddle. "
                        "Please try again shortly or contact Eleven Zero PB support."
                    )
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        platform_fee_cents = min(
            total_cents - 1,
            max(0, int(round(total_cents * STRIPE_PLATFORM_FEE_PERCENT / 100))),
        )
        stripe_application_fee_cents = platform_fee_cents + shipping_cents

        product_name = f"{listing['brand']} {listing['model']}".strip()
        payload = {
            "mode": "payment",
            "success_url": self.checkout_success_url(),
            "cancel_url": self.checkout_cancel_url(),
            "customer_email": user["email"],
            "client_reference_id": f"ezpb-{listing['id']}-{user['id']}-{secrets.token_hex(4)}",
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(total_cents),
            "line_items[0][price_data][product_data][name]": product_name,
            "line_items[0][price_data][product_data][description]": listing["notes"][:180],
            "line_items[1][quantity]": "1",
            "line_items[1][price_data][currency]": "usd",
            "line_items[1][price_data][unit_amount]": str(shipping_cents),
            "line_items[1][price_data][product_data][name]": "Prepaid shipping",
            "line_items[1][price_data][product_data][description]": shipping_quote["summary"],
            # Keep the marketplace commission plus the buyer-paid shipping amount on
            # Eleven Zero. The product proceeds still route to the connected seller.
            "payment_intent_data[application_fee_amount]": str(stripe_application_fee_cents),
            "payment_intent_data[transfer_data][destination]": seller_profile["connectedAccountId"],
            "shipping_address_collection[allowed_countries][0]": "US",
            "phone_number_collection[enabled]": "true",
            "metadata[platform]": "Eleven Zero PB",
            "metadata[listing_id]": str(listing["id"]),
            "metadata[buyer_user_id]": str(user["id"]),
            "metadata[seller_user_id]": str(seller_user_id),
            "metadata[shipping_summary]": shipping_quote["summary"],
            "metadata[shipping_postal_code]": shipping_quote["postal_code"],
        }

        try:
            session = stripe_request("POST", "/checkout/sessions", payload)
        except (RuntimeError, ValueError) as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.BAD_GATEWAY)
            return

        checkout_url = session.get("url", "")
        session_id = session.get("id", "")
        if not checkout_url or not session_id:
            self.send_json(
                {"error": "Stripe did not return a checkout session."},
                status=HTTPStatus.BAD_GATEWAY,
            )
            return

        with closing(connect_db()) as connection:
            connection.execute(
                """
                INSERT INTO orders (
                  listing_id,
                  buyer_user_id,
                  seller_user_id,
                  stripe_checkout_session_id,
                  stripe_payment_intent_id,
                  amount_total_cents,
                  shipping_amount_cents,
                  shipping_label,
                  shipping_address_json,
                  shippo_rate_id,
                  shippo_shipment_id,
                  shipping_carrier,
                  shipping_service,
                  shipping_status,
                  platform_fee_cents,
                  stripe_payment_status,
                  stripe_session_status,
                  status,
                  created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    listing["id"],
                    user["id"],
                    seller_user_id,
                    session_id,
                    str(session.get("payment_intent") or ""),
                    final_total_cents,
                    shipping_cents,
                    shipping_quote["label"],
                    json.dumps(shipping_quote["address"], separators=(",", ":")),
                    shipping_quote.get("shippo_rate_id", ""),
                    shipping_quote.get("shippo_shipment_id", ""),
                    shipping_quote.get("carrier", ""),
                    shipping_quote.get("service", ""),
                    "pending" if shipping_quote.get("shippo_rate_id") else "manual",
                    platform_fee_cents,
                    str(session.get("payment_status") or "unpaid"),
                    str(session.get("status") or "open"),
                    "open",
                    utc_now(),
                ),
            )
            connection.commit()

        self.send_json(
            {
                "ok": True,
                "checkoutUrl": checkout_url,
                "sessionId": session_id,
                "listing": {
                    "id": listing["id"],
                    "title": product_name,
                    "priceUsd": listing["price_usd"],
                    "sellerName": listing["seller_name"] or "Eleven Zero PB seller",
                },
                "fee": {
                    "platformFeePercent": STRIPE_PLATFORM_FEE_PERCENT,
                    "platformFeeCents": platform_fee_cents,
                    "shippingHeldByPlatformCents": shipping_cents,
                },
                "shipping": {
                    "amountCents": shipping_cents,
                    "amountUsd": round(shipping_cents / 100, 2),
                    "label": shipping_quote["label"],
                    "estimatedTotalCents": final_total_cents,
                    "estimatedTotalUsd": round(final_total_cents / 100, 2),
                },
            },
            status=HTTPStatus.CREATED,
        )

    def handle_shipping_quote(self, body: dict):
        listing_id_raw = str(body.get("listingId", "")).strip()

        if not listing_id_raw.isdigit():
            self.send_json(
                {"error": "Choose a valid listing before estimating shipping."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        listing_row = self.fetch_listing_checkout_row(int(listing_id_raw))
        if not listing_row:
            self.send_json({"error": "That listing could not be found."}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            quote = build_shipping_quote_for_listing(listing_row, body.get("shippingAddress", {}))
        except ValueError as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return

        if quote["rate_kind"] == "free":
            message = f"Free shipping confirmed for {quote['destination_summary']}."
        elif quote["rate_kind"] == "flat":
            message = f"Flat shipping to {quote['destination_summary']} is ${quote['amount_usd']:.0f}."
        elif quote["rate_kind"] == "live":
            message = f"Live {quote['provider_label'].lower()} to {quote['destination_summary']} is ${quote['amount_usd']:.2f}."
        else:
            message = f"Estimated shipping to {quote['destination_summary']} is ${quote['amount_usd']:.0f}."

        self.send_json(
            {
                "ok": True,
                "message": message,
                "quote": {
                    "amountCents": quote["amount_cents"],
                    "amountUsd": quote["amount_usd"],
                    "estimatedTotalCents": quote["estimated_total_cents"],
                    "estimatedTotalUsd": quote["estimated_total_usd"],
                    "label": quote["label"],
                    "summary": quote["summary"],
                    "destinationSummary": quote["destination_summary"],
                    "serviceLevel": quote["service_level"],
                    "rateKind": quote["rate_kind"],
                    "isEstimate": quote["is_estimate"],
                    "providerLabel": quote["provider_label"],
                    "policyLabel": quote["policy_label"],
                },
            }
        )

    def handle_checkout_session_status(self, user: dict, session_id: str):
        if not session_id.startswith("cs_"):
            self.send_json(
                {"error": "A valid Stripe checkout session is required."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        order_row = self.fetch_order_row(session_id)
        if not order_row:
            self.send_json(
                {"error": "That checkout session could not be matched to an order yet."},
                status=HTTPStatus.NOT_FOUND,
            )
            return

        if order_row["buyer_user_id"] != user["id"]:
            self.send_json(
                {"error": "That checkout session belongs to another account."},
                status=HTTPStatus.FORBIDDEN,
            )
            return

        try:
            session = stripe_request("GET", f"/checkout/sessions/{session_id}")
        except (RuntimeError, ValueError) as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.BAD_GATEWAY)
            return

        payment_status = str(session.get("payment_status") or "unpaid")
        session_status = str(session.get("status") or "open")

        if payment_status == "paid":
            order_status = "paid"
            message = "Payment confirmed. The seller payout will route through Stripe after the platform fee."
        elif session_status == "complete":
            order_status = "processing"
            message = "Stripe shows the checkout as complete and the payment is still processing."
        elif session_status == "expired":
            order_status = "expired"
            message = "This checkout session expired before payment finished."
        else:
            order_status = "open"
            message = "This checkout session is still open."

        completed_at = utc_now() if order_status == "paid" else None

        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET
                  stripe_payment_intent_id = ?,
                  stripe_payment_status = ?,
                  stripe_session_status = ?,
                  status = ?,
                  completed_at = CASE
                    WHEN ? IS NOT NULL THEN COALESCE(completed_at, ?)
                    ELSE completed_at
                  END
                WHERE stripe_checkout_session_id = ?
                """,
                (
                    str(session.get("payment_intent") or ""),
                    payment_status,
                    session_status,
                    order_status,
                    completed_at,
                    completed_at,
                    session_id,
                ),
            )
            connection.commit()

        if order_status == "paid":
            finalize_paid_order(session_id)
            order_row = self.fetch_order_row(session_id) or order_row

        listing_title = " ".join(part for part in [order_row["brand"], order_row["model"]] if part).strip()

        self.send_json(
            {
                "ok": True,
                "message": message,
                "order": {
                    "sessionId": session_id,
                    "status": order_status,
                    "paymentStatus": payment_status,
                    "sessionStatus": session_status,
                    "listingTitle": listing_title or "Eleven Zero PB listing",
                    "sellerName": order_row["seller_name"] or "Eleven Zero PB seller",
                    "amountTotalCents": order_row["amount_total_cents"],
                    "shippingAmountCents": order_row["shipping_amount_cents"],
                    "shippingLabel": order_row["shipping_label"],
                    "shippingStatus": order_row["shipping_status"],
                    "trackingNumber": order_row["tracking_number"],
                    "trackingUrl": order_row["tracking_url"],
                    "platformFeeCents": order_row["platform_fee_cents"],
                },
            }
        )

    def handle_retry_shipping_label(self, user: dict, body: dict):
        session_id = compact_whitespace(body.get("sessionId", ""))
        if not session_id.startswith("cs_"):
            self.send_json(
                {"error": "Choose a valid paid order before retrying the shipping label."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        order_row = self.fetch_order_row(session_id)
        if not order_row:
            self.send_json({"error": "That order could not be found."}, status=HTTPStatus.NOT_FOUND)
            return

        is_admin = bool(user.get("isAdmin"))
        if int(order_row["seller_user_id"] or 0) != int(user["id"]) and not is_admin:
            self.send_json(
                {"error": "Only this order’s seller or the Eleven Zero PB owner can retry its label."},
                status=HTTPStatus.FORBIDDEN,
            )
            return

        if order_row["status"] != "paid" and order_row["stripe_payment_status"] != "paid":
            self.send_json(
                {"error": "The payment must be confirmed before a prepaid label can be purchased."},
                status=HTTPStatus.CONFLICT,
            )
            return

        if order_row["shippo_label_url"]:
            order_row = send_seller_shipping_label_email_for_order(session_id) or order_row
            self.send_json(
                {
                    "ok": True,
                    "message": "This prepaid label is already ready.",
                    "shippingStatus": order_row["shipping_status"],
                    "labelUrl": order_row["shippo_label_url"],
                    "trackingNumber": order_row["tracking_number"],
                    "trackingUrl": order_row["tracking_url"],
                    "sellerLabelEmailStatus": row_value(
                        order_row, "seller_label_email_status", "pending"
                    ),
                }
            )
            return

        refreshed_order = refresh_shippo_rate_for_order(session_id)
        if refreshed_order and refreshed_order["shipping_status"] == "pending":
            refreshed_order = purchase_shippo_label_for_order(session_id)
        refreshed_order = refreshed_order or self.fetch_order_row(session_id)

        if not refreshed_order or refreshed_order["shipping_status"] != "label_ready":
            self.send_json(
                {
                    "error": (
                        compact_whitespace(row_value(refreshed_order, "shipping_error", ""))
                        or "Shippo could not create the prepaid label. Please check the seller address and try again."
                    ),
                    "shippingStatus": row_value(refreshed_order, "shipping_status", "attention_needed"),
                },
                status=HTTPStatus.BAD_GATEWAY,
            )
            return

        self.send_json(
            {
                "ok": True,
                "message": "The prepaid shipping label is ready to print.",
                "shippingStatus": refreshed_order["shipping_status"],
                "labelUrl": refreshed_order["shippo_label_url"],
                "trackingNumber": refreshed_order["tracking_number"],
                "trackingUrl": refreshed_order["tracking_url"],
            }
        )

    def build_dashboard(self, user_id: int) -> dict:
        with closing(connect_db()) as connection:
            user = connection.execute(
                """
                SELECT
                  id,
                  name,
                  email,
                  profile_image_data,
                  profile_image_updated_at,
                  profile_pending_name,
                  profile_pending_image_data,
                  profile_pending_image_action,
                  profile_review_status,
                  profile_review_note,
                  profile_submitted_at,
                  profile_reviewed_at,
                  account_status,
                  account_status_note,
                  account_status_updated_at,
                  created_at,
                  stripe_account_id,
                  stripe_details_submitted,
                  stripe_charges_enabled,
                  stripe_payouts_enabled,
                  stripe_onboarding_complete,
                  stripe_requirements_due_count,
                  stripe_account_status_updated_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            listing_count = connection.execute(
                "SELECT COUNT(*) FROM listings WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            trainer_count = connection.execute(
                "SELECT COUNT(*) FROM trainers WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            review_count = connection.execute(
                "SELECT COUNT(*) FROM trainer_reviews WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            recent_listings = connection.execute(
                """
                SELECT
                  id,
                  brand,
                  model,
                  category,
                  condition,
                  price_usd,
                  location,
                  approval_status,
                  sale_status,
                  reviewed_at,
                  created_at
                FROM listings
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (user_id,),
            ).fetchall()
            recent_trainers = connection.execute(
                """
                SELECT name, level, format, rate, verified, joined_at
                FROM trainers
                WHERE user_id = ?
                ORDER BY joined_at DESC
                LIMIT 5
                """,
                (user_id,),
            ).fetchall()
            recent_sales = connection.execute(
                """
                SELECT
                  orders.stripe_checkout_session_id,
                  orders.amount_total_cents,
                  orders.shipping_amount_cents,
                  orders.shipping_carrier,
                  orders.shipping_service,
                  orders.shippo_label_url,
                  orders.tracking_number,
                  orders.tracking_url,
                  orders.shipping_status,
                  orders.shipping_error,
                  orders.status,
                  orders.created_at,
                  listings.brand,
                  listings.model
                FROM orders
                LEFT JOIN listings ON listings.id = orders.listing_id
                WHERE orders.seller_user_id = ?
                ORDER BY orders.created_at DESC
                LIMIT 10
                """,
                (user_id,),
            ).fetchall()

        return {
            "user": serialize_user(user),
            "sellerProfile": stripe_profile_from_row(user),
            "stats": {
                "listings": listing_count,
                "trainers": trainer_count,
                "reviews": review_count,
            },
            "recentListings": [row_to_dict(row) for row in recent_listings],
            "recentTrainers": [row_to_dict(row) for row in recent_trainers],
            "recentSales": [row_to_dict(row) for row in recent_sales],
        }

    def handle_update_profile(self, user: dict, body: dict):
        name = compact_whitespace(body.get("name", ""))
        if len(name) < 2 or len(name) > 60:
            self.send_json(
                {"error": "Display name must be between 2 and 60 characters."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if any(ord(character) < 32 for character in name):
            self.send_json(
                {"error": "Display name contains unsupported characters."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if profile_name_contains_profanity(name):
            self.send_json(
                {"error": "Choose a different display name. Profanity is not allowed."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        client_key = f"account-profile:{int(user['id'])}"
        if not rate_limit_allows(client_key, 20, 3600):
            self.send_json(
                {"error": "Too many profile changes. Please wait and try again."},
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )
            return

        image_was_provided = "profileImage" in body
        profile_image_data = ""
        pending_image_action = "keep"
        if image_was_provided:
            raw_profile_image = str(body.get("profileImage", "") or "").strip()
            if raw_profile_image:
                try:
                    profile_image_data = normalize_profile_image_data(raw_profile_image)
                    pending_image_action = "replace"
                except ValueError as error:
                    self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                    return
            else:
                profile_image_data = ""
                pending_image_action = "remove"

        with closing(connect_db()) as connection:
            submitted_at = utc_now()
            connection.execute(
                """
                UPDATE users
                SET
                  profile_pending_name = ?,
                  profile_pending_image_data = ?,
                  profile_pending_image_action = ?,
                  profile_review_status = 'pending',
                  profile_review_note = NULL,
                  profile_submitted_at = ?,
                  profile_reviewed_at = NULL
                WHERE id = ?
                """,
                (name, profile_image_data, pending_image_action, submitted_at, int(user["id"])),
            )

            updated_user = connection.execute(
                """
                SELECT
                  id,
                  name,
                  email,
                  email_verified,
                  profile_image_data,
                  profile_image_updated_at,
                  profile_pending_name,
                  profile_pending_image_data,
                  profile_pending_image_action,
                  profile_review_status,
                  profile_review_note,
                  profile_submitted_at,
                  profile_reviewed_at,
                  account_status,
                  account_status_note,
                  account_status_updated_at,
                  created_at,
                  stripe_account_id,
                  stripe_details_submitted,
                  stripe_charges_enabled,
                  stripe_payouts_enabled,
                  stripe_onboarding_complete,
                  stripe_requirements_due_count,
                  stripe_account_status_updated_at
                FROM users
                WHERE id = ?
                """,
                (int(user["id"]),),
            ).fetchone()
            connection.commit()

        self.send_json(
            {
                "ok": True,
                "message": "Profile changes submitted for review.",
                "user": serialize_user(updated_user),
            }
        )

    def build_admin_dashboard(self) -> dict:
        with closing(connect_db()) as connection:
            user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            profile_pending_count = connection.execute(
                "SELECT COUNT(*) FROM users WHERE profile_review_status = 'pending'"
            ).fetchone()[0]
            account_suspended_count = connection.execute(
                "SELECT COUNT(*) FROM users WHERE account_status = 'suspended'"
            ).fetchone()[0]
            listing_count = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            listing_pending_count = connection.execute(
                "SELECT COUNT(*) FROM listings WHERE approval_status = 'pending'"
            ).fetchone()[0]
            listing_approved_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM listings
                WHERE approval_status = 'approved'
                  AND sale_status = 'available'
                """
            ).fetchone()[0]
            listing_rejected_count = connection.execute(
                "SELECT COUNT(*) FROM listings WHERE approval_status = 'rejected'"
            ).fetchone()[0]
            court_count = connection.execute("SELECT COUNT(*) FROM courts_directory").fetchone()[0]
            court_pending_count = connection.execute(
                "SELECT COUNT(*) FROM courts_directory WHERE approval_status = 'pending'"
            ).fetchone()[0]
            court_approved_count = connection.execute(
                "SELECT COUNT(*) FROM courts_directory WHERE approval_status = 'approved'"
            ).fetchone()[0]
            court_rejected_count = connection.execute(
                "SELECT COUNT(*) FROM courts_directory WHERE approval_status = 'rejected'"
            ).fetchone()[0]
            trainer_count = connection.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
            trainer_review_count = connection.execute("SELECT COUNT(*) FROM trainer_reviews").fetchone()[0]
            court_report_count = connection.execute("SELECT COUNT(*) FROM court_reports").fetchone()[0]

            paid_orders = connection.execute(
                """
                SELECT
                  id,
                  buyer_user_id,
                  amount_total_cents,
                  created_at,
                  completed_at
                FROM orders
                WHERE status = 'paid' OR stripe_payment_status = 'paid'
                ORDER BY COALESCE(completed_at, created_at) ASC, id ASC
                """
            ).fetchall()

            purchase_activity = connection.execute(
                """
                SELECT
                  orders.id,
                  orders.listing_id,
                  orders.stripe_checkout_session_id,
                  orders.amount_total_cents,
                  orders.shipping_status,
                  orders.shipping_error,
                  orders.buyer_confirmation_status,
                  orders.buyer_confirmation_error,
                  orders.buyer_confirmation_sent_at,
                  COALESCE(orders.completed_at, orders.created_at) AS activity_at,
                  listings.brand,
                  listings.model,
                  buyers.name AS buyer_name,
                  buyers.email AS buyer_email,
                  sellers.name AS seller_name,
                  sellers.email AS seller_email
                FROM orders
                LEFT JOIN listings ON listings.id = orders.listing_id
                LEFT JOIN users AS buyers ON buyers.id = orders.buyer_user_id
                LEFT JOIN users AS sellers ON sellers.id = orders.seller_user_id
                WHERE orders.status = 'paid' OR orders.stripe_payment_status = 'paid'
                ORDER BY COALESCE(orders.completed_at, orders.created_at) DESC, orders.id DESC
                LIMIT 20
                """
            ).fetchall()

            listing_activity = connection.execute(
                """
                SELECT
                  listings.id,
                  listings.brand,
                  listings.model,
                  listings.price_usd,
                  listings.approval_status,
                  listings.sale_status,
                  listings.created_at AS activity_at,
                  users.name AS seller_name,
                  users.email AS seller_email
                FROM listings
                JOIN users ON users.id = listings.user_id
                ORDER BY listings.created_at DESC, listings.id DESC
                LIMIT 20
                """
            ).fetchall()

            listings = connection.execute(
                """
                SELECT
                  listings.id,
                  listings.user_id,
                  listings.brand,
                  listings.model,
                  listings.color,
                  listings.thickness_mm,
                  listings.category,
                  listings.condition,
                  listings.price_usd,
                  listings.location,
                  listings.notes,
                  listings.shipping_mode,
                  listings.shipping_flat_usd,
                  listings.shipping_origin_zip,
                  listings.shipping_origin_street1,
                  listings.shipping_weight_oz,
                  listings.shipping_length_in,
                  listings.shipping_width_in,
                  listings.shipping_height_in,
                  listings.shipping_note,
                  listings.image_data_json,
                  listings.approval_status,
                  listings.sale_status,
                  listings.reviewed_at,
                  listings.created_at,
                  users.name AS seller_name,
                  users.email AS seller_email,
                  users.stripe_account_id,
                  users.stripe_details_submitted,
                  users.stripe_charges_enabled,
                  users.stripe_payouts_enabled,
                  users.stripe_onboarding_complete,
                  users.stripe_requirements_due_count,
                  users.stripe_account_status_updated_at
                FROM listings
                LEFT JOIN users ON users.id = listings.user_id
                ORDER BY listings.created_at DESC, listings.id DESC
                LIMIT 16
                """
            ).fetchall()

            courts = connection.execute(
                """
                SELECT
                  courts_directory.id,
                  courts_directory.user_id,
                  courts_directory.name,
                  courts_directory.location,
                  courts_directory.address,
                  courts_directory.access_kind,
                  courts_directory.surface_kind,
                  courts_directory.court_count,
                  courts_directory.access_note,
                  courts_directory.amenities,
                  courts_directory.description,
                  courts_directory.website,
                  courts_directory.affiliate_url,
                  courts_directory.affiliate_label,
                  courts_directory.approval_status,
                  courts_directory.reviewed_at,
                  courts_directory.lat,
                  courts_directory.lon,
                  courts_directory.created_at,
                  users.name AS owner_name,
                  users.email AS owner_email
                FROM courts_directory
                LEFT JOIN users ON users.id = courts_directory.user_id
                ORDER BY
                  CASE courts_directory.approval_status
                    WHEN 'pending' THEN 0
                    WHEN 'rejected' THEN 1
                    ELSE 2
                  END,
                  courts_directory.created_at DESC,
                  courts_directory.id DESC
                LIMIT 16
                """
            ).fetchall()

            trainers = connection.execute(
                """
                SELECT
                  trainers.id,
                  trainers.user_id,
                  trainers.name,
                  trainers.location,
                  trainers.format,
                  trainers.level,
                  trainers.rate,
                  trainers.email,
                  trainers.verified,
                  trainers.experience,
                  trainers.bio,
                  trainers.availability,
                  trainers.joined_at,
                  trainers.rating,
                  trainers.review_count,
                  trainers.approval_status,
                  trainers.reviewed_at,
                  users.name AS owner_name,
                  users.email AS owner_email
                FROM trainers
                LEFT JOIN users ON users.id = trainers.user_id
                ORDER BY trainers.joined_at DESC, trainers.id DESC
                LIMIT 16
                """
            ).fetchall()

            trainer_reviews = connection.execute(
                """
                SELECT
                  trainer_reviews.id,
                  trainer_reviews.trainer_id,
                  trainers.name AS trainer_name,
                  trainer_reviews.reviewer_name,
                  trainer_reviews.rating,
                  trainer_reviews.comment,
                  trainer_reviews.created_at
                FROM trainer_reviews
                JOIN trainers ON trainers.id = trainer_reviews.trainer_id
                ORDER BY trainer_reviews.created_at DESC, trainer_reviews.id DESC
                LIMIT 12
                """
            ).fetchall()

            court_reports = connection.execute(
                """
                SELECT
                  id,
                  court_id,
                  court_name,
                  court_location,
                  reviewer_name,
                  condition_rating,
                  busyness_rating,
                  player_level,
                  comment,
                  created_at
                FROM court_reports
                ORDER BY created_at DESC, id DESC
                LIMIT 12
                """
            ).fetchall()

            profile_reviews = connection.execute(
                """
                SELECT
                  id,
                  name,
                  email,
                  profile_image_data,
                  profile_pending_name,
                  profile_pending_image_data,
                  profile_pending_image_action,
                  profile_review_status,
                  profile_review_note,
                  profile_submitted_at,
                  profile_reviewed_at,
                  account_status,
                  account_status_note,
                  account_status_updated_at
                FROM users
                WHERE profile_review_status = 'pending'
                   OR account_status = 'suspended'
                ORDER BY
                  CASE profile_review_status WHEN 'pending' THEN 0 ELSE 1 END,
                  COALESCE(profile_submitted_at, account_status_updated_at, created_at) DESC,
                  id DESC
                LIMIT 30
                """
            ).fetchall()

        commerce_notifications = []
        for row in purchase_activity:
            item = row_to_dict(row)
            item.update({"id": f"purchase-{row['id']}", "type": "purchase"})
            commerce_notifications.append(item)
        for row in listing_activity:
            item = row_to_dict(row)
            item.update({"id": f"listing-{row['id']}", "listing_id": row["id"], "type": "listing"})
            commerce_notifications.append(item)

        commerce_notifications.sort(
            key=lambda item: parse_activity_datetime(item.get("activity_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        return {
            "stats": {
                "users": user_count,
                "profilePending": profile_pending_count,
                "accountSuspended": account_suspended_count,
                "listings": listing_count,
                "listingPending": listing_pending_count,
                "listingApproved": listing_approved_count,
                "listingNeedsChanges": listing_rejected_count,
                "courts": court_count,
                "courtPending": court_pending_count,
                "courtApproved": court_approved_count,
                "courtNeedsChanges": court_rejected_count,
                "trainers": trainer_count,
                "trainerReviews": trainer_review_count,
                "courtReports": court_report_count,
            },
            "listings": [serialize_admin_listing_row(row) for row in listings],
            "courts": [serialize_admin_court_row(row) for row in courts],
            "trainers": [serialize_admin_trainer_row(row) for row in trainers],
            "trainerReviews": [serialize_admin_trainer_review_row(row) for row in trainer_reviews],
            "courtReports": [serialize_admin_court_report_row(row) for row in court_reports],
            "profileReviews": [serialize_admin_profile_row(row) for row in profile_reviews],
            "commerceNotifications": commerce_notifications[:20],
            "salesAnalytics": build_sales_analytics(paid_orders),
        }

    def handle_admin_profile_review(self, admin_user: dict, body: dict):
        user_id = int(body.get("id") or 0)
        action = str(body.get("action") or "").strip().lower()
        note = compact_whitespace(body.get("note", ""))[:240]
        if user_id <= 0 or action not in {"approve", "reject", "suspend", "restore"}:
            self.send_json(
                {"error": "Choose a valid member and moderation action."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if action == "suspend" and user_id == int(admin_user.get("id") or 0):
            self.send_json(
                {"error": "The active owner account cannot suspend itself."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        with closing(connect_db()) as connection:
            row = connection.execute(
                """
                SELECT
                  id,
                  name,
                  profile_image_data,
                  profile_pending_name,
                  profile_pending_image_data,
                  profile_pending_image_action,
                  profile_review_status,
                  account_status
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            if not row:
                self.send_json({"error": "Member not found."}, status=HTTPStatus.NOT_FOUND)
                return

            now = utc_now()
            if action == "approve":
                if str(row["profile_review_status"] or "approved") != "pending":
                    self.send_json(
                        {"error": "This member has no pending profile changes."},
                        status=HTTPStatus.CONFLICT,
                    )
                    return

                approved_name = compact_whitespace(row["profile_pending_name"] or row["name"])
                pending_image_action = str(row["profile_pending_image_action"] or "keep")
                approved_image = str(row["profile_image_data"] or "")
                image_changed = pending_image_action in {"replace", "remove"}
                if pending_image_action == "replace":
                    approved_image = str(row["profile_pending_image_data"] or "")
                elif pending_image_action == "remove":
                    approved_image = ""

                connection.execute(
                    """
                    UPDATE users
                    SET
                      name = ?,
                      profile_image_data = ?,
                      profile_image_updated_at = CASE WHEN ? THEN ? ELSE profile_image_updated_at END,
                      profile_pending_name = NULL,
                      profile_pending_image_data = NULL,
                      profile_pending_image_action = 'keep',
                      profile_review_status = 'approved',
                      profile_review_note = ?,
                      profile_reviewed_at = ?
                    WHERE id = ?
                    """,
                    (approved_name, approved_image, image_changed, now, note, now, user_id),
                )
                message = f"{approved_name}'s profile changes are approved."
            elif action == "reject":
                rejection_note = note or "The proposed profile did not meet the community guidelines."
                connection.execute(
                    """
                    UPDATE users
                    SET
                      profile_pending_name = NULL,
                      profile_pending_image_data = NULL,
                      profile_pending_image_action = 'keep',
                      profile_review_status = 'rejected',
                      profile_review_note = ?,
                      profile_reviewed_at = ?
                    WHERE id = ?
                    """,
                    (rejection_note, now, user_id),
                )
                message = f"{row['name']}'s proposed profile was rejected."
            elif action == "suspend":
                suspension_note = note or "Account suspended by the Eleven Zero PB moderator."
                connection.execute(
                    """
                    UPDATE users
                    SET
                      account_status = 'suspended',
                      account_status_note = ?,
                      account_status_updated_at = ?,
                      profile_pending_name = NULL,
                      profile_pending_image_data = NULL,
                      profile_pending_image_action = 'keep',
                      profile_review_status = CASE
                        WHEN profile_review_status = 'pending' THEN 'rejected'
                        ELSE profile_review_status
                      END,
                      profile_review_note = CASE
                        WHEN profile_review_status = 'pending' THEN ?
                        ELSE profile_review_note
                      END,
                      profile_reviewed_at = CASE
                        WHEN profile_review_status = 'pending' THEN ?
                        ELSE profile_reviewed_at
                      END
                    WHERE id = ?
                    """,
                    (suspension_note, now, suspension_note, now, user_id),
                )
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                message = f"{row['name']}'s account is suspended."
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET account_status = 'active', account_status_note = NULL, account_status_updated_at = ?
                    WHERE id = ?
                    """,
                    (now, user_id),
                )
                message = f"{row['name']}'s account is active again."

            connection.commit()

        self.send_json({"ok": True, "message": message})

    def handle_admin_listing_update(self, body: dict):
        listing_id = int(body.get("id") or 0)
        brand = str(body.get("brand", "")).strip()
        model = str(body.get("model", "")).strip()
        color = str(body.get("color", "")).strip()
        thickness_raw = str(body.get("thickness", "")).strip()
        thickness_mm = parse_thickness_mm(thickness_raw) if thickness_raw else None
        category = str(body.get("category", "")).strip().lower() or "control"
        condition = str(body.get("condition", "")).strip()
        location = str(body.get("location", "")).strip()
        notes = str(body.get("notes", "")).strip() or "No extra condition notes added yet."
        price_raw = str(body.get("price", "")).strip()
        digits = "".join(ch for ch in price_raw if ch.isdigit())
        price_usd = int(digits) if digits else 0

        if listing_id <= 0:
            self.send_json({"error": "Choose a valid listing to update."}, status=HTTPStatus.BAD_REQUEST)
            return

        if not all([brand, model, category, condition, location, notes]) or price_usd <= 0:
            self.send_json({"error": "Please complete every listing field before saving."}, status=HTTPStatus.BAD_REQUEST)
            return

        if category not in {"control", "power", "hybrid"}:
            self.send_json({"error": "Listing category must be control, power, or hybrid."}, status=HTTPStatus.BAD_REQUEST)
            return

        if thickness_raw and thickness_mm is None:
            self.send_json({"error": "Add a valid paddle thickness in millimeters."}, status=HTTPStatus.BAD_REQUEST)
            return

        with closing(connect_db()) as connection:
            cursor = connection.execute(
                """
                UPDATE listings
                SET
                  brand = ?,
                  model = ?,
                  color = ?,
                  thickness_mm = ?,
                  category = ?,
                  condition = ?,
                  price_usd = ?,
                  location = ?,
                  notes = ?
                WHERE id = ?
                """,
                (brand, model, color, thickness_mm, category, condition, price_usd, location, notes, listing_id),
            )
            connection.commit()

        if cursor.rowcount <= 0:
            self.send_json({"error": "Listing not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, "message": f"{brand} {model} was updated."})

    def handle_admin_listing_review(self, body: dict):
        listing_id = int(body.get("id") or 0)
        requested_status = compact_whitespace(body.get("status", "")).lower()

        if listing_id <= 0:
            self.send_json({"error": "Choose a valid listing to review."}, status=HTTPStatus.BAD_REQUEST)
            return

        if requested_status not in LISTING_APPROVAL_LABELS:
            self.send_json(
                {"error": "Choose pending review, live, or needs changes for this listing."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        reviewed_at = utc_now() if requested_status in {"approved", "rejected"} else None

        with closing(connect_db()) as connection:
            listing_row = connection.execute(
                "SELECT brand, model FROM listings WHERE id = ?",
                (listing_id,),
            ).fetchone()

            if not listing_row:
                self.send_json({"error": "Listing not found."}, status=HTTPStatus.NOT_FOUND)
                return

            connection.execute(
                """
                UPDATE listings
                SET approval_status = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (requested_status, reviewed_at, listing_id),
            )
            connection.commit()

        title = " ".join(
            part for part in [listing_row["brand"], listing_row["model"]] if compact_whitespace(part)
        ).strip() or "Listing"
        status_label = LISTING_APPROVAL_LABELS.get(requested_status, "Pending review")
        self.send_json({"ok": True, "message": f"{title} is now marked as {status_label.lower()}."})

    def handle_admin_listing_sale_status(self, body: dict):
        listing_id = int(body.get("id") or 0)
        requested_status = normalize_listing_sale_status(body.get("status", ""), default="")

        if listing_id <= 0:
            self.send_json(
                {"error": "Choose a valid listing to update."}, status=HTTPStatus.BAD_REQUEST
            )
            return

        if requested_status not in LISTING_SALE_LABELS:
            self.send_json(
                {"error": "Choose available, sale pending, or sold for this listing."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        with closing(connect_db()) as connection:
            listing_row = connection.execute(
                "SELECT brand, model FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()
            if not listing_row:
                self.send_json({"error": "Listing not found."}, status=HTTPStatus.NOT_FOUND)
                return
            connection.execute(
                "UPDATE listings SET sale_status = ? WHERE id = ?",
                (requested_status, listing_id),
            )
            connection.commit()

        title = " ".join(
            part for part in [listing_row["brand"], listing_row["model"]] if compact_whitespace(part)
        ).strip() or "Listing"
        self.send_json(
            {
                "ok": True,
                "message": f"{title} is now marked {LISTING_SALE_LABELS[requested_status].lower()}.",
            }
        )

    def handle_admin_send_order_confirmation(self, body: dict):
        session_id = compact_whitespace(body.get("sessionId", ""))
        if not session_id.startswith("cs_"):
            self.send_json(
                {"error": "Choose a valid paid order before sending its confirmation."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        order_row = order_email_row(session_id)
        if not order_row:
            self.send_json({"error": "That order could not be found."}, status=HTTPStatus.NOT_FOUND)
            return
        if order_row["status"] != "paid" and order_row["stripe_payment_status"] != "paid":
            self.send_json(
                {"error": "The payment must be confirmed before sending a purchase confirmation."},
                status=HTTPStatus.CONFLICT,
            )
            return

        if order_row["buyer_confirmation_sent_at"]:
            self.send_json({"ok": True, "message": "The buyer confirmation was already sent."})
            return

        if not transactional_email_is_configured():
            self.send_json(
                {
                    "error": (
                        "Buyer email is ready, but transactional email is not configured. "
                        "Add the Eleven Zero PB Gmail app password in Render first."
                    )
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        with closing(connect_db()) as connection:
            connection.execute(
                """
                UPDATE orders
                SET buyer_confirmation_status = 'pending', buyer_confirmation_error = ''
                WHERE stripe_checkout_session_id = ?
                  AND buyer_confirmation_sent_at IS NULL
                """,
                (session_id,),
            )
            connection.commit()

        result = send_purchase_confirmation_for_order(session_id)
        if result and result["buyer_confirmation_status"] == "sent":
            self.send_json({"ok": True, "message": "Purchase confirmation sent to the buyer."})
            return

        self.send_json(
            {
                "error": (
                    compact_whitespace(row_value(result, "buyer_confirmation_error", ""))
                    or "The purchase confirmation could not be sent."
                )
            },
            status=HTTPStatus.BAD_GATEWAY,
        )

    def handle_admin_listing_delete(self, body: dict):
        listing_id = int(body.get("id") or 0)
        if listing_id <= 0:
            self.send_json({"error": "Choose a valid listing to remove."}, status=HTTPStatus.BAD_REQUEST)
            return

        with closing(connect_db()) as connection:
            cursor = connection.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
            connection.commit()

        if cursor.rowcount <= 0:
            self.send_json({"error": "Listing not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, "message": "Listing removed from the marketplace."})

    def handle_admin_court_update(self, body: dict):
        court_id = int(body.get("id") or 0)
        name = str(body.get("name", "")).strip()
        location = str(body.get("location", "")).strip()
        address = str(body.get("address", "")).strip() or location
        access_kind = str(body.get("accessKind", "")).strip().lower()
        surface_kind = str(body.get("surfaceKind", "")).strip().lower()
        access_note = str(body.get("accessNote", "")).strip()
        amenities = str(body.get("amenities", "")).strip()
        description = str(body.get("description", "")).strip()
        website = str(body.get("website", "")).strip()
        affiliate_url = str(body.get("affiliateUrl", "")).strip()
        affiliate_label = str(body.get("affiliateLabel", "")).strip()

        try:
            court_count = int(str(body.get("courtCount", "")).strip() or "0")
        except ValueError:
            court_count = 0

        if court_id <= 0:
            self.send_json({"error": "Choose a valid court to update."}, status=HTTPStatus.BAD_REQUEST)
            return

        if not all([name, location, address, access_kind, surface_kind, description]) or court_count <= 0:
            self.send_json({"error": "Please complete every court field before saving."}, status=HTTPStatus.BAD_REQUEST)
            return

        if access_kind not in {"free", "paid", "check"}:
            self.send_json({"error": "Court access must be free, paid, or check."}, status=HTTPStatus.BAD_REQUEST)
            return

        if surface_kind not in {"indoor", "outdoor"}:
            self.send_json({"error": "Court surface must be indoor or outdoor."}, status=HTTPStatus.BAD_REQUEST)
            return

        if website and not urlparse(website).scheme:
            website = f"https://{website}"

        if affiliate_url and not urlparse(affiliate_url).scheme:
            affiliate_url = f"https://{affiliate_url}"

        with closing(connect_db()) as connection:
            cursor = connection.execute(
                """
                UPDATE courts_directory
                SET
                  name = ?,
                  location = ?,
                  address = ?,
                  access_kind = ?,
                  surface_kind = ?,
                  court_count = ?,
                  access_note = ?,
                  amenities = ?,
                  description = ?,
                  website = ?,
                  affiliate_url = ?,
                  affiliate_label = ?
                WHERE id = ?
                """,
                (
                    name,
                    location,
                    address,
                    access_kind,
                    surface_kind,
                    court_count,
                    access_note,
                    amenities,
                    description,
                    website,
                    affiliate_url,
                    affiliate_label,
                    court_id,
                ),
            )
            connection.commit()

        if cursor.rowcount <= 0:
            self.send_json({"error": "Court not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, "message": f"{name} was updated in the courts directory."})

    def handle_admin_court_review(self, body: dict):
        court_id = int(body.get("id") or 0)
        requested_status = compact_whitespace(body.get("status", "")).lower()

        if court_id <= 0:
            self.send_json({"error": "Choose a valid court to review."}, status=HTTPStatus.BAD_REQUEST)
            return

        if requested_status not in COURT_APPROVAL_LABELS:
            self.send_json(
                {"error": "Choose pending review, live, or needs changes for this court."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        reviewed_at = utc_now() if requested_status in {"approved", "rejected"} else None

        with closing(connect_db()) as connection:
            court_row = connection.execute(
                "SELECT name FROM courts_directory WHERE id = ?",
                (court_id,),
            ).fetchone()

            if not court_row:
                self.send_json({"error": "Court not found."}, status=HTTPStatus.NOT_FOUND)
                return

            connection.execute(
                """
                UPDATE courts_directory
                SET approval_status = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (requested_status, reviewed_at, court_id),
            )
            connection.commit()

        court_name = compact_whitespace(court_row["name"]) or "Court"
        status_label = COURT_APPROVAL_LABELS.get(requested_status, "Pending review")
        self.send_json({"ok": True, "message": f"{court_name} is now marked as {status_label.lower()}."})

    def handle_admin_court_delete(self, body: dict):
        court_id = int(body.get("id") or 0)
        if court_id <= 0:
            self.send_json({"error": "Choose a valid court to remove."}, status=HTTPStatus.BAD_REQUEST)
            return

        directory_court_public_id = f"directory-{court_id}"

        with closing(connect_db()) as connection:
            cursor = connection.execute("DELETE FROM courts_directory WHERE id = ?", (court_id,))
            connection.execute("DELETE FROM court_reports WHERE court_id = ?", (directory_court_public_id,))
            connection.commit()

        if cursor.rowcount <= 0:
            self.send_json({"error": "Court not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, "message": "Court removed from the directory."})

    def handle_admin_trainer_update(self, body: dict):
        trainer_id = int(body.get("id") or 0)
        name = str(body.get("name", "")).strip()
        location = str(body.get("location", "")).strip()
        format_value = str(body.get("format", "")).strip().lower()
        level = str(body.get("level", "")).strip().lower()
        rate = str(body.get("rate", "")).strip()
        email = normalize_email(str(body.get("email", "")).strip())
        experience = str(body.get("experience", "")).strip()
        availability = str(body.get("availability", "")).strip()
        bio = str(body.get("bio", "")).strip()
        verified = bool(body.get("verified"))

        if trainer_id <= 0:
            self.send_json({"error": "Choose a valid trainer profile to update."}, status=HTTPStatus.BAD_REQUEST)
            return

        if not all([name, location, format_value, level, rate, email, experience, availability, bio]):
            self.send_json({"error": "Please complete every trainer field before saving."}, status=HTTPStatus.BAD_REQUEST)
            return

        if format_value not in {"private", "group", "clinic", "virtual"}:
            self.send_json({"error": "Trainer format is not valid."}, status=HTTPStatus.BAD_REQUEST)
            return

        if level not in {"beginner", "intermediate", "advanced"}:
            self.send_json({"error": "Trainer level is not valid."}, status=HTTPStatus.BAD_REQUEST)
            return

        with closing(connect_db()) as connection:
            cursor = connection.execute(
                """
                UPDATE trainers
                SET
                  name = ?,
                  location = ?,
                  format = ?,
                  level = ?,
                  rate = ?,
                  email = ?,
                  verified = ?,
                  experience = ?,
                  bio = ?,
                  availability = ?
                WHERE id = ?
                """,
                (
                    name,
                    location,
                    format_value,
                    level,
                    rate,
                    email,
                    bool_to_int(verified),
                    experience,
                    bio,
                    availability,
                    trainer_id,
                ),
            )
            connection.commit()

        if cursor.rowcount <= 0:
            self.send_json({"error": "Trainer not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, "message": f"{name} was updated."})

    def handle_admin_trainer_review(self, body: dict):
        trainer_id = int(body.get("id") or 0)
        requested_status = normalize_listing_approval_status(str(body.get("status", "")), default="")
        if trainer_id <= 0 or requested_status not in LISTING_APPROVAL_LABELS:
            self.send_json(
                {"error": "Choose a valid trainer and review status."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        reviewed_at = utc_now() if requested_status in {"approved", "rejected"} else None
        with closing(connect_db()) as connection:
            row = connection.execute("SELECT name FROM trainers WHERE id = ?", (trainer_id,)).fetchone()
            if not row:
                self.send_json({"error": "Trainer not found."}, status=HTTPStatus.NOT_FOUND)
                return
            connection.execute(
                "UPDATE trainers SET approval_status = ?, reviewed_at = ? WHERE id = ?",
                (requested_status, reviewed_at, trainer_id),
            )
            connection.commit()

        label = LISTING_APPROVAL_LABELS.get(requested_status, "Pending review")
        self.send_json({"ok": True, "message": f"{row['name']} is now marked {label.lower()}."})

    def handle_admin_trainer_delete(self, body: dict):
        trainer_id = int(body.get("id") or 0)
        if trainer_id <= 0:
            self.send_json({"error": "Choose a valid trainer to remove."}, status=HTTPStatus.BAD_REQUEST)
            return

        with closing(connect_db()) as connection:
            cursor = connection.execute("DELETE FROM trainers WHERE id = ?", (trainer_id,))
            connection.commit()

        if cursor.rowcount <= 0:
            self.send_json({"error": "Trainer not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, "message": "Trainer profile removed."})

    def handle_admin_trainer_review_delete(self, body: dict):
        review_id = int(body.get("id") or 0)
        if review_id <= 0:
            self.send_json({"error": "Choose a valid trainer review to remove."}, status=HTTPStatus.BAD_REQUEST)
            return

        with closing(connect_db()) as connection:
            review_row = connection.execute(
                "SELECT trainer_id, rating FROM trainer_reviews WHERE id = ?",
                (review_id,),
            ).fetchone()

            if not review_row:
                self.send_json({"error": "Trainer review not found."}, status=HTTPStatus.NOT_FOUND)
                return

            trainer_id = review_row["trainer_id"]
            rating = int(review_row["rating"] or 0)

            connection.execute("DELETE FROM trainer_reviews WHERE id = ?", (review_id,))

            trainer = connection.execute(
                "SELECT review_count, rating FROM trainers WHERE id = ?",
                (trainer_id,),
            ).fetchone()

            if trainer:
                review_count = max(int(trainer["review_count"] or 0) - 1, 0)
                current_rating = float(trainer["rating"] or 0)
                if review_count > 0:
                    next_rating = max(((current_rating * (review_count + 1)) - rating) / review_count, 0)
                else:
                    next_rating = 0

                connection.execute(
                    "UPDATE trainers SET review_count = ?, rating = ? WHERE id = ?",
                    (review_count, round(next_rating, 2), trainer_id),
                )

            connection.commit()

        self.send_json({"ok": True, "message": "Trainer review removed."})

    def handle_admin_court_report_delete(self, body: dict):
        report_id = int(body.get("id") or 0)
        if report_id <= 0:
            self.send_json({"error": "Choose a valid court report to remove."}, status=HTTPStatus.BAD_REQUEST)
            return

        with closing(connect_db()) as connection:
            cursor = connection.execute("DELETE FROM court_reports WHERE id = ?", (report_id,))
            connection.commit()

        if cursor.rowcount <= 0:
            self.send_json({"error": "Court report not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, "message": "Court report removed."})

    def handle_signup(self, body: dict):
        name = str(body.get("name", "")).strip()
        email = normalize_email(str(body.get("email", "")))
        password = str(body.get("password", ""))

        client_key = f"signup:{self.client_address[0]}"
        if not rate_limit_allows(client_key, 5, 3600):
            self.send_json(
                {"error": "Too many account attempts. Please wait and try again."},
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )
            return

        if len(name) < 2 or "@" not in email or len(password) < 8:
            self.send_json(
                {"error": "Use a real name, a valid email, and a password with at least 8 characters."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if profile_name_contains_profanity(name):
            self.send_json(
                {"error": "Choose a different display name. Profanity is not allowed."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        salt_hex, digest_hex = hash_password(password)

        try:
            with closing(connect_db()) as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (
                      name, email, password_salt, password_hash, email_verified, email_verified_at, created_at
                    ) VALUES (?, ?, ?, ?, 0, NULL, ?)
                    """,
                    (name, email, salt_hex, digest_hex, utc_now()),
                )
                user_row = connection.execute(
                    """
                    SELECT
                      id,
                      name,
                      email,
                      email_verified,
                      profile_image_data,
                      profile_image_updated_at,
                      created_at,
                      stripe_account_id,
                      stripe_details_submitted,
                      stripe_charges_enabled,
                      stripe_payouts_enabled,
                      stripe_onboarding_complete,
                      stripe_requirements_due_count,
                      stripe_account_status_updated_at
                    FROM users
                    WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
                connection.commit()
                user_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            self.send_json(
                {"error": "That email already has an account."},
                status=HTTPStatus.CONFLICT,
            )
            return

        token, csrf_token = self.create_session(user_id)
        verification_sent = send_verification_email(user_id, email)
        self.send_json(
            {
                "ok": True,
                "user": serialize_user(user_row),
                "csrfToken": csrf_token,
                "verificationSent": verification_sent,
            },
            status=HTTPStatus.CREATED,
            cookie=self.session_cookie(token),
        )

    def handle_signin(self, body: dict):
        email = normalize_email(str(body.get("email", "")))
        password = str(body.get("password", ""))

        client_key = f"signin:{self.client_address[0]}:{email}"
        if not rate_limit_allows(client_key, 8, 900):
            self.send_json(
                {"error": "Too many sign-in attempts. Please wait 15 minutes and try again."},
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )
            return

        with closing(connect_db()) as connection:
            user_row = connection.execute(
                """
                SELECT
                  id,
                  name,
                  email,
                  email_verified,
                  profile_image_data,
                  profile_image_updated_at,
                  profile_pending_name,
                  profile_pending_image_data,
                  profile_pending_image_action,
                  profile_review_status,
                  profile_review_note,
                  profile_submitted_at,
                  profile_reviewed_at,
                  account_status,
                  account_status_note,
                  account_status_updated_at,
                  password_salt,
                  password_hash,
                  created_at,
                  stripe_account_id,
                  stripe_details_submitted,
                  stripe_charges_enabled,
                  stripe_payouts_enabled,
                  stripe_onboarding_complete,
                  stripe_requirements_due_count,
                  stripe_account_status_updated_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

        if not user_row or not verify_password(
            password, user_row["password_salt"], user_row["password_hash"]
        ):
            self.send_json(
                {"error": "Email or password is incorrect."},
                status=HTTPStatus.UNAUTHORIZED,
            )
            return

        if str(row_value(user_row, "account_status", "active") or "active") == "suspended":
            self.send_json(
                {"error": "This account is suspended. Contact Eleven Zero PB support."},
                status=HTTPStatus.FORBIDDEN,
            )
            return

        token, csrf_token = self.create_session(user_row["id"])
        self.send_json(
            {
                "ok": True,
                "user": serialize_user(user_row),
                "csrfToken": csrf_token,
            },
            cookie=self.session_cookie(token),
        )

    def handle_password_reset_request(self, body: dict):
        email = normalize_email(str(body.get("email", "")))
        client_key = f"password-reset:{self.client_address[0]}:{email}"
        if not rate_limit_allows(client_key, 5, 3600):
            self.send_json(
                {"error": "Too many reset requests. Please wait and try again."},
                status=HTTPStatus.TOO_MANY_REQUESTS,
            )
            return

        with closing(connect_db()) as connection:
            user = connection.execute(
                "SELECT id, email FROM users WHERE email = ?", (email,)
            ).fetchone()

        if user and transactional_email_is_configured():
            token = create_auth_token(user["id"], "password_reset", lifetime_minutes=60)
            site_url = (SITE_URL or self.current_origin()).rstrip("/")
            action_url = f"{site_url}/auth.html?mode=reset&token={token}"
            try:
                send_account_action_email(
                    user["email"],
                    "Reset your Eleven Zero PB password",
                    "Reset your password",
                    "Use this secure link within one hour to choose a new password for your account.",
                    "Choose a new password",
                    action_url,
                )
            except (OSError, RuntimeError, smtplib.SMTPException):
                pass

        self.send_json(
            {
                "ok": True,
                "message": "If that email has an account, a reset link is on the way.",
            }
        )

    def handle_password_reset_confirm(self, body: dict):
        token = str(body.get("token", "")).strip()
        password = str(body.get("password", ""))
        if len(token) < 24 or len(password) < 8:
            self.send_json(
                {"error": "Use the complete reset link and a password with at least 8 characters."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        salt_hex, digest_hex = hash_password(password)
        with closing(connect_db()) as connection:
            row = connection.execute(
                """
                SELECT id, user_id FROM auth_tokens
                WHERE purpose = 'password_reset' AND token_hash = ? AND used_at IS NULL AND expires_at > ?
                """,
                (token_hash, utc_now()),
            ).fetchone()
            if not row:
                self.send_json(
                    {"error": "That reset link is invalid or expired. Request a new one."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            connection.execute(
                "UPDATE users SET password_salt = ?, password_hash = ? WHERE id = ?",
                (salt_hex, digest_hex, row["user_id"]),
            )
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))
            connection.execute("UPDATE auth_tokens SET used_at = ? WHERE id = ?", (utc_now(), row["id"]))
            connection.commit()

        self.send_json({"ok": True, "message": "Password updated. You can sign in now."})

    def handle_verify_email(self, body: dict):
        token = str(body.get("token", "")).strip()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with closing(connect_db()) as connection:
            row = connection.execute(
                """
                SELECT id, user_id FROM auth_tokens
                WHERE purpose = 'verify_email' AND token_hash = ? AND used_at IS NULL AND expires_at > ?
                """,
                (token_hash, utc_now()),
            ).fetchone()
            if not row:
                self.send_json(
                    {"error": "That verification link is invalid or expired."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            connection.execute(
                "UPDATE users SET email_verified = 1, email_verified_at = ? WHERE id = ?",
                (utc_now(), row["user_id"]),
            )
            connection.execute("UPDATE auth_tokens SET used_at = ? WHERE id = ?", (utc_now(), row["id"]))
            connection.commit()
        self.send_json({"ok": True, "message": "Email verified. Your account is ready."})

    def handle_resend_verification(self, user: dict):
        if user.get("emailVerified"):
            self.send_json({"ok": True, "message": "Your email is already verified."})
            return
        sent = send_verification_email(user["id"], user["email"])
        if not sent:
            self.send_json(
                {"error": "Verification email could not be sent right now. Please try again later."},
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        self.send_json({"ok": True, "message": "A new verification email is on the way."})

    def handle_create_listing(self, user: dict, body: dict):
        try:
            seller_profile = self.fetch_seller_profile(user["id"], force_refresh=True)["sellerProfile"]
        except (RuntimeError, ValueError):
            try:
                seller_profile = self.fetch_seller_profile(user["id"])["sellerProfile"]
            except ValueError:
                seller_profile = stripe_profile_from_row({})

        if not seller_profile["readyForPayouts"] or not seller_profile["connectedAccountId"]:
            self.send_json(
                {
                    "error": (
                        "Finish Stripe payout setup before submitting this paddle for review. "
                        "Your draft is still saved on this device."
                    ),
                    "code": "seller_payouts_required",
                    "actionUrl": "./account.html#seller-payouts",
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        if str(body.get("photoAttestation", "")).strip().lower() not in {"1", "true", "yes", "on"}:
            self.send_json(
                {"error": "Confirm that the photos show the actual paddle you are selling."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        brand = str(body.get("brand", "")).strip()
        model = str(body.get("model", "")).strip()
        color = str(body.get("color", "")).strip()
        thickness_raw = str(body.get("thickness", "")).strip()
        thickness_mm = parse_thickness_mm(thickness_raw) if thickness_raw else None
        category = str(body.get("category", "")).strip().lower() or "control"
        condition = str(body.get("condition", "")).strip()
        location = str(body.get("location", "")).strip()
        notes = str(body.get("notes", "")).strip() or "No extra condition notes added yet."
        images = normalize_listing_image_payload(body.get("images", []))
        price_usd = parse_whole_dollar_amount(body.get("price"))
        shipping_mode = "calculated"
        shipping_flat_usd = parse_whole_dollar_amount(body.get("shippingFlat"))
        shipping_origin_zip_raw = str(body.get("shippingOriginZip", "")).strip()
        shipping_origin_zip = parse_zip_code(shipping_origin_zip_raw)
        shipping_origin_street1 = compact_whitespace(body.get("shippingOriginStreet1", ""))
        shipping_weight_raw = str(body.get("shippingWeightOz", "")).strip()
        shipping_weight_oz = (
            parse_shipping_weight_oz(shipping_weight_raw)
            if shipping_weight_raw
            else DEFAULT_PADDLE_PACKAGE["weight_oz"]
        )
        shipping_length_raw = str(body.get("shippingLengthIn", "")).strip()
        shipping_width_raw = str(body.get("shippingWidthIn", "")).strip()
        shipping_height_raw = str(body.get("shippingHeightIn", "")).strip()
        shipping_length_in = (
            parse_shipping_dimension_in(shipping_length_raw)
            if shipping_length_raw
            else DEFAULT_PADDLE_PACKAGE["length_in"]
        )
        shipping_width_in = (
            parse_shipping_dimension_in(shipping_width_raw)
            if shipping_width_raw
            else DEFAULT_PADDLE_PACKAGE["width_in"]
        )
        shipping_height_in = (
            parse_shipping_dimension_in(shipping_height_raw)
            if shipping_height_raw
            else DEFAULT_PADDLE_PACKAGE["height_in"]
        )
        shipping_note = str(body.get("shippingNote", "")).strip()

        if brand and model:
            paddle_selection = resolve_paddle_selection(brand, model)
            if not paddle_selection:
                if paddle_catalog_key(brand) not in PADDLE_CATALOG_INDEX:
                    catalog_error = "Choose a paddle brand from the Eleven Zero PB catalog."
                else:
                    catalog_error = f"Choose a listed {brand} model from the paddle catalog."
                self.send_json(
                    {"error": catalog_error, "code": "invalid_paddle_catalog_selection"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            brand, model = paddle_selection

        canonical_color = resolve_paddle_color(color)
        if color and not canonical_color:
            self.send_json(
                {
                    "error": "Choose the paddle's primary color from the list.",
                    "code": "invalid_paddle_color_selection",
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        color = canonical_color or ""

        canonical_thickness = resolve_paddle_thickness(thickness_raw)
        if thickness_raw and not canonical_thickness:
            self.send_json(
                {
                    "error": "Choose a paddle thickness from the list.",
                    "code": "invalid_paddle_thickness_selection",
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        thickness_raw = canonical_thickness or ""
        thickness_mm = float(thickness_raw) if thickness_raw else None

        if not all([brand, model, color, category, condition, location]) or price_usd <= 0:
            self.send_json(
                {
                    "error": (
                        "Add the brand, model, color, condition, price, and "
                        "ships-from city before submitting it for review."
                    )
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if category not in {"control", "power", "hybrid"}:
            self.send_json(
                {"error": "Listing category must be control, power, or hybrid."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if shipping_origin_zip_raw and not shipping_origin_zip:
            self.send_json(
                {"error": "Add a valid U.S. ZIP code for where this paddle ships from."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if shipping_weight_raw and shipping_weight_oz is None:
            self.send_json(
                {"error": "Add a realistic packed weight in ounces so shipping stays accurate."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        invalid_dimension_fields = []
        if shipping_length_raw and shipping_length_in is None:
            invalid_dimension_fields.append("length")
        if shipping_width_raw and shipping_width_in is None:
            invalid_dimension_fields.append("width")
        if shipping_height_raw and shipping_height_in is None:
            invalid_dimension_fields.append("height")

        if invalid_dimension_fields:
            dimension_text = ", ".join(invalid_dimension_fields)
            self.send_json(
                {"error": f"Add a realistic packed box {dimension_text} in inches so carrier-ready shipping stays accurate."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if shipping_mode == "calculated" and not shipping_origin_zip:
            self.send_json(
                {"error": "Add the shipping origin ZIP code so buyer shipping can be calculated better."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if shipping_mode == "calculated" and not shipping_origin_street1:
            self.send_json(
                {"error": "Add the street address the paddle will ship from. It stays private and is used only for the prepaid label."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if shipping_mode == "flat" and shipping_flat_usd <= 0:
            self.send_json(
                {"error": "Add the flat shipping amount buyers should pay for this listing."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if shipping_mode == "free":
            shipping_flat_usd = 0

        if not images:
            attempted_images = bool(body.get("images"))
            self.send_json(
                {
                    "error": (
                        "We could not save those photos. Try smaller JPG or PNG images and upload them again."
                        if attempted_images
                        else "Add at least one paddle photo before submitting the listing for review."
                    )
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        with closing(connect_db()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO listings (
                  user_id, brand, model, color, thickness_mm, category, condition, price_usd, location, notes,
                  shipping_mode, shipping_flat_usd, shipping_origin_zip, shipping_origin_street1, shipping_weight_oz,
                  shipping_length_in, shipping_width_in, shipping_height_in, shipping_note,
                  image_data_json, approval_status, reviewed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    brand,
                    model,
                    color,
                    thickness_mm,
                    category,
                    condition,
                    price_usd,
                    location,
                    notes,
                    shipping_mode,
                    shipping_flat_usd,
                    shipping_origin_zip,
                    shipping_origin_street1,
                    shipping_weight_oz,
                    shipping_length_in,
                    shipping_width_in,
                    shipping_height_in,
                    shipping_note,
                    json.dumps(images),
                    "pending",
                    None,
                    utc_now(),
                ),
            )
            connection.commit()

            row = connection.execute(
                """
                SELECT
                  listings.id,
                  listings.user_id,
                  listings.brand,
                  listings.model,
                  listings.color,
                  listings.thickness_mm,
                  listings.category,
                  listings.condition,
                  listings.price_usd,
                  listings.location,
                  listings.notes,
                  listings.shipping_mode,
                  listings.shipping_flat_usd,
                  listings.shipping_origin_zip,
                  listings.shipping_origin_street1,
                  listings.shipping_weight_oz,
                  listings.shipping_length_in,
                  listings.shipping_width_in,
                  listings.shipping_height_in,
                  listings.shipping_note,
                  listings.image_data_json,
                  listings.approval_status,
                  listings.sale_status,
                  listings.reviewed_at,
                  listings.created_at,
                  users.name AS seller_name,
                  users.stripe_account_id,
                  users.stripe_details_submitted,
                  users.stripe_charges_enabled,
                  users.stripe_payouts_enabled,
                  users.stripe_onboarding_complete,
                  users.stripe_requirements_due_count,
                  users.stripe_account_status_updated_at
                FROM listings
                LEFT JOIN users ON users.id = listings.user_id
                WHERE listings.id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()

        self.send_json({"ok": True, "item": serialize_listing_row(row)}, status=HTTPStatus.CREATED)

    def handle_create_trainer(self, user: dict, body: dict):
        name = str(body.get("name", "")).strip()
        location = str(body.get("location", "")).strip()
        format_value = str(body.get("format", "")).strip().lower()
        level = str(body.get("level", "")).strip().lower()
        rate = str(body.get("rate", "")).strip()
        email = normalize_email(str(body.get("email", "")).strip() or user["email"])
        experience = str(body.get("experience", "")).strip()
        availability = str(body.get("availability", "")).strip()
        bio = str(body.get("bio", "")).strip()

        if not all([name, location, format_value, level, rate, email]):
            self.send_json(
                {"error": "Please complete every trainer field before submitting the profile."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if format_value not in {"private", "group", "clinic", "virtual"}:
            self.send_json({"error": "Trainer format is not valid."}, status=HTTPStatus.BAD_REQUEST)
            return

        if level not in {"beginner", "intermediate", "advanced"}:
            self.send_json({"error": "Trainer level is not valid."}, status=HTTPStatus.BAD_REQUEST)
            return

        if not experience:
            experience = "New trainer profile · Account verified"

        if not availability:
            availability = "Reply through Eleven Zero PB"

        if not bio:
            bio = (
                f"{name} joined Eleven Zero PB to offer {format_value} coaching for "
                f"{level} players and start receiving direct intro requests."
            )

        with closing(connect_db()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  verified, experience, bio, availability, joined_at, rating, review_count,
                  approval_status, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0, 0, 'pending', NULL)
                """,
                (
                    user["id"],
                    name,
                    location,
                    format_value,
                    level,
                    rate,
                    email,
                    experience,
                    bio,
                    availability,
                    datetime.now().date().isoformat(),
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM trainers WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()

        self.send_json(
            {
                "ok": True,
                "item": row_to_dict(row),
                "message": "Trainer profile submitted for Eleven Zero PB review.",
            },
            status=HTTPStatus.CREATED,
        )

    def handle_create_directory_court(self, user: dict, body: dict):
        name = str(body.get("name", "")).strip()
        location = str(body.get("location", "")).strip()
        address = str(body.get("address", "")).strip() or location
        access_kind = str(body.get("accessKind", "")).strip().lower()
        surface_kind = str(body.get("surfaceKind", "")).strip().lower()
        access_note = str(body.get("accessNote", "")).strip()
        amenities = str(body.get("amenities", "")).strip()
        description = str(body.get("description", "")).strip()
        website = str(body.get("website", "")).strip()
        court_count_raw = str(body.get("courtCount", "")).strip()

        try:
            lat = float(body.get("lat")) if body.get("lat") not in {None, ""} else None
            lon = float(body.get("lon")) if body.get("lon") not in {None, ""} else None
        except (TypeError, ValueError):
            self.send_json(
                {"error": "Court coordinates were invalid. Try a more specific city or address."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            court_count = int(court_count_raw or "0")
        except ValueError:
            court_count = 0

        if not all([name, location, access_kind, surface_kind, description]) or court_count <= 0:
            self.send_json(
                {"error": "Please complete every required field before submitting the court for review."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if access_kind not in {"free", "paid"}:
            self.send_json(
                {"error": "Court access must be either free or paid."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if surface_kind not in {"indoor", "outdoor"}:
            self.send_json(
                {"error": "Court surface must be indoor or outdoor."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if len(description) < 12:
            self.send_json(
                {"error": "Add a short court description so players understand the setup."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if website and not urlparse(website).scheme:
            website = f"https://{website}"

        with closing(connect_db()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO courts_directory (
                  user_id,
                  name,
                  location,
                  address,
                  access_kind,
                  surface_kind,
                  court_count,
                  access_note,
                  amenities,
                  description,
                  website,
                  affiliate_url,
                  affiliate_label,
                  approval_status,
                  reviewed_at,
                  lat,
                  lon,
                  created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    name,
                    location,
                    address,
                    access_kind,
                    surface_kind,
                    court_count,
                    access_note,
                    amenities,
                    description,
                    website,
                    "",
                    "",
                    "pending",
                    None,
                    lat,
                    lon,
                    utc_now(),
                ),
            )
            connection.commit()
            row = connection.execute(
                """
                SELECT
                  id,
                  user_id,
                  name,
                  location,
                  address,
                  access_kind,
                  surface_kind,
                  court_count,
                  access_note,
                  amenities,
                  description,
                  website,
                  affiliate_url,
                  affiliate_label,
                  approval_status,
                  reviewed_at,
                  lat,
                  lon,
                  created_at
                FROM courts_directory
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()

        self.send_json(
            {
                "ok": True,
                "item": serialize_directory_court_row(row),
                "message": f"Thanks — {name} is now in review and will go live after approval.",
            },
            status=HTTPStatus.CREATED,
        )

    def handle_create_review(self, user: dict, body: dict):
        trainer_id = int(body.get("trainerId") or 0)
        rating = int(body.get("rating") or 0)
        comment = str(body.get("comment", "")).strip()

        if trainer_id <= 0 or rating not in {1, 2, 3, 4, 5} or len(comment) < 12:
            self.send_json(
                {"error": "Please choose a trainer, set a rating, and write a short review."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        with closing(connect_db()) as connection:
            trainer = connection.execute(
                "SELECT id, name, rating, review_count, approval_status FROM trainers WHERE id = ?",
                (trainer_id,),
            ).fetchone()

            if not trainer:
                self.send_json({"error": "Trainer not found."}, status=HTTPStatus.NOT_FOUND)
                return

            if trainer["approval_status"] != "approved":
                self.send_json(
                    {"error": "That trainer profile is still under review."},
                    status=HTTPStatus.CONFLICT,
                )
                return

            existing_review = connection.execute(
                "SELECT id FROM trainer_reviews WHERE trainer_id = ? AND user_id = ?",
                (trainer_id, user["id"]),
            ).fetchone()
            if existing_review:
                self.send_json(
                    {"error": "You already reviewed this trainer."},
                    status=HTTPStatus.CONFLICT,
                )
                return

            new_review_count = trainer["review_count"] + 1
            new_rating = round(
                ((trainer["rating"] * trainer["review_count"]) + rating) / new_review_count, 1
            )

            connection.execute(
                """
                INSERT INTO trainer_reviews (
                  trainer_id, user_id, reviewer_name, rating, comment, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    trainer_id,
                    user["id"],
                    user["name"],
                    rating,
                    comment,
                    utc_now(),
                ),
            )
            connection.execute(
                "UPDATE trainers SET rating = ?, review_count = ? WHERE id = ?",
                (new_rating, new_review_count, trainer_id),
            )
            connection.commit()

        self.send_json(
            {
                "ok": True,
                "message": f"Your review for {trainer['name']} is now live.",
            },
            status=HTTPStatus.CREATED,
        )

    def handle_create_court_report(self, user: dict, body: dict):
        court_id = str(body.get("courtId", "")).strip()
        court_name = str(body.get("courtName", "")).strip()
        court_location = str(body.get("courtLocation", "")).strip()
        condition_rating = int(body.get("conditionRating") or 0)
        busyness_rating = int(body.get("busynessRating") or 0)
        player_level = str(body.get("playerLevel", "")).strip().lower()
        comment = str(body.get("comment", "")).strip()

        if not all([court_id, court_name, court_location, comment]):
            self.send_json(
                {"error": "Choose a court first, then complete every report field."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if condition_rating not in {1, 2, 3, 4, 5}:
            self.send_json(
                {"error": "Court condition must be rated from 1 to 5."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if busyness_rating not in {1, 2, 3, 4}:
            self.send_json(
                {"error": "Court busyness must be set from quiet to packed."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if player_level not in {"beginner", "intermediate", "advanced", "mixed"}:
            self.send_json(
                {"error": "Choose the player level you usually see at that court."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if len(comment) < 12:
            self.send_json(
                {"error": "Write a short note so other players get useful context."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        with closing(connect_db()) as connection:
            connection.execute(
                """
                INSERT INTO court_reports (
                  court_id,
                  court_name,
                  court_location,
                  user_id,
                  reviewer_name,
                  condition_rating,
                  busyness_rating,
                  player_level,
                  comment,
                  created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    court_id,
                    court_name,
                    court_location,
                    user["id"],
                    user["name"],
                    condition_rating,
                    busyness_rating,
                    player_level,
                    comment,
                    utc_now(),
                ),
            )
            connection.commit()

        summary_payload = self.fetch_court_reports(court_id, [])
        self.send_json(
            {
                "ok": True,
                "message": f"Your court report for {court_name} is now live.",
                "summary": summary_payload.get("summary"),
                "items": summary_payload.get("items", []),
            },
            status=HTTPStatus.CREATED,
        )


def run() -> None:
    init_database()
    server = ThreadingHTTPServer((HOST, PORT), ElevenZeroHandler)
    public_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    print(f"Eleven Zero PB is running in {APP_ENV} mode at http://{public_host}:{PORT}")
    if SITE_URL:
        print(f"Configured public URL: {SITE_URL}")
    print(f"Database path: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
