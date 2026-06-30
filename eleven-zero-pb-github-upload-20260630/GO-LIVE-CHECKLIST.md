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
- `PLATFORM_FEE_PERCENT=8.5`

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
- seller Stripe onboarding foundation
- checkout foundation
- privacy page
- terms page

## What still needs your real business info

- your real support email
- your live domain
- your live Stripe keys
- your live Google Analytics ID

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

## Last missing item before live payments

The only Stripe item still missing from the production setup is:

- `STRIPE_SECRET_KEY`

Without that key, the site can still go online, but real buyer checkout and seller payout
activation will stay off.
