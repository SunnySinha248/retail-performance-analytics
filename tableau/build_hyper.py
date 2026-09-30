"""
build_hyper.py — builds Tableau .hyper extracts for the three CSVs and packages
tableau/Retail_Performance_Analytics.twbx (twb + extracts).
Run after build_twb.py.
"""
import sys, zipfile, datetime
from pathlib import Path
import pandas as pd
from tableauhyperapi import (HyperProcess, Telemetry, Connection, CreateMode, TableDefinition,
                             SqlType, TableName, Inserter, NOT_NULLABLE, NULLABLE)

sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
HY = ROOT / "tableau" / "extracts"
HY.mkdir(exist_ok=True)

SQL = {"string": SqlType.text(), "integer": SqlType.big_int(), "real": SqlType.double(), "date": SqlType.date()}


def build(csv, cols, out):
    df = pd.read_csv(PROC / csv)
    table = TableDefinition(TableName("Extract", "Extract"),
                            [TableDefinition.Column(n, SQL[t], NULLABLE) for n, t in cols])
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"default_database_version": "2"}) as hp:
        with Connection(hp.endpoint, out, CreateMode.CREATE_AND_REPLACE) as con:
            con.catalog.create_schema_if_not_exists("Extract")
            con.catalog.create_table(table)
            rows = []
            for rec in df[[c for c, _ in cols]].itertuples(index=False):
                r = []
                for v, (n, t) in zip(rec, cols):
                    if pd.isna(v):
                        r.append(None)
                    elif t == "date":
                        r.append(datetime.date.fromisoformat(str(v)[:10]))
                    elif t == "integer":
                        r.append(int(v))
                    elif t == "real":
                        r.append(float(v))
                    else:
                        r.append(str(v))
                rows.append(r)
            with Inserter(con, table) as ins:
                ins.add_rows(rows)
                ins.execute()
    print("built", out, len(df))


if __name__ == "__main__":
    twb_arg = sys.argv[1] if len(sys.argv) > 1 else None
    sys.argv = [sys.argv[0]]
    import os; os.environ["TWB_OUT"] = "/tmp/_scratch.twb"
    import build_twb as B
    for key, d in B.DS.items():
        build(d["file"], d["cols"], HY / (key + ".hyper"))
    twb = Path(twb_arg) if twb_arg else ROOT / "tableau" / "Retail_Performance_Analytics.twb"
    twbx = twb.with_suffix(".twbx")
    with zipfile.ZipFile(twbx, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(twb, twb.name)
        for key in B.DS:
            z.write(HY / (key + ".hyper"), f"Data/Extracts/{key}.hyper")
    print("packaged", twbx)
