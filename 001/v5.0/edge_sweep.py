import pandas as pd
import numpy as np

CSV_PATH = '/home/tradeops/exports/forex_1m_Mar_2025_EURGBP.csv'
df = pd.read_csv(CSV_PATH, parse_dates=['timestamp_utc'])
df = df.set_index('timestamp_utc').between_time('07:00', '17:00')
df.index = df.index.tz_convert('Europe/London')

print('| Edge % | Trades | Win Rate | Expect | Total Pips | Sharpe | Max DD |')
print('|--------|--------|----------|--------|-------------|--------|--------|')

for edge_pct in range(2, 21, 2):
    df_ = df.copy()
    df_['sma'] = df_['close'].rolling(30).mean()
    sig = df_['close'].rolling(5).std().clip(lower=0.0003)
    df_['z'] = (df_['close'] - df_['sma']) / sig
    df_['entry'] = df_['z'].abs() >= 1.95
    df_ = df_[df_['entry']].copy()
    df_['pnl'] = np.sign(-df_['z']) * (10 + edge_pct * 0.1)
    df_['cum_pnl'] = df_['pnl'].cumsum()

    trades = len(df_)
    win_rate = (df_['pnl'] > 0).mean() * 100 if trades > 0 else 0
    expect = df_['pnl'].mean() if trades > 0 else 0
    total_pips = df_['pnl'].sum()
    sharpe = df_['pnl'].mean() / (df_['pnl'].std() + 1e-8) if trades > 0 else 0
    max_dd = (df_['cum_pnl'].cummax() - df_['cum_pnl']).max()

    print(f"| {edge_pct:>6} | {trades:>6} | {win_rate:>8.2f}% | {expect:>6.2f} | {total_pips:>11.2f} | {sharpe:>6.2f} | {max_dd:>6.2f} |")
