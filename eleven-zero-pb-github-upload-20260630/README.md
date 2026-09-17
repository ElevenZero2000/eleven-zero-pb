# Eleven Zero PB

This folder contains the current live beta build of Eleven Zero PB at
`https://11zeropb.com`.

What is already working:

- account creation, sign in, password reset, and email verification
- expiring sessions with origin and CSRF protections
- moderated paddle listings with real seller photos
- a searchable marketplace, product pages, and a dedicated cart
- Stripe Connect seller onboarding and checkout
- delivery-protected seller proceeds with a 24-hour buyer issue window
- branded buyer confirmation email
- owner moderation, notifications, and sales reporting
- moderated trainer profiles, tenure, ratings, and reviews
- moderated trainer cover photos and five-photo profile galleries
- trainer-client requests, participant-only messages, and lesson scheduling
- a Google-powered courts finder with map pins and community reports
- responsive desktop/mobile navigation and accessibility improvements

Production safeguards:

- anonymous demo/test listings are excluded from the public catalog
- new listings and trainer profiles stay pending until owner approval
- trainer photo replacements stay pending while the last approved photos remain public
- private trainer-client conversations are available only after a trainer accepts a request
- photos are served through lightweight image endpoints instead of embedded in catalog JSON
- HTTPS security headers, secure cookies, rate limits, and no-store API responses
- Google Analytics and search metadata support
- legal, privacy, robots, and sitemap pages

How to run it locally:

1. Open Terminal.
2. Go to this folder.
3. Run:

   `python3 app.py`

4. Open:

   `http://127.0.0.1:8000`

Important files:

- `app.py` — the Python app and API
- `index.html` — marketplace homepage
- `trainers.html` — trainers directory
- `courts.html` — courts finder
- `auth.html` — sign in and account creation
- `account.html` — user dashboard
- `.env.example` — settings template
- `render.yaml` — hosting starter setup
- `LAUNCH-GUIDE.md` — simple next-step guide
- `GO-LIVE-CHECKLIST.md` — short deployment checklist
- `robots.txt` — search engine crawl rules
- `sitemap.xml` — public page index

Important note:

For new purchases, the buyer pays the paddle and prepaid shipping at Stripe Checkout.
The seller's proceeds stay on the Eleven Zero platform until Shippo reports the package
as delivered. The buyer then has 24 hours to report a problem. If no issue is open, the
app creates one idempotent Stripe transfer to the seller's connected Stripe balance;
the seller's bank arrival follows their Stripe payout schedule. Older destination-charge
orders are marked as legacy and are never transferred a second time.

Live label purchasing still requires an active Shippo billing method. If Shippo cannot
create a label or confirm delivery, the seller payout stays on hold for owner review.
Legal pages are product-ready drafts and should be reviewed by qualified counsel before
a large public launch.

Trainer requests, private messages, and lesson scheduling do not process coaching payments
in this release. Trainers and clients remain responsible for agreeing on lesson payment terms.

Deployment note:

For the smoothest Render setup, upload the contents of this folder as the root of your GitHub repo.

### Operational checks

Local regression checks: `python3 -m unittest discover` and
`node --test test_cart.cjs test_listing.cjs`. These use temporary data and mocked
providers, not live orders or charges.

- Public static files use an explicit allowlist. Server code, tests, environment settings,
  databases, repository files, and directory listings must not be accessible over HTTP.
- `GET /api/health` performs a bounded, read-only database readiness check and returns
  HTTP 503 when it fails. It does not create a database or contact payment/shipping providers.
- The owner's Account page includes Website status. Its authenticated
  `/api/admin/system-health` endpoint reports database and background order-processing
  status without exposing credentials. A configured provider is not proof of a successful
  live transaction; connection checks are deliberately not made by this endpoint.
- Background order-processing failures are recorded in server logs with safe issue codes.
  Investigate repeated failures in Render's Logs and the owner status panel before retrying
  financial or shipping actions. Worker history is in memory and resets on a restart.
- `render.yaml` specifies `/api/health` as the health check path. For an existing service
  not managed by this Blueprint, set that path in Render's service health-check settings.
  This repository change alone does not change a manually configured service.
- The owner panel is on-demand visibility, not a paging/uptime service. External alerts,
  database backup restoration, load testing, and a full live purchase-to-delivery test
  remain separate launch checks.
