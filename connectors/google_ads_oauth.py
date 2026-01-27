"""
Google Ads OAuth - Get Refresh Token

Run this once to get your refresh token.
"""

import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_ADS_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"
SCOPE = "https://www.googleapis.com/auth/adwords"

refresh_token = None


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global refresh_token

        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]

            if code:
                # Exchange code for tokens
                token_url = "https://oauth2.googleapis.com/token"
                response = requests.post(token_url, data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": REDIRECT_URI,
                })

                if response.status_code == 200:
                    data = response.json()
                    refresh_token = data.get("refresh_token")

                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()

                    html = f"""
                    <html>
                    <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                        <h1>Success!</h1>
                        <p>Your refresh token:</p>
                        <pre style="background: #f0f0f0; padding: 20px; word-break: break-all;">{refresh_token}</pre>
                        <p>Add to .env as:</p>
                        <pre>GOOGLE_ADS_REFRESH_TOKEN={refresh_token}</pre>
                    </body>
                    </html>
                    """
                    self.wfile.write(html.encode())

                    print("\n" + "="*60)
                    print("SUCCESS! Refresh token:")
                    print("="*60)
                    print(f"\nGOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
                    print("\nAdd this to your .env file!")
                else:
                    self.send_error(500, f"Token exchange failed: {response.text}")
            else:
                error = params.get("error", ["Unknown error"])[0]
                self.send_error(400, f"OAuth error: {error}")
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET in .env first!")
        return

    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"

    print("="*60)
    print("Google Ads OAuth")
    print("="*60)
    print(f"\nOpening browser...")
    print(f"\nIf browser doesn't open, visit:\n{auth_url}\n")

    server = HTTPServer(("localhost", 8080), OAuthHandler)
    webbrowser.open(auth_url)

    print("Waiting for authorization...")
    while refresh_token is None:
        server.handle_request()

    server.server_close()


if __name__ == "__main__":
    main()
