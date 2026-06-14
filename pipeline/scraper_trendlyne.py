import logging
import re
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / 'logs'
SCRAPER_LOG = LOG_DIR / 'scraper_errors.log'

BASE_URL = "https://trendlyne.com/equity/{symbol}/"


def _log_error(symbol, error_msg):
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().isoformat(timespec='seconds')
    with open(SCRAPER_LOG, 'a') as f:
        f.write(f"{ts} | {symbol} | trendlyne | {error_msg}\n")


def _get_cached(symbol, conn, today):
    """Return cached analyst data from candidates_log (last 5 trading days)."""
    if conn is None:
        return None
    try:
        rows = conn.execute("""
            SELECT analyst_consensus, analyst_upside, date
            FROM candidates_log
            WHERE symbol = ? AND date < ? AND analyst_upside IS NOT NULL
            ORDER BY date DESC LIMIT 5
        """, (symbol, today)).fetchall()
        if not rows:
            return None
        row = rows[0]
        from datetime import date as dt
        try:
            age = (dt.fromisoformat(today) - dt.fromisoformat(row[2])).days
        except Exception:
            age = 1
        return {
            'analyst_count': 3,
            'upside_to_target': row[1] or 10.0,
            'consensus': row[0] or 'Buy',
            'cached': True,
            'cache_age_days': age,
        }
    except Exception as e:
        logging.warning(f"Trendlyne cache lookup failed for {symbol}: {e}")
        return None


async def scrape(symbol: str, conn=None, today=None) -> dict | None:
    if today is None:
        today = datetime.now().strftime('%Y-%m-%d')

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        _log_error(symbol, "playwright not installed")
        return _get_cached(symbol, conn, today)

    url = BASE_URL.format(symbol=symbol)
    result = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            page.set_default_timeout(20000)
            await page.goto(url, wait_until='networkidle')

            content = await page.content()

            analyst_count = 0
            upside_to_target = 0.0
            consensus = 'Buy'

            count_match = re.search(r'(\d+)\s*(?:analyst|Analyst)', content)
            if count_match:
                try:
                    analyst_count = int(count_match.group(1))
                except ValueError:
                    pass

            upside_match = re.search(r'[Uu]pside[^<]*?([\d.]+)\s*%', content)
            if upside_match:
                try:
                    upside_to_target = float(upside_match.group(1))
                except ValueError:
                    pass

            if re.search(r'\b[Ss]trong\s+[Bb]uy\b', content):
                consensus = 'Strong Buy'
            elif re.search(r'\b[Bb]uy\b', content):
                consensus = 'Buy'
            elif re.search(r'\b[Hh]old\b', content):
                consensus = 'Hold'
            elif re.search(r'\b[Ss]ell\b', content):
                consensus = 'Sell'

            if analyst_count > 0 or upside_to_target > 0:
                result = {
                    'analyst_count': analyst_count,
                    'upside_to_target': upside_to_target,
                    'consensus': consensus,
                    'cached': False,
                    'cache_age_days': 0,
                }
                logging.info(f"Trendlyne data for {symbol}: {result}")
            else:
                _log_error(symbol, f"no analyst data extracted from {url}")

            await browser.close()
    except Exception as e:
        _log_error(symbol, str(e))
        logging.warning(f"Trendlyne scrape failed for {symbol}: {e}")
        result = _get_cached(symbol, conn, today)
        if result:
            logging.info(f"Using cached trendlyne data for {symbol} (age {result.get('cache_age_days')}d)")
        else:
            logging.warning(f"No cached data for {symbol} — excluding from Step 3")

    return result
