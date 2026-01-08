# Instagram Webhook POC

A simple webhook receiver to test Instagram webhooks and validate required scopes.

## Features

- Receives and displays Instagram webhooks (messages, comments, mentions)
- Verifies webhook signatures using app secret
- Shows required OAuth scopes for each webhook type
- Auto-refreshing dashboard to see webhooks in real-time

## Setup

### Option 1: Deploy to Render.com (Free Tier - Recommended)

Render.com offers a free tier perfect for testing webhooks.

#### Quick Deploy

1. **Push to GitHub** (if not already done):
   ```bash
   # Create a new repo on GitHub first, then:
   git remote add origin https://github.com/yourusername/instagram-webhook-poc.git
   git branch -M main
   git push -u origin main
   ```

2. **Deploy on Render**:
   - Go to [render.com](https://render.com) and sign up/login
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect the `render.yaml` and configure everything
   - Click "Create Web Service"

3. **Set Environment Variables** (after creation):
   - Go to your service → Environment
   - `VERIFY_TOKEN` will be auto-generated
   - Add `APP_SECRET`: Your Meta app secret (from Meta Developer Dashboard)

4. **Get your webhook URL**:
   - Your app will be at: `https://instagram-webhook-poc-<random>.onrender.com`
   - Webhook endpoint: `https://instagram-webhook-poc-<random>.onrender.com/webhook`

#### Notes about Render Free Tier
- ⚠️ Free services spin down after 15 minutes of inactivity
- First request after sleeping takes 30-50 seconds to wake up
- Sufficient for testing and POC work
- No credit card required for free tier

### Option 2: Deploy to Railway.app (Free Tier)

Railway offers $5 free credit per month.

1. **Deploy on Railway**:
   ```bash
   # Install Railway CLI
   npm install -g @railway/cli

   # Login
   railway login

   # Create project and deploy
   railway init
   railway up

   # Set environment variables
   railway variables set VERIFY_TOKEN="my_secure_token_$(openssl rand -hex 16)"
   railway variables set APP_SECRET="your_meta_app_secret"

   # Get URL
   railway domain
   ```

### Option 3: Local Testing with ngrok

For local development:

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
VERIFY_TOKEN="test_token" python app.py

# In another terminal, expose with ngrok
ngrok http 5000
```

Use the ngrok URL (e.g., `https://abc123.ngrok.io/webhook`) as your webhook URL in Meta Dashboard.

## Configure Meta App

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Select your app (or create new one)
3. Add Instagram product
4. Go to Webhooks section
5. Add webhook:
   - **Callback URL**: `https://your-app.onrender.com/webhook`
   - **Verify Token**: Get from Render environment variables
   - **Subscribe to fields**: `messages`, `comments`, `mentions`

## Test

Visit your app URL to see the dashboard:
```
https://your-app.onrender.com/
```

Send test webhooks from Meta App Dashboard or trigger real events by:
- Sending a DM to your Instagram Business account
- Commenting on a post
- @mentioning your business in a story or post

## Required Scopes

### Core Requirements (Facebook Login approach)
- ✅ `instagram_basic` - Base Instagram access (enables mentions webhooks)
- ✅ `instagram_manage_messages` - For message/DM webhooks
- ✅ `instagram_manage_comments` - For comment webhooks
- ✅ `pages_show_list` - To list Facebook Pages

### Optional but Helpful
- `instagram_content_publish` - For content publishing
- `instagram_manage_insights` - For analytics
- `pages_read_engagement` - Additional engagement data

## Webhook Types Supported

1. **Messages** - Direct messages to business account
2. **Comments** - Comments on posts/reels
3. **Mentions** - @mentions in stories or post captions

## Environment Variables

- `VERIFY_TOKEN` - Token for webhook verification (required, auto-generated on Render)
- `APP_SECRET` - Meta app secret for signature verification (optional but recommended)
- `PORT` - Port to run on (set automatically by hosting platform)

## Troubleshooting

### Render Free Tier Spin Down
If your first webhook fails after inactivity:
1. Visit the dashboard URL to wake up the service
2. Wait 30-60 seconds
3. Re-send the webhook

### Webhook Verification Failed
- Check that `VERIFY_TOKEN` in Render matches the token in Meta App Dashboard
- Verify the callback URL ends with `/webhook`

### Signature Verification Failed
- Ensure `APP_SECRET` is set correctly in environment variables
- Get your app secret from Meta Developer Dashboard → Settings → Basic → App Secret

## Deployment Commands

```bash
# Update Render deployment
git add .
git commit -m "Update webhook handler"
git push origin main
# Render will auto-deploy

# View logs on Render
# Go to your service dashboard → Logs tab
```
