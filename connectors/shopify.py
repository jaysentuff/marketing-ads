"""
Shopify Connector for TuffWraps Marketing Attribution

Pulls orders, customers, and product data for CAM calculation.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import json
import time

from dotenv import load_dotenv
import requests

load_dotenv()


class ShopifyConnector:
    """Connector for Shopify Admin API."""

    API_VERSION = "2024-01"

    def __init__(self):
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.store_url = os.getenv("SHOPIFY_STORE_URL", "tuffwraps-com.myshopify.com")

        self.base_url = f"https://{self.store_url}/admin/api/{self.API_VERSION}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

        self.data_dir = Path(__file__).parent / "data" / "shopify"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _check_credentials(self):
        """Verify credentials are present."""
        if not self.access_token:
            raise ValueError("Missing SHOPIFY_ACCESS_TOKEN in .env file")
        return True

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated request to Shopify API."""
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 429:  # Rate limited
            retry_after = int(response.headers.get("Retry-After", 2))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            return self._make_request(endpoint, params)

        if response.status_code != 200:
            raise Exception(f"Shopify API Error ({response.status_code}): {response.text}")

        return response.json()

    def get_shop_info(self) -> dict:
        """Get shop information."""
        self._check_credentials()
        data = self._make_request("shop.json")
        return data.get("shop", {})

    def get_orders_count(self, status: str = "any", **filters) -> int:
        """Get count of orders matching filters."""
        params = {"status": status, **filters}
        data = self._make_request("orders/count.json", params)
        return data.get("count", 0)

    def get_orders(self, limit: int = 250, since_id: int = None,
                   created_at_min: str = None, created_at_max: str = None,
                   status: str = "any", financial_status: str = None) -> list[dict]:
        """
        Get orders with pagination support.

        Args:
            limit: Max orders per request (max 250)
            since_id: Get orders after this ID
            created_at_min: ISO 8601 datetime
            created_at_max: ISO 8601 datetime
            status: any, open, closed, cancelled
            financial_status: paid, pending, refunded, etc.
        """
        params = {"limit": min(limit, 250), "status": status}

        if since_id:
            params["since_id"] = since_id
        if created_at_min:
            params["created_at_min"] = created_at_min
        if created_at_max:
            params["created_at_max"] = created_at_max
        if financial_status:
            params["financial_status"] = financial_status

        data = self._make_request("orders.json", params)
        return data.get("orders", [])

    def get_all_orders(self, created_at_min: str = None, created_at_max: str = None,
                       financial_status: str = "paid", max_orders: int = None) -> list[dict]:
        """
        Get all orders with automatic pagination.

        Args:
            created_at_min: Start date (ISO 8601)
            created_at_max: End date (ISO 8601)
            financial_status: Filter by payment status
            max_orders: Maximum orders to fetch (None = all)
        """
        self._check_credentials()

        all_orders = []
        since_id = None
        page = 0

        print(f"Fetching orders...")
        if created_at_min:
            print(f"  From: {created_at_min}")
        if created_at_max:
            print(f"  To: {created_at_max}")

        while True:
            page += 1
            orders = self.get_orders(
                limit=250,
                since_id=since_id,
                created_at_min=created_at_min,
                created_at_max=created_at_max,
                financial_status=financial_status,
            )

            if not orders:
                break

            all_orders.extend(orders)
            since_id = orders[-1]["id"]

            print(f"  Page {page}: {len(orders)} orders (total: {len(all_orders)})")

            if max_orders and len(all_orders) >= max_orders:
                all_orders = all_orders[:max_orders]
                break

            if len(orders) < 250:
                break

            time.sleep(0.5)  # Be nice to the API

        print(f"  Done! Total orders: {len(all_orders)}")
        return all_orders

    def get_customers_count(self) -> int:
        """Get total customer count."""
        data = self._make_request("customers/count.json")
        return data.get("count", 0)

    def get_products(self, limit: int = 250) -> list[dict]:
        """Get products."""
        params = {"limit": min(limit, 250)}
        data = self._make_request("products.json", params)
        return data.get("products", [])

    def get_all_products(self) -> list[dict]:
        """Get all products with pagination."""
        self._check_credentials()
        all_products = []
        since_id = None

        while True:
            params = {"limit": 250}
            if since_id:
                params["since_id"] = since_id

            data = self._make_request("products.json", params)
            products = data.get("products", [])

            if not products:
                break

            all_products.extend(products)
            since_id = products[-1]["id"]

            if len(products) < 250:
                break

            time.sleep(0.5)

        return all_products

    def get_inventory_items(self, inventory_item_ids: list[int]) -> list[dict]:
        """Get inventory items with cost data."""
        all_items = []
        # API allows up to 100 IDs per request
        for i in range(0, len(inventory_item_ids), 100):
            batch_ids = inventory_item_ids[i:i + 100]
            ids_str = ",".join(str(id) for id in batch_ids)
            data = self._make_request("inventory_items.json", {"ids": ids_str})
            all_items.extend(data.get("inventory_items", []))
            if i + 100 < len(inventory_item_ids):
                time.sleep(0.5)
        return all_items

    def get_product_costs(self) -> dict:
        """
        Get cost (COGS) for all products.
        Returns dict mapping variant_id -> cost and sku -> cost.
        """
        self._check_credentials()
        print("Fetching product costs from Shopify...")

        # Get all products with variants
        products = self.get_all_products()
        print(f"  Found {len(products)} products")

        # Collect inventory item IDs from variants
        inventory_item_ids = []
        variant_to_inventory = {}  # variant_id -> inventory_item_id
        variant_info = {}  # variant_id -> {sku, product_title, variant_title}

        for product in products:
            for variant in product.get("variants", []):
                inv_id = variant.get("inventory_item_id")
                var_id = variant.get("id")
                if inv_id and var_id:
                    inventory_item_ids.append(inv_id)
                    variant_to_inventory[var_id] = inv_id
                    variant_info[var_id] = {
                        "sku": variant.get("sku", ""),
                        "product_title": product.get("title", ""),
                        "variant_title": variant.get("title", ""),
                        "price": float(variant.get("price", 0) or 0),
                    }

        print(f"  Found {len(inventory_item_ids)} inventory items")

        # Fetch inventory items with cost
        inventory_items = self.get_inventory_items(inventory_item_ids)

        # Build cost lookup by inventory_item_id
        inv_id_to_cost = {}
        for item in inventory_items:
            inv_id = item.get("id")
            cost = item.get("cost")
            if inv_id and cost is not None:
                try:
                    inv_id_to_cost[inv_id] = float(cost)
                except (ValueError, TypeError):
                    pass

        # Build final mappings
        costs = {
            "by_variant_id": {},
            "by_sku": {},
            "by_product_title": {},
            "average_cogs_percent": 0,
        }

        total_cost = 0
        total_price = 0
        cost_count = 0

        for product in products:
            product_title = product.get("title", "")
            product_costs = []
            product_prices = []

            for variant in product.get("variants", []):
                var_id = variant.get("id")
                sku = variant.get("sku", "")
                price = float(variant.get("price", 0) or 0)
                inv_id = variant_to_inventory.get(var_id)

                if inv_id and inv_id in inv_id_to_cost:
                    cost = inv_id_to_cost[inv_id]
                    costs["by_variant_id"][str(var_id)] = cost
                    if sku:
                        costs["by_sku"][sku] = cost
                    product_costs.append(cost)
                    product_prices.append(price)

                    total_cost += cost
                    total_price += price
                    cost_count += 1

            # Average cost for product (if multiple variants)
            if product_costs:
                avg_cost = sum(product_costs) / len(product_costs)
                costs["by_product_title"][product_title] = avg_cost

        # Calculate average COGS percentage
        if total_price > 0:
            costs["average_cogs_percent"] = (total_cost / total_price) * 100

        print(f"  Mapped costs for {len(costs['by_variant_id'])} variants")
        print(f"  Average COGS: {costs['average_cogs_percent']:.1f}% of price")

        self.save_data(costs, "product_costs.json")
        return costs

    def calculate_order_cogs(self, orders: list[dict], product_costs: dict = None) -> dict:
        """
        Calculate actual COGS for orders using product cost data.
        Returns total COGS and per-order breakdown.
        """
        if not product_costs:
            # Try to load from file
            costs_file = self.data_dir / "product_costs.json"
            if costs_file.exists():
                with open(costs_file) as f:
                    product_costs = json.load(f)
            else:
                print("Warning: No product costs data. Run get_product_costs() first.")
                return {"total_cogs": 0, "orders_with_cogs": 0}

        by_variant = product_costs.get("by_variant_id", {})
        by_sku = product_costs.get("by_sku", {})
        fallback_percent = product_costs.get("average_cogs_percent", 35) / 100

        total_cogs = 0
        orders_with_cogs = 0
        orders_estimated = 0

        for order in orders:
            order_cogs = 0
            has_actual_cost = False

            for item in order.get("line_items", []):
                quantity = int(item.get("quantity", 1))
                variant_id = str(item.get("variant_id", ""))
                sku = item.get("sku", "")
                line_price = float(item.get("price", 0) or 0)

                # Try to find actual cost
                cost = None
                if variant_id and variant_id in by_variant:
                    cost = by_variant[variant_id]
                    has_actual_cost = True
                elif sku and sku in by_sku:
                    cost = by_sku[sku]
                    has_actual_cost = True

                if cost is not None:
                    order_cogs += cost * quantity
                else:
                    # Fallback to average COGS %
                    order_cogs += line_price * quantity * fallback_percent

            total_cogs += order_cogs

            if has_actual_cost:
                orders_with_cogs += 1
            else:
                orders_estimated += 1

        return {
            "total_cogs": total_cogs,
            "orders_with_actual_cogs": orders_with_cogs,
            "orders_with_estimated_cogs": orders_estimated,
            "cogs_per_order": total_cogs / len(orders) if orders else 0,
        }

    def calculate_order_metrics(self, orders: list[dict], date_range_start: datetime = None) -> dict:
        """Calculate metrics from orders.

        Args:
            orders: List of order dicts from Shopify API
            date_range_start: Start of date range for determining new vs returning customers.
                             Customers created before this date are considered returning.
        """
        total_revenue = 0
        total_orders = len(orders)
        total_discounts = 0
        total_shipping = 0
        total_tax = 0
        new_customers = 0
        returning_customers = 0

        daily_stats = {}

        # Track unique customers to avoid double-counting
        seen_customers = {}  # customer_id -> {created_at, order_count_in_period}

        for order in orders:
            revenue = float(order.get("total_price", 0) or 0)
            discounts = float(order.get("total_discounts", 0) or 0)
            tax = float(order.get("total_tax", 0) or 0)

            shipping = sum(
                float(line.get("price", 0) or 0)
                for line in order.get("shipping_lines", [])
            )

            total_revenue += revenue
            total_discounts += discounts
            total_shipping += shipping
            total_tax += tax

            # Daily tracking
            date = order.get("created_at", "")[:10]
            if date:
                if date not in daily_stats:
                    daily_stats[date] = {"orders": 0, "revenue": 0}
                daily_stats[date]["orders"] += 1
                daily_stats[date]["revenue"] += revenue

            # Customer tracking - use customer ID and created_at to determine new vs returning
            customer = order.get("customer")
            if customer:
                customer_id = customer.get("id")
                if customer_id and customer_id not in seen_customers:
                    customer_created = customer.get("created_at", "")
                    seen_customers[customer_id] = customer_created

        # Now classify customers as new vs returning based on when they were created
        # If customer account was created within the date range, they're new
        # If created before the date range, they're returning
        for customer_id, customer_created in seen_customers.items():
            if customer_created and date_range_start:
                try:
                    # Parse customer created_at (format: "2026-01-17T02:18:02-05:00")
                    created_dt = datetime.fromisoformat(customer_created.replace('Z', '+00:00'))
                    # Make date_range_start timezone-aware if needed for comparison
                    if created_dt.tzinfo and date_range_start.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=None)

                    if created_dt >= date_range_start:
                        new_customers += 1
                    else:
                        returning_customers += 1
                except (ValueError, TypeError):
                    # If we can't parse the date, count as new
                    new_customers += 1
            else:
                # No date info, count as new
                new_customers += 1

        return {
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "total_discounts": total_discounts,
            "total_shipping": total_shipping,
            "total_tax": total_tax,
            "aov": total_revenue / total_orders if total_orders > 0 else 0,
            "new_customers": new_customers,
            "returning_customers": returning_customers,
            "unique_customers": len(seen_customers),
            "daily_stats": daily_stats,
        }

    def save_data(self, data: list | dict, filename: str):
        """Save data to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved to {filepath}")
        return filepath

    def pull_last_30_days(self) -> dict:
        """Pull and analyze last 30 days of orders."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        orders = self.get_all_orders(
            created_at_min=start_date.isoformat(),
            created_at_max=end_date.isoformat(),
            financial_status="paid",
        )

        self.save_data(orders, "orders_last_30d.json")

        metrics = self.calculate_order_metrics(orders, date_range_start=start_date)
        self.save_data(metrics, "metrics_last_30d.json")

        print("\n" + "=" * 50)
        print("SHOPIFY METRICS - LAST 30 DAYS")
        print("=" * 50)
        print(f"Total Revenue:    ${metrics['total_revenue']:,.2f}")
        print(f"Total Orders:     {metrics['total_orders']:,}")
        print(f"AOV:              ${metrics['aov']:.2f}")
        print(f"Unique Customers: {metrics['unique_customers']:,}")
        print(f"  New:            {metrics['new_customers']:,}")
        print(f"  Returning:      {metrics['returning_customers']:,}")
        print("=" * 50)

        return metrics


def main():
    """Test the connector."""
    connector = ShopifyConnector()

    try:
        # Test connection
        shop = connector.get_shop_info()
        print(f"Connected to: {shop.get('name')}")
        print(f"Domain: {shop.get('domain')}")

        # Get order count
        count = connector.get_orders_count()
        print(f"Total orders: {count:,}")

        # Pull last 30 days
        print("\nPulling last 30 days...")
        metrics = connector.pull_last_30_days()

    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
