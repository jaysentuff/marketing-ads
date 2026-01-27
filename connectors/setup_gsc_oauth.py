"""
Google Search Console OAuth Setup

Run this script to authorize access to Google Search Console.
Uses the same OAuth client as Google Ads but with different scopes.
"""

import os
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()


def get_authorization_url():
    """Generate the OAuth authorization URL."""
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")

    if not client_id:
        raise ValueError("GOOGLE_ADS_CLIENT_ID not found in .env")

    params = {
        "client_id": client_id,
        "redirect_uri": "http://localhost:8080",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/webmasters.readonly",
        "access_type": "offline",
        "prompt": "consent",  # Force refresh token generation
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return auth_url


def exchange_code_for_tokens(auth_code: str) -> dict:
    """Exchange authorization code for tokens."""
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")

    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:8080",
        },
    )

    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")

    return response.json()


def main():
    print("=" * 60)
    print("Google Search Console OAuth Setup")
    print("=" * 60)
    print()

    # Generate auth URL
    auth_url = get_authorization_url()

    print("1. Opening browser for Google authorization...")
    print()
    print("   If browser doesn't open, visit this URL manually:")
    print(f"   {auth_url}")
    print()

    # Try to open browser
    webbrowser.open(auth_url)

    print("2. After authorizing, you'll be redirected to localhost.")
    print("   The page won't load (that's expected).")
    print()
    print("3. Copy the FULL URL from your browser's address bar and paste it below.")
    print("   It will look like: http://localhost:8080/?code=XXXXX&scope=...")
    print()

    redirect_url = input("Paste the redirect URL here: ").strip()

    # Parse the code from the URL
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)

    if "code" not in params:
        print("\nError: No authorization code found in URL")
        print("Make sure you copied the full URL including the ?code= parameter")
        return

    auth_code = params["code"][0]

    print()
    print("4. Exchanging code for tokens...")

    tokens = exchange_code_for_tokens(auth_code)

    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        print("\nWarning: No refresh token returned.")
        print("This might happen if you've already authorized this app before.")
        print("Try revoking access at https://myaccount.google.com/permissions")
        print("Then run this script again.")
        return

    print()
    print("=" * 60)
    print("SUCCESS! Add this to your .env file:")
    print("=" * 60)
    print()
    print(f"GSC_REFRESH_TOKEN={refresh_token}")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
