import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

import scraper_screener as screener
import scraper_trendlyne as trendlyne

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'history.db'
MKTCAP_CSV = BASE_DIR / 'data' / 'market_caps.csv'

STATIC_SECTORS = {
    'KPITTECH': 'IT',
    'BHEL': 'Infrastructure',
    'HDFCBANK': 'Banking',
    'TATASTEEL': 'Metals',
    'COALINDIA': 'Mining',
    'INFY': 'IT',
    'WIPRO': 'IT',
    'RELIANCE': 'Energy',
    'TCS': 'IT',
    'ICICIBANK': 'Banking',
    'SBIN': 'Banking',
    'SUNPHARMA': 'Pharma',
    'BAJFINANCE': 'Finance',
    'TITAN': 'Consumer',
    'AXISBANK': 'Banking',
    'NTPC': 'Power',
    'MARUTI': 'Auto',
    'ONGC': 'Energy',
}


def _load_market_caps():
    if not MKTCAP_CSV.exists():
        logging.warning("market_caps.csv not found — skipping static market cap filter")
        return None
    try:
        df = pd.read_csv(MKTCAP_CSV)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except Exception as e:
        logging.warning(f"Failed to load market_caps.csv: {e}")
        return None


def _market_cap_filter(row, mktcap_df, static_large_cap):
    """Return True if symbol passes market cap filter (>1000 Cr)."""
    shares = row.get('shares_outstanding')
    if shares and shares > 0:
        cap_cr = (float(row['close']) * shares) / 1_00_00_000
        return cap_cr > 1000, 'dynamic'
    # Fall back to static CSV — only reject if symbol is explicitly listed AND below threshold
    if static_large_cap is not None and row['symbol'] in static_large_cap:
        return True, 'static'
    # Symbol not in CSV: our download universe is already Nifty 500, so pass through
    return True, 'universe'


def _apply_technical_filters(df, mktcap_df):
    required = ['close', 'ema20', 'volume_ratio', 'delivery_pct', 'high40', 'rsi14']
    for col in required:
        if col not in df.columns:
            logging.error(f"Missing column: {col}")
            return pd.DataFrame()

    static_large_cap = None
    if mktcap_df is not None and not mktcap_df.empty:
        static_large_cap = set(mktcap_df[mktcap_df['market_cap_cr'] > 1000]['symbol'])

    # delivery_pct filter only applied when data is available (NSE bhavdata).
    # yfinance doesn't provide delivery data so delivery_pct == 0.0 for all rows —
    # in that case we skip the filter entirely.
    has_delivery = df['delivery_pct'].gt(0).any()

    mask = (
        df['close'].notna() &
        df['ema20'].notna() &
        df['rsi14'].notna() &
        df['volume_ratio'].notna() &
        df['high40'].notna() &
        (df['close'] > df['ema20']) &
        (df['volume_ratio'] > 1.5) &
        (df['close'] >= df['high40'] * 0.97) &
        (df['rsi14'] >= 50) &
        (df['rsi14'] <= 70) &
        (df['close'] >= 50) &
        (df['close'] <= 10000)
    )
    if has_delivery:
        mask = mask & (df['delivery_pct'] > 50)
    filtered = df[mask].copy()

    # Market cap filter using dynamic shares_outstanding where available
    if 'shares_outstanding' not in filtered.columns:
        filtered['shares_outstanding'] = None

    if filtered.empty:
        logging.info(f"Step 1 (technical): {len(df)} → 0 symbols")
        return filtered

    filtered['_cap_ok'] = filtered.apply(
        lambda row: _market_cap_filter(row, mktcap_df, static_large_cap)[0], axis=1
    )
    filtered['market_cap_source'] = filtered.apply(
        lambda row: _market_cap_filter(row, mktcap_df, static_large_cap)[1], axis=1
    )
    filtered = filtered[filtered['_cap_ok']].drop(columns=['_cap_ok'])

    logging.info(f"Step 1 (technical): {len(df)} → {len(filtered)} symbols")
    return filtered


def _apply_fundamental_filters(df, fund_data):
    passing = []
    for _, row in df.iterrows():
        sym = row['symbol']
        fd = fund_data.get(sym)
        if fd is None:
            # No scrape data — pass through so scraper outages don't kill all candidates
            passing.append(row)
            continue
        if (
            fd.get('profit_growth', 0) > 0 and
            fd.get('debt_equity', 99) < 1.5 and
            fd.get('promoter_holding', 0) > 40 and
            fd.get('quarterly_sales_growth_positive', False)
        ):
            passing.append(row)
    result = pd.DataFrame(passing)
    logging.info(f"Step 2 (fundamental): {len(df)} → {len(result)} symbols")
    return result


def _apply_analyst_filters(df, analyst_data):
    passing = []
    for _, row in df.iterrows():
        sym = row['symbol']
        ad = analyst_data.get(sym)
        if ad is None:
            # No scrape data — pass through
            passing.append(row)
            continue
        if (
            ad.get('analyst_count', 0) >= 3 and
            ad.get('upside_to_target', 0) > 10
        ):
            passing.append(row)
    result = pd.DataFrame(passing)
    logging.info(f"Step 3 (analyst): {len(df)} → {len(result)} symbols")
    return result


def _compute_score(row, analyst_upside, promoter_holding):
    vr = min(20.0, max(0.0, (row['volume_ratio'] - 1.5) / 1.5 * 20))
    # delivery_pct==0 means no data (yfinance) — use neutral 10 pts instead of penalising
    if row['delivery_pct'] > 0:
        dp = min(20.0, max(0.0, (row['delivery_pct'] - 50) / 30 * 20))
    else:
        dp = 10.0
    rsi_norm = max(0.0, 1 - abs(row['rsi14'] - 60) / 10)
    rsi_score = rsi_norm * 20
    au = min(20.0, max(0.0, (analyst_upside - 10) / 20 * 20))
    ph = min(20.0, max(0.0, (promoter_holding - 40) / 35 * 20))
    return int(round(vr + dp + rsi_score + au + ph))


def _sector_warning(candidates):
    from collections import Counter
    sectors = [c.get('sector', 'Equity') for c in candidates]
    counts = Counter(sectors)
    for sector, n in counts.most_common(1):
        if n >= 3:
            return True, f"{sector} appears {n} times in today's candidates"
    return False, ''


async def _fetch_fundamentals(symbols, conn):
    results = {}
    today = datetime.now().strftime('%Y-%m-%d')
    for sym in symbols:
        try:
            data = await screener.scrape(sym, conn=conn, today=today)
            if data:
                results[sym] = data
        except Exception as e:
            logging.warning(f"Screener scrape failed for {sym}: {e}")
        await asyncio.sleep(2)
    return results


async def _fetch_analyst(symbols, conn):
    results = {}
    today = datetime.now().strftime('%Y-%m-%d')
    for sym in symbols:
        try:
            data = await trendlyne.scrape(sym, conn=conn, today=today)
            if data:
                results[sym] = data
        except Exception as e:
            logging.warning(f"Trendlyne scrape failed for {sym}: {e}")
        await asyncio.sleep(2)
    return results


def run(today_df, breadth_pct, conn):
    if today_df.empty:
        logging.warning("No indicator data — skipping scan")
        return [], 0, 0

    mktcap_df = _load_market_caps()
    step1 = _apply_technical_filters(today_df, mktcap_df)
    total_scanned = len(today_df)

    if step1.empty:
        logging.info("No symbols passed technical filter")
        return [], total_scanned, 0

    symbols_step1 = step1['symbol'].tolist()
    fund_data = asyncio.run(_fetch_fundamentals(symbols_step1, conn))
    step2 = _apply_fundamental_filters(step1, fund_data)

    if step2.empty:
        logging.info("No symbols passed fundamental filter")
        return [], total_scanned, len(step1)

    symbols_step2 = step2['symbol'].tolist()
    analyst_data = asyncio.run(_fetch_analyst(symbols_step2, conn))
    step3 = _apply_analyst_filters(step2, analyst_data)

    if step3.empty:
        logging.info("No symbols passed analyst filter")
        return [], total_scanned, len(step1)

    candidates = []
    for _, row in step3.iterrows():
        sym = row['symbol']
        fd = fund_data.get(sym, {})
        ad = analyst_data.get(sym, {})
        analyst_upside = ad.get('upside_to_target', 10)
        promoter_holding = fd.get('promoter_holding', 40)
        score = _compute_score(row, analyst_upside, promoter_holding)

        sparkline = row.get('sparkline', [])
        if hasattr(sparkline, 'tolist'):
            sparkline = sparkline.tolist()

        atr14 = float(row.get('atr14') or row['close'] * 0.02)
        close = float(row['close'])

        candidates.append({
            'symbol': sym,
            'sector': STATIC_SECTORS.get(sym, row.get('sector', 'Equity')),
            'score': score,
            'rsi': round(float(row['rsi14']), 1),
            'volume_ratio': round(float(row['volume_ratio']), 2),
            'delivery_pct': round(float(row['delivery_pct']), 1),
            'ema20': round(float(row['ema20']), 2),
            'high40': round(float(row['high40']), 2),
            'close': round(close, 2),
            'atr14': round(atr14, 2),
            'analyst_consensus': ad.get('consensus', 'Buy'),
            'analyst_upside': round(analyst_upside, 1),
            'profit_growth': round(fd.get('profit_growth', 0), 1),
            'debt_equity': round(fd.get('debt_equity', 0), 2),
            'promoter_holding': round(promoter_holding, 1),
            'sparkline': sparkline,
            'stop_price': round(close - 1.5 * atr14, 2),
            'target_price': round(close + 3.0 * atr14, 2),
            'cached_data': ad.get('cached', False) or fd.get('cached', False),
            'cache_age_days': max(
                ad.get('cache_age_days', 0) or 0,
                fd.get('cache_age_days', 0) or 0,
            ) or None,
            'shares_outstanding': fd.get('shares_outstanding'),
            'market_cap_source': row.get('market_cap_source', 'dynamic'),
        })

    candidates.sort(key=lambda x: x['score'], reverse=True)
    top5 = candidates[:5]

    sw, sw_msg = _sector_warning(top5)
    logging.info(f"Final candidates: {[c['symbol'] for c in top5]}")
    if sw:
        logging.warning(f"Sector concentration: {sw_msg}")

    return top5, total_scanned, len(step1), sw, sw_msg


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    import indicators
    conn = sqlite3.connect(DB_PATH)
    df, breadth = indicators.compute_indicators(conn)
    result = run(df, breadth, conn)
    conn.close()
    print(result)
