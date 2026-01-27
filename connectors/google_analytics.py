"""
Google Analytics 4 Connector for TuffWraps Marketing Attribution

Pulls traffic and conversion data for triangulation:
- Traffic sources breakdown
- Conversion data (secondary to Shopify)
- User behavior metrics
- Device/geographic breakdowns

Uses GA4 Data API with OAuth 2.0.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()


class GA4Connector:
    """Connector for Google Analytics 4 Data API."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE = "https://analyticsdata.googleapis.com/v1beta"

    def __init__(self):
        self.client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
        self.refresh_token = os.getenv("GA4_REFRESH_TOKEN") or os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
        self.property_id = os.getenv("GA4_PROPERTY_ID")

        self.access_token = None
        self.data_dir = Path(__file__).parent / "data" / "ga4"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.property_id:
            print("Warning: GA4_PROPERTY_ID not set in .env")
            print("Find your property ID in GA4: Admin > Property > Property Details")
            self.configured = False
        elif not all([self.client_id, self.client_secret, self.refresh_token]):
            print("Warning: Google OAuth credentials not configured.")
            self.configured = False
        else:
            self.configured = True
            self._refresh_access_token()

    def _refresh_access_token(self):
        """Get a new access token using refresh token."""
        response = requests.post(
            self.TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if response.status_code != 200:
            raise Exception(f"Failed to refresh token: {response.text}")

        data = response.json()
        self.access_token = data["access_token"]

    def _api_request(self, endpoint: str, data: dict) -> dict:
        """Make API request to GA4 Data API."""
        if not self.configured:
            raise Exception("GA4 not configured. Check credentials in .env")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        url = f"{self.API_BASE}/{endpoint}"

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 401:
            # Token expired, refresh and retry
            self._refresh_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = requests.post(url, headers=headers, json=data)

        if response.status_code != 200:
            raise Exception(f"GA4 API Error: {response.status_code} - {response.text}")

        return response.json()

    def run_report(
        self,
        start_date: str,
        end_date: str,
        metrics: list,
        dimensions: list = None,
        dimension_filter: dict = None,
        limit: int = 10000,
    ) -> dict:
        """
        Run a GA4 report.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            metrics: List of metrics like ["sessions", "conversions", "totalRevenue"]
            dimensions: List of dimensions like ["date", "sessionSource", "sessionMedium"]
            dimension_filter: Optional filter criteria
            limit: Max rows to return

        Returns:
            Report data
        """
        data = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "metrics": [{"name": m} for m in metrics],
            "limit": limit,
        }

        if dimensions:
            data["dimensions"] = [{"name": d} for d in dimensions]

        if dimension_filter:
            data["dimensionFilter"] = dimension_filter

        return self._api_request(f"properties/{self.property_id}:runReport", data)

    def get_traffic_sources(self, start_date: str, end_date: str) -> list:
        """Get traffic breakdown by source/medium."""
        result = self.run_report(
            start_date=start_date,
            end_date=end_date,
            metrics=["sessions", "totalUsers", "newUsers", "conversions", "totalRevenue"],
            dimensions=["sessionSource", "sessionMedium"],
        )

        # Parse response
        rows = []
        for row in result.get("rows", []):
            rows.append({
                "source": row["dimensionValues"][0]["value"],
                "medium": row["dimensionValues"][1]["value"],
                "sessions": int(row["metricValues"][0]["value"]),
                "users": int(row["metricValues"][1]["value"]),
                "new_users": int(row["metricValues"][2]["value"]),
                "conversions": float(row["metricValues"][3]["value"]),
                "revenue": float(row["metricValues"][4]["value"]),
            })

        return sorted(rows, key=lambda x: x["sessions"], reverse=True)

    def get_daily_traffic(self, start_date: str, end_date: str) -> list:
        """Get daily traffic metrics."""
        result = self.run_report(
            start_date=start_date,
            end_date=end_date,
            metrics=["sessions", "totalUsers", "newUsers", "conversions", "totalRevenue"],
            dimensions=["date"],
        )

        rows = []
        for row in result.get("rows", []):
            date_str = row["dimensionValues"][0]["value"]
            # Convert YYYYMMDD to YYYY-MM-DD
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            rows.append({
                "date": formatted_date,
                "sessions": int(row["metricValues"][0]["value"]),
                "users": int(row["metricValues"][1]["value"]),
                "new_users": int(row["metricValues"][2]["value"]),
                "conversions": float(row["metricValues"][3]["value"]),
                "revenue": float(row["metricValues"][4]["value"]),
            })

        return sorted(rows, key=lambda x: x["date"])

    def get_device_breakdown(self, start_date: str, end_date: str) -> list:
        """Get traffic breakdown by device category."""
        result = self.run_report(
            start_date=start_date,
            end_date=end_date,
            metrics=["sessions", "conversions", "totalRevenue"],
            dimensions=["deviceCategory"],
        )

        rows = []
        for row in result.get("rows", []):
            rows.append({
                "device": row["dimensionValues"][0]["value"],
                "sessions": int(row["metricValues"][0]["value"]),
                "conversions": float(row["metricValues"][1]["value"]),
                "revenue": float(row["metricValues"][2]["value"]),
            })

        return rows

    def get_landing_pages(self, start_date: str, end_date: str, limit: int = 50) -> list:
        """Get top landing pages by sessions."""
        result = self.run_report(
            start_date=start_date,
            end_date=end_date,
            metrics=["sessions", "conversions", "totalRevenue", "bounceRate"],
            dimensions=["landingPage"],
            limit=limit,
        )

        rows = []
        for row in result.get("rows", []):
            rows.append({
                "landing_page": row["dimensionValues"][0]["value"],
                "sessions": int(row["metricValues"][0]["value"]),
                "conversions": float(row["metricValues"][1]["value"]),
                "revenue": float(row["metricValues"][2]["value"]),
                "bounce_rate": float(row["metricValues"][3]["value"]),
            })

        return rows

    def save_data(self, data: dict | list, filename: str) -> Path:
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath

    def pull_last_30_days(self) -> dict:
        """Pull GA4 data for last 30 days."""
        if not self.configured:
            print("GA4 not configured. Skipping.")
            return {"error": "Not configured"}

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"Pulling GA4 data from {start_date} to {end_date}...")
        print(f"Property ID: {self.property_id}")

        try:
            # Get traffic sources
            print("  Fetching traffic sources...")
            traffic_sources = self.get_traffic_sources(start_date, end_date)
            self.save_data(traffic_sources, "traffic_sources.json")

            # Get daily traffic
            print("  Fetching daily traffic...")
            daily_traffic = self.get_daily_traffic(start_date, end_date)
            self.save_data(daily_traffic, "daily_traffic.json")

            # Get device breakdown
            print("  Fetching device breakdown...")
            devices = self.get_device_breakdown(start_date, end_date)
            self.save_data(devices, "device_breakdown.json")

            # Get top landing pages
            print("  Fetching landing pages...")
            landing_pages = self.get_landing_pages(start_date, end_date)
            self.save_data(landing_pages, "landing_pages.json")

            # Calculate totals
            total_sessions = sum(row["sessions"] for row in traffic_sources)
            total_users = sum(row["users"] for row in traffic_sources)
            total_conversions = sum(row["conversions"] for row in traffic_sources)
            total_revenue = sum(row["revenue"] for row in traffic_sources)

            summary = {
                "period": {"start": start_date, "end": end_date},
                "total_sessions": total_sessions,
                "total_users": total_users,
                "total_conversions": total_conversions,
                "total_revenue": total_revenue,
                "top_sources": traffic_sources[:10],
                "devices": devices,
            }

            self.save_data(summary, "summary_last_30d.json")

            # Print summary
            print("\n" + "=" * 50)
            print("GOOGLE ANALYTICS 4 SUMMARY")
            print("=" * 50)
            print(f"  Period: {start_date} to {end_date}")
            print(f"  Sessions: {total_sessions:,}")
            print(f"  Users: {total_users:,}")
            print(f"  Conversions: {total_conversions:,.0f}")
            print(f"  Revenue (GA4): ${total_revenue:,.2f}")
            print(f"\n  Top Traffic Sources:")
            for src in traffic_sources[:5]:
                print(f"    - {src['source']}/{src['medium']}: {src['sessions']:,} sessions")
            print(f"\n  Note: Use Shopify as source of truth for revenue.")
            print(f"  GA4 is for traffic triangulation only.")
            print("=" * 50)

            return summary

        except Exception as e:
            print(f"Error pulling GA4 data: {e}")
            return {"error": str(e)}


def setup_instructions():
    """Print setup instructions for GA4."""
    print("""
================================================================================
GOOGLE ANALYTICS 4 API SETUP
================================================================================

1. Find Your GA4 Property ID:
   - Go to: https://analytics.google.com
   - Click Admin (gear icon)
   - Under Property, click "Property Details"
   - Copy the Property ID (numbers only, e.g., "123456789")

2. Enable GA4 Data API:
   - Go to: https://console.cloud.google.com
   - Select your project (same one used for Google Ads)
   - Go to APIs & Services > Library
   - Search for "Google Analytics Data API"
   - Click Enable

3. Set Up OAuth (if not already done for Google Ads):
   - The same OAuth credentials used for Google Ads will work
   - Run: python setup_ga4_oauth.py (if scopes not included)

4. Add to .env:
   GA4_PROPERTY_ID=123456789

   If using a separate refresh token:
   GA4_REFRESH_TOKEN=your-refresh-token

================================================================================

Note: GA4 data has a 24-48 hour processing delay.
Use Shopify as the source of truth for conversion/revenue data.
GA4 is best used for traffic source triangulation.
================================================================================
""")


def main():
    """Test the connector or show setup instructions."""
    connector = GA4Connector()

    if not connector.configured:
        setup_instructions()
        return

    try:
        data = connector.pull_last_30_days()
        print("\nGA4 data pulled successfully!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
