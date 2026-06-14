"""Run once to add new columns to existing history.db schema.
Safe to run multiple times — skips already-existing columns."""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'history.db'

MIGRATIONS = [
    "ALTER TABLE paper_trades ADD COLUMN gap_rejected_pct REAL",
    "ALTER TABLE paper_trades ADD COLUMN stop_moved_to_breakeven INTEGER DEFAULT 0",
    "ALTER TABLE candidates_log ADD COLUMN atr14 REAL",
    "ALTER TABLE candidates_log ADD COLUMN stop_price REAL",
    "ALTER TABLE candidates_log ADD COLUMN target_price REAL",
    "ALTER TABLE candidates_log ADD COLUMN cached_data INTEGER DEFAULT 0",
    "ALTER TABLE candidates_log ADD COLUMN cache_age_days INTEGER",
    "ALTER TABLE candidates_log ADD COLUMN shares_outstanding INTEGER",
    "ALTER TABLE candidates_log ADD COLUMN market_cap_source TEXT DEFAULT 'dynamic'",
]


def migrate(conn):
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
            col = sql.split('ADD COLUMN')[1].strip().split()[0]
            print(f"  Added column: {col}")
        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                col = sql.split('ADD COLUMN')[1].strip().split()[0]
                print(f"  Already exists: {col}")
            else:
                print(f"  ERROR: {sql}\n    -> {e}")
    conn.commit()


def main():
    print(f"Migrating {DB_PATH} ...")
    if not DB_PATH.exists():
        print("  DB not found — run seed_demo.py first")
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        migrate(conn)
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
