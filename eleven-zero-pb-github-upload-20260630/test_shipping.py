import sqlite3
import tempfile
import unittest
from pathlib import Path

import app


class ManagedShippingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = app.DB_PATH
        self.original_shippo_key = app.SHIPPO_API_KEY
        self.original_shippo_request = app.shippo_request
        self.original_starter_listings = app.ENABLE_STARTER_LISTINGS
        self.original_demo_data = app.ENABLE_DEMO_DATA
        self.original_smtp = app.smtplib.SMTP
        self.original_smtp_host = app.SMTP_HOST
        self.original_smtp_username = app.SMTP_USERNAME
        self.original_smtp_password = app.SMTP_PASSWORD
        self.original_email_from = app.EMAIL_FROM
        app.DB_PATH = Path(self.temp_dir.name) / "shipping-test.db"
        app.SHIPPO_API_KEY = "shippo_test_key"
        app.ENABLE_STARTER_LISTINGS = False
        app.ENABLE_DEMO_DATA = False
        app.init_database()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        app.SHIPPO_API_KEY = self.original_shippo_key
        app.shippo_request = self.original_shippo_request
        app.ENABLE_STARTER_LISTINGS = self.original_starter_listings
        app.ENABLE_DEMO_DATA = self.original_demo_data
        app.smtplib.SMTP = self.original_smtp
        app.SMTP_HOST = self.original_smtp_host
        app.SMTP_USERNAME = self.original_smtp_username
        app.SMTP_PASSWORD = self.original_smtp_password
        app.EMAIL_FROM = self.original_email_from
        self.temp_dir.cleanup()

    def create_paid_order(self, session_id="cs_test_fulfillment"):
        with sqlite3.connect(app.DB_PATH) as connection:
            seller_id = connection.execute(
                """
                INSERT INTO users (name, email, password_salt, password_hash, created_at)
                VALUES ('Seller', 'fulfillment-seller@example.com', 'salt', 'hash', '2026-07-21T00:00:00Z')
                """
            ).lastrowid
            buyer_id = connection.execute(
                """
                INSERT INTO users (name, email, password_salt, password_hash, created_at)
                VALUES ('Buyer', 'fulfillment-buyer@example.com', 'salt', 'hash', '2026-07-21T00:00:00Z')
                """
            ).lastrowid
            listing_id = connection.execute(
                """
                INSERT INTO listings (
                  user_id, brand, model, category, condition, price_usd, location,
                  notes, approval_status, sale_status, created_at
                ) VALUES (?, 'JOOLA', 'Perseus', 'power', 'Used - good', 150,
                  'Miami, FL', 'Clean paddle', 'approved', 'available', '2026-07-21T00:00:00Z')
                """,
                (seller_id,),
            ).lastrowid
            connection.execute(
                """
                INSERT INTO orders (
                  listing_id, buyer_user_id, seller_user_id,
                  stripe_checkout_session_id, amount_total_cents,
                  shipping_amount_cents, shipping_label, shipping_address_json,
                  shippo_rate_id, shipping_status, platform_fee_cents,
                  stripe_payment_status, stripe_session_status, status, created_at
                ) VALUES (?, ?, ?, ?, 16000, 1000, 'Live shipping',
                  '{"city":"Arlington","state":"VA","postalCode":"22201"}',
                  'rate_123', 'pending', 1275, 'paid', 'complete', 'paid',
                  '2026-07-21T00:00:00Z')
                """,
                (listing_id, buyer_id, seller_id, session_id),
            )
            connection.commit()
        return listing_id

    def test_live_quote_preserves_rate_for_label_purchase(self):
        captured = {}

        def fake_shippo_request(path, payload):
            captured["path"] = path
            captured["payload"] = payload
            return {
                "object_id": "shipment_123",
                "rates": [
                    {
                        "object_id": "rate_expensive",
                        "amount": "18.00",
                        "currency": "USD",
                        "provider": "UPS",
                        "servicelevel": {"name": "Ground"},
                    },
                    {
                        "object_id": "rate_best",
                        "amount": "9.75",
                        "currency": "USD",
                        "provider": "USPS",
                        "servicelevel": {"name": "Ground Advantage"},
                        "estimated_days": 4,
                    },
                ],
            }

        app.shippo_request = fake_shippo_request
        listing = {
            "seller_name": "Seller",
            "location": "Miami, FL",
            "shipping_mode": "calculated",
            "shipping_origin_street1": "123 Main Street",
            "shipping_origin_zip": "33101",
            "shipping_weight_oz": 24,
            "shipping_length_in": 20,
            "shipping_width_in": 10,
            "shipping_height_in": 4,
            "price_usd": 150,
        }
        quote = app.build_shipping_quote_for_listing(
            listing,
            {
                "line1": "500 Market Street",
                "city": "Philadelphia",
                "state": "PA",
                "postalCode": "19106",
                "country": "US",
            },
        )

        self.assertEqual(captured["path"], "/shipments/")
        self.assertEqual(quote["rate_kind"], "live")
        self.assertEqual(quote["amount_cents"], 975)
        self.assertEqual(quote["shippo_rate_id"], "rate_best")
        self.assertEqual(quote["shippo_shipment_id"], "shipment_123")
        self.assertEqual(captured["payload"]["parcels"][0]["length"], "20.0")

    def test_label_purchase_is_idempotent(self):
        with sqlite3.connect(app.DB_PATH) as connection:
            seller_id = connection.execute(
                """
                INSERT INTO users (name, email, password_salt, password_hash, created_at)
                VALUES ('Seller', 'seller@example.com', 'salt', 'hash', '2026-07-21T00:00:00Z')
                """
            ).lastrowid
            buyer_id = connection.execute(
                """
                INSERT INTO users (name, email, password_salt, password_hash, created_at)
                VALUES ('Buyer', 'buyer@example.com', 'salt', 'hash', '2026-07-21T00:00:00Z')
                """
            ).lastrowid
            listing_id = connection.execute(
                """
                INSERT INTO listings (
                  user_id, brand, model, category, condition, price_usd, location,
                  notes, approval_status, created_at
                ) VALUES (?, 'JOOLA', 'Perseus', 'power', 'Used - good', 150,
                  'Miami, FL', 'Clean paddle', 'approved', '2026-07-21T00:00:00Z')
                """,
                (seller_id,),
            ).lastrowid
            connection.execute(
                """
                INSERT INTO orders (
                  listing_id, buyer_user_id, seller_user_id,
                  stripe_checkout_session_id, amount_total_cents,
                  shipping_amount_cents, shipping_label, shipping_address_json,
                  shippo_rate_id, shipping_status, platform_fee_cents,
                  stripe_payment_status, stripe_session_status, status, created_at
                ) VALUES (?, ?, ?, 'cs_test_shipping', 16000, 1000, 'Live shipping', '{}',
                  'rate_123', 'pending', 1275, 'paid', 'complete', 'paid',
                  '2026-07-21T00:00:00Z')
                """,
                (listing_id, buyer_id, seller_id),
            )
            connection.commit()

        calls = []

        def fake_transaction(path, payload):
            calls.append((path, payload))
            return {
                "object_id": "transaction_123",
                "status": "SUCCESS",
                "label_url": "https://example.com/label.pdf",
                "tracking_number": "TRACK123",
                "tracking_url_provider": "https://example.com/track/TRACK123",
            }

        app.shippo_request = fake_transaction
        first = app.purchase_shippo_label_for_order("cs_test_shipping")
        second = app.purchase_shippo_label_for_order("cs_test_shipping")

        self.assertEqual(len(calls), 1)
        self.assertEqual(first["shipping_status"], "label_ready")
        self.assertEqual(second["shippo_transaction_id"], "transaction_123")
        self.assertEqual(second["tracking_number"], "TRACK123")

    def test_failed_label_purchase_requires_review_before_retry(self):
        with sqlite3.connect(app.DB_PATH) as connection:
            seller_id = connection.execute(
                """
                INSERT INTO users (name, email, password_salt, password_hash, created_at)
                VALUES ('Seller', 'seller2@example.com', 'salt', 'hash', '2026-07-21T00:00:00Z')
                """
            ).lastrowid
            buyer_id = connection.execute(
                """
                INSERT INTO users (name, email, password_salt, password_hash, created_at)
                VALUES ('Buyer', 'buyer2@example.com', 'salt', 'hash', '2026-07-21T00:00:00Z')
                """
            ).lastrowid
            listing_id = connection.execute(
                """
                INSERT INTO listings (
                  user_id, brand, model, category, condition, price_usd, location,
                  notes, approval_status, created_at
                ) VALUES (?, 'Selkirk', 'Vanguard', 'control', 'Excellent', 120,
                  'Richmond, VA', 'Clean paddle', 'approved', '2026-07-21T00:00:00Z')
                """,
                (seller_id,),
            ).lastrowid
            connection.execute(
                """
                INSERT INTO orders (
                  listing_id, buyer_user_id, seller_user_id,
                  stripe_checkout_session_id, amount_total_cents,
                  shipping_amount_cents, shipping_label, shipping_address_json,
                  shippo_rate_id, shipping_status, platform_fee_cents,
                  stripe_payment_status, stripe_session_status, status, created_at
                ) VALUES (?, ?, ?, 'cs_test_shipping_failure', 13000, 1000,
                  'Live shipping', '{}', 'rate_failure', 'pending', 2020,
                  'paid', 'complete', 'paid', '2026-07-21T00:00:00Z')
                """,
                (listing_id, buyer_id, seller_id),
            )
            connection.commit()

        calls = []

        def fake_failed_transaction(path, payload):
            calls.append((path, payload))
            raise ValueError("Carrier rejected this parcel.")

        app.shippo_request = fake_failed_transaction
        first = app.purchase_shippo_label_for_order("cs_test_shipping_failure")
        second = app.purchase_shippo_label_for_order("cs_test_shipping_failure")

        self.assertEqual(len(calls), 1)
        self.assertEqual(first["shipping_status"], "attention_needed")
        self.assertEqual(second["shipping_status"], "attention_needed")
        self.assertEqual(second["shipping_error"], "Carrier rejected this parcel.")

    def test_listing_submission_requires_ready_stripe_payouts(self):
        captured = {}

        class StubHandler:
            def fetch_seller_profile(self, user_id, force_refresh=False):
                return {
                    "sellerProfile": {
                        "readyForPayouts": False,
                        "connectedAccountId": "",
                    }
                }

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_listing(StubHandler(), {"id": 42}, {})

        self.assertEqual(captured["status"], app.HTTPStatus.CONFLICT)
        self.assertEqual(captured["payload"]["code"], "seller_payouts_required")
        self.assertEqual(captured["payload"]["actionUrl"], "./account.html#seller-payouts")

    def test_ready_stripe_seller_reaches_listing_validation(self):
        captured = {}

        class StubHandler:
            def fetch_seller_profile(self, user_id, force_refresh=False):
                return {
                    "sellerProfile": {
                        "readyForPayouts": True,
                        "connectedAccountId": "acct_ready",
                    }
                }

            def send_json(self, payload, status=200, **_kwargs):
                captured["payload"] = payload
                captured["status"] = status

        app.ElevenZeroHandler.handle_create_listing(StubHandler(), {"id": 42}, {})

        self.assertEqual(captured["status"], app.HTTPStatus.BAD_REQUEST)
        self.assertNotEqual(captured["payload"].get("code"), "seller_payouts_required")

    def test_paid_order_immediately_marks_listing_sale_pending(self):
        listing_id = self.create_paid_order("cs_test_sale_pending")

        app.mark_listing_sale_pending_for_order("cs_test_sale_pending")

        with sqlite3.connect(app.DB_PATH) as connection:
            sale_status = connection.execute(
                "SELECT sale_status FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()[0]
        self.assertEqual(sale_status, "pending")

    def test_database_startup_repairs_older_paid_listing_sale_status(self):
        listing_id = self.create_paid_order("cs_test_startup_repair")

        app.init_database()

        with sqlite3.connect(app.DB_PATH) as connection:
            sale_status = connection.execute(
                "SELECT sale_status FROM listings WHERE id = ?", (listing_id,)
            ).fetchone()[0]
        self.assertEqual(sale_status, "pending")

    def test_failed_label_can_refresh_rate_and_retry_safely(self):
        self.create_paid_order("cs_test_shipping_retry")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                """
                UPDATE listings
                SET shipping_mode = 'calculated',
                    shipping_origin_street1 = '123 Main Street',
                    shipping_origin_zip = '33101',
                    shipping_weight_oz = 24,
                    shipping_length_in = 20,
                    shipping_width_in = 10,
                    shipping_height_in = 4
                WHERE id = (SELECT listing_id FROM orders WHERE stripe_checkout_session_id = ?)
                """,
                ("cs_test_shipping_retry",),
            )
            connection.execute(
                """
                UPDATE orders
                SET shipping_status = 'attention_needed',
                    shipping_error = 'Shippo billing needs attention.',
                    shipping_address_json = ?
                WHERE stripe_checkout_session_id = ?
                """,
                (
                    '{"line1":"500 Market Street","city":"Arlington","state":"VA","postalCode":"22201","country":"US"}',
                    "cs_test_shipping_retry",
                ),
            )
            connection.commit()

        paths = []

        def fake_retry(path, payload):
            paths.append(path)
            if path == "/shipments/":
                return {
                    "object_id": "shipment_retry",
                    "rates": [
                        {
                            "object_id": "rate_retry",
                            "amount": "10.00",
                            "currency": "USD",
                            "provider": "USPS",
                            "servicelevel": {"name": "Ground Advantage"},
                        }
                    ],
                }
            return {
                "object_id": "transaction_retry",
                "status": "SUCCESS",
                "label_url": "https://example.com/retry-label.pdf",
                "tracking_number": "RETRY123",
                "tracking_url_provider": "https://example.com/track/RETRY123",
            }

        app.shippo_request = fake_retry
        refreshed = app.refresh_shippo_rate_for_order("cs_test_shipping_retry")
        completed = app.purchase_shippo_label_for_order("cs_test_shipping_retry")

        self.assertEqual(refreshed["shipping_status"], "pending")
        self.assertEqual(completed["shipping_status"], "label_ready")
        self.assertEqual(paths, ["/shipments/", "/transactions/"])

    def test_purchase_confirmation_email_is_sent_once(self):
        self.create_paid_order("cs_test_email")
        app.SMTP_HOST = "smtp.example.com"
        app.SMTP_USERNAME = "user"
        app.SMTP_PASSWORD = "app-password"
        app.EMAIL_FROM = "11zeropb@gmail.com"
        sent_messages = []

        class FakeSMTP:
            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def starttls(self):
                pass

            def login(self, *_args):
                pass

            def send_message(self, message):
                sent_messages.append(message)

        app.smtplib.SMTP = FakeSMTP
        first = app.send_purchase_confirmation_for_order("cs_test_email")
        second = app.send_purchase_confirmation_for_order("cs_test_email")

        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(first["buyer_confirmation_status"], "sent")
        self.assertEqual(second["buyer_confirmation_status"], "sent")
        self.assertIn("Purchase confirmed", sent_messages[0]["Subject"])
        self.assertIn("JOOLA Perseus", sent_messages[0].get_content())

    def test_sale_pending_listing_cannot_start_checkout(self):
        state = app.listing_checkout_state_from_row(
            {
                "user_id": 1,
                "price_usd": 150,
                "approval_status": "approved",
                "sale_status": "pending",
                "stripe_account_id": "acct_ready",
                "stripe_details_submitted": 1,
                "stripe_charges_enabled": 1,
                "stripe_payouts_enabled": 1,
                "stripe_onboarding_complete": 1,
                "stripe_requirements_due_count": 0,
            }
        )

        self.assertFalse(state["available"])
        self.assertIn("sale is pending", state["reason"].lower())


if __name__ == "__main__":
    unittest.main()
