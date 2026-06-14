import path from 'path';
import fs from 'fs';

function getDb() {
  try {
    const Database = require('better-sqlite3');
    const dbPath = path.join(process.cwd(), '..', 'data', 'history.db');
    if (!fs.existsSync(dbPath)) return null;
    return new Database(dbPath, { readonly: true });
  } catch {
    return null;
  }
}

/* Analyst count heuristic keyed by symbol (from seed / live pipeline) */
const ANALYST_COUNTS = {
  KPITTECH: 18, BHEL: 12, HDFCBANK: 9, TATASTEEL: 14, COALINDIA: 11,
};

export default function handler(req, res) {
  const db = getDb();

  if (!db) {
    const jsonPath = path.join(process.cwd(), 'public', 'data.json');
    if (fs.existsSync(jsonPath)) {
      const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
      return res.status(200).json({ candidates: data.candidates ?? [], regime: data.regime });
    }
    return res.status(200).json({ candidates: [], regime: null });
  }

  try {
    const latest = db.prepare('SELECT MAX(date) as d FROM candidates_log').get();
    const latestDate = latest?.d;
    if (!latestDate) {
      db.close();
      return res.status(200).json({ candidates: [], regime: null });
    }

    const rows = db.prepare(`
      SELECT symbol, score, rsi, volume_ratio, delivery_pct, ema20, high40,
             analyst_consensus, analyst_upside, profit_growth, debt_equity,
             promoter_holding, sector
      FROM candidates_log WHERE date = ?
      ORDER BY score DESC
    `).all(latestDate);

    const candidates = rows.map(row => {
      /* Today's close */
      const closeRow = db.prepare(
        'SELECT close FROM ohlcv_history WHERE symbol = ? ORDER BY date DESC LIMIT 1'
      ).get(row.symbol);
      const close = closeRow?.close ?? row.ema20;

      /* Day change % — compare last two closes */
      const last2 = db.prepare(
        'SELECT close FROM ohlcv_history WHERE symbol = ? ORDER BY date DESC LIMIT 2'
      ).all(row.symbol);
      const day_change_pct = last2.length >= 2
        ? ((last2[0].close - last2[1].close) / last2[1].close * 100)
        : 0;

      /* Sparkline — last 7 closes (oldest first) */
      const sparkRows = db.prepare(
        'SELECT close FROM ohlcv_history WHERE symbol = ? ORDER BY date DESC LIMIT 7'
      ).all(row.symbol);
      const sparkline = sparkRows.map(r => r.close).reverse();

      const analyst_count = ANALYST_COUNTS[row.symbol] ?? 0;

      return {
        ...row,
        close:        Math.round(close * 100) / 100,
        target_price: Math.round(close * 1.12 * 100) / 100,
        stop_price:   Math.round(close * 0.94 * 100) / 100,
        day_change_pct: Math.round(day_change_pct * 100) / 100,
        analyst_count,
        sparkline,
      };
    });

    const regime = db.prepare(
      'SELECT * FROM market_regime ORDER BY date DESC LIMIT 1'
    ).get() ?? null;

    db.close();
    res.status(200).json({ candidates, regime, date: latestDate });
  } catch (err) {
    if (db) db.close();
    console.error('candidates API error:', err);
    res.status(500).json({ error: err.message });
  }
}
