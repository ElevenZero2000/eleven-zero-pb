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
- a Google-powered courts finder with map pins and community reports
- responsive desktop/mobile navigation and accessibility improvements

Production safeguards:

- anonymous demo/test listings are excluded from the public catalog
- new listings and trainer profiles stay pending until owner approval
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

Deployment note:

For the smoothest Render setup, upload the contents of this folder as the root of your GitHub repo.
