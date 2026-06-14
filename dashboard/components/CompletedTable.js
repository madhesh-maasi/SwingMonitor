function outcomeDisplay(status) {
  switch (status) {
    case 'target_hit': return { icon: '🎯', label: 'Target hit', cls: 'pill-green' };
    case 'stop_hit':   return { icon: '🛑', label: 'Stop hit',   cls: 'pill-red' };
    case 'expired':    return { icon: '⏱', label: 'Expired',     cls: 'pill-gray' };
    default:           return { icon: '—',  label: status,        cls: 'pill-gray' };
  }
}

function fmt(n) {
  if (n == null || isNaN(n)) return '—';
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
}

export default function CompletedTable({ data }) {
  const { summary, trades } = data ?? {};

  return (
    <>
      <div className="completed-summary">
        <div className="summary-card">
          <div className="summary-label">Win rate</div>
          <div className={`summary-val ${(summary?.win_rate ?? 0) >= 50 ? 'positive' : 'negative'}`}>
            {summary?.win_rate ?? '—'}%
          </div>
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
        </div>
      </div>

      {(!trades || trades.length === 0) ? (
        <div className="empty-state">No completed trades yet — paper trades close after target, stop, or 21 days.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Entry date</th>
              <th>Exit date</th>
              <th>Entry ₹</th>
              <th>Exit ₹</th>
              <th>P&amp;L %</th>
              <th>Days</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => {
              const { icon, label, cls } = outcomeDisplay(t.outcome ?? t.status);
              const pnlCls = (t.pnl_pct ?? 0) >= 0 ? 'pnl-positive' : 'pnl-negative';
              return (
                <tr key={i}>
                  <td><strong>{t.symbol}</strong></td>
                  <td>{t.entry_date}</td>
                  <td>{t.exit_date ?? '—'}</td>
                  <td>₹{t.entry_price?.toFixed(2)}</td>
                  <td>₹{t.exit_price?.toFixed(2) ?? '—'}</td>
                  <td className={pnlCls}>{fmt(t.pnl_pct)}</td>
                  <td>{t.days_held ?? '—'}</td>
                  <td><span className={`pill ${cls}`}>{icon} {label}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}
