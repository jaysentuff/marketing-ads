"""
Amazon Seller Central Connector for TuffWraps Marketing Attribution

Pulls data from Amazon SP-API:
- Orders and sales data
- Revenue by product
- Amazon fees (for CAM calculation)
- Amazon halo effect tracking (correlate with TOF spend)

Requires Amazon SP-API credentials (separate from AWS credentials).
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()


class AmazonSellerConnector:
    """Connector for Amazon Selling Partner API."""

    # Amazon SP-API endpoints (US marketplace)
    LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
    SP_API_BASE = "https://sellingpartnerapi-na.amazon.com"

    MARKETPLACE_ID = "ATVPDKIKX0DER"  # US marketplace

    def __init__(self):
        # LWA (Login with Amazon) credentials
        self.lwa_client_id = os.getenv("AMAZON_LWA_CLIENT_ID")
        self.lwa_client_secret = os.getenv("AMAZON_LWA_CLIENT_SECRET")
        self.lwa_refresh_token = os.getenv("AMAZON_LWA_REFRESH_TOKEN")

        # SP-API credentials
        self.sp_api_role_arn = os.getenv("AMAZON_SP_API_ROLE_ARN")

        self.access_token = None
        self.data_dir = Path(__file__).parent / "data" / "amazon"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Validate credentials
        if not all([self.lwa_client_id, self.lwa_client_secret, self.lwa_refresh_token]):
            print("Warning: Amazon SP-API credentials not configured.")
            print("Add the following to .env:")
            print("  AMAZON_LWA_CLIENT_ID=")
            print("  AMAZON_LWA_CLIENT_SECRET=")
            print("  AMAZON_LWA_REFRESH_TOKEN=")
            self.configured = False
        else:
            self.configured = True
            self._refresh_access_token()

    def _refresh_access_token(self):
        """Get a new LWA access token."""
        response = requests.post(
            self.LWA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.lwa_refresh_token,
                "client_id": self.lwa_client_id,
                "client_secret": self.lwa_client_secret,
            },
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get Amazon access token: {response.text}")

        data = response.json()
        self.access_token = data["access_token"]

    def _api_request(self, endpoint: str, method: str = "GET", params: dict = None) -> dict:
        """Make API request to SP-API."""
        if not self.configured:
            raise Exception("Amazon SP-API not configured. Check credentials in .env")

        headers = {
            "x-amz-access-token": self.access_token,
            "Content-Type": "application/json",
        }

        url = f"{self.SP_API_BASE}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"

        response = requests.request(method, url, headers=headers)

        if response.status_code == 401:
            # Token expired, refresh and retry
            self._refresh_access_token()
            headers["x-amz-access-token"] = self.access_token
            response = requests.request(method, url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Amazon API Error: {response.status_code} - {response.text}")

        return response.json()

    def get_orders(self, start_date: str, end_date: str, max_pages: int = 10) -> list:
        """
        Get orders within date range with pagination support.

        Args:
            start_date: ISO format (YYYY-MM-DD)
            end_date: ISO format (YYYY-MM-DD)
            max_pages: Maximum number of pages to fetch (default 10, ~1000 orders)

        Returns:
            List of orders with details
        """
        # Convert to ISO 8601 with timezone
        created_after = f"{start_date}T00:00:00Z"

        # Amazon API requires CreatedBefore to be at least 2 minutes before current time
        # Check if end_date is today - if so, use current time minus 3 minutes for safety
        now = datetime.utcnow()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

        if end_date_obj.date() >= now.date():
            # End date is today or future - use current time minus 3 minutes
            safe_time = now - timedelta(minutes=3)
            created_before = safe_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            # End date is in the past - use end of day
            created_before = f"{end_date}T23:59:59Z"

        all_orders = []
        next_token = None
        pages_fetched = 0

        while pages_fetched < max_pages:
            params = {
                "MarketplaceIds": self.MARKETPLACE_ID,
                "CreatedAfter": created_after,
                "CreatedBefore": created_before,
                "OrderStatuses": "Shipped,Unshipped,PartiallyShipped",
            }

            if next_token:
                params["NextToken"] = next_token

            result = self._api_request("/orders/v0/orders", params=params)
            payload = result.get("payload", {})

            orders = payload.get("Orders", [])
            all_orders.extend(orders)
            pages_fetched += 1

            # Check for more pages
            next_token = payload.get("NextToken")
            if not next_token:
                break

        return all_orders

    def get_sales_by_date(self, start_date: str, end_date: str) -> list:
        """
        Get sales and traffic data by date using Reports API.

        This provides daily aggregated data including:
        - Units ordered
        - Revenue
        - Sessions (traffic)
        """
        # Request a GET_SALES_AND_TRAFFIC_REPORT
        report_params = {
            "reportType": "GET_SALES_AND_TRAFFIC_REPORT",
            "marketplaceIds": [self.MARKETPLACE_ID],
            "dataStartTime": f"{start_date}T00:00:00Z",
            "dataEndTime": f"{end_date}T23:59:59Z",
        }

        # Create report request
        create_response = self._api_request(
            "/reports/2021-06-30/reports",
            method="POST",
            params=report_params,
        )

        report_id = create_response.get("reportId")

        # Poll for report completion (simplified - in production use async)
        import time
        for _ in range(30):  # Max 5 minutes
            status = self._api_request(f"/reports/2021-06-30/reports/{report_id}")
            if status.get("processingStatus") == "DONE":
                # Get the report document
                doc_id = status.get("reportDocumentId")
                doc = self._api_request(f"/reports/2021-06-30/documents/{doc_id}")
                # Download and parse report
                report_url = doc.get("url")
                report_data = requests.get(report_url).json()
                return report_data
            elif status.get("processingStatus") == "FATAL":
                raise Exception(f"Report generation failed: {status}")
            time.sleep(10)

        raise Exception("Report generation timed out")

    def get_orders_for_timeframe(self, days: int) -> dict:
        """
        Get orders for the last N days and return aggregated metrics.

        Args:
            days: Number of days to look back (1 = yesterday, 7 = last week)

        Returns:
            Dictionary with aggregated Amazon metrics for dashboard
        """
        from datetime import timezone
        import pytz

        # Use EST timezone for consistency with the rest of the dashboard
        est = pytz.timezone("US/Eastern")
        now_est = datetime.now(est)

        # Calculate date range
        if days == 1:
            # Yesterday
            end_date = (now_est - timedelta(days=1)).strftime("%Y-%m-%d")
            start_date = end_date
        else:
            # Last N days (not including today)
            end_date = (now_est - timedelta(days=1)).strftime("%Y-%m-%d")
            start_date = (now_est - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            orders = self.get_orders(start_date, end_date)

            # Aggregate metrics
            total_revenue = 0.0
            total_orders = len(orders)

            for order in orders:
                order_total = order.get("OrderTotal", {})
                if order_total:
                    amount = float(order_total.get("Amount", 0))
                    total_revenue += amount

            # Calculate ROAS if we have Amazon ad spend
            # For now, we'll return 0 and let the backend calculate with actual ad spend
            return {
                "success": True,
                "period": {
                    "start": start_date,
                    "end": end_date,
                    "days": days,
                },
                "metrics": {
                    "sales": round(total_revenue, 2),
                    "orders": total_orders,
                    "avg_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
                },
                "raw_orders": orders,  # Include for detailed analysis if needed
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "period": {
                    "start": start_date,
                    "end": end_date,
                    "days": days,
                },
                "metrics": {
                    "sales": 0,
                    "orders": 0,
                    "avg_order_value": 0,
                },
            }

    def get_fba_fees(self, start_date: str, end_date: str) -> dict:
        """
        Get FBA fee estimates for cost calculation.

        Returns aggregated fee data.
        """
        # FBA fees are typically in the settlement reports
        # This is a simplified version
        return {
            "note": "FBA fees require settlement report analysis",
            "estimated_fee_rate": 0.15,  # ~15% of revenue is typical for FBA
        }

    def save_data(self, data: dict | list, filename: str) -> Path:
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath

    def pull_last_30_days(self) -> dict:
        """Pull all Amazon data for last 30 days."""
        if not self.configured:
            print("Amazon SP-API not configured. Skipping.")
            return {"error": "Not configured"}

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"Pulling Amazon data from {start_date} to {end_date}...")

        try:
            # Get orders
            print("  Fetching orders...")
            orders = self.get_orders(start_date, end_date)
            self.save_data(orders, "orders_last_30d.json")

            # Calculate summary
            total_revenue = 0
            total_orders = len(orders)

            for order in orders:
                total_revenue += float(order.get("OrderTotal", {}).get("Amount", 0))

            summary = {
                "period": {"start": start_date, "end": end_date},
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "orders": orders,
            }

            self.save_data(summary, "summary_last_30d.json")

            # Print summary
            print("\n" + "=" * 50)
            print("AMAZON SELLER CENTRAL SUMMARY")
            print("=" * 50)
            print(f"  Period: {start_date} to {end_date}")
            print(f"  Orders: {total_orders:,}")
            print(f"  Revenue: ${total_revenue:,.2f}")
            print("=" * 50)

            return summary

        except Exception as e:
            print(f"Error pulling Amazon data: {e}")
            return {"error": str(e)}


def setup_instructions():
    """Print setup instructions for Amazon SP-API."""
    print("""
================================================================================
AMAZON SELLER CENTRAL SP-API SETUP
================================================================================

1. Register as a Developer:
   - Go to: https://sellercentral.amazon.com/sellingpartner/developerconsole
   - Create a developer profile
   - Choose "Private" application type (for your own seller account)

2. Create an SP-API Application:
   - In Developer Console, create a new app
   - Select required APIs:
     * Orders API
     * Reports API
     * Sales API
   - Note your LWA credentials:
     * LWA Client ID
     * LWA Client Secret

3. Authorize the Application:
   - In Seller Central, go to Apps & Services > Manage Your Apps
   - Find your app and click "Authorize"
   - Complete OAuth flow to get the Refresh Token

4. Add to .env:
   AMAZON_LWA_CLIENT_ID=<your-lwa-client-id>
   AMAZON_LWA_CLIENT_SECRET=<your-lwa-client-secret>
   AMAZON_LWA_REFRESH_TOKEN=<your-refresh-token>

5. (Optional) If using delegated API access:
   AMAZON_SP_API_ROLE_ARN=<your-iam-role-arn>

================================================================================
""")


def main():
    """Test the connector or show setup instructions."""
    connector = AmazonSellerConnector()

    if not connector.configured:
        setup_instructions()
        return

    try:
        data = connector.pull_last_30_days()
        print("\nAmazon data pulled successfully!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
