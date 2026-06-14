import sqlite3
import logging
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'history.db'


def _today():
    return date.today().isoformat()


def _days_between(date1_str, date2_str):
    d1 = datetime.strptime(date1_str, '%Y-%m-%d').date()
    d2 = datetime.strptime(date2_str, '%Y-%m-%d').date()
    return (d2 - d1).days


def update_open_trades(conn):
    today = _today()
    open_trades = conn.execute(
        "SELECT id, symbol, entry_date, entry_price, target_price, stop_price FROM paper_trades WHERE status = 'open'"
    ).fetchall()

    for trade in open_trades:
        tid, symbol, entry_date, entry_price, target_price, stop_price = trade
        days_held = _days_between(entry_date, today)

        row = conn.execute(
            "SELECT high, low, close FROM ohlcv_history WHERE symbol = ? AND date = ?",
            (symbol, today)
        ).fetchone()

        if row is None:
            # No today's data yet — skip
            continue

        high, low, close = row
        status = 'open'
        exit_price = None
        exit_date = None

        if high >= target_price:
            status = 'target_hit'
            exit_price = target_price
            exit_date = today
        elif low <= stop_price:
            status = 'stop_hit'
            exit_price = stop_price
            exit_date = today
        elif days_held >= 21:
            status = 'expired'
            exit_price = close
            exit_date = today

        if status != 'open':
            pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2)
            conn.execute("""
                UPDATE paper_trades
                SET status = ?, exit_date = ?, exit_price = ?, pnl_pct = ?, days_held = ?
                WHERE id = ?
            """, (status, exit_date, exit_price, pnl_pct, days_held, tid))
            logging.info(f"Trade {tid} ({symbol}): {status}, P&L {pnl_pct:+.2f}%")

    conn.commit()


def insert_new_trades(candidates, conn):
    today = _today()
    for c in candidates:
        symbol = c['symbol']
        # Only insert if no open trade already exists for this symbol
        existing = conn.execute(
            "SELECT id FROM paper_trades WHERE symbol = ? AND status = 'open'",
            (symbol,)
        ).fetchone()
        if existing:
            logging.info(f"Skipping paper trade insert for {symbol}: already open")
            continue

        conn.execute("""
            INSERT INTO paper_trades (symbol, entry_date, entry_price, target_price, stop_price, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        """, (symbol, today, c['close'], c['target_price'], c['stop_price']))
        logging.info(f"Inserted paper trade: {symbol} @ {c['close']} | T:{c['target_price']} S:{c['stop_price']}")

    conn.commit()


def run(candidates, conn=None):
    close_conn = conn is None
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
    try:
        update_open_trades(conn)
        if candidates:
            insert_new_trades(candidates, conn)
    except Exception as e:
        logging.error(f"paper_trades.run() failed: {e}")
        raise
    finally:
        if close_conn:
            conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run([])
