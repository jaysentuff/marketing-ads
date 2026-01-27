"""
Kendall.ai Connector for TuffWraps Marketing Attribution

Connects to Kendall's MCP server to pull attributed revenue data.
Uses Streamable HTTP transport (POST to SSE endpoint).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import requests


class KendallConnector:
    """Connector for Kendall.ai Attribution via MCP."""

    # Kendall MCP endpoint
    MCP_URL = "https://mcp.kendall.ai/sse?store_id=1126&secret=1waF3I5RxGA0cyNjm0m0"

    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        self.request_id = 0
        self.data_dir = Path(__file__).parent / "data" / "kendall"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize connection
        self._initialize()

    def _next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def _call_method(self, method: str, params: dict = None) -> dict:
        """Make JSON-RPC call to Kendall MCP."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {}
        }

        response = requests.post(
            self.MCP_URL,
            json=payload,
            headers=self.headers,
            timeout=60
        )

        # Parse SSE response
        result = None
        for line in response.text.split("\n"):
            if line.startswith("data:"):
                text = line[5:].strip()
                if text:
                    data = json.loads(text)
                    if "error" in data:
                        raise Exception(f"Kendall API Error: {data['error']}")
                    result = data.get("result", data)

        return result or {}

    def _initialize(self):
        """Initialize MCP connection."""
        result = self._call_method("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tuffwraps-cam", "version": "1.0"}
        })
        print(f"Connected to Kendall: {result.get('serverInfo', {}).get('name', 'unknown')}")

    def call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """Call a Kendall MCP tool."""
        return self._call_method("tools/call", {
            "name": tool_name,
            "arguments": arguments or {}
        })

    def get_attributed_orders(self, start_date: str, end_date: str, limit: int = 1000) -> list:
        """
        Get orders with attribution data.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            limit: Max orders to return
        """
        result = self.call_tool("get_attributed_orders", {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit
        })

        return self._extract_content(result)

    def get_all_sources_attribution(self, start_date: str, end_date: str,
                                      attribution_model: str = "last_click_per_channel") -> dict:
        """
        Get attribution breakdown by traffic source.

        Args:
            attribution_model: "kendall", "first_click", "last_click", etc.

        Returns top campaigns per source with attributed revenue.
        """
        result = self.call_tool("get_all_sources_attribution", {
            "date_start": start_date,
            "date_end": end_date,
            "attribution_model": attribution_model,
            "include_breakdowns": True
        })

        return self._extract_content(result)

    def _extract_content(self, result: dict):
        """Extract text content from MCP tool response."""
        if not result:
            return {}

        if "content" in result:
            for item in result["content"]:
                if item.get("type") == "text":
                    text = item["text"]
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"raw": text}

        return result

    def get_historical_metrics(self, start_date: str, end_date: str) -> dict:
        """Get daily historical metrics."""
        result = self.call_tool("get_historical_metrics", {
            "start_date": start_date,
            "end_date": end_date
        })
        return self._extract_content(result)

    def get_profit_loss_report(self, start_date: str, end_date: str) -> dict:
        """Get P&L report with all costs and revenue."""
        result = self.call_tool("get_profit_loss_report", {
            "date_start": start_date,
            "date_end": end_date
        })
        return self._extract_content(result)

    def get_ads_report(self, start_date: str, end_date: str) -> dict:
        """Get ads performance report (top 50 by spend)."""
        result = self.call_tool("get_ads_report", {
            "start_date": start_date,
            "end_date": end_date
        })
        return self._extract_content(result)

    def save_data(self, data: dict | list, filename: str):
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath

    def pull_data(self, days: int = 60) -> dict:
        """Pull all attribution data for specified number of days.

        Args:
            days: Number of days to pull (default 60 for 30-day comparisons)
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        print(f"Pulling Kendall data from {start_date} to {end_date} ({days} days)...")

        # Get attribution by source
        print("  Fetching source attribution...")
        attribution = self.get_all_sources_attribution(start_date, end_date)
        self.save_data(attribution, "attribution_by_source.json")

        # Get P&L report
        print("  Fetching P&L report...")
        pnl = self.get_profit_loss_report(start_date, end_date)
        self.save_data(pnl, "profit_loss.json")

        # Get historical metrics
        print("  Fetching historical metrics...")
        metrics = self.get_historical_metrics(start_date, end_date)
        self.save_data(metrics, "historical_metrics.json")

        # Print summary
        print("\n" + "=" * 50)
        print("KENDALL ATTRIBUTION SUMMARY")
        print("=" * 50)

        if isinstance(attribution, dict):
            for source, data in attribution.items():
                if isinstance(data, dict):
                    revenue = data.get("attributed_revenue", data.get("revenue", 0))
                    orders = data.get("attributed_orders", data.get("orders", 0))
                    print(f"  {source}: ${revenue:,.2f} ({orders} orders)")
                elif isinstance(data, list):
                    print(f"  {source}: {len(data)} campaigns")

        print("=" * 50)

        return {
            "attribution": attribution,
            "pnl": pnl,
            "metrics": metrics,
            "days_pulled": days
        }

    def pull_last_30_days(self) -> dict:
        """Pull all attribution data for last 30 days (legacy method)."""
        return self.pull_data(days=30)

    def pull_last_60_days(self) -> dict:
        """Pull all attribution data for last 60 days (for 30-day comparisons)."""
        return self.pull_data(days=60)


def main():
    """Pull 60 days of Kendall data for signal triangulation comparisons."""
    try:
        connector = KendallConnector()
        # Pull 60 days to support 30-day comparisons (need current 30 + previous 30)
        data = connector.pull_data(days=60)
        print(f"\nKendall data pulled successfully! ({data.get('days_pulled', 60)} days)")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
