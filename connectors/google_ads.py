"""
Google Ads Connector for TuffWraps Marketing Attribution

Pulls campaign-level spend, clicks, conversions data for CAM calculation.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv()


class GoogleAdsConnector:
    """Connector for Google Ads API."""

    def __init__(self):
        self.client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
        self.developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
        self.customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
        self.refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
        self.login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

        self.client = None
        self.data_dir = Path(__file__).parent / "data" / "google_ads"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _check_credentials(self):
        """Verify all required credentials are present."""
        missing = []
        if not self.client_id:
            missing.append("GOOGLE_ADS_CLIENT_ID")
        if not self.client_secret:
            missing.append("GOOGLE_ADS_CLIENT_SECRET")
        if not self.developer_token:
            missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
        if not self.customer_id:
            missing.append("GOOGLE_ADS_CUSTOMER_ID")
        if not self.refresh_token:
            missing.append("GOOGLE_ADS_REFRESH_TOKEN")

        if missing:
            raise ValueError(f"Missing credentials: {', '.join(missing)}")

        return True

    def connect(self):
        """Initialize the Google Ads client."""
        self._check_credentials()

        try:
            from google.ads.googleads.client import GoogleAdsClient
        except ImportError:
            raise ImportError("google-ads package not installed. Run: pip install google-ads")

        credentials = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "developer_token": self.developer_token,
            "refresh_token": self.refresh_token,
            "use_proto_plus": True,
        }

        if self.login_customer_id:
            credentials["login_customer_id"] = self.login_customer_id

        self.client = GoogleAdsClient.load_from_dict(credentials)
        print(f"Connected to Google Ads for customer: {self.customer_id}")
        return True

    def get_campaign_performance(self, start_date: str, end_date: str) -> list[dict]:
        """
        Get campaign performance metrics.

        Args:
            start_date: YYYY-MM-DD format
            end_date: YYYY-MM-DD format

        Returns:
            List of campaign performance records
        """
        if not self.client:
            self.connect()

        ga_service = self.client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                segments.date,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.conversions_value,
                metrics.ctr,
                metrics.average_cpc
            FROM campaign
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                AND campaign.status != 'REMOVED'
            ORDER BY segments.date DESC, metrics.cost_micros DESC
        """

        # Remove the dashes from customer_id for API call
        customer_id = self.customer_id.replace("-", "")

        response = ga_service.search_stream(customer_id=customer_id, query=query)

        results = []
        for batch in response:
            for row in batch.results:
                results.append({
                    "campaign_id": row.campaign.id,
                    "campaign_name": row.campaign.name,
                    "campaign_status": row.campaign.status.name,
                    "channel_type": row.campaign.advertising_channel_type.name,
                    "date": row.segments.date,
                    "spend": row.metrics.cost_micros / 1_000_000,  # Convert micros to dollars
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                    "ctr": row.metrics.ctr,
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,
                })

        return results

    def get_daily_spend(self, start_date: str, end_date: str) -> dict:
        """
        Get total daily spend across all campaigns.

        Returns dict: {date: total_spend}
        """
        campaigns = self.get_campaign_performance(start_date, end_date)

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

        print(f"Pulling Google Ads data from {start_date} to {end_date}...")
        data = self.get_campaign_performance(start_date, end_date)
        self.save_data(data, "campaigns_last_30d.json")

        # Calculate summary
        total_spend = sum(r["spend"] for r in data)
        total_clicks = sum(r["clicks"] for r in data)
        total_conversions = sum(r["conversions"] for r in data)

        print(f"\nGoogle Ads Summary (Last 30 Days):")
        print(f"  Total Spend: ${total_spend:,.2f}")
        print(f"  Total Clicks: {total_clicks:,}")
        print(f"  Total Conversions: {total_conversions:,.1f}")
        if total_spend > 0:
            print(f"  Blended CPA: ${total_spend/total_conversions:,.2f}" if total_conversions > 0 else "  Blended CPA: N/A")

        return data


def main():
    """Test the connector."""
    connector = GoogleAdsConnector()

    try:
        data = connector.pull_last_30_days()
        print(f"\nPulled {len(data)} campaign-day records")
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease set up your .env file with Google Ads credentials.")
        print("See README.md for setup instructions.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
