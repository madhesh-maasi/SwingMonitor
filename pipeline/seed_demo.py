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
    'KPITTECH': {'price': 1652, 'vol': 0.018, 'sector': 'IT'},
    'BHEL':     {'price': 288,  'vol': 0.024, 'sector': 'Infrastructure'},
    'HDFCBANK': {'price': 1715, 'vol': 0.013, 'sector': 'Banking'},
    'TATASTEEL':{'price': 167,  'vol': 0.022, 'sector': 'Metals'},
    'COALINDIA':{'price': 463,  'vol': 0.016, 'sector': 'Mining'},
}

TODAY = date.today()
TODAY_STR = TODAY.isoformat()


def business_days_back(n):
    """Return list of n business days ending today (oldest first)."""
    days = []
    d = TODAY
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(days))


def generate_ohlcv(symbol, start_price, daily_vol, n_days):
    """Generate n_days of OHLCV with a mild uptrend and sine-wave variation."""
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

        # Volume spike on big-move days
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
            exit_date TEXT, exit_price REAL, pnl_pct REAL, days_held INTEGER
        );
        CREATE TABLE IF NOT EXISTS candidates_log (
            date TEXT, symbol TEXT, score INTEGER,
            rsi REAL, volume_ratio REAL, delivery_pct REAL,
            ema20 REAL, high40 REAL,
            analyst_consensus TEXT, analyst_upside REAL,
            profit_growth REAL, debt_equity REAL, promoter_holding REAL, sector TEXT,
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
        start_price = meta['price'] * 0.87  # start ~13% lower 90 days ago
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
    conn.execute("""
        INSERT OR REPLACE INTO market_regime (date, nifty_close, ema20, breadth_pct, regime)
        VALUES (?, 24312.0, 24047.0, 68.0, 'GO')
    """, (TODAY_STR,))
    conn.commit()
    print("  Seeded market regime: GO")


def seed_candidates(conn):
    candidates = [
        ('KPITTECH', 82, 62.3, 2.31, 65.2, 1598.0, 1720.0, 'Strong Buy', 22.4, 18.5, 0.21, 72.1, 'IT'),
        ('BHEL',     74, 59.1, 1.92, 58.4, 274.0,  310.0,  'Buy',        18.2, 12.3, 0.88, 54.6, 'Infrastructure'),
        ('HDFCBANK', 68, 64.0, 1.74, 61.3, 1682.0, 1760.0, 'Buy',        15.1, 22.0, 0.65, 48.3, 'Banking'),
        ('TATASTEEL',63, 60.2, 2.14, 54.1, 158.0,  188.0,  'Buy',        12.4,  8.9, 1.12, 45.2, 'Metals'),
        ('COALINDIA',58, 56.8, 1.61, 52.7, 447.0,  490.0,  'Hold',       11.0, 14.2, 0.04, 52.0, 'Mining'),
    ]

    # Get today's close for each symbol
    closes = {}
    for sym in [c[0] for c in candidates]:
        row = conn.execute(
            "SELECT close FROM ohlcv_history WHERE symbol = ? ORDER BY date DESC LIMIT 1", (sym,)
        ).fetchone()
        closes[sym] = row[0] if row else 100.0

    for c in candidates:
        sym, score, rsi, vr, dp, ema20, high40, consensus, upside, pg, de, ph, sector = c
        conn.execute("""
            INSERT OR REPLACE INTO candidates_log
            (date, symbol, score, rsi, volume_ratio, delivery_pct, ema20, high40,
             analyst_consensus, analyst_upside, profit_growth, debt_equity, promoter_holding, sector)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (TODAY_STR, sym, score, rsi, vr, dp, ema20, high40,
              consensus, upside, pg, de, ph, sector))
    conn.commit()
    print(f"  Seeded {len(candidates)} candidates for today")
    return closes


def seed_paper_trades(conn, closes):
    days = business_days_back(30)

    def entry_date(days_ago):
        idx = max(0, len(days) - 1 - days_ago)
        return days[idx]

    # 3 open trades
    open_trades = [
        ('KPITTECH', entry_date(10), 1620.0, round(1620 * 1.12, 2), round(1620 * 0.94, 2)),
        ('BHEL',     entry_date(5),  272.0,  round(272  * 1.12, 2), round(272  * 0.94, 2)),
        ('TATASTEEL',entry_date(15), 158.0,  round(158  * 1.12, 2), round(158  * 0.94, 2)),
    ]
    for sym, edate, eprice, tprice, sprice in open_trades:
        conn.execute("""
            INSERT OR IGNORE INTO paper_trades
            (symbol, entry_date, entry_price, target_price, stop_price, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        """, (sym, edate, eprice, tprice, sprice))

    # 10 completed trades
    completed_trades = [
        # symbol, entry_date, entry_price, exit_price, status, days_held
        ('INFY',      entry_date(60), 1450.0, round(1450 * 1.12, 2), 'target_hit', 18),
        ('WIPRO',     entry_date(55), 485.0,  round(485  * 1.12, 2), 'target_hit', 15),
        ('RELIANCE',  entry_date(50), 2800.0, round(2800 * 1.12, 2), 'target_hit', 20),
        ('SUNPHARMA', entry_date(45), 1580.0, round(1580 * 1.12, 2), 'target_hit', 19),
        ('BAJFINANCE',entry_date(40), 6800.0, round(6800 * 1.12, 2), 'target_hit', 21),
        ('TITAN',     entry_date(35), 3200.0, round(3200 * 1.12, 2), 'target_hit', 16),
        ('AXISBANK',  entry_date(28), 1050.0, round(1050 * 0.94, 2), 'stop_hit',   8),
        ('NTPC',      entry_date(25), 330.0,  round(330  * 0.94, 2), 'stop_hit',   12),
        ('MARUTI',    entry_date(22), 11000.0,round(11000* 0.94, 2), 'stop_hit',   5),
        ('ONGC',      entry_date(21), 260.0,  round(260  * 1.055, 2),'expired',    21),
    ]
    exit_day = days[-1]
    for sym, edate, eprice, xprice, status, dheld in completed_trades:
        pnl = round((xprice - eprice) / eprice * 100, 2)
        conn.execute("""
            INSERT OR IGNORE INTO paper_trades
            (symbol, entry_date, entry_price, target_price, stop_price,
             status, exit_date, exit_price, pnl_pct, days_held)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sym, edate, eprice,
              round(eprice * 1.12, 2), round(eprice * 0.94, 2),
              status, exit_day, xprice, pnl, dheld))
    conn.commit()
    print(f"  Seeded 3 open + 10 completed paper trades")


def build_data_json(conn, closes):
    """Write data.json so the dashboard works before any live pipeline run."""
    candidates_rows = conn.execute("""
        SELECT symbol, score, rsi, volume_ratio, delivery_pct, ema20, high40,
               analyst_consensus, analyst_upside, profit_growth, debt_equity,
               promoter_holding, sector
        FROM candidates_log WHERE date = ?
        ORDER BY score DESC
    """, (TODAY_STR,)).fetchall()

    # Get sparkline (last 7 closes per symbol)
    candidates = []
    for row in candidates_rows:
        sym = row[0]
        sparkline_rows = conn.execute("""
            SELECT close FROM ohlcv_history WHERE symbol = ?
            ORDER BY date DESC LIMIT 7
        """, (sym,)).fetchall()
        sparkline = [r[0] for r in reversed(sparkline_rows)]
        close = closes.get(sym, row[5])
        candidates.append({
            'symbol': sym, 'sector': row[12],
            'score': row[1], 'rsi': row[2], 'volume_ratio': row[3],
            'delivery_pct': row[4], 'ema20': row[5], 'high40': row[6],
            'analyst_consensus': row[7], 'analyst_upside': row[8],
            'profit_growth': row[9], 'debt_equity': row[10], 'promoter_holding': row[11],
            'close': round(close, 2),
            'target_price': round(close * 1.12, 2),
            'stop_price': round(close * 0.94, 2),
            'sparkline': sparkline,
        })

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

    completed_rows = conn.execute("""
        SELECT symbol, entry_date, exit_date, entry_price, exit_price, pnl_pct, status, days_held
        FROM paper_trades WHERE status != 'open'
        ORDER BY exit_date DESC
    """).fetchall()

    wins = [r for r in completed_rows if r[5] and r[5] > 0]
    losses = [r for r in completed_rows if r[5] and r[5] <= 0]
    total = len(completed_rows)
    win_rate = round(len(wins) / total * 100, 1) if total else 0.0
    avg_gain = round(sum(r[5] for r in wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(r[5] for r in losses) / len(losses), 2) if losses else 0.0
    expectancy = round((win_rate / 100 * avg_gain) + ((1 - win_rate / 100) * avg_loss), 2)

    data = {
        'updated_at': datetime.now().strftime('%H:%M'),
        'regime': {
            'date': TODAY_STR,
            'nifty_close': 24312.0,
            'ema20': 24047.0,
            'breadth_pct': 68.0,
            'regime': 'GO',
        },
        'metrics': {
            'stocks_scanned': 2418,
            'passed_technical': 47,
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
                'win_rate': win_rate, 'avg_gain': avg_gain,
                'avg_loss': avg_loss, 'expectancy': expectancy,
                'total_trades': total,
            },
            'trades': [
                {
                    'symbol': r[0], 'entry_date': r[1], 'exit_date': r[2],
                    'entry_price': r[3], 'exit_price': r[4], 'pnl_pct': r[5],
                    'outcome': r[6], 'days_held': r[7],
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
