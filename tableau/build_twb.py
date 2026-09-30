"""
build_twb.py — generates tableau/Retail_Performance_Analytics.twb
Usage: python tableau/build_twb.py [absolute path to data/processed]
"""
import sys, uuid, re
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr, unescape

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "processed")
import os
OUT = Path(os.environ.get("TWB_OUT", ROOT / "tableau" / "Retail_Performance_Analytics.twb"))
ONLY = os.environ.get("ONLY")          # comma list of sheet names to keep
NODASH = os.environ.get("NODASH") == "1"

# ----------------------------------------------------------------- data sources
SALES_COLS = [
    ("Order ID", "string"), ("Order Date", "date"), ("Ship Date", "date"), ("Ship Mode", "string"),
    ("Channel", "string"), ("Customer ID", "string"), ("Customer Name", "string"), ("Segment", "string"),
    ("Region", "string"), ("State", "string"), ("City", "string"), ("Country", "string"),
    ("Category", "string"), ("Sub-Category", "string"), ("Unit Price", "real"), ("Quantity", "integer"),
    ("Discount", "real"), ("Sales", "real"), ("Profit", "real"), ("Fiscal Year", "string"),
    ("Order Month", "date"), ("Profit Margin", "real"), ("Discount Band", "string"),
    ("Ship Lag Days", "integer"), ("Is Loss", "integer"), ("Customer Segment (Cluster)", "string"),
    ("RFM Score", "integer"),
]
CUST_COLS = [
    ("Customer ID", "string"), ("Recency", "integer"), ("Frequency", "integer"), ("Monetary", "real"),
    ("Profit", "real"), ("R_Score", "integer"), ("F_Score", "integer"), ("M_Score", "integer"),
    ("RFM Score", "integer"), ("Cluster", "integer"), ("Customer Segment (Cluster)", "string"),
    ("Customer Name", "string"), ("Segment", "string"), ("Region", "string"), ("State", "string"),
    ("City", "string"),
]
FC_COLS = [("Month", "date"), ("Revenue", "real"), ("Type", "string"), ("Fitted", "real"),
           ("Lower 95%", "real"), ("Upper 95%", "real")]

MEASURE_TYPES = {"real", "integer"}
DIM_OVERRIDE = {"RFM Score", "Cluster", "R_Score", "F_Score", "M_Score", "Ship Lag Days"}  # keep as measures anyway except Cluster
GEO = {"State": "[State].[Name]", "City": "[City].[Name]", "Country": "[Country].[Name]"}

SALES_CALCS = {
    # name: (caption, formula, datatype, format)
    "Calculation_1001": ("Revenue (Cr)", "SUM([Sales]) / 10000000", "real", '*"₹"#,##0.00" Cr"'),
    "Calculation_1002": ("Profit (Cr)", "SUM([Profit]) / 10000000", "real", '*"₹"#,##0.00" Cr"'),
    "Calculation_1003": ("Profit Margin %", "SUM([Profit]) / SUM([Sales])", "real", "p0.0%"),
    "Calculation_1004": ("Orders", "COUNTD([Order ID])", "integer", "n#,##0"),
    "Calculation_1005": ("AOV", "SUM([Sales]) / COUNTD([Order ID])", "real", '*"₹"#,##0'),
    "Calculation_1006": ("Loss Order Lines %", "SUM([Is Loss]) / COUNT([Order ID])", "real", "p0%"),
    "Calculation_1007": ("Revenue (Lakh)", "SUM([Sales]) / 100000", "real", '*"₹"#,##0.0" L"'),
    "Calculation_1008": ("Profit (Lakh)", "SUM([Profit]) / 100000", "real", '*"₹"#,##0.0" L"'),
    "Calculation_1009": ("Avg Discount %", "AVG([Discount])", "real", "p0.0%"),
    "Calculation_1010": ("Margin Flag",
                         'IF SUM([Profit]) / SUM([Sales]) < 0 THEN "Loss" ELSEIF SUM([Profit]) / SUM([Sales]) < 0.05 THEN "Thin (<5%)" ELSE "Healthy" END',
                         "string", None),
}
CUST_CALCS = {
    "Calculation_2001": ("Customer Share %", "COUNT([Customer ID]) / MIN({FIXED : COUNT([Customer ID])})", "real", "p0%"),
    "Calculation_2002": ("Revenue Share %", "SUM([Monetary]) / MIN({FIXED : SUM([Monetary])})", "real", "p0%"),
    "Calculation_2003": ("Lifetime Revenue (Lakh)", "SUM([Monetary]) / 100000", "real", '*"₹"#,##0.0" L"'),
}
FC_CALCS = {
    "Calculation_3001": ("Revenue (Lakh) ", "SUM([Revenue]) / 100000", "real", '*"₹"#,##0" L"'),
    "Calculation_3002": ("Lower 95% (Lakh)", "SUM([Lower 95%]) / 100000", "real", '*"₹"#,##0" L"'),
    "Calculation_3003": ("Upper 95% (Lakh)", "SUM([Upper 95%]) / 100000", "real", '*"₹"#,##0" L"'),
}

DS = {
    "sales": dict(name="federated.0sales0001", caption="Sales", file="sales_enriched.csv", cols=SALES_COLS, calcs=SALES_CALCS),
    "cust": dict(name="federated.0cust00001", caption="Customers", file="customer_segments.csv", cols=CUST_COLS, calcs=CUST_CALCS),
    "fc": dict(name="federated.0fcst00001", caption="Forecast", file="revenue_forecast.csv", cols=FC_COLS, calcs=FC_CALCS),
}


def col_role(name, dtype):
    if dtype in MEASURE_TYPES and name != "Cluster":
        return "measure", "quantitative"
    if dtype == "date":
        return "dimension", "ordinal"
    return "dimension", "nominal"


def datasource_xml(key):
    d = DS[key]
    tbl = d["file"].replace(".", "#")
    conn = f"textscan.{d['name'].split('.')[1]}"
    cols = "\n".join(
        f"            <column datatype='{t}' name={quoteattr(n)} ordinal='{i}' />" for i, (n, t) in enumerate(d["cols"]))
    objid = d['file'].split('.')[0] + "_" + uuid.uuid4().hex.upper()
    relation = f"""<relation connection='{conn}' name={quoteattr(d['file'])} table='[{tbl}]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_IN' separator=','>
{cols}
          </columns>
        </relation>"""
    RT = {"string": 129, "integer": 20, "real": 5, "date": 133}
    recs = "".join(
        f"<metadata-record class='column'><remote-name>{escape(n)}</remote-name><remote-type>{RT[t]}</remote-type>"
        f"<local-name>{escape('[' + n + ']')}</local-name><parent-name>[Extract]</parent-name>"
        f"<remote-alias>{escape(n)}</remote-alias><ordinal>{i}</ordinal><family>{escape(d['file'].split('.')[0])}</family>"
        f"<local-type>{t}</local-type><contains-null>true</contains-null><object-id>[{objid}]</object-id></metadata-record>"
        for i, (n, t) in enumerate(d["cols"]))
    extract = f"""      <extract _.fcp.VConnDownstreamExtractsWithWarnings.true...user-specific='false' count='-1' enabled='true' object-id='' units='records'>
        <connection access_mode='readonly' author-locale='en_US' class='hyper' dbname='Data/Extracts/{key}.hyper' default-settings='hyper' schema='Extract' sslmode='' tablename='Extract' update-time='10/01/2026 01:00:00 AM' username='tableau_internal_user'>
          <relation name='Extract' table='[Extract].[Extract]' type='table' />
          <metadata-records>{recs}</metadata-records>
        </connection>
      </extract>"""
    meta = []
    for n, t in d["cols"]:
        role, typ = col_role(n, t)
        extra = f" semantic-role='{GEO[n]}'" if (key != "fc" and n in GEO) else ""
        meta.append(f"      <column datatype='{t}' name={quoteattr('[' + n + ']')} role='{role}' type='{typ}'{extra} />")
    for cname, (cap, formula, dt, fmt) in d["calcs"].items():
        role, typ = ("dimension", "nominal") if dt == "string" else ("measure", "quantitative")
        f_attr = f" default-format={quoteattr(fmt)}" if fmt else ""
        meta.append(
            f"      <column caption={quoteattr(cap.strip())} datatype='{dt}'{f_attr} name='[{cname}]' role='{role}' type='{typ}'>\n"
            f"        <calculation class='tableau' formula={quoteattr(formula)} />\n      </column>")
    return f"""    <datasource caption={quoteattr(d['caption'])} inline='true' name='{d['name']}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption={quoteattr(d['file'].split('.')[0])} name='{conn}'>
            <connection class='textscan' directory={quoteattr(DATA_DIR)} filename={quoteattr(d['file'])} password='' server='' />
          </named-connection>
        </named-connections>
        <relation connection='{conn}' name={quoteattr(d['file'])} table='[{tbl}]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_IN' separator=','>
{cols}
          </columns>
        </relation>
      </connection>
      <aliases enabled='yes' />
{chr(10).join(meta)}
      <column caption={quoteattr(d['file'].split('.')[0])} datatype='table' name='[__tableau_internal_object_id__].[{objid}]' role='measure' type='quantitative' />
{extract}
      <layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />
      <semantic-values>
        <semantic-value key='[Country].[Name]' value='&quot;India&quot;' />
      </semantic-values>
      <object-graph>
        <objects>
          <object caption={quoteattr(d['file'].split('.')[0])} id='{objid}'>
            <properties context=''>
              {relation}
            </properties>
            <properties context='extract'>
              <relation name='Extract' table='[Extract].[Extract]' type='table' />
            </properties>
          </object>
        </objects>
      </object-graph>
    </datasource>"""


# ----------------------------------------------------------------- field refs
class F:
    """A field instance on a shelf."""
    def __init__(self, ds, field, deriv, kind):
        self.ds, self.field, self.deriv, self.kind = ds, field, deriv, kind  # kind: nk, qk, ok

    @property
    def calc(self):
        return self.field.startswith("Calculation_")

    @property
    def inst(self):
        return f"[{self.deriv}:{self.field}:{self.kind}]"

    @property
    def generated(self):
        return "(generated)" in self.field

    @property
    def ref(self):
        if self.generated:
            return f"[{DS[self.ds]['name']}].[{self.field}]"
        return f"[{DS[self.ds]['name']}].{self.inst}"

    def dep_xml(self):
        d = DS[self.ds]
        if self.calc:
            cap, formula, dt, fmt = d["calcs"][self.field]
            role, typ = ("dimension", "nominal") if dt == "string" else ("measure", "quantitative")
            f_attr = f" default-format={quoteattr(fmt)}" if fmt else ""
            col = (f"<column caption={quoteattr(cap.strip())} datatype='{dt}'{f_attr} name='[{self.field}]' role='{role}' type='{typ}'>"
                   f"<calculation class='tableau' formula={quoteattr(formula)} /></column>")
        else:
            dt = dict(d["cols"])[self.field]
            role, typ = col_role(self.field, dt)
            extra = f" semantic-role='{GEO[self.field]}'" if (self.ds != "fc" and self.field in GEO) else ""
            col = f"<column datatype='{dt}' name={quoteattr('[' + self.field + ']')} role='{role}' type='{typ}'{extra} />"
        typ_i = {"nk": "nominal", "qk": "quantitative", "ok": "ordinal"}[self.kind]
        deriv = {"none": "None", "sum": "Sum", "usr": "User", "tmn": "Month-Trunc", "avg": "Avg",
                 "ctd": "CountD", "cnt": "Count", "yr": "Year"}[self.deriv]
        inst = (f"<column-instance column={quoteattr('[' + self.field + ']')} derivation='{deriv}' "
                f"name={quoteattr(self.inst)} pivot='key' type='{typ_i}' />")
        return col, inst


def dim(ds, f):   return F(ds, f, "none", "nk")
def ssum(ds, f):  return F(ds, f, "sum", "qk")
def avg(ds, f):   return F(ds, f, "avg", "qk")
def usr(ds, f):   return F(ds, f, "usr", "qk")
def usrn(ds, f):  return F(ds, f, "usr", "nk")
def month(ds, f): return F(ds, f, "tmn", "qk")
def cnt(ds, f):   return F(ds, f, "cnt", "qk")


def worksheet(name, ds, mark, rows=(), cols=(), color=None, text=None, label=None, detail=(), size=None,
              sort=None, manual=None, show_labels=False, extra_fields=(), title=None, tooltip=()):
    fields = [x for x in list(rows) + list(cols) + [color, text, label, size] + list(detail) + list(extra_fields) + list(tooltip) if x]
    if sort:
        fields.append(sort[1])
    cols_xml, insts, seen_c, seen_i = [], [], set(), set()
    for f in fields:
        if f.generated:
            continue
        c, i = f.dep_xml()
        if f.field not in seen_c:
            cols_xml.append(c); seen_c.add(f.field)
        if f.inst not in seen_i:
            insts.append(i); seen_i.add(f.inst)
    enc = []
    if color: enc.append(f"<color column={quoteattr(color.ref)} />")
    if size: enc.append(f"<size column={quoteattr(size.ref)} />")
    if text: enc.append(f"<text column={quoteattr(text.ref)} />")
    if label: enc.append(f"<text column={quoteattr(label.ref)} />")
    for d_ in detail: enc.append(f"<lod column={quoteattr(d_.ref)} />")
    if mark == "Multipolygon":
        enc.append(f"<geometry column={quoteattr('[' + DS[ds]['name'] + '].[Geometry (generated)]')} />")
    for t_ in tooltip: enc.append(f"<tooltip column={quoteattr(t_.ref)} />")
    sort_xml = ""
    if sort:
        dimf, meas, direction = sort
        sort_xml += f"<computed-sort column={quoteattr(dimf.ref)} direction='{direction}' using={quoteattr(meas.ref)} />"
    if manual:
        dimf, members = manual
        buckets = "".join(f"<bucket>{escape(chr(34) + m + chr(34))}</bucket>" for m in members)
        sort_xml += f"<manual-sort column={quoteattr(dimf.ref)} direction='ASC'><dictionary>{buckets}</dictionary></manual-sort>"
    style = "<style />"
    if show_labels or text:
        style = ("<style><style-rule element='mark'><format attr='mark-labels-show' value='true' />"
                 "<format attr='mark-labels-cull' value='true' /></style-rule></style>")
    big = ""
    if text:
        big = ("<style><style-rule element='mark'><format attr='mark-labels-show' value='true' /></style-rule>"
               "<style-rule element='cell'><format attr='font-size' value='26' /><format attr='font-weight' value='bold' />"
               "<format attr='color' value='#2F6DB5' /><format attr='text-align' value='center' /></style-rule></style>")
        style = big
    title_xml = ""
    if title:
        title_xml = (f"<layout-options><title><formatted-text><run fontsize='11' fontcolor='#6B7580'>{escape(title)}</run>"
                     f"</formatted-text></title></layout-options>")
    row_s = " / ".join(r.ref for r in rows) if rows else ""
    col_s = " / ".join(c.ref for c in cols) if cols else ""
    return f"""    <worksheet name={quoteattr(name)}>
      {title_xml}
      <table>
        <view>
          <datasources><datasource caption={quoteattr(DS[ds]['caption'])} name='{DS[ds]['name']}' /></datasources>{"<mapsources><mapsource name='Tableau' /></mapsources>" if mark == "Multipolygon" else ""}
          <datasource-dependencies datasource='{DS[ds]['name']}'>
            {''.join(cols_xml)}
            {''.join(insts)}
          </datasource-dependencies>
          {sort_xml}
          <aggregation value='true' />
        </view>
        {style}
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view><breakdown value='auto' /></view>
            <mark class='{mark}' />
            <encodings>{''.join(enc)}</encodings>
          </pane>
        </panes>
        <rows>{escape(row_s)}</rows>
        <cols>{escape(col_s)}</cols>
      </table>
      <simple-id uuid='{{{str(uuid.uuid4()).upper()}}}' />
    </worksheet>"""


S, C, FC = "sales", "cust", "fc"
sheets = []
# --- Dashboard 1: Executive Overview
KPIS = [("KPI Revenue", "Calculation_1001", "Revenue"), ("KPI Profit", "Calculation_1002", "Profit"),
        ("KPI Margin", "Calculation_1003", "Profit Margin"), ("KPI Orders", "Calculation_1004", "Orders"),
        ("KPI AOV", "Calculation_1005", "Avg Order Value")]
for sname, calc, t in KPIS:
    sheets.append(worksheet(sname, S, "Text", text=usr(S, calc), title=t))
sheets.append(worksheet("Monthly Revenue Trend", S, "Line", rows=[usr(S, "Calculation_1007")],
                        cols=[month(S, "Order Date")], title="Monthly revenue (₹ lakh)"))
sheets.append(worksheet("Revenue by Fiscal Year", S, "Bar", rows=[usr(S, "Calculation_1001")],
                        cols=[dim(S, "Fiscal Year")], color=usr(S, "Calculation_1003"), label=usr(S, "Calculation_1001"),
                        show_labels=True, title="Revenue by fiscal year (colour = margin)"))
sheets.append(worksheet("Sub-Category Revenue & Margin", S, "Bar", rows=[dim(S, "Sub-Category")],
                        cols=[usr(S, "Calculation_1007")], color=usr(S, "Calculation_1003"),
                        sort=(dim(S, "Sub-Category"), ssum(S, "Sales"), "DESC"),
                        title="Revenue by sub-category (colour = profit margin)"))
# --- Dashboard 2: Regional & Profitability
sheets.append(worksheet("State Margin Map", S, "Multipolygon", rows=[F(S, "Latitude (generated)", "none", "qk")],
                        cols=[F(S, "Longitude (generated)", "none", "qk")], color=usr(S, "Calculation_1003"),
                        detail=[dim(S, "State"), dim(S, "Country")], title="Profit margin by state"))
sheets.append(worksheet("Margin by Region", S, "Bar", rows=[dim(S, "Region")], cols=[usr(S, "Calculation_1003")],
                        color=usr(S, "Calculation_1003"), label=usr(S, "Calculation_1003"), show_labels=True,
                        sort=(dim(S, "Region"), usr(S, "Calculation_1003"), "DESC"), title="Profit margin by region"))
sheets.append(worksheet("Loss Rate by Discount Band", S, "Bar", cols=[dim(S, "Discount Band")],
                        rows=[usr(S, "Calculation_1006")], label=usr(S, "Calculation_1006"), show_labels=True,
                        manual=(dim(S, "Discount Band"), ["No Discount", "1-10%", "11-20%", ">20%"]),
                        color=usr(S, "Calculation_1006"), title="% of order lines sold at a loss, by discount band"))
sheets.append(worksheet("Discount vs Margin", S, "Circle", cols=[usr(S, "Calculation_1009")],
                        rows=[usr(S, "Calculation_1003")], color=dim(S, "Region"),
                        detail=[dim(S, "Sub-Category")], size=ssum(S, "Sales"),
                        title="Avg discount vs margin (each dot = sub-category x region)"))
sheets.append(worksheet("Sub-Category Profit", S, "Bar", rows=[dim(S, "Sub-Category")],
                        cols=[usr(S, "Calculation_1008")], color=usrn(S, "Calculation_1010"),
                        sort=(dim(S, "Sub-Category"), ssum(S, "Profit"), "ASC"), title="Profit by sub-category (₹ lakh)"))
# --- Dashboard 3: Customers & Forecast
sheets.append(worksheet("Segment Share", C, "Bar", rows=[dim(C, "Customer Segment (Cluster)")],
                        cols=[usr(C, "Calculation_2001"), usr(C, "Calculation_2002")],
                        color=dim(C, "Customer Segment (Cluster)"), show_labels=True,
                        sort=(dim(C, "Customer Segment (Cluster)"), ssum(C, "Monetary"), "DESC"),
                        title="Share of customers vs share of revenue"))
sheets.append(worksheet("Customer RFM Scatter", C, "Circle", cols=[ssum(C, "Frequency")],
                        rows=[usr(C, "Calculation_2003")], color=dim(C, "Customer Segment (Cluster)"),
                        detail=[dim(C, "Customer ID")], title="Customers: orders vs lifetime revenue (₹ lakh)"))
sheets.append(worksheet("Revenue Forecast", FC, "Line", cols=[month(FC, "Month")],
                        rows=[usr(FC, "Calculation_3001")], color=dim(FC, "Type"),
                        tooltip=[usr(FC, "Calculation_3002"), usr(FC, "Calculation_3003")],
                        title="Monthly revenue: actual vs 12-month Holt-Winters forecast (₹ lakh)"))

# ----------------------------------------------------------------- dashboards
_zid = [100]
def zid():
    _zid[0] += 1
    return _zid[0]

W, H = 1366, 800
def px(v, total):  # pixel -> 100000 units
    return int(round(v / total * 100000))

def zone(sheet, x, y, w, h):
    return (f"<zone h='{px(h, H)}' id='{zid()}' name={quoteattr(sheet)} "
            f"w='{px(w, W)}' x='{px(x, W)}' y='{px(y, H)}' />")

def text_zone(txt, sub, x, y, w, h):
    return (f"<zone h='{px(h, H)}' id='{zid()}' type-v2='text' w='{px(w, W)}' x='{px(x, W)}' y='{px(y, H)}'>"
            f"<formatted-text><run bold='true' fontcolor='#1F2933' fontsize='18'>{escape(txt)}</run>"
            f"<run>&#10;</run><run fontcolor='#6B7580' fontsize='11'>{escape(sub)}</run></formatted-text></zone>")

def dashboard(name, title, sub, zones):
    inner = "\n          ".join([text_zone(title, sub, 0, 0, W, 70)] + zones)
    return f"""    <dashboard name={quoteattr(name)}>
      <style />
      <size maxheight='{H}' maxwidth='{W}' minheight='{H}' minwidth='{W}' sizing-mode='fixed' />
      <zones>
        <zone h='100000' id='{zid()}' type-v2='layout-basic' w='100000' x='0' y='0'>
          {inner}
        </zone>
      </zones>
      <simple-id uuid='{{{str(uuid.uuid4()).upper()}}}' />
    </dashboard>"""

kw = W // 5
d1 = [zone(n, i * kw, 70, kw, 110) for i, (n, _, _) in enumerate(KPIS)]
d1 += [zone("Monthly Revenue Trend", 0, 180, 820, 300), zone("Revenue by Fiscal Year", 820, 180, 546, 300),
       zone("Sub-Category Revenue & Margin", 0, 480, W, 320)]
d2 = [zone("State Margin Map", 0, 70, 460, 400), zone("Margin by Region", 460, 70, 450, 200),
      zone("Loss Rate by Discount Band", 460, 270, 450, 200), zone("Sub-Category Profit", 910, 70, 456, 400),
      zone("Discount vs Margin", 0, 470, W, 330)]
d3 = [zone("Segment Share", 0, 70, 683, 330), zone("Customer RFM Scatter", 683, 70, 683, 330),
      zone("Revenue Forecast", 0, 400, W, 400)]
dashboards = [
    dashboard("Executive Overview", "Retail Performance — Executive Overview",
              "Revenue grew ~15% CAGR to ₹22.5 Cr (FY25-26), but profit margin stayed flat at ~7%.", d1),
    dashboard("Regional & Profitability", "Where do we make and lose money?",
              "East earns 1.6% margin vs 8.4% in South/West. Discounts above ~10% turn most orders loss-making; Tables loses money.", d2),
    dashboard("Customers & Forecast", "Who drives revenue — and what's next?",
              "Champions are 26% of customers but 52% of revenue. Holt-Winters forecast: ₹24.2 Cr next 12 months (backtest MAPE 9.3%).", d3),
]

if ONLY:
    keep = set(ONLY.split(","))
    sheets = [x for x in sheets if any(f"name={quoteattr(k)}>" in x for k in keep)]
if NODASH or ONLY:
    dashboards = []
sheet_names = [unescape(re.search(r"<worksheet name=(['\"])(.*?)\1", x).group(2), {"&quot;": '"'}) for x in sheets]
windows = "\n".join(
    [f"    <window class='dashboard' maximized='true' name={quoteattr(n)} />" for n in
     ["Executive Overview", "Regional & Profitability", "Customers & Forecast"]] +
    [f"    <window class='worksheet' hidden='true' name={quoteattr(n)} />" for n in sheet_names])

CARDS = """<cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge><edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip><strip size='31'><card type='title' /></strip></edge></cards>"""
def sid(): return f"<simple-id uuid='{{{str(uuid.uuid4()).upper()}}}' />"
wins = []
dash_names = [unescape(re.search(r"<dashboard name=(['\"])(.*?)\1", d).group(2), {"&quot;": '"'}) for d in dashboards]
for i, dn in enumerate(dash_names):
    mx = "maximized='true' " if i == 0 else ""
    dxml = dashboards[i]
    zn = [m for m in re.findall(r"<zone h='[0-9]+' id='[0-9]+' name=(?:'|\")(.*?)(?:'|\") w=", dxml)]
    zn = [unescape(z, {"&quot;": '"'}) for z in zn]
    vps = "".join(f"<viewpoint name={quoteattr(n)}><zoom type='entire-view' /></viewpoint>" for n in sorted(set(zn)))
    wins.append(f"    <window class='dashboard' {mx}name={quoteattr(dn)}><viewpoints>{vps}</viewpoints><active id='-1' />{sid()}</window>")
for j, sn in enumerate(sheet_names):
    hid = "hidden='true' " if dashboards else ""
    mx = "maximized='true' " if (not dashboards and j == 0) else ""
    wins.append(f"    <window class='worksheet' {hid}{mx}name={quoteattr(sn)}>{CARDS}{sid()}</window>")
WIN_XML = chr(10).join(wins)
def action(i, cap, dash, src):
    return (f"    <action caption={quoteattr(cap)} name='[Action{i}]'>"
            f"<activation auto-clear='true' type='on-select' />"
            f"<source dashboard={quoteattr(dash)} type='sheet' worksheet={quoteattr(src)} />"
            f"<command command='tsc:tsl-filter'><param name='special-fields' value='all' />"
            f"<param name='target' value={quoteattr(dash)} /></command></action>")
ACTIONS = [] if not dashboards or os.environ.get("NOACT") else [
    action(1, "Filter by region", "Regional & Profitability", "Margin by Region"),
    action(2, "Filter by state", "Regional & Profitability", "State Margin Map"),
    action(3, "Filter by fiscal year", "Executive Overview", "Revenue by Fiscal Year"),
    action(4, "Filter by customer segment", "Customers & Forecast", "Segment Share"),
]
ACTIONS_XML = ("  <actions>\n" + chr(10).join(ACTIONS) + "\n  </actions>\n") if ACTIONS else ""
DASH_XML = ("  <dashboards>\n" + chr(10).join(dashboards) + "\n  </dashboards>\n") if dashboards else ""
xml = f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2025.2.0 (20252.25.0514.2217)' source-platform='mac' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
    <AnimationOnByDefault />
    <IntuitiveSorting />
    <IntuitiveSorting_SP2 />
    <MapboxVectorStylesAndLayers />
    <MarkAnimation />
    <ObjectModelEncapsulateLegacy />
    <ObjectModelExtractV2 />
    <ObjectModelTableType />
    <SchemaViewerObjectModel />
    <SheetIdentifierTracking />
    <SortTagCleanup />
    <_.fcp.VConnDownstreamExtractsWithWarnings.true...VConnDownstreamExtractsWithWarnings />
    <WindowsPersistSimpleIdentifiers />
  </document-format-change-manifest>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <datasources>
{datasource_xml('sales')}
{datasource_xml('cust')}
{datasource_xml('fc')}
  </datasources>
{ACTIONS_XML}  <worksheets>
{chr(10).join(sheets)}
  </worksheets>
{DASH_XML}  <windows source-height='30'>
{WIN_XML}
  </windows>
</workbook>
"""
OUT.write_text(xml, encoding="utf-8")
print("wrote", OUT, len(xml), "bytes")
