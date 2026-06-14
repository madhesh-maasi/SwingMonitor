function formatDate(str) {
  if (!str) return '';
  const d = new Date(str);
  const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${String(d.getDate()).padStart(2, '0')} ${m[d.getMonth()]}`;
}

function dayCount(entryDate) {
  if (!entryDate) return 0;
  const diff = Date.now() - new Date(entryDate).getTime();
  return Math.max(0, Math.floor(diff / 86400000));
}

function getStatus(current, entry, stop, target) {
  if (current == null) return { label: 'No price', dot: 'var(--text-muted)', textColor: 'var(--text-muted)' };
  if (current >= target * 0.97)  return { label: 'Near target',  dot: 'var(--green)', textColor: 'var(--green)' };
  if (current > entry)           return { label: 'Progressing',  dot: 'var(--green)', textColor: 'var(--green)' };
  if (current <= stop * 1.03)    return { label: 'Near stop',    dot: 'var(--red)',   textColor: 'var(--red)' };
  return                                { label: 'Watching',      dot: 'var(--amber)', textColor: 'var(--amber)' };
}

export default function PaperTradeCard({ trade }) {
  const { symbol, entry_date, entry_price, target_price, stop_price, current_price, days_held } = trade;

  const current = current_price ?? entry_price;
  const days    = days_held ?? dayCount(entry_date);

  const range       = (target_price - stop_price) || 1;
  const currentPct  = Math.min(100, Math.max(0, ((current - stop_price) / range) * 100));
  const entryPct    = Math.min(100, Math.max(0, ((entry_price - stop_price) / range) * 100));

  const pnlPct      = entry_price ? ((current - entry_price) / entry_price * 100) : 0;
  const pnlSign     = pnlPct >= 0 ? '+' : '';
  const isAboveEntry = current >= entry_price;

  const fillLeft  = Math.min(entryPct, currentPct);
  const fillWidth = Math.abs(currentPct - entryPct);
  const fillColor = isAboveEntry ? 'var(--green)' : 'var(--amber)';

  const status = getStatus(current, entry_price, stop_price, target_price);

  return (
    <div className="pt-card">
      {/* Header */}
      <div className="pt-header">
        <div>
          <div className="pt-sym">{symbol}</div>
          <div className="pt-date-row">Entry {formatDate(entry_date)} · Day {days} of 21</div>
        </div>
        <span className="pt-badge-open">Open</span>
      </div>

      {/* Entry · CMP */}
      <div className="pt-cmp-row">
        Entry <strong>₹{entry_price?.toFixed(2)}</strong>
        {' · '}
        CMP <strong style={{ color: isAboveEntry ? 'var(--green)' : 'var(--red)' }}>
          ₹{current?.toFixed(2)}
        </strong>
      </div>

      {/* Progress bar */}
      <div className="pt-progress-wrap">
        <div className="pt-progress-track">
          {/* Fill between entry and current */}
          <div
            className="pt-progress-fill"
            style={{ left: `${fillLeft}%`, width: `${fillWidth}%`, background: fillColor, opacity: 0.75 }}
          />
          {/* Entry marker */}
          <div
            className="pt-progress-marker"
            style={{ left: `${entryPct}%`, background: 'var(--text-secondary)' }}
          />
        </div>

        {/* Bar labels */}
        <div className="pt-bar-labels">
          <span>Stop ₹{stop_price?.toFixed(0)}</span>
          <span
            className="pt-bar-center"
            style={{ color: isAboveEntry ? 'var(--green)' : 'var(--red)' }}
          >
            {pnlSign}{pnlPct.toFixed(1)}%
          </span>
          <span>Target ₹{target_price?.toFixed(0)}</span>
        </div>
      </div>

      {/* Status row */}
      <div className="pt-status-row" style={{ color: status.textColor }}>
        <div className="pt-status-dot" style={{ background: status.dot }} />
        <span>{pnlSign}{pnlPct.toFixed(1)}% · {status.label}</span>
      </div>
    </div>
  );
}
