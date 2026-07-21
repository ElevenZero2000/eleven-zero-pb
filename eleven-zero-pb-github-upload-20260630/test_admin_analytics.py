import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import app
from app import build_sales_analytics, parse_activity_datetime


class AdminSalesAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 21, 18, 0, tzinfo=timezone.utc)
        self.orders = [
            {
                "buyer_user_id": 1,
                "amount_total_cents": 1000,
                "created_at": "2026-07-21T12:00:00Z",
                "completed_at": "2026-07-21T12:05:00Z",
            },
            {
                "buyer_user_id": 1,
                "amount_total_cents": 2000,
                "created_at": "2026-07-21T14:00:00Z",
                "completed_at": "2026-07-21T14:05:00Z",
            },
            {
                "buyer_user_id": 2,
                "amount_total_cents": 3000,
                "created_at": "2026-07-20T16:00:00Z",
                "completed_at": None,
            },
            {
                "buyer_user_id": 3,
                "amount_total_cents": 4000,
                "created_at": "2026-06-10T16:00:00Z",
                "completed_at": "2026-06-10T16:05:00Z",
            },
            {
                "buyer_user_id": 4,
                "amount_total_cents": 5000,
                "created_at": "2026-02-10T16:00:00Z",
                "completed_at": "2026-02-10T16:05:00Z",
            },
            {
                "buyer_user_id": 5,
                "amount_total_cents": 6000,
                "created_at": "2025-11-10T16:00:00Z",
                "completed_at": "2025-11-10T16:05:00Z",
            },
        ]

    def test_daily_view_counts_unique_buyers_and_paid_orders(self):
        analytics = build_sales_analytics(self.orders, self.now)

        today = analytics["day"]["buckets"][-1]
        yesterday = analytics["day"]["buckets"][-2]

        self.assertEqual(today["buyers"], 1)
        self.assertEqual(today["orders"], 2)
        self.assertEqual(today["revenueCents"], 3000)
        self.assertEqual(yesterday["buyers"], 1)
        self.assertEqual(analytics["day"]["summary"]["buyers"], 2)
        self.assertEqual(analytics["day"]["summary"]["orders"], 3)

    def test_month_quarter_and_year_views_use_correct_windows(self):
        analytics = build_sales_analytics(self.orders, self.now)

        july = analytics["month"]["buckets"][-1]
        q3 = analytics["quarter"]["buckets"][-1]
        year = analytics["year"]["buckets"][-1]

        self.assertEqual((july["buyers"], july["orders"]), (2, 3))
        self.assertEqual((q3["buyers"], q3["orders"]), (2, 3))
        self.assertEqual((year["buyers"], year["orders"]), (4, 5))
        self.assertEqual(year["revenueCents"], 15000)

    def test_activity_datetime_accepts_utc_and_rejects_invalid_values(self):
        parsed = parse_activity_datetime("2026-07-21T12:05:00Z")

        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertIsNone(parse_activity_datetime("not-a-date"))

    def test_admin_dashboard_returns_real_notifications_and_analytics(self):
        original_db_path = app.DB_PATH
        original_starter_setting = app.ENABLE_STARTER_LISTINGS
        original_demo_setting = app.ENABLE_DEMO_DATA

        with TemporaryDirectory() as temp_dir:
            try:
                app.DB_PATH = Path(temp_dir) / "admin-dashboard.db"
                app.ENABLE_STARTER_LISTINGS = False
                app.ENABLE_DEMO_DATA = False
                app.init_database()

                with app.closing(app.connect_db()) as connection:
                    connection.executemany(
                        """
                        INSERT INTO users (name, email, password_salt, password_hash, created_at)
                        VALUES (?, ?, 'salt', 'hash', ?)
                        """,
                        [
                            ("Buyer One", "buyer@example.com", "2026-07-20T10:00:00Z"),
                            ("Seller One", "seller@example.com", "2026-07-20T10:00:00Z"),
                        ],
                    )
                    connection.execute(
                        """
                        INSERT INTO listings (
                          user_id, brand, model, category, condition, price_usd,
                          location, notes, approval_status, created_at
                        ) VALUES (2, 'JOOLA', 'Perseus', 'power', 'Excellent', 120,
                                  'Arlington, VA', 'Ready to play', 'pending', '2026-07-21T12:00:00Z')
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO orders (
                          listing_id, buyer_user_id, seller_user_id,
                          stripe_checkout_session_id, amount_total_cents,
                          platform_fee_cents, stripe_payment_status,
                          stripe_session_status, status, created_at, completed_at
                        ) VALUES (1, 1, 2, 'cs_test_admin', 12900, 1020,
                                  'paid', 'complete', 'paid',
                                  '2026-07-21T13:00:00Z', '2026-07-21T13:05:00Z')
                        """
                    )
                    connection.commit()

                dashboard = app.ElevenZeroHandler.build_admin_dashboard(None)

                self.assertEqual(dashboard["commerceNotifications"][0]["type"], "purchase")
                self.assertEqual(dashboard["commerceNotifications"][1]["type"], "listing")
                self.assertEqual(dashboard["commerceNotifications"][0]["buyer_name"], "Buyer One")
                current_year = dashboard["salesAnalytics"]["year"]["buckets"][-1]
                self.assertEqual((current_year["buyers"], current_year["orders"]), (1, 1))
            finally:
                app.DB_PATH = original_db_path
                app.ENABLE_STARTER_LISTINGS = original_starter_setting
                app.ENABLE_DEMO_DATA = original_demo_setting


if __name__ == "__main__":
    unittest.main()
