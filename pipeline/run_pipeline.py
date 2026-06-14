"""Master pipeline runner — called by cron at 4:30 PM IST (11:00 UTC) Mon–Fri."""

import json
import logging
import sqlite3
import sys
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'history.db'
LOG_DIR = Path(__file__).parent / 'logs'
DATA_JSON = BASE_DIR / 'dashboard' / 'public' / 'data.json'

sys.path.insert(0, str(Path(__file__).parent))
import download
import indicators
import scanner
import paper_trades


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{date.today().isoformat()}.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    fh = logging.FileHandler(log_file)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.handlers = [fh, sh]


def compute_regime(nifty_close, ema20, breadth_pct):
    if nifty_close > ema20 and breadth_pct > 60:
        return 'GO'
    elif nifty_close > ema20 * 0.97 or breadth_pct > 45:
        return 'CAUTION'
    else:
        return 'AVOID'


def upsert_regime(conn, today_df, breadth_pct):
    today = date.today().isoformat()
    # Use NIFTY 50 index close as proxy; fallback to median of all stocks
    nifty_row = conn.execute(
        "SELECT close FROM ohlcv_history WHERE symbol = 'NIFTY 50' AND date = ? LIMIT 1",
        (today,)
    ).fetchone()

    if nifty_row:
        nifty_close = nifty_row[0]
    else:
        nifty_close = float(today_df['close'].median()) if not today_df.empty else 24000.0

    nifty_ema20 = float(today_df['ema20'].median()) if not today_df.empty else nifty_close * 0.99
    regime = compute_regime(nifty_close, nifty_ema20, breadth_pct)

    conn.execute("""
        INSERT OR REPLACE INTO market_regime (date, nifty_close, ema20, breadth_pct, regime)
        VALUES (?, ?, ?, ?, ?)
    """, (today, nifty_close, round(nifty_ema20, 2), round(breadth_pct, 1), regime))
    conn.commit()
    return {'date': today, 'nifty_close': nifty_close, 'ema20': round(nifty_ema20, 2),
            'breadth_pct': round(breadth_pct, 1), 'regime': regime}


def log_candidates(candidates, conn, today):
    for c in candidates:
        conn.execute("""
            INSERT OR REPLACE INTO candidates_log
            (date, symbol, score, rsi, volume_ratio, delivery_pct, ema20, high40,
             analyst_consensus, analyst_upside, profit_growth, debt_equity, promoter_holding, sector)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today, c['symbol'], c['score'], c['rsi'], c['volume_ratio'],
            c['delivery_pct'], c['ema20'], c['high40'],
            c['analyst_consensus'], c['analyst_upside'], c['profit_growth'],
            c['debt_equity'], c['promoter_holding'], c.get('sector', 'Equity')
        ))
    conn.commit()


def build_data_json(conn, regime, candidates, total_scanned, passed_tech):
    today = date.today().isoformat()

    open_trades = conn.execute("""
        SELECT pt.id, pt.symbol, pt.entry_date, pt.entry_price, pt.target_price, pt.stop_price,
               h.close as current_price
        FROM paper_trades pt
        LEFT JOIN (
            SELECT symbol, close FROM ohlcv_history
            WHERE date = (SELECT MAX(date) FROM ohlcv_history)
        ) h ON pt.symbol = h.symbol
        WHERE pt.status = 'open'
    """).fetchall()

    completed = conn.execute("""
        SELECT symbol, entry_date, exit_date, entry_price, exit_price, pnl_pct, status, days_held
        FROM paper_trades WHERE status != 'open'
        ORDER BY exit_date DESC LIMIT 50
    """).fetchall()

    wins = [r for r in completed if r[5] and r[5] > 0]
    losses = [r for r in completed if r[5] and r[5] <= 0]
    win_rate = round(len(wins) / len(completed) * 100, 1) if completed else 0.0
    avg_gain = round(sum(r[5] for r in wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(r[5] for r in losses) / len(losses), 2) if losses else 0.0
    expectancy = round((win_rate / 100 * avg_gain) + ((1 - win_rate / 100) * avg_loss), 2)

    data = {
        'updated_at': datetime.now().strftime('%H:%M'),
        'regime': regime,
        'metrics': {
            'stocks_scanned': total_scanned,
            'passed_technical': passed_tech,
            'final_candidates': len(candidates),
            'paper_win_rate': win_rate,
        },
        'candidates': candidates,
        'paper_trades': [
            {
                'id': r[0], 'symbol': r[1], 'entry_date': r[2],
                'entry_price': r[3], 'target_price': r[4], 'stop_price': r[5],
                'current_price': r[6],
            }
            for r in open_trades
        ],
        'completed': {
            'summary': {
                'win_rate': win_rate,
                'avg_gain': avg_gain,
                'avg_loss': avg_loss,
                'expectancy': expectancy,
                'total_trades': len(completed),
            },
            'trades': [
                {
                    'symbol': r[0], 'entry_date': r[1], 'exit_date': r[2],
                    'entry_price': r[3], 'exit_price': r[4], 'pnl_pct': r[5],
                    'outcome': r[6], 'days_held': r[7],
                }
                for r in completed
            ],
        },
    }
    return data


def run():
    setup_logging()
    today = date.today().isoformat()
    logging.info(f"=== Pipeline run started: {today} ===")

    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        # Step 1: Download
        logging.info("--- Step 1: Download ---")
        download.init_db(conn)
        try:
            download.run()
        except Exception as e:
            logging.error(f"Download failed (continuing): {e}")

        # Step 2: Indicators
        logging.info("--- Step 2: Indicators ---")
        today_df, breadth_pct = indicators.run(conn)
        logging.info(f"Indicators: {len(today_df)} symbols, breadth {breadth_pct:.1f}%")

        # Step 3: Regime
        regime = upsert_regime(conn, today_df, breadth_pct)
        logging.info(f"Regime: {regime['regime']} (Nifty {regime['nifty_close']:.0f}, Breadth {regime['breadth_pct']}%)")

        # Step 4: Scanner
        logging.info("--- Step 4: Scanner ---")
        total_scanned = len(today_df)
        passed_tech = 0
        candidates = []
        if not today_df.empty:
            scan_result = scanner.run(today_df, breadth_pct, conn)
            if isinstance(scan_result, tuple) and len(scan_result) == 3:
                candidates, total_scanned, passed_tech = scan_result
            else:
                candidates = scan_result or []

        log_candidates(candidates, conn, today)

        # Step 5: Paper trades
        logging.info("--- Step 5: Paper trades ---")
        paper_trades.run(candidates, conn)

        # Write data.json
        DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        data = build_data_json(conn, regime, candidates, total_scanned, passed_tech)
        with open(DATA_JSON, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logging.info(f"data.json written ({len(candidates)} candidates)")

        logging.info("=== Pipeline run complete ===")
        return data

    except Exception as e:
        logging.error(f"Pipeline failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run()
