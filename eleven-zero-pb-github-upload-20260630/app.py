from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


APP_ROOT = Path(__file__).resolve().parent


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
SITE_URL = os.getenv("SITE_URL", "").strip()
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "").strip()
PRIMARY_OWNER_EMAIL = os.getenv("PRIMARY_OWNER_EMAIL", "11zeropb@gmail.com").strip()
ADMIN_EMAILS_RAW = os.getenv("ADMIN_EMAILS", "").strip()
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "").strip()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
GOOGLE_MAPS_MAP_ID = os.getenv("GOOGLE_MAPS_MAP_ID", "").strip()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
STRIPE_COUNTRY = os.getenv("STRIPE_COUNTRY", "US").strip().upper() or "US"
STRIPE_PLATFORM_FEE_PERCENT = float(os.getenv("PLATFORM_FEE_PERCENT", "8.5"))
STRIPE_API_BASE = "https://api.stripe.com/v1"


def cache_control_for_path(path: str) -> str:
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
            "img-src 'self' data: https://tile.openstreetmap.org https://*.googleapis.com https://*.gstatic.com https://*.googleusercontent.com",
            "script-src 'self' https://www.googletagmanager.com https://maps.googleapis.com",
            "style-src 'self' 'unsafe-inline'",
            "connect-src 'self' https://www.google-analytics.com https://region1.google-analytics.com https://nominatim.openstreetmap.org https://overpass-api.de https://www.openstreetmap.org https://api.stripe.com https://*.googleapis.com https://*.gstatic.com https://*.google.com",
        ]
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
}

DIRECTORY_SURFACE_LABELS = {
    "indoor": "Indoor",
    "outdoor": "Outdoor",
}


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
    website = (row["website"] or "").strip()
    access_note = (row["access_note"] or "").strip()
    amenities = (row["amenities"] or "").strip()

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
        }
    )
    return payload


def serialize_admin_trainer_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

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
    }

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
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
              image_data_json TEXT NOT NULL DEFAULT '[]',
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
              review_count INTEGER NOT NULL DEFAULT 0
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

        add_column_if_missing(connection, "users", "stripe_account_id", "TEXT")
        add_column_if_missing(connection, "users", "stripe_details_submitted", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_charges_enabled", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_payouts_enabled", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_onboarding_complete", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_requirements_due_count", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "users", "stripe_account_status_updated_at", "TEXT")
        add_column_if_missing(connection, "listings", "color", "TEXT NOT NULL DEFAULT ''")
        add_column_if_missing(connection, "listings", "thickness_mm", "REAL")
        add_column_if_missing(connection, "listings", "image_data_json", "TEXT NOT NULL DEFAULT '[]'")
        add_column_if_missing(connection, "courts_directory", "address", "TEXT NOT NULL DEFAULT ''")

        listing_count = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        trainer_count = connection.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
        review_count = connection.execute("SELECT COUNT(*) FROM trainer_reviews").fetchone()[0]
        court_report_count = connection.execute("SELECT COUNT(*) FROM court_reports").fetchone()[0]

        if ENABLE_DEMO_DATA and not listing_count:
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
        if len(image) > 1_600_000:
            continue
        if image in images:
            continue

        images.append(image)
        if len(images) >= 4:
            break

    return images


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


def listing_checkout_state_from_row(row: sqlite3.Row | dict | None) -> dict:
    row = row or {}
    seller_user_id = row.get("user_id") if isinstance(row, dict) else row["user_id"]
    seller_profile = stripe_profile_from_row(row)
    price_usd = int(row.get("price_usd", 0) if isinstance(row, dict) else row["price_usd"] or 0)

    if not stripe_is_configured():
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
        "available": bool(seller_user_id and seller_profile["readyForPayouts"] and stripe_is_configured()),
        "reason": reason,
    }


def serialize_listing_row(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None

    checkout_state = listing_checkout_state_from_row(row)
    color = (row.get("color", "") if isinstance(row, dict) else row["color"] or "").strip()
    thickness_mm = row.get("thickness_mm") if isinstance(row, dict) else row["thickness_mm"]
    images = normalize_listing_image_payload(
        row.get("image_data_json", "[]") if isinstance(row, dict) else row["image_data_json"]
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
        "seller_name": row["seller_name"],
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
        "stripeConfigured": stripe_is_configured(),
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
                  users.created_at,
                  users.stripe_account_id,
                  users.stripe_details_submitted,
                  users.stripe_charges_enabled,
                  users.stripe_payouts_enabled,
                  users.stripe_onboarding_complete,
                  users.stripe_requirements_due_count,
                  users.stripe_account_status_updated_at,
                  sessions.token,
                  sessions.created_at
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()

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

    def session_cookie(self, token: str) -> str:
        secure_flag = "; Secure" if SESSION_COOKIE_SECURE else ""
        return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; Max-Age=2592000; SameSite=Lax{secure_flag}"

    def clear_session_cookie(self) -> str:
        secure_flag = "; Secure" if SESSION_COOKIE_SECURE else ""
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; Max-Age=0; SameSite=Lax{secure_flag}"

    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        with closing(connect_db()) as connection:
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            connection.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, user_id, utc_now()),
            )
            connection.commit()
        return token

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
        return f"{self.current_origin()}/index.html?checkout=success&session_id={{CHECKOUT_SESSION_ID}}#shop"

    def checkout_cancel_url(self) -> str:
        return f"{self.current_origin()}/index.html?checkout=cancel#shop"

    def handle_api_get(self, parsed):
        if parsed.path == "/api/health":
            self.send_json({"ok": True, "time": utc_now(), "environment": APP_ENV})
            return

        if parsed.path == "/api/site-config":
            self.send_json(site_config_payload())
            return

        if parsed.path == "/api/auth/session":
            user = self.current_user()
            self.send_json({"authenticated": bool(user), "user": user})
            return

        if parsed.path.startswith("/api/listings/"):
            listing_id = parsed.path.rsplit("/", 1)[-1].strip()
            if not listing_id.isdigit():
                self.send_json({"error": "That listing could not be found."}, status=HTTPStatus.NOT_FOUND)
                return

            item = self.fetch_listing_by_id(int(listing_id))
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

        if parsed.path == "/api/auth/signout":
            self.destroy_session()
            self.send_json({"ok": True}, cookie=self.clear_session_cookie())
            return

        if parsed.path == "/api/listings":
            user = self.require_user()
            if not user:
                return
            self.handle_create_listing(user, body)
            return

        if parsed.path == "/api/trainers":
            user = self.require_user()
            if not user:
                return
            self.handle_create_trainer(user, body)
            return

        if parsed.path == "/api/courts-directory":
            user = self.require_user()
            if not user:
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

        if parsed.path == "/api/checkout/create-session":
            user = self.require_user()
            if not user:
                return
            self.handle_create_checkout_session(user, body)
            return

        if parsed.path == "/api/trainer-reviews":
            user = self.require_user()
            if not user:
                return
            self.handle_create_review(user, body)
            return

        if parsed.path == "/api/court-reports":
            user = self.require_user()
            if not user:
                return
            self.handle_create_court_report(user, body)
            return

        self.send_json({"error": "Unknown API route."}, status=HTTPStatus.NOT_FOUND)

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
                  listings.image_data_json,
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
                ORDER BY listings.created_at DESC
                """
            ).fetchall()

        return [serialize_listing_row(row) for row in rows]

    def fetch_listing_by_id(self, listing_id: int) -> dict | None:
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
                  listings.image_data_json,
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
                  review_count
                FROM trainers
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
                  lat,
                  lon,
                  created_at
                FROM courts_directory
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
        """
        params: tuple = ()

        if trainer_id:
            query += " WHERE trainer_reviews.trainer_id = ?"
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
                  listings.image_data_json,
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

        platform_fee_cents = min(
            total_cents - 1,
            max(0, int(round(total_cents * STRIPE_PLATFORM_FEE_PERCENT / 100))),
        )

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
            "payment_intent_data[application_fee_amount]": str(platform_fee_cents),
            "payment_intent_data[transfer_data][destination]": seller_profile["connectedAccountId"],
            "metadata[platform]": "Eleven Zero PB",
            "metadata[listing_id]": str(listing["id"]),
            "metadata[buyer_user_id]": str(user["id"]),
            "metadata[seller_user_id]": str(seller_user_id),
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
                  platform_fee_cents,
                  stripe_payment_status,
                  stripe_session_status,
                  status,
                  created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    listing["id"],
                    user["id"],
                    seller_user_id,
                    session_id,
                    str(session.get("payment_intent") or ""),
                    total_cents,
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
                },
            },
            status=HTTPStatus.CREATED,
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
                    "platformFeeCents": order_row["platform_fee_cents"],
                },
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
                SELECT brand, model, category, condition, price_usd, location, created_at
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
        }

    def build_admin_dashboard(self) -> dict:
        with closing(connect_db()) as connection:
            user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            listing_count = connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            court_count = connection.execute("SELECT COUNT(*) FROM courts_directory").fetchone()[0]
            trainer_count = connection.execute("SELECT COUNT(*) FROM trainers").fetchone()[0]
            trainer_review_count = connection.execute("SELECT COUNT(*) FROM trainer_reviews").fetchone()[0]
            court_report_count = connection.execute("SELECT COUNT(*) FROM court_reports").fetchone()[0]

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
                  listings.image_data_json,
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
                  courts_directory.lat,
                  courts_directory.lon,
                  courts_directory.created_at,
                  users.name AS owner_name,
                  users.email AS owner_email
                FROM courts_directory
                LEFT JOIN users ON users.id = courts_directory.user_id
                ORDER BY courts_directory.created_at DESC, courts_directory.id DESC
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

        return {
            "stats": {
                "users": user_count,
                "listings": listing_count,
                "courts": court_count,
                "trainers": trainer_count,
                "trainerReviews": trainer_review_count,
                "courtReports": court_report_count,
            },
            "listings": [serialize_admin_listing_row(row) for row in listings],
            "courts": [serialize_admin_court_row(row) for row in courts],
            "trainers": [serialize_admin_trainer_row(row) for row in trainers],
            "trainerReviews": [serialize_admin_trainer_review_row(row) for row in trainer_reviews],
            "courtReports": [serialize_admin_court_report_row(row) for row in court_reports],
        }

    def handle_admin_listing_update(self, body: dict):
        listing_id = int(body.get("id") or 0)
        brand = str(body.get("brand", "")).strip()
        model = str(body.get("model", "")).strip()
        color = str(body.get("color", "")).strip()
        thickness_mm = parse_thickness_mm(body.get("thickness"))
        category = str(body.get("category", "")).strip().lower()
        condition = str(body.get("condition", "")).strip()
        location = str(body.get("location", "")).strip()
        notes = str(body.get("notes", "")).strip()
        price_raw = str(body.get("price", "")).strip()
        digits = "".join(ch for ch in price_raw if ch.isdigit())
        price_usd = int(digits) if digits else 0

        if listing_id <= 0:
            self.send_json({"error": "Choose a valid listing to update."}, status=HTTPStatus.BAD_REQUEST)
            return

        if not all([brand, model, color, category, condition, location, notes]) or price_usd <= 0:
            self.send_json({"error": "Please complete every listing field before saving."}, status=HTTPStatus.BAD_REQUEST)
            return

        if category not in {"control", "power", "hybrid"}:
            self.send_json({"error": "Listing category must be control, power, or hybrid."}, status=HTTPStatus.BAD_REQUEST)
            return

        if thickness_mm is None:
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
                  website = ?
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
                    court_id,
                ),
            )
            connection.commit()

        if cursor.rowcount <= 0:
            self.send_json({"error": "Court not found."}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, "message": f"{name} was updated in the courts directory."})

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

        if len(name) < 2 or "@" not in email or len(password) < 8:
            self.send_json(
                {"error": "Use a real name, a valid email, and a password with at least 8 characters."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        salt_hex, digest_hex = hash_password(password)

        try:
            with closing(connect_db()) as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (name, email, password_salt, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, email, salt_hex, digest_hex, utc_now()),
                )
                user_row = connection.execute(
                    """
                    SELECT
                      id,
                      name,
                      email,
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

        token = self.create_session(user_id)
        self.send_json(
            {"ok": True, "user": serialize_user(user_row)},
            status=HTTPStatus.CREATED,
            cookie=self.session_cookie(token),
        )

    def handle_signin(self, body: dict):
        email = normalize_email(str(body.get("email", "")))
        password = str(body.get("password", ""))

        with closing(connect_db()) as connection:
            user_row = connection.execute(
                """
                SELECT
                  id,
                  name,
                  email,
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

        token = self.create_session(user_row["id"])
        self.send_json(
            {
                "ok": True,
                "user": serialize_user(user_row),
            },
            cookie=self.session_cookie(token),
        )

    def handle_create_listing(self, user: dict, body: dict):
        brand = str(body.get("brand", "")).strip()
        model = str(body.get("model", "")).strip()
        color = str(body.get("color", "")).strip()
        thickness_mm = parse_thickness_mm(body.get("thickness"))
        category = str(body.get("category", "")).strip().lower()
        condition = str(body.get("condition", "")).strip()
        location = str(body.get("location", "")).strip()
        notes = str(body.get("notes", "")).strip()
        images = normalize_listing_image_payload(body.get("images", []))
        price_raw = str(body.get("price", "")).strip()

        digits = "".join(ch for ch in price_raw if ch.isdigit())
        price_usd = int(digits) if digits else 0

        if not all([brand, model, color, category, condition, location, notes]) or price_usd <= 0:
            self.send_json(
                {"error": "Please complete every listing field before publishing."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if thickness_mm is None:
            self.send_json(
                {"error": "Add the paddle thickness in millimeters so buyers can filter properly."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if category not in {"control", "power", "hybrid"}:
            self.send_json(
                {"error": "Listing category must be control, power, or hybrid."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if not images:
            self.send_json(
                {"error": "Add at least one paddle photo before publishing the listing."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        with closing(connect_db()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO listings (
                  user_id, brand, model, color, thickness_mm, category, condition, price_usd, location, notes, image_data_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(images),
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
                  listings.image_data_json,
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
                {"error": "Please complete every trainer field before publishing the profile."},
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
                  verified, experience, bio, availability, joined_at, rating, review_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0, 0)
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

        self.send_json({"ok": True, "item": row_to_dict(row)}, status=HTTPStatus.CREATED)

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
                {"error": "Please complete every court field before publishing it."},
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
                  lat,
                  lon,
                  created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                "message": f"{name} is now live in the courts directory.",
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
                "SELECT id, name, rating, review_count FROM trainers WHERE id = ?",
                (trainer_id,),
            ).fetchone()

            if not trainer:
                self.send_json({"error": "Trainer not found."}, status=HTTPStatus.NOT_FOUND)
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
