import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import app


class MarketplaceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = app.DB_PATH
        self.original_environment = app.APP_ENV
        self.original_starter_listings = app.ENABLE_STARTER_LISTINGS
        self.original_demo_data = app.ENABLE_DEMO_DATA
        app.DB_PATH = Path(self.temp_dir.name) / "marketplace-test.db"
        app.APP_ENV = "development"
        app.ENABLE_STARTER_LISTINGS = False
        app.ENABLE_DEMO_DATA = False
        app.init_database()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        app.APP_ENV = self.original_environment
        app.ENABLE_STARTER_LISTINGS = self.original_starter_listings
        app.ENABLE_DEMO_DATA = self.original_demo_data
        self.temp_dir.cleanup()

    def create_user(self, email="seller@example.com"):
        with sqlite3.connect(app.DB_PATH) as connection:
            user_id = connection.execute(
                """
                INSERT INTO users (
                  name, email, password_salt, password_hash,
                  email_verified, email_verified_at, created_at
                ) VALUES ('Real Seller', ?, 'salt', 'hash', 1,
                  '2026-07-22T00:00:00Z', '2026-01-15T00:00:00Z')
                """,
                (email,),
            ).lastrowid
            connection.commit()
        return user_id

    def create_listing(self, user_id, model, approval="approved", sale_status="available"):
        with sqlite3.connect(app.DB_PATH) as connection:
            listing_id = connection.execute(
                """
                INSERT INTO listings (
                  user_id, brand, model, category, condition, price_usd,
                  location, notes, image_data_json, approval_status,
                  sale_status, created_at
                ) VALUES (?, 'JOOLA', ?, 'control', 'Excellent', 150,
                  'Arlington, VA', 'Clean paddle', ?, ?, ?, '2026-07-22T00:00:00Z')
                """,
                (
                    user_id,
                    model,
                    json.dumps(["data:image/png;base64,aGVsbG8="]),
                    approval,
                    sale_status,
                ),
            ).lastrowid
            connection.commit()
        return listing_id

    def test_public_catalog_only_returns_approved_real_seller_listings(self):
        seller_id = self.create_user()
        visible_id = self.create_listing(seller_id, "Visible")
        self.create_listing(None, "Anonymous")
        self.create_listing(seller_id, "Pending", approval="pending")
        sold_id = self.create_listing(seller_id, "Sold", sale_status="sold")

        items = app.ElevenZeroHandler.fetch_listings(None)

        self.assertEqual([item["id"] for item in items], [visible_id, sold_id])
        self.assertEqual(items[0]["seller_name"], "Real Seller")
        self.assertEqual(items[0]["images"], [f"/api/listings/{visible_id}/images/0"])

    def test_production_startup_quarantines_anonymous_content(self):
        anonymous_listing_id = self.create_listing(None, "Anonymous")
        with sqlite3.connect(app.DB_PATH) as connection:
            anonymous_trainer_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, approval_status
                ) VALUES (NULL, 'Demo Coach', 'Virginia', 'private', 'beginner',
                  '$50', 'coach@example.com', '5 years', 'Bio', 'Weekends',
                  '2026-01-01', 'approved')
                """
            ).lastrowid
            anonymous_court_id = connection.execute(
                """
                INSERT INTO courts_directory (
                  user_id, name, location, address, access_kind, surface_kind,
                  court_count, description, approval_status, created_at
                ) VALUES (NULL, 'Demo Courts', 'Virginia', '123 Main Street',
                  'free', 'outdoor', 4, 'Community pickleball courts.',
                  'approved', '2026-01-01T00:00:00Z')
                """
            ).lastrowid
            connection.commit()

        app.APP_ENV = "production"
        app.init_database()

        with sqlite3.connect(app.DB_PATH) as connection:
            listing_status = connection.execute(
                "SELECT approval_status FROM listings WHERE id = ?", (anonymous_listing_id,)
            ).fetchone()[0]
            trainer_status = connection.execute(
                "SELECT approval_status FROM trainers WHERE id = ?", (anonymous_trainer_id,)
            ).fetchone()[0]
            court_status = connection.execute(
                "SELECT approval_status FROM courts_directory WHERE id = ?", (anonymous_court_id,)
            ).fetchone()[0]

        self.assertEqual(listing_status, "rejected")
        self.assertEqual(trainer_status, "rejected")
        self.assertEqual(court_status, "rejected")

    def test_unverified_accounts_cannot_publish_content(self):
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        allowed = app.ElevenZeroHandler.require_verified_user(
            StubHandler(), {"id": 7, "emailVerified": False}
        )

        self.assertFalse(allowed)
        self.assertEqual(captured["status"], app.HTTPStatus.FORBIDDEN)
        self.assertEqual(captured["payload"]["code"], "email_verification_required")


if __name__ == "__main__":
    unittest.main()
