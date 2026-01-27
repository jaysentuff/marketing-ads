"""
Meta (Facebook) Ads Connector for TuffWraps Marketing Attribution

Pulls campaign-level spend, impressions, conversions data for CAM calculation.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import json

from dotenv import load_dotenv
import requests

load_dotenv()


class MetaAdsConnector:
    """Connector for Meta Marketing API."""

    API_VERSION = "v18.0"
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN")
        self.ad_account_id = os.getenv("META_AD_ACCOUNT_ID")

        self.data_dir = Path(__file__).parent / "data" / "meta_ads"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _check_credentials(self):
        """Verify all required credentials are present."""
        missing = []
        if not self.access_token:
            missing.append("META_ACCESS_TOKEN")
        if not self.ad_account_id:
            missing.append("META_AD_ACCOUNT_ID")

        if missing:
            raise ValueError(f"Missing credentials: {', '.join(missing)}")

        # Ensure ad_account_id has act_ prefix
        if not self.ad_account_id.startswith("act_"):
            self.ad_account_id = f"act_{self.ad_account_id}"

        return True

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated request to Meta API."""
        if params is None:
            params = {}

        params["access_token"] = self.access_token

        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, params=params)

        if response.status_code != 200:
            error_data = response.json().get("error", {})
            raise Exception(f"Meta API Error: {error_data.get('message', response.text)}")

        return response.json()

    def get_account_info(self) -> dict:
        """Get ad account information to verify connection."""
        self._check_credentials()

        data = self._make_request(
            self.ad_account_id,
            params={"fields": "name,account_id,currency,timezone_name,amount_spent"}
        )

        print(f"Connected to Meta Ads Account: {data.get('name')}")
        print(f"  Account ID: {data.get('account_id')}")
        print(f"  Currency: {data.get('currency')}")
        print(f"  Timezone: {data.get('timezone_name')}")

        return data

    def get_campaign_insights(self, start_date: str, end_date: str) -> list[dict]:
        """
        Get campaign performance insights.

        Args:
            start_date: YYYY-MM-DD format
            end_date: YYYY-MM-DD format

        Returns:
            List of campaign performance records by day
        """
        self._check_credentials()

        # Fields to retrieve
        fields = [
            "campaign_id",
            "campaign_name",
            "objective",
            "spend",
            "impressions",
            "clicks",
            "reach",
            "cpc",
            "cpm",
            "ctr",
            "actions",  # Contains conversions
            "action_values",  # Contains conversion values
        ]

        params = {
            "fields": ",".join(fields),
            "time_range": json.dumps({"since": start_date, "until": end_date}),
            "time_increment": 1,  # Daily breakdown
            "level": "campaign",
            "limit": 500,
        }

        all_results = []
        endpoint = f"{self.ad_account_id}/insights"

        while True:
            data = self._make_request(endpoint, params)

            for row in data.get("data", []):
                # Parse actions to get conversions
                purchases = 0
                purchase_value = 0

                for action in row.get("actions", []):
                    if action.get("action_type") == "purchase":
                        purchases = float(action.get("value", 0))

                for action_value in row.get("action_values", []):
                    if action_value.get("action_type") == "purchase":
                        purchase_value = float(action_value.get("value", 0))

                all_results.append({
                    "campaign_id": row.get("campaign_id"),
                    "campaign_name": row.get("campaign_name"),
                    "objective": row.get("objective"),
                    "date": row.get("date_start"),
                    "spend": float(row.get("spend", 0)),
                    "impressions": int(row.get("impressions", 0)),
                    "clicks": int(row.get("clicks", 0)),
                    "reach": int(row.get("reach", 0)),
                    "cpc": float(row.get("cpc", 0)) if row.get("cpc") else 0,
                    "cpm": float(row.get("cpm", 0)) if row.get("cpm") else 0,
                    "ctr": float(row.get("ctr", 0)) if row.get("ctr") else 0,
                    "purchases": purchases,
                    "purchase_value": purchase_value,
                    "roas": purchase_value / float(row.get("spend", 1)) if float(row.get("spend", 0)) > 0 else 0,
                })

            # Handle pagination
            paging = data.get("paging", {})
            if "next" in paging:
                # Extract cursor for next page
                next_url = paging["next"]
                # Make direct request to next URL
                response = requests.get(next_url)
                data = response.json()
                continue
            else:
                break

        return all_results

    def get_daily_spend(self, start_date: str, end_date: str) -> dict:
        """
        Get total daily spend across all campaigns.

        Returns dict: {date: total_spend}
        """
        campaigns = self.get_campaign_insights(start_date, end_date)

        daily_spend = {}
        for row in campaigns:
            date = row["date"]
            if date not in daily_spend:
                daily_spend[date] = 0
            daily_spend[date] += row["spend"]

        return daily_spend

    def save_data(self, data: list[dict], filename: str = None):
        """Save pulled data to JSON file."""
        if filename is None:
            filename = f"campaigns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        print(f"Saved {len(data)} records to {filepath}")
        return filepath

    def pull_last_30_days(self) -> list[dict]:
        """Convenience method to pull last 30 days of data."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"Pulling Meta Ads data from {start_date} to {end_date}...")

        # Verify connection first
        self.get_account_info()

        data = self.get_campaign_insights(start_date, end_date)
        self.save_data(data, "campaigns_last_30d.json")

        # Calculate summary
        total_spend = sum(r["spend"] for r in data)
        total_impressions = sum(r["impressions"] for r in data)
        total_purchases = sum(r["purchases"] for r in data)
        total_revenue = sum(r["purchase_value"] for r in data)

        print(f"\nMeta Ads Summary (Last 30 Days):")
        print(f"  Total Spend: ${total_spend:,.2f}")
        print(f"  Total Impressions: {total_impressions:,}")
        print(f"  Total Purchases: {total_purchases:,.0f}")
        print(f"  Total Revenue (Attributed): ${total_revenue:,.2f}")
        if total_spend > 0:
            print(f"  Platform ROAS: {total_revenue/total_spend:.2f}x")
            if total_purchases > 0:
                print(f"  Platform CPA: ${total_spend/total_purchases:,.2f}")

        return data


def main():
    """Test the connector."""
    connector = MetaAdsConnector()

    try:
        data = connector.pull_last_30_days()
        print(f"\nPulled {len(data)} campaign-day records")
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease set up your .env file with Meta Ads credentials.")
        print("See README.md for setup instructions.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
