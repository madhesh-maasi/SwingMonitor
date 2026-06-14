import { useState } from 'react';

function AlertBanner({ message, onDismiss }) {
  if (!message) return null;
  return (
    <div className="alert-banner">
      <span className="alert-icon">⚠</span>
      <span className="alert-text">{message}</span>
      <button className="alert-dismiss" onClick={onDismiss} aria-label="Dismiss">✕</button>
    </div>
  );
}

function RegimeHistoryStrip({ history, isMobile }) {
  const [tooltip, setTooltip]     = useState(null);
  const [mobileSheet, setMobileSheet] = useState(null);

  if (!history || history.length === 0) return null;

  const items = isMobile ? history.slice(-14) : history.slice(-30);

  function colorFor(regime) {
    if (regime === 'GO')      return 'var(--green)';
    if (regime === 'CAUTION') return 'var(--amber)';
    return 'var(--red)';
  }

  function fmtDate(str) {
    if (!str) return '';
    const d = new Date(str);
    const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${String(d.getDate()).padStart(2,'0')} ${m[d.getMonth()]}`;
  }

  return (
    <div className="regime-history-wrap">
      <div className="regime-history-strip">
        {items.map((r, i) => (
          <div
            key={r.date ?? i}
            className="regime-history-bar"
            style={{ background: colorFor(r.regime) }}
            onMouseEnter={() => setTooltip({ ...r, idx: i })}
            onMouseLeave={() => setTooltip(null)}
            onClick={() => setMobileSheet(mobileSheet?.date === r.date ? null : r)}
          />
        ))}
        {/* Desktop tooltip */}
        {tooltip && (
          <div className="regime-tooltip">
            {fmtDate(tooltip.date)} · {tooltip.regime} · Breadth {tooltip.breadth_pct?.toFixed(0)}%
          </div>
        )}
      </div>
      <div className="regime-history-label">30-day market regime</div>

      {/* Mobile bottom sheet */}
      {mobileSheet && (
        <div className="regime-bottom-sheet" onClick={() => setMobileSheet(null)}>
          <div className="rbs-content" onClick={e => e.stopPropagation()}>
            <span style={{ color: colorFor(mobileSheet.regime), fontWeight: 500 }}>
              ● {mobileSheet.regime}
            </span>
            &nbsp;·&nbsp;{fmtDate(mobileSheet.date)}
            &nbsp;·&nbsp;Breadth {mobileSheet.breadth_pct?.toFixed(0)}%
          </div>
        </div>
      )}
    </div>
  );
}

export default function RegimeBar({ regime, regimeHistory, dataIntegrityWarning, integrityWarningMessage }) {
  const [dismissed, setDismissed] = useState(false);
  const [isMobile, setIsMobile]   = useState(false);

  // Detect mobile on mount (client only)
  if (typeof window !== 'undefined' && !isMobile && window.innerWidth < 640) {
    setIsMobile(true);
  }

  if (!regime) return null;

  const r   = regime.regime;
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

  const nifty   = regime.nifty_close?.toLocaleString('en-IN', { maximumFractionDigits: 0 });
  const ema20   = regime.ema20?.toLocaleString('en-IN', { maximumFractionDigits: 0 });
  const breadth = regime.breadth_pct?.toFixed(0);

  return (
    <>
      {dataIntegrityWarning && !dismissed && (
        <AlertBanner
          message={integrityWarningMessage || 'Fundamental data incomplete — verify signals before trading today'}
          onDismiss={() => setDismissed(true)}
        />
      )}
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
      <RegimeHistoryStrip history={regimeHistory} isMobile={isMobile} />
    </>
  );
}
