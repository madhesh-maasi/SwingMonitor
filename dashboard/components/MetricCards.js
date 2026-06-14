export default function MetricCards({ metrics }) {
  const {
    stocks_scanned, passed_technical, final_candidates, paper_win_rate,
    win_count, total_closed,
  } = metrics ?? {};

  const passedPct = stocks_scanned && passed_technical
    ? ((passed_technical / stocks_scanned) * 100).toFixed(1)
    : null;

  const cards = [
    {
      label: 'Stocks scanned',
      value: stocks_scanned?.toLocaleString('en-IN') ?? '—',
      sublabel: 'NSE EQ series',
      green: false,
    },
    {
      label: 'Passed technical',
      value: passed_technical?.toLocaleString('en-IN') ?? '—',
      sublabel: passedPct ? `Step 1 → ${passedPct}% of universe` : 'Step 1 filter',
      green: false,
    },
    {
      label: 'Final candidates',
      value: final_candidates ?? '—',
      sublabel: 'All 3 steps cleared',
      green: false,
    },
    {
      label: 'Paper win rate',
      value: paper_win_rate != null ? `${paper_win_rate}%` : '—',
      sublabel: win_count != null && total_closed != null
        ? `${win_count} of ${total_closed} closed trades`
        : 'Closed trades',
      green: true,
    },
  ];

  return (
    <div className="metric-grid">
      {cards.map(card => (
        <div key={card.label} className="metric-card">
          <div className="metric-label">{card.label}</div>
          <div className={`metric-value${card.green ? ' green' : ''}`}>{card.value}</div>
          <div className="metric-sublabel">{card.sublabel}</div>
        </div>
      ))}
    </div>
  );
}
