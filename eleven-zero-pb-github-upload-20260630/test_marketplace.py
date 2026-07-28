import base64
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
        app.RATE_LIMIT_BUCKETS.clear()
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
            "certificationOrg": "Professional Pickleball Registry",
            "certificationName": "PPR Coach Certification",
            "certificationId": "PPR-DEMO-001",
            "certificationUrl": "https://example.com/verify/PPR-DEMO-001",
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

    def test_new_trainer_requires_meaningful_certification(self):
        user_id = self.create_user("trainer-cert-required@example.com")
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_trainer(
            StubHandler(),
            {"id": user_id, "email": "trainer-cert-required@example.com"},
            self.trainer_payload(certificationOrg="N/A"),
        )
        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("certification organization", captured["payload"]["error"])

        app.ElevenZeroHandler.handle_create_trainer(
            StubHandler(),
            {"id": user_id, "email": "trainer-cert-required@example.com"},
            self.trainer_payload(certificationName="none"),
        )
        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("certification name", captured["payload"]["error"])

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
        self.assertEqual(
            item["certificationOrg"], "Professional Pickleball Registry"
        )
        self.assertEqual(item["certificationName"], "PPR Coach Certification")
        self.assertEqual(item["certificationId"], "PPR-DEMO-001")
        self.assertEqual(
            item["certificationUrl"],
            "https://example.com/verify/PPR-DEMO-001",
        )
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

    def test_trainer_certification_serialization_keeps_credential_id_private(self):
        user_id = self.create_user("trainer-cert-privacy@example.com")
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_trainer(
            StubHandler(),
            {"id": user_id, "email": "trainer-cert-privacy@example.com"},
            self.trainer_payload(),
        )
        owner_item = captured["payload"]["item"]
        trainer_id = owner_item["id"]
        self.assertEqual(owner_item["certificationId"], "PPR-DEMO-001")

        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                "UPDATE trainers SET approval_status = 'approved' WHERE id = ?",
                (trainer_id,),
            )
            connection.commit()

        public_item = app.ElevenZeroHandler.fetch_trainers(None)[0]
        self.assertEqual(
            public_item["certificationOrg"], "Professional Pickleball Registry"
        )
        self.assertEqual(
            public_item["certificationName"], "PPR Coach Certification"
        )
        self.assertEqual(
            public_item["certificationUrl"],
            "https://example.com/verify/PPR-DEMO-001",
        )
        self.assertNotIn("certificationId", public_item)
        self.assertNotIn("image_data", public_item)

        admin_item = next(
            item
            for item in app.ElevenZeroHandler.build_admin_dashboard(object())[
                "trainers"
            ]
            if item["id"] == trainer_id
        )
        self.assertEqual(admin_item["certificationId"], "PPR-DEMO-001")
        self.assertNotIn("image_data", admin_item)
        self.assertNotIn("data:image", json.dumps(admin_item))

    def test_public_trainer_detail_returns_profile_and_reviews_without_private_credential(self):
        trainer_owner_id = self.create_user("trainer-detail-owner@example.com")
        reviewer_id = self.create_user("trainer-detail-reviewer@example.com")
        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  verified, experience, bio, availability,
                  certification_organization, certification_name,
                  certification_credential_id, certification_verification_url,
                  joined_at, rating, review_count, approval_status
                ) VALUES (?, 'Andre Mercado', 'Arlington, VA', 'private',
                  'advanced', '$90/hr', 'andre@example.com', 1,
                  'Eight years coaching competitive players',
                  'Private lessons, clinics, and tournament preparation.',
                  'Weekday evenings and weekends',
                  'Professional Pickleball Registry',
                  'PPR Coach Certification', 'PPR-PRIVATE-009',
                  'https://example.com/verify/public-profile',
                  '2025-05-01', 5.0, 1, 'approved')
                """,
                (trainer_owner_id,),
            ).lastrowid
            connection.execute(
                """
                INSERT INTO trainer_reviews (
                  trainer_id, user_id, reviewer_name, rating, comment, created_at
                ) VALUES (?, ?, 'Verified Client', 5,
                  'Clear instruction and a very useful practice plan.',
                  '2026-07-28T12:00:00Z')
                """,
                (trainer_id, reviewer_id),
            )
            connection.commit()

        captured = {}

        class StubHandler:
            fetch_trainer_by_id = app.ElevenZeroHandler.fetch_trainer_by_id
            fetch_reviews = app.ElevenZeroHandler.fetch_reviews

            def current_user(self):
                return None

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_api_get(
            StubHandler(), app.urlparse(f"/api/trainers/{trainer_id}")
        )

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["item"]["id"], trainer_id)
        self.assertEqual(captured["payload"]["item"]["name"], "Andre Mercado")
        self.assertEqual(
            captured["payload"]["item"]["certificationName"],
            "PPR Coach Certification",
        )
        self.assertNotIn("certificationId", captured["payload"]["item"])
        self.assertNotIn("PPR-PRIVATE-009", json.dumps(captured["payload"]))
        self.assertEqual(len(captured["payload"]["reviews"]), 1)
        self.assertEqual(
            captured["payload"]["reviews"][0]["reviewer_name"],
            "Verified Client",
        )
        self.assertEqual(captured["payload"]["reviews"][0]["rating"], 5)

    def test_nonapproved_trainer_detail_is_private_to_owner_and_admin(self):
        pending_owner_id = self.create_user("trainer-pending-owner@example.com")
        other_user_id = self.create_user("trainer-detail-other@example.com")
        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_ids = {}
            for approval_status in ("pending", "rejected"):
                trainer_ids[approval_status] = connection.execute(
                    """
                    INSERT INTO trainers (
                      user_id, name, location, format, level, rate, email,
                      experience, bio, availability,
                      certification_organization, certification_name,
                      certification_credential_id, joined_at, approval_status
                    ) VALUES (?, ?, 'Arlington, VA', 'private', 'beginner',
                      '$75/hr', 'pending@example.com', 'Five years',
                      'Trainer profile awaiting moderator review.', 'Evenings',
                      'Professional Pickleball Registry',
                      'PPR Coach Certification', 'PPR-PRIVATE-010',
                      '2026-07-28', ?)
                    """,
                    (
                        pending_owner_id,
                        f"{approval_status.title()} Coach",
                        approval_status,
                    ),
                ).lastrowid
            connection.commit()

        captured = {}

        class StubHandler:
            fetch_trainer_by_id = app.ElevenZeroHandler.fetch_trainer_by_id
            fetch_reviews = app.ElevenZeroHandler.fetch_reviews

            def current_user(self):
                return None

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        for trainer_id in trainer_ids.values():
            captured.clear()
            app.ElevenZeroHandler.handle_api_get(
                StubHandler(), app.urlparse(f"/api/trainers/{trainer_id}")
            )
            self.assertEqual(captured["status"], app.HTTPStatus.NOT_FOUND)
            self.assertNotIn("PPR-PRIVATE-010", json.dumps(captured["payload"]))

            self.assertIsNone(
                app.ElevenZeroHandler.fetch_trainer_by_id(
                    None,
                    trainer_id,
                    {"id": other_user_id, "isAdmin": False},
                )
            )
            owner_item = app.ElevenZeroHandler.fetch_trainer_by_id(
                None,
                trainer_id,
                {"id": pending_owner_id, "isAdmin": False},
            )
            admin_item = app.ElevenZeroHandler.fetch_trainer_by_id(
                None,
                trainer_id,
                {"id": other_user_id, "isAdmin": True},
            )
            self.assertEqual(owner_item["id"], trainer_id)
            self.assertEqual(admin_item["id"], trainer_id)
            self.assertEqual(owner_item["certificationId"], "PPR-PRIVATE-010")
            self.assertEqual(admin_item["certificationId"], "PPR-PRIVATE-010")

    def test_anonymous_orphan_trainer_detail_is_never_public_or_owner_serialized(self):
        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, approval_status
                ) VALUES (NULL, 'Orphan Demo Coach', 'Virginia', 'private',
                  'beginner', '$50/hr', 'private@example.com', 'Five years',
                  'Private demo content', 'Weekends', '2026-01-01', 'approved')
                """
            ).lastrowid
            connection.commit()

        self.assertIsNone(
            app.ElevenZeroHandler.fetch_trainer_by_id(None, trainer_id, None)
        )
        admin_item = app.ElevenZeroHandler.fetch_trainer_by_id(
            None,
            trainer_id,
            {"id": 999, "isAdmin": True},
        )
        self.assertEqual(admin_item["email"], "private@example.com")

    def test_account_can_create_only_one_trainer_profile(self):
        user_id = self.create_user("trainer-single@example.com")
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        handler = StubHandler()
        user = {"id": user_id, "email": "trainer-single@example.com"}
        app.ElevenZeroHandler.handle_create_trainer(
            handler,
            user,
            self.trainer_payload(),
        )
        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)

        app.ElevenZeroHandler.handle_create_trainer(
            handler,
            user,
            self.trainer_payload(name="Second Trainer Profile"),
        )
        self.assertEqual(captured["status"], app.HTTPStatus.CONFLICT)
        self.assertIn("already has a trainer profile", captured["payload"]["error"])

        with sqlite3.connect(app.DB_PATH) as connection:
            trainer_count = connection.execute(
                "SELECT COUNT(*) FROM trainers WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
        self.assertEqual(trainer_count, 1)

    def test_json_body_rejects_oversized_request_before_reading(self):
        captured = {}

        class RejectRead(BytesIO):
            def read(self, *_args, **_kwargs):
                raise AssertionError("Oversized request body should not be read.")

        class StubHandler:
            headers = {"Content-Length": str(app.MAX_API_JSON_BODY_BYTES + 1)}
            rfile = RejectRead(b"")

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        with self.assertRaises(ValueError):
            app.ElevenZeroHandler.json_body(StubHandler())

        self.assertEqual(
            captured["status"],
            app.HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )
        self.assertIn("too large", captured["payload"]["error"].lower())

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

            def send_bytes(self, payload, content_type, status=200, **kwargs):
                captured["bytes"] = payload
                captured["content_type"] = content_type
                captured["status"] = status
                captured["cache_control"] = kwargs.get("cache_control")

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
        self.assertEqual(captured["cache_control"], "no-store")

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
        self.assertEqual(
            captured["cache_control"],
            "public, max-age=86400, immutable",
        )

    def test_owner_image_replacement_keeps_approved_profile_live_during_media_review(self):
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
        self.assertEqual(captured["payload"]["item"]["approval_status"], "approved")
        self.assertEqual(
            captured["payload"]["item"]["mediaReviewStatus"], "pending"
        )
        self.assertNotIn("data:image", json.dumps(captured["payload"]))
        with sqlite3.connect(app.DB_PATH) as connection:
            row = connection.execute(
                """
                SELECT
                  approval_status,
                  reviewed_at,
                  image_data,
                  pending_image_data,
                  media_review_status
                FROM trainers
                WHERE id = ?
                """,
                (trainer_id,),
            ).fetchone()
        self.assertEqual(row[0], "approved")
        self.assertEqual(row[1], "2026-07-23T12:05:00Z")
        self.assertEqual(row[2], original_image)
        self.assertNotEqual(row[3], original_image)
        self.assertEqual(row[4], "pending")

    def test_trainer_gallery_is_moderated_without_raw_image_leaks_or_downtime(self):
        owner_id = self.create_user("trainer-gallery@example.com")
        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

            def send_bytes(self, payload, content_type, status=200, **kwargs):
                captured["bytes"] = payload
                captured["content_type"] = content_type
                captured["status"] = status
                captured["cache_control"] = kwargs.get("cache_control")

        handler = StubHandler()
        app.ElevenZeroHandler.handle_create_trainer(
            handler,
            {"id": owner_id, "email": "trainer-gallery@example.com"},
            self.trainer_payload(
                trainerGalleryImages=[
                    self.trainer_image_data(width=1_300, height=800),
                    self.trainer_image_data(width=1_100, height=700),
                ]
            ),
        )

        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)
        trainer_id = captured["payload"]["item"]["id"]
        self.assertEqual(
            len(captured["payload"]["item"]["galleryImageUrls"]), 2
        )
        self.assertNotIn("data:image", json.dumps(captured["payload"]))

        app.ElevenZeroHandler.handle_admin_trainer_review(
            handler, {"id": trainer_id, "status": "approved"}
        )
        self.assertEqual(captured["status"], 200)
        public_item = app.ElevenZeroHandler.fetch_trainers(None)[0]
        self.assertEqual(len(public_item["galleryImageUrls"]), 2)

        app.ElevenZeroHandler.handle_replace_trainer_image(
            handler,
            {"id": owner_id},
            {
                "id": trainer_id,
                "trainerImage": self.trainer_image_data(width=1_500, height=900),
                "trainerGalleryImages": [
                    self.trainer_image_data(width=1_250, height=780)
                ],
            },
        )
        self.assertEqual(captured["status"], 200)
        self.assertEqual(
            captured["payload"]["item"]["mediaReviewStatus"], "pending"
        )
        self.assertEqual(
            len(app.ElevenZeroHandler.fetch_trainers(None)[0]["galleryImageUrls"]),
            2,
        )

        app.ElevenZeroHandler.handle_trainer_gallery_image(
            handler, trainer_id, 1, None, pending=True
        )
        self.assertEqual(captured["status"], app.HTTPStatus.NOT_FOUND)
        app.ElevenZeroHandler.handle_trainer_gallery_image(
            handler,
            trainer_id,
            1,
            {"id": owner_id, "isAdmin": False},
            pending=True,
        )
        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["content_type"], "image/jpeg")
        self.assertEqual(captured["cache_control"], "no-store")

        admin_item = next(
            item
            for item in app.ElevenZeroHandler.build_admin_dashboard(object())[
                "trainers"
            ]
            if item["id"] == trainer_id
        )
        self.assertEqual(len(admin_item["galleryImageUrls"]), 2)
        self.assertEqual(len(admin_item["pendingGalleryImageUrls"]), 1)

        app.ElevenZeroHandler.handle_admin_trainer_review(
            handler, {"id": trainer_id, "status": "approved"}
        )
        self.assertEqual(captured["status"], 200)
        promoted = app.ElevenZeroHandler.fetch_trainers(None)[0]
        self.assertEqual(len(promoted["galleryImageUrls"]), 1)

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

    def test_admin_requires_certification_for_pending_approval_but_allows_approved_legacy(self):
        owner_id = self.create_user("trainer-cert-review@example.com")
        image_data = app.normalize_trainer_landscape_image_data(
            self.trainer_image_data()
        )
        with sqlite3.connect(app.DB_PATH) as connection:
            pending_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, image_data,
                  image_updated_at, approval_status
                ) VALUES (?, 'Pending Certification Coach', 'Arlington, VA',
                  'private', 'beginner', '$75/hr',
                  'trainer-cert-review@example.com', 'Five years',
                  'Pending biography', 'Evenings', '2026-07-23', ?,
                  '2026-07-23T12:00:00Z', 'pending')
                """,
                (owner_id, image_data),
            ).lastrowid
            legacy_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, approval_status
                ) VALUES (?, 'Approved Legacy Coach', 'Alexandria, VA',
                  'private', 'beginner', '$70/hr',
                  'legacy-cert-review@example.com', 'Seven years',
                  'Legacy biography', 'Weekends', '2025-01-01', 'approved')
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
            handler, {"id": pending_id, "status": "approved"}
        )
        self.assertEqual(captured["status"], app.HTTPStatus.CONFLICT)
        self.assertIn("certification organization", captured["payload"]["error"])

        app.ElevenZeroHandler.handle_admin_trainer_review(
            handler, {"id": legacy_id, "status": "approved"}
        )
        self.assertEqual(captured["status"], 200)
        legacy_item = next(
            item
            for item in app.ElevenZeroHandler.fetch_trainers(None)
            if item["id"] == legacy_id
        )
        self.assertEqual(legacy_item["certificationOrg"], "")
        self.assertEqual(legacy_item["certificationName"], "")
        self.assertNotIn("certificationId", legacy_item)

    def test_admin_trainer_update_validates_certification_and_preserves_approved_legacy(self):
        owner_id = self.create_user("trainer-cert-update@example.com")
        image_data = app.normalize_trainer_landscape_image_data(
            self.trainer_image_data()
        )
        with sqlite3.connect(app.DB_PATH) as connection:
            pending_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, image_data,
                  image_updated_at, approval_status
                ) VALUES (?, 'Pending Update Coach', 'Arlington, VA',
                  'private', 'beginner', '$75/hr',
                  'trainer-cert-update@example.com', 'Five years',
                  'Pending biography', 'Evenings', '2026-07-23', ?,
                  '2026-07-23T12:00:00Z', 'pending')
                """,
                (owner_id, image_data),
            ).lastrowid
            legacy_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, approval_status
                ) VALUES (?, 'Legacy Update Coach', 'Alexandria, VA',
                  'private', 'beginner', '$70/hr',
                  'legacy-cert-update@example.com', 'Seven years',
                  'Legacy biography', 'Weekends', '2025-01-01', 'approved')
                """,
                (owner_id,),
            ).lastrowid
            connection.commit()

        captured = {}

        class StubHandler:
            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        base_payload = {
            "name": "Updated Coach",
            "location": "Arlington, VA",
            "format": "private",
            "level": "beginner",
            "rate": "$80/hr",
            "email": "updated@example.com",
            "experience": "Five years",
            "availability": "Weekday evenings",
            "bio": "Updated trainer biography.",
            "verified": False,
        }
        handler = StubHandler()
        app.ElevenZeroHandler.handle_admin_trainer_update(
            handler, {**base_payload, "id": pending_id}
        )
        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("certification organization", captured["payload"]["error"])

        app.ElevenZeroHandler.handle_admin_trainer_update(
            handler,
            {
                **base_payload,
                "id": pending_id,
                "certificationOrg": "Professional Pickleball Registry",
                "certificationName": "PPR Coach Certification",
                "certificationId": "PPR-ADMIN-001",
                "certificationUrl": "javascript:alert(1)",
            },
        )
        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("http:// or https://", captured["payload"]["error"])

        app.ElevenZeroHandler.handle_admin_trainer_update(
            handler,
            {
                **base_payload,
                "id": pending_id,
                "certificationOrg": "Professional Pickleball Registry",
                "certificationName": "PPR Coach Certification",
                "certificationId": "PPR-ADMIN-001",
                "certificationUrl": "https://example.com/verify/PPR-ADMIN-001",
            },
        )
        self.assertEqual(captured["status"], 200)
        with sqlite3.connect(app.DB_PATH) as connection:
            certification = connection.execute(
                """
                SELECT
                  certification_organization,
                  certification_name,
                  certification_credential_id,
                  certification_verification_url
                FROM trainers
                WHERE id = ?
                """,
                (pending_id,),
            ).fetchone()
        self.assertEqual(
            certification,
            (
                "Professional Pickleball Registry",
                "PPR Coach Certification",
                "PPR-ADMIN-001",
                "https://example.com/verify/PPR-ADMIN-001",
            ),
        )

        app.ElevenZeroHandler.handle_admin_trainer_update(
            handler, {**base_payload, "id": legacy_id}
        )
        self.assertEqual(captured["status"], 200)

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

    def test_trainer_client_flow_unlocks_private_messages_and_class_confirmation(self):
        trainer_user_id = self.create_user("coach-flow@example.com")
        client_user_id = self.create_user("client-flow@example.com")
        stranger_user_id = self.create_user("stranger-flow@example.com")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                "UPDATE users SET name = 'Coach Taylor' WHERE id = ?",
                (trainer_user_id,),
            )
            connection.execute(
                "UPDATE users SET name = 'Player Jordan' WHERE id = ?",
                (client_user_id,),
            )
            connection.execute(
                "UPDATE users SET name = 'Other Member' WHERE id = ?",
                (stranger_user_id,),
            )
            trainer_id = connection.execute(
                """
                INSERT INTO trainers (
                  user_id, name, location, format, level, rate, email,
                  experience, bio, availability, joined_at, approval_status
                ) VALUES (?, 'Coach Taylor', 'Arlington, VA', 'private',
                  'intermediate', '$80/hr', 'coach-flow@example.com',
                  'Six years', 'Private coaching profile', 'Weekends',
                  '2026-07-20', 'approved')
                """,
                (trainer_user_id,),
            ).lastrowid
            connection.commit()

        handler = object.__new__(app.ElevenZeroHandler)
        captured = {}

        def capture(payload, status=200, **_kwargs):
            captured["payload"] = payload
            captured["status"] = status

        handler.send_json = capture
        trainer_user = {
            "id": trainer_user_id,
            "email": "coach-flow@example.com",
        }
        client_user = {
            "id": client_user_id,
            "email": "client-flow@example.com",
        }
        stranger_user = {
            "id": stranger_user_id,
            "email": "stranger-flow@example.com",
        }

        handler.handle_create_trainer_client_request(
            client_user,
            {
                "trainerId": trainer_id,
                "introMessage": "I want to work on resets and transition play.",
            },
        )
        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)
        relationship_id = captured["payload"]["request"]["id"]

        pending_state = handler.fetch_trainer_viewer_state(
            trainer_id, client_user
        )
        self.assertEqual(pending_state["relationshipStatus"], "pending")
        self.assertIsNone(pending_state["relationshipId"])
        self.assertTrue(
            handler.fetch_trainer_viewer_state(
                trainer_id, trainer_user
            )["isOwner"]
        )
        self.assertEqual(
            handler.build_trainer_hub(trainer_user_id)["incomingRequests"][0][
                "id"
            ],
            relationship_id,
        )

        handler.handle_trainer_client_request_action(
            trainer_user,
            {"requestId": relationship_id, "action": "accept"},
        )
        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["status"], "active")
        active_state = handler.fetch_trainer_viewer_state(
            trainer_id, client_user
        )
        self.assertEqual(active_state["relationshipStatus"], "active")
        self.assertEqual(active_state["relationshipId"], relationship_id)

        handler.handle_create_trainer_message(
            client_user,
            {
                "relationshipId": relationship_id,
                "body": "Saturday morning works well for me.",
            },
        )
        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)
        self.assertEqual(
            handler.build_trainer_hub(trainer_user_id)["unreadCount"], 1
        )

        handler.handle_create_trainer_message(
            stranger_user,
            {
                "relationshipId": relationship_id,
                "body": "I should not be able to join this conversation.",
            },
        )
        self.assertEqual(captured["status"], app.HTTPStatus.NOT_FOUND)
        self.assertNotIn("Coach Taylor", json.dumps(captured["payload"]))

        handler.handle_create_trainer_message(
            trainer_user,
            {
                "relationshipId": relationship_id,
                "body": "Great. I can meet at Quincy Park.",
            },
        )
        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)

        handler.handle_trainer_relationship_detail(
            trainer_user, relationship_id
        )
        self.assertEqual(captured["status"], 200)
        self.assertEqual(len(captured["payload"]["messages"]), 2)
        self.assertEqual(
            handler.build_trainer_hub(trainer_user_id)["unreadCount"], 0
        )
        self.assertEqual(
            handler.build_trainer_hub(client_user_id)["unreadCount"], 1
        )

        handler.handle_create_trainer_lesson(
            client_user,
            {
                "relationshipId": relationship_id,
                "startsAt": datetime.now(timezone.utc).isoformat(),
                "durationMinutes": 60,
                "timezone": "America/New_York",
                "location": "Quincy Park",
            },
        )
        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertIn("future", captured["payload"]["error"])

        starts_at = (
            datetime.now(timezone.utc) + timedelta(days=2)
        ).replace(microsecond=0)
        handler.handle_create_trainer_lesson(
            client_user,
            {
                "relationshipId": relationship_id,
                "startsAt": starts_at.isoformat(),
                "durationMinutes": 60,
                "timezone": "America/New_York",
                "location": "Quincy Park, Court 2",
                "note": "Work on resets and transition play.",
            },
        )
        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)
        lesson_id = captured["payload"]["lesson"]["id"]

        handler.handle_trainer_lesson_action(
            client_user, {"lessonId": lesson_id, "action": "confirm"}
        )
        self.assertEqual(captured["status"], app.HTTPStatus.FORBIDDEN)

        handler.handle_trainer_lesson_action(
            trainer_user, {"lessonId": lesson_id, "action": "confirm"}
        )
        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["lesson"]["status"], "confirmed")
        self.assertEqual(
            handler.build_trainer_hub(client_user_id)["lessons"][0]["status"],
            "confirmed",
        )

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
