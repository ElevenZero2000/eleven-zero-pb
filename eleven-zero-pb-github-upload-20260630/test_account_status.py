"""Account status regressions with a temporary DB and mocked providers only."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

import app


class AccountStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / "account-status.sqlite3"
        patcher = mock.patch.multiple(
            app, DB_PATH=self.db, ENABLE_DEMO_DATA=False, ENABLE_STARTER_LISTINGS=False,
            SITE_URL="https://marketplace.example.test", STRIPE_SECRET_KEY="sk_test_qa_only",
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        network = mock.patch.object(app, "urlopen", side_effect=AssertionError("No external network in tests"))
        network.start()
        self.addCleanup(network.stop)
        app.init_database()
        with sqlite3.connect(self.db) as connection:
            self.seller_id = connection.execute(
                """INSERT INTO users (name,email,password_salt,password_hash,created_at,stripe_account_id)
                   VALUES ('Seller QA','seller@example.test','salt','hash',?,'acct_test_qa')""",
                (app.utc_now(),),
            ).lastrowid
            self.buyer_id = connection.execute(
                """INSERT INTO users (name,email,password_salt,password_hash,created_at)
                   VALUES ('Buyer QA','buyer@example.test','salt','hash',?)""",
                (app.utc_now(),),
            ).lastrowid
            self.listing_id = connection.execute(
                """INSERT INTO listings
                   (user_id,brand,model,category,condition,price_usd,location,notes,approval_status,created_at)
                   VALUES (?,'JOOLA','Perseus','power','Good',150,'Alexandria, VA','QA paddle','approved',?)""",
                (self.seller_id, app.utc_now()),
            ).lastrowid
        self.handler = object.__new__(app.ElevenZeroHandler)

    def test_onboarding_links_include_explicit_return_and_refresh_markers(self):
        for method, marker in [(self.handler.stripe_return_url, "return"), (self.handler.stripe_refresh_url, "refresh")]:
            parsed = urlparse(method())
            self.assertEqual(parsed.netloc, "marketplace.example.test")
            self.assertEqual(parsed.path, "/account.html")
            self.assertEqual(parse_qs(parsed.query), {"stripe_onboarding": [marker]})
            self.assertEqual(parsed.fragment, "seller-payouts")

    def test_stripe_refresh_reads_provider_readiness_and_persists_it(self):
        before = self.handler.fetch_seller_profile(self.seller_id)["sellerProfile"]
        self.assertFalse(before["readyForPayouts"])
        account = {
            "id": "acct_test_qa", "details_submitted": True, "charges_enabled": True,
            "payouts_enabled": True, "requirements": {"currently_due": []},
        }
        with mock.patch.object(app, "stripe_request", return_value=account) as request:
            refreshed = self.handler.fetch_seller_profile(self.seller_id, force_refresh=True)["sellerProfile"]
        request.assert_called_once_with("GET", "/accounts/acct_test_qa")
        self.assertTrue(refreshed["readyForPayouts"])
        self.assertTrue(self.handler.fetch_seller_profile(self.seller_id)["sellerProfile"]["readyForPayouts"])

    def test_incomplete_provider_response_is_not_presented_as_payout_ready(self):
        account = {
            "id": "acct_test_qa", "details_submitted": True, "charges_enabled": True,
            "payouts_enabled": False, "requirements": {"currently_due": ["external_account"]},
        }
        with mock.patch.object(app, "stripe_request", return_value=account):
            refreshed = self.handler.fetch_seller_profile(self.seller_id, force_refresh=True)["sellerProfile"]
        self.assertTrue(refreshed["hasAccount"])
        self.assertFalse(refreshed["readyForPayouts"])
        self.assertEqual(refreshed["requirementsDueCount"], 1)

    def test_admin_purchase_activity_retains_both_payment_status_fields(self):
        with sqlite3.connect(self.db) as connection:
            for index, (status, payment_status) in enumerate([("paid", "paid"), ("processing", "paid"), ("paid", "unpaid"), ("open", "unpaid")]):
                connection.execute(
                    """INSERT INTO orders (
                         listing_id,buyer_user_id,seller_user_id,stripe_checkout_session_id,
                         amount_total_cents,shipping_amount_cents,platform_fee_cents,status,
                         stripe_payment_status,payment_flow,payout_status,created_at
                       ) VALUES (?,?,?,?,15975,975,1275,?,?,'separate_charge_transfer','held_for_delivery',?)""",
                    (self.listing_id, self.buyer_id, self.seller_id, f"cs_test_status_{index}", status, payment_status, app.utc_now()),
                )
        dashboard = self.handler.build_admin_dashboard()
        purchases = {item["stripe_checkout_session_id"]: item for item in dashboard["commerceNotifications"] if item["type"] == "purchase"}
        self.assertEqual(set(purchases), {"cs_test_status_0", "cs_test_status_1", "cs_test_status_2"})
        self.assertEqual(purchases["cs_test_status_0"]["status"], "paid")
        self.assertEqual(purchases["cs_test_status_1"]["status"], "processing")
        self.assertEqual(purchases["cs_test_status_1"]["stripe_payment_status"], "paid")
        self.assertEqual(purchases["cs_test_status_2"]["status"], "paid")
        self.assertEqual(purchases["cs_test_status_2"]["stripe_payment_status"], "unpaid")


if __name__ == "__main__":
    unittest.main()
