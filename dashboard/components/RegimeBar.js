export default function RegimeBar({ regime }) {
  if (!regime) return null;

  const r = regime.regime;
  const cls = r === 'GO' ? 'go' : r === 'CAUTION' ? 'caution' : 'avoid';

  const titleMap = {
    GO:      'GO — Market regime is bullish',
    CAUTION: 'CAUTION — Reduce position sizes',
    AVOID:   'AVOID — Stay in cash',
  };
  const subMap = {
    GO:      'Nifty 50 above 20-day EMA · Breadth expanding',
    CAUTION: 'Nifty near EMA · Mixed breadth signals',
    AVOID:   'Nifty below EMA · Broad market weakness',
  };

  const nifty = regime.nifty_close?.toLocaleString('en-IN', { maximumFractionDigits: 0 });
  const ema20 = regime.ema20?.toLocaleString('en-IN', { maximumFractionDigits: 0 });
  const breadth = regime.breadth_pct?.toFixed(0);

  return (
    <div className={`regime-bar ${cls}`}>
      <div className="regime-dot" />
      <div className="regime-main">
        <div className="regime-title">{titleMap[r] ?? r}</div>
        <div className="regime-subtitle">{subMap[r]}</div>
      </div>
      <div className="regime-stats">
        <div className="regime-stat">
          <span className="regime-stat-val">{breadth}%</span>
          <span className="regime-stat-label">Breadth</span>
        </div>
        <div className="regime-stat">
          <span className="regime-stat-val">{nifty}</span>
          <span className="regime-stat-label">Nifty 50</span>
        </div>
        <div className="regime-stat">
          <span className="regime-stat-val">{ema20}</span>
          <span className="regime-stat-label">EMA 20</span>
        </div>
      </div>
    </div>
  );
}
