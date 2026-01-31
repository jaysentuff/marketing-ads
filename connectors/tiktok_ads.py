"""
TikTok Ads Connector for TuffWraps Marketing Attribution

Pulls campaign-level spend, impressions, conversions data for CAM calculation.
Uses TikTok Marketing API v1.3
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import json

from dotenv import load_dotenv
import requests

load_dotenv()


class TikTokAdsConnector:
    """Connector for TikTok Marketing API."""

    API_VERSION = "v1.3"
    BASE_URL = f"https://business-api.tiktok.com/open_api/{API_VERSION}"

    def __init__(self):
        self.access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        self.advertiser_id = os.getenv("TIKTOK_ADVERTISER_ID")

        self.data_dir = Path(__file__).parent / "data" / "tiktok_ads"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Check if configured
        self.configured = bool(self.access_token and self.advertiser_id)

    def _check_credentials(self):
        """Verify all required credentials are present."""
        missing = []
        if not self.access_token:
            missing.append("TIKTOK_ACCESS_TOKEN")
        if not self.advertiser_id:
            missing.append("TIKTOK_ADVERTISER_ID")

        if missing:
            raise ValueError(f"Missing credentials: {', '.join(missing)}")

        return True

    def _make_request(self, endpoint: str, params: dict = None, method: str = "GET") -> dict:
        """Make authenticated request to TikTok API."""
        if params is None:
            params = {}

        headers = {
            "Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

        url = f"{self.BASE_URL}/{endpoint}"

        if method == "GET":
            response = requests.get(url, headers=headers, params=params)
        else:
            response = requests.post(url, headers=headers, json=params)

        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"TikTok API Error: {data.get('message', response.text)}")

        return data.get("data", {})

    def get_advertiser_info(self) -> dict:
        """Get advertiser information to verify connection."""
        self._check_credentials()

        data = self._make_request(
            "advertiser/info/",
            params={
                "advertiser_ids": json.dumps([self.advertiser_id]),
                "fields": json.dumps(["name", "company", "status", "currency", "timezone"])
            }
        )

        advertiser = data.get("list", [{}])[0] if data.get("list") else {}

        print(f"Connected to TikTok Ads Account: {advertiser.get('name')}")
        print(f"  Advertiser ID: {self.advertiser_id}")
        print(f"  Company: {advertiser.get('company')}")
        print(f"  Currency: {advertiser.get('currency')}")
        print(f"  Status: {advertiser.get('status')}")

        return advertiser

    def get_campaign_insights(self, start_date: str, end_date: str) -> list[dict]:
        """
        Get campaign-level performance data.

        Args:
            start_date: YYYY-MM-DD format
            end_date: YYYY-MM-DD format

        Returns list of campaign performance data.
        """
        self._check_credentials()

        # TikTok uses integrated reporting endpoint
        params = {
            "advertiser_id": self.advertiser_id,
            "report_type": "BASIC",
            "dimensions": json.dumps(["campaign_id"]),
            "data_level": "AUCTION_CAMPAIGN",
            "start_date": start_date,
            "end_date": end_date,
            "metrics": json.dumps([
                "campaign_name",
                "spend",
                "impressions",
                "clicks",
                "ctr",
                "cpc",
                "cpm",
                "conversions",
                "cost_per_conversion",
                "conversion_rate",
                "reach",
                "frequency"
            ]),
            "page_size": 100
        }

        data = self._make_request("report/integrated/get/", params)

        campaigns = []
        for row in data.get("list", []):
            metrics = row.get("metrics", {})
            dimensions = row.get("dimensions", {})

            campaigns.append({
                "campaign_id": dimensions.get("campaign_id"),
                "campaign_name": metrics.get("campaign_name", "Unknown"),
                "spend": float(metrics.get("spend", 0) or 0),
                "impressions": int(metrics.get("impressions", 0) or 0),
                "clicks": int(metrics.get("clicks", 0) or 0),
                "ctr": float(metrics.get("ctr", 0) or 0),
                "cpc": float(metrics.get("cpc", 0) or 0),
                "cpm": float(metrics.get("cpm", 0) or 0),
                "conversions": int(metrics.get("conversions", 0) or 0),
                "cost_per_conversion": float(metrics.get("cost_per_conversion", 0) or 0),
                "conversion_rate": float(metrics.get("conversion_rate", 0) or 0),
                "reach": int(metrics.get("reach", 0) or 0),
                "frequency": float(metrics.get("frequency", 0) or 0),
            })

        return campaigns

    def get_daily_insights(self, start_date: str, end_date: str) -> list[dict]:
        """
        Get daily aggregate performance data.

        Args:
            start_date: YYYY-MM-DD format
            end_date: YYYY-MM-DD format
        """
        self._check_credentials()

        params = {
            "advertiser_id": self.advertiser_id,
            "report_type": "BASIC",
            "dimensions": json.dumps(["stat_time_day"]),
            "data_level": "AUCTION_ADVERTISER",
            "start_date": start_date,
            "end_date": end_date,
            "metrics": json.dumps([
                "spend",
                "impressions",
                "clicks",
                "conversions",
                "cost_per_conversion",
                "reach"
            ]),
            "page_size": 100
        }

        data = self._make_request("report/integrated/get/", params)

        daily_data = []
        for row in data.get("list", []):
            metrics = row.get("metrics", {})
            dimensions = row.get("dimensions", {})

            daily_data.append({
                "date": dimensions.get("stat_time_day"),
                "spend": float(metrics.get("spend", 0) or 0),
                "impressions": int(metrics.get("impressions", 0) or 0),
                "clicks": int(metrics.get("clicks", 0) or 0),
                "conversions": int(metrics.get("conversions", 0) or 0),
                "cost_per_conversion": float(metrics.get("cost_per_conversion", 0) or 0),
                "reach": int(metrics.get("reach", 0) or 0),
            })

        return daily_data

    def save_data(self, data: list | dict, filename: str):
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath

    def pull_last_30_days(self) -> dict:
        """Pull and analyze last 30 days of TikTok ads data."""
        if not self.configured:
            print("TikTok Ads not configured. Skipping.")
            return {"error": "Not configured"}

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"Pulling TikTok Ads data from {start_date} to {end_date}...")

        # Get campaign insights
        print("  Fetching campaign insights...")
        campaigns = self.get_campaign_insights(start_date, end_date)
        self.save_data(campaigns, "campaigns_last_30d.json")

        # Get daily breakdown
        print("  Fetching daily breakdown...")
        daily = self.get_daily_insights(start_date, end_date)
        self.save_data(daily, "daily_last_30d.json")

        # Calculate summary metrics
        total_spend = sum(c.get("spend", 0) for c in campaigns)
        total_impressions = sum(c.get("impressions", 0) for c in campaigns)
        total_clicks = sum(c.get("clicks", 0) for c in campaigns)
        total_conversions = sum(c.get("conversions", 0) for c in campaigns)

        summary = {
            "total_spend": total_spend,
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "ctr": (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
            "cpc": total_spend / total_clicks if total_clicks > 0 else 0,
            "cpa": total_spend / total_conversions if total_conversions > 0 else 0,
            "active_campaigns": len([c for c in campaigns if c.get("spend", 0) > 0]),
            "date_range": {"start": start_date, "end": end_date}
        }
        self.save_data(summary, "summary_last_30d.json")

        print("\n" + "=" * 50)
        print("TIKTOK ADS SUMMARY - LAST 30 DAYS")
        print("=" * 50)
        print(f"Total Spend:      ${summary['total_spend']:,.2f}")
        print(f"Impressions:      {summary['total_impressions']:,}")
        print(f"Clicks:           {summary['total_clicks']:,}")
        print(f"Conversions:      {summary['total_conversions']:,}")
        print(f"CTR:              {summary['ctr']:.2f}%")
        print(f"CPC:              ${summary['cpc']:.2f}")
        print(f"CPA:              ${summary['cpa']:.2f}")
        print(f"Active Campaigns: {summary['active_campaigns']}")
        print("=" * 50)

        return {
            "campaigns": campaigns,
            "daily": daily,
            "summary": summary
        }


def main():
    """Test the connector."""
    connector = TikTokAdsConnector()

    if not connector.configured:
        print("TikTok Ads not configured.")
        print("Please add TIKTOK_ACCESS_TOKEN and TIKTOK_ADVERTISER_ID to .env")
        return

    try:
        # Test connection
        connector.get_advertiser_info()

        # Pull data
        connector.pull_last_30_days()

    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
