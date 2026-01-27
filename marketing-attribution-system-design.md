# TuffWraps Marketing Attribution & Scaling System

## Overview

**Business Context:**
- E-commerce brand (Shopify Plus + Amazon) selling lifting gear: wrist wraps, knee sleeves, belts, straps, apparel
- AOV: $50-150 with some repeat customers
- Current ad spend: ~$34k/month (Meta ~$17k, Google ~$17k)
- Additional channels: TikTok influencer/affiliate, athlete partnerships
- Sales channels: Shopify DTC + Amazon Marketplace
- Attribution tool: Kendall.ai (has MCP server access)

**Core Problems:**
1. High CPA / low ROAS
2. Inconsistent performance
3. Can't scale without performance tanking
4. Attribution confusion - Meta and Google both claim credit for same sales
5. Single founder managing everything

**Goal:** Fix profitability → Systematize → Scale

---

## The Trust Problem with Attribution

No single attribution source is reliable. Each one lies in its own way:

| Source | How It Lies |
|--------|-------------|
| **Meta** | Claims credit for anyone who saw an ad in 7 days, even if they Googled you directly |
| **Google** | Claims branded search as a "conversion" when those people already knew you |
| **Kendall.ai** | Tries to deduplicate but still relies on click/view data affected by iOS privacy |
| **Shopify** | Tells you what sold, but not why |
| **GA4** | Last-click bias, data sampling, also affected by iOS privacy |

**Solution: Triangulate multiple signals instead of trusting one source.**

---

## Core Data Sources

| Source | What We Pull | How |
|--------|--------------|-----|
| Shopify Plus | Orders, customers, products, COGS, discounts | Shopify API |
| Amazon Seller Central | Orders, units, revenue by product, fees | Amazon SP-API |
| Meta Ads | Spend, campaigns, ad sets, ads, metrics | Meta Marketing API |
| Google Ads | Spend, campaigns, ad groups, keywords, metrics | Google Ads API |
| Kendall.ai | Attributed revenue, customer journeys, channel data | MCP Server |
| Google Search Console | Branded search impressions, clicks, CTR | GSC API |
| GA4 | Traffic sources, behavior data (triangulation) | GA4 API |
| Klaviyo | Email revenue, flows (if applicable) | Klaviyo API |

---

## Key Metrics Framework

### Primary Metric: Contribution After Marketing (CAM)

```
CAM = Revenue - COGS - Shipping - Ad Spend
```

Per order:
```
CAM per order = AOV - COGS - Shipping - (Ad Spend ÷ Orders)
```

### Calculated Daily:

- **Blended CAM** (total and per order)
- **CAM by channel** (using Kendall attribution)
- **CAM trends** (7-day, 30-day rolling)
- **Platform vs. Kendall attribution gap** (who's over-claiming)
- **New vs. returning customer revenue split**
- **Blended new customer CAC** = Total spend ÷ new customers

---

## Decision Framework: What To Actually Do

### Decision 1: Should I increase or decrease total ad spend?

| Blended CAM Trend (7-day) | New Customer Volume | Action |
|---------------------------|---------------------|--------|
| CAM above target, rising | Stable or growing | **Increase spend 10-15%** |
| CAM above target, flat | Stable | **Hold spend, test new creative** |
| CAM above target, falling | Growing | **Hold - watch for 3 more days** |
| CAM below target | Any | **Cut spend on worst performers until CAM recovers** |

### Decision 2: Where do I shift budget between channels?

| Signal | Action |
|--------|--------|
| Meta CAM > Google CAM for 7+ days | Shift 10-20% budget from Google → Meta |
| Google CAM > Meta CAM for 7+ days | Shift 10-20% budget from Meta → Google |
| Both channels CAM declining | Don't shift - fix creative or audiences first |
| One channel CAM rising, one flat | Increase spend on rising channel only |

### Decision 3: Which campaigns to scale vs. kill?

| Campaign CAM (7-day) | Trend | Action |
|----------------------|-------|--------|
| Above target | Rising or flat | **Scale: increase budget 20%** |
| Above target | Falling | **Hold: watch, refresh creative** |
| Below target | Rising | **Hold: give it 5 more days** |
| Below target | Flat or falling for 7+ days | **Kill: pause or cut budget 50%** |

### Decision 4: When to launch new creative vs. scale existing?

| Top performing ad | Action |
|-------------------|--------|
| CAM strong, but fatiguing (CPM rising, CTR dropping) | **Launch new creative variations** |
| CAM strong and stable | **Scale spend on this ad** |
| No ads with strong CAM | **Stop scaling, go into creative testing mode** |

---

## Measuring Top-of-Funnel's True Impact

### The Problem

Meta TOF shows 1.3 ROAS → looks like a loser

But in reality:
- New people see your ad
- They don't buy immediately
- They Google "TuffWraps" later
- Google Branded Search gets the conversion
- Google looks like a hero, Meta looks like a waste

**If you turn off Meta TOF, your "great" Google performance collapses.**

### Method 1: Blended New Customer Test

Don't look at TOF ROAS in isolation:

```
TOF spend goes up → Do NEW customers (blended) go up?
TOF spend goes down → Do NEW customers (blended) go down?
```

Track over 2-3 week windows. If Meta TOF is feeding the funnel, new customer volume should correlate with TOF spend, even if Meta's reported ROAS is low.

### Method 2: Branded Search as a Proxy

| TOF Spend | Branded Search Volume | What It Means |
|-----------|----------------------|---------------|
| Increase TOF | Branded searches go up in 7-14 days | TOF is working - creating demand |
| Decrease TOF | Branded searches drop | TOF was feeding the funnel |
| Change TOF | No change in branded | TOF might not be reaching new people |

**Data sources for branded search:**
- **Google Search Console**: Organic branded impressions (total demand)
- **Google Ads**: Branded campaign impressions/clicks (captured demand)

### Method 3: Geo Holdout Test (Gold Standard)

1. Pick a region (e.g., Texas)
2. Turn off Meta TOF in that region only
3. Keep everything else the same
4. After 3-4 weeks, compare:
   - Texas total revenue vs. same period last year
   - Texas vs. similar region where TOF stayed on

If Texas revenue drops more than expected → Meta TOF was incremental.

### System Output for TOF

Instead of just showing ROAS:

```
Meta TOF ROAS (platform):     1.3x
Branded Search Trend:         ↑ 12% since TOF increase
New Customer CAC (blended):   $42 (target: $50) ✓
Estimated TOF Contribution:   Likely incremental - don't cut
```

---

## Measuring Amazon Halo Effect

### The Problem

Meta/Google ads don't just drive Shopify sales - they also drive Amazon sales with zero attribution:

```
You run Meta TOF → Person sees TuffWraps ad →
They search "tuffwraps knee sleeves" on Amazon →
They buy on Amazon →
Meta gets zero credit → Amazon gets the sale
```

This is invisible unless you measure the correlation.

### How to Measure Amazon Halo

**Method 1: Correlation Analysis**

| TOF Spend | Amazon Sales (7-14 day lag) | What It Means |
|-----------|----------------------------|---------------|
| Increase Meta TOF | Amazon sales go up | TOF is driving Amazon demand |
| Decrease Meta TOF | Amazon sales drop | TOF was feeding Amazon |
| Change TOF | No change in Amazon | Audience may prefer DTC over Amazon |

Track with a 7-14 day lag - people don't buy immediately.

**Method 2: Product-Level Correlation**

If you run TOF ads featuring specific products (e.g., knee sleeves):
- Track if THAT product's Amazon sales correlate with TOF spend
- More specific correlation = stronger signal

**Method 3: Amazon Brand Analytics (if available)**

Amazon Brand Analytics shows:
- Search frequency rank for your brand terms
- Click share and conversion share

Track if branded search on Amazon increases when TOF spend increases.

### Data to Pull from Amazon

| Data Point | Why It Matters |
|------------|----------------|
| Daily orders by product | Correlate with TOF spend |
| Revenue by product | Calculate Amazon contribution to total CAM |
| Amazon fees (FBA, referral) | Needed for true Amazon CAM |
| Organic search rank (if available) | Signal for brand awareness |

### Updated Blended CAM Formula

```
Total Blended CAM = (Shopify Revenue + Amazon Revenue) - Total COGS - Total Shipping - Amazon Fees - Total Ad Spend
```

The system should now answer:
1. Is TOF driving Google branded search? (GSC data)
2. Is TOF driving Amazon sales? (Amazon SP-API data)
3. What's TRUE blended CAM across Shopify + Amazon?

### System Output for Amazon Halo

```
Meta TOF ROAS (platform):     1.3x
Branded Search Trend:         ↑ 12% since TOF increase
Amazon Sales Trend:           ↑ 18% (7-day lag) since TOF increase
Total Blended Revenue:        Shopify $42k + Amazon $18k = $60k
Blended CAM:                  $14,200 (target: $12,000) ✓
Estimated TOF Contribution:   Driving both Google + Amazon - don't cut
```

---

## Where GA4 Fits

**Useful for:**
- Another attribution view (triangulation)
- On-site behavior analysis
- Traffic source breakdown (organic, direct, referral)
- Audience insights

**NOT useful for:**
- Source of truth for conversions (use Shopify)
- Ad platform optimization (platforms use their own pixels)
- Real-time decisions (data delayed and sampled)

**Role in system:** Secondary triangulation input, not primary decision source.

---

## Automation & Alerts

### Daily Automated Calculations:
- Blended CAM (total and per order)
- CAM by channel
- CAM trends (7-day, 30-day)
- Branded search volume trends
- Platform attribution gap analysis

### Automated Alerts:
- "Blended CAM dropped 15% vs. last week"
- "Meta CAM trending down for 5 days straight"
- "Campaign X has negative CAM for 7 days - consider pausing"
- "Google branded search is 30% of spend but Kendall shows minimal incremental value"
- "Branded search impressions up 20% - TOF likely working"

### Actions (Start Manual, Automate Later):
- Pause underperforming ads
- Shift budget between campaigns
- Adjust bids based on CAM thresholds

---

## Implementation Phases

### Phase 1: Data Foundation
- Connect all data sources (Shopify, Amazon, Meta, Google Ads, Kendall.ai, GSC)
- Build daily data aggregation pipeline
- Calculate blended metrics and CAM (across Shopify + Amazon)

### Phase 2: Decision Dashboard
- Display CAM by channel and campaign
- Show branded search correlation with TOF spend
- Show Amazon sales correlation with TOF spend
- Surface alerts and recommendations

### Phase 3: Guided Actions
- Implement decision rules from framework
- Generate daily "what to do" recommendations
- Track outcomes of actions taken

### Phase 4: Incrementality Testing
- Build geo holdout test framework
- Measure true channel incrementality
- Refine decision rules based on test results

### Phase 5: Automation
- Auto-pause consistently negative CAM campaigns
- Auto-alert on significant trend changes
- Budget reallocation suggestions

---

## API Integrations Required

| Platform | API/Method | Key Endpoints |
|----------|------------|---------------|
| Shopify Plus | REST/GraphQL API | Orders, Customers, Products |
| Amazon Seller Central | SP-API | Orders, Sales Reports, Fees, Brand Analytics |
| Meta Ads | Marketing API | Campaigns, Ad Sets, Ads, Insights |
| Google Ads | Google Ads API | Campaigns, Ad Groups, Keywords, Metrics |
| Kendall.ai | MCP Server | Attribution data, Customer journeys |
| Google Search Console | GSC API | Search Analytics (queries, impressions) |
| GA4 | GA4 Data API | Traffic sources, Conversions |
| Klaviyo | Klaviyo API | Campaigns, Flows, Revenue |

---

## Success Criteria

1. **Clear daily guidance** on what to do (not just data to interpret)
2. **CAM trending above target** consistently (Shopify + Amazon combined)
3. **Confident TOF decisions** backed by branded search AND Amazon sales correlation
4. **Time savings** - less guessing, more acting on signals
5. **Scalable** - when CAM is healthy, can increase spend confidently
6. **Full picture visibility** - understand how ads impact both DTC and Amazon sales
