import logging
import re
from pathlib import Path

LOG_DIR = Path(__file__).parent / 'logs'
SCRAPER_LOG = LOG_DIR / 'scraper_errors.log'

BASE_URL = "https://www.screener.in/company/{symbol}/"


def _log_error(msg):
    LOG_DIR.mkdir(exist_ok=True)
    with open(SCRAPER_LOG, 'a') as f:
        from datetime import datetime
        f.write(f"{datetime.now().isoformat()} SCREENER {msg}\n")


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

            profit_growth = None
            debt_equity = None
            promoter_holding = None
            quarterly_sales_growth_positive = False

            # Profit growth — look for "Profit Growth" row in ratios table
            pg_match = re.search(
                r'Profit Growth[^<]*</td>[^<]*<td[^>]*>([^<]+)</td>',
                content, re.IGNORECASE
            )
            if pg_match:
                try:
                    profit_growth = float(pg_match.group(1).replace('%', '').replace(',', '').strip())
                except ValueError:
                    pass

            # Debt/Equity
            de_match = re.search(
                r'Debt to equity[^<]*</td>[^<]*<td[^>]*>([^<]+)</td>',
                content, re.IGNORECASE
            )
            if de_match:
                try:
                    debt_equity = float(de_match.group(1).replace(',', '').strip())
                except ValueError:
                    pass

            # Promoter holding
            ph_match = re.search(
                r'Promoters[^<]*</td>[^<]*<td[^>]*>([\d.]+)%',
                content, re.IGNORECASE
            )
            if ph_match:
                try:
                    promoter_holding = float(ph_match.group(1))
                except ValueError:
                    pass

            # Quarterly sales growth — check last 2 quarters
            sales_matches = re.findall(
                r'<td class="[^"]*right[^"]*">([\d,]+)</td>',
                content
            )
            if len(sales_matches) >= 2:
                try:
                    q1 = float(sales_matches[-1].replace(',', ''))
                    q2 = float(sales_matches[-2].replace(',', ''))
                    quarterly_sales_growth_positive = q1 > q2
                except ValueError:
                    pass

            if any(v is not None for v in [profit_growth, debt_equity, promoter_holding]):
                result = {
                    'profit_growth': profit_growth or 0.0,
                    'debt_equity': debt_equity if debt_equity is not None else 99.0,
                    'promoter_holding': promoter_holding or 0.0,
                    'quarterly_sales_growth_positive': quarterly_sales_growth_positive,
                }
                logging.info(f"Screener data for {symbol}: {result}")
            else:
                _log_error(f"{symbol}: no data extracted from {url}")

            await browser.close()
    except Exception as e:
        _log_error(f"{symbol}: {e}")
        logging.warning(f"Screener scrape failed for {symbol}: {e}")

    return result
