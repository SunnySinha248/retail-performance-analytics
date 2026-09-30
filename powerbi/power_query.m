// =====================================================================
// Power Query (M) — paste each query via Home → Transform data →
// New Source → Blank Query → Advanced Editor.
// First create a text parameter named DataFolder
// (Manage Parameters → New → Type: Text) pointing to your local
// data/processed/ folder, WITH a trailing backslash, e.g.
//   C:\Users\Sunny\retail-performance-analytics\data\processed\
// =====================================================================


// ---------------------------------------------------------------------
// Query: Sales   (fact table, one row per order line)
// ---------------------------------------------------------------------
let
    Source   = Csv.Document(File.Contents(DataFolder & "sales_enriched.csv"),
                 [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
        {"Order ID", type text}, {"Order Date", type date}, {"Ship Date", type date},
        {"Ship Mode", type text}, {"Channel", type text},
        {"Customer ID", type text}, {"Customer Name", type text}, {"Segment", type text},
        {"Region", type text}, {"State", type text}, {"City", type text}, {"Country", type text},
        {"Category", type text}, {"Sub-Category", type text},
        {"Unit Price", type number}, {"Quantity", Int64.Type}, {"Discount", type number},
        {"Sales", type number}, {"Profit", type number},
        {"Fiscal Year", type text}, {"Order Month", type date},
        {"Profit Margin", type number}, {"Discount Band", type text},
        {"Ship Lag Days", Int64.Type}, {"Is Loss", Int64.Type},
        {"Customer Segment (Cluster)", type text}, {"RFM Score", Int64.Type}
    }, "en-US"),
    // Sort key so Discount Band shows in logical order, not alphabetical
    BandSort = Table.AddColumn(Typed, "Discount Band Sort", each
        if [Discount Band] = "No Discount" then 1
        else if [Discount Band] = "1-10%" then 2
        else if [Discount Band] = "11-20%" then 3
        else 4, Int64.Type),
    // Map-friendly state name for Power BI's Bing map
    StateGeo = Table.AddColumn(BandSort, "State (Map)", each [State] & ", India", type text)
in
    StateGeo


// ---------------------------------------------------------------------
// Query: Customers   (dimension — RFM + K-Means cluster per customer)
// ---------------------------------------------------------------------
let
    Source   = Csv.Document(File.Contents(DataFolder & "customer_segments.csv"),
                 [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
        {"Customer ID", type text}, {"Recency", Int64.Type}, {"Frequency", Int64.Type},
        {"Monetary", type number}, {"Profit", type number},
        {"R_Score", Int64.Type}, {"F_Score", Int64.Type}, {"M_Score", Int64.Type},
        {"RFM Score", Int64.Type}, {"Cluster", Int64.Type},
        {"Customer Segment (Cluster)", type text}, {"Customer Name", type text},
        {"Segment", type text}, {"Region", type text}, {"State", type text}, {"City", type text}
    }, "en-US"),
    Renamed  = Table.RenameColumns(Typed, {
        {"Profit", "Lifetime Profit"}, {"Monetary", "Lifetime Revenue"},
        {"Segment", "Customer Type"}, {"Region", "Home Region"},
        {"State", "Home State"}, {"City", "Home City"}
    }),
    SegSort  = Table.AddColumn(Renamed, "Cluster Sort", each
        if [#"Customer Segment (Cluster)"] = "Champions" then 1
        else if [#"Customer Segment (Cluster)"] = "Loyal Regulars" then 2
        else if [#"Customer Segment (Cluster)"] = "Occasional Buyers" then 3
        else 4, Int64.Type)
in
    SegSort


// ---------------------------------------------------------------------
// Query: Forecast   (monthly actuals + 12-month Holt-Winters forecast)
// ---------------------------------------------------------------------
let
    Source   = Csv.Document(File.Contents(DataFolder & "revenue_forecast.csv"),
                 [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Blanks   = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue,
                 {"Fitted", "Lower 95%", "Upper 95%"}),
    Typed    = Table.TransformColumnTypes(Blanks, {
        {"Month", type date}, {"Revenue", type number}, {"Type", type text},
        {"Fitted", type number}, {"Lower 95%", type number}, {"Upper 95%", type number}
    }, "en-US")
in
    Typed
