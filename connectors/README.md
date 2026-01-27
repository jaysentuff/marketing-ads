# TuffWraps Marketing Attribution - Custom Connectors

## Overview
Custom Python connectors to pull data from ad platforms and attribution tools for CAM calculation.

## API Setup Guide

### 1. Google Ads API

**What you need:**
- Google Ads Manager Account ID (MCC or individual account)
- Google Cloud Project with Google Ads API enabled
- OAuth2 credentials (Client ID + Client Secret)
- Developer Token (apply at https://ads.google.com/aw/apicenter)

**Steps:**
1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable "Google Ads API" in APIs & Services
4. Create OAuth2 credentials (Desktop app type)
5. Download the JSON credentials file
6. Apply for Developer Token at Google Ads API Center (takes ~1 day for basic access)

**Required Scopes:**
- `https://www.googleapis.com/auth/adwords`

---

### 2. Meta (Facebook) Ads API

**What you need:**
- Facebook Business Manager account
- Ad Account ID (format: act_XXXXXXXXX)
- System User Access Token (long-lived)

**Steps:**
1. Go to https://business.facebook.com/settings/
2. Navigate to Business Settings > Users > System Users
3. Create a System User (Admin role recommended)
4. Generate Access Token with these permissions:
   - `ads_read`
   - `ads_management`
   - `business_management`
5. Note your Ad Account ID from Ads Manager

**Important:** System User tokens don't expire (unlike regular user tokens)

---

### 3. Kendall.ai API

**What you need:**
- Kendall.ai account with API access
- API Key or OAuth credentials

**Steps:**
1. Log into Kendall.ai dashboard
2. Go to Settings > API / Integrations
3. Generate API key
4. Note the API endpoint URL

**Alternative - MCP Server:**
If Kendall provides an MCP server, add to Claude Code settings:
```json
{
  "mcpServers": {
    "kendall": {
      "command": "npx",
      "args": ["-y", "@kendall/mcp-server"],
      "env": {
        "KENDALL_API_KEY": "your-api-key"
      }
    }
  }
}
```

---

### 4. Shopify (Already Connected via Rube)

For COGS data, check if stored in:
- Product variant `cost` field (requires inventory permissions)
- Product metafields
- Separate spreadsheet/system

---

## Credentials Storage

Create `.env` file in this directory (DO NOT COMMIT):

```env
# Google Ads
GOOGLE_ADS_CLIENT_ID=your-client-id
GOOGLE_ADS_CLIENT_SECRET=your-client-secret
GOOGLE_ADS_DEVELOPER_TOKEN=your-dev-token
GOOGLE_ADS_CUSTOMER_ID=your-customer-id
GOOGLE_ADS_REFRESH_TOKEN=your-refresh-token

# Meta Ads
META_ACCESS_TOKEN=your-system-user-token
META_AD_ACCOUNT_ID=act_XXXXXXXXX

# Kendall
KENDALL_API_KEY=your-api-key
KENDALL_API_URL=https://api.kendall.ai/v1

# Shopify (if needed for direct access)
SHOPIFY_STORE_URL=tuffwraps-com.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-access-token
```

---

## Directory Structure

```
connectors/
├── README.md           # This file
├── .env                # Credentials (gitignored)
├── requirements.txt    # Python dependencies
├── google_ads.py       # Google Ads connector
├── meta_ads.py         # Meta/Facebook Ads connector
├── kendall.py          # Kendall.ai connector
├── shopify_enhanced.py # Enhanced Shopify connector
├── data_aggregator.py  # Combines all sources for CAM
└── data/               # Output directory for pulled data
    ├── google_ads/
    ├── meta_ads/
    ├── kendall/
    └── shopify/
```

## Next Steps

1. Set up API credentials for each platform
2. Run individual connectors to test
3. Run aggregator to calculate CAM
4. Build daily automation (cron/scheduled task)
