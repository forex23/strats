#!/usr/bin/env python3
"""
Export one month from Postgres to CSV, any TF present in the DB.

Examples
--------
# EURGBP minute bars for March 2025
python export_month_csv.py EURGBP 2025-03 --tf M1

# tick quotes for EURUSD March 2025
python export_month_csv.py EURUSD 2025-03 --tf tick
"""
import argparse, calendar, datetime as dt, pathlib, sys, psycopg2, pandas as pd

PG_DSN     = "dbname=forex_data user=tradeops"      # adjust if needed
DATA_ROOT  = pathlib.Path("/home/tradeops/strats/data").expanduser()
TABLE_MAP  = {"M1": "forex_rates_1m", "tick": "forex_quotes_raw"}  # add more TFs → table names here

def date_bounds(year:int, month:int):
    lo = dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)
    hi = dt.datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, tzinfo=dt.timezone.utc)
    return lo, hi

def fetch(symbol, tf, month):
    y, m = [int(x) for x in month.split("-")]
    lo, hi = date_bounds(y, m)
    tbl = TABLE_MAP.get(tf, f"forex_rates_{tf.lower()}")  # fallback pattern
    cols = "timestamp_utc, open, high, low, close" if tf == "M1" else "timestamp_utc, bid_price, ask_price"
    sql  = f"""
        SELECT {cols}
        FROM   {tbl}
        WHERE  symbol = %s
          AND  timestamp_utc BETWEEN %s AND %s
        ORDER  BY timestamp_utc
    """
    with psycopg2.connect(PG_DSN) as con:
        return pd.read_sql(sql, con, params=[symbol, lo, hi])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("month", help="YYYY-MM")
    ap.add_argument("--tf", default="M1", choices=list(TABLE_MAP))
    args = ap.parse_args()

    df = fetch(args.symbol, args.tf, args.month)
    if df.empty:
        sys.exit(f"⚠️  no rows returned for {args.symbol} {args.month} ({args.tf})")

    out_dir = DATA_ROOT / args.symbol / args.tf
    out_dir.mkdir(parents=True, exist_ok=True)
    out_fp  = out_dir / f"{args.month}.csv"
    df.to_csv(out_fp, index=False)
    print(f"✅ {len(df):,} rows → {out_fp}")

if __name__ == "__main__":
    main()
