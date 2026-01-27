"""
Data Aggregator for TuffWraps Marketing Attribution

Combines data from all sources to calculate CAM (Contribution After Marketing).

CAM = Revenue - COGS - Shipping Cost - Ad Spend

This module:
1. Pulls data from all connectors
2. Uses Kendall attribution for de-duplicated channel revenue
3. Calculates blended and per-channel CAM
4. Generates the decision framework outputs
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import json
from dataclasses import dataclass, asdict, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class ChannelMetrics:
    """Metrics for a single marketing channel."""
    name: str
    orders: int = 0
    revenue: float = 0
    new_customer_orders: int = 0
    new_customer_revenue: float = 0
    returning_customer_orders: int = 0
    returning_customer_revenue: float = 0
    ad_spend: float = 0
    roas: float = 0
    nc_roas: float = 0  # New customer ROAS
    cam: float = 0
    cam_per_order: float = 0


@dataclass
class DailyMetrics:
    """Daily metrics for CAM calculation."""
    date: str

    # Revenue (from Shopify)
    total_revenue: float = 0
    total_orders: int = 0
    new_customers: int = 0
    returning_customers: int = 0
    shipping_collected: float = 0
    discounts: float = 0

    # Costs
    cogs: float = 0  # Cost of goods sold
    shipping_cost: float = 0  # Actual shipping cost (not collected)

    # Ad Spend (from platforms)
    google_ads_spend: float = 0
    meta_ads_spend: float = 0
    total_ad_spend: float = 0

    # Kendall Attributed Revenue (de-duplicated)
    google_attributed_revenue: float = 0
    google_attributed_orders: int = 0
    meta_attributed_revenue: float = 0
    meta_attributed_orders: int = 0
    organic_attributed_revenue: float = 0
    organic_attributed_orders: int = 0
    klaviyo_attributed_revenue: float = 0
    klaviyo_attributed_orders: int = 0

    # Platform-reported metrics (for comparison)
    google_platform_conversions: float = 0
    google_platform_revenue: float = 0
    meta_platform_conversions: float = 0
    meta_platform_revenue: float = 0

    # Calculated CAM
    blended_cam: float = 0
    google_cam: float = 0
    meta_cam: float = 0
    cam_per_order: float = 0


@dataclass
class AttributionSummary:
    """Summary of attribution data from Kendall."""
    period_start: str
    period_end: str
    total_orders: int = 0
    total_revenue: float = 0
    channels: dict = field(default_factory=dict)


class DataAggregator:
    """Aggregates data from all sources for CAM calculation."""

    # Default COGS percentage if not available per-product
    DEFAULT_COGS_PERCENT = 0.35  # 35% of revenue

    # Default shipping cost per order if not tracked
    DEFAULT_SHIPPING_COST_PER_ORDER = 6.50

    def __init__(self):
        self.data_dir = Path(__file__).parent / "data"
        self.output_dir = self.data_dir / "aggregated"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Store for pulled data
        self.shopify_data = []
        self.google_ads_data = []
        self.meta_ads_data = []
        self.kendall_attribution = {}
        self.gsc_data = {}
        self.amazon_data = {}

        # Real cost data (loaded from Shopify and ShipStation)
        self.product_costs = {}
        self.shipping_costs = {}
        self.actual_cogs = None  # Will be calculated from orders if available
        self.actual_shipping = None  # Will be loaded from ShipStation

        # Configuration (fallbacks if real data not available)
        self.cogs_percent = float(os.getenv("COGS_PERCENT", self.DEFAULT_COGS_PERCENT))
        self.shipping_cost_per_order = float(os.getenv("SHIPPING_COST_PER_ORDER", self.DEFAULT_SHIPPING_COST_PER_ORDER))

        # Flags to track data source
        self.using_actual_cogs = False
        self.using_actual_shipping = False

    def load_shopify_data(self, filepath: str = None):
        """Load Shopify order data from file or pull fresh."""
        default_path = self.data_dir / "shopify" / "orders_last_30d.json"

        if filepath:
            path = Path(filepath)
        elif default_path.exists():
            path = default_path
        else:
            path = None

        if path and path.exists():
            with open(path) as f:
                self.shopify_data = json.load(f)
            print(f"Loaded {len(self.shopify_data)} Shopify orders from {path}")
        else:
            print("No Shopify data file found.")
            self.shopify_data = []

    def load_google_ads_data(self, filepath: str = None):
        """Load Google Ads data from file or pull fresh."""
        default_path = self.data_dir / "google_ads" / "campaigns_last_30d.json"

        if filepath:
            path = Path(filepath)
        elif default_path.exists():
            path = default_path
        else:
            path = None

        if path and path.exists():
            with open(path) as f:
                self.google_ads_data = json.load(f)
            print(f"Loaded {len(self.google_ads_data)} Google Ads records from {path}")
        else:
            print("No Google Ads data found. Run google_ads.py to pull data.")
            self.google_ads_data = []

    def load_meta_ads_data(self, filepath: str = None):
        """Load Meta Ads data from file or pull fresh."""
        default_path = self.data_dir / "meta_ads" / "campaigns_last_30d.json"

        if filepath:
            path = Path(filepath)
        elif default_path.exists():
            path = default_path
        else:
            path = None

        if path and path.exists():
            with open(path) as f:
                self.meta_ads_data = json.load(f)
            print(f"Loaded {len(self.meta_ads_data)} Meta Ads records from {path}")
        else:
            print("No Meta Ads data found. Run meta_ads.py to pull data.")
            self.meta_ads_data = []

    def load_kendall_attribution(self, filepath: str = None):
        """Load Kendall attribution data."""
        default_path = self.data_dir / "kendall" / "attribution_by_source.json"

        if filepath:
            path = Path(filepath)
        elif default_path.exists():
            path = default_path
        else:
            path = None

        if path and path.exists():
            with open(path) as f:
                self.kendall_attribution = json.load(f)
            print(f"Loaded Kendall attribution data from {path}")
        else:
            print("No Kendall data found. Run kendall.py to pull data.")
            self.kendall_attribution = {}

    def load_gsc_data(self, filepath: str = None):
        """Load Google Search Console data."""
        default_path = self.data_dir / "gsc" / "branded_vs_nonbranded.json"

        if filepath:
            path = Path(filepath)
        elif default_path.exists():
            path = default_path
        else:
            path = None

        if path and path.exists():
            with open(path) as f:
                self.gsc_data = json.load(f)
            print(f"Loaded GSC data from {path}")
        else:
            print("No GSC data found.")
            self.gsc_data = {}

    def load_product_costs(self, filepath: str = None):
        """Load product costs (COGS) from Shopify data."""
        default_path = self.data_dir / "shopify" / "product_costs.json"

        if filepath:
            path = Path(filepath)
        elif default_path.exists():
            path = default_path
        else:
            path = None

        if path and path.exists():
            with open(path) as f:
                self.product_costs = json.load(f)

            # Update COGS percent from actual data
            actual_percent = self.product_costs.get("average_cogs_percent", 0)
            if actual_percent > 0:
                self.cogs_percent = actual_percent / 100
                self.using_actual_cogs = True
                print(f"Loaded actual COGS from Shopify: {actual_percent:.1f}%")
            else:
                print(f"Product costs loaded but no average calculated. Using default {self.DEFAULT_COGS_PERCENT*100:.0f}%")
        else:
            print(f"No product costs file. Using estimated COGS: {self.cogs_percent*100:.0f}%")
            print("  Run: python connectors/shopify.py to pull actual costs")

    def load_shipping_costs(self, filepath: str = None):
        """Load shipping costs from ShipStation data."""
        default_path = self.data_dir / "shipstation" / "shipping_costs_last_30d.json"

        if filepath:
            path = Path(filepath)
        elif default_path.exists():
            path = default_path
        else:
            path = None

        if path and path.exists():
            with open(path) as f:
                self.shipping_costs = json.load(f)

            # Update shipping cost per order from actual data
            actual_cost = self.shipping_costs.get("average_cost_per_shipment", 0)
            if actual_cost > 0:
                self.shipping_cost_per_order = actual_cost
                self.using_actual_shipping = True
                self.actual_shipping = self.shipping_costs.get("total_shipping_cost", 0)
                print(f"Loaded actual shipping costs from ShipStation: ${actual_cost:.2f}/order")
            else:
                print(f"Shipping costs loaded but no average calculated. Using default ${self.DEFAULT_SHIPPING_COST_PER_ORDER:.2f}")
        else:
            print(f"No ShipStation data. Using estimated shipping: ${self.shipping_cost_per_order:.2f}/order")
            print("  Run: python connectors/shipstation.py to pull actual costs")

    def calculate_actual_cogs_from_orders(self) -> float:
        """Calculate actual COGS from order line items using product costs."""
        if not self.shopify_data or not self.product_costs:
            return 0

        by_variant = self.product_costs.get("by_variant_id", {})
        by_sku = self.product_costs.get("by_sku", {})
        fallback_percent = self.product_costs.get("average_cogs_percent", 35) / 100

        total_cogs = 0
        items_with_cost = 0
        items_estimated = 0

        for order in self.shopify_data:
            for item in order.get("line_items", []):
                quantity = int(item.get("quantity", 1))
                variant_id = str(item.get("variant_id", ""))
                sku = item.get("sku", "")
                line_price = float(item.get("price", 0) or 0)

                cost = None
                if variant_id and variant_id in by_variant:
                    cost = by_variant[variant_id]
                    items_with_cost += 1
                elif sku and sku in by_sku:
                    cost = by_sku[sku]
                    items_with_cost += 1
                else:
                    # Fallback to percentage
                    cost = line_price * fallback_percent
                    items_estimated += 1

                total_cogs += cost * quantity

        if items_with_cost > 0:
            self.using_actual_cogs = True
            print(f"  Calculated COGS from {items_with_cost} items with actual costs, {items_estimated} estimated")

        return total_cogs

    def parse_kendall_attribution(self) -> AttributionSummary:
        """Parse Kendall attribution data into structured format."""
        summary = AttributionSummary(
            period_start="",
            period_end="",
        )

        # Skip metadata fields
        skip_keys = ["_fields", "filters_applied", "null"]

        for source, data in self.kendall_attribution.items():
            if source in skip_keys:
                continue

            if not isinstance(data, dict) or "total" not in data:
                continue

            total = data["total"]

            channel = ChannelMetrics(
                name=source,
                orders=total.get("orders", 0),
                revenue=total.get("sales", 0),
                new_customer_orders=total.get("nc_orders", 0),
                new_customer_revenue=total.get("nc_sales", 0),
                returning_customer_orders=total.get("rc_orders", 0),
                returning_customer_revenue=total.get("rc_sales", 0),
                roas=total.get("roas", 0),
                nc_roas=total.get("nc_roas", 0),
            )

            summary.channels[source] = channel
            summary.total_orders += channel.orders
            summary.total_revenue += channel.revenue

        return summary

    def get_total_ad_spend(self) -> dict:
        """Calculate total ad spend from platform data."""
        google_spend = sum(row.get("spend", 0) for row in self.google_ads_data)
        meta_spend = sum(row.get("spend", 0) for row in self.meta_ads_data)

        return {
            "google": google_spend,
            "meta": meta_spend,
            "total": google_spend + meta_spend,
        }

    def calculate_channel_cam(self, channel: ChannelMetrics, ad_spend: float) -> ChannelMetrics:
        """Calculate CAM for a channel using Kendall attributed revenue."""
        # CAM = Revenue - COGS - Shipping - Ad Spend
        cogs = channel.revenue * self.cogs_percent
        shipping = channel.orders * self.shipping_cost_per_order

        channel.ad_spend = ad_spend
        channel.cam = channel.revenue - cogs - shipping - ad_spend

        if channel.orders > 0:
            channel.cam_per_order = channel.cam / channel.orders

        return channel

    def generate_cam_report(self) -> dict:
        """Generate comprehensive CAM report using Kendall attribution."""
        # Parse Kendall data
        attribution = self.parse_kendall_attribution()

        # Get ad spend
        spend = self.get_total_ad_spend()

        # Calculate CAM for paid channels
        google_channel = attribution.channels.get("Google Ads", ChannelMetrics(name="Google Ads"))
        meta_channel = attribution.channels.get("Meta Ads", ChannelMetrics(name="Meta Ads"))
        organic_channel = attribution.channels.get("Organic", ChannelMetrics(name="Organic"))
        klaviyo_channel = attribution.channels.get("Klaviyo", ChannelMetrics(name="Klaviyo"))

        # Apply ad spend and calculate CAM
        google_channel = self.calculate_channel_cam(google_channel, spend["google"])
        meta_channel = self.calculate_channel_cam(meta_channel, spend["meta"])
        organic_channel = self.calculate_channel_cam(organic_channel, 0)  # No ad spend
        klaviyo_channel = self.calculate_channel_cam(klaviyo_channel, 0)  # No ad spend (email cost separate)

        # Calculate blended metrics
        total_revenue = attribution.total_revenue
        total_orders = attribution.total_orders

        # Use actual COGS from order line items if available
        if self.shopify_data and self.product_costs:
            total_cogs = self.calculate_actual_cogs_from_orders()
            cogs_source = "actual"
        else:
            total_cogs = total_revenue * self.cogs_percent
            cogs_source = "estimated"

        # Use actual shipping from ShipStation if available
        if self.using_actual_shipping and self.actual_shipping:
            total_shipping = self.actual_shipping
            shipping_source = "actual"
        else:
            total_shipping = total_orders * self.shipping_cost_per_order
            shipping_source = "estimated"

        total_ad_spend = spend["total"]

        blended_cam = total_revenue - total_cogs - total_shipping - total_ad_spend
        blended_cam_per_order = blended_cam / total_orders if total_orders > 0 else 0

        # Platform over-attribution analysis
        google_platform_revenue = sum(row.get("conversion_value", 0) for row in self.google_ads_data)
        meta_platform_revenue = sum(row.get("purchase_value", 0) for row in self.meta_ads_data)
        platform_total = google_platform_revenue + meta_platform_revenue
        kendall_paid_total = google_channel.revenue + meta_channel.revenue

        over_attribution = platform_total - kendall_paid_total if platform_total > 0 else 0
        over_attribution_pct = (over_attribution / platform_total * 100) if platform_total > 0 else 0

        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_revenue": total_revenue,
                "total_orders": total_orders,
                "total_cogs": total_cogs,
                "cogs_source": cogs_source,
                "cogs_percent": self.cogs_percent * 100,
                "total_shipping": total_shipping,
                "shipping_source": shipping_source,
                "shipping_per_order": self.shipping_cost_per_order,
                "total_ad_spend": total_ad_spend,
                "blended_cam": blended_cam,
                "blended_cam_per_order": blended_cam_per_order,
            },
            "channels": {
                "google_ads": asdict(google_channel),
                "meta_ads": asdict(meta_channel),
                "organic": asdict(organic_channel),
                "klaviyo": asdict(klaviyo_channel),
            },
            "platform_vs_kendall": {
                "google_platform_revenue": google_platform_revenue,
                "google_kendall_revenue": google_channel.revenue,
                "meta_platform_revenue": meta_platform_revenue,
                "meta_kendall_revenue": meta_channel.revenue,
                "platform_total": platform_total,
                "kendall_total": kendall_paid_total,
                "over_attribution": over_attribution,
                "over_attribution_pct": over_attribution_pct,
            },
            "branded_search": {
                "clicks": self.gsc_data.get("branded", {}).get("clicks", 0),
                "impressions": self.gsc_data.get("branded", {}).get("impressions", 0),
                "branded_pct": self.gsc_data.get("branded_percentage", 0),
            },
        }

        return report

    def generate_recommendations(self, report: dict) -> list[str]:
        """Generate actionable recommendations based on the decision framework."""
        recommendations = []

        summary = report.get("summary", {})
        channels = report.get("channels", {})
        platform_comparison = report.get("platform_vs_kendall", {})

        # Decision 1: Overall CAM health
        cam_per_order = summary.get("blended_cam_per_order", 0)
        if cam_per_order > 15:
            recommendations.append(
                f"HEALTHY: CAM per order is ${cam_per_order:.2f}. Consider scaling spend 10-15%."
            )
        elif cam_per_order > 5:
            recommendations.append(
                f"MODERATE: CAM per order is ${cam_per_order:.2f}. Hold spend, test new creative."
            )
        elif cam_per_order > 0:
            recommendations.append(
                f"LOW: CAM per order is ${cam_per_order:.2f}. Review underperforming campaigns."
            )
        else:
            recommendations.append(
                f"NEGATIVE: CAM per order is ${cam_per_order:.2f}. URGENT: Cut spend on worst performers."
            )

        # Decision 2: Channel comparison
        google = channels.get("google_ads", {})
        meta = channels.get("meta_ads", {})

        google_cam = google.get("cam", 0)
        meta_cam = meta.get("cam", 0)

        if google_cam > 0 and meta_cam > 0:
            if google_cam > meta_cam * 1.2:
                recommendations.append(
                    f"BUDGET SHIFT: Google CAM (${google_cam:,.0f}) outperforming Meta (${meta_cam:,.0f}). "
                    f"Consider shifting 10-20% budget from Meta to Google."
                )
            elif meta_cam > google_cam * 1.2:
                recommendations.append(
                    f"BUDGET SHIFT: Meta CAM (${meta_cam:,.0f}) outperforming Google (${google_cam:,.0f}). "
                    f"Consider shifting 10-20% budget from Google to Meta."
                )
            else:
                recommendations.append(
                    f"BALANCED: Channel CAM is similar (Google: ${google_cam:,.0f}, Meta: ${meta_cam:,.0f}). "
                    f"Maintain current allocation."
                )
        elif google_cam > 0 and meta_cam <= 0:
            recommendations.append(
                f"META ISSUE: Meta CAM is ${meta_cam:,.0f}. Review Meta campaigns or reduce spend."
            )
        elif meta_cam > 0 and google_cam <= 0:
            recommendations.append(
                f"GOOGLE ISSUE: Google CAM is ${google_cam:,.0f}. Review Google campaigns or reduce spend."
            )

        # Platform over-attribution warning
        over_attr_pct = platform_comparison.get("over_attribution_pct", 0)
        if over_attr_pct > 30:
            recommendations.append(
                f"ATTRIBUTION GAP: Platforms over-claiming revenue by {over_attr_pct:.0f}%. "
                f"Don't trust platform ROAS - use Kendall attribution for decisions."
            )

        # ROAS comparison
        google_roas = google.get("roas", 0)
        meta_roas = meta.get("roas", 0)
        google_nc_roas = google.get("nc_roas", 0)
        meta_nc_roas = meta.get("nc_roas", 0)

        if google_nc_roas > 0 or meta_nc_roas > 0:
            recommendations.append(
                f"NEW CUSTOMER ROAS - Google: {google_nc_roas:.2f}x, Meta: {meta_nc_roas:.2f}x "
                f"(New customers are harder to acquire - lower NC ROAS is normal)"
            )

        return recommendations

    def print_report(self, report: dict, recommendations: list[str]):
        """Print a formatted report."""
        print("\n" + "=" * 70)
        print("TUFFWRAPS CAM REPORT (KENDALL ATTRIBUTION)")
        print("=" * 70)

        summary = report.get("summary", {})
        cogs_source = summary.get("cogs_source", "estimated")
        cogs_pct = summary.get("cogs_percent", self.cogs_percent * 100)
        shipping_source = summary.get("shipping_source", "estimated")
        shipping_per = summary.get("shipping_per_order", self.shipping_cost_per_order)

        print(f"\n{'BLENDED METRICS':-^70}")
        print(f"  Total Revenue (Kendall):   ${summary.get('total_revenue', 0):>12,.2f}")
        print(f"  Total Orders:              {summary.get('total_orders', 0):>12,}")

        if cogs_source == "actual":
            print(f"  COGS (ACTUAL from Shopify):${summary.get('total_cogs', 0):>12,.2f}")
        else:
            print(f"  COGS (est {cogs_pct:.0f}%):           ${summary.get('total_cogs', 0):>12,.2f}")

        if shipping_source == "actual":
            print(f"  Shipping (ShipStation):    ${summary.get('total_shipping', 0):>12,.2f}")
        else:
            print(f"  Shipping (est ${shipping_per:.2f}/order): ${summary.get('total_shipping', 0):>12,.2f}")

        print(f"  Total Ad Spend:            ${summary.get('total_ad_spend', 0):>12,.2f}")
        print(f"  " + "-" * 45)
        print(f"  BLENDED CMAM:              ${summary.get('blended_cam', 0):>12,.2f}")
        print(f"  CMAM per Order:            ${summary.get('blended_cam_per_order', 0):>12,.2f}")

        print(f"\n{'CHANNEL BREAKDOWN (KENDALL ATTRIBUTION)':-^70}")
        channels = report.get("channels", {})

        for name, data in channels.items():
            if data.get("revenue", 0) > 0 or data.get("ad_spend", 0) > 0:
                print(f"\n  {name.upper().replace('_', ' ')}:")
                print(f"    Orders:           {data.get('orders', 0):>10,}")
                print(f"    Revenue:          ${data.get('revenue', 0):>10,.2f}")
                print(f"    Ad Spend:         ${data.get('ad_spend', 0):>10,.2f}")
                print(f"    ROAS (Kendall):   {data.get('roas', 0):>10.2f}x")
                print(f"    NC ROAS:          {data.get('nc_roas', 0):>10.2f}x")
                print(f"    Channel CAM:      ${data.get('cam', 0):>10,.2f}")
                print(f"    CAM per Order:    ${data.get('cam_per_order', 0):>10,.2f}")

        print(f"\n{'PLATFORM VS KENDALL ATTRIBUTION':-^70}")
        comparison = report.get("platform_vs_kendall", {})
        print(f"  Google - Platform: ${comparison.get('google_platform_revenue', 0):>10,.2f}  "
              f"Kendall: ${comparison.get('google_kendall_revenue', 0):>10,.2f}")
        print(f"  Meta -   Platform: ${comparison.get('meta_platform_revenue', 0):>10,.2f}  "
              f"Kendall: ${comparison.get('meta_kendall_revenue', 0):>10,.2f}")
        print(f"  " + "-" * 45)
        print(f"  Platform Over-Attribution: ${comparison.get('over_attribution', 0):>10,.2f} "
              f"({comparison.get('over_attribution_pct', 0):.1f}%)")

        branded = report.get("branded_search", {})
        if branded.get("clicks", 0) > 0:
            print(f"\n{'BRANDED SEARCH (GSC)':-^70}")
            print(f"  Branded Clicks:     {branded.get('clicks', 0):>10,}")
            print(f"  Branded Impressions:{branded.get('impressions', 0):>10,}")
            print(f"  Branded % of Total: {branded.get('branded_pct', 0):>10.1f}%")

        print(f"\n{'RECOMMENDATIONS':-^70}")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")

        print("\n" + "=" * 70)

    def save_report(self, report: dict, recommendations: list[str]):
        """Save report data to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save full report
        report_filepath = self.output_dir / f"cam_report_{timestamp}.json"
        with open(report_filepath, "w") as f:
            json.dump({
                "report": report,
                "recommendations": recommendations,
                "generated_at": datetime.now().isoformat(),
            }, f, indent=2)

        # Save latest (for dashboards)
        latest_filepath = self.output_dir / "latest_report.json"
        with open(latest_filepath, "w") as f:
            json.dump({
                "report": report,
                "recommendations": recommendations,
                "generated_at": datetime.now().isoformat(),
            }, f, indent=2)

        print(f"\nReports saved to:")
        print(f"  - {report_filepath}")
        print(f"  - {latest_filepath}")

    def run(self):
        """Run the full aggregation and reporting."""
        print("Loading data from all sources...")

        # Load data
        self.load_shopify_data()
        self.load_google_ads_data()
        self.load_meta_ads_data()
        self.load_kendall_attribution()
        self.load_gsc_data()

        # Load cost data (Shopify COGS and ShipStation shipping)
        self.load_product_costs()
        self.load_shipping_costs()

        if not self.kendall_attribution:
            print("\nERROR: No Kendall attribution data available.")
            print("Run kendall.py first to pull attribution data.")
            return None

        print("\nGenerating CAM report...")
        report = self.generate_cam_report()

        print("Generating recommendations...")
        recommendations = self.generate_recommendations(report)

        # Output
        self.print_report(report, recommendations)
        self.save_report(report, recommendations)

        return {
            "report": report,
            "recommendations": recommendations,
        }


def main():
    """Run the aggregator."""
    aggregator = DataAggregator()
    aggregator.run()


if __name__ == "__main__":
    main()
