# Power BI Build Guide — step by step

Build time: ~3 hours. Uses the **same processed data** as the Tableau version, so both tools tell the same story and can be compared side by side.

Files in this folder:

| File | Use |
|------|-----|
| `power_query.m` | Power Query code for the 3 data queries |
| `measures.dax` | Date table + ~45 DAX measures (KPIs, time intelligence, segments, forecast, dynamic titles) |
| `theme.json` | Report theme (blue accent, orange/red for losses) |

> **Mac users:** Power BI Desktop runs only on Windows. Options: a college lab / friend's Windows PC, Windows via Parallels or UTM, or a cloud Windows PC. Build the `.pbix` there, then copy it back into this repo.

---

## 0. Setup

1. Install **Power BI Desktop** (free, Microsoft Store).
2. Open it → **View → Themes → Browse for themes** → select `powerbi/theme.json`.
3. **File → Options → Current file → Regional settings** → Locale = *English (India)* (gives ₹ and lakh/crore-friendly formatting).

## 1. Load data (Power Query)

1. **Home → Transform data** → opens Power Query Editor.
2. **Manage Parameters → New Parameter** → Name `DataFolder`, Type *Text*, Current value = full path to your `data/processed/` folder **with a trailing backslash**.
3. **New Source → Blank Query** → **Advanced Editor** → paste the `Sales` query from `power_query.m` → rename query to `Sales`.
4. Repeat for `Customers` and `Forecast`.
5. **Close & Apply**.

## 2. Data model

1. **Modeling → New table** → paste the `Date` table from `measures.dax`.
2. Right-click `Date` → **Mark as date table** → column `Date`.
3. In `Date`: select `Month` → **Column tools → Sort by column → FY Month No**; select `Month-Year` → sort by `Month Start`.
4. In `Sales`: `Discount Band` → sort by `Discount Band Sort`. In `Customers`: `Customer Segment (Cluster)` → sort by `Cluster Sort`.
5. **Model view** → create relationships (drag column onto column):

```
Date[Date]            1 ──▶ *  Sales[Order Date]
Date[Date]            1 ──▶ *  Forecast[Month]
Customers[Customer ID] 1 ──▶ *  Sales[Customer ID]
```
   Single direction, Many-to-one. Delete any auto-detected relationship that differs from these.

6. Hide technical columns (right-click → Hide in report view): sort keys, `Sales[Fiscal Year]`, `Sales[Order Month]`, `Sales[Customer Segment (Cluster)]` (use the `Customers` version instead), `Cluster`.
7. Data category: `Sales[State (Map)]` → **State or Province**, `Sales[City]` → **City**, `Sales[Country]` → **Country**.

## 3. Measures

1. **Home → Enter data** → name the table `_Measures` → Load. (Delete the empty column later; the table then moves to the top of the Fields pane.)
2. Select `_Measures` → **New measure** → paste each measure from `measures.dax`, one at a time.
3. Formatting (Measure tools ribbon):
   - `%` measures → Percentage, 1 decimal
   - `Revenue`, `Profit`, `AOV`, `Revenue PY`, etc. → Currency ₹, 0 decimals, display units Auto
   - `Margin vs Company (pp)` → Percentage, 1 decimal, with `+0.0%;-0.0%` custom format

### Metric switcher (field parameter)
**Modeling → New parameter → Fields** → name `Select Metric` → add `Revenue`, `Profit`, `Orders`, `Profit Margin %` → tick *Add slicer to this page*. Use the parameter field as the Y-axis of the trend chart — the slicer swaps the measure.

---

## 4. Report pages

Canvas: **Format → Canvas settings → 16:9, 1280 × 720**. Keep a consistent grid: title bar across the top, KPI cards row, then 2×2 visuals.

### Page 1 — Executive Overview

| Visual | Fields | Notes |
|--------|--------|-------|
| Text box / Card (new) | `Title Overview` | Dynamic subtitle that updates with slicers |
| **Card (new)** ×5 | `Revenue`, `Profit`, `Profit Margin %`, `Orders`, `AOV` | Add reference label = `Revenue YoY %` etc. (Card → Reference labels) |
| Line chart | X: `Date[Month-Year]` · Y: `Select Metric` | Add **Analytics → Trend line** |
| Clustered column + line | X: `Date[Fiscal Year]` · Columns: `Revenue` · Line: `Revenue YoY %` | Secondary axis for the line |
| Bar chart | Y: `Category`, `Sub-Category` (drill) · X: `Revenue` | Bar colour → **fx → Field value → `Margin Colour`** — Tables shows red |
| Slicers | `Date[Fiscal Year]` (dropdown), `Sales[Region]`, `Sales[Segment]`, `Sales[Channel]` (tiles) | **View → Sync slicers** across all pages |

### Page 2 — Regional & Profitability Drivers

| Visual | Fields | Notes |
|--------|--------|-------|
| Text | `Title Region` | "East earns 1.6% margin vs 8.4% in South" |
| **Filled map** (or Azure Map) | Location: `State (Map)` · Colour: `Profit Margin %` | Fill colours → fx → Gradient, min red / centre grey / max blue. *If maps are disabled in your tenant: File → Options → Security → enable map visuals.* |
| Bar chart | Y: `Region` · X: `Profit Margin %` | Analytics → **Average line**; data labels on; colour by `Margin Colour` |
| Table / matrix | Rows: `Region` · Values: `Revenue`, `Revenue Share %`, `Profit Margin %`, `Margin vs Company (pp)`, `Avg Discount %`, `Loss Lines %` | Conditional formatting: data bars on Revenue, icons on `Margin vs Company` |
| Column chart | X: `Discount Band` · Y: `Loss Lines %` | Shows 1% → 17% → 56% → 95% |
| Scatter chart | X: `Sales[Discount]` (Don't summarize → Average) · Y: `Profit Margin %` · Values/Details: `Sub-Category`, `Region` · Size: `Revenue` | Analytics → **Trend line**; add constant Y line at 0 → break-even ~10% |
| **Key influencers** (AI visual) | Analyze: `Sales[Is Loss]` (set to 1) · Explain by: `Discount Band`, `Region`, `Category`, `Sub-Category`, `Segment`, `Channel`, `Ship Mode` | Power BI's built-in statistical driver analysis — confirms discount is the #1 driver |
| **Decomposition tree** | Analyze: `Profit` · Explain by: `Region`, `Category`, `Sub-Category`, `Discount Band` | Drill interactively to the loss pocket (East → Furniture → Tables, loss-making in every discounted band) |
| Card | `Profit Upside @10% Cap` | "Profit recoverable by capping discounts at 10%" (~₹1.8 Cr; upper bound, assumes volumes hold) |

### Page 3 — Customers & Forecast

| Visual | Fields | Notes |
|--------|--------|-------|
| Text | `Title Forecast` | |
| Cards | `Customers`, `Top 20% Customer Revenue Share`, `Next 12M Forecast (Cr)`, `Forecast Growth %` | |
| 100% stacked bar | Y: two rows via **Measure values** — `Customer Share %` and `Segment Revenue Share %` · Legend: `Customers[Customer Segment (Cluster)]` | "26% of customers = 52% of revenue" |
| Scatter | X: `Customers[Frequency]` · Y: `Customers[Lifetime Revenue]` (log axis) · Legend: `Customer Segment (Cluster)` · Details: `Customer ID` | Matches the Python RFM plot |
| Table | Rows: `Customer Segment (Cluster)` · Values: `Customers`, `Avg Recency (days)`, `Avg Orders per Customer`, `Revenue per Customer` | Segment profile |
| **Line chart (forecast)** | X: `Date[Month Start]` (continuous) · Y: `Actual Revenue`, `Forecast Revenue`, `Forecast Lower 95%`, `Forecast Upper 95%` | Format lines: Actual solid blue; Forecast dashed orange; bounds thin light-orange. Optional: **Error bars** on `Forecast Revenue` using Lower/Upper as bounds for a shaded band |
| (Optional) built-in forecast | Separate line chart X: `Date[Month Start]`, Y: `Revenue` → **Analytics → Forecast** (12 months, seasonality 12) | Compare Power BI's ETS forecast with the Python Holt-Winters model — good interview talking point |

Page 3 slicer note: select the FY slicer → **Format → Edit interactions** → set it to *None* for the forecast line chart (the forecast year has no sales and would otherwise be filtered out).

---

## 5. Interactivity checklist

- [ ] Cross-filtering: click a region bar → everything on the page filters (default). Set KPI cards to *filter*, not *highlight*.
- [ ] **Drill-through page** "Region Detail": new page, drag `Sales[Region]` into *Drill through* well, add matrix of State × Sub-Category with `Revenue`, `Profit Margin %`. Right-click any region → Drill through.
- [ ] **Tooltip page**: new page → Page information → *Allow use as tooltip*, size Tooltip; add a mini trend of `Revenue` and `Profit Margin %`. Set as report-page tooltip on the map.
- [ ] **Bookmarks + buttons**: Insert → Buttons → Navigator → **Page navigator** at the top of every page.
- [ ] Field parameter `Select Metric` on page 1.
- [ ] Sync slicers across pages.

## 6. Save & share

1. **File → Save as** `powerbi/Retail_Performance_Analytics.pbix`. The file embeds the data (~3–5 MB), fine for GitHub.
2. **File → Export → Export to PDF** → save as `powerbi/Retail_Performance_Analytics.pdf` (anyone can view it without Power BI).
3. Screenshot each page → `images/powerbi_overview.png`, `images/powerbi_profitability.png`, `images/powerbi_customers.png`.
4. *Optional online link:* **Publish** to Power BI Service needs a work/school account (try your IIM email). If your organisation allows it: in the Service, **File → Embed report → Publish to web** gives a public link for the README. If it's blocked, the PDF + screenshots + `.pbix` are enough for GitHub.
