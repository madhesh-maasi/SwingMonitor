"""Seed history.db with realistic demo data for immediate UI testing."""

import json
import math
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

random.seed(42)

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'history.db'
DATA_JSON = BASE_DIR / 'dashboard' / 'public' / 'data.json'

SYMBOLS = {
    'KPITTECH': {'price': 1652, 'vol': 0.018, 'sector': 'IT',             'shares_cr': 77},
    'BHEL':     {'price': 288,  'vol': 0.024, 'sector': 'Infrastructure', 'shares_cr': 350},
    'HDFCBANK': {'price': 1715, 'vol': 0.013, 'sector': 'Banking',        'shares_cr': 760},
    'TATASTEEL':{'price': 167,  'vol': 0.022, 'sector': 'Metals',         'shares_cr': 1230},
    'COALINDIA':{'price': 463,  'vol': 0.016, 'sector': 'Mining',         'shares_cr': 615},
}

TODAY = date.today()
TODAY_STR = TODAY.isoformat()


def business_days_back(n):
    days = []
    d = TODAY
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(days))


def generate_ohlcv(symbol, start_price, daily_vol, n_days):
    rows = []
    price = start_price
    for i in range(n_days):
        trend = 0.0004 + math.sin(i / 25) * 0.0003
        daily_return = random.gauss(trend, daily_vol)
        price = max(price * (1 + daily_return), 1)

        candle_range = price * random.uniform(0.008, 0.022)
        open_ = price + random.uniform(-candle_range * 0.3, candle_range * 0.3)
        high = max(open_, price) + random.uniform(0, candle_range * 0.6)
        low = min(open_, price) - random.uniform(0, candle_range * 0.4)
        close = price

        base_vol = random.randint(600_000, 2_500_000)
        vol_multiplier = 1 + max(0, abs(daily_return) / daily_vol - 1) * 2
        volume = int(base_vol * vol_multiplier)
        delivery_pct = random.uniform(48, 78)
        delivery_qty = int(volume * delivery_pct / 100)

        rows.append((
            symbol,
            round(open_, 2), round(high, 2), round(low, 2), round(close, 2),
            volume, delivery_qty, round(delivery_pct, 2)
        ))
    return rows


def init_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ohlcv_history (
            symbol TEXT, date TEXT,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER, delivery_qty INTEGER, delivery_pct REAL,
            PRIMARY KEY (symbol, date)
        );
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, entry_date TEXT, entry_price REAL,
            target_price REAL, stop_price REAL,
            status TEXT DEFAULT 'open',
            exit_date TEXT, exit_price REAL, pnl_pct REAL, days_held INTEGER,
            gap_rejected_pct REAL, stop_moved_to_breakeven INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS candidates_log (
            date TEXT, symbol TEXT, score INTEGER,
            rsi REAL, volume_ratio REAL, delivery_pct REAL,
            ema20 REAL, high40 REAL,
            analyst_consensus TEXT, analyst_upside REAL,
            profit_growth REAL, debt_equity REAL, promoter_holding REAL, sector TEXT,
            atr14 REAL, stop_price REAL, target_price REAL,
            cached_data INTEGER DEFAULT 0, cache_age_days INTEGER,
            shares_outstanding INTEGER, market_cap_source TEXT DEFAULT 'dynamic',
            PRIMARY KEY (date, symbol)
        );
        CREATE TABLE IF NOT EXISTS market_regime (
            date TEXT PRIMARY KEY,
            nifty_close REAL, ema20 REAL, breadth_pct REAL, regime TEXT
        );
    """)
    conn.commit()


def seed_ohlcv(conn):
    days = business_days_back(90)
    for sym, meta in SYMBOLS.items():
        start_price = meta['price'] * 0.87
        rows = generate_ohlcv(sym, start_price, meta['vol'], len(days))
        for i, day in enumerate(days):
            r = rows[i]
            conn.execute("""
                INSERT OR REPLACE INTO ohlcv_history
                (symbol, date, open, high, low, close, volume, delivery_qty, delivery_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (r[0], day) + r[1:])
    conn.commit()
    print(f"  Seeded {len(SYMBOLS) * len(days)} OHLCV rows")


def seed_regime(conn):
    conn.execute("DELETE FROM market_regime")
    conn.commit()
    days = business_days_back(35)
    regimes = ['GO', 'GO', 'GO', 'CAUTION', 'GO', 'AVOID', 'GO', 'CAUTION', 'GO', 'GO']
    for i, day in enumerate(days):
        r = regimes[i % len(regimes)]
        breadth = 68.0 if r == 'GO' else (48.0 if r == 'CAUTION' else 28.0)
        nifty = 24312.0 + (i - len(days) // 2) * 45
        ema20 = nifty * 0.99
        conn.execute("""
            INSERT OR REPLACE INTO market_regime (date, nifty_close, ema20, breadth_pct, regime)
            VALUES (?, ?, ?, ?, ?)
        """, (day, round(nifty, 0), round(ema20, 0), breadth, r))
    conn.commit()
    print(f"  Seeded {len(days)} market regime rows")


def seed_candidates(conn):
    conn.execute("DELETE FROM candidates_log")
    conn.commit()
    # (sym, score, rsi, vr, dp, ema20, high40, consensus, upside, pg, de, ph, sector, atr_factor)
    candidates = [
        ('KPITTECH', 82, 62.3, 2.31, 65.2, 1598.0, 1720.0, 'Strong Buy', 22.4, 18.5, 0.21, 72.1, 'IT',             0.018),
        ('BHEL',     74, 59.1, 1.92, 58.4, 274.0,  310.0,  'Buy',        18.2, 12.3, 0.88, 54.6, 'Infrastructure', 0.024),
        ('HDFCBANK', 68, 64.0, 1.74, 61.3, 1682.0, 1760.0, 'Buy',        15.1, 22.0, 0.65, 48.3, 'Banking',        0.013),
        ('TATASTEEL',63, 60.2, 2.14, 54.1, 158.0,  188.0,  'Buy',        12.4,  8.9, 1.12, 45.2, 'Metals',         0.022),
        ('COALINDIA',58, 56.8, 1.61, 52.7, 447.0,  490.0,  'Hold',       11.0, 14.2, 0.04, 52.0, 'Mining',         0.016),
    ]

    closes = {}
    for sym in [c[0] for c in candidates]:
        row = conn.execute(
            "SELECT close FROM ohlcv_history WHERE symbol = ? ORDER BY date DESC LIMIT 1", (sym,)
        ).fetchone()
        closes[sym] = row[0] if row else 100.0

    for c in candidates:
        sym, score, rsi, vr, dp, ema20, high40, consensus, upside, pg, de, ph, sector, atr_f = c
        close = closes[sym]
        atr14 = round(close * atr_f, 2)
        stop_price  = round(close - 1.5 * atr14, 2)
        target_price = round(close + 3.0 * atr14, 2)
        shares_outstanding = int(SYMBOLS[sym]['shares_cr'] * 1_00_000)
        conn.execute("""
            INSERT OR REPLACE INTO candidates_log
            (date, symbol, score, rsi, volume_ratio, delivery_pct, ema20, high40,
             analyst_consensus, analyst_upside, profit_growth, debt_equity, promoter_holding, sector,
             atr14, stop_price, target_price, cached_data, cache_age_days,
             shares_outstanding, market_cap_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (TODAY_STR, sym, score, rsi, vr, dp, ema20, high40,
              consensus, upside, pg, de, ph, sector,
              atr14, stop_price, target_price, 0, None,
              shares_outstanding, 'dynamic'))
    conn.commit()
    print(f"  Seeded {len(candidates)} candidates for today")
    return closes


def seed_paper_trades(conn, closes):
    # Clear existing trades so each seed run is idempotent
    conn.execute("DELETE FROM paper_trades")
    conn.commit()

    days = business_days_back(35)

    def entry_date(days_ago):
        idx = max(0, len(days) - 1 - days_ago)
        return days[idx]

    # 3 open trades (one with breakeven stop triggered)
    open_trades = [
        ('KPITTECH', entry_date(10), 1620.0, False),
        ('BHEL',     entry_date(5),  272.0,  False),
        ('TATASTEEL',entry_date(15), 158.0,  True),   # breakeven stop triggered
    ]
    for sym, edate, eprice, be in open_trades:
        close = closes.get(sym, eprice)
        atr14 = close * SYMBOLS.get(sym, {}).get('vol', 0.018)
        tprice = round(eprice + 3.0 * atr14, 2)
        sprice = eprice if be else round(eprice - 1.5 * atr14, 2)
        conn.execute("""
            INSERT OR IGNORE INTO paper_trades
            (symbol, entry_date, entry_price, target_price, stop_price, status,
             stop_moved_to_breakeven)
            VALUES (?, ?, ?, ?, ?, 'open', ?)
        """, (sym, edate, eprice, tprice, sprice, 1 if be else 0))

    # 1 gap-rejected trade
    conn.execute("""
        INSERT OR IGNORE INTO paper_trades
        (symbol, entry_date, entry_price, target_price, stop_price, status,
         exit_date, exit_price, gap_rejected_pct, days_held)
        VALUES (?, ?, ?, ?, ?, 'gap_rejected', ?, ?, ?, ?)
    """, ('HDFCBANK', entry_date(8), 1715.0,
          round(1715 + 3.0 * 1715 * 0.013, 2),
          round(1715 - 1.5 * 1715 * 0.013, 2),
          entry_date(7), round(1715 * 1.025, 2), 2.5, 1))

    today_dt = TODAY
    week_start = today_dt - timedelta(days=today_dt.weekday())  # Monday of current week
    # Exit date for "old" trades: 2 weeks before current week start (safely prior week)
    old_exit_day = (week_start - timedelta(days=10)).isoformat()
    # Exit date for "this week" trades: Tuesday of current week
    this_week_exit = (week_start + timedelta(days=1)).isoformat()

    # 10 completed trades (prior weeks) + 2 this week
    completed_trades = [
        ('INFY',      entry_date(60), 1450.0, 'target_hit', 18, False),
        ('WIPRO',     entry_date(55), 485.0,  'target_hit', 15, False),
        ('RELIANCE',  entry_date(50), 2800.0, 'target_hit', 20, False),
        ('SUNPHARMA', entry_date(45), 1580.0, 'target_hit', 19, False),
        ('BAJFINANCE',entry_date(40), 6800.0, 'target_hit', 21, False),
        ('TITAN',     entry_date(35), 3200.0, 'target_hit', 16, False),
        ('AXISBANK',  entry_date(28), 1050.0, 'stop_hit',   8,  False),
        ('NTPC',      entry_date(25), 330.0,  'stop_hit',   12, False),
        ('MARUTI',    entry_date(22), 11000.0,'stop_hit',   5,  False),
        ('ONGC',      entry_date(21), 260.0,  'expired',    21, False),
        # This week's trades
        ('SBIN',      entry_date(3),  825.0,  'target_hit', 3,  True),
        ('ICICIBANK', entry_date(2),  1250.0, 'target_hit', 2,  True),
    ]

    for sym, edate, eprice, status, dheld, this_week in completed_trades:
        xdate = this_week_exit if this_week else old_exit_day
        atr14 = eprice * 0.018
        if status == 'target_hit':
            xprice = round(eprice + 3.0 * atr14, 2)
        elif status == 'stop_hit':
            xprice = round(eprice - 1.5 * atr14, 2)
        else:
            xprice = round(eprice * 1.055, 2)
        pnl = round((xprice - eprice) / eprice * 100, 2)
        conn.execute("""
            INSERT OR IGNORE INTO paper_trades
            (symbol, entry_date, entry_price, target_price, stop_price,
             status, exit_date, exit_price, pnl_pct, days_held)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sym, edate, eprice,
              round(eprice + 3.0 * atr14, 2), round(eprice - 1.5 * atr14, 2),
              status, xdate, xprice, pnl, dheld))
    conn.commit()
    print("  Seeded 3 open + 1 gap-rejected + 12 completed paper trades")


def build_data_json(conn, closes):
    today_dt = TODAY
    week_start = today_dt - timedelta(days=today_dt.weekday())

    candidates_rows = conn.execute("""
        SELECT symbol, score, rsi, volume_ratio, delivery_pct, ema20, high40,
               analyst_consensus, analyst_upside, profit_growth, debt_equity,
               promoter_holding, sector, atr14, stop_price, target_price,
               cached_data, cache_age_days, shares_outstanding, market_cap_source
        FROM candidates_log WHERE date = ?
        ORDER BY score DESC
    """, (TODAY_STR,)).fetchall()

    candidates = []
    for row in candidates_rows:
        sym = row[0]
        sparkline_rows = conn.execute("""
            SELECT close FROM ohlcv_history WHERE symbol = ?
            ORDER BY date DESC LIMIT 7
        """, (sym,)).fetchall()
        sparkline = [r[0] for r in reversed(sparkline_rows)]
        close = closes.get(sym, row[5])
        last2 = conn.execute(
            "SELECT close FROM ohlcv_history WHERE symbol = ? ORDER BY date DESC LIMIT 2", (sym,)
        ).fetchall()
        day_change_pct = round((last2[0][0] - last2[1][0]) / last2[1][0] * 100, 2) if len(last2) >= 2 else 0.0

        atr14       = row[13] or round(close * 0.018, 2)
        stop_price  = row[14] or round(close - 1.5 * atr14, 2)
        target_price = row[15] or round(close + 3.0 * atr14, 2)

        candidates.append({
            'symbol': sym, 'sector': row[12],
            'score': row[1], 'rsi': row[2], 'volume_ratio': row[3],
            'delivery_pct': row[4], 'ema20': row[5], 'high40': row[6],
            'analyst_consensus': row[7], 'analyst_upside': row[8],
            'profit_growth': row[9], 'debt_equity': row[10], 'promoter_holding': row[11],
            'close': round(close, 2),
            'atr14': round(atr14, 2),
            'target_price': round(target_price, 2),
            'stop_price': round(stop_price, 2),
            'sparkline': sparkline,
            'day_change_pct': day_change_pct,
            'analyst_count': [18, 12, 9, 14, 11][list(closes.keys()).index(sym) % 5],
            'cached_data': bool(row[16]),
            'cache_age_days': row[17],
            'shares_outstanding': row[18],
            'market_cap_source': row[19] or 'dynamic',
        })

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

    completed_rows = conn.execute("""
        SELECT symbol, entry_date, exit_date, entry_price, exit_price, pnl_pct,
               status, days_held, gap_rejected_pct
        FROM paper_trades WHERE status != 'open'
        ORDER BY exit_date DESC
    """).fetchall()

    gap_rejected = [r for r in completed_rows if r[6] == 'gap_rejected']
    real_trades   = [r for r in completed_rows if r[6] != 'gap_rejected']
    wins   = [r for r in real_trades if r[5] and r[5] > 0]
    losses = [r for r in real_trades if r[5] and r[5] <= 0]
    total  = len(real_trades)
    win_rate   = round(len(wins) / total * 100, 1) if total else 0.0
    avg_gain   = round(sum(r[5] for r in wins) / len(wins), 2) if wins else 0.0
    avg_loss   = round(sum(r[5] for r in losses) / len(losses), 2) if losses else 0.0
    expectancy = round((win_rate / 100 * avg_gain) + ((1 - win_rate / 100) * avg_loss), 2)

    week_start_str = week_start.isoformat()
    this_week  = [r for r in completed_rows if r[2] and r[2] >= week_start_str]
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
        'regime': {
            'date': TODAY_STR,
            'nifty_close': 24312.0,
            'ema20': 24047.0,
            'breadth_pct': 68.0,
            'regime': 'GO',
        },
        'regime_history': [
            {'date': r[0], 'regime': r[1], 'breadth_pct': r[2], 'nifty_close': r[3]}
            for r in reversed(regime_history)
        ],
        'metrics': {
            'stocks_scanned': 2418,
            'passed_technical': 47,
            'final_candidates': len(candidates),
            'paper_win_rate': win_rate,
        },
        'sector_warning': False,
        'sector_warning_message': '',
        'data_integrity_warning': False,
        'integrity_warning_message': '',
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
                'win_rate': win_rate, 'avg_gain': avg_gain,
                'avg_loss': avg_loss, 'expectancy': expectancy,
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
                for r in completed_rows
            ],
        },
    }

    DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_JSON, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  Wrote {DATA_JSON}")


def main():
    print(f"Seeding {DB_PATH} ...")
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        init_schema(conn)
        # Run migration for any existing DB
        from migrate import migrate
        migrate(conn)
        seed_ohlcv(conn)
        seed_regime(conn)
        closes = seed_candidates(conn)
        seed_paper_trades(conn, closes)
        build_data_json(conn, closes)
        print("\nDone! Database seeded successfully.")
        print(f"Run:  cd dashboard && npm install && npm run dev")
        print(f"Open: http://localhost:3001")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
