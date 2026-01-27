"""
ShipStation Connector for TuffWraps Marketing Attribution

Pulls actual shipping label costs from ShipStation API.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import json
import time
import base64

from dotenv import load_dotenv
import requests

load_dotenv()


class ShipStationConnector:
    """Connector for ShipStation API."""

    BASE_URL = "https://ssapi.shipstation.com"

    def __init__(self):
        self.api_key = os.getenv("SHIPSTATION_API_KEY")
        self.api_secret = os.getenv("SHIPSTATION_API_SECRET")

        # ShipStation uses Basic Auth with base64 encoded key:secret
        if self.api_key and self.api_secret:
            credentials = f"{self.api_key}:{self.api_secret}"
            encoded = base64.b64encode(credentials.encode()).decode()
            self.headers = {
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json",
            }
        else:
            self.headers = {}

        self.data_dir = Path(__file__).parent / "data" / "shipstation"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _check_credentials(self):
        """Verify credentials are present."""
        if not self.api_key or not self.api_secret:
            raise ValueError("Missing SHIPSTATION_API_KEY or SHIPSTATION_API_SECRET in .env file")
        return True

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated request to ShipStation API."""
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 429:  # Rate limited
            retry_after = int(response.headers.get("Retry-After", 30))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            return self._make_request(endpoint, params)

        if response.status_code != 200:
            raise Exception(f"ShipStation API Error ({response.status_code}): {response.text}")

        return response.json()

    def get_shipments(
        self,
        ship_date_start: str = None,
        ship_date_end: str = None,
        page: int = 1,
        page_size: int = 500,
    ) -> dict:
        """
        Get shipments with their costs.

        Args:
            ship_date_start: Start date (YYYY-MM-DD)
            ship_date_end: End date (YYYY-MM-DD)
            page: Page number
            page_size: Results per page (max 500)
        """
        params = {
            "page": page,
            "pageSize": min(page_size, 500),
        }

        if ship_date_start:
            params["shipDateStart"] = ship_date_start
        if ship_date_end:
            params["shipDateEnd"] = ship_date_end

        return self._make_request("shipments", params)

    def get_all_shipments(
        self,
        ship_date_start: str = None,
        ship_date_end: str = None,
        max_shipments: int = None,
    ) -> list[dict]:
        """Get all shipments with pagination."""
        self._check_credentials()

        all_shipments = []
        page = 1

        print(f"Fetching shipments from ShipStation...")
        if ship_date_start:
            print(f"  From: {ship_date_start}")
        if ship_date_end:
            print(f"  To: {ship_date_end}")

        while True:
            data = self.get_shipments(
                ship_date_start=ship_date_start,
                ship_date_end=ship_date_end,
                page=page,
            )

            shipments = data.get("shipments", [])
            total = data.get("total", 0)

            if not shipments:
                break

            all_shipments.extend(shipments)
            print(f"  Page {page}: {len(shipments)} shipments (total: {len(all_shipments)}/{total})")

            if max_shipments and len(all_shipments) >= max_shipments:
                all_shipments = all_shipments[:max_shipments]
                break

            if len(all_shipments) >= total:
                break

            page += 1
            time.sleep(0.5)  # Be nice to the API

        print(f"  Done! Total shipments: {len(all_shipments)}")
        return all_shipments

    def calculate_shipping_costs(self, shipments: list[dict]) -> dict:
        """
        Calculate shipping cost metrics from shipments.

        Returns total costs, average per shipment, and breakdown by carrier/service.
        """
        total_cost = 0
        shipment_count = len(shipments)
        by_carrier = {}
        by_service = {}
        daily_costs = {}

        for ship in shipments:
            cost = float(ship.get("shipmentCost", 0) or 0)
            insurance_cost = float(ship.get("insuranceCost", 0) or 0)
            total_shipment_cost = cost + insurance_cost

            total_cost += total_shipment_cost

            # By carrier
            carrier = ship.get("carrierCode", "unknown")
            if carrier not in by_carrier:
                by_carrier[carrier] = {"count": 0, "total_cost": 0}
            by_carrier[carrier]["count"] += 1
            by_carrier[carrier]["total_cost"] += total_shipment_cost

            # By service
            service = ship.get("serviceCode", "unknown")
            if service not in by_service:
                by_service[service] = {"count": 0, "total_cost": 0}
            by_service[service]["count"] += 1
            by_service[service]["total_cost"] += total_shipment_cost

            # Daily tracking
            ship_date = ship.get("shipDate", "")[:10]
            if ship_date:
                if ship_date not in daily_costs:
                    daily_costs[ship_date] = {"count": 0, "total_cost": 0}
                daily_costs[ship_date]["count"] += 1
                daily_costs[ship_date]["total_cost"] += total_shipment_cost

        # Calculate averages
        avg_cost = total_cost / shipment_count if shipment_count > 0 else 0

        for carrier in by_carrier.values():
            carrier["avg_cost"] = carrier["total_cost"] / carrier["count"] if carrier["count"] > 0 else 0

        for service in by_service.values():
            service["avg_cost"] = service["total_cost"] / service["count"] if service["count"] > 0 else 0

        return {
            "total_shipping_cost": total_cost,
            "shipment_count": shipment_count,
            "average_cost_per_shipment": avg_cost,
            "by_carrier": by_carrier,
            "by_service": by_service,
            "daily_costs": daily_costs,
        }

    def save_data(self, data: list | dict, filename: str):
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath

    def pull_last_30_days(self) -> dict:
        """Pull and analyze last 30 days of shipments."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        shipments = self.get_all_shipments(
            ship_date_start=start_date.strftime("%Y-%m-%d"),
            ship_date_end=end_date.strftime("%Y-%m-%d"),
        )

        self.save_data(shipments, "shipments_last_30d.json")

        metrics = self.calculate_shipping_costs(shipments)
        self.save_data(metrics, "shipping_costs_last_30d.json")

        print("\n" + "=" * 50)
        print("SHIPSTATION METRICS - LAST 30 DAYS")
        print("=" * 50)
        print(f"Total Shipping Cost:    ${metrics['total_shipping_cost']:,.2f}")
        print(f"Total Shipments:        {metrics['shipment_count']:,}")
        print(f"Avg Cost per Shipment:  ${metrics['average_cost_per_shipment']:.2f}")
        print("\nBy Carrier:")
        for carrier, data in metrics["by_carrier"].items():
            print(f"  {carrier}: {data['count']} shipments, ${data['total_cost']:.2f} total, ${data['avg_cost']:.2f} avg")
        print("=" * 50)

        return metrics

    def get_average_shipping_cost(self) -> float:
        """Get the average shipping cost per order (for CMAM calculation)."""
        costs_file = self.data_dir / "shipping_costs_last_30d.json"

        if costs_file.exists():
            with open(costs_file) as f:
                data = json.load(f)
            return data.get("average_cost_per_shipment", 6.50)

        # Fallback estimate
        return 6.50


def main():
    """Test the connector."""
    connector = ShipStationConnector()

    try:
        print("Testing ShipStation connection...")
        metrics = connector.pull_last_30_days()

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nTo use ShipStation integration:")
        print("1. Go to ShipStation > Settings > API")
        print("2. Generate an API Key and Secret")
        print("3. Add to .env:")
        print("   SHIPSTATION_API_KEY=your_key")
        print("   SHIPSTATION_API_SECRET=your_secret")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
