import path from 'path';
import fs from 'fs';

function getDb() {
  try {
    const Database = require('better-sqlite3');
    const dbPath = path.join(process.cwd(), '..', 'data', 'history.db');
    if (!fs.existsSync(dbPath)) return null;
    return new Database(dbPath, { readonly: true });
  } catch { return null; }
}

function weekStart() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  d.setDate(d.getDate() - (day === 0 ? 6 : day - 1)); // Monday
  return d.toISOString().split('T')[0];
}

export default function handler(req, res) {
  const db = getDb();

  if (!db) {
    const jsonPath = path.join(process.cwd(), 'public', 'data.json');
    if (fs.existsSync(jsonPath)) {
      const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
      return res.status(200).json(data.completed ?? { summary: {}, weekly_summary: {}, trades: [] });
    }
    return res.status(200).json({ summary: {}, weekly_summary: {}, trades: [] });
  }

  try {
    const trades = db.prepare(`
      SELECT symbol, entry_date, exit_date, entry_price, exit_price,
             pnl_pct, status, days_held, gap_rejected_pct
      FROM paper_trades
      WHERE status != 'open'
      ORDER BY exit_date DESC
    `).all();

    const gapRejected = trades.filter(t => t.status === 'gap_rejected');
    const real        = trades.filter(t => t.status !== 'gap_rejected');
    const wins   = real.filter(t => t.pnl_pct > 0);
    const losses = real.filter(t => t.pnl_pct <= 0);
    const total  = real.length;
    const win_rate   = total > 0 ? Math.round((wins.length / total) * 1000) / 10 : 0;
    const avg_gain   = wins.length   > 0 ? Math.round(wins.reduce((s, t) => s + t.pnl_pct, 0)   / wins.length   * 100) / 100 : 0;
    const avg_loss   = losses.length > 0 ? Math.round(losses.reduce((s, t) => s + t.pnl_pct, 0) / losses.length * 100) / 100 : 0;
    const expectancy = Math.round(((win_rate / 100) * avg_gain + (1 - win_rate / 100) * avg_loss) * 100) / 100;

    const ws = weekStart();
    const thisWeek  = trades.filter(t => t.exit_date && t.exit_date >= ws);
    const weekReal  = thisWeek.filter(t => t.status !== 'gap_rejected');
    const weekWins  = weekReal.filter(t => t.pnl_pct > 0);
    const weekWinRate = weekReal.length > 0 ? Math.round((weekWins.length / weekReal.length) * 1000) / 10 : 0;
    const bestTrade  = weekReal.length > 0 ? weekReal.reduce((a, b) => (a.pnl_pct ?? 0) > (b.pnl_pct ?? 0) ? a : b) : null;
    const worstTrade = weekReal.length > 0 ? weekReal.reduce((a, b) => (a.pnl_pct ?? 0) < (b.pnl_pct ?? 0) ? a : b) : null;

    db.close();
    res.status(200).json({
      summary: {
        win_rate, avg_gain, avg_loss, expectancy,
        total_trades: total,
        gap_rejections: gapRejected.length,
      },
      weekly_summary: {
        trades_closed_this_week: weekReal.length,
        week_win_rate: weekWinRate,
        best_trade:  bestTrade  ? { symbol: bestTrade.symbol,  pnl_pct: bestTrade.pnl_pct  } : null,
        worst_trade: worstTrade ? { symbol: worstTrade.symbol, pnl_pct: worstTrade.pnl_pct } : null,
        gap_rejections_this_week: thisWeek.filter(t => t.status === 'gap_rejected').length,
      },
      trades,
    });
  } catch (err) {
    if (db) db.close();
    console.error('completed API error:', err);
    res.status(500).json({ error: err.message });
  }
}
