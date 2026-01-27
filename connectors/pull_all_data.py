"""
Master Data Pull Script for TuffWraps Marketing Attribution

Pulls data from all connected sources:
- Shopify (orders, revenue)
- Google Ads (spend, conversions)
- Meta Ads (spend, conversions)
- Kendall.ai (de-duplicated attribution)
- Google Search Console (branded search trends)
- Amazon Seller Central (Amazon sales)
- Klaviyo (email performance)
- GA4 (traffic triangulation)

Run this daily to update all data.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add connectors directory to path
sys.path.insert(0, str(Path(__file__).parent))


def pull_shopify():
    """Pull Shopify data."""
    print("\n" + "=" * 60)
    print("SHOPIFY")
    print("=" * 60)
    try:
        from shopify import ShopifyConnector
        connector = ShopifyConnector()
        return connector.pull_last_30_days()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_shopify_costs():
    """Pull Shopify product costs (COGS)."""
    print("\n" + "=" * 60)
    print("SHOPIFY PRODUCT COSTS")
    print("=" * 60)
    try:
        from shopify import ShopifyConnector
        connector = ShopifyConnector()
        return connector.get_product_costs()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_shipstation():
    """Pull ShipStation shipping costs."""
    print("\n" + "=" * 60)
    print("SHIPSTATION")
    print("=" * 60)
    try:
        from shipstation import ShipStationConnector
        connector = ShipStationConnector()
        return connector.pull_last_30_days()
    except ValueError as e:
        print(f"Not configured: {e}")
        return {"error": "Not configured"}
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_google_ads():
    """Pull Google Ads data."""
    print("\n" + "=" * 60)
    print("GOOGLE ADS")
    print("=" * 60)
    try:
        from google_ads import GoogleAdsConnector
        connector = GoogleAdsConnector()
        return connector.pull_last_30_days()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_meta_ads():
    """Pull Meta Ads data."""
    print("\n" + "=" * 60)
    print("META ADS")
    print("=" * 60)
    try:
        from meta_ads import MetaAdsConnector
        connector = MetaAdsConnector()
        return connector.pull_last_30_days()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_kendall():
    """Pull Kendall attribution data."""
    print("\n" + "=" * 60)
    print("KENDALL.AI ATTRIBUTION")
    print("=" * 60)
    try:
        from kendall import KendallConnector
        connector = KendallConnector()
        return connector.pull_last_30_days()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_gsc():
    """Pull Google Search Console data."""
    print("\n" + "=" * 60)
    print("GOOGLE SEARCH CONSOLE")
    print("=" * 60)
    try:
        from google_search_console import GoogleSearchConsoleConnector
        connector = GoogleSearchConsoleConnector()
        return connector.pull_last_30_days()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_amazon():
    """Pull Amazon Seller Central data."""
    print("\n" + "=" * 60)
    print("AMAZON SELLER CENTRAL")
    print("=" * 60)
    try:
        from amazon_seller import AmazonSellerConnector
        connector = AmazonSellerConnector()
        if not connector.configured:
            print("Amazon not configured. Skipping.")
            return {"error": "Not configured"}
        return connector.pull_last_30_days()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_klaviyo():
    """Pull Klaviyo data."""
    print("\n" + "=" * 60)
    print("KLAVIYO")
    print("=" * 60)
    try:
        from klaviyo import KlaviyoConnector
        connector = KlaviyoConnector()
        if not connector.configured:
            print("Klaviyo not configured. Skipping.")
            return {"error": "Not configured"}
        return connector.pull_last_30_days()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def pull_ga4():
    """Pull GA4 data."""
    print("\n" + "=" * 60)
    print("GOOGLE ANALYTICS 4")
    print("=" * 60)
    try:
        from google_analytics import GA4Connector
        connector = GA4Connector()
        if not connector.configured:
            print("GA4 not configured. Skipping.")
            return {"error": "Not configured"}
        return connector.pull_last_30_days()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def main():
    """Pull data from all sources."""
    print("\n" + "=" * 70)
    print("TUFFWRAPS MARKETING ATTRIBUTION - DATA PULL")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    results = {}

    # Core data sources (required)
    print("\n>>> PULLING CORE DATA SOURCES <<<")

    # Shopify - primary revenue source
    results["shopify"] = pull_shopify()

    # Shopify product costs - actual COGS data
    results["shopify_costs"] = pull_shopify_costs()

    # Ad platforms - spend data
    results["google_ads"] = pull_google_ads()
    results["meta_ads"] = pull_meta_ads()

    # Kendall - de-duplicated attribution
    results["kendall"] = pull_kendall()

    # ShipStation - actual shipping label costs
    results["shipstation"] = pull_shipstation()

    # Secondary sources (optional)
    print("\n>>> PULLING SECONDARY DATA SOURCES <<<")

    # GSC - branded search trends for TOF analysis
    results["gsc"] = pull_gsc()

    # Amazon - for blended CAM across channels
    results["amazon"] = pull_amazon()

    # Klaviyo - email revenue (also in Kendall)
    results["klaviyo"] = pull_klaviyo()

    # GA4 - traffic triangulation
    results["ga4"] = pull_ga4()

    # Summary
    print("\n" + "=" * 70)
    print("DATA PULL COMPLETE")
    print("=" * 70)

    print("\nSource Status:")
    for source, result in results.items():
        if isinstance(result, dict) and result.get("error"):
            print(f"  {source}: ERROR - {result['error']}")
        elif result:
            print(f"  {source}: OK")
        else:
            print(f"  {source}: No data")

    print(f"\nCompleted: {datetime.now().isoformat()}")
    print("\nNext step: Run data_aggregator.py to calculate CAM")
    print("=" * 70)

    return results


if __name__ == "__main__":
    main()
