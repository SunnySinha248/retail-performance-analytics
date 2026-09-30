"""
01_generate_data.py
Generates a realistic synthetic retail sales dataset (India, FY2022-FY2025)
for the Revenue, Profitability & Regional Performance dashboard.

Output: data/raw/retail_sales.csv  (one row per order line)
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "retail_sales.csv"

# ---------- Dimensions ----------
regions = {
    "North":   {"states": {"Delhi": ["New Delhi"], "Haryana": ["Gurugram", "Faridabad"], "Punjab": ["Ludhiana", "Amritsar"], "Uttar Pradesh": ["Lucknow", "Noida", "Kanpur"]}, "weight": 0.27, "margin_adj": 0.00},
    "West":    {"states": {"Maharashtra": ["Mumbai", "Pune", "Nagpur"], "Gujarat": ["Ahmedabad", "Surat"], "Rajasthan": ["Jaipur"]}, "weight": 0.29, "margin_adj": 0.02},
    "South":   {"states": {"Karnataka": ["Bengaluru", "Mysuru"], "Tamil Nadu": ["Chennai", "Coimbatore"], "Telangana": ["Hyderabad"], "Kerala": ["Kochi"]}, "weight": 0.26, "margin_adj": 0.015},
    "East":    {"states": {"West Bengal": ["Kolkata"], "Odisha": ["Bhubaneswar", "Sambalpur"], "Bihar": ["Patna"]}, "weight": 0.11, "margin_adj": -0.035},
    "Central": {"states": {"Madhya Pradesh": ["Indore", "Bhopal"], "Chhattisgarh": ["Raipur"]}, "weight": 0.07, "margin_adj": -0.01},
}

catalog = {
    "Technology": {"Phones": (8000, 45000, 0.14), "Laptops": (35000, 110000, 0.11), "Accessories": (500, 6000, 0.26), "Printers": (6000, 30000, 0.16)},
    "Furniture":  {"Chairs": (3000, 22000, 0.12), "Tables": (6000, 40000, 0.04), "Bookcases": (4000, 18000, 0.07), "Furnishings": (400, 5000, 0.20)},
    "Office Supplies": {"Paper": (100, 1200, 0.32), "Binders": (150, 1500, 0.30), "Storage": (800, 8000, 0.15), "Appliances": (2000, 15000, 0.18), "Stationery": (50, 800, 0.35)},
}
cat_weights = {"Technology": 0.30, "Furniture": 0.22, "Office Supplies": 0.48}

segments = {"Consumer": 0.51, "Corporate": 0.31, "Small Business": 0.18}
ship_modes = {"Standard": (0.60, 5), "Second Class": (0.20, 3), "First Class": (0.15, 2), "Same Day": (0.05, 0)}
channels = {"Online": 0.58, "In-Store": 0.42}

# ---------- Customers ----------
N_CUST = 1400
first = ["Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kavya", "Rohan", "Saanvi", "Arjun", "Meera", "Kabir", "Priya", "Rahul", "Neha", "Vikram", "Pooja", "Karan", "Sneha", "Amit"]
last = ["Sharma", "Verma", "Iyer", "Reddy", "Patel", "Gupta", "Nair", "Das", "Singh", "Mehta", "Rao", "Joshi", "Kulkarni", "Banerjee", "Mishra", "Chopra"]

region_names = list(regions)
region_w = np.array([regions[r]["weight"] for r in region_names])
cust = []
for i in range(N_CUST):
    r = rng.choice(region_names, p=region_w)
    st = rng.choice(list(regions[r]["states"]))
    city = rng.choice(regions[r]["states"][st])
    seg = rng.choice(list(segments), p=list(segments.values()))
    activity = rng.gamma(1.4, 1.0)  # heterogeneity in purchase frequency
    cust.append((f"CUST-{10001+i}", f"{rng.choice(first)} {rng.choice(last)}", seg, r, st, city, activity))
cust = pd.DataFrame(cust, columns=["Customer ID", "Customer Name", "Segment", "Region", "State", "City", "activity"])

# ---------- Orders ----------
dates = pd.date_range("2022-04-01", "2026-03-31", freq="D")  # FY22-23 .. FY25-26 (4 Indian fiscal years)
t = np.arange(len(dates)) / 365.0
month = dates.month.values
# seasonality: Diwali/festive peak Oct-Nov, fiscal year-end push in March, monsoon dip Jul-Aug
season = np.select([np.isin(month, [10, 11]), month == 3, np.isin(month, [7, 8]), month == 12],
                   [1.45, 1.25, 0.82, 1.15], 1.0)
growth = 1.14 ** t  # ~14% YoY growth
dow = np.where(dates.dayofweek >= 5, 1.10, 1.0)
lam = 7.5 * season * growth * dow
n_orders = rng.poisson(lam)

cust_p = cust["activity"].values / cust["activity"].sum()
rows = []
oid = 100000
for d, n in zip(dates, n_orders):
    for _ in range(n):
        oid += 1
        c = cust.iloc[rng.choice(N_CUST, p=cust_p)]
        mode = rng.choice(list(ship_modes), p=[v[0] for v in ship_modes.values()])
        ship_days = ship_modes[mode][1] + rng.integers(0, 3) if mode != "Same Day" else 0
        chan = rng.choice(list(channels), p=list(channels.values()))
        for _line in range(rng.choice([1, 1, 1, 2, 2, 3, 4])):
            cat = rng.choice(list(cat_weights), p=list(cat_weights.values()))
            sub = rng.choice(list(catalog[cat]))
            lo, hi, base_m = catalog[cat][sub]
            unit_price = float(np.round(np.exp(rng.uniform(np.log(lo), np.log(hi))), -1))
            qty = int(rng.choice([1, 1, 2, 2, 3, 4, 5, 6], p=[.25, .15, .2, .12, .1, .08, .05, .05]))
            # discounting: heavier in festive months, East region, Furniture
            disc_p = 0.35 + 0.15 * (d.month in (10, 11)) + 0.10 * (c.Region == "East") + 0.08 * (cat == "Furniture")
            discount = float(rng.choice([0.05, 0.10, 0.15, 0.20, 0.30, 0.40], p=[.25, .28, .18, .14, .10, .05])) if rng.random() < disc_p else 0.0
            sales = round(unit_price * qty * (1 - discount), 2)
            margin = base_m + regions[c.Region]["margin_adj"] - 1.25 * discount + rng.normal(0, 0.05)
            if chan == "Online":
                margin += 0.01
            profit = round(sales * margin, 2)
            rows.append({
                "Order ID": f"ORD-{oid}", "Order Date": d.date(), "Ship Date": (d + pd.Timedelta(days=int(ship_days))).date(),
                "Ship Mode": mode, "Channel": chan, "Customer ID": c["Customer ID"], "Customer Name": c["Customer Name"],
                "Segment": c.Segment, "Region": c.Region, "State": c.State, "City": c.City, "Country": "India",
                "Category": cat, "Sub-Category": sub, "Unit Price": unit_price, "Quantity": qty,
                "Discount": discount, "Sales": sales, "Profit": profit,
            })

df = pd.DataFrame(rows)
OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT, index=False)
print(f"Wrote {len(df):,} rows, {df['Order ID'].nunique():,} orders -> {OUT}")
print(f"Revenue: INR {df.Sales.sum()/1e7:,.2f} Cr | Profit: INR {df.Profit.sum()/1e7:,.2f} Cr | Margin: {df.Profit.sum()/df.Sales.sum():.1%}")
