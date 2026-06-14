# SwingMonitor

Personal NSE/BSE swing trade dashboard — 3-step scanner, paper trading, EOD pipeline.

## Quick start

### 1. Python environment

```bash
cd swing-monitor
python3 -m venv .venv && source .venv/bin/activate
pip install requests pandas playwright python-dotenv
playwright install chromium
```

### 2. Seed demo data

```bash
python3 pipeline/seed_demo.py
```

This creates `data/history.db` with 90 days of OHLCV for 5 symbols, 3 open paper
trades, 10 completed trades, and today's candidates.  It also writes
`dashboard/public/data.json` so the UI is immediately populated.

### 3. Start the dashboard

```bash
cd dashboard
npm install
npm run dev        # http://localhost:3001
```

### 4. Run the live pipeline (manual)

```bash
cd swing-monitor
python3 pipeline/run_pipeline.py
```

Requires internet access to download NSE bhavdata and Playwright for scraping.
Scrapers return `None` gracefully on failure — the pipeline always completes.

---

## Cron setup (daily at 4:30 PM IST)

```bash
crontab -e
```

Paste this line (replace `/YOUR/PATH`):

```
30 11 * * 1-5 cd /YOUR/PATH/swing-monitor && python3 pipeline/run_pipeline.py >> pipeline/logs/cron.log 2>&1
```

Save (`Esc → :wq` in vi, or `Ctrl+O → Ctrl+X` in nano).

Verify with `crontab -l`.

---

## Market cap list

`data/market_caps.csv` ships with the top 25 NSE stocks. To refresh weekly:

1. Download the NSE market cap file from nseindia.com → Products → Historical Data
2. Save as `data/market_caps.csv` with columns `symbol,market_cap_cr`

Or add any symbol manually; stocks not in the file pass the filter by default when
the file is missing/empty (scanner logs a warning).

---

## Folder structure

```
swing-monitor/
├── pipeline/
│   ├── download.py           Download NSE EOD CSV → SQLite
│   ├── indicators.py         EMA20, RSI14, Volume, Breadth
│   ├── scanner.py            3-step filter + scoring
│   ├── paper_trades.py       Auto-track paper trades
│   ├── scraper_screener.py   Playwright → Screener.in fundamentals
│   ├── scraper_trendlyne.py  Playwright → Trendlyne analyst data
│   ├── run_pipeline.py       Master runner
│   └── seed_demo.py          Demo data seeder
├── data/
│   ├── history.db            SQLite (auto-created)
│   └── market_caps.csv       NSE market cap list
├── dashboard/                Next.js app (port 3001)
│   ├── pages/
│   │   ├── index.js
│   │   └── api/
│   │       ├── candidates.js
│   │       ├── paper-trades.js
│   │       ├── completed.js
│   │       └── refresh.js
│   ├── components/
│   │   ├── RegimeBar.js
│   │   ├── MetricCards.js
│   │   ├── CandidateCard.js
│   │   ├── PaperTradeCard.js
│   │   └── CompletedTable.js
│   └── styles/globals.css
├── crontab.txt
└── README.md
```

---

## Paper trade rules

| Event | Trigger | Exit |
|-------|---------|------|
| Target hit | Daily high ≥ target | At target price |
| Stop hit | Daily low ≤ stop | At stop price |
| Expired | Days held ≥ 21 | At today's close |

Target = entry × 1.12 (12% upside)  
Stop = entry × 0.94 (6% downside → 1:2 risk-reward)

---

## Logs

- Daily pipeline: `pipeline/logs/YYYY-MM-DD.log`  
- Scraper errors: `pipeline/logs/scraper_errors.log`
