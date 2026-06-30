# Eleven Zero PB launch guide

You already have a lot of the business setup done:

- domain
- Stripe account
- bank account
- LLC
- tax ID
- Google Analytics
- Zapier
- Gmail

That means the next phase is mainly website launch work.

Your launch domain is:

- `11zeropb.com`

## What this website is right now

This build is a working beta app. It already has:

- accounts
- sign in
- listings
- trainers
- reviews
- courts directory
- interactive map on the courts page
- court condition, crowd, and player-level reports
- Stripe seller onboarding foundation
- marketplace checkout foundation with buyer purchase states

Right now it still runs locally unless you put it on hosting.

## What “putting it online” means

To make it public, we need to:

1. Upload the app to hosting
2. Connect the domain
3. Put the database on a persistent server disk
4. Turn on HTTPS
5. Add analytics ID
6. Test the live domain

## Easiest first public setup

Recommended first hosting path:

- Render for hosting
- this app as the web service
- Render disk for the beta database
- your existing domain connected to Render
- Google Analytics measurement ID added in environment settings

That is the fastest clean path for a first live beta.

## Important business note about Stripe

Having Stripe is great, but for a marketplace you will want **Stripe Connect**, not only a basic Stripe account.

That is what lets:

- buyers pay
- sellers receive their share
- Eleven Zero PB keep a commission

The current beta now includes the marketplace checkout foundation, but it still will not process live payments until your real Stripe keys are added and tested.

## What still needs to be built before full marketplace launch

- live Stripe keys and final Stripe testing
- listing photo uploads
- email notifications
- password reset flow
- admin moderation tools
- stronger anti-spam and fraud controls

The starter legal pages now exist in:

- `privacy.html`
- `terms.html`

Before a full public launch, you should still review those pages with a lawyer so they match your final fee policy, return/refund approach, trainer rules, and state-specific requirements.

## What you can do next

### Option 1: soft beta

Put the site online first and let a small group test:

- account creation
- listing creation
- trainer profiles
- reviews
- court finder

This is the best next move if you want momentum quickly.

### Option 2: full marketplace path

Before going public, add:

- payments
- seller payouts
- images
- moderation
- legal pages

This takes longer, but it is closer to a real public business launch.

## Files added for deployment

- `render.yaml` — starter hosting setup
- `.env.example` — settings template
- `requirements.txt` — build file
- `privacy.html` — starter privacy policy page
- `terms.html` — starter terms page

## Stripe setup note

To turn on the new seller onboarding flow, you will need to add:

- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `PLATFORM_FEE_PERCENT`
- `SUPPORT_EMAIL`

Your current business settings for this build are:

- site URL: `https://11zeropb.com`
- support email: `11zeropb@gmail.com`
- Google Analytics: `G-SH18CJ4XZD`
- commission: `8.5%`

The app already includes the Stripe seller-status flow and onboarding link generation. Once the keys are added, sellers can begin connecting their payout accounts.

## My recommendation

Launch a small beta first, then add payments after the live site is stable.

That gives you:

- a real public website
- real user feedback
- less risk
- a cleaner path into Stripe Connect
