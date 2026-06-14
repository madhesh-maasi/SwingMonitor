import requests
import sqlite3
import csv
import io
import logging
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'history.db'
LOG_DIR = Path(__file__).parent / 'logs'

NSE_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full.csv"
NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.nseindia.com',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
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


def download_bhavdata():
    session = requests.Session()
    session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=30)
    resp = session.get(NSE_URL, headers=NSE_HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.text


def parse_and_upsert(csv_text, conn):
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    today = datetime.now().strftime('%Y-%m-%d')

    for row in reader:
        if row.get('SERIES', '').strip() != 'EQ':
            continue
        try:
            symbol = row['SYMBOL'].strip()
            open_ = float(row['OPEN'])
            high = float(row['HIGH'])
            low = float(row['LOW'])
            close = float(row['CLOSE'])
            volume = int(float(row.get('TTL_TRD_QNTY', 0) or 0))
            delivery_qty = int(float(row.get('DELIV_QTY', 0) or 0))
            raw_pct = row.get('DELIV_PER', '0') or '0'
            delivery_pct = float(raw_pct) if raw_pct.strip() not in ('', '-') else 0.0
            date_str = row.get('DATE1', today).strip()
            try:
                date = datetime.strptime(date_str, '%d-%b-%Y').strftime('%Y-%m-%d')
            except ValueError:
                date = today
            rows.append((symbol, date, open_, high, low, close, volume, delivery_qty, delivery_pct))
        except (ValueError, KeyError):
            continue

    conn.executemany("""
        INSERT OR REPLACE INTO ohlcv_history
        (symbol, date, open, high, low, close, volume, delivery_qty, delivery_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    return len(rows)


def run():
    setup_logging()
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        logging.info("Downloading NSE bhavdata CSV...")
        csv_text = download_bhavdata()
        count = parse_and_upsert(csv_text, conn)
        logging.info(f"Upserted {count} EQ rows into ohlcv_history")
        return count
    except Exception as e:
        logging.error(f"download.run() failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run()
