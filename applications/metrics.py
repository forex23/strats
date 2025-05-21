"""
metrics.py  –  shared reporting helper
Takes a trade-log + equity curve and returns the canonical JSON bundle
used by every back-test and live-sim result.
"""

from __future__ import annotations
import base64, io, json
from typing import List, Dict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ───────────────────────── internal ──────────────────────────
def _png_from_equity(eq: List[dict]) -> str | None:
    if not eq:
        return None
    ts  = [p["ts"] for p in eq]
    bal = [p["equity"] for p in eq]

    fig, ax = plt.subplots()
    ax.plot(ts, bal, linewidth=1.2)
    ax.set_title("Equity curve")
    ax.set_xlabel("Time"); ax.set_ylabel("Equity (pips)")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


# ───────────────────────── public API ────────────────────────
def generate_backtest_output(trade_log: pd.DataFrame,
                             equity_curve: List[dict],
                             params: dict,
                             engine_file: str) -> Dict:
    """
    Build the result-bundle consumed by dashboards and audit tools.
    `trade_log` must include columns:
        ['pips','entry_time','exit_time','side','reason']
    """
    pnl = trade_log["pips"]
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]

    # ---------- basic hit counts ----------
    tot_hits   = len(trade_log)
    stop_hits  = (trade_log.reason == "stop").sum()
    time_hits  = (trade_log.reason == "time").sum()
    mean_hits  = (trade_log.reason == "mean").sum()

    # ---------- streak calc ----------
    signs = np.sign(pnl)
    win_streak = loss_streak = cur = 0
    for s in signs:
        if   s > 0: cur =  max(1, cur + 1)
        elif s < 0: cur = -max(1, abs(cur) + 1)
        else:       cur = 0
        win_streak  = max(win_streak,  cur)
        loss_streak = min(loss_streak, cur)
    loss_streak = abs(loss_streak)

    # ---------- simultaneous trades ----------
    sim = trade_log.entry_time.dt.floor("T").value_counts()
    gt1 = (sim > 1).sum()
    max_sim = sim.max() if not sim.empty else 0

    png_b64 = _png_from_equity(equity_curve)

    out = {
        "engine"        : engine_file,
        "params"        : params,
        "trades"        : int(tot_hits),
        "win_%"         : round(float((pnl > 0).mean() * 100), 2),
        "expect_pips"   : round(float(pnl.mean()), 2),
        "total_pips"    : round(float(pnl.sum()), 2),
        "av_win_pips"   : round(float(wins.mean()), 2) if not wins.empty else None,
        "av_loss_pips"  : round(float(losses.mean()), 2) if not losses.empty else None,
        "profit_factor" : round(float(wins.sum() / -losses.sum()), 2)
                           if not losses.empty else None,
        "sharpe"        : round(float(pnl.mean() / pnl.std()), 2)
                           if pnl.std() > 0 else None,
        "max_dd_pips"   : round(float(
                            (pd.Series([e["equity"] for e in equity_curve]).cummax()
                             - pd.Series([e["equity"] for e in equity_curve])).max()), 2)
                           if equity_curve else None,
        "#_stop_hits"   : int(stop_hits),
        "stop_hit_%"    : round(stop_hits / tot_hits * 100, 1) if tot_hits else None,
        "#_time_hits"   : int(time_hits),
        "time_hit_%"    : round(time_hits / tot_hits * 100, 1) if tot_hits else None,
        "#_mean_hits"   : int(mean_hits),
        "mean_hit_%"    : round(mean_hits / tot_hits * 100, 1) if tot_hits else None,
        "avg_trade_len_min":
            round(float((trade_log.exit_time - trade_log.entry_time)
                        .dt.total_seconds().mean() / 60), 2) if not trade_log.empty else None,
        "#_sim_trades_gt1": int(gt1),
        "max_sim_trades" : int(max_sim),
        "win_streak_max" : int(win_streak),
        "loss_streak_max": int(loss_streak),
        "equity_curve_png": png_b64,
        "trade_log"       : trade_log.to_dict(orient="records"),
    }
    return out
