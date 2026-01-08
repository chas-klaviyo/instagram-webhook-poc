import os
import hmac
import hashlib
import json
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Get from environment variables
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'my_verify_token_12345')
APP_SECRET = os.environ.get('APP_SECRET', '')

# Store recent webhooks for inspection
recent_webhooks = []
MAX_STORED_WEBHOOKS = 50


def verify_signature(payload, signature):
    """Verify the webhook signature using app secret"""
    if not APP_SECRET:
        app.logger.warning("APP_SECRET not set, skipping signature verification")
        return True

    expected_signature = hmac.new(
        APP_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Signature comes as "sha256=<hash>"
    if signature.startswith('sha256='):
        signature = signature[7:]

    return hmac.compare_digest(expected_signature, signature)


@app.route('/')
def index():
    """Show dashboard with recent webhooks"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Instagram Webhook POC</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
            h1 { color: #333; }
            .info-box { background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .webhook { background: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; border-radius: 4px; }
            .webhook-header { font-weight: bold; color: #333; margin-bottom: 10px; }
            pre { background: #263238; color: #aed581; padding: 15px; border-radius: 4px; overflow-x: auto; }
            .scopes { background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .scope-item { margin: 5px 0; }
            .required { color: #d32f2f; font-weight: bold; }
            .optional { color: #f57c00; }
            .status { display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; }
            .status-verified { background: #4CAF50; color: white; }
            .status-unverified { background: #ff9800; color: white; }
        </style>
        <script>
            // Auto-refresh every 5 seconds
            setTimeout(function(){ location.reload(); }, 5000);
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Instagram Webhook POC</h1>

            <div class="info-box">
                <h3>Configuration</h3>
                <p><strong>Webhook URL:</strong> {webhook_url}</p>
                <p><strong>Verify Token:</strong> {verify_token}</p>
                <p><strong>App Secret Configured:</strong> {app_secret_status}</p>
            </div>

            <div class="scopes">
                <h3>Required Scopes for Instagram Webhooks</h3>
                <div class="scope-item"><span class="required">REQUIRED:</span> <code>instagram_basic</code> - Base Instagram access, enables mentions webhooks</div>
                <div class="scope-item"><span class="required">REQUIRED:</span> <code>instagram_manage_messages</code> - Required for message/DM webhooks</div>
                <div class="scope-item"><span class="required">REQUIRED:</span> <code>instagram_manage_comments</code> - Required for comment webhooks</div>
                <div class="scope-item"><span class="optional">OPTIONAL:</span> <code>instagram_content_publish</code> - For content publishing</div>
                <div class="scope-item"><span class="optional">OPTIONAL:</span> <code>instagram_manage_insights</code> - For analytics</div>
                <div class="scope-item"><span class="required">REQUIRED:</span> <code>pages_show_list</code> - To list Facebook Pages</div>
                <div class="scope-item"><span class="optional">HELPFUL:</span> <code>pages_read_engagement</code> - Additional engagement data</div>
            </div>

            <h2>Recent Webhooks ({count})</h2>
            <p style="color: #666;">Auto-refreshes every 5 seconds</p>
            {webhooks_html}
        </div>
    </body>
    </html>
    """

    webhooks_html = ""
    for wh in reversed(recent_webhooks[-20:]):  # Show last 20
        webhooks_html += f"""
        <div class="webhook">
            <div class="webhook-header">
                {wh['timestamp']} - {wh['type']}
                <span class="status status-{wh['signature_status']}">{wh['signature_status']}</span>
            </div>
            <pre>{json.dumps(wh['data'], indent=2)}</pre>
        </div>
        """

    if not webhooks_html:
        webhooks_html = "<p style='color: #999;'>No webhooks received yet. Send a test webhook from Meta App Dashboard.</p>"

    return html.format(
        webhook_url=request.url_root + 'webhook',
        verify_token=VERIFY_TOKEN,
        app_secret_status='Yes ✓' if APP_SECRET else 'No (set APP_SECRET env var)',
        count=len(recent_webhooks),
        webhooks_html=webhooks_html
    )


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Handle Instagram/Facebook webhook verification and events"""

    if request.method == 'GET':
        # Webhook verification
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        app.logger.info(f"Verification request: mode={mode}, token={token}")

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            app.logger.info("Webhook verified successfully!")
            return challenge, 200
        else:
            app.logger.error("Webhook verification failed!")
            return 'Verification failed', 403

    elif request.method == 'POST':
        # Webhook event received
        signature = request.headers.get('X-Hub-Signature-256', '')
        payload = request.get_data()

        # Verify signature
        signature_valid = verify_signature(payload, signature)

        try:
            data = request.get_json()

            # Determine webhook type
            webhook_type = 'Unknown'
            if data.get('object') == 'instagram':
                webhook_type = 'Instagram'
            elif data.get('object') == 'page':
                webhook_type = 'Facebook Page'

            # Extract event details
            if 'entry' in data and len(data['entry']) > 0:
                entry = data['entry'][0]

                # Check for Instagram messaging
                if 'messaging' in entry:
                    webhook_type += ' - Messages'
                # Check for Instagram changes (comments/mentions)
                elif 'changes' in entry:
                    changes = entry['changes']
                    if changes and len(changes) > 0:
                        field = changes[0].get('field', '')
                        webhook_type += f' - {field.title()}'

            # Store webhook
            webhook_entry = {
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                'type': webhook_type,
                'signature_status': 'verified' if signature_valid else 'unverified',
                'data': data
            }

            recent_webhooks.append(webhook_entry)

            # Keep only recent webhooks
            if len(recent_webhooks) > MAX_STORED_WEBHOOKS:
                recent_webhooks.pop(0)

            app.logger.info(f"Webhook received: {webhook_type} (signature: {signature_valid})")

        except Exception as e:
            app.logger.error(f"Error processing webhook: {str(e)}")

        # Always return 200 to acknowledge receipt
        return jsonify({'status': 'ok'}), 200


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'webhooks_received': len(recent_webhooks),
        'verify_token_set': bool(VERIFY_TOKEN),
        'app_secret_set': bool(APP_SECRET)
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
