# Eleven Zero PB go-live checklist

This is the simple version of what happens next.

## Where each piece will live

- your website pages and app logic: on hosting, like Render
- your database: on a persistent Render disk
- your domain: with your domain provider, pointed to Render
- payments and seller payouts: in Stripe
- traffic tracking: in Google Analytics

That means the website is not “living on your laptop” once it is deployed. It will live on the hosting service.

## Best first launch path

For your first public version, the cleanest path is:

1. Put this project into GitHub
2. Create a new web service on Render
3. Connect the GitHub repo
4. Add the environment settings from `.env.example`
5. Attach a persistent disk for the database
6. Let Render publish the site
7. Connect your domain
8. Add your Stripe keys
9. Add your Google Analytics ID
10. Test the live site

## Environment settings you will need

- `APP_ENV=production`
- `DATABASE_PATH=/var/data/eleven_zero_pb.db`
- `SESSION_COOKIE_SECURE=true`
- `ENABLE_DEMO_DATA=false`
- `SITE_URL=https://11zeropb.com`
- `SUPPORT_EMAIL=11zeropb@gmail.com`
- `GA_MEASUREMENT_ID=G-SH18CJ4XZD`
- `STRIPE_SECRET_KEY=...`
- `STRIPE_PUBLISHABLE_KEY=pk_live_...`
- `STRIPE_WEBHOOK_SECRET=whsec_...`
- `SHIPPO_API_KEY=shippo_live_...`
- `PLATFORM_FEE_PERCENT=8.5`
- `PAYOUT_PROTECTION_HOURS=24`
- `PAYOUT_RELEASE_CHECK_SECONDS=300`

## Your real domain

Your public domain for this launch is:

- `11zeropb.com`

When you connect the domain in Render, point the root domain there and keep `SITE_URL`
set to `https://11zeropb.com`.

## What is already ready

- homepage
- paddle marketplace
- account system
- trainer directory
- trainer reviews and rating display
- courts page
- interactive court map
- court condition, crowd, and player-level reporting
- seller Stripe onboarding
- Stripe Checkout with separate charges and delayed seller transfers
- prepaid Shippo labels and carrier tracking
- a 24-hour buyer issue window after carrier-confirmed delivery
- privacy page
- terms page

## Required live-payment checks

- Shippo has an active billing method for prepaid labels
- Stripe sends Checkout completion, refund, and dispute events to the production webhook
- the Shippo `track_updated` webhook is active for the production site
- a seller has completed Stripe Connect onboarding
- a test order produces one label, one tracking number, and no immediate seller transfer
- a delivered test order remains protected for 24 hours, then creates only one seller transfer

## What I recommend next

Launch this as a soft beta first.

That means you put it online and let a small group test:

- account creation
- paddle listings
- trainer profiles
- court finder
- reviews

Then we can improve the next layer:

- listing photo uploads
- email notifications
- admin moderation
- full payment testing

## Files to use

- `render.yaml` for the hosting setup
- `.env.example` for environment settings
- `LAUNCH-GUIDE.md` for the fuller explanation
- `privacy.html` and `terms.html` for public trust pages

## Money movement

For new orders, the platform receives the buyer charge. The seller does not receive an
immediate destination charge. After Shippo reports delivery and the 24-hour protection
window ends without an open buyer issue, the app transfers the paddle price minus the
8.5% marketplace commission to the seller's connected Stripe balance. Shipping remains
on the platform to pay for the prepaid label. Stripe then pays the connected balance to
the seller's bank on that account's payout schedule.
