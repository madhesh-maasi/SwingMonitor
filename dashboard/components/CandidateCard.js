import { useState } from 'react';

const SECTOR_INFO = {
  KPITTECH:  { sector: 'IT',              cap: 'Mid cap' },
  BHEL:      { sector: 'Capital goods',   cap: 'Large cap' },
  HDFCBANK:  { sector: 'Banking',         cap: 'Large cap' },
  TATASTEEL: { sector: 'Metals',          cap: 'Large cap' },
  COALINDIA: { sector: 'Mining',          cap: 'Large cap' },
  INFY:      { sector: 'IT',              cap: 'Large cap' },
  WIPRO:     { sector: 'IT',              cap: 'Large cap' },
  TCS:       { sector: 'IT',              cap: 'Large cap' },
  RELIANCE:  { sector: 'Energy',          cap: 'Large cap' },
  ICICIBANK: { sector: 'Banking',         cap: 'Large cap' },
  SBIN:      { sector: 'Banking',         cap: 'Large cap' },
  AXISBANK:  { sector: 'Banking',         cap: 'Large cap' },
  SUNPHARMA: { sector: 'Pharma',          cap: 'Large cap' },
  BAJFINANCE:{ sector: 'Finance',         cap: 'Large cap' },
  TITAN:     { sector: 'Consumer',        cap: 'Large cap' },
  NTPC:      { sector: 'Power',           cap: 'Large cap' },
  MARUTI:    { sector: 'Auto',            cap: 'Large cap' },
  ONGC:      { sector: 'Energy',          cap: 'Large cap' },
  LTIM:      { sector: 'IT',              cap: 'Large cap' },
};

function Sparkline({ data, isUp }) {
  if (!data || data.length === 0) return null;
  const bars = data.slice(-7);
  const min = Math.min(...bars);
  const max = Math.max(...bars);
  const range = max - min || 1;
  return (
    <div className="sparkline">
      {bars.map((v, i) => {
        const pct = Math.max(12, ((v - min) / range) * 100);
        return (
          <div
            key={i}
            className="spark-bar"
            style={{
              height: `${pct}%`,
              background: isUp ? 'var(--green)' : 'var(--red)',
              opacity: 0.45 + (i / bars.length) * 0.55,
            }}
          />
        );
      })}
    </div>
  );
}

function PriceChange({ pct }) {
  if (pct == null) return null;
  const isUp = pct >= 0;
  return (
    <div className="price-change-row">
      <div className="price-change-dot" style={{ background: isUp ? 'var(--green)' : 'var(--red)' }} />
      <span className={`price-change-pct ${isUp ? 'up' : 'down'}`}>
        {isUp ? '+' : ''}{pct.toFixed(1)}%
      </span>
    </div>
  );
}

function ScoreBar({ label, value, display, max = 100, colorClass }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="score-metric">
      <div className="score-header-row">
        <span className="score-label">{label}</span>
        <span className="score-val">{display ?? value}</span>
      </div>
      <div className="bar-track">
        <div className={`bar-fill ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function consensusPill(consensus, analystCount) {
  const text = analystCount > 0
    ? `${consensus} · ${analystCount} analysts`
    : consensus;
  const lower = (consensus ?? '').toLowerCase();
  const cls = lower.includes('strong buy') || lower === 'buy' ? 'pill-green'
    : lower === 'hold' ? 'pill-amber'
    : lower === 'sell' ? 'pill-red'
    : 'pill-gray';
  return <span className={`pill ${cls}`}>{text}</span>;
}

function fmt(n, decimals = 0) {
  return n?.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export default function CandidateCard({ candidate, isTop, onPaperTrade }) {
  const [adding, setAdding] = useState(false);
  const [added, setAdded]   = useState(false);
  const c = candidate;

  const info = SECTOR_INFO[c.symbol] ?? { sector: c.sector ?? 'Equity', cap: '' };
  const sectorLabel = info.cap ? `${info.sector} — ${info.cap}` : info.sector;

  const sparklineIsUp = true;
  const targetPct = c.close ? ((c.target_price - c.close) / c.close * 100) : 0;
  const stopPct   = c.close ? ((c.stop_price  - c.close) / c.close * 100) : 0;
  const gapSkip   = c.close ? Math.round(c.close * 1.02 * 100) / 100 : 0;
  const entrySkip = c.close ? Math.round(c.close * 1.015 * 100) / 100 : 0;
  const kiteUrl   = `https://kite.zerodha.com/chart/ext/ciq/NSE/${c.symbol}/EQ`;

  async function handleAddTrade() {
    setAdding(true);
    try {
      const resp = await fetch('/api/paper-trades', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: c.symbol, close: c.close }),
      });
      if (resp.ok || resp.status === 409) {
        setAdded(true);
        onPaperTrade?.();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className={`candidate-card${isTop ? ' top-pick' : ''}`}>
      {/* Col 1: Symbol + sector + sparkline */}
      <div className="candidate-col">
        <div className="sym-row">
          <span className="sym-name">{c.symbol}</span>
          {isTop && <span className="top-pick-badge">Top pick</span>}
        </div>
        <div className="sym-sector">{sectorLabel}</div>
        <div className="sparkline-wrap">
          <Sparkline data={c.sparkline} isUp={sparklineIsUp} />
        </div>
      </div>

      {/* Col 2: Price + change */}
      <div className="candidate-col">
        <div className="price-main">₹{fmt(c.close, 2)}</div>
        <PriceChange pct={c.day_change_pct} />
      </div>

      {/* Col 3: Score + RSI bars */}
      <div className="candidate-col">
        <ScoreBar label="Score" value={c.score} display={`${c.score}/100`} max={100} colorClass="bar-green" />
        <ScoreBar label="RSI" value={c.rsi} display={c.rsi?.toFixed(0)} max={100} colorClass="bar-blue" />
      </div>

      {/* Col 4: Badges */}
      <div className="candidate-col">
        <div className="badge-stack">
          <span className="pill pill-blue">Vol {c.volume_ratio?.toFixed(1)}× avg</span>
          <span className="pill pill-blue">Del {c.delivery_pct?.toFixed(0)}%</span>
          {consensusPill(c.analyst_consensus, c.analyst_count ?? 0)}
          {c.cached_data && (
            <span className="pill pill-amber">
              Fundamentals {c.cache_age_days ?? '?'}d old
            </span>
          )}
        </div>
      </div>

      {/* Col 5: Target + stop + ATR + gap skip + entry guidance */}
      <div className="candidate-col">
        <div className="tp-group">
          <div className="tp-price">₹{fmt(c.target_price, 0)}</div>
          <div className="tp-pct">Target +{targetPct.toFixed(1)}%</div>
        </div>
        <div className="tp-group">
          <div className="tp-price red">₹{fmt(c.stop_price, 0)}</div>
          <div className="tp-pct red">Stop {stopPct.toFixed(1)}%</div>
        </div>
        {c.atr14 != null && (
          <div className="atr-badge">ATR ₹{c.atr14.toFixed(0)}</div>
        )}
        <div className="gap-skip-line">
          Gap skip above ₹{fmt(gapSkip, 0)}
        </div>
        <div className="entry-guidance">
          <div className="entry-guidance-desktop">
            <span className="eg-label">Entry window:</span> 10:00 – 10:30 AM IST
            <br />
            <span className="eg-label">Skip if open &gt;</span> ₹{fmt(entrySkip, 0)}
          </div>
          <div className="entry-guidance-mobile">
            Entry: 10–10:30 AM · Skip &gt;₹{fmt(entrySkip, 0)}
          </div>
        </div>
      </div>

      {/* Col 6: Actions */}
      <div className="candidate-col">
        <div className="action-col">
          <a className="btn btn-outline" href={kiteUrl} target="_blank" rel="noreferrer">
            ↗ Open in Kite
          </a>
          <button
            className="btn btn-green"
            onClick={handleAddTrade}
            disabled={adding || added}
          >
            {added ? '✓ Added' : adding ? '…' : '+ Paper trade'}
          </button>
        </div>
      </div>
    </div>
  );
}
