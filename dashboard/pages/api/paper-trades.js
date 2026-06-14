import path from 'path';
import fs from 'fs';

function getDb(readonly = true) {
  try {
    const Database = require('better-sqlite3');
    const dbPath = path.join(process.cwd(), '..', 'data', 'history.db');
    if (!fs.existsSync(dbPath)) return null;
    return new Database(dbPath, { readonly });
  } catch {
    return null;
  }
}

export default function handler(req, res) {
  if (req.method === 'POST') {
    return handlePost(req, res);
  }
  return handleGet(req, res);
}

function handleGet(req, res) {
  const db = getDb(true);
  if (!db) {
    const jsonPath = path.join(process.cwd(), 'public', 'data.json');
    if (fs.existsSync(jsonPath)) {
      const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
      return res.status(200).json({ trades: data.paper_trades || [] });
    }
    return res.status(200).json({ trades: [] });
  }

  try {
    const trades = db.prepare(`
      SELECT pt.id, pt.symbol, pt.entry_date, pt.entry_price,
             pt.target_price, pt.stop_price, pt.status,
             h.close as current_price,
             CAST(julianday('now') - julianday(pt.entry_date) AS INTEGER) as days_held
      FROM paper_trades pt
      LEFT JOIN (
        SELECT symbol, close FROM ohlcv_history
        WHERE date = (SELECT MAX(date) FROM ohlcv_history)
      ) h ON pt.symbol = h.symbol
      WHERE pt.status = 'open'
      ORDER BY pt.entry_date DESC
    `).all();

    db.close();
    res.status(200).json({ trades });
  } catch (err) {
    if (db) db.close();
    console.error('paper-trades GET error:', err);
    res.status(500).json({ error: err.message });
  }
}

function handlePost(req, res) {
  const db = getDb(false);
  if (!db) return res.status(503).json({ error: 'Database not found' });

  try {
    const { symbol, close } = req.body;
    if (!symbol || !close) {
      db.close();
      return res.status(400).json({ error: 'symbol and close required' });
    }

    const existing = db.prepare(
      "SELECT id FROM paper_trades WHERE symbol = ? AND status = 'open'"
    ).get(symbol);

    if (existing) {
      db.close();
      return res.status(409).json({ error: `Open trade for ${symbol} already exists` });
    }

    const today = new Date().toISOString().split('T')[0];
    const entry_price = parseFloat(close);
    const target_price = Math.round(entry_price * 1.12 * 100) / 100;
    const stop_price = Math.round(entry_price * 0.94 * 100) / 100;

    const result = db.prepare(`
      INSERT INTO paper_trades (symbol, entry_date, entry_price, target_price, stop_price, status)
      VALUES (?, ?, ?, ?, ?, 'open')
    `).run(symbol, today, entry_price, target_price, stop_price);

    db.close();
    res.status(201).json({ id: result.lastInsertRowid, symbol, entry_price, target_price, stop_price });
  } catch (err) {
    if (db) db.close();
    console.error('paper-trades POST error:', err);
    res.status(500).json({ error: err.message });
  }
}
