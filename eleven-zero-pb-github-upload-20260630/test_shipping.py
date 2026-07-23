import sqlite3
import tempfile
import unittest
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import app


class ManagedShippingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = app.DB_PATH
        self.original_shippo_key = app.SHIPPO_API_KEY
        self.original_shippo_request = app.shippo_request
        self.original_shippo_api_request = app.shippo_api_request
        self.original_payout_protection_hours = app.PAYOUT_PROTECTION_HOURS
        self.original_starter_listings = app.ENABLE_STARTER_LISTINGS
        self.original_demo_data = app.ENABLE_DEMO_DATA
        self.original_smtp = app.smtplib.SMTP
        self.original_smtp_host = app.SMTP_HOST
        self.original_smtp_username = app.SMTP_USERNAME
        self.original_smtp_password = app.SMTP_PASSWORD
        self.original_email_from = app.EMAIL_FROM
        self.original_stripe_key = app.STRIPE_SECRET_KEY
        self.original_stripe_request = app.stripe_request
        app.DB_PATH = Path(self.temp_dir.name) / "shipping-test.db"
        app.SHIPPO_API_KEY = "shippo_test_key"
        app.PAYOUT_PROTECTION_HOURS = 24
        app.ENABLE_STARTER_LISTINGS = False
        app.ENABLE_DEMO_DATA = False
        app.init_database()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        app.SHIPPO_API_KEY = self.original_shippo_key
        app.shippo_request = self.original_shippo_request
        app.shippo_api_request = self.original_shippo_api_request
        app.PAYOUT_PROTECTION_HOURS = self.original_payout_protection_hours
        app.ENABLE_STARTER_LISTINGS = self.original_starter_listings
        app.ENABLE_DEMO_DATA = self.original_demo_data
        app.smtplib.SMTP = self.original_smtp
        app.SMTP_HOST = self.original_smtp_host
        app.SMTP_USERNAME = self.original_smtp_username
        app.SMTP_PASSWORD = self.original_smtp_password
        app.EMAIL_FROM = self.original_email_from
        app.STRIPE_SECRET_KEY = self.original_stripe_key
        app.stripe_request = self.original_stripe_request
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

    def create_delivery_gated_order(
        self,
        session_id="cs_test_delivery_gated",
        *,
        release_at="2020-01-01T00:00:00Z",
        buyer_issue_status="none",
    ):
        email_tag = "".join(character for character in session_id if character.isalnum())
        with sqlite3.connect(app.DB_PATH) as connection:
            seller_id = connection.execute(
                """
                INSERT INTO users (
                  name, email, password_salt, password_hash, created_at,
                  stripe_account_id
                ) VALUES ('Seller', ?, 'salt', 'hash',
                  '2026-07-23T00:00:00Z', 'acct_ready')
                """,
                (f"payout-seller+{email_tag}@example.com",),
            ).lastrowid
            buyer_id = connection.execute(
                """
                INSERT INTO users (name, email, password_salt, password_hash, created_at)
                VALUES ('Buyer', ?, 'salt', 'hash',
                  '2026-07-23T00:00:00Z')
                """,
                (f"payout-buyer+{email_tag}@example.com",),
            ).lastrowid
            listing_id = connection.execute(
                """
                INSERT INTO listings (
                  user_id, brand, model, category, condition, price_usd, location,
                  notes, approval_status, sale_status, created_at
                ) VALUES (?, 'JOOLA', 'Perseus', 'power', 'Used - good', 150,
                  'Miami, FL', 'Clean paddle', 'approved', 'pending',
                  '2026-07-23T00:00:00Z')
                """,
                (seller_id,),
            ).lastrowid
            order_id = connection.execute(
                """
                INSERT INTO orders (
                  listing_id, buyer_user_id, seller_user_id,
                  stripe_checkout_session_id, stripe_payment_intent_id,
                  amount_total_cents, shipping_amount_cents, platform_fee_cents,
                  stripe_application_fee_cents, seller_proceeds_cents,
                  payment_flow, stripe_destination_account_id,
                  stripe_transfer_group, stripe_charge_id, payout_status,
                  payout_release_at, tracking_status, shippo_transaction_id,
                  tracking_number, shipping_carrier, shipping_status,
                  buyer_issue_status, stripe_payment_status,
                  stripe_session_status, status, created_at
                ) VALUES (?, ?, ?, ?, 'pi_test_delivery', 16000, 1000, 1275,
                  0, 13725, 'separate_charge_transfer', 'acct_ready', ?,
                  'ch_test_delivery', 'release_scheduled', ?, 'DELIVERED',
                  'transaction_delivery', 'TRACK123', 'USPS', 'delivered', ?,
                  'paid', 'complete', 'paid', '2026-07-23T00:00:00Z')
                """,
                (
                    listing_id,
                    buyer_id,
                    seller_id,
                    session_id,
                    f"EZPB_{listing_id}_{session_id}",
                    release_at,
                    buyer_issue_status,
                ),
            ).lastrowid
            connection.commit()
        return order_id

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
        self.assertIn("Order confirmed", sent_messages[0]["Subject"])
        plain_part = sent_messages[0].get_body(preferencelist=("plain",))
        html_part = sent_messages[0].get_body(preferencelist=("html",))
        self.assertIsNotNone(plain_part)
        self.assertIsNotNone(html_part)
        self.assertIn("JOOLA Perseus", plain_part.get_content())
        self.assertIn("Your order is confirmed", html_part.get_content())
        self.assertIn("View your account", html_part.get_content())
        self.assertIn("cid:eleven-zero-logo", html_part.get_content())
        self.assertIn("Paddle price: $150.00", plain_part.get_content())
        self.assertIn("$150.00", html_part.get_content())
        self.assertIn("$10.00", html_part.get_content())
        self.assertIn("$160.00", html_part.get_content())
        self.assertTrue(
            any(part.get_content_type() == "image/png" for part in sent_messages[0].walk())
        )

    def test_seller_shipping_label_email_is_sent_once(self):
        self.create_paid_order("cs_test_seller_label_email")
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

        def fake_transaction(_path, _payload):
            return {
                "object_id": "transaction_seller_email",
                "status": "SUCCESS",
                "label_url": "https://example.com/prepaid-label.pdf",
                "tracking_number": "SELLERTRACK123",
                "tracking_url_provider": "https://example.com/track/SELLERTRACK123",
            }

        app.smtplib.SMTP = FakeSMTP
        app.shippo_request = fake_transaction
        first = app.purchase_shippo_label_for_order("cs_test_seller_label_email")
        second = app.purchase_shippo_label_for_order("cs_test_seller_label_email")

        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(first["seller_label_email_status"], "sent")
        self.assertEqual(second["seller_label_email_status"], "sent")
        self.assertEqual(sent_messages[0]["To"], "fulfillment-seller@example.com")
        self.assertIn("Shipping label ready", sent_messages[0]["Subject"])
        plain_part = sent_messages[0].get_body(preferencelist=("plain",))
        html_part = sent_messages[0].get_body(preferencelist=("html",))
        self.assertIsNotNone(plain_part)
        self.assertIsNotNone(html_part)
        self.assertIn("https://example.com/prepaid-label.pdf", plain_part.get_content())
        self.assertIn("How to ship the paddle", plain_part.get_content())
        self.assertIn("Sale price: $150.00", plain_part.get_content())
        self.assertIn("Estimated proceeds: $137.25", plain_part.get_content())
        self.assertIn("Open shipping label", html_part.get_content())
        self.assertIn("Pack and ship in six steps", html_part.get_content())
        self.assertIn("cid:eleven-zero-logo", html_part.get_content())
        self.assertTrue(
            any(part.get_content_type() == "image/png" for part in sent_messages[0].walk())
        )

    def test_seller_sale_confirmation_is_immediate_idempotent_and_shows_net(self):
        self.create_paid_order("cs_test_seller_sale_email")
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
        first = app.send_seller_sale_confirmation_for_order("cs_test_seller_sale_email")
        second = app.send_seller_sale_confirmation_for_order("cs_test_seller_sale_email")

        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(first["seller_sale_email_status"], "sent")
        self.assertEqual(second["seller_sale_email_status"], "sent")
        self.assertEqual(sent_messages[0]["To"], "fulfillment-seller@example.com")
        self.assertIn("Your paddle sold", sent_messages[0]["Subject"])
        plain_part = sent_messages[0].get_body(preferencelist=("plain",))
        html_part = sent_messages[0].get_body(preferencelist=("html",))
        self.assertIn("Sale price: $150.00", plain_part.get_content())
        self.assertIn("Eleven Zero PB fee (8.5%): -$12.75", plain_part.get_content())
        self.assertIn("Estimated proceeds: $137.25", plain_part.get_content())
        self.assertIn("Your paddle sold", html_part.get_content())

    def test_finalize_still_notifies_buyer_and_seller_when_label_fails(self):
        listing_id = self.create_paid_order("cs_test_email_before_label")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                "UPDATE listings SET sale_status = 'reserved', reserved_checkout_session_id = ? WHERE id = ?",
                ("cs_test_email_before_label", listing_id),
            )
            connection.commit()

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

        def fail_label(_path, _payload):
            raise ValueError("Shippo billing needs attention.")

        app.shippo_request = fail_label
        result = app.finalize_paid_order("cs_test_email_before_label")

        self.assertEqual(result["shipping_status"], "attention_needed")
        self.assertEqual(len(sent_messages), 2)
        self.assertTrue(any("Order confirmed" in message["Subject"] for message in sent_messages))
        self.assertTrue(any("Your paddle sold" in message["Subject"] for message in sent_messages))
        with sqlite3.connect(app.DB_PATH) as connection:
            sale_status, reservation = connection.execute(
                "SELECT sale_status, reserved_checkout_session_id FROM listings WHERE id = ?",
                (listing_id,),
            ).fetchone()
        self.assertEqual(sale_status, "pending")
        self.assertEqual(reservation, "")

    def test_shippo_configuration_never_falls_back_to_an_unusable_estimate(self):
        app.shippo_request = lambda _path, _payload: {
            "object_id": "shipment_no_rates",
            "rates": [],
        }
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
        with self.assertRaisesRegex(ValueError, "live prepaid shipping rate"):
            app.build_shipping_quote_for_listing(
                listing,
                {
                    "line1": "500 Market Street",
                    "city": "Philadelphia",
                    "state": "PA",
                    "postalCode": "19106",
                    "country": "US",
                },
            )

    def test_startup_normalizes_legacy_shipping_modes(self):
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                """
                INSERT INTO listings (
                  brand, model, category, condition, price_usd, location, notes,
                  shipping_mode, shipping_flat_usd, created_at
                ) VALUES ('JOOLA', 'Legacy', 'control', 'Good', 100, 'Arlington, VA',
                  'Legacy shipping', 'flat', 12, '2026-07-21T00:00:00Z')
                """
            )
            connection.commit()

        app.init_database()

        with sqlite3.connect(app.DB_PATH) as connection:
            mode, flat = connection.execute(
                "SELECT shipping_mode, shipping_flat_usd FROM listings WHERE model = 'Legacy'"
            ).fetchone()
        self.assertEqual(mode, "calculated")
        self.assertEqual(flat, 0)

    def test_checkout_uses_one_address_and_reserves_listing_atomically(self):
        app.STRIPE_SECRET_KEY = "sk_test_checkout"
        with sqlite3.connect(app.DB_PATH) as connection:
            seller_id = connection.execute(
                """
                INSERT INTO users (
                  name, email, password_salt, password_hash, created_at,
                  stripe_account_id, stripe_details_submitted, stripe_charges_enabled,
                  stripe_payouts_enabled, stripe_onboarding_complete,
                  stripe_requirements_due_count
                ) VALUES ('Seller', 'checkout-seller@example.com', 'salt', 'hash',
                  '2026-07-21T00:00:00Z', 'acct_ready', 1, 1, 1, 1, 0)
                """
            ).lastrowid
            buyer_id = connection.execute(
                """
                INSERT INTO users (name, email, password_salt, password_hash, created_at)
                VALUES ('Buyer Name', 'checkout-buyer@example.com', 'salt', 'hash',
                  '2026-07-21T00:00:00Z')
                """
            ).lastrowid
            listing_id = connection.execute(
                """
                INSERT INTO listings (
                  user_id, brand, model, category, condition, price_usd, location,
                  notes, shipping_mode, shipping_origin_street1, shipping_origin_zip,
                  shipping_weight_oz, shipping_length_in, shipping_width_in,
                  shipping_height_in, approval_status, sale_status, created_at
                ) VALUES (?, 'JOOLA', 'Perseus', 'power', 'Good', 150, 'Miami, FL',
                  'Clean paddle', 'calculated', '123 Main Street', '33101',
                  24, 20, 10, 4, 'approved', 'available', '2026-07-21T00:00:00Z')
                """,
                (seller_id,),
            ).lastrowid
            connection.commit()

        captured = {}

        def fake_shippo(_path, payload):
            captured["shippo"] = payload
            return {
                "object_id": "shipment_checkout",
                "rates": [
                    {
                        "object_id": "rate_checkout",
                        "amount": "10.00",
                        "currency": "USD",
                        "provider": "USPS",
                        "servicelevel": {"name": "Ground Advantage"},
                    }
                ],
            }

        def fake_stripe(method, path, data=None):
            captured.setdefault("stripeCalls", []).append((method, path, data or {}))
            return {
                "id": "cs_test_address_reservation",
                "url": "https://checkout.stripe.test/session",
                "payment_status": "unpaid",
                "status": "open",
            }

        class StubHandler:
            def fetch_listing_checkout_row(self, requested_id):
                return app.ElevenZeroHandler.fetch_listing_checkout_row(self, requested_id)

            def checkout_success_url(self):
                return "https://11zeropb.com/success"

            def checkout_cancel_url(self):
                return "https://11zeropb.com/cancel"

            def send_json(self, payload, status=200, **_kwargs):
                captured["response"] = payload
                captured["status"] = status

        app.shippo_request = fake_shippo
        app.stripe_request = fake_stripe
        app.ElevenZeroHandler.handle_create_checkout_session(
            StubHandler(),
            {
                "id": buyer_id,
                "name": "Buyer Name",
                "email": "checkout-buyer@example.com",
            },
            {
                "listingId": listing_id,
                "shippingAddress": {
                    "line1": "500 Market Street",
                    "line2": "Unit 4",
                    "city": "Philadelphia",
                    "state": "PA",
                    "postalCode": "19106",
                    "country": "US",
                },
            },
        )

        stripe_payload = captured["stripeCalls"][0][2]
        self.assertEqual(captured["status"], app.HTTPStatus.CREATED)
        self.assertNotIn("shipping_address_collection[allowed_countries][0]", stripe_payload)
        self.assertEqual(
            stripe_payload["payment_intent_data[shipping][address][line1]"],
            "500 Market Street",
        )
        self.assertEqual(stripe_payload["payment_intent_data[shipping][name]"], "Buyer Name")
        self.assertEqual(captured["shippo"]["address_to"]["name"], "Buyer Name")
        self.assertEqual(
            captured["shippo"]["address_to"]["email"],
            "checkout-buyer@example.com",
        )
        self.assertEqual(stripe_payload["payment_method_types[0]"], "card")
        self.assertNotIn(
            "payment_intent_data[application_fee_amount]",
            stripe_payload,
        )
        self.assertNotIn(
            "payment_intent_data[transfer_data][destination]",
            stripe_payload,
        )
        self.assertTrue(
            stripe_payload["payment_intent_data[transfer_group]"].startswith(
                f"EZPB_{listing_id}_"
            )
        )

        with sqlite3.connect(app.DB_PATH) as connection:
            listing_state = connection.execute(
                """
                SELECT sale_status, reserved_checkout_session_id
                FROM listings WHERE id = ?
                """,
                (listing_id,),
            ).fetchone()
            order = connection.execute(
                """
                SELECT shipping_address_json, platform_fee_cents,
                  stripe_application_fee_cents, seller_proceeds_cents,
                  payment_flow, stripe_destination_account_id,
                  stripe_transfer_group, payout_status
                FROM orders WHERE stripe_checkout_session_id = ?
                """,
                ("cs_test_address_reservation",),
            ).fetchone()
        self.assertEqual(listing_state, ("reserved", "cs_test_address_reservation"))
        self.assertEqual(json.loads(order[0])["name"], "Buyer Name")
        self.assertEqual(order[1:4], (1275, 0, 13725))
        self.assertEqual(order[4], "separate_charge_transfer")
        self.assertEqual(order[5], "acct_ready")
        self.assertEqual(
            order[6],
            stripe_payload["payment_intent_data[transfer_group]"],
        )
        self.assertEqual(order[7], "awaiting_payment")

    def test_legacy_destination_charge_order_can_never_transfer_twice(self):
        order_id = self.create_delivery_gated_order("cs_test_legacy_guard")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                """
                UPDATE orders
                SET payment_flow = 'legacy_destination_charge',
                    payout_status = 'legacy_released'
                WHERE id = ?
                """,
                (order_id,),
            )
            connection.commit()

        app.shippo_api_request = lambda *_args, **_kwargs: {
            "carrier": "USPS",
            "tracking_status": {"status": "DELIVERED"},
        }

        def reject_stripe_call(*_args, **_kwargs):
            raise AssertionError("A legacy destination-charge order must never transfer again.")

        app.stripe_request = reject_stripe_call
        result = app.release_seller_transfer_for_order(order_id)

        self.assertEqual(result["payment_flow"], "legacy_destination_charge")
        self.assertEqual(result["payout_status"], "legacy_released")
        self.assertEqual(result["stripe_transfer_id"], "")

    def test_shippo_delivery_schedules_full_24_hour_window_idempotently(self):
        order_id = self.create_delivery_gated_order("cs_test_delivery_schedule")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                """
                UPDATE orders
                SET payout_status = 'held_for_delivery',
                    payout_release_at = NULL,
                    tracking_status = 'UNKNOWN',
                    shipping_status = 'label_ready',
                    delivered_at = NULL
                WHERE id = ?
                """,
                (order_id,),
            )
            connection.commit()

        event = {
            "transaction_id": "transaction_delivery",
            "tracking_number": "TRACK123",
            "carrier": "USPS",
            "status": "DELIVERED",
            "details": "Delivered at front door.",
            "status_date": "2026-07-22T10:00:00Z",
            "event_id": "track_event_123",
            "substatus": "delivered",
            "action_required": False,
        }
        before = datetime.now(timezone.utc)
        first = app.apply_shippo_tracking_update(event)
        second = app.apply_shippo_tracking_update(event)
        after = datetime.now(timezone.utc)

        release_at = datetime.strptime(
            first["payout_release_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        self.assertGreaterEqual(
            release_at,
            before + timedelta(hours=24) - timedelta(seconds=1),
        )
        self.assertLessEqual(release_at, after + timedelta(hours=24, seconds=1))
        self.assertEqual(first["tracking_status"], "DELIVERED")
        self.assertEqual(first["shipping_status"], "delivered")
        self.assertEqual(first["payout_status"], "release_scheduled")
        self.assertEqual(second["payout_release_at"], first["payout_release_at"])
        self.assertEqual(second["delivered_at"], first["delivered_at"])

    def test_shippo_return_or_action_required_overrides_prior_delivery(self):
        hold_events = (
            {
                "status": "RETURNED",
                "details": "Package is being returned to the sender.",
                "action_required": False,
            },
            {
                "status": "DELIVERED",
                "details": "Carrier needs address confirmation.",
                "action_required": True,
            },
        )
        for index, event_state in enumerate(hold_events, start=1):
            with self.subTest(event_state=event_state):
                order_id = self.create_delivery_gated_order(
                    f"cs_test_delivery_hold_{index}"
                )
                transaction_id = f"transaction_delivery_hold_{index}"
                tracking_number = f"TRACKHOLD{index}"
                with sqlite3.connect(app.DB_PATH) as connection:
                    connection.execute(
                        """
                        UPDATE orders
                        SET shippo_transaction_id = ?, tracking_number = ?
                        WHERE id = ?
                        """,
                        (transaction_id, tracking_number, order_id),
                    )
                    connection.commit()
                event = {
                    "transaction_id": transaction_id,
                    "tracking_number": tracking_number,
                    "carrier": "USPS",
                    "status_date": "2026-07-23T12:00:00Z",
                    "event_id": f"track_hold_{index}",
                    "substatus": "carrier_attention",
                    **event_state,
                }

                result = app.apply_shippo_tracking_update(event)

                self.assertEqual(result["id"], order_id)
                self.assertEqual(result["shipping_status"], "attention_needed")
                self.assertEqual(result["payout_status"], "on_hold")
                self.assertEqual(result["stripe_transfer_id"], "")
                self.assertIn(event_state["details"], result["payout_error"])

    def test_open_buyer_issue_freezes_due_seller_payout(self):
        order_id = self.create_delivery_gated_order(
            "cs_test_issue_hold",
            buyer_issue_status="open",
        )
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                "UPDATE orders SET payout_status = 'on_hold' WHERE id = ?",
                (order_id,),
            )
            connection.commit()

        app.shippo_api_request = lambda *_args, **_kwargs: {
            "carrier": "USPS",
            "tracking_status": {"status": "DELIVERED"},
        }

        def reject_stripe_call(*_args, **_kwargs):
            raise AssertionError("An open buyer issue must prevent all Stripe payout calls.")

        app.stripe_request = reject_stripe_call
        result = app.release_seller_transfer_for_order(order_id)

        self.assertEqual(result["buyer_issue_status"], "open")
        self.assertEqual(result["payout_status"], "on_hold")
        self.assertEqual(result["stripe_transfer_id"], "")

    def test_due_delivery_transfers_exact_product_proceeds_excluding_shipping(self):
        order_id = self.create_delivery_gated_order("cs_test_exact_transfer")
        calls = []

        app.shippo_api_request = lambda *_args, **_kwargs: {
            "carrier": "USPS",
            "tracking_status": {"status": "DELIVERED"},
        }

        def fake_stripe(method, path, data=None, idempotency_key=None):
            calls.append((method, path, data or {}, idempotency_key))
            if path == "/payment_intents/pi_test_delivery":
                return {
                    "id": "pi_test_delivery",
                    "status": "succeeded",
                    "latest_charge": "ch_test_delivery",
                }
            if path == "/transfers":
                if method == "GET":
                    return {"data": []}
                return {"id": "tr_exact_13725"}
            if path == "/charges/ch_test_delivery":
                return {
                    "id": "ch_test_delivery",
                    "status": "succeeded",
                    "paid": True,
                    "refunded": False,
                    "amount_refunded": 0,
                    "disputed": False,
                }
            raise AssertionError(f"Unexpected Stripe request: {method} {path}")

        app.stripe_request = fake_stripe
        result = app.release_seller_transfer_for_order(order_id)

        transfer_call = next(
            call for call in calls if call[0] == "POST" and call[1] == "/transfers"
        )
        self.assertEqual(transfer_call[2]["amount"], 13725)
        self.assertEqual(transfer_call[2]["source_transaction"], "ch_test_delivery")
        self.assertEqual(transfer_call[2]["destination"], "acct_ready")
        self.assertIn("ezpb-seller-transfer-", transfer_call[3])
        self.assertEqual(result["payout_status"], "released")
        self.assertEqual(result["stripe_transfer_id"], "tr_exact_13725")
        with sqlite3.connect(app.DB_PATH) as connection:
            amounts = connection.execute(
                """
                SELECT amount_total_cents, shipping_amount_cents,
                  platform_fee_cents, seller_proceeds_cents
                FROM orders WHERE id = ?
                """,
                (order_id,),
            ).fetchone()
        self.assertEqual(amounts, (16000, 1000, 1275, 13725))

    def test_seller_transfer_cannot_run_before_protection_window_is_due(self):
        future = (
            datetime.now(timezone.utc) + timedelta(hours=23)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        order_id = self.create_delivery_gated_order(
            "cs_test_not_due",
            release_at=future,
        )
        app.shippo_api_request = lambda *_args, **_kwargs: {
            "carrier": "USPS",
            "tracking_status": {"status": "DELIVERED"},
        }

        def reject_stripe_call(*_args, **_kwargs):
            raise AssertionError("Stripe must not be called before payout_release_at.")

        app.stripe_request = reject_stripe_call
        result = app.release_seller_transfer_for_order(
            order_id,
            admin_override=True,
        )

        self.assertEqual(result["payout_status"], "release_scheduled")
        self.assertEqual(result["stripe_transfer_id"], "")

    def test_hold_committed_during_release_blocks_transfer_and_is_preserved(self):
        order_id = self.create_delivery_gated_order("cs_test_release_hold_race")
        calls = []

        app.shippo_api_request = lambda *_args, **_kwargs: {
            "carrier": "USPS",
            "tracking_status": {"status": "DELIVERED"},
        }

        def fake_stripe(method, path, data=None, idempotency_key=None):
            calls.append((method, path, data or {}, idempotency_key))
            if path == "/payment_intents/pi_test_delivery":
                return {
                    "id": "pi_test_delivery",
                    "status": "succeeded",
                    "latest_charge": "ch_test_delivery",
                }
            if path == "/transfers" and method == "GET":
                # Reproduce a refund/return/issue webhook committing after the
                # payout claim but before the final Stripe transfer.
                with sqlite3.connect(app.DB_PATH) as connection:
                    connection.execute(
                        """
                        UPDATE orders
                        SET payout_status = 'on_hold',
                            buyer_issue_status = 'open',
                            buyer_issue_reason = 'item_not_as_described',
                            payout_error = 'Concurrent safety hold'
                        WHERE id = ?
                        """,
                        (order_id,),
                    )
                    connection.commit()
                return {"data": []}
            if path == "/transfers" and method == "POST":
                raise AssertionError(
                    "A committed safety hold must block the Stripe transfer."
                )
            if path == "/charges/ch_test_delivery":
                raise AssertionError(
                    "Final local payout eligibility must be checked before Charge lookup."
                )
            raise AssertionError(f"Unexpected Stripe request: {method} {path}")

        app.stripe_request = fake_stripe
        result = app.release_seller_transfer_for_order(order_id)

        self.assertEqual(result["payout_status"], "on_hold")
        self.assertEqual(result["buyer_issue_status"], "open")
        self.assertEqual(result["stripe_transfer_id"], "")
        self.assertFalse(
            any(method == "POST" and path == "/transfers" for method, path, *_ in calls)
        )

    def test_existing_stripe_transfer_is_adopted_and_retries_are_idempotent(self):
        order_id = self.create_delivery_gated_order("cs_test_existing_transfer")
        stripe_calls = []

        app.shippo_api_request = lambda *_args, **_kwargs: {
            "carrier": "USPS",
            "tracking_status": {"status": "DELIVERED"},
        }

        def fake_stripe(method, path, data=None, idempotency_key=None):
            stripe_calls.append((method, path, data or {}, idempotency_key))
            if path == "/payment_intents/pi_test_delivery":
                return {
                    "id": "pi_test_delivery",
                    "status": "succeeded",
                    "latest_charge": "ch_test_delivery",
                }
            if path == "/transfers" and method == "GET":
                return {
                    "data": [
                        {
                            "id": "tr_already_created",
                            "amount": 13725,
                            "transfer_group": data["transfer_group"],
                            "metadata": {"order_id": str(order_id)},
                        }
                    ]
                }
            raise AssertionError(f"Unexpected Stripe request: {method} {path}")

        app.stripe_request = fake_stripe
        first = app.release_seller_transfer_for_order(order_id)
        second = app.release_seller_transfer_for_order(order_id)

        self.assertEqual(first["stripe_transfer_id"], "tr_already_created")
        self.assertEqual(first["payout_status"], "released")
        self.assertEqual(second["stripe_transfer_id"], "tr_already_created")
        self.assertFalse(
            any(method == "POST" and path == "/transfers" for method, path, *_ in stripe_calls)
        )
        self.assertEqual(
            sum(method == "GET" and path == "/transfers" for method, path, *_ in stripe_calls),
            1,
        )

    def test_refunded_or_disputed_charge_is_held_before_transfer(self):
        invalid_charge_states = (
            {"refunded": True, "amount_refunded": 16000, "disputed": False},
            {"refunded": False, "amount_refunded": 0, "disputed": True},
        )
        for index, invalid_state in enumerate(invalid_charge_states, start=1):
            with self.subTest(invalid_state=invalid_state):
                order_id = self.create_delivery_gated_order(
                    f"cs_test_invalid_charge_{index}"
                )
                app.shippo_api_request = lambda *_args, **_kwargs: {
                    "carrier": "USPS",
                    "tracking_status": {"status": "DELIVERED"},
                }
                calls = []

                def fake_stripe(method, path, data=None, idempotency_key=None):
                    calls.append((method, path, data or {}, idempotency_key))
                    if path == "/payment_intents/pi_test_delivery":
                        return {
                            "id": "pi_test_delivery",
                            "status": "succeeded",
                            "latest_charge": "ch_test_delivery",
                        }
                    if path == "/transfers" and method == "GET":
                        return {"data": []}
                    if path == "/charges/ch_test_delivery":
                        return {
                            "id": "ch_test_delivery",
                            "status": "succeeded",
                            "paid": True,
                            **invalid_state,
                        }
                    raise AssertionError(f"Unexpected Stripe request: {method} {path}")

                app.stripe_request = fake_stripe
                result = app.release_seller_transfer_for_order(order_id)

                self.assertEqual(result["payout_status"], "on_hold")
                self.assertEqual(result["stripe_transfer_id"], "")
                self.assertIn("refunded, disputed", result["payout_error"])
                self.assertFalse(
                    any(
                        method == "POST" and path == "/transfers"
                        for method, path, *_ in calls
                    )
                )

    def test_expired_order_releases_only_its_own_reservation(self):
        listing_id = self.create_paid_order("cs_test_release")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                """
                UPDATE orders
                SET stripe_payment_status = 'unpaid', status = 'expired'
                WHERE stripe_checkout_session_id = 'cs_test_release'
                """
            )
            connection.execute(
                """
                UPDATE listings
                SET sale_status = 'reserved',
                    reserved_checkout_session_id = 'cs_test_release'
                WHERE id = ?
                """,
                (listing_id,),
            )
            connection.commit()

        app.release_listing_reservation_for_order("cs_test_release")
        with sqlite3.connect(app.DB_PATH) as connection:
            state = connection.execute(
                "SELECT sale_status, reserved_checkout_session_id FROM listings WHERE id = ?",
                (listing_id,),
            ).fetchone()
        self.assertEqual(state, ("available", ""))

    def test_overdue_reservation_self_heals_after_stripe_confirms_expiration(self):
        listing_id = self.create_paid_order("cs_test_reconcile_expired")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                """
                UPDATE orders
                SET stripe_payment_status = 'unpaid', status = 'open',
                    stripe_session_status = 'open'
                WHERE stripe_checkout_session_id = 'cs_test_reconcile_expired'
                """
            )
            connection.execute(
                """
                UPDATE listings
                SET sale_status = 'reserved',
                    reserved_checkout_session_id = 'cs_test_reconcile_expired',
                    reserved_until = '2020-01-01T00:00:00Z'
                WHERE id = ?
                """,
                (listing_id,),
            )
            connection.commit()

        app.STRIPE_SECRET_KEY = "sk_test_reconcile"
        app.stripe_request = lambda method, path, data=None: {
            "id": "cs_test_reconcile_expired",
            "payment_status": "unpaid",
            "status": "expired",
        }
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            listing_row = connection.execute(
                "SELECT * FROM listings WHERE id = ?",
                (listing_id,),
            ).fetchone()

        self.assertTrue(app.reconcile_expired_listing_reservation(listing_row))
        with sqlite3.connect(app.DB_PATH) as connection:
            listing_state = connection.execute(
                "SELECT sale_status, reserved_checkout_session_id FROM listings WHERE id = ?",
                (listing_id,),
            ).fetchone()
            order_state = connection.execute(
                "SELECT status, stripe_session_status FROM orders WHERE stripe_checkout_session_id = ?",
                ("cs_test_reconcile_expired",),
            ).fetchone()
        self.assertEqual(listing_state, ("available", ""))
        self.assertEqual(order_state, ("expired", "expired"))

    def test_catalog_read_releases_missed_async_payment_failure(self):
        listing_id = self.create_paid_order("cs_test_reconcile_failed")
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(
                """
                UPDATE orders
                SET stripe_payment_intent_id = 'pi_test_reconcile_failed',
                    stripe_payment_status = 'unpaid',
                    status = 'processing',
                    stripe_session_status = 'complete'
                WHERE stripe_checkout_session_id = 'cs_test_reconcile_failed'
                """
            )
            connection.execute(
                """
                UPDATE listings
                SET sale_status = 'reserved',
                    reserved_checkout_session_id = 'cs_test_reconcile_failed',
                    reserved_until = '2020-01-01T00:00:00Z'
                WHERE id = ?
                """,
                (listing_id,),
            )
            connection.commit()

        app.STRIPE_SECRET_KEY = "sk_test_reconcile"

        def fake_stripe_request(method, path, data=None):
            if path == "/checkout/sessions/cs_test_reconcile_failed":
                return {
                    "id": "cs_test_reconcile_failed",
                    "payment_intent": "pi_test_reconcile_failed",
                    "payment_status": "unpaid",
                    "status": "complete",
                }
            if path == "/payment_intents/pi_test_reconcile_failed":
                return {
                    "id": "pi_test_reconcile_failed",
                    "status": "requires_payment_method",
                }
            raise AssertionError(f"Unexpected Stripe request: {method} {path}")

        app.stripe_request = fake_stripe_request
        items = app.ElevenZeroHandler.fetch_listings(None)

        listing = next(item for item in items if item["id"] == listing_id)
        self.assertEqual(listing["sale_status"], "available")
        with sqlite3.connect(app.DB_PATH) as connection:
            order_state = connection.execute(
                """
                SELECT status, stripe_session_status
                FROM orders
                WHERE stripe_checkout_session_id = ?
                """,
                ("cs_test_reconcile_failed",),
            ).fetchone()
        self.assertEqual(order_state, ("payment_failed", "complete"))

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
