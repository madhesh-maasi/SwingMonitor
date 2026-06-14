function outcomeDisplay(status) {
  switch (status) {
    case 'target_hit':   return { icon: '🎯', label: 'Target hit',    cls: 'pill-green' };
    case 'stop_hit':     return { icon: '🛑', label: 'Stop hit',      cls: 'pill-red' };
    case 'expired':      return { icon: '⏱',  label: 'Expired',       cls: 'pill-gray' };
    case 'gap_rejected': return { icon: '↷',  label: 'Gap rejected',  cls: 'pill-gray' };
    default:             return { icon: '—',   label: status,          cls: 'pill-gray' };
  }
}

function fmt(n) {
  if (n == null || isNaN(n)) return '—';
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
}

function WeeklySummary({ ws }) {
  if (!ws) return null;
  const cards = [
    {
      label: 'Closed this week',
      value: ws.trades_closed_this_week ?? 0,
      sub: ws.gap_rejections_this_week > 0
        ? `+${ws.gap_rejections_this_week} gap rejected`
        : 'trades',
      green: false,
    },
    {
      label: 'Week win rate',
      value: ws.trades_closed_this_week > 0 ? `${ws.week_win_rate}%` : '—',
      sub: 'Mon – Sun',
      green: (ws.week_win_rate ?? 0) >= 50,
    },
    {
      label: 'Best trade',
      value: ws.best_trade ? ws.best_trade.symbol : '—',
      sub: ws.best_trade ? fmt(ws.best_trade.pnl_pct) : 'no trades this week',
      green: !!ws.best_trade,
    },
    {
      label: 'Worst trade',
      value: ws.worst_trade ? ws.worst_trade.symbol : '—',
      sub: ws.worst_trade ? fmt(ws.worst_trade.pnl_pct) : 'no trades this week',
      green: false,
      red: !!(ws.worst_trade && (ws.worst_trade.pnl_pct ?? 0) < 0),
    },
  ];
  return (
    <div className="weekly-summary-section">
      <div className="section-header" style={{ marginBottom: 10 }}>This week</div>
      <div className="completed-summary weekly-grid">
        {cards.map(card => (
          <div key={card.label} className="summary-card">
            <div className="summary-label">{card.label}</div>
            <div className={`summary-val ${card.green ? 'positive' : card.red ? 'negative' : 'neutral'}`}>
              {card.value}
            </div>
            <div className="summary-sub">{card.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CompletedTable({ data }) {
  const { summary, weekly_summary, trades } = data ?? {};
  const realTrades = (trades ?? []).filter(t => t.outcome !== 'gap_rejected');
  const gapTrades  = (trades ?? []).filter(t => t.outcome === 'gap_rejected');

  return (
    <>
      <WeeklySummary ws={weekly_summary} />

      <div className="completed-summary" style={{ marginTop: 16 }}>
        <div className="summary-card">
          <div className="summary-label">Win rate</div>
          <div className={`summary-val ${(summary?.win_rate ?? 0) >= 50 ? 'positive' : 'negative'}`}>
            {summary?.win_rate ?? '—'}%
          </div>
          <div className="summary-sub">excl. gap rejections</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Avg gain</div>
          <div className="summary-val positive">
            {summary?.avg_gain != null ? `+${summary.avg_gain.toFixed(2)}%` : '—'}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Avg loss</div>
          <div className="summary-val negative">
            {summary?.avg_loss != null ? `${summary.avg_loss.toFixed(2)}%` : '—'}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Expectancy</div>
          <div className={`summary-val ${(summary?.expectancy ?? 0) >= 0 ? 'positive' : 'negative'}`}>
            {summary?.expectancy != null ? fmt(summary.expectancy) : '—'}
          </div>
          {(summary?.gap_rejections ?? 0) > 0 && (
            <div className="summary-sub">{summary.gap_rejections} gap rejected</div>
          )}
        </div>
      </div>

      {(!trades || trades.length === 0) ? (
        <div className="empty-state">No completed trades yet — paper trades close after target, stop, or 21 days.</div>
      ) : (
        <div className="table-scroll-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Entry date</th>
                <th>Exit date</th>
                <th>Entry ₹</th>
                <th>Exit ₹</th>
                <th>P&amp;L %</th>
                <th className="col-days">Days</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => {
                const { icon, label, cls } = outcomeDisplay(t.outcome ?? t.status);
                const pnlCls = (t.pnl_pct ?? 0) >= 0 ? 'pnl-positive' : 'pnl-negative';
                const isGap  = (t.outcome ?? t.status) === 'gap_rejected';
                return (
                  <tr key={i} className={isGap ? 'row-gap-rejected' : ''}>
                    <td><strong>{t.symbol}</strong></td>
                    <td>{t.entry_date}</td>
                    <td>{t.exit_date ?? '—'}</td>
                    <td>₹{t.entry_price?.toFixed(2)}</td>
                    <td>{t.exit_price != null ? `₹${t.exit_price.toFixed(2)}` : '—'}</td>
                    <td className={isGap ? '' : pnlCls}>
                      {isGap ? <span style={{ color: 'var(--text-muted)' }}>—</span> : fmt(t.pnl_pct)}
                    </td>
                    <td className="col-days">{t.days_held ?? '—'}</td>
                    <td><span className={`pill ${cls}`}>{icon} {label}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
