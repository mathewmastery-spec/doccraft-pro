# DocCraft Pro account verification email setup

The account verification flow uses a single-use link that expires after 30 minutes. The application sends it through Resend's HTTPS API by default; this avoids depending on outbound SMTP from the Render web service.

## Render environment variables

Set these on the `doccraft-pro` web service:

- `EMAIL_PROVIDER=resend`
- `RESEND_API_KEY` = a server-side Resend API key with permission to send email. Keep it only in Render's environment settings; never commit it or paste it into chat.
- `MAIL_DEFAULT_SENDER` = an address on a domain verified in Resend, for example `DocCraft Pro <accounts@your-verified-domain.example>`.
- `APP_BASE_URL=https://doccraft-pro.onrender.com`

Do not remove or rotate existing application, database, AI, or Paystack environment variables. No Gmail connection is required.

## Activate the sender

1. Sign in to Resend and add a domain you control.
2. Publish the DNS records Resend supplies at your domain's DNS host.
3. Wait until Resend marks the domain verified.
4. Create a sending API key and add it to Render as `RESEND_API_KEY`.
5. Set `MAIL_DEFAULT_SENDER` to an address using that verified domain.
6. Save the environment changes and allow Render to redeploy.

Resend's shared `onboarding@resend.dev` sender is for limited testing and is not the production sender for arbitrary customers. A verified sending domain is required for the production flow.

## Verify the production flow

1. Register using an email inbox you control.
2. Confirm the verification email arrives and the link opens the DocCraft Pro site.
3. Confirm the link verifies the account and signs the user in.
4. Sign out, then sign in again with the same account.
5. Try a wrong password and an unverified account; both must be denied.
6. Use resend verification and confirm the newest link works once while the previous link no longer works.
7. Confirm the existing wallet balance remains attached to the same account.

The application never treats an email address typed into a wallet request as proof of ownership. Wallet and Paystack processing are not changed by this email transport.

## Provider troubleshooting

The application logs the HTTP status and provider response when Resend rejects a message, without logging the API key. Check the Render application logs and the Resend email logs. Common causes are an invalid API key, an unverified sender domain, or a sender address that does not belong to the verified domain.
