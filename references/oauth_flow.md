# TikTok OAuth 2.0 Setup

## Prerequisites

- A **business email** (Gmail, Outlook, etc.) — personal TikTok accounts cannot register developer apps
- Your TikTok account username (the one that will post content)

## Step 1: Register a TikTok Developer App

1. Go to https://developers.tiktok.com
2. Sign in with your business email (not your TikTok account)
3. Click **"Create App"** in the top-right
4. Fill in:
   - **App Name:** e.g., "Lubanja TikTok Uploader"
   - **Description:** "Upload video and photo content to TikTok inbox drafts"
   - **Platform:** Web (even though this is a local tool, TikTok requires a platform)
   - **Redirect URL:** `https://localhost:8080/callback` (TikTok requires HTTPS — we won't actually use this redirect for a local CLI tool, but it must be a valid URL)
   - **Scopes:** **Content Posting API** (`video.publish`, `video.upload`)
5. After creation, note your **Client Key** and **Client Secret** from the app dashboard

## Step 2: Add Sandbox Users (Testing Before Audit)

1. In your app dashboard, go to **"Sandbox"** tab
2. Add your TikTok account username as a sandbox user
3. Sandbox mode is limited to 5 users but works immediately without audit
4. This allows testing the Content Posting API before submitting for audit

## Step 3: Get Access & Refresh Tokens

Since this is a local CLI tool, use the OAuth 2.0 authorization code flow manually:

1. Construct the authorization URL:

```
https://www.tiktok.com/v2/auth/authorize/
  ?client_key=YOUR_CLIENT_KEY
  &scope=video.publish,video.upload
  &response_type=code
  &redirect_uri=https://localhost:8080/callback
  &state=your_csrf_token
```

2. Open this URL in a browser. Log in with your TikTok account and authorize the app.
3. You'll be redirected to `https://localhost:8080/callback?code=AUTHORIZATION_CODE&state=...`
4. Copy the `code` parameter from the URL (the browser will show a connection error — that's fine, just copy the code from the address bar)

5. Exchange the code for tokens:

```bash
curl -X POST https://open-api.tiktok.com/v2/oauth/token/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_key=YOUR_CLIENT_KEY" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "grant_type=authorization_code" \
  -d "code=THE_AUTHORIZATION_CODE" \
  -d "redirect_uri=https://localhost:8080/callback"
```

6. The response includes:
```json
{
  "data": {
    "access_token": "clt.example.access.token.string",
    "expires_in": 86400,
    "refresh_token": "clt.example.refresh.token.string",
    "refresh_expires_in": 31536000,
    "token_type": "Bearer"
  }
}
```

7. Copy these values into `.env`:

```
LUBANJA_ACCESS_TOKEN=clt.example.access.token.string
LUBANJA_REFRESH_TOKEN=clt.example.refresh.token.string
```

## Step 4: Token Refresh Cycle

- **Access token** expires every **24 hours** (86400 seconds)
- **Refresh token** expires every **365 days** (31536000 seconds)
- The tool auto-refreshes via `auth.py` — it checks token age before each run
- If the refresh token also expires, re-run Step 3

## Step 5: Submit for Audit (Optional — For Direct Publishing)

Upload to Inbox (draft mode) does **not** require audit. If you want Direct Post (publishes without opening TikTok Studio):
1. In app dashboard → **"Audit"** tab
2. Submit screenshots/video of your app using the API
3. Audit takes 2–6 weeks and is free
4. Until approved, only sandbox users can use the app
