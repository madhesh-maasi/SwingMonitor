import logging
import re
from pathlib import Path

LOG_DIR = Path(__file__).parent / 'logs'
SCRAPER_LOG = LOG_DIR / 'scraper_errors.log'

BASE_URL = "https://trendlyne.com/equity/{symbol}/"


def _log_error(msg):
    LOG_DIR.mkdir(exist_ok=True)
    with open(SCRAPER_LOG, 'a') as f:
        from datetime import datetime
        f.write(f"{datetime.now().isoformat()} TRENDLYNE {msg}\n")


async def scrape(symbol: str) -> dict | None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        _log_error(f"{symbol}: playwright not installed")
        return None

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

            # Analyst count
            count_match = re.search(
                r'(\d+)\s*(?:analyst|Analyst)',
                content
            )
            if count_match:
                try:
                    analyst_count = int(count_match.group(1))
                except ValueError:
                    pass

            # Upside to target
            upside_match = re.search(
                r'[Uu]pside[^<]*?([\d.]+)\s*%',
                content
            )
            if upside_match:
                try:
                    upside_to_target = float(upside_match.group(1))
                except ValueError:
                    pass

            # Consensus: look for Buy/Hold/Sell ratio
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
                }
                logging.info(f"Trendlyne data for {symbol}: {result}")
            else:
                _log_error(f"{symbol}: no analyst data extracted from {url}")

            await browser.close()
    except Exception as e:
        _log_error(f"{symbol}: {e}")
        logging.warning(f"Trendlyne scrape failed for {symbol}: {e}")

    return result
