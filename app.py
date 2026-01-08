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
FB_APP_ID = os.environ.get('FB_APP_ID', '758214417322401')

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
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
            h1 {{ color: #333; }}
            .info-box {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .webhook {{ background: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; border-radius: 4px; }}
            .webhook-header {{ font-weight: bold; color: #333; margin-bottom: 10px; }}
            pre {{ background: #263238; color: #aed581; padding: 15px; border-radius: 4px; overflow-x: auto; }}
            .scopes {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .scope-item {{ margin: 5px 0; }}
            .required {{ color: #d32f2f; font-weight: bold; }}
            .optional {{ color: #f57c00; }}
            .status {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; }}
            .status-verified {{ background: #4CAF50; color: white; }}
            .status-unverified {{ background: #ff9800; color: white; }}
        </style>
        <script>
            // Auto-refresh every 5 seconds
            setTimeout(function(){{ location.reload(); }}, 5000);
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Instagram Webhook POC</h1>
            <p><a href="/auth" style="color: #1877f2; text-decoration: none; font-weight: bold;">→ Test Facebook Login & Scopes</a></p>

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


@app.route('/auth')
def auth_test():
    """Facebook Login test page"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Instagram/Facebook Auth Test</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
            h1 {{ color: #333; }}
            .section {{ margin: 30px 0; padding: 20px; background: #f9f9f9; border-radius: 5px; }}
            .scopes {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .scope-item {{ margin: 5px 0; }}
            .required {{ color: #d32f2f; font-weight: bold; }}
            button {{ background: #1877f2; color: white; border: none; padding: 12px 24px;
                      font-size: 16px; border-radius: 5px; cursor: pointer; margin: 10px 5px; }}
            button:hover {{ background: #166fe5; }}
            button:disabled {{ background: #ccc; cursor: not-allowed; }}
            .result {{ background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .error {{ background: #ffebee; color: #c62828; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            pre {{ background: #263238; color: #aed581; padding: 15px; border-radius: 4px; overflow-x: auto; }}
            .token {{ word-break: break-all; font-family: monospace; font-size: 12px; }}
            .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Instagram/Facebook Auth Test</h1>
            <p><a href="/">← Back to Webhook Dashboard</a></p>

            <div class="info">
                <h3>Testing Facebook Login for Instagram API</h3>
                <p>This page helps you test the Facebook Login flow and verify which scopes are granted.</p>
                <p><strong>App ID:</strong> {FB_APP_ID}</p>
            </div>

            <div class="scopes">
                <h3>Scopes We'll Request</h3>
                <div class="scope-item"><span class="required">Core:</span> <code>instagram_basic</code> - Base Instagram access (mentions, comments webhooks)</div>
                <div class="scope-item"><span class="required">Core:</span> <code>instagram_manage_messages</code> - DM webhooks</div>
                <div class="scope-item"><span class="required">Core:</span> <code>pages_show_list</code> - List Facebook Pages</div>
                <div class="scope-item"><span class="required">Core:</span> <code>business_management</code> - Manage Business assets</div>
                <div class="scope-item">Optional: <code>pages_read_engagement</code> - Page engagement data</div>
                <div class="scope-item">Optional: <code>pages_manage_metadata</code> - Manage page metadata</div>
                <div class="scope-item">Optional: <code>instagram_content_publish</code> - Publish content</div>
                <div class="scope-item" style="color: #999;"><strike>instagram_manage_comments</strike> - Not available via Facebook Login</div>
                <div class="scope-item" style="color: #999;"><strike>instagram_manage_insights</strike> - Not available via Facebook Login</div>
            </div>

            <div class="section">
                <h3>Step 1: Login with Facebook</h3>
                <button id="loginBtn" onclick="fbLogin()">Login with Facebook</button>
                <div id="loginStatus"></div>
            </div>

            <div class="section">
                <h3>Step 2: Check Granted Permissions</h3>
                <button id="checkPermsBtn" onclick="checkPermissions()" disabled>Check My Permissions</button>
                <div id="permissionsResult"></div>
            </div>

            <div class="section">
                <h3>Step 3: Get Instagram Business Account</h3>
                <button id="getIgBtn" onclick="getInstagramAccount()" disabled>Get Instagram Business Account</button>
                <div id="igAccountResult"></div>
            </div>

            <div class="section">
                <h3>Alternative Method: Manual API Test</h3>
                <p>If Step 3 shows 0 pages, try this alternative approach using Graph API Explorer:</p>
                <ol style="text-align: left;">
                    <li>Go to <a href="https://developers.facebook.com/tools/explorer" target="_blank">Graph API Explorer</a></li>
                    <li>Select your app: <strong>{FB_APP_ID}</strong></li>
                    <li>Click "Generate Access Token"</li>
                    <li>Grant permissions: <code>pages_show_list</code>, <code>instagram_basic</code>, <code>business_management</code>, <code>pages_manage_metadata</code></li>
                    <li>In the query box, enter: <code>me/accounts?fields=id,name,instagram_business_account</code></li>
                    <li>Click "Submit" and see if your page appears</li>
                </ol>
                <p style="margin-top: 15px;">Copy your access token from Graph Explorer:</p>
                <input type="text" id="manualToken" placeholder="Paste access token here" style="width: 100%; padding: 10px; margin: 5px 0; font-family: monospace; font-size: 12px;">
                <button onclick="testManualToken()">Test This Token</button>
                <div id="manualTestResult"></div>
            </div>

            <div class="section">
                <h3>Step 4: Subscribe to Webhooks (Manual)</h3>
                <p>After getting your Instagram Business Account ID above, you can subscribe to webhooks:</p>
                <pre id="curlCommand">Loading...</pre>
                <button onclick="copyToClipboard()">Copy Command</button>
            </div>
        </div>

        <script>
            let accessToken = null;
            let userId = null;
            let pages = [];
            let igAccountId = null;

            window.fbAsyncInit = function() {{
                FB.init({{
                    appId      : '{FB_APP_ID}',
                    cookie     : true,
                    xfbml      : true,
                    version    : 'v21.0'
                }});

                // Check login status on load
                FB.getLoginStatus(function(response) {{
                    if (response.status === 'connected') {{
                        accessToken = response.authResponse.accessToken;
                        userId = response.authResponse.userID;
                        showLoginSuccess();
                    }}
                }});
            }};

            (function(d, s, id){{
                var js, fjs = d.getElementsByTagName(s)[0];
                if (d.getElementById(id)) return;
                js = d.createElement(s); js.id = id;
                js.src = "https://connect.facebook.net/en_US/sdk.js";
                fjs.parentNode.insertBefore(js, fjs);
            }}(document, 'script', 'facebook-jssdk'));

            function fbLogin() {{
                FB.login(function(response) {{
                    if (response.status === 'connected') {{
                        accessToken = response.authResponse.accessToken;
                        userId = response.authResponse.userID;
                        showLoginSuccess();
                    }} else {{
                        document.getElementById('loginStatus').innerHTML =
                            '<div class="error">Login failed or was cancelled</div>';
                    }}
                }}, {{
                    scope: 'instagram_basic,instagram_manage_messages,pages_show_list,pages_read_engagement,instagram_content_publish,business_management,pages_manage_metadata',
                    auth_type: 'rerequest'
                }});
            }}

            function showLoginSuccess() {{
                document.getElementById('loginStatus').innerHTML =
                    '<div class="result"><strong>✓ Login successful!</strong><br>' +
                    'User ID: ' + userId + '<br>' +
                    'Access Token: <span class="token">' + accessToken + '</span></div>';
                document.getElementById('checkPermsBtn').disabled = false;
                document.getElementById('getIgBtn').disabled = false;
            }}

            function checkPermissions() {{
                FB.api('/me/permissions', function(response) {{
                    if (response && !response.error) {{
                        let granted = [];
                        let declined = [];

                        response.data.forEach(function(perm) {{
                            if (perm.status === 'granted') {{
                                granted.push(perm.permission);
                            }} else {{
                                declined.push(perm.permission);
                            }}
                        }});

                        let html = '<div class="result">';
                        html += '<h4>Granted Permissions (' + granted.length + '):</h4>';
                        html += '<pre>' + JSON.stringify(granted, null, 2) + '</pre>';

                        if (declined.length > 0) {{
                            html += '<h4>Declined Permissions:</h4>';
                            html += '<pre>' + JSON.stringify(declined, null, 2) + '</pre>';
                        }}
                        html += '</div>';

                        document.getElementById('permissionsResult').innerHTML = html;
                    }} else {{
                        document.getElementById('permissionsResult').innerHTML =
                            '<div class="error">Error: ' + JSON.stringify(response.error) + '</div>';
                    }}
                }});
            }}

            function getInstagramAccount() {{
                // First get Facebook Pages
                FB.api('/me/accounts', {{ fields: 'id,name,access_token,instagram_business_account' }}, function(response) {{
                    let html = '';

                    // Debug: Show raw response
                    html += '<div class="info" style="margin-bottom: 15px;">';
                    html += '<h4>🔍 Debug: Raw API Response</h4>';
                    html += '<pre style="max-height: 200px; overflow-y: auto;">' + JSON.stringify(response, null, 2) + '</pre>';
                    html += '</div>';

                    if (response && response.error) {{
                        html += '<div class="error">';
                        html += '<strong>API Error:</strong><br>';
                        html += 'Code: ' + response.error.code + '<br>';
                        html += 'Message: ' + response.error.message + '<br>';
                        html += 'Type: ' + response.error.type + '<br>';
                        html += '</div>';
                        document.getElementById('igAccountResult').innerHTML = html;
                        return;
                    }}

                    if (response && response.data) {{
                        pages = response.data;
                        html += '<div class="result">';
                        html += '<h4>Facebook Pages (' + pages.length + '):</h4>';

                        if (pages.length === 0) {{
                            html += '<div class="error">';
                            html += '<strong>No Pages Found</strong><br>';
                            html += '<p>Possible reasons:</p>';
                            html += '<ul style="text-align: left; margin-left: 20px;">';
                            html += '<li>You do not have any Facebook Pages where you are an Admin or Editor</li>';
                            html += '<li>Your app needs to be added to Business Manager</li>';
                            html += '<li>Try adding <code>pages_manage_metadata</code> permission</li>';
                            html += '</ul>';
                            html += '<p><strong>Next steps:</strong></p>';
                            html += '<ol style="text-align: left; margin-left: 20px;">';
                            html += '<li>Go to <a href="https://www.facebook.com/pages" target="_blank">facebook.com/pages</a></li>';
                            html += '<li>Create a new Page if you do not have one</li>';
                            html += '<li>Make sure you are an Admin on the page</li>';
                            html += '<li>Try the "Alternative Method" below</li>';
                            html += '</ol>';
                            html += '</div>';
                        }} else {{
                            pages.forEach(function(page) {{
                                html += '<div style="margin: 10px 0; padding: 10px; background: white; border-radius: 4px;">';
                                html += '<strong>' + page.name + '</strong><br>';
                                html += 'Page ID: ' + page.id + '<br>';

                                if (page.instagram_business_account) {{
                                    igAccountId = page.instagram_business_account.id;
                                    html += '<span style="color: green;">✓ Instagram Business Account Connected!</span><br>';
                                    html += 'Instagram Business Account ID: <strong>' + page.instagram_business_account.id + '</strong><br>';

                                    // Get Instagram account details
                                    getIgAccountDetails(page.instagram_business_account.id, page.access_token);

                                    // Update curl command
                                    updateCurlCommand(page.access_token, page.instagram_business_account.id);
                                }} else {{
                                    html += '<span style="color: orange;">⚠ No Instagram Business Account connected</span><br>';
                                }}
                                html += '</div>';
                            }});
                        }}

                        html += '</div>';
                    }} else {{
                        html += '<div class="error">Unexpected response format</div>';
                    }}

                    document.getElementById('igAccountResult').innerHTML = html;
                }});
            }}

            function getIgAccountDetails(igAccountId, pageAccessToken) {{
                fetch('https://graph.facebook.com/v21.0/' + igAccountId +
                      '?fields=id,username,name,profile_picture_url&access_token=' + pageAccessToken)
                    .then(response => response.json())
                    .then(data => {{
                        let html = '<div class="result" style="margin-top: 10px;">';
                        html += '<h4>Instagram Account Details:</h4>';
                        html += '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                        html += '</div>';

                        let currentHtml = document.getElementById('igAccountResult').innerHTML;
                        document.getElementById('igAccountResult').innerHTML = currentHtml + html;
                    }});
            }}

            function updateCurlCommand(pageAccessToken, igAccountId) {{
                let cmd = `# Subscribe to Instagram webhooks\\n`;
                cmd += `curl -X POST "https://graph.facebook.com/v21.0/${{igAccountId}}/subscribed_apps" \\\\\\n`;
                cmd += `  -d "access_token=${{pageAccessToken}}" \\\\\\n`;
                cmd += `  -d "subscribed_fields=messages,comments,mentions"\\n\\n`;
                cmd += `# Check subscription status\\n`;
                cmd += `curl "https://graph.facebook.com/v21.0/${{igAccountId}}/subscribed_apps?access_token=${{pageAccessToken}}"`;

                cmd = cmd.replace('${{igAccountId}}', igAccountId);
                cmd = cmd.replace(/\\${{pageAccessToken}}/g, pageAccessToken);

                document.getElementById('curlCommand').textContent = cmd;
            }}

            function testManualToken() {{
                let token = document.getElementById('manualToken').value.trim();
                if (!token) {{
                    document.getElementById('manualTestResult').innerHTML =
                        '<div class="error">Please paste an access token</div>';
                    return;
                }}

                fetch('https://graph.facebook.com/v21.0/me/accounts?fields=id,name,access_token,instagram_business_account&access_token=' + token)
                    .then(response => response.json())
                    .then(data => {{
                        let html = '<div class="result" style="margin-top: 10px;">';
                        html += '<h4>Manual Token Test Result:</h4>';
                        html += '<pre>' + JSON.stringify(data, null, 2) + '</pre>';

                        if (data.data && data.data.length > 0) {{
                            html += '<div style="margin-top: 10px; padding: 10px; background: #e8f5e9; border-radius: 4px;">';
                            html += '<strong style="color: green;">✓ Success! Found ' + data.data.length + ' page(s)</strong>';

                            data.data.forEach(function(page) {{
                                if (page.instagram_business_account) {{
                                    html += '<p>Instagram Business Account ID: <strong>' + page.instagram_business_account.id + '</strong></p>';
                                    updateCurlCommand(page.access_token, page.instagram_business_account.id);
                                }}
                            }});
                            html += '</div>';
                        }}
                        html += '</div>';
                        document.getElementById('manualTestResult').innerHTML = html;
                    }})
                    .catch(error => {{
                        document.getElementById('manualTestResult').innerHTML =
                            '<div class="error">Error: ' + error.message + '</div>';
                    }});
            }}

            function copyToClipboard() {{
                let text = document.getElementById('curlCommand').textContent;
                navigator.clipboard.writeText(text).then(function() {{
                    alert('Copied to clipboard!');
                }});
            }}

            // Initialize curl command placeholder
            document.getElementById('curlCommand').textContent =
                '# Complete steps 1-3 first to generate subscription commands';
        </script>
    </body>
    </html>
    """.format(FB_APP_ID=FB_APP_ID)
    return html


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'webhooks_received': len(recent_webhooks),
        'verify_token_set': bool(VERIFY_TOKEN),
        'app_secret_set': bool(APP_SECRET),
        'fb_app_id': FB_APP_ID
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
