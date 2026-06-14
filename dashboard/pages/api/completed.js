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

export default function handler(req, res) {
  const db = getDb();

  if (!db) {
    const jsonPath = path.join(process.cwd(), 'public', 'data.json');
    if (fs.existsSync(jsonPath)) {
      const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
      return res.status(200).json(data.completed ?? { summary: {}, trades: [] });
    }
    return res.status(200).json({ summary: {}, trades: [] });
  }

  try {
    const trades = db.prepare(`
      SELECT symbol, entry_date, exit_date, entry_price, exit_price,
             pnl_pct, status, days_held
      FROM paper_trades
      WHERE status != 'open'
      ORDER BY exit_date DESC
    `).all();

    const wins   = trades.filter(t => t.pnl_pct > 0);
    const losses = trades.filter(t => t.pnl_pct <= 0);
    const total  = trades.length;
    const win_rate  = total > 0 ? Math.round((wins.length / total) * 1000) / 10 : 0;
    const avg_gain  = wins.length  > 0 ? Math.round(wins.reduce((s, t) => s + t.pnl_pct, 0)   / wins.length  * 100) / 100 : 0;
    const avg_loss  = losses.length > 0 ? Math.round(losses.reduce((s, t) => s + t.pnl_pct, 0) / losses.length * 100) / 100 : 0;
    const expectancy = Math.round(((win_rate / 100) * avg_gain + (1 - win_rate / 100) * avg_loss) * 100) / 100;

    db.close();
    res.status(200).json({
      summary: { win_rate, avg_gain, avg_loss, expectancy, total_trades: total },
      trades,
    });
  } catch (err) {
    if (db) db.close();
    console.error('completed API error:', err);
    res.status(500).json({ error: err.message });
  }
}
