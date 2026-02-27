# FiscalPilot Restaurant Example: QuickBooks Integration

This example demonstrates FiscalPilot's production-grade restaurant financial analysis with QuickBooks Online integration.

## Features

- **Industry-specific KPIs**: Food Cost %, Labor Cost %, Prime Cost, Occupancy Cost
- **QuickBooks Online Integration**: Auto-classifies QB accounts to restaurant cost buckets
- **Rate Limiting & Retry**: Production-ready API handling (500 req/min limit, exponential backoff)
- **Restaurant Account Mapping**: 80+ QuickBooks account names mapped (food cost, labor, beverage, etc.)

## Quick Start

### Option 1: CSV Analysis (No QuickBooks needed)

```bash
# Analyze existing transaction data
fiscalpilot restaurant --csv transactions.csv --company "Joe's Diner" --revenue 1200000
```

### Option 2: QuickBooks Integration

```bash
# Step 1: Connect to QuickBooks (interactive OAuth wizard)
fiscalpilot connect quickbooks

# Step 2: Run restaurant analysis
fiscalpilot restaurant --quickbooks --company "Joe's Diner"
```

## Setting Up QuickBooks Integration

### 1. Create a QuickBooks Developer App

1. Go to [developer.intuit.com](https://developer.intuit.com)
2. Create a new app with "Accounting" scope
3. Set redirect URI to `http://localhost:8765/callback`
4. Copy your Client ID and Client Secret

### 2. Connect FiscalPilot

```bash
fiscalpilot connect quickbooks
```

This launches an interactive wizard that:
1. Prompts for your credentials
2. Opens a browser for OAuth authorization
3. Exchanges the auth code for tokens
4. Saves tokens securely to `~/.fiscalpilot/tokens/`

### 3. Configure for Production

Create `fiscalpilot.yaml`:

```yaml
company:
  name: Joes Diner
  industry: restaurant
  annual_revenue: 1200000  # for ratio calculations

connectors:
  - type: quickbooks
    credentials:
      client_id: ${QUICKBOOKS_CLIENT_ID}
      client_secret: ${QUICKBOOKS_CLIENT_SECRET}
      realm_id: "your-company-id"
    options:
      sandbox: false
      start_date: "2024-01-01"

restaurant:
  seat_count: 60  # For RevPASH calculations
  operating_hours_per_week: 70
```

## Understanding Your Results

### Health Grade

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 85-100 | Excellent - all KPIs in healthy range |
| B | 70-84 | Good - minor improvements possible |
| C | 55-69 | Fair - several areas need attention |
| D | 40-54 | Poor - significant issues |
| F | 0-39 | Critical - immediate action required |

### Key KPIs

| KPI | Healthy Range | Critical Threshold |
|-----|--------------|-------------------|
| Food Cost % | 28-32% | >38% |
| Labor Cost % | 28-32% | >38% |
| Prime Cost % | 55-65% | >72% |
| Occupancy Cost % | 6-10% | >12% |
| Net Margin | 6-10% | <2% |

### QuickBooks Account Mapping

FiscalPilot automatically maps 80+ common QuickBooks account names to restaurant cost categories:

**Food Cost (maps to inventory benchmark)**
- Food Cost, Food Purchases, Food and Beverage
- COGS - Food, Cost of Food Sold
- Produce, Meat & Seafood, Dairy, Dry Goods

**Labor Cost (maps to payroll benchmark)**
- Kitchen Labor, FOH Labor, BOH Labor
- Server Wages, Cook Wages, Manager Salary
- Tips Paid, Employer Taxes, Workers Comp, Health Benefits

**Operating Expenses**
- Smallwares, Kitchen Supplies, Paper Goods
- POS Fees, Credit Card Fees, Third Party Delivery
- Pest Control, Grease Trap Service, Hood Cleaning

## Sample Output

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃           🍽️ Restaurant Analysis          ┃
┃                                          ┃
┃              Health Grade: B              ┃
┃              Score: 72/100                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ KPI               ┃ Actual ┃ Target      ┃ Status    ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ Food Cost %       │ 31.2%  │ 25-35%      │ ✅ healthy │
│ Labor Cost %      │ 33.8%  │ 25-35%      │ ⚠️ warning │
│ Prime Cost %      │ 65.0%  │ 55-68%      │ ✅ healthy │
│ Occupancy Cost %  │ 9.2%   │ 6-10%       │ ✅ healthy │
│ Net Margin        │ 5.8%   │ 2-10%       │ ✅ healthy │
└───────────────────┴────────┴─────────────┴───────────┘
```

## Troubleshooting

### "QuickBooks not connected"

Run the connection wizard:
```bash
fiscalpilot connect quickbooks
```

### "Rate limited (429)"

FiscalPilot handles this automatically with exponential backoff, but if persistent:
- Wait a few minutes
- Reduce date range with `start_date` option

### Token Expired

Tokens auto-refresh. If issues persist:
```bash
rm ~/.fiscalpilot/tokens/quickbooks.json
fiscalpilot connect quickbooks
```

## API Reference

### Python Usage

```python
from fiscalpilot.connectors.quickbooks_connector import QuickBooksConnector
from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer

async def analyze_restaurant():
    # Connect to QuickBooks
    connector = QuickBooksConnector(credentials={
        "client_id": "...",
        "client_secret": "...",
        "refresh_token": "...",
        "realm_id": "...",
    })
    
    # Pull data
    dataset = await connector.pull(company_profile)
    
    # Run restaurant analysis
    result = RestaurantAnalyzer.analyze(
        dataset, 
        annual_revenue=1_200_000,
        seat_count=60,
    )
    
    print(f"Health Grade: {result.health_grade}")
    print(f"Food Cost %: {result.kpis[0].actual:.1f}%")
    print(f"Labor Cost %: {result.kpis[1].actual:.1f}%")
    
    for alert in result.critical_alerts:
        print(f"⚠️ {alert}")
    
    await connector.close()
```

## Next Steps

- [Full Documentation](../../README.md)
- [Xero Integration](../xero/README.md) (coming soon)
- [Multi-location Support](../multi-location/README.md) (coming soon)
