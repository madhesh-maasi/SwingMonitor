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
  const {
    symbol, entry_date, entry_price, target_price, stop_price,
    current_price, days_held, stop_moved_to_breakeven, status, gap_rejected_pct,
  } = trade;

  // Gap-rejected card
  if (status === 'gap_rejected') {
    return (
      <div className="pt-card pt-card-rejected">
        <div className="pt-header">
          <div>
            <div className="pt-sym">{symbol}</div>
            <div className="pt-date-row">Entry {formatDate(entry_date)}</div>
          </div>
          <span className="pt-badge-rejected">Gap Rejected</span>
        </div>
        <div className="pt-cmp-row" style={{ color: 'var(--text-muted)' }}>
          Entry <strong>₹{entry_price?.toFixed(2)}</strong>
          {gap_rejected_pct != null && (
            <> · Opened +{gap_rejected_pct.toFixed(1)}% above entry</>
          )}
        </div>
        <div className="pt-status-row" style={{ color: 'var(--text-muted)' }}>
          <div className="pt-status-dot" style={{ background: 'var(--text-muted)' }} />
          <span>Skipped — gap exceeded 2% threshold</span>
        </div>
      </div>
    );
  }

  const current      = current_price ?? entry_price;
  const days         = days_held ?? dayCount(entry_date);
  const range        = (target_price - stop_price) || 1;
  const currentPct   = Math.min(100, Math.max(0, ((current - stop_price) / range) * 100));
  const entryPct     = Math.min(100, Math.max(0, ((entry_price - stop_price) / range) * 100));
  const pnlPct       = entry_price ? ((current - entry_price) / entry_price * 100) : 0;
  const pnlSign      = pnlPct >= 0 ? '+' : '';
  const isAboveEntry = current >= entry_price;
  const fillLeft     = Math.min(entryPct, currentPct);
  const fillWidth    = Math.abs(currentPct - entryPct);
  const fillColor    = isAboveEntry ? 'var(--green)' : 'var(--amber)';
  const tradeStatus  = getStatus(current, entry_price, stop_price, target_price);

  return (
    <div className="pt-card">
      {/* Header */}
      <div className="pt-header">
        <div>
          <div className="pt-sym">{symbol}</div>
          <div className="pt-date-row">Entry {formatDate(entry_date)} · Day {days} of 21</div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {stop_moved_to_breakeven && (
            <span className="pt-badge-breakeven">Stop at breakeven</span>
          )}
          <span className="pt-badge-open">Open</span>
        </div>
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
          <div
            className="pt-progress-fill"
            style={{ left: `${fillLeft}%`, width: `${fillWidth}%`, background: fillColor, opacity: 0.75 }}
          />
          <div
            className="pt-progress-marker"
            style={{ left: `${entryPct}%`, background: 'var(--text-secondary)' }}
          />
        </div>
        <div className="pt-bar-labels">
          <span>{stop_moved_to_breakeven ? 'BE ₹' : 'Stop ₹'}{stop_price?.toFixed(0)}</span>
          <span className="pt-bar-center" style={{ color: isAboveEntry ? 'var(--green)' : 'var(--red)' }}>
            {pnlSign}{pnlPct.toFixed(1)}%
          </span>
          <span>Target ₹{target_price?.toFixed(0)}</span>
        </div>
      </div>

      {/* Status row */}
      <div className="pt-status-row" style={{ color: tradeStatus.textColor }}>
        <div className="pt-status-dot" style={{ background: tradeStatus.dot }} />
        <span>{pnlSign}{pnlPct.toFixed(1)}% · {tradeStatus.label}</span>
      </div>
    </div>
  );
}
