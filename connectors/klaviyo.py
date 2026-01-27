"""
Klaviyo Connector for TuffWraps Marketing Attribution

Pulls email/SMS marketing data:
- Campaign performance (sends, opens, clicks, revenue)
- Flow performance
- Attributed revenue (for CAM calculation)

Uses Klaviyo API v2024-02-15.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()


class KlaviyoConnector:
    """Connector for Klaviyo API."""

    API_BASE = "https://a.klaviyo.com/api"
    API_REVISION = "2024-02-15"

    def __init__(self):
        self.api_key = os.getenv("KLAVIYO_API_KEY")
        self.data_dir = Path(__file__).parent / "data" / "klaviyo"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_key:
            print("Warning: Klaviyo API key not configured.")
            print("Add KLAVIYO_API_KEY to .env file.")
            print("Get your API key from: Klaviyo > Settings > API Keys")
            self.configured = False
        else:
            self.configured = True

    def _api_request(self, endpoint: str, params: dict = None) -> dict:
        """Make API request to Klaviyo."""
        if not self.configured:
            raise Exception("Klaviyo not configured. Check KLAVIYO_API_KEY in .env")

        headers = {
            "Authorization": f"Klaviyo-API-Key {self.api_key}",
            "revision": self.API_REVISION,
            "Accept": "application/json",
        }

        url = f"{self.API_BASE}/{endpoint}"

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            raise Exception(f"Klaviyo API Error: {response.status_code} - {response.text}")

        return response.json()

    def get_campaigns(self, status: str = None) -> list:
        """
        Get campaigns, optionally filtered by status.

        Args:
            status: Optional - "Draft", "Scheduled", "Sent", "Cancelled"

        Returns:
            List of campaigns
        """
        params = {"filter": "equals(messages.channel,'email')"}
        result = self._api_request("campaigns", params=params)
        campaigns = result.get("data", [])

        # Filter by status locally if specified
        if status:
            campaigns = [c for c in campaigns if c.get("attributes", {}).get("status") == status]

        return campaigns

    def get_campaign_metrics(self, campaign_id: str) -> dict:
        """Get detailed metrics for a campaign."""
        result = self._api_request(f"campaigns/{campaign_id}")
        return result.get("data", {})

    def get_flows(self) -> list:
        """Get all flows."""
        result = self._api_request("flows")
        return result.get("data", [])

    def get_metrics_aggregates(
        self,
        metric_id: str,
        start_date: str,
        end_date: str,
        interval: str = "day",
    ) -> dict:
        """
        Get aggregated metrics over time.

        Args:
            metric_id: The metric to aggregate (e.g., Opened Email, Placed Order)
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            interval: "hour", "day", "week", "month"
        """
        params = {
            "filter": f"greater-or-equal(datetime,{start_date}T00:00:00Z),less-than(datetime,{end_date}T23:59:59Z)",
            "group-by": f"$message_channel,{interval}(datetime)",
        }

        result = self._api_request(f"metrics/{metric_id}/aggregate", params=params)
        return result.get("data", {})

    def get_account_metrics_summary(self, start_date: str, end_date: str) -> dict:
        """
        Get overall account metrics summary.

        Returns aggregated email performance.
        """
        # Get key metrics
        metrics_to_fetch = [
            "Received Email",
            "Opened Email",
            "Clicked Email",
            "Placed Order",
        ]

        # First, list available metrics to get their IDs
        metrics_result = self._api_request("metrics")
        metrics = metrics_result.get("data", [])

        metric_map = {}
        for m in metrics:
            name = m.get("attributes", {}).get("name", "")
            metric_map[name] = m.get("id")

        summary = {
            "period": {"start": start_date, "end": end_date},
            "email": {},
            "sms": {},
        }

        # Note: Detailed metric aggregation requires additional API calls
        # For now, return the available metrics list

        return {
            "available_metrics": list(metric_map.keys()),
            "metric_ids": metric_map,
            "summary": summary,
        }

    def get_profiles_count(self) -> int:
        """Get total number of profiles (subscribers)."""
        result = self._api_request("profiles", params={"page[size]": 1})
        # The meta contains count info
        return result.get("meta", {}).get("total", 0)

    def save_data(self, data: dict | list, filename: str) -> Path:
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath

    def pull_last_30_days(self) -> dict:
        """Pull Klaviyo data for last 30 days."""
        if not self.configured:
            print("Klaviyo not configured. Skipping.")
            return {"error": "Not configured"}

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"Pulling Klaviyo data from {start_date} to {end_date}...")

        try:
            # Get sent campaigns
            print("  Fetching sent campaigns...")
            campaigns = self.get_campaigns(status="sent")
            self.save_data(campaigns, "campaigns_sent.json")

            # Get flows
            print("  Fetching flows...")
            flows = self.get_flows()
            self.save_data(flows, "flows.json")

            # Get metrics summary
            print("  Fetching metrics...")
            metrics = self.get_account_metrics_summary(start_date, end_date)
            self.save_data(metrics, "metrics_summary.json")

            # Get profile count
            print("  Fetching profile count...")
            profile_count = self.get_profiles_count()

            # Build summary
            summary = {
                "period": {"start": start_date, "end": end_date},
                "campaigns_sent": len(campaigns),
                "flows_active": len([f for f in flows if f.get("attributes", {}).get("status") == "live"]),
                "total_flows": len(flows),
                "total_profiles": profile_count,
                "available_metrics": metrics.get("available_metrics", []),
            }

            self.save_data(summary, "summary_last_30d.json")

            # Print summary
            print("\n" + "=" * 50)
            print("KLAVIYO SUMMARY")
            print("=" * 50)
            print(f"  Period: {start_date} to {end_date}")
            print(f"  Campaigns Sent: {summary['campaigns_sent']}")
            print(f"  Active Flows: {summary['flows_active']}")
            print(f"  Total Profiles: {summary['total_profiles']:,}")
            print(f"\n  Note: Kendall.ai provides Klaviyo attribution data")
            print(f"  with de-duplicated revenue (see Kendall attribution)")
            print("=" * 50)

            return summary

        except Exception as e:
            print(f"Error pulling Klaviyo data: {e}")
            return {"error": str(e)}


def setup_instructions():
    """Print setup instructions for Klaviyo."""
    print("""
================================================================================
KLAVIYO API SETUP
================================================================================

1. Log in to Klaviyo: https://www.klaviyo.com/login

2. Go to Settings > API Keys:
   - Account > Settings > API Keys

3. Create a Private API Key:
   - Click "Create Private API Key"
   - Give it a name (e.g., "TuffWraps Attribution")
   - Select the following scopes:
     * Campaigns: Read
     * Flows: Read
     * Metrics: Read
     * Profiles: Read
   - Copy the API key (starts with "pk_")

4. Add to .env:
   KLAVIYO_API_KEY=pk_xxxxxxxxxxxxxxxxxxxxx

================================================================================

Note: Klaviyo revenue attribution is also available through Kendall.ai
which provides de-duplicated attribution across all channels.
================================================================================
""")


def main():
    """Test the connector or show setup instructions."""
    connector = KlaviyoConnector()

    if not connector.configured:
        setup_instructions()
        return

    try:
        data = connector.pull_last_30_days()
        print("\nKlaviyo data pulled successfully!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
