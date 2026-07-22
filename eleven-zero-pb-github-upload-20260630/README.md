# Eleven Zero PB

This folder contains the current live beta build of Eleven Zero PB at
`https://11zeropb.com`.

What is already working:

- account creation, sign in, password reset, and email verification
- expiring sessions with origin and CSRF protections
- moderated paddle listings with real seller photos
- a searchable marketplace, product pages, and a dedicated cart
- Stripe Connect seller onboarding and checkout
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

Managed shipping and automated label purchasing are intentionally paused until the
Shippo billing method and the complete fulfillment workflow are ready. Do not describe
that portion as fully launched yet. Legal pages are product-ready drafts and should be
reviewed by qualified counsel before a large public launch.

Deployment note:

For the smoothest Render setup, upload the contents of this folder as the root of your GitHub repo.
