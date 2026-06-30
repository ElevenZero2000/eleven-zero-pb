# Eleven Zero PB

This folder contains the current live beta build of Eleven Zero PB.

Planned public domain:

- `https://11zeropb.com`

What is already working:

- account creation and sign in
- session-based authentication
- paddle listings
- trainer profiles
- trainer reviews
- account dashboard
- courts finder
- interactive courts map
- court condition, crowd, and player-level reports
- Stripe seller onboarding foundation
- marketplace checkout foundation with seller readiness states

What was added for launch prep:

- production-friendly host and port settings
- safer cookies for HTTPS
- basic security headers
- Google Analytics support through an environment variable
- Stripe Connect environment placeholders
- Render deployment starter file
- environment example file
- launch guide

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

This version is now much closer to a public beta. Stripe seller onboarding and checkout foundations are built in, but live Stripe keys, listing photos, email flows, and admin moderation still need to be connected before a full marketplace launch.

Deployment note:

For the smoothest Render setup, upload the contents of this folder as the root of your GitHub repo.
