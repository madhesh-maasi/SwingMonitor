"""Download OHLCV from Yahoo Finance for NSE universe + Nifty 50 index."""
import sqlite3
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / 'data' / 'history.db'
LOG_DIR  = Path(__file__).parent / 'logs'

# Nifty 50 + Next 50 + selected Nifty Midcap 150
# Add or remove symbols here to control the scan universe
NSE_SYMBOLS = [
    # ── Nifty 50 ──────────────────────────────────────────────────
    'ADANIENT','ADANIPORTS','APOLLOHOSP','ASIANPAINT','AXISBANK',
    'BAJAJ-AUTO','BAJFINANCE','BAJAJFINSV','BEL','BPCL',
    'BHARTIARTL','BRITANNIA','CIPLA','COALINDIA','DRREDDY',
    'EICHERMOT','GRASIM','HCLTECH','HDFCBANK','HDFCLIFE',
    'HEROMOTOCO','HINDALCO','HINDUNILVR','ICICIBANK','ITC',
    'INDUSINDBK','INFY','JSWSTEEL','KOTAKBANK','LT',
    'M&M','MARUTI','NESTLEIND','NTPC','ONGC',
    'POWERGRID','RELIANCE','SBILIFE','SHRIRAMFIN','SBIN',
    'SUNPHARMA','TCS','TATACONSUM','TATAMOTORS','TATASTEEL',
    'TECHM','TITAN','TRENT','ULTRACEMCO','WIPRO',
    # ── Nifty Next 50 ─────────────────────────────────────────────
    'ABB','AMBUJACEM','DMART','BANKBARODA','BERGEPAINT','BHEL',
    'BOSCHLTD','CHOLAFIN','COLPAL','DLF','DABUR',
    'DIVISLAB','GAIL','GODREJCP','GODREJPROP','HAL',
    'HAVELLS','ICICIGI','ICICIPRULI','IOC','IRCTC',
    'INDIGO','JINDALSTEL','JIOFIN','LTIM','LICI',
    'MARICO','MUTHOOTFIN','NHPC','NMDC','NAUKRI',
    'PIIND','PFC','PGHH','RECLTD','SBICARD',
    'SRF','SIEMENS','TATAPOWER','TORNTPHARM',
    'TVSMOTOR','VBL','VEDL','ZOMATO','ZYDUSLIFE',
    # ── Nifty Midcap 150 (selected) ───────────────────────────────
    'ABCAPITAL','ALKEM','ASHOKLEY','ASTRAL','AUROPHARMA',
    'BALKRISIND','BANDHANBNK','BATAINDIA','CANBK',
    'COFORGE','CROMPTON','CONCOR','CUMMINSIND','DEEPAKNTR',
    'FEDERALBNK','GMRINFRA','GLENMARK','INDHOTEL',
    'INDUSTOWER','IRFC','KAYNES','KPITTECH','LALPATHLAB',
    'LAURUSLABS','LUPIN','MFSL','MAXHEALTH','METROPOLIS',
    'MPHASIS','MRF','NYKAA','OBEROIRLTY','OFSS',
    'PAGEIND','PERSISTENT','PETRONET','PNB','POLYCAB',
    'PRESTIGE','RBLBANK','SOLARINDS','SUNDARMFIN','SUNTV',
    'SUPREMEIND','TATACHEM','TATAELXSI','TORNTPOWER','TRIDENT',
    'UNIONBANK','VOLTAS','YESBANK',
]

NIFTY_INDEX = '^NSEI'


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{date.today().isoformat()}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ]
    )


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ohlcv_history (
            symbol TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            delivery_qty INTEGER,
            delivery_pct REAL,
            PRIMARY KEY (symbol, date)
        );
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            entry_date TEXT,
            entry_price REAL,
            target_price REAL,
            stop_price REAL,
            status TEXT DEFAULT 'open',
            exit_date TEXT,
            exit_price REAL,
            pnl_pct REAL,
            days_held INTEGER
        );
        CREATE TABLE IF NOT EXISTS candidates_log (
            date TEXT,
            symbol TEXT,
            score INTEGER,
            rsi REAL,
            volume_ratio REAL,
            delivery_pct REAL,
            ema20 REAL,
            high40 REAL,
            analyst_consensus TEXT,
            analyst_upside REAL,
            profit_growth REAL,
            debt_equity REAL,
            promoter_holding REAL,
            sector TEXT,
            PRIMARY KEY (date, symbol)
        );
        CREATE TABLE IF NOT EXISTS market_regime (
            date TEXT PRIMARY KEY,
            nifty_close REAL,
            ema20 REAL,
            breadth_pct REAL,
            regime TEXT
        );
    """)
    conn.commit()


def _yf_ticker(symbol):
    """Convert NSE symbol to Yahoo Finance ticker."""
    return symbol + '.NS'


def _rows_from_df(df, symbol):
    """Convert a single-ticker OHLCV DataFrame to insert row tuples."""
    # Flatten multi-level columns if present (yfinance >= 0.2 returns (Price, Ticker))
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(1, axis=1)
    df = df.dropna(subset=['Close'])
    df.index = pd.to_datetime(df.index)
    rows = []
    for ts, row in df.iterrows():
        rows.append((
            symbol,
            ts.strftime('%Y-%m-%d'),
            round(float(row['Open']),  2),
            round(float(row['High']),  2),
            round(float(row['Low']),   2),
            round(float(row['Close']), 2),
            int(row.get('Volume', 0) or 0),
            0,    # delivery_qty — not in yfinance
            0.0,  # delivery_pct — not in yfinance
        ))
    return rows


def download_ohlcv(period_days=180):
    """Fetch OHLCV for all NSE symbols via yfinance."""
    import yfinance as yf

    end   = date.today()
    start = end - timedelta(days=period_days)
    tickers_ns = [_yf_ticker(s) for s in NSE_SYMBOLS]

    logging.info(f"Downloading {len(tickers_ns)} NSE symbols from Yahoo Finance …")
    raw = yf.download(
        tickers_ns,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval='1d',
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    # raw has MultiIndex columns: (Price, Ticker) e.g. ('Close', 'HDFCBANK.NS')
    rows = []
    for ns_ticker, symbol in zip(tickers_ns, NSE_SYMBOLS):
        try:
            # Extract this ticker's slice: all price columns for one ticker
            ticker_df = raw.xs(ns_ticker, axis=1, level=1)
            rows.extend(_rows_from_df(ticker_df, symbol))
        except (KeyError, Exception) as e:
            logging.debug(f"Skip {symbol}: {e}")

    logging.info(f"Parsed {len(rows)} rows from {len(tickers_ns)} tickers")
    return rows


def download_nifty50(period_days=180):
    """Fetch Nifty 50 index and store as symbol='NIFTY 50'."""
    import yfinance as yf

    end   = date.today()
    start = end - timedelta(days=period_days)

    logging.info("Downloading Nifty 50 index (^NSEI) …")
    df = yf.download(
        NIFTY_INDEX,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval='1d',
        auto_adjust=True,
        progress=False,
    )
    # Single ticker — may have MultiIndex with level 0 = Price, level 1 = '^NSEI'
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(1, axis=1)
    df = df.dropna(subset=['Close'])
    df.index = pd.to_datetime(df.index)

    rows = []
    for ts, row in df.iterrows():
        rows.append((
            'NIFTY 50', ts.strftime('%Y-%m-%d'),
            round(float(row['Open']),  2),
            round(float(row['High']),  2),
            round(float(row['Low']),   2),
            round(float(row['Close']), 2),
            int(row.get('Volume', 0) or 0),
            0, 0.0,
        ))
    return rows


def upsert_rows(rows, conn):
    conn.executemany("""
        INSERT OR REPLACE INTO ohlcv_history
        (symbol, date, open, high, low, close, volume, delivery_qty, delivery_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()


def run():
    setup_logging()
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        equity_rows = download_ohlcv()
        nifty_rows  = download_nifty50()
        all_rows    = equity_rows + nifty_rows
        upsert_rows(all_rows, conn)
        logging.info(f"Upserted {len(equity_rows)} equity rows + {len(nifty_rows)} Nifty rows")
        return len(all_rows)
    except Exception as e:
        logging.error(f"download.run() failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run()
