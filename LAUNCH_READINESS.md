# DocCraft Pro — Production Launch Checklist

Last reviewed: 2026-10-23

This checklist deliberately separates code readiness from account/provider activation. Do not announce paid production billing as complete until the live provider and credit fulfillment are verified.

## 1. Production billing

### Code path present
- [x] Paystack checkout initialization uses the server-side secret key and returns a hosted checkout URL.
- [x] Payment verification calls Paystack's server-side transaction verification endpoint.
- [x] The webhook endpoint is `POST /api/payments/webhook`; Paystack events are authenticated using the `x-paystack-signature` HMAC.
- [x] Credit grants check the stored transaction amount, currency, and active package and avoid issuing a second grant for an already-granted transaction.
- [x] Checkout retry handling was tightened so a failed/incomplete initialization is not returned as a successful checkout with a missing URL.
- [x] New paid checkout requests now respect `BILLING_ENABLED`; when disabled, the endpoint returns a controlled 503 instead of initializing a payment.
- [x] Production Paystack key guard rejects a test secret when billing is enabled on the HTTPS production URL.
- [x] Added a focused pytest file for the production key guard. CI execution is not confirmed in this session.
- [x] Added draft privacy and terms documents under `docs/`; these are deliberately drafts and must not be published until their owner-specific placeholders and actual practices are confirmed.

### Still required in the live accounts
- [ ] Paystack account is approved for live payments.
- [ ] Render's `PAYSTACK_SECRET_KEY` is the **live secret key**, not a test key. Never place keys in source control or send them in chat.
- [ ] Render environment includes `PAYMENT_PROVIDER=paystack`, `APP_BASE_URL=https://doccraft-pro.onrender.com`, production `DATABASE_URL`, `SECRET_KEY`, `OPENAI_API_KEY`, and `BILLING_ENABLED=true`.
- [ ] Configure the Paystack webhook URL as `https://doccraft-pro.onrender.com/api/payments/webhook`.
- [ ] Ensure the database schema and credit packages are initialized in the production database.
- [ ] Deploy the latest commit to Render.
- [ ] Verify one genuine, authorized live transaction end-to-end: provider confirms success, the transaction matches expected amount/currency, the intended wallet receives the package credits once, and a duplicate webhook/verification does not grant credits again.

**Current status:** Code paths exist, but live billing is **not yet verified**. A browser console error from Paystack's hosted checkout alone cannot prove whether the account is in test mode or live mode; the Paystack account activation status and the key configured in Render determine this.

## 2. Website URL and search visibility

- [x] Public base URL is configured in the code: `https://doccraft-pro.onrender.com`.
- [x] The app defines `/health`, `/robots.txt`, and `/sitemap.xml` routes.
- [x] The main HTML contains a Google site-verification meta tag and page metadata.
- [ ] Confirm the latest Render deployment is healthy and the public health/packages endpoints return expected responses.
- [ ] Confirm the Google Search Console property is verified, submit `https://doccraft-pro.onrender.com/sitemap.xml`, and request indexing of the homepage.
- [ ] Publish accessible Privacy Policy and Terms pages that accurately describe data collection, retention, payments, refunds, and contact details. Do not publish placeholder legal claims.

## 3. Google Play Store

The current repository is a Flask web app; the presence of a public website does not by itself produce an Android App Bundle.

- [ ] Decide and implement an Android delivery route (for example, a properly configured Trusted Web Activity or native Android app) and generate a signed Android App Bundle.
- [ ] Prepare Play Console app details, screenshots, icon, feature graphic, support contact, privacy policy URL, Data safety answers, content rating, app-access instructions, and testing/release tracks.
- [ ] Resolve billing policy before Play submission: DocCraft credits are digital goods used inside the app. Google Play's applicable billing rules and any eligible regional/program exceptions must be checked for the chosen app and distribution model. A website's Paystack checkout should not simply be assumed to satisfy Play Billing requirements for digital credits inside a Play-distributed app.
- [ ] Complete Play Console testing and address any account-specific testing requirements before production rollout.

## Release rule

Do not mark the launch complete based only on a successful checkout redirect. Completion means a confirmed live payment, correctly verified server-side, with exactly one matching credit grant, plus a healthy deployment and the required platform compliance.
