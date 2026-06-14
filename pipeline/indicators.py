import sqlite3
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'history.db'


def _compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def _compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))


def compute_indicators(conn):
    cutoff = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
    df = pd.read_sql_query(
        """SELECT symbol, date, open, high, low, close, volume, delivery_pct
           FROM ohlcv_history WHERE date >= ? ORDER BY symbol, date""",
        conn, params=(cutoff,)
    )
    if df.empty:
        return pd.DataFrame(), 0.0

    results = []
    for symbol, grp in df.groupby('symbol'):
        grp = grp.sort_values('date').reset_index(drop=True)
        if len(grp) < 20:
            continue
        grp['ema20'] = _compute_ema(grp['close'], 20)
        grp['rsi14'] = _compute_rsi(grp['close'], 14)
        grp['avg_vol20'] = grp['volume'].rolling(20).mean()
        grp['high40'] = grp['high'].rolling(40).max()
        grp['volume_ratio'] = grp['volume'] / grp['avg_vol20'].replace(0, float('nan'))
        last = grp.iloc[-1].copy()
        last['symbol'] = symbol
        # Keep last 7 closes for sparkline
        last['sparkline'] = grp['close'].iloc[-7:].tolist()
        results.append(last)

    if not results:
        return pd.DataFrame(), 0.0

    today_df = pd.DataFrame(results)

    # Breadth: % of symbols within 5% of their EMA20
    within = (
        (today_df['close'] >= today_df['ema20'] * 0.95) &
        (today_df['close'] <= today_df['ema20'] * 1.05)
    )
    breadth_pct = float(within.mean() * 100)

    return today_df, breadth_pct


def run(conn=None):
    close_conn = conn is None
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
    try:
        return compute_indicators(conn)
    except Exception as e:
        logging.error(f"indicators.run() failed: {e}")
        return pd.DataFrame(), 0.0
    finally:
        if close_conn:
            conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    df, breadth = run()
    if not df.empty:
        print(f"Indicators computed for {len(df)} symbols  |  Breadth: {breadth:.1f}%")
        print(df[['symbol', 'close', 'ema20', 'rsi14', 'volume_ratio']].head(10).to_string())
    else:
        print("No data — run seed_demo.py first")
