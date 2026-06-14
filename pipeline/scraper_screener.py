import logging
import re
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / 'logs'
SCRAPER_LOG = LOG_DIR / 'scraper_errors.log'

BASE_URL = "https://www.screener.in/company/{symbol}/"


def _log_error(symbol, error_msg):
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().isoformat(timespec='seconds')
    with open(SCRAPER_LOG, 'a') as f:
        f.write(f"{ts} | {symbol} | screener | {error_msg}\n")


def _get_cached(symbol, conn, today):
    """Return cached fundamental data from candidates_log (last 5 trading days)."""
    if conn is None:
        return None
    try:
        rows = conn.execute("""
            SELECT profit_growth, debt_equity, promoter_holding, date
            FROM candidates_log
            WHERE symbol = ? AND date < ? AND profit_growth IS NOT NULL
            ORDER BY date DESC LIMIT 5
        """, (symbol, today)).fetchall()
        if not rows:
            return None
        row = rows[0]
        from datetime import date as dt
        try:
            age = (dt.fromisoformat(today) - dt.fromisoformat(row[3])).days
        except Exception:
            age = 1
        return {
            'profit_growth': row[0] or 0.0,
            'debt_equity': row[1] if row[1] is not None else 99.0,
            'promoter_holding': row[2] or 0.0,
            'quarterly_sales_growth_positive': True,
            'cached': True,
            'cache_age_days': age,
        }
    except Exception as e:
        logging.warning(f"Screener cache lookup failed for {symbol}: {e}")
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

            profit_growth = None
            debt_equity = None
            promoter_holding = None
            quarterly_sales_growth_positive = False
            shares_outstanding = None

            pg_match = re.search(
                r'Profit Growth[^<]*</td>[^<]*<td[^>]*>([^<]+)</td>',
                content, re.IGNORECASE
            )
            if pg_match:
                try:
                    profit_growth = float(pg_match.group(1).replace('%', '').replace(',', '').strip())
                except ValueError:
                    pass

            de_match = re.search(
                r'Debt to equity[^<]*</td>[^<]*<td[^>]*>([^<]+)</td>',
                content, re.IGNORECASE
            )
            if de_match:
                try:
                    debt_equity = float(de_match.group(1).replace(',', '').strip())
                except ValueError:
                    pass

            ph_match = re.search(
                r'Promoters[^<]*</td>[^<]*<td[^>]*>([\d.]+)%',
                content, re.IGNORECASE
            )
            if ph_match:
                try:
                    promoter_holding = float(ph_match.group(1))
                except ValueError:
                    pass

            # Shares outstanding (in Cr shares)
            so_match = re.search(
                r'(?:Shares outstanding|Number of shares)[^<]*</td>[^<]*<td[^>]*>([\d,.]+)',
                content, re.IGNORECASE
            )
            if so_match:
                try:
                    val = float(so_match.group(1).replace(',', '').strip())
                    shares_outstanding = int(val * 1_00_000)  # convert Cr to units
                except ValueError:
                    pass

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
                    'shares_outstanding': shares_outstanding,
                    'cached': False,
                    'cache_age_days': 0,
                }
                logging.info(f"Screener data for {symbol}: {result}")
            else:
                _log_error(symbol, f"no data extracted from {url}")

            await browser.close()
    except Exception as e:
        _log_error(symbol, str(e))
        logging.warning(f"Screener scrape failed for {symbol}: {e}")
        # Fall back to cache
        result = _get_cached(symbol, conn, today)
        if result:
            logging.info(f"Using cached screener data for {symbol} (age {result.get('cache_age_days')}d)")
        else:
            logging.warning(f"No cached data for {symbol} — excluding from Step 2")

    return result
