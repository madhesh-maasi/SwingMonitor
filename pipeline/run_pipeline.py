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

    # Use the most recent Nifty 50 close available (works on weekends / holidays)
    nifty_row = conn.execute(
        "SELECT close FROM ohlcv_history WHERE symbol = 'NIFTY 50' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    nifty_close = nifty_row[0] if nifty_row else 24000.0

    # Compute Nifty EMA20 from actual Nifty history
    nifty_hist = conn.execute(
        "SELECT close FROM ohlcv_history WHERE symbol = 'NIFTY 50' ORDER BY date DESC LIMIT 25"
    ).fetchall()
    if len(nifty_hist) >= 5:
        import pandas as pd
        closes = pd.Series([r[0] for r in reversed(nifty_hist)])
        nifty_ema20 = float(closes.ewm(span=20, adjust=False).mean().iloc[-1])
    else:
        nifty_ema20 = nifty_close * 0.99

    regime = compute_regime(nifty_close, nifty_ema20, breadth_pct)

    conn.execute("""
        INSERT OR REPLACE INTO market_regime (date, nifty_close, ema20, breadth_pct, regime)
        VALUES (?, ?, ?, ?, ?)
    """, (today, nifty_close, round(nifty_ema20, 2), round(breadth_pct, 1), regime))
    conn.commit()
    return {'date': today, 'nifty_close': nifty_close, 'ema20': round(nifty_ema20, 2),
            'breadth_pct': round(breadth_pct, 1), 'regime': regime}


def log_candidates(candidates, conn, today):
    # Clear today's entries so live data replaces any seeded/stale rows
    conn.execute("DELETE FROM candidates_log WHERE date = ?", (today,))
    for c in candidates:
        conn.execute("""
            INSERT OR REPLACE INTO candidates_log
            (date, symbol, score, rsi, volume_ratio, delivery_pct, ema20, high40,
             analyst_consensus, analyst_upside, profit_growth, debt_equity, promoter_holding,
             sector, atr14, stop_price, target_price,
             cached_data, cache_age_days, shares_outstanding, market_cap_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today, c['symbol'], c['score'], c['rsi'], c['volume_ratio'],
            c['delivery_pct'], c['ema20'], c['high40'],
            c['analyst_consensus'], c['analyst_upside'], c['profit_growth'],
            c['debt_equity'], c['promoter_holding'], c.get('sector', 'Equity'),
            c.get('atr14'), c.get('stop_price'), c.get('target_price'),
            1 if c.get('cached_data') else 0,
            c.get('cache_age_days'),
            c.get('shares_outstanding'),
            c.get('market_cap_source', 'dynamic'),
        ))
    conn.commit()


def _data_integrity_check(candidates, total_step2):
    """Return (warning_bool, message) based on null fundamental rate."""
    null_count = sum(1 for c in candidates if c.get('cached_data'))
    if total_step2 == 0:
        return False, ''
    if null_count / max(total_step2, 1) > 0.30:
        msg = (f"Fundamental data incomplete for {null_count} of {total_step2} candidates. "
               "Verify before trading.")
        return True, msg
    return False, ''


def build_data_json(conn, regime, candidates, total_scanned, passed_tech,
                    sector_warning=False, sector_warning_message='',
                    data_integrity_warning=False, integrity_warning_message=''):
    today = date.today().isoformat()

    open_trades = conn.execute("""
        SELECT pt.id, pt.symbol, pt.entry_date, pt.entry_price, pt.target_price, pt.stop_price,
               h.close as current_price, pt.stop_moved_to_breakeven
        FROM paper_trades pt
        LEFT JOIN (
            SELECT symbol, close FROM ohlcv_history
            WHERE date = (SELECT MAX(date) FROM ohlcv_history)
        ) h ON pt.symbol = h.symbol
        WHERE pt.status = 'open'
    """).fetchall()

    completed = conn.execute("""
        SELECT symbol, entry_date, exit_date, entry_price, exit_price, pnl_pct,
               status, days_held, gap_rejected_pct
        FROM paper_trades WHERE status != 'open'
        ORDER BY exit_date DESC LIMIT 50
    """).fetchall()

    gap_rejected = [r for r in completed if r[6] == 'gap_rejected']
    real_trades   = [r for r in completed if r[6] != 'gap_rejected']
    wins   = [r for r in real_trades if r[5] and r[5] > 0]
    losses = [r for r in real_trades if r[5] and r[5] <= 0]
    total  = len(real_trades)
    win_rate   = round(len(wins) / total * 100, 1) if total else 0.0
    avg_gain   = round(sum(r[5] for r in wins) / len(wins), 2) if wins else 0.0
    avg_loss   = round(sum(r[5] for r in losses) / len(losses), 2) if losses else 0.0
    expectancy = round((win_rate / 100 * avg_gain) + ((1 - win_rate / 100) * avg_loss), 2)

    # Weekly summary
    from datetime import date as dt_date
    today_dt = dt_date.fromisoformat(today)
    week_start = (today_dt - __import__('datetime').timedelta(days=today_dt.weekday())).isoformat()
    this_week  = [r for r in completed if r[2] and r[2] >= week_start]
    week_real  = [r for r in this_week if r[6] != 'gap_rejected']
    week_wins  = [r for r in week_real if r[5] and r[5] > 0]
    week_win_rate = round(len(week_wins) / len(week_real) * 100, 1) if week_real else 0.0
    best_trade  = max(week_real, key=lambda r: r[5] or 0, default=None)
    worst_trade = min(week_real, key=lambda r: r[5] or 0, default=None)

    regime_history = conn.execute("""
        SELECT date, regime, breadth_pct, nifty_close
        FROM market_regime ORDER BY date DESC LIMIT 30
    """).fetchall()

    data = {
        'updated_at': datetime.now().strftime('%H:%M'),
        'regime': regime,
        'regime_history': [
            {'date': r[0], 'regime': r[1], 'breadth_pct': r[2], 'nifty_close': r[3]}
            for r in reversed(regime_history)
        ],
        'metrics': {
            'stocks_scanned': total_scanned,
            'passed_technical': passed_tech,
            'final_candidates': len(candidates),
            'paper_win_rate': win_rate,
        },
        'sector_warning': sector_warning,
        'sector_warning_message': sector_warning_message,
        'data_integrity_warning': data_integrity_warning,
        'integrity_warning_message': integrity_warning_message,
        'candidates': candidates,
        'paper_trades': [
            {
                'id': r[0], 'symbol': r[1], 'entry_date': r[2],
                'entry_price': r[3], 'target_price': r[4], 'stop_price': r[5],
                'current_price': r[6], 'stop_moved_to_breakeven': bool(r[7]),
            }
            for r in open_trades
        ],
        'completed': {
            'summary': {
                'win_rate': win_rate,
                'avg_gain': avg_gain,
                'avg_loss': avg_loss,
                'expectancy': expectancy,
                'total_trades': total,
                'gap_rejections': len(gap_rejected),
            },
            'weekly_summary': {
                'trades_closed_this_week': len(week_real),
                'week_win_rate': week_win_rate,
                'best_trade': {'symbol': best_trade[0], 'pnl_pct': best_trade[5]} if best_trade else None,
                'worst_trade': {'symbol': worst_trade[0], 'pnl_pct': worst_trade[5]} if worst_trade else None,
                'gap_rejections_this_week': sum(1 for r in this_week if r[6] == 'gap_rejected'),
            },
            'trades': [
                {
                    'symbol': r[0], 'entry_date': r[1], 'exit_date': r[2],
                    'entry_price': r[3], 'exit_price': r[4], 'pnl_pct': r[5],
                    'outcome': r[6], 'days_held': r[7], 'gap_rejected_pct': r[8],
                }
                for r in completed
            ],
        },
    }
    return data


FLAG_FILE = Path(__file__).parent / 'running.flag'


def _clear_flag():
    try:
        FLAG_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def run():
    setup_logging()
    FLAG_FILE.touch()          # mark as running (also set by refresh.js)
    today = date.today().isoformat()
    logging.info(f"=== Pipeline run started: {today} ===")

    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        logging.info("--- Step 1: Download ---")
        download.init_db(conn)
        try:
            download.run()
        except Exception as e:
            logging.error(f"Download failed (continuing): {e}")

        logging.info("--- Step 2: Indicators ---")
        today_df, breadth_pct = indicators.run(conn)
        logging.info(f"Indicators: {len(today_df)} symbols, breadth {breadth_pct:.1f}%")

        regime = upsert_regime(conn, today_df, breadth_pct)
        logging.info(f"Regime: {regime['regime']}")

        logging.info("--- Step 3: Scanner ---")
        total_scanned = len(today_df)
        passed_tech = 0
        candidates = []
        sector_warning = False
        sector_warning_message = ''

        if not today_df.empty:
            scan_result = scanner.run(today_df, breadth_pct, conn)
            if isinstance(scan_result, tuple) and len(scan_result) >= 3:
                candidates = scan_result[0] or []
                total_scanned = scan_result[1]
                passed_tech = scan_result[2]
                if len(scan_result) >= 5:
                    sector_warning = scan_result[3]
                    sector_warning_message = scan_result[4]
            else:
                candidates = scan_result or []

        log_candidates(candidates, conn, today)

        # Data integrity check
        null_count = sum(1 for c in candidates if c.get('cached_data'))
        total_candidates = len(candidates)
        data_integrity_warning = False
        integrity_warning_message = ''
        if total_candidates > 0 and null_count / total_candidates > 0.30:
            data_integrity_warning = True
            integrity_warning_message = (
                f"Fundamental data incomplete for {null_count} of {total_candidates} candidates. "
                "Verify before trading."
            )
            logging.warning(f"Data integrity warning: {integrity_warning_message}")

        logging.info("--- Step 4: Paper trades ---")
        paper_trades.run(candidates, conn)

        DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
        data = build_data_json(
            conn, regime, candidates, total_scanned, passed_tech,
            sector_warning=sector_warning,
            sector_warning_message=sector_warning_message,
            data_integrity_warning=data_integrity_warning,
            integrity_warning_message=integrity_warning_message,
        )
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
        _clear_flag()


if __name__ == '__main__':
    run()
