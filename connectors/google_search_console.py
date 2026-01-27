"""
Google Search Console Connector for TuffWraps Marketing Attribution

Pulls search analytics data to measure:
- Branded search volume (indicates TOF effectiveness)
- Organic search trends
- Search impressions/clicks/CTR by query

Uses OAuth 2.0 with existing Google credentials.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()


class GoogleSearchConsoleConnector:
    """Connector for Google Search Console Search Analytics API."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE = "https://searchconsole.googleapis.com/webmasters/v3"

    def __init__(self):
        self.client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
        self.refresh_token = os.getenv("GSC_REFRESH_TOKEN") or os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
        self.site_url = os.getenv("GSC_SITE_URL", "https://tuffwraps.com")

        self.access_token = None
        self.data_dir = Path(__file__).parent / "data" / "gsc"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError("Missing Google OAuth credentials. Check .env file.")

        # Get access token
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

    def _api_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        """Make API request to GSC."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        url = f"{self.API_BASE}/{endpoint}"

        if method == "GET":
            response = requests.get(url, headers=headers)
        else:
            response = requests.post(url, headers=headers, json=data)

        if response.status_code == 401:
            # Token expired, refresh and retry
            self._refresh_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            if method == "GET":
                response = requests.get(url, headers=headers)
            else:
                response = requests.post(url, headers=headers, json=data)

        if response.status_code != 200:
            raise Exception(f"GSC API Error: {response.status_code} - {response.text}")

        return response.json()

    def list_sites(self) -> list:
        """List all verified sites in GSC."""
        result = self._api_request("sites")
        return result.get("siteEntry", [])

    def get_search_analytics(
        self,
        start_date: str,
        end_date: str,
        dimensions: list = None,
        row_limit: int = 1000,
        search_type: str = "web",
    ) -> list:
        """
        Get search analytics data.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            dimensions: List of dimensions like ["query", "date", "page", "country", "device"]
            row_limit: Max rows to return (max 25000)
            search_type: "web", "image", "video", "news"

        Returns:
            List of rows with metrics
        """
        if dimensions is None:
            dimensions = ["query", "date"]

        # URL encode the site URL
        encoded_site = requests.utils.quote(self.site_url, safe="")

        data = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "searchType": search_type,
        }

        result = self._api_request(
            f"sites/{encoded_site}/searchAnalytics/query",
            method="POST",
            data=data,
        )

        return result.get("rows", [])

    def get_branded_vs_nonbranded(
        self,
        start_date: str,
        end_date: str,
        brand_terms: list = None,
    ) -> dict:
        """
        Get branded vs non-branded search breakdown.

        Args:
            brand_terms: List of brand-related search terms
                         Default: ["tuffwraps", "tuff wraps", "tuff-wraps"]

        Returns:
            Dict with branded and non-branded totals
        """
        if brand_terms is None:
            brand_terms = ["tuffwraps", "tuff wraps", "tuff-wraps", "tuff wrap"]

        # Get all queries
        rows = self.get_search_analytics(
            start_date=start_date,
            end_date=end_date,
            dimensions=["query"],
            row_limit=5000,
        )

        branded = {"clicks": 0, "impressions": 0, "queries": []}
        non_branded = {"clicks": 0, "impressions": 0, "queries": []}

        for row in rows:
            query = row["keys"][0].lower()
            is_branded = any(term in query for term in brand_terms)

            target = branded if is_branded else non_branded
            target["clicks"] += row.get("clicks", 0)
            target["impressions"] += row.get("impressions", 0)
            target["queries"].append({
                "query": row["keys"][0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0),
                "position": row.get("position", 0),
            })

        # Calculate CTR
        branded["ctr"] = branded["clicks"] / branded["impressions"] if branded["impressions"] > 0 else 0
        non_branded["ctr"] = non_branded["clicks"] / non_branded["impressions"] if non_branded["impressions"] > 0 else 0

        # Sort queries by clicks
        branded["queries"].sort(key=lambda x: x["clicks"], reverse=True)
        non_branded["queries"].sort(key=lambda x: x["clicks"], reverse=True)

        # Keep top 50 each
        branded["queries"] = branded["queries"][:50]
        non_branded["queries"] = non_branded["queries"][:50]

        return {
            "branded": branded,
            "non_branded": non_branded,
            "total_clicks": branded["clicks"] + non_branded["clicks"],
            "branded_percentage": branded["clicks"] / (branded["clicks"] + non_branded["clicks"]) * 100
            if (branded["clicks"] + non_branded["clicks"]) > 0
            else 0,
        }

    def get_daily_branded_trend(
        self,
        start_date: str,
        end_date: str,
        brand_terms: list = None,
    ) -> list:
        """
        Get daily branded search trend for correlation with TOF spend.

        Returns list of daily branded search metrics.
        """
        if brand_terms is None:
            brand_terms = ["tuffwraps", "tuff wraps", "tuff-wraps", "tuff wrap"]

        # Get queries by date
        rows = self.get_search_analytics(
            start_date=start_date,
            end_date=end_date,
            dimensions=["query", "date"],
            row_limit=25000,
        )

        # Aggregate by date
        daily_data = {}

        for row in rows:
            query = row["keys"][0].lower()
            date = row["keys"][1]
            is_branded = any(term in query for term in brand_terms)

            if date not in daily_data:
                daily_data[date] = {
                    "date": date,
                    "branded_clicks": 0,
                    "branded_impressions": 0,
                    "non_branded_clicks": 0,
                    "non_branded_impressions": 0,
                }

            if is_branded:
                daily_data[date]["branded_clicks"] += row.get("clicks", 0)
                daily_data[date]["branded_impressions"] += row.get("impressions", 0)
            else:
                daily_data[date]["non_branded_clicks"] += row.get("clicks", 0)
                daily_data[date]["non_branded_impressions"] += row.get("impressions", 0)

        # Convert to list and sort by date
        result = list(daily_data.values())
        result.sort(key=lambda x: x["date"])

        return result

    def save_data(self, data: dict | list, filename: str) -> Path:
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath

    def pull_last_30_days(self) -> dict:
        """Pull all GSC data for last 30 days."""
        # GSC has 3-day data delay
        end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=33)).strftime("%Y-%m-%d")

        print(f"Pulling GSC data from {start_date} to {end_date}...")
        print(f"Site: {self.site_url}")

        # Get branded vs non-branded breakdown
        print("  Fetching branded vs non-branded breakdown...")
        branded_data = self.get_branded_vs_nonbranded(start_date, end_date)
        self.save_data(branded_data, "branded_vs_nonbranded.json")

        # Get daily trend for correlation analysis
        print("  Fetching daily branded trend...")
        daily_trend = self.get_daily_branded_trend(start_date, end_date)
        self.save_data(daily_trend, "daily_branded_trend.json")

        # Get top queries overall
        print("  Fetching top queries...")
        top_queries = self.get_search_analytics(
            start_date=start_date,
            end_date=end_date,
            dimensions=["query"],
            row_limit=500,
        )
        self.save_data(top_queries, "top_queries.json")

        # Print summary
        print("\n" + "=" * 50)
        print("GOOGLE SEARCH CONSOLE SUMMARY")
        print("=" * 50)
        print(f"  Period: {start_date} to {end_date}")
        print(f"\n  Total Clicks: {branded_data['total_clicks']:,}")
        print(f"  Branded Clicks: {branded_data['branded']['clicks']:,} ({branded_data['branded_percentage']:.1f}%)")
        print(f"  Non-Branded Clicks: {branded_data['non_branded']['clicks']:,}")
        print(f"\n  Branded Impressions: {branded_data['branded']['impressions']:,}")
        print(f"  Branded CTR: {branded_data['branded']['ctr']*100:.2f}%")

        print("\n  Top 10 Branded Queries:")
        for q in branded_data["branded"]["queries"][:10]:
            query = q['query'].encode('ascii', 'replace').decode('ascii')
            print(f"    - {query}: {q['clicks']} clicks, {q['impressions']} impressions")

        print("\n  Top 10 Non-Branded Queries:")
        for q in branded_data["non_branded"]["queries"][:10]:
            query = q['query'].encode('ascii', 'replace').decode('ascii')
            print(f"    - {query}: {q['clicks']} clicks, {q['impressions']} impressions")

        print("=" * 50)

        return {
            "branded_breakdown": branded_data,
            "daily_trend": daily_trend,
            "top_queries": top_queries,
        }


def main():
    """Test the connector."""
    try:
        connector = GoogleSearchConsoleConnector()

        # First, list sites to verify access
        print("Checking GSC access...")
        sites = connector.list_sites()
        print(f"Found {len(sites)} verified sites:")
        for site in sites:
            print(f"  - {site.get('siteUrl')}")

        # Pull data
        data = connector.pull_last_30_days()
        print("\nGSC data pulled successfully!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
