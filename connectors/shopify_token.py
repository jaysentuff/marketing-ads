"""
Get Shopify Access Token - Manual Flow

Since the app is installed, we can get the token by
triggering the OAuth flow and capturing the code manually.
"""

import os
from urllib.parse import urlencode
from dotenv import load_dotenv
import requests

load_dotenv()

CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
SHOP = "tuffwraps-com.myshopify.com"
SCOPES = "read_orders,read_all_orders,read_customers,read_products,read_inventory,read_analytics"

def get_install_url():
    """Generate the OAuth install URL."""
    params = {
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": "http://localhost:3000/callback",
    }
    url = f"https://{SHOP}/admin/oauth/authorize?{urlencode(params)}"
    return url

def exchange_code_for_token(code):
    """Exchange authorization code for access token."""
    url = f"https://{SHOP}/admin/oauth/access_token"

    response = requests.post(url, json={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
    })

    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    print("="*60)
    print("SHOPIFY TOKEN EXCHANGE")
    print("="*60)

    # Check if user has a code to exchange
    code = input("\nDo you have an authorization code? (paste it, or press Enter to get URL): ").strip()

    if code:
        print("\nExchanging code for token...")
        token = exchange_code_for_token(code)
        if token:
            print("\n" + "="*60)
            print("SUCCESS! Your access token:")
            print("="*60)
            print(f"\nSHOPIFY_ACCESS_TOKEN={token}")
            print("\nAdd this to your .env file!")
        else:
            print("Failed to exchange code for token.")
    else:
        print("\nOpen this URL in your browser while logged into Shopify Admin:")
        print(get_install_url())
        print("\nAfter authorizing, check your browser URL for the 'code' parameter.")
        print("Copy the code value and run this script again.")
