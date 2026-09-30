# Tableau Build Guide — step by step

Build time: ~2–3 hours. Tool: **Tableau Public (free)** — download from public.tableau.com. Tableau Public saves workbooks to your free online profile, which gives you a shareable link for the GitHub README and your resume.

You will build **3 dashboards** tied together as one story:

| # | Dashboard | Answers |
|---|-----------|---------|
| 1 | Executive Overview | How big, how fast growing, how profitable? |
| 2 | Regional & Profitability Drivers | Where and why do we make or lose money? |
| 3 | Customers & Forecast | Who drives revenue, and what's next year? |

---

## 0. Connect the data

1. Open Tableau Public → **Connect → Text file** → `data/processed/sales_enriched.csv`.
2. On the Data Source page, drag in `customer_segments.csv` → it creates a **relationship**. Set it to `Customer ID = Customer ID`.
3. Separately: **Data → New Data Source → Text file** → `revenue_forecast.csv` (keep it as its own source; it is only used for the forecast chart).
4. Check data types (click the icon above each column):
   - `Order Date`, `Ship Date`, `Order Month`, `Month` → Date
   - `State` → Geographic Role → State/Province; `City` → Geographic Role → City; `Country` → Country
   - `Discount`, `Profit Margin` → Number (decimal)
5. Rename the data source to `Sales` and `Forecast`.

## 1. Calculated fields (Analysis → Create Calculated Field)

Create these in the `Sales` source. Copy exactly.

```
// Revenue (Cr)
SUM([Sales]) / 10000000

// Profit Margin %
SUM([Profit]) / SUM([Sales])

// Orders
COUNTD([Order ID])

// Customers
COUNTD([Customer ID])

// AOV
SUM([Sales]) / COUNTD([Order ID])

// Loss Order Lines %
SUM([Is Loss]) / COUNT([Order ID])

// Current FY  (parameter-free version: latest FY in data)
[Fiscal Year] = {MAX([Fiscal Year])}

// Prior FY Sales   (for YoY)
LOOKUP(SUM([Sales]), -1)

// YoY Growth %
(SUM([Sales]) - LOOKUP(SUM([Sales]), -1)) / ABS(LOOKUP(SUM([Sales]), -1))

// Margin Flag
IF [Profit Margin %] < 0 THEN "Loss"
ELSEIF [Profit Margin %] < 0.05 THEN "Thin (<5%)"
ELSE "Healthy" END

// Profit Colour (for diverging colour)
SUM([Profit])
```

Formatting: right-click each field → **Default Properties → Number Format**:
- `Profit Margin %`, `YoY Growth %`, `Loss Order Lines %` → Percentage, 1 decimal
- `Sales`, `Profit`, `AOV` → Currency (Custom), prefix `₹`, display units Lakhs or Crores as appropriate

### Parameter (makes the dashboard interactive)
**Create Parameter → `Select Metric`** (String, List): `Revenue`, `Profit`, `Orders`.
Then a calculated field:
```
// Metric Value
CASE [Select Metric]
WHEN "Revenue" THEN SUM([Sales])
WHEN "Profit"  THEN SUM([Profit])
WHEN "Orders"  THEN COUNTD([Order ID])
END
```
Right-click the parameter → **Show Parameter**.

---

## 2. Worksheets (one per chart — name each sheet as shown)

### Dashboard 1 — Executive Overview

**KPI Revenue** (repeat for Profit, Margin %, Orders, AOV)
- Drag `Revenue (Cr)` to **Text**. Marks = Text. Format: big font (28pt, bold), label "Revenue" above in 11pt grey.
- Filter `Fiscal Year` → show filter → single value dropdown. Right-click the filter → **Apply to Worksheets → All using this data source**.

**Sales Trend**
- Columns: `Order Date` → right-click → **Month (continuous, green pill)**
- Rows: `Metric Value`
- Marks: Line. Add `Fiscal Year` to Colour (optional).
- Analytics pane → drag **Trend Line** (linear) onto the view.

**Category Mix**
- Rows: `Category`, then `Sub-Category`. Columns: `SUM(Sales)`.
- Colour: `Profit Margin %` → Edit Colours → **Orange-Blue Diverging**, centre at 0.
- Sort descending by Sales. This instantly shows Tables are big but loss-making.

**YoY Growth**
- Columns: `Fiscal Year`. Rows: `SUM(Sales)` (bars) and `YoY Growth %` (dual axis, line).
- Right-click second axis → Dual Axis → Synchronise is OFF (different units).

### Dashboard 2 — Regional & Profitability Drivers

**Region Map**
- Double-click `State` (Tableau plots India automatically — if not, Map → Edit Locations → Country = India).
- Marks: Map (filled). Colour: `Profit Margin %` (diverging). Tooltip: Sales, Profit, Margin, Orders.

**Region Margin Bar**
- Rows: `Region`. Columns: `Profit Margin %`. Sort ascending. Label marks.
- Add a **Reference Line** (Analytics pane → Average Line) = company average margin.

**Discount vs Margin (statistical view)**
- Columns: `Discount` (Dimension, discrete) or `Discount Band`. Rows: `Profit Margin %`.
- Alternative scatter: Columns `AVG(Discount)`, Rows `Profit Margin %`, Detail `Order ID`, then Analytics → **Trend Line**. Hover the line → shows R² and p-value — this is your "statistical analysis" evidence.
- Add a constant reference line at 0 margin; the crossing point ≈ 10% discount = break-even.

**Loss by Discount Band**
- Columns: `Discount Band`. Rows: `Loss Order Lines %`. Bars, labelled.

**Sub-Category Profit (Pareto-style)**
- Rows: `Sub-Category`. Columns: `SUM(Profit)`. Colour: `Margin Flag`. Sort ascending → Tables appears first in red/orange.

### Dashboard 3 — Customers & Forecast

**Segment Summary**
- Rows: `Customer Segment (Cluster)`. Columns: `CNT(Customer ID)` and `SUM(Monetary)` side by side.
- Quick table calc on the second: **Percent of Total** → shows "26% of customers = 52% of revenue".

**RFM Scatter**
- Columns: `Frequency`. Rows: `Monetary` (right-click axis → Logarithmic). Colour: `Customer Segment (Cluster)`. Detail: `Customer ID`.

**Revenue Forecast** (uses the `Forecast` source)
- Columns: `Month` → continuous month. Rows: `Revenue`. Colour: `Type` (Actual = blue, Forecast = orange).
- Drag `Lower 95%` and `Upper 95%` to Rows → combine onto one axis via **Measure Values**, or use **Reference Band** (Analytics → Reference Band from `MIN(Lower 95%)` to `MAX(Upper 95%)`, per cell).
- Title: "12-month revenue forecast (Holt-Winters, backtest MAPE 9.3%)".
- *Optional cross-check:* on the Sales Trend sheet, Analytics → **Forecast** uses Tableau's own exponential smoothing — compare it with the Python forecast in a tooltip or caption.

---

## 3. Assemble dashboards

For each dashboard: **New Dashboard** → Size → **Fixed, 1366 × 768** (or Automatic).

Layout pattern (use Tiled containers):
```
┌──────────────────────────────────────────────────────────┐
│ Title + subtitle (1-line insight)          [FY filter]   │
├────────┬────────┬────────┬────────┬────────────────────────┤
│ KPI 1  │ KPI 2  │ KPI 3  │ KPI 4  │ KPI 5                  │
├────────┴────────┴────────┼────────┴────────────────────────┤
│ Main chart (trend/map)   │ Supporting chart               │
├──────────────────────────┼────────────────────────────────┤
│ Supporting chart         │ Supporting chart               │
└──────────────────────────┴────────────────────────────────┘
```

Interactivity (this is what makes it "interactive" on the resume):
1. **Dashboard → Actions → Add Action → Filter**: source = Region Map, target = all sheets, run on Select. Clicking a state filters everything.
2. **Highlight action**: hover on `Category` highlights across sheets.
3. **Navigation buttons**: Objects → Navigation → add buttons "Overview / Profitability / Customers" on each dashboard.
4. Keep the `Select Metric` parameter and `Fiscal Year` / `Region` / `Segment` filters on Dashboard 1.

Design rules:
- One accent colour (blue) + one alert colour (orange) for loss/negative. Grey for everything else.
- Every dashboard title states the insight, e.g. *"East region earns 1.6% margin vs 8.4% in South — driven by deep discounting."*
- Remove gridlines (Format → Lines → None), keep axis labels light grey.

## 4. Optional: Story

**New Story** → add the 3 dashboards as story points with captions:
1. "Revenue grew ~15% CAGR to ₹22.5 Cr, but margin is flat at ~7%."
2. "Discounts above 10% turn most orders loss-making; East region and Tables are the leaks."
3. "26% of customers bring 52% of revenue; forecast points to ₹24.2 Cr next FY."

## 5. Publish

1. **File → Save to Tableau Public As…** → sign in (free account) → name it `Retail Performance Analytics — India`.
2. It opens in the browser. Copy the URL.
3. Take screenshots of each dashboard → save as `images/dashboard_overview.png`, `images/dashboard_profitability.png`, `images/dashboard_customers.png`.
4. Also **File → Save As** a local copy as `tableau/Retail_Performance_Analytics.twbx` (Tableau Public allows "Save to Tableau Public" only; download the `.twbx` from your profile page via the download icon if you need the file for GitHub).
5. Paste the Tableau Public link into the README.
