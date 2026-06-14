import { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import RegimeBar from '../components/RegimeBar';
import MetricCards from '../components/MetricCards';
import CandidateCard from '../components/CandidateCard';
import PaperTradeCard from '../components/PaperTradeCard';
import CompletedTable from '../components/CompletedTable';

const TABS = ['Today\'s candidates', 'Paper trades', 'Completed'];

function CandlestickIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="2"  y="6"  width="4" height="7" rx="1" fill="currentColor" opacity="0.6" />
      <line x1="4"  y1="3"  x2="4"  y2="6"  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="4"  y1="13" x2="4"  y2="16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <rect x="12" y="5"  width="4" height="6" rx="1" fill="var(--green)" opacity="0.9" />
      <line x1="14" y1="2"  x2="14" y2="5"  stroke="var(--green)" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="14" y1="11" x2="14" y2="15" stroke="var(--green)" strokeWidth="1.5" strokeLinecap="round" />
      <rect x="7"  y="8"  width="4" height="5" rx="1" fill="currentColor" opacity="0.45" />
      <line x1="9"  y1="5"  x2="9"  y2="8"  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.45" />
      <line x1="9"  y1="13" x2="9"  y2="16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.45" />
    </svg>
  );
}

function RefreshIcon({ spinning }) {
  return (
    <svg
      width="13" height="13" viewBox="0 0 13 13" fill="none"
      className={spinning ? 'spinning' : ''}
      style={{ display: 'inline-block', flexShrink: 0 }}
    >
      <path
        d="M11 6.5A4.5 4.5 0 1 1 6.5 2a4.5 4.5 0 0 1 3.18 1.32L11 2v3.5H7.5l1.3-1.3A3 3 0 1 0 9.5 6.5"
        stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  );
}

function nowLabel() {
  const d = new Date();
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const days   = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ampm = d.getHours() >= 12 ? 'PM' : 'AM';
  const h12 = d.getHours() % 12 || 12;
  return `Updated ${h12}:${mm} ${ampm} IST · ${days[d.getDay()]} ${String(d.getDate()).padStart(2,'0')} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

export default function Home() {
  const [activeTab, setActiveTab]   = useState(0);
  const [candidates, setCandidates] = useState([]);
  const [regime, setRegime]         = useState(null);
  const [metrics, setMetrics]       = useState(null);
  const [paperTrades, setPaperTrades] = useState([]);
  const [completed, setCompleted]   = useState(null);
  const [updatedAt, setUpdatedAt]   = useState('');
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [candRes, ptRes, compRes] = await Promise.all([
        fetch('/api/candidates'),
        fetch('/api/paper-trades'),
        fetch('/api/completed'),
      ]);

      if (candRes.ok) {
        const d = await candRes.json();
        setCandidates(d.candidates ?? []);
        setRegime(d.regime ?? null);
      }

      let winCount = 0, totalClosed = 0, winRate = null;
      if (compRes.ok) {
        const d = await compRes.json();
        setCompleted(d);
        winRate    = d?.summary?.win_rate;
        winCount   = d?.summary ? Math.round((d.summary.win_rate / 100) * d.summary.total_trades) : 0;
        totalClosed = d?.summary?.total_trades ?? 0;
      }

      if (ptRes.ok) {
        const d = await ptRes.json();
        setPaperTrades(d.trades ?? []);
      }

      // Rebuild metrics after both API calls
      setCandidates(prev => {
        setMetrics({
          stocks_scanned:    2418,
          passed_technical:  47,
          final_candidates:  prev.length,
          paper_win_rate:    winRate,
          win_count:         winCount,
          total_closed:      totalClosed,
        });
        return prev;
      });

      setUpdatedAt(nowLabel());
    } catch (e) {
      console.error('fetchAll error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await fetch('/api/refresh', { method: 'POST' });
      await new Promise(r => setTimeout(r, 2500));
      await fetchAll();
    } catch (e) {
      console.error('refresh error:', e);
    } finally {
      setRefreshing(false);
    }
  }

  const openTrades = paperTrades.filter(t => !t.status || t.status === 'open');

  return (
    <>
      <Head>
        <title>SwingMonitor</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </Head>

      {/* Top bar */}
      <header className="topbar">
        <div className="topbar-logo">
          <CandlestickIcon />
          Swing<span className="accent">Monitor</span>
        </div>
        <div className="topbar-right">
          {updatedAt && <span className="badge">{updatedAt}</span>}
          <button className="btn btn-outline" onClick={handleRefresh} disabled={refreshing}>
            <RefreshIcon spinning={refreshing} />
            {refreshing ? 'Running…' : 'Refresh ↗'}
          </button>
        </div>
      </header>

      <main className="container">
        <RegimeBar regime={regime} />
        <MetricCards metrics={metrics} />

        {/* Pill tabs */}
        <div className="tabs">
          {TABS.map((tab, i) => (
            <button
              key={tab}
              className={`tab${activeTab === i ? ' active' : ''}`}
              onClick={() => setActiveTab(i)}
            >
              {tab}
              {i === 1 && openTrades.length > 0 && (
                <span style={{ marginLeft: 5, opacity: 0.65, fontSize: 11 }}>
                  ({openTrades.length})
                </span>
              )}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="loading">Loading…</div>
        ) : (
          <>
            {/* ── Tab 0: Candidates + active paper trades ── */}
            {activeTab === 0 && (
              <>
                <div className="section-header">
                  {candidates.length} candidate{candidates.length !== 1 ? 's' : ''} · ranked by composite score
                </div>

                {candidates.length === 0 ? (
                  <div className="empty-state">
                    No candidates today.{' '}
                    Run <code style={{ fontSize: 11 }}>python3 pipeline/seed_demo.py</code> to load demo data.
                  </div>
                ) : (
                  candidates.map((c, i) => (
                    <CandidateCard
                      key={c.symbol}
                      candidate={c}
                      isTop={i === 0}
                      onPaperTrade={fetchAll}
                    />
                  ))
                )}

                {/* Active paper trades preview below candidates */}
                {openTrades.length > 0 && (
                  <>
                    <div className="section-header" style={{ marginTop: 32 }}>
                      Active paper trades · {openTrades.length} open
                    </div>
                    <div className="pt-grid">
                      {openTrades.map(t => (
                        <PaperTradeCard key={t.id} trade={t} />
                      ))}
                    </div>
                  </>
                )}
              </>
            )}

            {/* ── Tab 1: All paper trades ── */}
            {activeTab === 1 && (
              <>
                <div className="section-header">
                  Active paper trades · {openTrades.length} open
                </div>
                {openTrades.length === 0 ? (
                  <div className="empty-state">
                    No open paper trades — click "+ Paper trade" on any candidate.
                  </div>
                ) : (
                  <div className="pt-grid">
                    {openTrades.map(t => (
                      <PaperTradeCard key={t.id} trade={t} />
                    ))}
                  </div>
                )}
              </>
            )}

            {/* ── Tab 2: Completed ── */}
            {activeTab === 2 && (
              <CompletedTable data={completed} />
            )}
          </>
        )}
      </main>

      <footer className="footer">
        Personal use only · Not SEBI-registered investment advice · Always verify signals before trading
      </footer>
    </>
  );
}
