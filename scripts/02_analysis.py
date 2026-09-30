"""
02_analysis.py
Segmentation, statistical analysis and forecasting on the retail sales data.
Produces Tableau-ready extracts in data/processed/ and summary charts in images/.

Steps
  1. Clean + feature engineering (fiscal year, margin, discount band, ship lag)
  2. Customer segmentation: RFM scoring + K-Means clustering
  3. Statistical analysis:
       - One-way ANOVA: does profit margin differ by region?
       - Chi-square: is loss-making order incidence linked to discount band?
       - OLS regression: drivers of line-level profit margin
  4. Forecasting: Holt-Winters (triple exponential smoothing) on monthly revenue,
     12-month horizon with 95% prediction intervals, backtested on last 6 months.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import statsmodels.formula.api as smf
from statsmodels.tsa.holtwinters import ExponentialSmoothing

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "retail_sales.csv"
PROC = ROOT / "data" / "processed"
IMG = ROOT / "images"
PROC.mkdir(parents=True, exist_ok=True)
IMG.mkdir(exist_ok=True)
summary = {}

# ------------------------------------------------------------------ 1. Clean
df = pd.read_csv(RAW, parse_dates=["Order Date", "Ship Date"])
df = df.drop_duplicates()
df["Fiscal Year"] = np.where(df["Order Date"].dt.month >= 4, df["Order Date"].dt.year, df["Order Date"].dt.year - 1)
df["Fiscal Year"] = "FY" + (df["Fiscal Year"] % 100).astype(str).str.zfill(2) + "-" + ((df["Fiscal Year"] + 1) % 100).astype(str).str.zfill(2)
df["Order Month"] = df["Order Date"].dt.to_period("M").dt.to_timestamp()
df["Profit Margin"] = df["Profit"] / df["Sales"]
df["Discount Band"] = pd.cut(df["Discount"], [-0.01, 0, 0.10, 0.20, 1], labels=["No Discount", "1-10%", "11-20%", ">20%"])
df["Ship Lag Days"] = (df["Ship Date"] - df["Order Date"]).dt.days
df["Is Loss"] = (df["Profit"] < 0).astype(int)

# ------------------------------------------------------------------ 2. Segmentation (RFM + K-Means)
snapshot = df["Order Date"].max() + pd.Timedelta(days=1)
rfm = df.groupby("Customer ID").agg(
    Recency=("Order Date", lambda s: (snapshot - s.max()).days),
    Frequency=("Order ID", "nunique"),
    Monetary=("Sales", "sum"),
    Profit=("Profit", "sum"),
).reset_index()
for col, asc in [("Recency", False), ("Frequency", True), ("Monetary", True)]:
    ranks = rfm[col].rank(method="first", ascending=asc)
    rfm[col[0] + "_Score"] = pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["RFM Score"] = rfm[["R_Score", "F_Score", "M_Score"]].sum(axis=1)

X = StandardScaler().fit_transform(np.column_stack([np.log1p(rfm.Recency), np.log1p(rfm.Frequency), np.log1p(rfm.Monetary)]))
sil = {k: silhouette_score(X, KMeans(k, n_init=10, random_state=42).fit_predict(X)) for k in range(3, 7)}
K = 4  # business-interpretable choice; silhouette scores stored below for reference
km = KMeans(K, n_init=10, random_state=42).fit(X)
rfm["Cluster"] = km.labels_
# Name clusters by average monetary value / recency
prof = rfm.groupby("Cluster").agg(R=("Recency", "mean"), F=("Frequency", "mean"), M=("Monetary", "mean"))
order = prof.sort_values("M", ascending=False).index.tolist()
names = {}
names[order[0]] = "Champions"
rest = prof.loc[order[1:]]
at_risk = rest["R"].idxmax()
names[at_risk] = "At Risk / Lapsing"
remaining = [c for c in order[1:] if c != at_risk]
names[remaining[0]] = "Loyal Regulars"
for c in remaining[1:]:
    names[c] = "Occasional Buyers"
rfm["Customer Segment (Cluster)"] = rfm["Cluster"].map(names)
cust_attr = df.drop_duplicates("Customer ID")[["Customer ID", "Customer Name", "Segment", "Region", "State", "City"]]
rfm = rfm.merge(cust_attr, on="Customer ID")
rfm.to_csv(PROC / "customer_segments.csv", index=False)

seg_prof = rfm.groupby("Customer Segment (Cluster)").agg(
    Customers=("Customer ID", "count"), Avg_Recency_Days=("Recency", "mean"), Avg_Orders=("Frequency", "mean"),
    Avg_Revenue=("Monetary", "mean"), Total_Revenue=("Monetary", "sum"), Total_Profit=("Profit", "sum"),
).round(1)
seg_prof["Revenue Share"] = (seg_prof.Total_Revenue / seg_prof.Total_Revenue.sum()).round(3)
seg_prof["Customer Share"] = (seg_prof.Customers / seg_prof.Customers.sum()).round(3)
summary["segmentation"] = {"silhouette_by_k": {k: round(v, 3) for k, v in sil.items()}, "chosen_k": K,
                           "profile": seg_prof.reset_index().to_dict(orient="records")}

df = df.merge(rfm[["Customer ID", "Customer Segment (Cluster)", "RFM Score"]], on="Customer ID", how="left")

# ------------------------------------------------------------------ 3. Statistical analysis
# 3a ANOVA: margin by region (order-level margin)
orders = df.groupby(["Order ID", "Region"]).agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).reset_index()
orders["Margin"] = orders.Profit / orders.Sales
groups = [g.Margin.values for _, g in orders.groupby("Region")]
f_stat, p_anova = stats.f_oneway(*groups)
kw_stat, p_kw = stats.kruskal(*groups)
region_margin = df.groupby("Region").apply(lambda g: g.Profit.sum() / g.Sales.sum(), include_groups=False).sort_values()
summary["anova_margin_by_region"] = {"F": round(f_stat, 2), "p_value": float(f"{p_anova:.3g}"),
                                     "kruskal_H": round(kw_stat, 2), "kruskal_p": float(f"{p_kw:.3g}"),
                                     "region_margin": region_margin.round(4).to_dict()}

# 3b Chi-square: loss incidence vs discount band
ct = pd.crosstab(df["Discount Band"], df["Is Loss"])
chi2, p_chi, dof, _ = stats.chi2_contingency(ct)
loss_rate = df.groupby("Discount Band", observed=True)["Is Loss"].mean().round(4)
summary["chi_square_loss_vs_discount"] = {"chi2": round(chi2, 1), "dof": int(dof), "p_value": float(f"{p_chi:.3g}"),
                                          "loss_rate_by_band": {str(k): v for k, v in loss_rate.items()}}

# 3c OLS: drivers of profit margin
reg_df = df.rename(columns={"Profit Margin": "margin", "Sub-Category": "subcat", "Ship Mode": "shipmode"})
model = smf.ols("margin ~ Discount + C(Region, Treatment('North')) + C(Category) + C(Segment) + C(Channel) + np.log(Sales)", data=reg_df).fit(cov_type="HC3")
coefs = model.params.round(4).to_dict()
pvals = model.pvalues.to_dict()
summary["ols_margin_drivers"] = {"r_squared": round(model.rsquared, 3), "n": int(model.nobs),
                                 "coefficients": {k: {"coef": coefs[k], "p": float(f"{pvals[k]:.3g}")} for k in coefs}}
with open(ROOT / "docs" / "regression_output.txt", "w") as f:
    f.write(str(model.summary()))

# Discount break-even: margin = a + b*discount -> discount where margin hits 0 (overall avg)
b = model.params["Discount"]
base_margin_no_disc = df.loc[df.Discount == 0, "Profit"].sum() / df.loc[df.Discount == 0, "Sales"].sum()
summary["discount_breakeven"] = round(base_margin_no_disc / -b, 3)

# ------------------------------------------------------------------ 4. Forecasting
monthly = df.groupby("Order Month").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).asfreq("MS")
y = monthly["Sales"]

def hw(series):
    return ExponentialSmoothing(series, trend="add", seasonal="mul", seasonal_periods=12,
                                initialization_method="estimated").fit(optimized=True)

# Backtest: train on all but last 6 months
train, test = y.iloc[:-6], y.iloc[-6:]
bt = hw(train).forecast(6)
mape = float(np.mean(np.abs((test - bt) / test)))
naive = y.shift(12).iloc[-6:]
mape_naive = float(np.mean(np.abs((test - naive) / test)))

fit = hw(y)
H = 12
fc = fit.forecast(H)
resid_sd = np.std(fit.resid, ddof=1)
# simulate prediction intervals
sims = fit.simulate(H, repetitions=2000, error="mul", random_errors="bootstrap", random_state=42)
lo, hi = sims.quantile(0.025, axis=1), sims.quantile(0.975, axis=1)

hist = pd.DataFrame({"Month": y.index, "Revenue": y.values, "Type": "Actual",
                     "Fitted": fit.fittedvalues.values, "Lower 95%": np.nan, "Upper 95%": np.nan})
fut = pd.DataFrame({"Month": fc.index, "Revenue": fc.values, "Type": "Forecast",
                    "Fitted": np.nan, "Lower 95%": lo.values, "Upper 95%": hi.values})
forecast_df = pd.concat([hist, fut], ignore_index=True).round(2)
forecast_df.to_csv(PROC / "revenue_forecast.csv", index=False)

summary["forecast"] = {"model": "Holt-Winters (additive trend, multiplicative seasonality, m=12)",
                       "backtest_mape_6m": round(mape, 4), "seasonal_naive_mape_6m": round(mape_naive, 4),
                       "next_12m_revenue_cr": round(fc.sum() / 1e7, 2),
                       "last_12m_revenue_cr": round(y.iloc[-12:].sum() / 1e7, 2),
                       "implied_growth": round(fc.sum() / y.iloc[-12:].sum() - 1, 4)}

# ------------------------------------------------------------------ Tableau extracts
df.to_csv(PROC / "sales_enriched.csv", index=False)
reg_summary = df.groupby(["Fiscal Year", "Region"]).agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"),
                                                        Orders=("Order ID", "nunique"), Customers=("Customer ID", "nunique")).reset_index()
reg_summary["Margin"] = reg_summary.Profit / reg_summary.Sales
reg_summary.round(4).to_csv(PROC / "region_fy_summary.csv", index=False)

# KPI summary
fy = df.groupby("Fiscal Year").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"), Orders=("Order ID", "nunique"))
fy["Margin"] = fy.Profit / fy.Sales
fy["YoY Growth"] = fy.Sales.pct_change()
fy["AOV"] = fy.Sales / fy.Orders
summary["kpis_by_fy"] = fy.round(4).reset_index().to_dict(orient="records")
subcat = df.groupby("Sub-Category").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).sort_values("Profit")
summary["loss_making_subcategories"] = subcat[subcat.Profit < 0].round(0).reset_index().to_dict(orient="records")
summary["top_profit_subcategories"] = subcat.tail(3).round(0).reset_index().to_dict(orient="records")

with open(ROOT / "docs" / "analysis_summary.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)

# ------------------------------------------------------------------ Charts for README
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREY = "#2F6DB5", "#E07B39", "#9AA3AD"

fig, ax = plt.subplots(figsize=(10, 4.2))
ax.plot(y.index, y / 1e5, color=BLUE, lw=2, label="Actual")
ax.plot(fc.index, fc / 1e5, color=ORANGE, lw=2, ls="--", label="Forecast (Holt-Winters)")
ax.fill_between(fc.index, lo / 1e5, hi / 1e5, color=ORANGE, alpha=0.15, label="95% interval")
ax.set_ylabel("Monthly revenue (INR lakh)")
ax.set_title(f"Monthly revenue with 12-month forecast  |  backtest MAPE {mape:.1%}", loc="left")
ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(IMG / "forecast.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 3.6))
rm = region_margin.sort_values()
ax.barh(rm.index, rm.values * 100, color=[ORANGE if v == rm.min() else BLUE for v in rm.values])
for i, v in enumerate(rm.values):
    ax.text(v * 100 + 0.1, i, f"{v:.1%}", va="center")
ax.set_xlabel("Profit margin (%)"); ax.set_title(f"Profit margin by region  |  ANOVA p = {p_anova:.1e}", loc="left")
fig.tight_layout(); fig.savefig(IMG / "region_margin.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 3.6))
lr = loss_rate * 100
ax.bar(lr.index.astype(str), lr.values, color=[GREY, BLUE, BLUE, ORANGE])
for i, v in enumerate(lr.values):
    ax.text(i, v + 1, f"{v:.0f}%", ha="center")
ax.set_ylabel("% of order lines at a loss"); ax.set_title("Loss incidence rises sharply with discount depth", loc="left")
fig.tight_layout(); fig.savefig(IMG / "discount_loss.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 4))
colors = {"Champions": BLUE, "Loyal Regulars": "#5FA8D3", "Occasional Buyers": GREY, "At Risk / Lapsing": ORANGE}
for name, g in rfm.groupby("Customer Segment (Cluster)"):
    ax.scatter(g.Frequency, g.Monetary / 1e5, s=10, alpha=0.6, label=name, color=colors.get(name, GREY))
ax.set_xlabel("Orders (frequency)"); ax.set_ylabel("Lifetime revenue (INR lakh)"); ax.set_yscale("log")
ax.set_title("Customer segments (RFM + K-Means, k=4)", loc="left"); ax.legend(frameon=False, markerscale=2)
fig.tight_layout(); fig.savefig(IMG / "customer_segments.png", dpi=150); plt.close(fig)

print(json.dumps({k: summary[k] for k in ["anova_margin_by_region", "chi_square_loss_vs_discount", "forecast", "discount_breakeven"]}, indent=2, default=str))
print(seg_prof)
print(fy.round(3))
print("OLS R2:", round(model.rsquared, 3), "| Discount coef:", round(b, 3))
print(subcat.round(0))
