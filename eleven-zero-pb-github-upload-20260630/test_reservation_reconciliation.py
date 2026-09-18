"""Stale provider snapshots must never undo a concurrently confirmed payment."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class ReservationReconciliationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = mock.patch.multiple(
            app, DB_PATH=Path(temporary.name) / "reconciliation.sqlite3",
            ENABLE_DEMO_DATA=False, ENABLE_STARTER_LISTINGS=False,
        )
        settings.start()
        self.addCleanup(settings.stop)
        network = mock.patch.object(app, "urlopen", side_effect=AssertionError("No external network"))
        network.start()
        self.addCleanup(network.stop)
        app.init_database()
        with app.connect_db() as db:
            for uid in (1, 2):
                db.execute(
                    "INSERT INTO users (id,name,email,password_salt,password_hash,created_at) VALUES (?,?,?,'salt','hash',?)",
                    (uid, f"QA {uid}", f"qa{uid}@example.test", app.utc_now()),
                )
            db.execute(
                """INSERT INTO listings (id,user_id,brand,model,category,condition,price_usd,location,notes,
                   approval_status,sale_status,reserved_checkout_session_id,reserved_until,created_at)
                   VALUES (1,1,'JOOLA','QA','control','Good',150,'Arlington, VA','QA','approved',
                   'reserved','cs_test_reconciliation','2000-01-01T00:00:00Z',?)""", (app.utc_now(),),
            )
            db.execute(
                """INSERT INTO orders (listing_id,buyer_user_id,seller_user_id,stripe_checkout_session_id,
                   amount_total_cents,platform_fee_cents,status,stripe_payment_status,stripe_session_status,created_at)
                   VALUES (1,2,1,'cs_test_reconciliation',15975,1275,'open','unpaid','open',?)""", (app.utc_now(),),
            )
        self.handler = object.__new__(app.ElevenZeroHandler)

    def row(self, table):
        with app.connect_db() as db:
            return dict(db.execute(f"SELECT * FROM {table} WHERE id=1").fetchone())

    def reset_open_order(self):
        with app.connect_db() as db:
            db.execute("UPDATE orders SET status='open',stripe_payment_status='unpaid',stripe_session_status='open'")

    def confirm_payment(self, status, payment_status):
        with app.connect_db() as db:
            db.execute(
                "UPDATE orders SET status=?,stripe_payment_status=?,stripe_session_status='complete'",
                (status, payment_status),
            )

    def test_expired_snapshot_cannot_overwrite_either_paid_signal(self):
        for status, payment_status in [("paid", "paid"), ("paid", "unpaid"), ("processing", "paid")]:
            with self.subTest(status=status, payment_status=payment_status):
                self.reset_open_order()

                def expired_snapshot(*args):
                    self.confirm_payment(status, payment_status)
                    return {"id": "cs_test_reconciliation", "status": "expired", "payment_status": "unpaid"}

                with mock.patch.object(app, "stripe_request", side_effect=expired_snapshot) as provider:
                    # Exercises the real caller too: a rejected stale write must
                    # not recurse indefinitely while webhook fulfillment is pending.
                    listing = self.handler.fetch_listing_checkout_row(1)
                self.assertEqual(provider.call_count, 1)
                self.assertEqual(listing["sale_status"], "reserved")
                order = self.row("orders")
                self.assertEqual((order["status"], order["stripe_payment_status"]), (status, payment_status))
                self.assertEqual(order["stripe_session_status"], "complete")

    def test_failed_intent_snapshot_cannot_overwrite_concurrent_paid_order(self):
        for intent_status in ("canceled", "requires_payment_method"):
            for status, payment_status in [("paid", "unpaid"), ("processing", "paid")]:
                with self.subTest(intent_status=intent_status, status=status, payment_status=payment_status):
                    self.reset_open_order()

                    def stale_snapshot(method, path):
                        if path.startswith("/checkout/sessions/"):
                            return {"id": "cs_test_reconciliation", "status": "complete", "payment_status": "unpaid", "payment_intent": "pi_test_qa"}
                        self.confirm_payment(status, payment_status)
                        return {"id": "pi_test_qa", "status": intent_status}

                    with mock.patch.object(app, "stripe_request", side_effect=stale_snapshot) as provider:
                        listing = self.handler.fetch_listing_checkout_row(1)
                    self.assertEqual(provider.call_count, 2)
                    self.assertEqual(listing["sale_status"], "reserved")
                    order = self.row("orders")
                    self.assertEqual((order["status"], order["stripe_payment_status"]), (status, payment_status))

    def test_confirmed_unpaid_expiry_still_releases_the_reservation(self):
        with mock.patch.object(app, "stripe_request", return_value={"status": "expired", "payment_status": "unpaid"}):
            self.assertTrue(app.reconcile_expired_listing_reservation(self.row("listings")))
        self.assertEqual(self.row("orders")["status"], "expired")
        self.assertEqual(self.row("listings")["sale_status"], "available")

    def test_confirmed_failed_intent_still_releases_the_reservation(self):
        with mock.patch.object(app, "stripe_request", side_effect=[
            {"status": "complete", "payment_status": "unpaid", "payment_intent": "pi_test_qa"},
            {"id": "pi_test_qa", "status": "canceled"},
        ]):
            self.assertTrue(app.reconcile_expired_listing_reservation(self.row("listings")))
        self.assertEqual(self.row("orders")["status"], "payment_failed")
        self.assertEqual(self.row("listings")["sale_status"], "available")


if __name__ == "__main__":
    unittest.main()
