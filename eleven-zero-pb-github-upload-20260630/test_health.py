"""HTTP-level static boundary and observational health regression tests.

All writes use temporary databases/files; providers and payment actions are
mocked where relevant. No worker is started by the HTTP fixture.
"""

import base64
import http.client
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from http.cookies import SimpleCookie
from pathlib import Path
from unittest import mock

import app


REAL_APP_ROOT = app.APP_ROOT
SECRET = "private-marker-sk_live_NEVER_PUBLIC"
IMAGE_DATA = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z4X0AAAAASUVORK5CYII="
)


class HealthAndStaticHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "public"
        self.root.mkdir()
        self.db = self.root / "data" / "private.db"
        patcher = mock.patch.multiple(
            app, APP_ROOT=self.root, DB_PATH=self.db, ENABLE_DEMO_DATA=False,
            ENABLE_STARTER_LISTINGS=False, WORKER_HEALTH={},
            ADMIN_EMAILS={"owner@example.test"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        app.init_database()
        for name in (
            "app.py", "test_health.py", "test_cart.cjs", ".env", ".env.production",
            "requirements.txt", "render.yaml", "README.md", "unreviewed.html",
            "config.js", "settings.json", ".git/config", "assets/.env",
            "assets/source.py", "assets/private.db", "assets/config.json",
            "assets/.private/photo.png", "assets/nested/secret.txt",
        ):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SECRET)
        for name in ("index.html", "sell.html", "app.js", "seller-camera.js", "styles.css", "paddle-catalog.json", "robots.txt", "sitemap.xml"):
            (self.root / name).write_text("public-" + name)
        (self.root / "assets" / "logo.png").write_bytes(IMAGE_DATA)
        (self.root / "assets" / "nested" / "photo.webp").write_bytes(IMAGE_DATA)
        self.owner_id = self.create_user("owner@example.test", "owner-session")
        self.member_id = self.create_user("member@example.test", "member-session")
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.ElevenZeroHandler)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.server_thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)

    def create_user(self, email, token):
        with sqlite3.connect(self.db) as connection:
            user_id = connection.execute(
                """INSERT INTO users (name, email, password_salt, password_hash, created_at)
                   VALUES ('Test User', ?, 'salt', 'hash', ?)""", (email, app.utc_now())
            ).lastrowid
            connection.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, user_id, app.utc_now()),
            )
        return user_id

    def request(self, path, method="GET", token=None, *, csrf=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            headers = {"Cookie": f"{app.SESSION_COOKIE}={token}"} if token else {}
            if csrf is not None:
                headers["X-CSRF-Token"] = csrf
            connection.request(method, path, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_signout_invalidates_session_and_expires_only_its_cookie(self):
        status, _, body = self.request("/api/auth/session", token="member-session")
        session = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(session["authenticated"])
        self.assertTrue(session["csrfToken"])

        status, headers, body = self.request(
            "/api/auth/signout", "POST", "member-session", csrf=session["csrfToken"]
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        cookie = SimpleCookie(headers["Set-Cookie"])[app.SESSION_COOKIE]
        self.assertEqual(cookie.value, "")
        self.assertEqual(cookie["max-age"], "0")
        self.assertEqual(cookie["path"], "/")
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        with sqlite3.connect(self.db) as connection:
            self.assertIsNone(connection.execute(
                "SELECT token FROM sessions WHERE token = 'member-session'"
            ).fetchone())
            self.assertIsNotNone(connection.execute(
                "SELECT token FROM sessions WHERE token = 'owner-session'"
            ).fetchone())
            self.assertIsNotNone(connection.execute(
                "SELECT id FROM users WHERE id = ?", (self.member_id,)
            ).fetchone())

        # Even replaying the old browser cookie cannot restore authentication.
        status, _, body = self.request("/api/auth/session", token="member-session")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"authenticated": False, "user": None, "csrfToken": ""})
        self.assertEqual(self.request("/api/account/profile-image", token="member-session")[0], 401)
        self.assertTrue(json.loads(self.request("/api/auth/session", token="owner-session")[2])["authenticated"])

    def test_signout_rejects_wrong_or_missing_csrf_without_ending_session(self):
        session = json.loads(self.request("/api/auth/session", token="member-session")[2])
        self.assertTrue(session["csrfToken"])
        for csrf in (None, "incorrect-csrf-token"):
            with self.subTest(csrf=csrf):
                status, headers, body = self.request(
                    "/api/auth/signout", "POST", "member-session", csrf=csrf
                )
                self.assertEqual(status, 403)
                self.assertIn("error", json.loads(body))
                self.assertNotIn("Set-Cookie", headers)
                with sqlite3.connect(self.db) as connection:
                    self.assertIsNotNone(connection.execute(
                        "SELECT token FROM sessions WHERE token = 'member-session'"
                    ).fetchone())
                self.assertTrue(json.loads(self.request("/api/auth/session", token="member-session")[2])["authenticated"])

    def test_sensitive_files_and_directories_are_not_public_get_or_head(self):
        paths = (
            "/app.py", "/test_health.py", "/test_cart.cjs", "/.env", "/.env.production",
            "/.git/config", "/.git/", "/requirements.txt", "/render.yaml", "/README.md",
            "/unreviewed.html", "/config.js", "/settings.json", "/data/private.db",
            "/data/", "/assets/", "/assets/nested/", "/assets/.env", "/assets/source.py",
            "/assets/private.db", "/assets/config.json", "/assets/.private/photo.png",
            "/assets/nested/secret.txt", "/does-not-exist", "/app.py?download=1",
        )
        for method in ("GET", "HEAD"):
            for path in paths:
                with self.subTest(method=method, path=path):
                    status, headers, body = self.request(path, method)
                    self.assertEqual(status, 404)
                    self.assertNotIn(SECRET.encode(), body)
                    self.assertNotIn(str(self.root).encode(), body)
                    self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                    if method == "HEAD":
                        self.assertEqual(body, b"")

    def test_encoded_traversal_and_noncanonical_paths_are_rejected(self):
        paths = (
            "/%61pp.py", "/%2eenv", "/assets/../app.py", "/assets/../index.html",
            "/assets/%2e%2e/app.py", "/assets/%252e%252e/app.py", "/assets/%2flogo.png",
            "/assets//logo.png", "/assets/./logo.png", "/assets/..%5capp.py",
            "/assets/logo.png%00.py", "/assets/logo.png;anything", "/%69ndex.html",
            "/assets\\logo.png", "/index.html/", "/index.html;anything",
        )
        for method in ("GET", "HEAD"):
            for path in paths:
                with self.subTest(method=method, path=path):
                    self.assertEqual(self.request(path, method)[0], 404)

    def test_symlink_files_and_directories_are_not_public(self):
        outside = Path(self.temp_dir.name) / "secret.png"
        outside.write_text(SECRET)
        (self.root / "assets" / "escape.png").symlink_to(outside)
        (self.root / "assets" / "internal.png").symlink_to(self.root / ".env")
        (self.root / "assets" / "outside").symlink_to(outside.parent, target_is_directory=True)
        (self.root / "shop.html").symlink_to(outside)
        for method in ("GET", "HEAD"):
            for path in ("/assets/escape.png", "/assets/internal.png", "/assets/outside/secret.png", "/shop.html"):
                with self.subTest(method=method, path=path):
                    self.assertEqual(self.request(path, method)[0], 404)

    def test_all_shipped_browser_assets_are_still_served(self):
        with mock.patch.object(app, "APP_ROOT", REAL_APP_ROOT):
            paths = ["/"] + ["/" + name for name in app.PUBLIC_ROOT_FILES]
            paths += ["/" + str(path.relative_to(REAL_APP_ROOT)) for path in (REAL_APP_ROOT / "assets").rglob("*") if path.is_file()]
            for path in paths:
                with self.subTest(path=path):
                    status, headers, body = self.request(path + "?v=cache-bust")
                    self.assertEqual(status, 200)
                    self.assertTrue(body)
                    head_status, head_headers, head_body = self.request(path, "HEAD")
                    self.assertEqual(head_status, 200)
                    self.assertEqual(head_headers["Content-Length"], headers["Content-Length"])
                    self.assertEqual(head_body, b"")

    def test_camera_is_allowed_only_on_the_successful_selling_document(self):
        for method in ("GET", "HEAD"):
            for path in ("/sell.html", "/sell.html?fresh=camera-test"):
                with self.subTest(method=method, path=path):
                    status, headers, body = self.request(path, method)
                    self.assertEqual(status, 200)
                    self.assertEqual(headers["Content-Type"], "text/html")
                    self.assertEqual(headers["Permissions-Policy"], "geolocation=(), microphone=(), camera=(self)")
                    self.assertEqual(headers["Content-Security-Policy"], app.build_content_security_policy())
                    self.assertEqual(headers["X-Frame-Options"], "DENY")
                    self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                    self.assertIn("no-store", headers["Cache-Control"])
                    if method == "HEAD":
                        self.assertEqual(body, b"")

    def test_camera_script_is_public_javascript_without_camera_permissions(self):
        for method in ("GET", "HEAD"):
            with self.subTest(method=method):
                status, headers, body = self.request("/seller-camera.js?v=camera-test", method)
                self.assertEqual(status, 200)
                self.assertIn(headers["Content-Type"], {"text/javascript", "application/javascript"})
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["Permissions-Policy"], "geolocation=(), microphone=(), camera=()")
                self.assertEqual(body, b"public-seller-camera.js" if method == "GET" else b"")

    def test_camera_remains_blocked_on_other_documents_apis_and_errors(self):
        for method in ("GET", "HEAD"):
            for path in ("/", "/index.html", "/app.js", "/api/paddle-catalog", "/missing.html", "/sell.html;not-document", "/%73ell.html"):
                with self.subTest(method=method, path=path):
                    _, headers, _ = self.request(path, method)
                    self.assertEqual(headers["Permissions-Policy"], "geolocation=(), microphone=(), camera=()")
                    self.assertEqual(headers["Content-Security-Policy"], app.build_content_security_policy())
        # Rejected POSTs and unavailable selling documents must not grant it.
        self.assertEqual(self.request("/sell.html", "POST")[1]["Permissions-Policy"], "geolocation=(), microphone=(), camera=()")
        (self.root / "sell.html").unlink()
        status, headers, _ = self.request("/sell.html")
        self.assertEqual(status, 404)
        self.assertEqual(headers["Permissions-Policy"], "geolocation=(), microphone=(), camera=()")

    def test_nested_asset_is_allowed_and_api_catalog_still_works(self):
        self.assertEqual(self.request("/assets/nested/photo.webp")[2], IMAGE_DATA)
        status, _, body = self.request("/api/paddle-catalog")
        self.assertEqual(status, 200)
        self.assertIn("brands", json.loads(body))
        self.assertEqual(self.request("/api/unknown")[0], 404)

    def test_api_image_authorization_is_preserved_for_get_and_head(self):
        image = "data:image/png;base64," + base64.b64encode(IMAGE_DATA).decode()
        with sqlite3.connect(self.db) as connection:
            listing_id = connection.execute(
                """INSERT INTO listings (user_id, brand, model, category, condition,
                   price_usd, location, notes, image_data_json, approval_status, created_at)
                   VALUES (?, 'Test', 'Paddle', 'control', 'Good', 50, 'Test', '', ?, 'pending', ?)""",
                (self.member_id, json.dumps([image]), app.utc_now()),
            ).lastrowid
        path = f"/api/listings/{listing_id}/images/0"
        for method in ("GET", "HEAD"):
            self.assertEqual(self.request(path, method)[0], 404)
            for token in ("member-session", "owner-session"):
                status, headers, body = self.request(path, method, token)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "image/png")
                self.assertEqual(body, IMAGE_DATA if method == "GET" else b"")
        with sqlite3.connect(self.db) as connection:
            connection.execute("UPDATE listings SET approval_status = 'approved' WHERE id = ?", (listing_id,))
        self.assertEqual(self.request(path)[2], IMAGE_DATA)
        self.assertEqual(self.request("/api/account/profile-image")[0], 401)
        self.assertEqual(self.request("/api/account/profile-image", "HEAD")[0], 401)

    def test_head_cannot_trigger_checkout_or_dashboard_actions(self):
        with mock.patch.object(app.ElevenZeroHandler, "handle_checkout_session_status") as checkout:
            with mock.patch.object(app.ElevenZeroHandler, "build_admin_dashboard") as dashboard:
                for path in ("/api/checkout/session-status?sessionId=secret", "/api/admin/dashboard"):
                    self.assertEqual(self.request(path, "HEAD", "owner-session")[0], 405)
                checkout.assert_not_called()
                dashboard.assert_not_called()

    def test_public_health_is_read_only_and_never_calls_providers_or_payments(self):
        before = self.db.read_bytes()
        before_mtime = self.db.stat().st_mtime_ns
        with mock.patch.object(app, "reconcile_order_tracking_and_payouts") as reconcile, \
             mock.patch.object(app, "release_seller_transfer_for_order") as payout, \
             mock.patch.object(app, "urlopen") as external, \
             mock.patch.object(app, "init_database") as init:
            status, headers, body = self.request("/api/health")
            self.assertEqual(status, 200)
            self.assertEqual(set(json.loads(body)), {"ok", "time"})
            self.assertTrue(json.loads(body)["ok"])
            self.assertIn("no-store", headers["Cache-Control"])
            self.assertEqual(self.request("/api/health", "HEAD")[0], 200)
            self.request("/api/admin/system-health", token="owner-session")
            for action in (reconcile, payout, external, init):
                action.assert_not_called()
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.db.stat().st_mtime_ns, before_mtime)

    def test_readiness_connection_enforces_read_only_access(self):
        with closing(app.connect_health_db()) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM sessions")

    def test_missing_corrupt_or_incomplete_database_reports_generic_503(self):
        missing = self.root / "missing-secret-directory" / "secret.sqlite"
        corrupt = self.root / "corrupt-private.db"
        corrupt.write_bytes(SECRET.encode())
        empty = self.root / "empty.db"
        with sqlite3.connect(empty):
            pass
        for db_path in (missing, corrupt, empty):
            with self.subTest(database=db_path.name), mock.patch.object(app, "DB_PATH", db_path):
                with self.assertLogs(app.LOGGER, level="WARNING"):
                    status, _, body = self.request("/api/health")
                    self.assertEqual(self.request("/api/health", "HEAD")[0], 503)
                self.assertEqual(status, 503)
                self.assertEqual(set(json.loads(body)), {"ok", "time"})
                self.assertFalse(json.loads(body)["ok"])
                self.assertNotIn(db_path.name.encode(), body)
                self.assertNotIn(SECRET.encode(), body)
        self.assertFalse(missing.exists())
        self.assertFalse(missing.parent.exists())

    def test_database_lock_has_bounded_readiness_timeout(self):
        with sqlite3.connect(self.db) as connection:
            connection.execute("BEGIN EXCLUSIVE")
            started = time.monotonic()
            with self.assertLogs(app.LOGGER, level="WARNING"):
                status, _, body = self.request("/api/health")
            elapsed = time.monotonic() - started
            self.assertEqual(status, 503)
            self.assertLess(elapsed, 1.5)
            self.assertNotIn(b"locked", body)

    def test_admin_health_requires_current_owner_session(self):
        for method in ("GET", "HEAD"):
            self.assertEqual(self.request("/api/admin/system-health", method)[0], 401)
            self.assertEqual(self.request("/api/admin/system-health", method, "invalid")[0], 401)
            self.assertEqual(self.request("/api/admin/system-health", method, "member-session")[0], 403)
            self.assertEqual(self.request("/api/admin/system-health", method, "owner-session")[0], 200)
        with sqlite3.connect(self.db) as connection:
            connection.execute("UPDATE sessions SET created_at = '2000-01-01T00:00:00Z' WHERE token = 'owner-session'")
        self.assertEqual(self.request("/api/admin/system-health", token="owner-session")[0], 401)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM sessions WHERE token = 'owner-session'").fetchone()[0], 1)

    def test_suspended_owner_is_not_authorized(self):
        with sqlite3.connect(self.db) as connection:
            connection.execute("UPDATE users SET account_status = 'suspended' WHERE id = ?", (self.owner_id,))
        self.assertEqual(self.request("/api/admin/system-health", token="owner-session")[0], 401)

    def test_admin_health_reports_configured_not_validated_without_secrets(self):
        with mock.patch.multiple(
            app, STRIPE_SECRET_KEY=SECRET, STRIPE_PUBLISHABLE_KEY="pk_test_public",
            STRIPE_WEBHOOK_SECRET=SECRET, SHIPPO_API_KEY=SECRET,
            SMTP_USERNAME=SECRET, SMTP_PASSWORD=SECRET, GOOGLE_PLACES_API_KEY=SECRET,
        ):
            app.worker_health_started("orderMaintenance")
            app.worker_health_finished("orderMaintenance", error_code="maintenance_pass_failed")
            status, _, body = self.request("/api/admin/system-health", token="owner-session")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["database"], {"status": "ready", "readOnly": True})
        for provider in payload["providers"].values():
            self.assertTrue(provider["configured"])
            self.assertEqual(provider["validation"], "not_checked")
        worker = payload["workers"]["orderMaintenance"]
        self.assertEqual(worker["status"], "error")
        self.assertEqual(worker["consecutiveFailures"], 1)
        self.assertTrue(worker["lastFailureAt"])
        self.assertIn("trackingFailures", worker["lastResult"])
        self.assertIn("payoutFailures", worker["lastResult"])
        for sensitive in (SECRET, str(self.db), "owner@example.test", "owner-session"):
            self.assertNotIn(sensitive.encode(), body)

    def test_admin_can_inspect_schema_failure_if_session_tables_work(self):
        with sqlite3.connect(self.db) as connection:
            connection.execute("DROP TABLE orders")
        with self.assertLogs(app.LOGGER, level="WARNING"):
            status, _, body = self.request("/api/admin/system-health", token="owner-session")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "unavailable")
        self.assertNotIn(b"orders", body)
        self.assertNotIn(str(self.db).encode(), body)

    def test_worker_failure_success_and_stale_state_are_observable(self):
        app.worker_health_started("orderMaintenance")
        app.worker_health_finished("orderMaintenance", error_code="maintenance_pass_failed")
        failed_at = app.worker_health_snapshot("orderMaintenance", 60)["lastFailureAt"]
        result = {"refreshed": 2, "released": 0, "trackingFailures": 0, "payoutFailures": 0}
        app.worker_health_started("orderMaintenance")
        app.worker_health_finished("orderMaintenance", result=result)
        state = app.worker_health_snapshot("orderMaintenance", 60)
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["consecutiveFailures"], 0)
        self.assertEqual(state["lastFailureAt"], failed_at)
        self.assertTrue(state["lastSuccessAt"])
        self.assertEqual(state["lastResult"], result)
        app.WORKER_HEALTH["orderMaintenance"]["lastStartedAt"] = "2000-01-01T00:00:00Z"
        self.assertEqual(app.worker_health_snapshot("orderMaintenance", 60)["status"], "stale")

    def test_worker_records_failures_and_logs_no_raw_provider_errors(self):
        with mock.patch.object(app, "ensure_shippo_tracking_webhook", side_effect=ValueError(SECRET)), \
             mock.patch.object(app, "reconcile_order_tracking_and_payouts", side_effect=ValueError(SECRET)), \
             mock.patch.object(app.time, "sleep", side_effect=StopIteration):
            with self.assertLogs(app.LOGGER, level="WARNING") as logs:
                with self.assertRaises(StopIteration):
                    app.maintenance_worker()
        for record in logs.records:
            payload = json.loads(record.getMessage())
            self.assertIn("event", payload)
            self.assertNotIn(SECRET, record.getMessage())
        self.assertEqual(app.worker_health_snapshot("orderMaintenance", 60)["status"], "error")
        self.assertEqual(app.worker_health_snapshot("shippoWebhook", 60)["status"], "error")

    def test_worker_partial_failures_are_not_reported_as_success(self):
        result = {"refreshed": 1, "released": 0, "trackingFailures": 2, "payoutFailures": 1}
        with mock.patch.object(app, "ensure_shippo_tracking_webhook", return_value={"configured": False}), \
             mock.patch.object(app, "reconcile_order_tracking_and_payouts", return_value=result), \
             mock.patch.object(app.time, "sleep", side_effect=StopIteration):
            with self.assertLogs(app.LOGGER, level="WARNING"):
                with self.assertRaises(StopIteration):
                    app.maintenance_worker()
        state = app.worker_health_snapshot("orderMaintenance", 60)
        self.assertEqual(state["status"], "degraded")
        self.assertEqual(state["lastResult"], result)
        self.assertIsNone(state["lastSuccessAt"])

    def test_reconciliation_counts_failed_tracking_and_payout_jobs(self):
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                """INSERT INTO orders (
                   stripe_checkout_session_id, amount_total_cents, platform_fee_cents,
                   status, stripe_payment_status, payment_flow, shippo_transaction_id,
                   tracking_number, tracking_status, payout_status, payout_release_at, created_at
                   ) VALUES ('cs_test', 10000, 850, 'paid', 'paid', 'separate_charge_transfer',
                   'test-transaction', 'test-tracking', 'DELIVERED', 'release_scheduled',
                   '2000-01-01T00:00:00Z', ?)""", (app.utc_now(),)
            )
        with mock.patch.object(app, "refresh_shippo_tracking_for_order", side_effect=ValueError(SECRET)), \
             mock.patch.object(app, "release_seller_transfer_for_order", return_value={"payout_status": "attention_needed"}), \
             self.assertLogs(app.LOGGER, level="WARNING") as logs:
            result = app.reconcile_order_tracking_and_payouts(limit=1)
        self.assertEqual(result, {"refreshed": 0, "released": 0, "trackingFailures": 1, "payoutFailures": 1})
        for record in logs.records:
            self.assertNotIn(SECRET, record.getMessage())

    def test_webhook_worker_requires_confirmed_registration_not_just_keys(self):
        clean_result = {"refreshed": 0, "released": 0, "trackingFailures": 0, "payoutFailures": 0}
        for registration in ({"configured": False}, {"configured": True, "webhookId": ""}):
            with self.subTest(registration=registration), \
                 mock.patch.object(app, "ensure_shippo_tracking_webhook", return_value=registration), \
                 mock.patch.object(app, "reconcile_order_tracking_and_payouts", return_value=clean_result), \
                 mock.patch.object(app.time, "sleep", side_effect=StopIteration):
                with self.assertLogs(app.LOGGER, level="WARNING"):
                    with self.assertRaises(StopIteration):
                        app.maintenance_worker()
                state = app.worker_health_snapshot("shippoWebhook", 60)
                self.assertEqual(state["status"], "error")
                self.assertEqual(state["lastErrorCode"], "webhook_not_configured")
                self.assertIsNone(state["lastSuccessAt"])
        with mock.patch.object(app, "ensure_shippo_tracking_webhook", return_value={"configured": True, "webhookId": "test-hook"}), \
             mock.patch.object(app, "reconcile_order_tracking_and_payouts", return_value=clean_result), \
             mock.patch.object(app.time, "sleep", side_effect=StopIteration):
            with self.assertRaises(StopIteration):
                app.maintenance_worker()
        self.assertEqual(app.worker_health_snapshot("shippoWebhook", 60)["status"], "ok")
        self.assertTrue(app.worker_health_snapshot("shippoWebhook", 60)["lastSuccessAt"])

    def test_paused_google_places_does_not_degrade_core_marketplace_readiness(self):
        with mock.patch.multiple(
            app, STRIPE_SECRET_KEY=SECRET, STRIPE_PUBLISHABLE_KEY="pk_test_public",
            STRIPE_WEBHOOK_SECRET=SECRET, SHIPPO_API_KEY=SECRET,
            SMTP_HOST="smtp.example.test", SMTP_USERNAME=SECRET, SMTP_PASSWORD=SECRET,
            EMAIL_FROM="test@example.test", GOOGLE_PLACES_API_KEY="",
        ):
            for name in ("orderMaintenance", "shippoWebhook"):
                app.worker_health_started(name)
                app.worker_health_finished(name)
            payload = json.loads(self.request("/api/admin/system-health", token="owner-session")[2])
        self.assertEqual(payload["status"], "ready")
        self.assertFalse(payload["providers"]["googlePlaces"]["configured"])

    def test_request_logs_do_not_include_query_tokens_or_cookie_values(self):
        with self.assertLogs(app.LOGGER, level="INFO") as logs:
            self.request("/api/health?token=" + SECRET, token=SECRET)
        self.assertTrue(logs.records)
        for record in logs.records:
            json.loads(record.getMessage())
            self.assertNotIn(SECRET, record.getMessage())


if __name__ == "__main__":
    unittest.main()
