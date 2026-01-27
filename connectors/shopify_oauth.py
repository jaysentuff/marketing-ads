"""
Shopify OAuth Flow - Get Access Token

Run this once to authorize and get your access token.
"""

import os
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
SHOP_NAME = "tuffwraps-com"  # Just the name part, not full domain
CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:3000/callback"
SCOPES = "read_orders,read_all_orders,read_customers,read_products,read_inventory,read_analytics"

# Store the access token when we get it
access_token = None
state_token = secrets.token_urlsafe(16)


class OAuthHandler(BaseHTTPRequestHandler):
    """Handle the OAuth callback."""

    def do_GET(self):
        global access_token

        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)

            # Verify state
            if params.get("state", [None])[0] != state_token:
                self.send_error(400, "Invalid state parameter")
                return

            code = params.get("code", [None])[0]
            if not code:
                self.send_error(400, "No code provided")
                return

            # Exchange code for access token
            token_url = f"https://{SHOP_NAME}.myshopify.com/admin/oauth/access_token"
            response = requests.post(token_url, json={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
            })

            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")

                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                html = f"""
                <html>
                <head><title>Success!</title></head>
                <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>Authorization Successful!</h1>
                    <p>Your access token has been retrieved.</p>
                    <p style="background: #f0f0f0; padding: 20px; word-break: break-all; font-family: monospace;">
                        {access_token}
                    </p>
                    <p>Add this to your .env file as:</p>
                    <pre style="background: #f0f0f0; padding: 10px;">SHOPIFY_ACCESS_TOKEN={access_token}</pre>
                    <p>You can close this window now.</p>
                </body>
                </html>
                """
                self.wfile.write(html.encode())

                print("\n" + "="*60)
                print("SUCCESS! Access token retrieved:")
                print("="*60)
                print(f"\nSHOPIFY_ACCESS_TOKEN={access_token}")
                print("\nAdd this to your .env file!")
                print("="*60 + "\n")

            else:
                self.send_error(500, f"Token exchange failed: {response.text}")
        else:
            self.send_error(404, "Not found")

    def log_message(self, format, *args):
        pass  # Suppress default logging


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET in your .env file first!")
        print("\nAdd these lines to your .env:")
        print("  SHOPIFY_CLIENT_ID=your_client_id_here")
        print("  SHOPIFY_CLIENT_SECRET=your_client_secret_here")
        return

    # Build authorization URL
    auth_params = {
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": state_token,
    }

    auth_url = f"https://{SHOP_NAME}.myshopify.com/admin/oauth/authorize?{urlencode(auth_params)}"

    print("="*60)
    print("Shopify OAuth Authorization")
    print("="*60)
    print(f"\nShop: {SHOP_NAME}.myshopify.com")
    print(f"Scopes: {SCOPES}")
    print(f"\nOpening browser for authorization...")
    print("If browser doesn't open, visit this URL:")
    print(f"\n{auth_url}\n")

    # Start local server to catch the callback
    server = HTTPServer(("localhost", 3000), OAuthHandler)

    # Open browser
    webbrowser.open(auth_url)

    print("Waiting for authorization callback...")
    print("(Press Ctrl+C to cancel)\n")

    # Handle one request (the callback)
    try:
        while access_token is None:
            server.handle_request()
    except KeyboardInterrupt:
        print("\nCancelled.")

    server.server_close()


if __name__ == "__main__":
    main()
