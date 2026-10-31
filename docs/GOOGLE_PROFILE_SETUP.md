# Google profile photo setup

DocCraft links a Google profile only after the user explicitly chooses **Connect Google profile** from the wallet panel.

## Google Cloud configuration

1. In Google Cloud Console, create or select a project.
2. Configure the OAuth consent screen with the DocCraft Pro application name and support/contact details.
3. Create an OAuth client ID of type **Web application**.
4. Add this authorized JavaScript origin:

   `https://doccraft-pro.onrender.com`

5. Add this authorized redirect URI:

   `https://doccraft-pro.onrender.com/auth/google/callback`

6. In Render, open the `doccraft-pro` web service → Environment and add:
   - `GOOGLE_CLIENT_ID` = the OAuth client ID
   - `GOOGLE_CLIENT_SECRET` = the OAuth client secret

   Keep the client secret in Render only. Do not commit it to GitHub or send it in chat.

7. Save the environment changes and allow Render to redeploy.

## User flow and safeguards

- The user enters the email already used for the DocCraft wallet and selects **Connect Google profile**.
- Google sign-in requests only OpenID identity, email, and basic profile scopes.
- DocCraft requires Google's email to be verified and to match the wallet email exactly before showing the profile image.
- If the Google account has no usable profile image, DocCraft shows the wallet email's initial.
- The user can disconnect the Google profile from the same wallet panel.
- DocCraft does not request access to Gmail, Drive, contacts, or other Google data.
- The current implementation keeps the linked profile in the signed browser session; it does not store Google access tokens or change wallet/payment records.

If the OAuth consent screen is in Testing mode, add the intended Google account as a test user until the app's consent configuration is ready for production.
