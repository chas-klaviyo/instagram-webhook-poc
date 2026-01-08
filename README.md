# Instagram Webhook POC

A simple webhook receiver to test Instagram webhooks and validate required scopes.

## Features

- Receives and displays Instagram webhooks (messages, comments, mentions)
- Verifies webhook signatures using app secret
- Shows required OAuth scopes for each webhook type
- Auto-refreshing dashboard to see webhooks in real-time

## Setup

### 1. Deploy to Heroku

```bash
# Login to Heroku
heroku login

# Create app
heroku create instagram-webhook-poc-<your-name>

# Set environment variables
heroku config:set VERIFY_TOKEN="my_secure_token_$(openssl rand -hex 16)"
heroku config:set APP_SECRET="your_meta_app_secret"

# Deploy
git init
git add .
git commit -m "Initial commit"
git push heroku main
```

### 2. Configure Meta App

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Select your app (or create new one)
3. Add Instagram product
4. Go to Webhooks section
5. Add webhook:
   - Callback URL: `https://your-app.herokuapp.com/webhook`
   - Verify Token: (use the VERIFY_TOKEN you set above)
   - Subscribe to fields: `messages`, `comments`, `mentions`

### 3. Test

Visit your Heroku app URL to see the dashboard:
```
https://your-app.herokuapp.com/
```

Send test webhooks from Meta App Dashboard or trigger real events by:
- Sending a DM to your Instagram Business account
- Commenting on a post
- @mentioning your business in a story or post

## Required Scopes

### Core Requirements (Facebook Login approach)
- `instagram_basic` - Base Instagram access
- `instagram_manage_messages` - For message/DM webhooks
- `instagram_manage_comments` - For comment webhooks
- `pages_show_list` - To list Facebook Pages

### Optional but Helpful
- `instagram_content_publish` - For content publishing
- `instagram_manage_insights` - For analytics
- `pages_read_engagement` - Additional engagement data

## Webhook Types Supported

1. **Messages** - Direct messages to business account
2. **Comments** - Comments on posts/reels
3. **Mentions** - @mentions in stories or post captions

## Environment Variables

- `VERIFY_TOKEN` - Token for webhook verification (required)
- `APP_SECRET` - Meta app secret for signature verification (optional but recommended)
- `PORT` - Port to run on (set automatically by Heroku)
