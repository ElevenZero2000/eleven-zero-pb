import base64
import json
import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import app
from PIL import Image


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

    def trainer_image_data(self, width=1_200, height=800, image_format="PNG"):
        image = Image.new("RGB", (width, height), (18, 104, 72))
        output = BytesIO()
        image.save(output, format=image_format)
        mime_type = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }[image_format]
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def trainer_payload(self, **overrides):
        payload = {
            "name": "Eleven Zero Demo Coach",
            "location": "Arlington, VA",
            "format": "private",
            "level": "beginner",
            "rate": "$75/hr",
            "email": "trainer@example.com",
            "experience": "PPR-certified coach",
            "availability": "Weekday evenings",
            "bio": "Demo profile for platform testing and trainer flow review.",
            "trainerImage": self.trainer_image_data(),
        }
        payload.update(overrides)
        return payload

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

    def test_admin_live_paddle_count_excludes_sold_listings(self):
        seller_id = self.create_user()
        self.create_listing(seller_id, "Available")
        self.create_listing(seller_id, "Sold", sale_status="sold")
        self.create_listing(seller_id, "Pending", approval="pending")

        dashboard = app.ElevenZeroHandler.build_admin_dashboard(object())

        self.assertEqual(dashboard["stats"]["listingApproved"], 1)
        self.assertEqual(dashboard["stats"]["listingPending"], 1)
        self.assertEqual(len(dashboard["listings"]), 3)

    def test_seller_can_mark_only_own_paid_pending_listing_sold(self):
        seller_id = self.create_user("paid-seller@example.com")
        buyer_id = self.create_user("paid-buyer@example.com")
        listing_id = self.create_listing(
            seller_id,
            "Paid Pending",
            sale_status="pending",
        )
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                """
                INSERT INTO orders (
                  listing_id, buyer_user_id, seller_user_id,
                  stripe_checkout_session_id, amount_total_cents,
                  shipping_amount_cents, platform_fee_cents,
                  stripe_payment_status, stripe_session_status, status, created_at
                ) VALUES (?, ?, ?, 'cs_test_mark_sold', 16000, 1000, 1275,
                  'paid', 'complete', 'paid', '2026-07-22T00:00:00Z')
                """,
                (listing_id, buyer_id, seller_id),
            )
            connection.commit()

        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_owner_mark_listing_sold(
            StubHandler(),
            {"id": seller_id},
            {"id": listing_id},
        )

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["saleStatus"], "sold")
        with sqlite3.connect(app.DB_PATH) as connection:
            sale_status = connection.execute(
                "SELECT sale_status FROM listings WHERE id = ?",
                (listing_id,),
            ).fetchone()[0]
        self.assertEqual(sale_status, "sold")

    def test_other_seller_cannot_mark_listing_sold(self):
        seller_id = self.create_user("owner-seller@example.com")
        other_seller_id = self.create_user("other-seller@example.com")
        listing_id = self.create_listing(
            seller_id,
            "Protected Pending",
            sale_status="pending",
        )
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_owner_mark_listing_sold(
            StubHandler(),
            {"id": other_seller_id},
            {"id": listing_id},
        )

        self.assertEqual(captured["status"], app.HTTPStatus.FORBIDDEN)
        with sqlite3.connect(app.DB_PATH) as connection:
            sale_status = connection.execute(
                "SELECT sale_status FROM listings WHERE id = ?",
                (listing_id,),
            ).fetchone()[0]
        self.assertEqual(sale_status, "pending")

    def test_account_profile_settings_queue_name_and_photo_for_review(self):
        user_id = self.create_user()
        captured = {}
        png_payload = b"\x89PNG\r\n\x1a\n" + b"profile-photo"
        profile_image = "data:image/png;base64," + base64.b64encode(png_payload).decode("ascii")

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_update_profile(
            StubHandler(),
            {"id": user_id},
            {"name": "Santiago Player", "profileImage": profile_image},
        )

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["user"]["name"], "Real Seller")
        self.assertEqual(captured["payload"]["user"]["profileReviewStatus"], "pending")
        self.assertEqual(captured["payload"]["user"]["profilePendingName"], "Santiago Player")
        self.assertTrue(
            captured["payload"]["user"]["profilePendingImageUrl"].startswith(
                "/api/account/profile-pending-image?v="
            )
        )
        with sqlite3.connect(app.DB_PATH) as connection:
            row = connection.execute(
                """
                SELECT
                  name,
                  profile_image_data,
                  profile_pending_name,
                  profile_pending_image_data,
                  profile_pending_image_action,
                  profile_review_status
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
        self.assertEqual(row[0], "Real Seller")
        self.assertEqual(row[1], "")
        self.assertEqual(row[2], "Santiago Player")
        self.assertEqual(row[3], profile_image)
        self.assertEqual(row[4], "replace")
        self.assertEqual(row[5], "pending")

    def test_admin_can_approve_pending_profile_without_exposing_it_early(self):
        user_id = self.create_user("review@example.com")
        captured = {}
        png_payload = b"\x89PNG\r\n\x1a\n" + b"review-photo"
        profile_image = "data:image/png;base64," + base64.b64encode(png_payload).decode("ascii")

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        handler = StubHandler()
        app.ElevenZeroHandler.handle_update_profile(
            handler,
            {"id": user_id},
            {"name": "Approved Player", "profileImage": profile_image},
        )
        app.ElevenZeroHandler.handle_admin_profile_review(
            handler,
            {"id": 999},
            {"id": user_id, "action": "approve"},
        )

        self.assertEqual(captured["status"], 200)
        with sqlite3.connect(app.DB_PATH) as connection:
            row = connection.execute(
                """
                SELECT
                  name,
                  profile_image_data,
                  profile_pending_name,
                  profile_review_status,
                  profile_image_updated_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
        self.assertEqual(row[0], "Approved Player")
        self.assertEqual(row[1], profile_image)
        self.assertIsNone(row[2])
        self.assertEqual(row[3], "approved")
        self.assertTrue(row[4])

    def test_profile_name_profanity_is_rejected_before_review(self):
        user_id = self.create_user("clean@example.com")
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_update_profile(
            StubHandler(),
            {"id": user_id},
            {"name": "Sh1t Player"},
        )

        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("Profanity", captured["payload"]["error"])

    def test_admin_suspension_invalidates_member_sessions(self):
        user_id = self.create_user("suspend@example.com")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                "INSERT INTO sessions (token, user_id, csrf_token, created_at) VALUES ('session-token', ?, 'csrf', ?)",
                (user_id, app.utc_now()),
            )
            connection.commit()

        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_admin_profile_review(
            StubHandler(),
            {"id": 999},
            {"id": user_id, "action": "suspend"},
        )

        with sqlite3.connect(app.DB_PATH) as connection:
            status = connection.execute(
                "SELECT account_status FROM users WHERE id = ?", (user_id,)
            ).fetchone()[0]
            session_count = connection.execute(
                "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
        self.assertEqual(status, "suspended")
        self.assertEqual(session_count, 0)

    def test_court_report_form_has_an_explicit_court_picker(self):
        html = (Path(__file__).parent / "courts.html").read_text(encoding="utf-8")
        javascript = (Path(__file__).parent / "courts.js").read_text(encoding="utf-8")
        self.assertIn("data-court-report-court", html)
        self.assertIn('name="comment"', html)
        self.assertIn('minlength="12"', html)
        self.assertIn("syncCourtReportCourtOptions", javascript)

    def test_court_report_missing_note_does_not_blame_court_selection(self):
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_court_report(
            StubHandler(),
            {"id": 1},
            {
                "courtId": "directory-1",
                "courtName": "Wakefield Park",
                "courtLocation": "Annandale, VA",
                "conditionRating": 3,
                "busynessRating": 2,
                "playerLevel": "intermediate",
                "comment": "",
            },
        )

        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("short note", captured["payload"]["error"])
        self.assertNotIn("Choose a court", captured["payload"]["error"])

    def test_google_places_browser_search_uses_javascript_place_field_names(self):
        javascript = (Path(__file__).parent / "courts.js").read_text(encoding="utf-8")
        self.assertIn('"googleMapsURI"', javascript)
        self.assertIn('"websiteURI"', javascript)
        self.assertIn("place?.googleMapsURI || place?.googleMapsUri", javascript)
        self.assertIn("place?.websiteURI || place?.websiteUri", javascript)

    def test_account_profile_settings_reject_unsupported_image(self):
        user_id = self.create_user("second@example.com")
        captured = {}
        svg_payload = base64.b64encode(b"<svg></svg>").decode("ascii")

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_update_profile(
            StubHandler(),
            {"id": user_id},
            {"name": "Second Player", "profileImage": f"data:image/svg+xml;base64,{svg_payload}"},
        )

        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("JPG, PNG, or WebP", captured["payload"]["error"])

    def test_new_trainer_requires_exactly_one_landscape_image(self):
        user_id = self.create_user("trainer-required@example.com")
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_trainer(
            StubHandler(),
            {"id": user_id, "email": "trainer-required@example.com"},
            self.trainer_payload(trainerImage=None),
        )
        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("landscape trainer photo", captured["payload"]["error"])

        app.ElevenZeroHandler.handle_create_trainer(
            StubHandler(),
            {"id": user_id, "email": "trainer-required@example.com"},
            self.trainer_payload(trainerImage=[self.trainer_image_data()]),
        )
        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("exactly one", captured["payload"]["error"])

        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_count = connection.execute(
                "SELECT COUNT(*) FROM trainers WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
        self.assertEqual(trainer_count, 0)

    def test_new_trainer_rejects_portrait_image(self):
        user_id = self.create_user("trainer-portrait@example.com")
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_trainer(
            StubHandler(),
            {"id": user_id, "email": "trainer-portrait@example.com"},
            self.trainer_payload(
                trainerImage=self.trainer_image_data(width=600, height=900)
            ),
        )

        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("wider than it is tall", captured["payload"]["error"])

    def test_new_trainer_stores_normalized_image_without_base64_leak(self):
        user_id = self.create_user("trainer-valid@example.com")
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_trainer(
            StubHandler(),
            {"id": user_id, "email": "trainer-valid@example.com"},
            self.trainer_payload(),
        )

        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)
        item = captured["payload"]["item"]
        self.assertTrue(item["imageUrl"].startswith("/api/trainers/"))
        self.assertNotIn("image_data", item)
        self.assertNotIn("data:image", json.dumps(captured["payload"]))
        self.assertEqual(item["approval_status"], "pending")

        with sqlite3.connect(app.DB_PATH) as connection:
            row = connection.execute(
                """
                SELECT image_data, image_updated_at, approval_status
                FROM trainers
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        self.assertTrue(row[0].startswith("data:image/jpeg;base64,"))
        self.assertTrue(row[1])
        self.assertEqual(row[2], "pending")

        mime_type, normalized_payload = app.decode_trainer_image_data(row[0])
        self.assertEqual(mime_type, "image/jpeg")
        with Image.open(BytesIO(normalized_payload)) as normalized:
            self.assertGreater(normalized.width, normalized.height)
            self.assertNotIn("exif", normalized.info)

    def test_trainer_image_access_is_limited_until_approval(self):
        owner_id = self.create_user("trainer-owner@example.com")
        other_id = self.create_user("trainer-other@example.com")
        image_data = app.normalize_trainer_landscape_image_data(
            self.trainer_image_data()
        )
        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, image_data,
                  image_updated_at, approval_status
                ) VALUES (?, 'Demo Coach', 'Arlington, VA', 'private',
                  'beginner', '$75/hr', 'trainer-owner@example.com',
                  'Five years', 'Demo biography', 'Evenings', '2026-07-23',
                  ?, '2026-07-23T12:00:00Z', 'pending')
                """,
                (owner_id, image_data),
            ).lastrowid
            connection.commit()

        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

            def send_bytes(self, payload, content_type, status=200):
                captured["bytes"] = payload
                captured["content_type"] = content_type
                captured["status"] = status

        handler = StubHandler()
        app.ElevenZeroHandler.handle_trainer_image(handler, trainer_id, None)
        self.assertEqual(captured["status"], app.HTTPStatus.NOT_FOUND)

        app.ElevenZeroHandler.handle_trainer_image(
            handler, trainer_id, {"id": other_id, "isAdmin": False}
        )
        self.assertEqual(captured["status"], app.HTTPStatus.NOT_FOUND)

        app.ElevenZeroHandler.handle_trainer_image(
            handler, trainer_id, {"id": owner_id, "isAdmin": False}
        )
        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["content_type"], "image/jpeg")
        self.assertTrue(captured["bytes"].startswith(b"\xff\xd8\xff"))

        app.ElevenZeroHandler.handle_trainer_image(
            handler, trainer_id, {"id": 999, "isAdmin": True}
        )
        self.assertEqual(captured["status"], 200)

        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                "UPDATE trainers SET approval_status = 'approved' WHERE id = ?",
                (trainer_id,),
            )
            connection.commit()
        app.ElevenZeroHandler.handle_trainer_image(handler, trainer_id, None)
        self.assertEqual(captured["status"], 200)

    def test_owner_image_replacement_returns_entire_profile_to_review(self):
        owner_id = self.create_user("trainer-replace@example.com")
        original_image = app.normalize_trainer_landscape_image_data(
            self.trainer_image_data(width=1_000, height=700)
        )
        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, image_data,
                  image_updated_at, approval_status, reviewed_at
                ) VALUES (?, 'Approved Coach', 'Arlington, VA', 'private',
                  'beginner', '$75/hr', 'trainer-replace@example.com',
                  'Five years', 'Demo biography', 'Evenings', '2026-07-23',
                  ?, '2026-07-23T12:00:00Z', 'approved',
                  '2026-07-23T12:05:00Z')
                """,
                (owner_id, original_image),
            ).lastrowid
            connection.commit()

        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_replace_trainer_image(
            StubHandler(),
            {"id": owner_id},
            {
                "id": trainer_id,
                "trainerImage": self.trainer_image_data(width=1_400, height=900),
            },
        )

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["item"]["approval_status"], "pending")
        self.assertNotIn("data:image", json.dumps(captured["payload"]))
        with sqlite3.connect(app.DB_PATH) as connection:
            row = connection.execute(
                """
                SELECT approval_status, reviewed_at, image_data
                FROM trainers
                WHERE id = ?
                """,
                (trainer_id,),
            ).fetchone()
        self.assertEqual(row[0], "pending")
        self.assertIsNone(row[1])
        self.assertNotEqual(row[2], original_image)

    def test_admin_cannot_approve_pending_image_less_trainer_but_legacy_live_survives(self):
        owner_id = self.create_user("trainer-legacy@example.com")
        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, approval_status
                ) VALUES (?, 'Legacy Coach', 'Arlington, VA', 'private',
                  'beginner', '$75/hr', 'trainer-legacy@example.com',
                  'Five years', 'Legacy biography', 'Evenings', '2026-07-23',
                  'pending')
                """,
                (owner_id,),
            ).lastrowid
            connection.commit()

        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        handler = StubHandler()
        app.ElevenZeroHandler.handle_admin_trainer_review(
            handler, {"id": trainer_id, "status": "approved"}
        )
        self.assertEqual(captured["status"], app.HTTPStatus.CONFLICT)
        self.assertIn("landscape trainer photo", captured["payload"]["error"])

        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                "UPDATE trainers SET approval_status = 'approved' WHERE id = ?",
                (trainer_id,),
            )
            connection.commit()
        app.ElevenZeroHandler.handle_admin_trainer_review(
            handler, {"id": trainer_id, "status": "approved"}
        )
        self.assertEqual(captured["status"], 200)
        public_items = app.ElevenZeroHandler.fetch_trainers(None)
        self.assertEqual(public_items[0]["id"], trainer_id)
        self.assertEqual(public_items[0]["imageUrl"], "")

    def test_admin_dashboard_exposes_trainer_image_url_without_raw_image(self):
        owner_id = self.create_user("trainer-admin-preview@example.com")
        image_data = app.normalize_trainer_landscape_image_data(
            self.trainer_image_data()
        )
        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, image_data,
                  image_updated_at, approval_status
                ) VALUES (?, 'Pending Coach', 'Arlington, VA', 'private',
                  'beginner', '$75/hr', 'trainer-admin-preview@example.com',
                  'Five years', 'Pending biography', 'Evenings', '2026-07-23',
                  ?, '2026-07-23T12:00:00Z', 'pending')
                """,
                (owner_id, image_data),
            ).lastrowid
            connection.commit()

        dashboard = app.ElevenZeroHandler.build_admin_dashboard(object())
        item = next(
            trainer for trainer in dashboard["trainers"] if trainer["id"] == trainer_id
        )
        self.assertTrue(
            item["imageUrl"].startswith(f"/api/trainers/{trainer_id}/image?v=")
        )
        self.assertNotIn("image_data", item)
        self.assertNotIn("data:image", json.dumps(item))

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

    def test_paddle_catalog_has_broad_brand_and_model_coverage(self):
        payload = app.paddle_catalog_payload()

        self.assertGreaterEqual(payload["brandCount"], 60)
        self.assertGreaterEqual(payload["modelCount"], 700)
        self.assertIn("JOOLA", [entry["name"] for entry in payload["brands"]])
        self.assertEqual(
            app.resolve_paddle_selection("joola", "Pro V Perseus"),
            ("JOOLA", "Pro V Perseus"),
        )
        self.assertGreaterEqual(payload["colorCount"], 12)
        self.assertGreaterEqual(payload["thicknessCount"], 12)
        self.assertEqual(app.resolve_paddle_color("black"), "Black")
        self.assertEqual(app.resolve_paddle_thickness("16.0"), "16")

    def test_listing_submission_rejects_invented_brand_and_model(self):
        captured = {}

        class StubHandler:
            def fetch_seller_profile(self, _user_id, force_refresh=False):
                return {
                    "sellerProfile": {
                        "readyForPayouts": True,
                        "connectedAccountId": "acct_ready",
                    }
                }

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_listing(
            StubHandler(),
            {"id": 7},
            {
                "photoAttestation": "1",
                "brand": "Totally Invented Paddles",
                "model": "Random Words 9000",
            },
        )

        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertEqual(captured["payload"]["code"], "invalid_paddle_catalog_selection")

    def test_listing_submission_rejects_unlisted_color(self):
        captured = {}

        class StubHandler:
            def fetch_seller_profile(self, _user_id, force_refresh=False):
                return {
                    "sellerProfile": {
                        "readyForPayouts": True,
                        "connectedAccountId": "acct_ready",
                    }
                }

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_listing(
            StubHandler(),
            {"id": 7},
            {
                "photoAttestation": "1",
                "brand": "JOOLA",
                "model": "Pro V Perseus",
                "color": "Invisible Neon",
                "thickness": "16",
            },
        )

        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertEqual(captured["payload"]["code"], "invalid_paddle_color_selection")

    def test_listing_submission_rejects_unlisted_thickness(self):
        captured = {}

        class StubHandler:
            def fetch_seller_profile(self, _user_id, force_refresh=False):
                return {
                    "sellerProfile": {
                        "readyForPayouts": True,
                        "connectedAccountId": "acct_ready",
                    }
                }

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_listing(
            StubHandler(),
            {"id": 7},
            {
                "photoAttestation": "1",
                "brand": "JOOLA",
                "model": "Pro V Perseus",
                "color": "Black",
                "thickness": "13.7",
            },
        )

        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertEqual(captured["payload"]["code"], "invalid_paddle_thickness_selection")

    def test_listing_submission_allows_omitted_thickness(self):
        captured = {}
        seller_id = self.create_user()

        class StubHandler:
            def fetch_seller_profile(self, _user_id, force_refresh=False):
                return {
                    "sellerProfile": {
                        "readyForPayouts": True,
                        "connectedAccountId": "acct_ready",
                    }
                }

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_listing(
            StubHandler(),
            {"id": seller_id},
            {
                "photoAttestation": "1",
                "brand": "JOOLA",
                "model": "Pro V Perseus",
                "color": "Black",
                "thickness": "",
                "category": "control",
                "condition": "Excellent",
                "price": "150",
                "location": "Arlington, VA",
                "shippingOriginZip": "22201",
                "shippingOriginStreet1": "123 Test Street",
                "images": [
                    "data:image/png;base64,"
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z4X0AAAAASUVORK5CYII="
                ],
            },
        )

        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)
        with sqlite3.connect(app.DB_PATH) as connection:
            thickness = connection.execute(
                "SELECT thickness_mm FROM listings WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (seller_id,),
            ).fetchone()[0]
        self.assertIsNone(thickness)


if __name__ == "__main__":
    unittest.main()
