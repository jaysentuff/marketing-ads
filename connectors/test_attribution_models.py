"""Test different Kendall attribution models."""

from kendall import KendallConnector
from datetime import datetime, timedelta
import json

k = KendallConnector()

end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

print(f"Testing attribution models for {start_date} to {end_date}")
print("=" * 60)

for model in ['kendall', 'first_click', 'last_click', 'last_click_per_channel']:
    try:
        result = k.call_tool('get_all_sources_attribution', {
            'date_start': start_date,
            'date_end': end_date,
            'attribution_model': model,
            'include_breakdowns': False
        })
        content = k._extract_content(result)

        meta_total = content.get('Meta Ads', {}).get('total', {})
        google_total = content.get('Google Ads', {}).get('total', {})

        print(f"\n{model}:")
        print(f"  Meta:   {meta_total.get('orders', 0):>4} orders, ${meta_total.get('sales', 0):>10,.0f} revenue")
        print(f"  Google: {google_total.get('orders', 0):>4} orders, ${google_total.get('sales', 0):>10,.0f} revenue")
    except Exception as e:
        print(f"{model}: Error - {e}")

print("\n" + "=" * 60)
print("Note: First-click attribution will show higher Meta revenue")
print("if TOF ads are introducing new customers who later convert")
print("via Google branded search (last-click).")
