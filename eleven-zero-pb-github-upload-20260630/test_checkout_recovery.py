"""Isolated checkout recovery tests: all payment/fulfillment providers mocked."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class CheckoutRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(app, DB_PATH=Path(self.temp.name) / "qa.db",
                                       ENABLE_DEMO_DATA=False, ENABLE_STARTER_LISTINGS=False)
        self.settings.start()
        app.init_database()
        with app.connect_db() as db:
            for uid in (1, 2, 3):
                db.execute("INSERT INTO users (id,name,email,password_salt,password_hash,created_at) VALUES (?,?,?,'salt','hash',?)",
                           (uid, f"QA {uid}", f"qa{uid}@example.test", app.utc_now()))
            db.execute("""INSERT INTO listings (id,user_id,brand,model,category,condition,price_usd,location,notes,
                       approval_status,sale_status,reserved_checkout_session_id,reserved_until,created_at)
                       VALUES (1,1,'JOOLA','QA','control','Good',150,'Arlington, VA','QA','approved',
                       'reserved','cs_test_recovery','2099-01-01T00:00:00Z',?)""", (app.utc_now(),))
            db.execute("""INSERT INTO orders (listing_id,buyer_user_id,seller_user_id,stripe_checkout_session_id,
                       amount_total_cents,shipping_amount_cents,platform_fee_cents,status,stripe_payment_status,stripe_session_status,created_at)
                       VALUES (1,2,1,'cs_test_recovery',15975,975,1275,'open','unpaid','open',?)""", (app.utc_now(),))
        self.handler = object.__new__(app.ElevenZeroHandler)
        self.output = []
        self.handler.send_json = lambda payload, status=200: self.output.append((int(status), payload))
        self.user = {"id": 2, "email": "qa2@example.test"}
        self.session = {"id": "cs_test_recovery", "status": "open", "payment_status": "unpaid",
                        "url": "https://checkout.stripe.com/c/pay/qa-not-real"}
        self.provider = patch.object(app, "stripe_request", side_effect=self.stripe)
        self.provider_mock = self.provider.start()
        self.fulfill = patch.object(app, "finalize_paid_order")
        self.fulfill_mock = self.fulfill.start()

    def tearDown(self):
        self.fulfill.stop()
        self.provider.stop()
        self.settings.stop()
        self.temp.cleanup()

    def stripe(self, method, path, data=None):
        if method == "POST" and path.endswith("/expire"):
            self.session["status"] = "expired"
        return dict(self.session)

    def act(self, action="cancel", user=None):
        self.handler.handle_checkout_reservation(user or self.user, {"sessionId": "cs_test_recovery", "action": action})
        return self.output[-1]

    def listing(self):
        with app.connect_db() as db:
            return dict(db.execute("SELECT * FROM listings WHERE id=1").fetchone())

    def test_reservations_only_include_current_buyer_and_no_private_address(self):
        self.handler.handle_checkout_reservations(self.user)
        item = self.output[-1][1]["items"][0]
        self.assertEqual(item["listingId"], 1)
        self.assertEqual(item["amountTotalCents"], 15975)
        self.assertNotIn("shippingAddress", item)
        self.assertNotIn("checkoutUrl", item)
        self.handler.handle_checkout_reservations({"id": 3})
        self.assertEqual(self.output[-1][1]["items"], [])

    def test_resume_uses_existing_provider_session_not_a_second_payment(self):
        code, body = self.act("resume")
        self.assertEqual(code, 200)
        self.assertEqual(body["checkoutUrl"], self.session["url"])
        self.assertEqual(self.provider_mock.call_count, 1)
        self.assertEqual(self.listing()["sale_status"], "reserved")

    def test_cancel_confirms_expiry_and_releases_once(self):
        code, body = self.act()
        self.assertEqual(code, 200)
        self.assertTrue(body["expired"])
        self.assertEqual(self.listing()["sale_status"], "available")
        count = self.provider_mock.call_count
        self.act()
        self.assertEqual(self.provider_mock.call_count, count)

    def test_other_buyer_cannot_resume_or_cancel(self):
        for action in ("resume", "cancel"):
            self.assertEqual(self.act(action, {"id": 3})[0], 404)
        self.provider_mock.assert_not_called()
        self.assertEqual(self.listing()["sale_status"], "reserved")

    def test_provider_failure_does_not_release_stock(self):
        self.provider_mock.side_effect = RuntimeError("simulated outage")
        self.assertEqual(self.act()[0], 502)
        self.assertEqual(self.listing()["sale_status"], "reserved")

    def test_failed_expiry_does_not_release_open_checkout(self):
        def failure(method, path, data=None):
            if method == "POST":
                raise RuntimeError("simulated expiry failed")
            return dict(self.session)
        self.provider_mock.side_effect = failure
        self.assertEqual(self.act()[0], 409)
        self.assertEqual(self.listing()["sale_status"], "reserved")

    def test_paid_checkout_cannot_be_canceled(self):
        self.session.update(status="complete", payment_status="paid")
        code, body = self.act()
        self.assertEqual(code, 200)
        self.assertEqual(body["order"]["status"], "paid")
        self.assertEqual(body["order"]["listingId"], 1)
        self.assertEqual(body["order"]["amountTotalCents"], 15975)
        self.assertFalse(any(call.args[0] == "POST" for call in self.provider_mock.call_args_list))
        self.assertNotEqual(self.listing()["sale_status"], "available")

    def test_processing_checkout_stays_visible_to_its_buyer(self):
        self.session["status"] = "complete"
        code, body = self.act("resume")
        self.assertEqual(code, 200)
        self.assertEqual(body["order"]["status"], "processing")
        self.handler.handle_checkout_reservations(self.user)
        self.assertEqual(self.output[-1][1]["items"][0]["status"], "processing")
        self.assertEqual(self.listing()["sale_status"], "reserved")

    def test_poll_cannot_regress_concurrently_confirmed_payment(self):
        def late_snapshot(method, path, data=None):
            with app.connect_db() as db:
                db.execute("UPDATE orders SET status='paid',stripe_payment_status='paid',stripe_session_status='complete'")
            return dict(self.session)
        self.provider_mock.side_effect = late_snapshot
        self.handler.handle_checkout_session_status(self.user, "cs_test_recovery")
        self.assertEqual(self.output[-1][1]["order"]["status"], "paid")
        self.assertEqual(self.handler.fetch_order_row("cs_test_recovery")["stripe_payment_status"], "paid")

    def test_changed_reservation_is_never_released(self):
        with app.connect_db() as db:
            db.execute("UPDATE listings SET reserved_checkout_session_id='cs_other'")
        self.assertEqual(self.act()[0], 409)
        self.provider_mock.assert_not_called()
        self.assertEqual(self.listing()["reserved_checkout_session_id"], "cs_other")

    def test_expired_reservation_recovers_without_a_manual_reload(self):
        with app.connect_db() as db:
            db.execute("UPDATE listings SET reserved_until='2000-01-01T00:00:00Z'")
        self.session["status"] = "expired"
        code, body = self.act("resume")
        self.assertEqual(code, 200)
        self.assertTrue(body["expired"])
        self.assertEqual(self.listing()["sale_status"], "available")

    def test_stripe_returns_to_dedicated_cart(self):
        self.handler.current_origin = lambda: "https://example.test"
        self.assertIn("/cart.html?checkout=success", self.handler.checkout_success_url())
        self.assertIn("session_id={CHECKOUT_SESSION_ID}", self.handler.checkout_success_url())
        self.assertIn("/cart.html?checkout=cancel", self.handler.checkout_cancel_url())


if __name__ == "__main__":
    unittest.main()
