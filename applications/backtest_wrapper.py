"""
backtest_wrapper.py – single-run orchestrator
---------------------------------------------
CLI example:
    python applications/backtest_wrapper.py \
           --engine 001/v6.02 --from 2025-03-01 --to 2025-03-31 \
           --tf M1 --params base_z=2.1,step_z=0.3

Writes JSON to:
    <ENGINE_ROOT>/<engine>/results/<UTC-timestamp>.json
Echoes one line (parsed by /kick_bt):
    JSON: <engine>/results/<file>.json
"""

# ── make project root importable ────────────────────────────────────
import sys, pathlib, argparse, json, datetime
ROOT = pathlib.Path(__file__).resolve().parent.parent   # /home/tradeops/strats
sys.path.insert(0, str(ROOT))

# ── project / third-party imports ───────────────────────────────────
from applications.metrics import generate_backtest_output
import importlib.machinery, importlib.util
import calendar, datetime as dt, psycopg2, pandas as pd
from pathlib import Path

# ── paths ───────────────────────────────────────────────────────────
ENGINE_ROOT = ROOT
DATA_ROOT   = ROOT / "data"            # CSV cache lives here

# ── Postgres info (fallback when CSV not cached) ────────────────────
PG_DSN    = "dbname=forex_data user=tradeops"
TABLE_MAP = {"M1": "forex_rates_1m", "tick": "forex_quotes_raw"}

# ── helper: make timestamp column tz-aware UTC ──────────────────────
def _ensure_utc(df: pd.DataFrame) -> pd.DataFrame:
    if df["timestamp_utc"].dt.tz is None:
        df["timestamp_utc"] = df["timestamp_utc"].dt.tz_localize("UTC")
    return df

# ── CSV-or-DB loader, glues months together ─────────────────────────
def load_bars(symbol: str, start: str, end: str,
              tf: str = "M1", cache_csv: bool = True) -> pd.DataFrame:
    start = pd.to_datetime(start, utc=True)
    end   = pd.to_datetime(end,   utc=True)
    frames = []
    for per in pd.period_range(start, end, freq="M"):
        ym, yr, mo = per.strftime("%Y-%m"), per.year, per.month
        # 1) CSV cache?
        fp_csv = DATA_ROOT / symbol / tf / f"{ym}.csv"
        if fp_csv.is_file():
            df = _ensure_utc(pd.read_csv(fp_csv, parse_dates=["timestamp_utc"]))
        else:
            # 2) fallback to Postgres
            first = dt.datetime(yr, mo, 1, tzinfo=dt.timezone.utc)
            last  = dt.datetime(yr, mo, calendar.monthrange(yr, mo)[1], 23, 59,
                                tzinfo=dt.timezone.utc)
            tbl   = TABLE_MAP.get(tf, f"forex_rates_{tf.lower()}")
            cols  = ("timestamp_utc, open, high, low, close"
                     if tf == "M1" else
                     "timestamp_utc, bid_price, ask_price")
            sql   = f"""
                SELECT {cols}
                FROM   {tbl}
                WHERE  symbol = %s
                  AND  timestamp_utc BETWEEN %s AND %s
                ORDER  BY timestamp_utc
            """
            with psycopg2.connect(PG_DSN) as con:
                df = _ensure_utc(pd.read_sql(sql, con, params=[symbol, first, last]))
            if cache_csv:
                fp_csv.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(fp_csv, index=False,
                          date_format="%Y-%m-%dT%H:%M:%SZ")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df[(df.timestamp_utc >= start) & (df.timestamp_utc <= end)]
    return df.set_index("timestamp_utc")

# ── dynamic import of engine.py (handles “001/v6.02”) ───────────────
def load_engine(engine_path: str):
    eng_file = (ENGINE_ROOT / engine_path / "engine.py").resolve()
    if not eng_file.is_file():
        raise FileNotFoundError(f"Engine file not found: {eng_file}")
    loader = importlib.machinery.SourceFileLoader("engine_mod", str(eng_file))
    spec   = importlib.util.spec_from_loader(loader.name, loader)
    eng_mod= importlib.util.module_from_spec(spec)
    loader.exec_module(eng_mod)
    return eng_mod

# ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, help="e.g. 001/v6.02")
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to",   dest="end",   required=True)
    ap.add_argument("--symbol", default="EURGBP")
    ap.add_argument("--tf",     choices=["M1", "tick"], default="M1")
    ap.add_argument("--params", type=str,
                    help='JSON blob or key1=val1,key2=val2 overrides')
    args = ap.parse_args()

    # 1) load engine & bars
    engine = load_engine(args.engine)
    bars   = load_bars(args.symbol, args.start, args.end, tf=args.tf)

    # 2) merge CFG + CLI overrides
    overrides = {}
    if args.params:
        if args.params.strip().startswith("{"):
            overrides = json.loads(args.params)
        else:
            kv = [s.split("=", 1) for s in args.params.split(",")]
            overrides = {k: (float(v) if "." in v else int(v)) for k, v in kv}
    cfg = {**getattr(engine, "CFG", {}), **overrides}

    # 3) run back-test
    trade_log, equity = engine.run_backtest(bars, cfg)

    # 4) build pretty JSON result bundle
    results = generate_backtest_output(
                 trade_log, equity, cfg, engine_file=args.engine)

    res_dir  = ENGINE_ROOT / args.engine / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    stamp    = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    out_path = res_dir / f"{stamp}.txt"
    out_path.write_text(json.dumps(results, indent=2, default=str))

    # echo path for /kick_bt
    print("JSON:", out_path.relative_to(ENGINE_ROOT))
    return 0

# ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.exit(main())
