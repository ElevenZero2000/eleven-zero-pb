"""Local HTTP regressions for label claims and monotonic payment webhooks.

Fixtures live in temporary SQLite databases. All external requests and emails
are disabled; Shippo/Stripe responses are explicit mocks.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import hmac
import http.client
import json
import sqlite3
import threading
import time
import unittest
from unittest import mock

import app
import test_shipping


class LabelConcurrencyTests(unittest.TestCase):
    session_id = "cs_test_label_concurrency"
    quote = {"rate_kind": "live", "shippo_rate_id": "rate_retry", "shippo_shipment_id": "shipment_retry", "carrier": "USPS", "service": "Ground"}

    def setUp(self):
        self.fixture = test_shipping.ManagedShippingTests("test_label_purchase_is_idempotent")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.create_paid_order(self.session_id)
        with sqlite3.connect(app.DB_PATH) as connection:
            seller_id = connection.execute("SELECT seller_user_id FROM orders WHERE stripe_checkout_session_id = ?", (self.session_id,)).fetchone()[0]
            connection.execute("INSERT INTO sessions (token, user_id, csrf_token, created_at) VALUES (?, ?, ?, ?)", ("seller-session", seller_id, "seller-csrf", app.utc_now()))
        for name, kwargs in (
            ("urlopen", {"side_effect": AssertionError("External requests disabled")}),
            ("send_seller_sale_confirmation_for_order", {"return_value": None}),
            ("send_seller_shipping_label_email_for_order", {"side_effect": lambda _session: self.row()}),
        ):
            patcher = mock.patch.object(app, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.ElevenZeroHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def row(self):
        with closing(app.connect_db()) as connection:
            return connection.execute("SELECT * FROM orders WHERE stripe_checkout_session_id = ?", (self.session_id,)).fetchone()

    def update(self, sql, parameters=()):
        with sqlite3.connect(app.DB_PATH) as connection:
            connection.execute(sql, parameters)

    def request(self, path="/api/orders/shipping/retry", payload=None, *, signed=False):
        body = json.dumps(payload or {"sessionId": self.session_id}).encode()
        headers = {"Content-Type": "application/json", "Cookie": f"{app.SESSION_COOKIE}=seller-session", "X-CSRF-Token": "seller-csrf"}
        if signed:
            stamp = str(int(time.time()))
            signature = hmac.new(b"whsec_local_test", stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
            headers["Stripe-Signature"] = f"t={stamp},v1={signature}"
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=6)
        try:
            connection.request("POST", path, body, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    @staticmethod
    def transaction(number=1):
        return {"object_id": f"tx_test_{number}", "status": "SUCCESS", "label_url": f"https://example.invalid/label-{number}.pdf", "tracking_number": f"TEST{number}"}

    def test_overlapping_authenticated_retries_purchase_only_one_label(self):
        entered, release = threading.Event(), threading.Event()

        def slow_transaction(_path, _payload):
            entered.set()
            self.assertTrue(release.wait(4))
            return self.transaction()

        with mock.patch.object(app, "build_shipping_quote_for_listing", return_value=self.quote), \
             mock.patch.object(app, "shippo_request", side_effect=slow_transaction) as purchases, \
             ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(self.request)
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.row()["shipping_status"], "purchasing")
                status, body = self.request()
                self.assertEqual(status, 409)
                self.assertEqual(body["code"], "shipping_label_in_progress")
                self.assertEqual(self.row()["shipping_status"], "purchasing")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3)[0], 200)
            purchases.assert_called_once()
        self.assertEqual(self.row()["shippo_transaction_id"], "tx_test_1")

    def test_overlapping_rate_refreshes_do_not_clobber_the_claim(self):
        entered, release = threading.Event(), threading.Event()

        def slow_quote(*_args):
            entered.set()
            self.assertTrue(release.wait(4))
            return self.quote

        with mock.patch.object(app, "build_shipping_quote_for_listing", side_effect=slow_quote) as quotes, \
             mock.patch.object(app, "shippo_request", return_value=self.transaction()) as purchases, \
             ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(self.request)
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.row()["shipping_status"], "rate_refreshing")
                self.assertEqual(self.request()[0], 409)
                purchases.assert_not_called()
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3)[0], 200)
            quotes.assert_called_once()
            purchases.assert_called_once()

    def test_stale_refresh_success_or_failure_cannot_overwrite_a_recorded_label(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                self.update("UPDATE orders SET shipping_status='attention_needed', shippo_transaction_id='', shippo_label_url=''")

                def completed_elsewhere(*_args):
                    self.update("UPDATE orders SET shipping_status='label_ready', shippo_transaction_id='tx_adopted', shippo_label_url='https://example.invalid/adopted.pdf'")
                    if fails:
                        raise ValueError("Older rate response failed")
                    return self.quote

                with mock.patch.object(app, "build_shipping_quote_for_listing", side_effect=completed_elsewhere):
                    row = app.refresh_shippo_rate_for_order(self.session_id)
                self.assertEqual(row["shipping_status"], "label_ready")
                self.assertEqual(row["shippo_transaction_id"], "tx_adopted")

    def test_unknown_purchase_outcome_blocks_all_further_attempts(self):
        with mock.patch.object(app, "build_shipping_quote_for_listing", return_value=self.quote) as quotes, \
             mock.patch.object(app, "shippo_request", side_effect=TimeoutError("private provider details")) as purchases:
            with self.assertLogs(app.LOGGER, level="WARNING"):
                status, body = self.request()
            self.assertEqual(status, 409)
            self.assertEqual(body["code"], "shipping_label_review_required")
            self.assertEqual(self.row()["shipping_status"], "purchase_unknown")
            self.assertNotIn("private provider details", body["error"])
            self.assertEqual(self.request()[0], 409)
            app.refresh_shippo_rate_for_order(self.session_id)
            app.purchase_shippo_label_for_order(self.session_id)
            purchases.assert_called_once()
            quotes.assert_called_once()

    def test_incomplete_provider_transaction_is_preserved_for_owner_review(self):
        with mock.patch.object(app, "build_shipping_quote_for_listing", return_value=self.quote), \
             mock.patch.object(app, "shippo_request", return_value={"status": "WAITING", "object_id": "tx_waiting"}) as purchases:
            with self.assertLogs(app.LOGGER, level="WARNING"):
                self.assertEqual(self.request()[0], 409)
            self.assertEqual(self.row()["shipping_status"], "purchase_unknown")
            self.assertEqual(self.row()["shippo_transaction_id"], "tx_waiting")
            self.assertEqual(self.request()[0], 409)
            purchases.assert_called_once()

    def test_explicit_rejected_transaction_remains_retryable(self):
        with mock.patch.object(app, "build_shipping_quote_for_listing", return_value=self.quote), \
             mock.patch.object(app, "shippo_request", side_effect=[{"status": "ERROR", "messages": [{"text": "Carrier rejected package"}]}, self.transaction()]) as purchases:
            with self.assertLogs(app.LOGGER, level="WARNING"):
                self.assertEqual(self.request()[0], 502)
            self.assertEqual(self.row()["shipping_status"], "attention_needed")
            self.assertEqual(self.request()[0], 200)
            self.assertEqual(purchases.call_count, 2)

    def test_startup_blocks_interrupted_purchase_but_recovers_rate_refresh(self):
        self.update("UPDATE orders SET shipping_status='purchasing'")
        app.init_database()
        self.assertEqual(self.row()["shipping_status"], "purchase_unknown")
        self.assertEqual(self.request()[0], 409)
        self.update("UPDATE orders SET shipping_status='rate_refreshing'")
        app.init_database()
        self.assertEqual(self.row()["shipping_status"], "attention_needed")
        self.assertIn("rate refresh", self.row()["shipping_error"])

    def test_unpaid_order_cannot_refresh_or_purchase_a_label(self):
        self.update("UPDATE orders SET status='open', stripe_payment_status='unpaid'")
        with mock.patch.object(app, "shippo_request") as purchases, \
             mock.patch.object(app, "build_shipping_quote_for_listing") as quotes:
            self.assertEqual(self.request()[0], 409)
            app.refresh_shippo_rate_for_order(self.session_id)
            app.purchase_shippo_label_for_order(self.session_id)
            purchases.assert_not_called()
            quotes.assert_not_called()

    def test_signed_stale_webhooks_cannot_regress_paid_order_or_release_inventory(self):
        self.update("UPDATE orders SET payout_status='held_for_delivery', stripe_payment_intent_id='pi_paid', completed_at='2026-01-01T00:00:00Z'")
        before = dict(self.row())
        with mock.patch.object(app, "STRIPE_WEBHOOK_SECRET", "whsec_local_test"), \
             mock.patch.object(app, "finalize_paid_order") as finalize, \
             mock.patch.object(app, "release_listing_reservation_for_order") as release:
            for index, event_type in enumerate(("checkout.session.completed", "checkout.session.expired", "checkout.session.async_payment_failed")):
                status, _ = self.request("/api/stripe/webhook", {
                    "id": f"evt_stale_{index}", "type": event_type,
                    "data": {"object": {"id": self.session_id, "payment_status": "unpaid", "status": "complete"}},
                }, signed=True)
                self.assertEqual(status, 200)
                self.assertEqual(dict(self.row()), before)
            finalize.assert_not_called()
            release.assert_not_called()

    def test_paid_webhook_still_advances_order_and_duplicate_is_idempotent(self):
        self.update("UPDATE orders SET status='processing', stripe_payment_status='unpaid', stripe_payment_intent_id='pi_existing'")
        event = {"id": "evt_paid", "type": "checkout.session.async_payment_succeeded", "data": {"object": {"id": self.session_id, "payment_status": "paid", "status": "complete"}}}
        with mock.patch.object(app, "STRIPE_WEBHOOK_SECRET", "whsec_local_test"), \
             mock.patch.object(app, "finalize_paid_order") as finalize:
            self.assertEqual(self.request("/api/stripe/webhook", event, signed=True)[0], 200)
            duplicate = self.request("/api/stripe/webhook", event, signed=True)
            self.assertTrue(duplicate[1]["duplicate"])
            finalize.assert_called_once_with(self.session_id)
        row = self.row()
        self.assertEqual(row["status"], "paid")
        self.assertEqual(row["stripe_payment_status"], "paid")
        self.assertEqual(row["stripe_payment_intent_id"], "pi_existing")
        self.assertTrue(row["completed_at"])


if __name__ == "__main__":
    unittest.main()
