"""
GISAID Data Source Accessor

Provides programmatic access to genomic surveillance data from GISAID
(Global Initiative on Sharing All Influenza Data).

GISAID is the world's largest database for genomic data of influenza viruses
and other priority pathogens, with 22M+ sequence submissions from 222+ countries.

Data Source: https://gisaid.org/
Portal: https://app1.epicov.org/epi3/start
Registration: https://gisaid.org/register/

**Authentication**: Free registration required with personal identification
and agreement to GISAID Database Access Agreement (DAA).

**Access method**: Uses Playwright browser automation to interact with GISAID's
web interface (no official REST API available). All browser operations run in a
dedicated thread to avoid conflicts with Jupyter's asyncio event loop.

Supported Databases:
- EpiCoV: SARS-CoV-2 / COVID-19 (15M+ sequences)
- EpiFlu: Influenza A, B, C viruses (all subtypes)
- EpiPox: Mpox virus (MPXV)
- EpiRSV: Respiratory Syncytial Virus (A and B subgroups)
- EpiArbo: Arboviruses (DENV, ZIKV, CHIKV, YFV)

Author: Flavio Codeco Coelho
License: MIT
"""

import concurrent.futures
import contextlib
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pandas as pd

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Playwright availability check (lazy, to avoid import-time event loop capture)
# ============================================================================

_playwright_imported = False
_has_playwright = None


def _check_playwright() -> bool:
    """Lazily check if Playwright is available."""
    global _has_playwright
    if _has_playwright is None:
        try:
            import playwright  # noqa: F401
            _has_playwright = True
        except ImportError:
            _has_playwright = False
    return _has_playwright


def _ensure_playwright() -> None:
    """Ensure Playwright is available, raising a helpful error if not."""
    if not _check_playwright():
        raise ImportError(
            "Playwright is required for GISAID access. Install with:\n"
            "    pip install epidatasets[gisaid]\n"
            "    playwright install chromium\n\n"
            "Or install directly:\n"
            "    pip install playwright>=1.40\n"
            "    playwright install chromium"
        )


# ============================================================================
# GISAID Location Hierarchy
# ============================================================================

GISAID_LOCATIONS: dict[str, dict[str, dict[str, str]]] = {
    "Africa": {
        "regions": {
            "Algeria": "DZA", "Angola": "AGO", "Benin": "BEN",
            "Botswana": "BWA", "Burkina Faso": "BFA", "Burundi": "BDI",
            "Cameroon": "CMR", "Cape Verde": "CPV",
            "Central African Republic": "CAF", "Chad": "TCD", "Comoros": "COM",
            "Congo": "COG", "Cote d'Ivoire": "CIV",
            "Democratic Republic of the Congo": "COD", "Djibouti": "DJI",
            "Egypt": "EGY", "Equatorial Guinea": "GNQ", "Eritrea": "ERI",
            "Eswatini": "SWZ", "Ethiopia": "ETH", "Gabon": "GAB",
            "Gambia": "GMB", "Ghana": "GHA", "Guinea": "GIN",
            "Guinea-Bissau": "GNB", "Kenya": "KEN", "Lesotho": "LSO",
            "Liberia": "LBR", "Libya": "LBY", "Madagascar": "MDG",
            "Malawi": "MWI", "Mali": "MLI", "Mauritania": "MRT",
            "Mauritius": "MUS", "Mayotte": "MYT", "Morocco": "MAR",
            "Mozambique": "MOZ", "Namibia": "NAM", "Niger": "NER",
            "Nigeria": "NGA", "Republic of the Congo": "COG", "Reunion": "REU",
            "Rwanda": "RWA", "Sao Tome and Principe": "STP", "Senegal": "SEN",
            "Seychelles": "SYC", "Sierra Leone": "SLE", "Somalia": "SOM",
            "South Africa": "ZAF", "South Sudan": "SSD", "Sudan": "SDN",
            "Tanzania": "TZA", "Togo": "TGO", "Tunisia": "TUN",
            "Uganda": "UGA", "Western Sahara": "ESH", "Zambia": "ZMB",
            "Zimbabwe": "ZWE",
        }
    },
    "Asia": {
        "regions": {
            "Afghanistan": "AFG", "Armenia": "ARM", "Azerbaijan": "AZE",
            "Bahrain": "BHR", "Bangladesh": "BGD", "Bhutan": "BTN",
            "Brunei": "BRN", "Cambodia": "KHM", "China": "CHN",
            "Georgia": "GEO", "Hong Kong": "HKG", "India": "IND",
            "Indonesia": "IDN", "Iran": "IRN", "Iraq": "IRQ",
            "Israel": "ISR", "Japan": "JPN", "Jordan": "JOR",
            "Kazakhstan": "KAZ", "Kuwait": "KWT", "Kyrgyzstan": "KGZ",
            "Laos": "LAO", "Lebanon": "LBN", "Macau": "MAC",
            "Malaysia": "MYS", "Maldives": "MDV", "Mongolia": "MNG",
            "Myanmar": "MMR", "Nepal": "NPL", "Oman": "OMN",
            "Pakistan": "PAK", "Palestine": "PSE", "Philippines": "PHL",
            "Qatar": "QAT", "Saudi Arabia": "SAU", "Singapore": "SGP",
            "South Korea": "KOR", "Sri Lanka": "LKA", "Syria": "SYR",
            "Taiwan": "TWN", "Tajikistan": "TJK", "Thailand": "THA",
            "Timor-Leste": "TLS", "Turkey": "TUR",
            "United Arab Emirates": "ARE", "Uzbekistan": "UZB",
            "Vietnam": "VNM", "Yemen": "YEM",
        }
    },
    "Europe": {
        "regions": {
            "Albania": "ALB", "Andorra": "AND", "Austria": "AUT",
            "Belarus": "BLR", "Belgium": "BEL",
            "Bosnia and Herzegovina": "BIH", "Bulgaria": "BGR",
            "Croatia": "HRV", "Cyprus": "CYP", "Czech Republic": "CZE",
            "Denmark": "DNK", "Estonia": "EST", "Finland": "FIN",
            "France": "FRA", "Germany": "DEU", "Gibraltar": "GIB",
            "Greece": "GRC", "Hungary": "HUN", "Iceland": "ISL",
            "Ireland": "IRL", "Italy": "ITA", "Kosovo": "XKX",
            "Latvia": "LVA", "Liechtenstein": "LIE", "Lithuania": "LTU",
            "Luxembourg": "LUX", "Malta": "MLT", "Moldova": "MDA",
            "Monaco": "MCO", "Montenegro": "MNE", "Netherlands": "NLD",
            "North Macedonia": "MKD", "Norway": "NOR", "Poland": "POL",
            "Portugal": "PRT", "Romania": "ROU", "Russia": "RUS",
            "San Marino": "SMR", "Serbia": "SRB", "Slovakia": "SVK",
            "Slovenia": "SVN", "Spain": "ESP", "Sweden": "SWE",
            "Switzerland": "CHE", "Ukraine": "UKR",
            "United Kingdom": "GBR", "Vatican City": "VAT",
        }
    },
    "North America": {
        "regions": {
            "Anguilla": "AIA", "Antigua and Barbuda": "ATG",
            "Aruba": "ABW", "Bahamas": "BHS", "Barbados": "BRB",
            "Belize": "BLZ", "Bermuda": "BMU", "Bonaire": "BES",
            "British Virgin Islands": "VGB", "Canada": "CAN",
            "Cayman Islands": "CYM", "Costa Rica": "CRI", "Cuba": "CUB",
            "Curacao": "CUW", "Dominica": "DMA",
            "Dominican Republic": "DOM", "El Salvador": "SLV",
            "Greenland": "GRL", "Grenada": "GRD", "Guadeloupe": "GLP",
            "Guatemala": "GTM", "Haiti": "HTI", "Honduras": "HND",
            "Jamaica": "JAM", "Martinique": "MTQ", "Mexico": "MEX",
            "Montserrat": "MSR", "Nicaragua": "NIC", "Panama": "PAN",
            "Puerto Rico": "PRI", "Saint Barthelemy": "BLM",
            "Saint Kitts and Nevis": "KNA", "Saint Lucia": "LCA",
            "Saint Martin": "MAF",
            "Saint Vincent and the Grenadines": "VCT",
            "Sint Maarten": "SXM", "Trinidad and Tobago": "TTO",
            "Turks and Caicos Islands": "TCA", "USA": "USA",
        }
    },
    "Oceania": {
        "regions": {
            "Australia": "AUS", "Fiji": "FJI",
            "French Polynesia": "PYF", "Guam": "GUM",
            "New Caledonia": "NCL", "New Zealand": "NZL",
            "Papua New Guinea": "PNG", "Samoa": "WSM",
            "Solomon Islands": "SLB", "Vanuatu": "VUT",
            "Wallis and Futuna": "WLF",
        }
    },
    "South America": {
        "regions": {
            "Argentina": "ARG", "Bolivia": "BOL", "Brazil": "BRA",
            "Chile": "CHL", "Colombia": "COL", "Ecuador": "ECU",
            "Falkland Islands": "FLK", "French Guiana": "GUF",
            "Guyana": "GUY", "Paraguay": "PRY", "Peru": "PER",
            "Suriname": "SUR", "Uruguay": "URY", "Venezuela": "VEN",
        }
    },
}


# ============================================================================
# GISAID Accessor
# ============================================================================


class GISAIDAccessor(BaseAccessor):
    """Accessor for GISAID genomic surveillance databases.

    Provides programmatic access to genomic sequence data and metadata from
    GISAID's EpiCoV, EpiFlu, EpiPox, EpiRSV, and EpiArbo databases.

    **Authentication**: Free GISAID registration required.
    Register at https://gisaid.org/register/

    **Important**: Users must agree to and comply with the GISAID Database
    Access Agreement (DAA).

    **Browser automation**: All Playwright operations run in a dedicated
    thread to ensure compatibility with Jupyter / IPython environments.

    Example:
        >>> gisaid = GISAIDAccessor(
        ...     database="EpiCoV",
        ...     username="your_username",
        ...     password="your_password",
        ... )
        >>> df = gisaid.query(location="Brazil", lineage="JN.1", nrows=100)
    """

    source_name: ClassVar[str] = "gisaid"
    source_description: ClassVar[str] = (
        "GISAID - Global Initiative on Sharing All Influenza Data. "
        "World's largest genomic database for influenza, SARS-CoV-2, "
        "mpox, RSV, and arboviruses. 22M+ sequences from 222+ countries."
    )
    source_url: ClassVar[str] = "https://gisaid.org/"

    LOGIN_URL = "https://app1.epicov.org/epi3/start"
    SEARCH_URL = "https://www.epicov.org/epi3/frontend"

    DATABASES: ClassVar[dict[str, dict[str, str]]] = {
        "EpiCoV": {
            "name": "EpiCoV",
            "description": "SARS-CoV-2 / COVID-19 genomic surveillance",
            "pathogens": "SARS-CoV-2 (hCoV-19)",
            "records": "15M+ sequences",
            "features": "Pango lineage, GISAID clade, variant monitoring",
        },
        "EpiFlu": {
            "name": "EpiFlu",
            "description": "Influenza virus genomic surveillance",
            "pathogens": "Influenza A, B, C (all subtypes)",
            "records": "Millions of sequences",
            "features": "WHO GISRS integration, vaccine strain selection",
        },
        "EpiPox": {
            "name": "EpiPox",
            "description": "Mpox virus genomic surveillance",
            "pathogens": "Monkeypox virus (MPXV)",
            "records": "Global surveillance data",
            "features": "Clade Ia, Ib, IIa, IIb tracking",
        },
        "EpiRSV": {
            "name": "EpiRSV",
            "description": "Respiratory Syncytial Virus surveillance",
            "pathogens": "RSV A and B subgroups",
            "records": "Global RSV surveillance data",
            "features": "Subgroup classification, seasonal tracking",
        },
        "EpiArbo": {
            "name": "EpiArbo",
            "description": "Arbovirus genomic surveillance (early access)",
            "pathogens": "Dengue (DENV), Zika (ZIKV), Chikungunya (CHIKV), YFV",
            "records": "Global arbovirus data",
            "features": "Serotype tracking, phylogeography",
        },
    }

    def __init__(
        self,
        database: str = "EpiCoV",
        username: str | None = None,
        password: str | None = None,
        config_path: str | Path | None = None,
        cache_dir: str | None = None,
        cache_ttl: int = 24,
        rate_limit: float = 3.0,
        headless: bool = True,
        timeout: int = 120,
        debug: bool = False,
    ):
        """Initialize GISAID accessor.

        Args:
            database: Database ('EpiCoV', 'EpiFlu', 'EpiPox', 'EpiRSV', 'EpiArbo').
            username: GISAID username (email). If None, loaded from env
                      vars, config file, or an interactive prompt.
            password: GISAID password. Same resolution as *username*.
            config_path: Path to JSON config file with credentials.
            cache_dir: Directory for local data cache.
            cache_ttl: Cache time-to-live in hours (default: 24).
            rate_limit: Seconds between requests (default: 3.0).
            headless: Run browser in headless mode (default: True).
            timeout: Browser operation timeout in seconds (default: 120).
            debug: Save screenshots and page source to cache_dir on errors.

        Credentials resolution order:

        1. ``username`` / ``password`` constructor arguments
        2. ``GISAID_USERNAME`` / ``GISAID_PASSWORD`` environment variables
        3. Config file at ``~/.config/epi_data/gisaid.json``::

               {"username": "you@example.org", "password": "secret"}

        4. **Interactive prompt** — if none of the above are available,
           the accessor will ask you to type your credentials at runtime.

        Register for a free GISAID account at https://gisaid.org/register/
        """
        _ensure_playwright()

        if database not in self.DATABASES:
            raise ValueError(
                f"Database '{database}' not supported. "
                f"Choose from: {list(self.DATABASES.keys())}"
            )

        self.database = database
        self.database_info = self.DATABASES[database]
        self._headless = headless
        self._timeout = timeout * 1000
        self._rate_limit = rate_limit
        self._last_request_time = 0.0

        self.username, self.password = self._load_credentials(
            username, password, config_path
        )

        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "gisaid"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=cache_ttl)
        self._debug = debug

        # Thread-based Playwright isolation (avoids Jupyter asyncio conflicts)
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._browser_ready = False

        logger.info("Initialized GISAID accessor for %s database", database)

    # ====================================================================
    # Debug helpers
    # ====================================================================

    def _debug_dump(self, label: str) -> None:
        """Save page source and screenshot for debugging GISAID DOM."""
        if not self._debug:
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = label.replace(" ", "_").replace("/", "_")

            html_path = self.cache_dir / f"debug_{safe}_{ts}.html"
            png_path = self.cache_dir / f"debug_{safe}_{ts}.png"
            txt_path = self.cache_dir / f"debug_{safe}_{ts}.txt"

            self._page.screenshot(path=str(png_path))
            html = self._page.content()
            html_path.write_text(str(html), encoding="utf-8", errors="replace")

            buttons = self._page.locator(
                "button, input[type='submit'], input[type='button'], "
                "input[type='image'], a.button, [role='button']"
            )
            btn_info = []
            for i in range(min(buttons.count(), 50)):
                try:
                    b = buttons.nth(i)
                    tag = b.evaluate("el => el.tagName")
                    txt = b.inner_text().strip()[:80]
                    name = b.get_attribute("name") or ""
                    val = b.get_attribute("value") or ""
                    cls = b.get_attribute("class") or ""
                    bid = b.get_attribute("id") or ""
                    btn_info.append(
                        f"<{tag}> text='{txt}' name='{name}' "
                        f"value='{val}' class='{cls}' id='{bid}'"
                    )
                except Exception:
                    pass
            txt_path.write_text(
                f"=== Page title: {self._page.title()} ===\n"
                + "\n".join(btn_info),
                encoding="utf-8",
            )

            logger.info("Debug dump saved to %s", png_path.parent)
        except Exception as e:
            logger.warning("Failed to write debug dump: %s", e)

    def _debug_dump_raw(self, label: str, content: str) -> None:
        """Save raw HTML/text content for debugging."""
        if not self._debug:
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = label.replace(" ", "_").replace("/", "_")
            path = self.cache_dir / f"debug_{safe}_{ts}.html"
            path.write_text(content[:200000], encoding="utf-8", errors="replace")
            logger.info("Debug raw saved: %s (%d chars)", path.name, len(content))
        except Exception:
            pass

    @staticmethod
    def _extract_sid(html: str) -> str:
        """Try multiple patterns to extract the GISAID session ID."""
        patterns = [
            r'name="sid"\s+value=\'([^\']*)\'',
            r'name="sid"\s+value="([^"]*)"',
            r"name='sid'\s+value='([^']*)'",
            r'"sid"\s*:\s*"([^"]*)"',
            r"sid=([a-zA-Z0-9_]+)",
            r"'sid'\s*,\s*'([^']*)'",
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match and len(match.group(1)) > 5:
                return match.group(1)
        return ""

    # ====================================================================
    # Thread management
    # ====================================================================

    def _worker(self, func, *args, **kwargs):
        """Run *func* on the dedicated browser thread and return its result.

        All Playwright code must execute on the same thread.  This method
        ensures that the executor is a single-worker pool so that every
        call serialises on the one browser thread — no asyncio loop
        interference in Jupyter.
        """
        if self._executor is None:
            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = self._executor.submit(func, *args, **kwargs)
        return future.result(timeout=self._timeout / 1000 * 3)

    def _ensure_browser(self):
        """Start the browser (on the worker thread) if not already running."""
        if self._browser_ready:
            return

        def _init():
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self._headless)
            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = self._context.new_page()
            self._page.set_default_timeout(self._timeout)
            self._login_on_page()

        self._worker(_init)
        self._browser_ready = True

    def _login_on_page(self):
        """Log into GISAID and verify success.

        Uses the page's own ``sys`` JavaScript framework by filling the
        login form and calling ``doLogin()``.  All operations go through
        ``page.evaluate()`` — no raw HTTP calls that would trigger GISAID's
        bot detection.
        """
        logger.info("Logging into GISAID...")

        self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        self._page.wait_for_timeout(5000)
        html = self._page.content()
        self._debug_dump_raw("00_login_page", html)

        # Extract session IDs
        self._sid = self._extract_js_var(html, "SID")
        self._wid = self._extract_js_var(html, "WID")
        self._pid = self._extract_js_var(html, "PID")
        logger.info(
            "Session: SID=%s... WID=%s PID=%s",
            self._sid[:12] if self._sid else "(none)",
            self._wid[:15] if self._wid else "(none)",
            self._pid[:15] if self._pid else "(none)",
        )

        # Fill the login form
        login_field = self._page.locator(
            'input[name="login"], #elogin, input[id="elogin"]'
        )
        pass_field = self._page.locator(
            'input[name="password"], #epassword, input[id="epassword"]'
        )
        if login_field.count() == 0:
            raise RuntimeError(
                "Could not find login field on GISAID page. "
                f"URL: {self._page.url}"
            )

        login_field.first.fill(self.username.strip())
        pass_field.first.fill(self.password.strip())

        # Call doLogin() — try evaluate first, then button click
        try:
            self._page.evaluate("window.doLogin()")
        except Exception:
            logger.debug("doLogin() evaluate failed, trying button click")
            btn = self._page.locator(
                'input[value="Login"], input[onclick*="doLogin"], '
                'button:has-text("Login")'
            )
            if btn.count() > 0:
                btn.first.click()
            else:
                raise RuntimeError("Could not trigger GISAID login") from None

        # Wait for the AJAX response to process
        self._page.wait_for_timeout(5000)

        # === Robust login verification ===
        # GISAID shows errors in a YUI panel: check visibility via JS
        error_info = self._page.evaluate("""
            () => {
                // Check YUI error panel
                const panel = document.querySelector(
                    '.yui-panel-container .bd'
                );
                if (panel) {
                    const container = panel.closest('.yui-panel-container');
                    if (container) {
                        const style = window.getComputedStyle(container);
                        if (style.display !== 'none' &&
                            style.visibility !== 'hidden') {
                            return panel.innerText.trim();
                        }
                    }
                    return panel.innerText.trim() || '';
                }
                // Check generic error elements
                const err = document.querySelector(
                    '.error, .alert-danger, #error_message'
                );
                if (err && err.offsetParent !== null) {
                    return err.innerText.trim();
                }
                return '';
            }
        """)

        if error_info:
            raise RuntimeError(
                f"GISAID login failed: {error_info}. "
                "Please verify your username and password. "
                "GISAID usernames are typically email addresses."
            )

        # Double-check: are we still on the login page?
        post_html = self._page.content()
        self._debug_dump_raw("01_after_login", post_html)

        still_on_login = self._page.evaluate("""
            () => {
                const loginField = document.getElementById('elogin');
                if (!loginField) return false;
                // Is the login form still visible?
                const pane = document.getElementById('welcome_anonpane');
                if (pane) {
                    return pane.offsetParent !== null;
                }
                return loginField.offsetParent !== null;
            }
        """)

        if still_on_login:
            raise RuntimeError(
                "GISAID login failed — login form is still visible. "
                "Please check your credentials. "
                f"URL: {self._page.url}"
            )

        logger.info("Successfully logged into GISAID")
        logger.info("Post-login URL: %s", self._page.url)

        # Extract search components from the authenticated page
        self._extract_ceids_from_authenticated_page(post_html)

    @staticmethod
    def _extract_js_var(html: str, var_name: str) -> str:
        """Extract a value from ``sys["VAR"] = "value"`` in page HTML."""
        for pattern in [
            rf'sys\["{var_name}"\]\s*=\s*"([^"]*)"',
            rf"sys\['{var_name}'\]\s*=\s*'([^']*)'",
            rf'sys\.{var_name}\s*=\s*"([^"]*)"',
        ]:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""

    def _extract_ceids_from_authenticated_page(self, html: str):
        """After login, navigate to the search page via the sys framework
        and extract all component IDs needed for querying.

        Instead of making HTTP API calls (which trigger bot detection),
        we call ``sys.getC().call('Go', ...)`` via ``page.evaluate()``
        to navigate within the SPA, then parse the resulting page HTML.
        """
        # Look for the action bar component to navigate to the browse page
        browse_page = (
            "page_corona2020.Corona2020BrowsePage"
            if self.database == "EpiCoV"
            else f"page_{self.database.lower()}.{self.database}BrowsePage"
        )

        # Find actionbar CID
        ab_match = re.search(
            r"sys-actionbar-action-ni\"\s+onclick=\"sys\.getC\('([^']*)",
            html,
        )

        if ab_match:
            actionbar_cid = ab_match.group(1)
            logger.info("Navigating to search page via sys framework...")
            try:
                self._page.evaluate(
                    f"sys.getC('{actionbar_cid}').call('Go', "
                    f"{{page: '{browse_page}'}})"
                )
                self._page.wait_for_timeout(5000)
            except Exception as e:
                logger.warning("Could not navigate via sys framework: %s", e)

        # Try clicking the Search action directly if sys call didn't work
        search_html = self._page.content()
        self._debug_dump_raw("02_search_page", search_html)

        # If we still don't see search components, try clicking by text
        if "createComponent" not in search_html or "SearchComponent" not in search_html:
            for text in ["Search", "Browse", "EpiCoV", "COVID-19"]:
                try:
                    btn = self._page.locator(f'a:has-text("{text}"), button:has-text("{text}")')
                    if btn.count() > 0:
                        btn.first.click()
                        self._page.wait_for_timeout(3000)
                        search_html = self._page.content()
                        if "SearchComponent" in search_html or "sys-datatable" in search_html:
                            break
                except Exception:
                    continue

        self._debug_dump_raw("03_final_search_page", search_html)
        self._extract_ceids(search_html, self._pid)

    def _gisaid_post_raw(self, sid, wid, pid, queue) -> dict:
        """Low-level POST to the GISAID API via Playwright's request context."""
        ts = str(int(time.time() * 1000))
        url = "https://www.epicov.org/epi3/frontend"
        try:
            response = self._page.request.post(
                url,
                form={
                    "sid": sid,
                    "wid": wid,
                    "pid": pid,
                    "data": json.dumps({"queue": queue}),
                    "ts": ts,
                    "mode": "ajax",
                },
                headers={
                    "accept": "application/json, text/javascript, */*; q=0.01",
                },
                timeout=self._timeout,
            )
            body = response.text()
            status = response.status
            ct = response.headers.get("content-type", "")

            if "application/json" not in ct and not body.strip().startswith("{"):
                logger.error(
                    "GISAID POST returned non-JSON: status=%d ct=%s "
                    "body_start=%s",
                    status, ct, body[:200].replace("\n", " "),
                )
                self._debug_dump_raw(
                    "api_error_post",
                    f"URL: {url}\nStatus: {status}\n"
                    f"Content-Type: {ct}\n\n{body[:5000]}",
                )
                return {}

            return json.loads(body)
        except Exception as e:
            logger.error("GISAID API POST failed: %s", e)
            return {}

    def _extract_ceids(self, html: str, pid: str):
        """Extract all component element IDs (ceids) from page HTML."""
        self._search_pid = pid

        def _find(pattern: str) -> str:
            m = re.search(pattern, html)
            return m.group(1) if m else ""

        search_component = (
            "Corona2020SearchComponent"
            if self.database == "EpiCoV"
            else "SearchComponent"
        )
        self._search_cid = _find(
            rf"createComponent\('([^']*)','{search_component}'"
        )
        self._query_cid = _find(
            r'class="sys-datatable[^"]*"\s+id="([^"]*)_table'
        )
        if not self._query_cid:
            self._query_cid = _find(
                r'sys-datatable[^"]*"[^>]*id="([^"]*)_table'
            )

        self._location_ceid = self._extract_search_ceid(html, "covv_location")
        self._lineage_ceid = self._extract_search_ceid(html, "pangolin_lineage")
        self._from_ceid = self._extract_search_ceid(
            html, "covv_collection_date_from"
        )
        self._to_ceid = self._extract_search_ceid(
            html, "covv_collection_date_to"
        )
        self._from_sub_ceid = self._extract_search_ceid(
            html, "covv_subm_date_from"
        )
        self._to_sub_ceid = self._extract_search_ceid(
            html, "covv_subm_date_to"
        )
        self._virus_name_ceid = self._extract_search_ceid(
            html, "covv_virus_name"
        )
        self._variant_ceid = self._extract_search_ceid(html, "variants")
        self._complete_ceid = self._extract_search_ceid(html, "complete")
        self._highq_ceid = self._extract_search_ceid(html, "highq")
        self._lowcov_ceid = self._extract_search_ceid(html, "low_quality")
        self._coldc_ceid = self._extract_search_ceid(html, "coldc")

        logger.info(
            "Extracted ceids: search=%s query=%s location=%s lineage=%s",
            bool(self._search_cid), bool(self._query_cid),
            bool(self._location_ceid), bool(self._lineage_ceid),
        )

    @staticmethod
    def _extract_search_ceid(html: str, widget: str) -> str:
        """Extract a ceid for a widget name using GISAIDR's pattern."""
        pattern = rf"\.createFI\('([^']*)','\w*Widget','{widget}"
        m = re.search(pattern, html)
        if m:
            return m.group(1)
        pattern2 = rf"createFI\('([^']*)','[^']*','{widget}"
        m = re.search(pattern2, html)
        return m.group(1) if m else ""

    def _fetch_page_html(self, params: str = "") -> str:
        """Load a GISAID sub-page via browser navigation and return its HTML.

        Uses ``page.goto()`` instead of ``fetch()`` to avoid CORS issues
        when the browser origin differs from the target URL.
        """
        url = "https://www.epicov.org/epi3/frontend"
        if params:
            url += f"?{params}"
        self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_timeout(2000)
        return self._page.content()

    def _gisaid_post(self, queue: list) -> dict:
        """Send a command queue to GISAID's API."""
        return self._gisaid_post_raw(
            self._sid,
            self._wid,
            self._search_pid if hasattr(self, "_search_pid") else self._pid,
            queue,
        )

    def _gisaid_get(self, queue: list) -> dict:
        """Send a GET request with command queue to GISAID's API."""
        import urllib.parse

        ts = str(int(time.time() * 1000))
        params = urllib.parse.urlencode({
            "sid": self._sid,
            "wid": self._wid,
            "pid": self._search_pid if hasattr(self, "_search_pid") else self._pid,
            "data": json.dumps({"queue": queue}),
            "ts": ts,
            "mode": "ajax",
        })
        url = f"https://www.epicov.org/epi3/frontend?{params}"
        try:
            response = self._page.request.get(
                url,
                headers={
                    "accept": "application/json, text/javascript, */*; q=0.01",
                },
                timeout=self._timeout,
            )
            return response.json()
        except Exception as e:
            logger.error("GISAID API GET failed: %s", e)
            return {}

    def _close_browser(self):
        """Clean up browser resources (on the worker thread)."""
        if not self._browser_ready:
            return

        def _shutdown():
            with contextlib.suppress(Exception):
                if hasattr(self, "_context") and self._context:
                    self._context.close()
            with contextlib.suppress(Exception):
                if hasattr(self, "_browser") and self._browser:
                    self._browser.close()
            with contextlib.suppress(Exception):
                if hasattr(self, "_pw") and self._pw:
                    self._pw.stop()

        with contextlib.suppress(Exception):
            self._worker(_shutdown)
        self._browser_ready = False

        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None

    # ====================================================================
    # Credential Management
    # ====================================================================

    def _load_credentials(
        self,
        username: str | None,
        password: str | None,
        config_path: str | Path | None,
    ) -> tuple[str, str]:
        """Load GISAID credentials.

        Resolution order:
        1. Explicit constructor arguments
        2. Environment variables (``GISAID_USERNAME``, ``GISAID_PASSWORD``)
        3. Config file (``~/.config/epi_data/gisaid.json`` or *config_path*)
        4. Interactive prompt (asks the user at runtime)

        Returns:
            ``(username, password)`` tuple.
        """
        if username and password:
            return username, password

        env_username = os.getenv("GISAID_USERNAME")
        env_password = os.getenv("GISAID_PASSWORD")
        if env_username and env_password:
            return env_username, env_password

        search_paths: list[Path] = []
        if config_path:
            search_paths.append(Path(config_path))
        search_paths.extend(
            [
                Path.home() / ".config" / "epi_data" / "gisaid.json",
                Path.home() / ".nanobot" / "config" / "gisaid.json",
                Path.cwd() / "gisaid_config.json",
            ]
        )

        for path in search_paths:
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    u = data.get("username") or data.get("user")
                    p = data.get("password") or data.get("pass")
                    if u and p:
                        logger.info("Loaded credentials from %s", path)
                        return u, p
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Failed to read %s: %s", path, e)

        # Interactive prompt fallback
        return self._prompt_credentials()

    @staticmethod
    def _is_jupyter() -> bool:
        """Detect whether we are running inside a Jupyter/IPython kernel."""
        try:
            from IPython import get_ipython

            shell = get_ipython()
            if shell is None:
                return False
            return type(shell).__name__ == "ZMQInteractiveShell"
        except (ImportError, NameError):
            return False

    @staticmethod
    def _prompt_credentials() -> tuple[str, str]:
        """Interactively prompt the user for GISAID credentials.

        In Jupyter/IPython environments :func:`getpass.getpass` is
        unreliable because it reads from ``/dev/tty`` which is not
        connected to the notebook frontend, causing garbled or empty
        input.  In those environments the password is read via
        :func:`input` instead (with a warning that it will be visible in
        the cell output).  For secure, non-echoed entry use a config
        file or environment variables.

        Falls back to a :class:`ValueError` if stdin is not available
        (e.g. in non-interactive test environments).
        """
        import getpass
        import sys

        if not sys.stdin.isatty() and not sys.stdin.readable():
            raise ValueError(
                "GISAID credentials required but stdin is not available. "
                "Provide them via:\n"
                "  1. GISAIDAccessor(username=..., password=...)\n"
                "  2. Env vars: GISAID_USERNAME, GISAID_PASSWORD\n"
                "  3. Config file at ~/.config/epi_data/gisaid.json"
            )

        in_jupyter = GISAIDAccessor._is_jupyter()
        banner_lines = [
            "",
            "=" * 60,
            "No GISAID credentials found in environment or config file.",
        ]
        if in_jupyter:
            banner_lines.append(
                "Running in Jupyter — the password will be visible in the\n"
                "cell output. For secure entry, use env vars or a config\n"
                "file (see docstring)."
            )
        banner_lines.append("Register for free at: https://gisaid.org/register/")
        banner_lines.append("=" * 60)
        print("\n".join(banner_lines))

        try:
            username = input("GISAID username (email): ").strip()
            if not username:
                raise ValueError("GISAID username is required.")
            if in_jupyter:
                password = input("GISAID password: ")
            else:
                password = getpass.getpass("GISAID password: ")
            if not password:
                raise ValueError("GISAID password is required.")
        except (EOFError, OSError) as e:
            raise ValueError(
                "GISAID credentials required but could not read from "
                f"stdin: {e}"
            ) from e
        return username, password

    # ====================================================================
    # Rate Limiting
    # ====================================================================

    def _rate_limit_wait(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request_time = time.time()

    # ====================================================================
    # Caching
    # ====================================================================

    def _get_cache_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return self.cache_dir / f"{self.database}_{safe_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    @staticmethod
    def _read_cache(cache_path: Path) -> dict | None:
        try:
            return json.loads(cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _write_cache(cache_path: Path, data: dict) -> None:
        cache_path.write_text(json.dumps(data, default=str))

    # ====================================================================
    # Static / read-only methods (no browser needed)
    # ====================================================================

    def list_databases(self) -> pd.DataFrame:
        """List available GISAID databases."""
        records = [
            {
                "database": key,
                "description": info["description"],
                "pathogens": info["pathogens"],
                "records": info["records"],
                "features": info["features"],
            }
            for key, info in self.DATABASES.items()
        ]
        return pd.DataFrame(records)

    def list_countries(self) -> pd.DataFrame:
        """List countries covered by GISAID with geographic hierarchy."""
        records = []
        for region, data in GISAID_LOCATIONS.items():
            for country, code in data["regions"].items():
                records.append({
                    "country_code": code,
                    "country_name": country,
                    "region": region,
                })
        return pd.DataFrame(records)

    def get_regions(self) -> list[str]:
        """List geographic regions available in GISAID."""
        return list(GISAID_LOCATIONS.keys())

    def get_countries_by_region(self, region: str) -> pd.DataFrame:
        """Get countries in a specific GISAID region."""
        if region not in GISAID_LOCATIONS:
            raise ValueError(
                f"Region '{region}' not found. "
                f"Available: {list(GISAID_LOCATIONS.keys())}"
            )
        records = [
            {"country_code": code, "country_name": country}
            for country, code in GISAID_LOCATIONS[region]["regions"].items()
        ]
        return pd.DataFrame(records)

    # ====================================================================
    # Query (runs on worker thread)
    # ====================================================================

    def query(
        self,
        location: str | None = None,
        lineage: str | None = None,
        variant: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        from_subm: str | None = None,
        to_subm: str | None = None,
        virus_name: str | None = None,
        complete: bool = False,
        high_coverage: bool = False,
        low_coverage_excl: bool = False,
        collection_date_complete: bool = False,
        nrows: int = 50,
        load_all: bool = False,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Query GISAID database with filters.

        Returns a DataFrame with accession IDs and basic metadata.
        """
        params = {
            "location": location, "lineage": lineage, "variant": variant,
            "from_date": from_date, "to_date": to_date,
            "from_subm": from_subm, "to_subm": to_subm,
            "virus_name": virus_name,
            "complete": complete, "high_coverage": high_coverage,
            "low_coverage_excl": low_coverage_excl,
            "collection_date_complete": collection_date_complete,
            "nrows": nrows, "load_all": load_all,
        }

        cache_key = f"query_{hash(str(params))}"
        cache_path = self._get_cache_path(cache_key)

        if use_cache and self._is_cache_valid(cache_path):
            cached = self._read_cache(cache_path)
            if cached and "data" in cached:
                logger.info("Loading query results from cache")
                return pd.DataFrame(cached["data"])

        self._ensure_browser()
        self._rate_limit_wait()

        def _do_query():
            return self._query_via_api(**params)

        try:
            results = self._worker(_do_query)
        except Exception as e:
            logger.error("Query failed: %s", e)
            raise RuntimeError(f"GISAID query failed: {e}") from e

        data = {
            "data": results.to_dict("records"),
            "timestamp": datetime.now().isoformat(),
        }
        self._write_cache(cache_path, data)
        return results

    # ------------------------------------------------------------------
    # Page helpers (called ON the worker thread)
    # ------------------------------------------------------------------

    def _select_database_on_page(self, page: object) -> None:
        try:
            sel = page.locator(
                'select[name="db"], #db_selector, .database-selector'
            )
            if sel.count() > 0:
                sel.select_option(self.database)
                page.wait_for_load_state("networkidle")
                logger.info("Selected %s database", self.database)
        except Exception:
            logger.warning(
                "Could not select %s database on page", self.database
            )

    def _make_filter_queue(self, **filters) -> list:
        """Build filter commands for the sys framework (via page.evaluate)."""
        commands = []

        def _add_filter(ceid: str, value, cmd: str = "FilterChange"):
            if not ceid or not value:
                return
            commands.append(
                f"sys.getC('{self._search_cid}').call('setTarget', "
                f"{{cvalue: {json.dumps(str(value))}, ceid: '{ceid}'}})"
            )
            commands.append(
                f"sys.getC('{self._search_cid}').call('ChangeValue', "
                f"{{cvalue: {json.dumps(str(value))}, ceid: '{ceid}'}})"
            )
            commands.append(
                f"sys.getC('{self._search_cid}').call('{cmd}', "
                f"{{ceid: '{ceid}'}})"
            )

        if filters.get("location"):
            _add_filter(self._location_ceid, filters["location"])
        if filters.get("lineage"):
            cmd = "LineageChange" if self.database == "EpiCoV" else "FilterChange"
            _add_filter(self._lineage_ceid, filters["lineage"], cmd)
        if filters.get("variant"):
            _add_filter(self._variant_ceid, filters["variant"], "VariantsChange")
        if filters.get("virus_name"):
            _add_filter(self._virus_name_ceid, filters["virus_name"])
        if filters.get("from_date"):
            _add_filter(self._from_ceid, filters["from_date"])
        if filters.get("to_date"):
            _add_filter(self._to_ceid, filters["to_date"])
        if filters.get("from_subm"):
            _add_filter(self._from_sub_ceid, filters["from_subm"])
        if filters.get("to_subm"):
            _add_filter(self._to_sub_ceid, filters["to_subm"])
        if filters.get("complete"):
            _add_filter(self._complete_ceid, "complete")
        if filters.get("high_coverage"):
            _add_filter(self._highq_ceid, "highq")
        if filters.get("low_coverage_excl"):
            _add_filter(self._lowcov_ceid, "lowco")
        if filters.get("collection_date_complete"):
            _add_filter(self._coldc_ceid, "coldc")

        return commands

    def _query_via_api(self, **filters) -> pd.DataFrame:
        """Query GISAID via the page's own sys JS framework (page.evaluate)."""
        nrows = filters.pop("nrows", 50)
        filters.pop("load_all", False)

        # Apply filters via sys framework
        filter_cmds = self._make_filter_queue(**filters)
        for cmd_js in filter_cmds:
            try:
                self._page.evaluate(cmd_js)
            except Exception as e:
                logger.debug("Filter command failed: %s", e)

        # Get data via sys framework
        try:
            # Set pagination
            self._page.evaluate(
                f"sys.getC('{self._query_cid}').call('SetPaginating', "
                f"{{start_index: 0, rows_per_page: {nrows}}})"
            )
            # Get data — returns JSON with records
            raw = self._page.evaluate(
                f"JSON.stringify(sys.getC('{self._query_cid}').call('GetData'))"
            )
            resp = json.loads(raw) if raw else {}
        except Exception as e:
            logger.error("GetData via sys framework failed: %s", e)
            # Try extracting from the rendered datatable
            return self._extract_datatable_from_page()

        if not resp or "records" not in resp:
            logger.warning("No records in GISAID response")
            return pd.DataFrame()

        total = resp.get("totalRecords", 0)
        records = resp.get("records", [])
        logger.info("GISAID returned %d of %d records", len(records), total)

        df = pd.DataFrame(records) if records else pd.DataFrame()
        if not df.empty:
            df = self._rename_columns(df)
        return df

    def _extract_datatable_from_page(self) -> pd.DataFrame:
        """Fallback: parse the rendered sys-datatable HTML."""
        try:
            tables = self._page.locator(".sys-datatable table, table.sys-datatable")
            if tables.count() == 0:
                tables = self._page.locator("table")
            if tables.count() == 0:
                return pd.DataFrame()

            # Extract table data via JavaScript
            raw = self._page.evaluate("""
                () => {
                    const table = document.querySelector(
                        '.sys-datatable table, table.sys-datatable, table'
                    );
                    if (!table) return '[]';
                    const rows = [...table.querySelectorAll('tr')];
                    return JSON.stringify(rows.map(r =>
                        [...r.querySelectorAll('th,td')].map(c => c.innerText.trim())
                    ));
                }
            """)
            rows_data = json.loads(raw) if raw else []
            if not rows_data:
                return pd.DataFrame()

            headers = rows_data[0] if rows_data else []
            data_rows = rows_data[1:] if len(rows_data) > 1 else []
            df = pd.DataFrame(data_rows, columns=headers) if data_rows else pd.DataFrame()
            logger.info("Extracted %d rows from datatable HTML", len(df))
            return df
        except Exception as e:
            logger.error("Failed to extract datatable: %s", e)
            return pd.DataFrame()

    @staticmethod
    def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Rename single-letter column keys to readable names."""
        col_map = {
            "b": "id", "d": "virus_name", "e": "passage_details_history",
            "f": "accession_id", "g": "collection_date",
            "h": "submission_date", "i": "information",
            "j": "length", "k": "host",
            "l": "location", "m": "originating_lab",
            "n": "submitting_lab",
        }
        return df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    def _reset_query(self):
        """Reset search parameters after a query."""
        self._gisaid_post([{
            "wid": self._wid, "pid": self._search_pid,
            "cid": self._search_cid, "cmd": "Reset",
        }])

    # ====================================================================
    # Download metadata (runs on worker thread)
    # ====================================================================

    def download_metadata(
        self,
        list_of_accession_ids: list[str],
        metadata_type: str = "dates_and_location",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Download metadata for specified accession IDs.

        GISAID limits downloads to 5,000 records per request.
        """
        valid_types = {
            "dates_and_location", "patient_status", "sequencing_technology"
        }
        if metadata_type not in valid_types:
            raise ValueError(f"metadata_type must be one of: {valid_types}")

        if not list_of_accession_ids:
            return pd.DataFrame()

        cache_key = (
            f"meta_{metadata_type}_"
            f"{hash(str(sorted(list_of_accession_ids)))}"
        )
        cache_path = self._get_cache_path(cache_key)

        if use_cache and self._is_cache_valid(cache_path):
            cached = self._read_cache(cache_path)
            if cached and "data" in cached:
                logger.info("Loading metadata from cache")
                return pd.DataFrame(cached["data"])

        self._ensure_browser()
        batch_size = 5000
        all_results = []

        for i in range(0, len(list_of_accession_ids), batch_size):
            batch = list_of_accession_ids[i : i + batch_size]
            self._rate_limit_wait()

            def _download(b=batch, mt=metadata_type):
                return self._download_metadata_batch_on_worker(b, mt)

            batch_df = self._worker(_download)
            if batch_df is not None:
                all_results.append(batch_df)
            logger.info(
                "Downloaded metadata batch %d/%d",
                i // batch_size + 1,
                (len(list_of_accession_ids) - 1) // batch_size + 1,
            )

        if not all_results:
            return pd.DataFrame()

        result = pd.concat(all_results, ignore_index=True)
        self._write_cache(
            cache_path,
            {
                "data": result.to_dict("records"),
                "timestamp": datetime.now().isoformat(),
            },
        )
        return result

    def _download_metadata_batch_on_worker(
        self, accession_ids: list[str], metadata_type: str
    ) -> pd.DataFrame | None:
        """Called ON the worker thread."""
        page: object = self._page
        page.goto(self.SEARCH_URL, wait_until="networkidle")

        sel = page.locator(
            'button:has-text("Select"), a:has-text("Select"), '
            'input[value="Select"]'
        )
        if sel.count() > 0:
            sel.first.click()
            page.wait_for_load_state("networkidle")

        text_input = page.locator("textarea, .accession-input")
        if text_input.count() > 0:
            text_input.first.fill("\n".join(accession_ids))
        else:
            logger.warning("Could not find accession ID input on page")
            return None

        ok = page.locator(
            'button:has-text("OK"), input[value="OK"], button[type="submit"]'
        )
        if ok.count() > 0:
            ok.first.click()
            page.wait_for_load_state("networkidle")

        labels = {
            "dates_and_location": "Dates and Location",
            "patient_status": "Patient status metadata",
            "sequencing_technology": "Sequencing technology metadata",
        }
        label = labels[metadata_type]
        opt = page.locator(f'text="{label}"')
        if opt.count() > 0:
            opt.first.click()

        dl = page.locator(
            'button:has-text("Download"), input[value="Download"]'
        )
        if dl.count() > 0:
            with page.expect_download(timeout=60000) as di:
                dl.first.click()
            download = di.value

            td = tempfile.mkdtemp()
            tp = Path(td) / download.suggested_filename
            download.save_as(str(tp))

            if tp.suffix in (".tsv", ".txt", ".csv"):
                df = pd.read_csv(
                    tp,
                    sep="\t" if tp.suffix == ".tsv" else ",",
                    low_memory=False,
                )
            else:
                logger.warning("Unexpected download format: %s", tp.suffix)
                df = pd.DataFrame()

            tp.unlink(missing_ok=True)
            Path(td).rmdir()
            return df

        logger.warning("Could not find download button")
        return None

    # ====================================================================
    # Download sequences (runs on worker thread)
    # ====================================================================

    def download_sequences(
        self,
        list_of_accession_ids: list[str],
        use_cache: bool = True,
    ) -> str:
        """Download FASTA nucleotide sequences for accession IDs.

        GISAID limits downloads to 5,000 sequences per request.
        """
        if not list_of_accession_ids:
            return ""

        cache_key = f"fasta_{hash(str(sorted(list_of_accession_ids)))}"
        cache_path = self._get_cache_path(cache_key)

        if use_cache and self._is_cache_valid(cache_path):
            cached = self._read_cache(cache_path)
            if cached and "fasta" in cached:
                logger.info("Loading sequences from cache")
                return cached["fasta"]

        self._ensure_browser()
        batch_size = 5000
        all_fasta = []

        for i in range(0, len(list_of_accession_ids), batch_size):
            batch = list_of_accession_ids[i : i + batch_size]
            self._rate_limit_wait()

            def _download_seqs(b=batch):
                return self._download_sequences_batch_on_worker(b)

            fasta = self._worker(_download_seqs)
            if fasta:
                all_fasta.append(fasta)

        result = "\n".join(all_fasta)
        if result and use_cache:
            self._write_cache(
                cache_path,
                {"fasta": result, "timestamp": datetime.now().isoformat()},
            )
        return result

    def _download_sequences_batch_on_worker(
        self, accession_ids: list[str]
    ) -> str | None:
        """Called ON the worker thread."""
        page: object = self._page
        page.goto(self.SEARCH_URL, wait_until="networkidle")

        sel = page.locator(
            'button:has-text("Select"), a:has-text("Select")'
        )
        if sel.count() > 0:
            sel.first.click()
            page.wait_for_load_state("networkidle")

        text_input = page.locator("textarea, .accession-input")
        if text_input.count() > 0:
            text_input.first.fill("\n".join(accession_ids))
        else:
            return None

        ok = page.locator('button:has-text("OK"), input[value="OK"]')
        if ok.count() > 0:
            ok.first.click()
            page.wait_for_load_state("networkidle")

        opt = page.locator(
            'text="Nucleotide Sequences (FASTA)", text="Sequences (FASTA)"'
        )
        if opt.count() > 0:
            opt.first.click()

        dl = page.locator(
            'button:has-text("Download"), input[value="Download"]'
        )
        if dl.count() > 0:
            with page.expect_download(timeout=60000) as di:
                dl.first.click()
            download = di.value

            td = tempfile.mkdtemp()
            tp = Path(td) / download.suggested_filename
            download.save_as(str(tp))

            fasta_content = tp.read_text(encoding="utf-8", errors="replace")
            tp.unlink(missing_ok=True)
            Path(td).rmdir()
            return fasta_content

        return None

    # ====================================================================
    # Count sequences
    # ====================================================================

    def count_sequences(
        self,
        location: str | None = None,
        lineage: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> int:
        """Count sequences matching criteria."""
        df = self.query(
            location=location, lineage=lineage,
            from_date=from_date, to_date=to_date,
            nrows=1, load_all=False,
        )
        try:
            raw = self._page.evaluate(
                f"sys.getC('{self._query_cid}').totalRecords || 0"
            )
            if raw and int(raw) > 0:
                return int(raw)
        except Exception:
            pass
        return len(df)

    # ====================================================================
    # Convenience
    # ====================================================================

    def get_brazil_data(
        self,
        lineage: str | None = None,
        date_range: tuple[str, str] | None = None,
        nrows: int = 100,
    ) -> pd.DataFrame:
        """Convenience method to query Brazilian data."""
        kwargs: dict = {"location": "Brazil", "nrows": nrows}
        if lineage:
            kwargs["lineage"] = lineage
        if date_range:
            kwargs["from_date"] = date_range[0]
            kwargs["to_date"] = date_range[1]
        return self.query(**kwargs)

    def info(self) -> str:
        """Return detailed information about the accessor."""
        base_info = super().info()
        db_info = self.DATABASES[self.database]
        return (
            f"{base_info}\n"
            f"  Database: {db_info['name']}\n"
            f"  Description: {db_info['description']}\n"
            f"  Pathogens: {db_info['pathogens']}\n"
            f"  Records: {db_info['records']}\n"
            f"  Features: {db_info['features']}\n"
            f"  Authentication: Required "
            f"(free registration at {self.source_url})\n"
            f"  Max download: 5,000 records per request\n"
            f"  Important: By using this accessor you agree to "
            f"GISAID's DAA terms"
        )

    def close(self) -> None:
        """Clean up browser resources."""
        self._close_browser()
        logger.info("GISAID accessor closed")

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self._close_browser()


# ============================================================================
# Module-level convenience functions
# ============================================================================


def _get_brazil_data(
    database: str,
    username: str | None,
    password: str | None,
    lineage: str | None = None,
    date_range: tuple[str, str] | None = None,
    nrows: int = 100,
) -> pd.DataFrame:
    """Shared helper for Brazil convenience functions."""
    accessor = GISAIDAccessor(
        database=database, username=username, password=password
    )
    try:
        return accessor.get_brazil_data(
            lineage=lineage, date_range=date_range, nrows=nrows
        )
    finally:
        accessor.close()


def get_covid_brazil(
    username: str | None = None,
    password: str | None = None,
    lineage: str | None = None,
    date_range: tuple[str, str] | None = None,
    nrows: int = 100,
) -> pd.DataFrame:
    """Get COVID-19 (EpiCoV) data for Brazil."""
    return _get_brazil_data(
        "EpiCoV", username, password, lineage=lineage,
        date_range=date_range, nrows=nrows,
    )


def get_influenza_brazil(
    username: str | None = None,
    password: str | None = None,
    date_range: tuple[str, str] | None = None,
    nrows: int = 100,
) -> pd.DataFrame:
    """Get Influenza (EpiFlu) data for Brazil."""
    return _get_brazil_data(
        "EpiFlu", username, password,
        date_range=date_range, nrows=nrows,
    )


def get_mpox_brazil(
    username: str | None = None,
    password: str | None = None,
    date_range: tuple[str, str] | None = None,
    nrows: int = 100,
) -> pd.DataFrame:
    """Get Mpox (EpiPox) data for Brazil."""
    return _get_brazil_data(
        "EpiPox", username, password,
        date_range=date_range, nrows=nrows,
    )


def get_dengue_brazil(
    username: str | None = None,
    password: str | None = None,
    date_range: tuple[str, str] | None = None,
    nrows: int = 100,
) -> pd.DataFrame:
    """Get Dengue (EpiArbo) data for Brazil."""
    return _get_brazil_data(
        "EpiArbo", username, password,
        date_range=date_range, nrows=nrows,
    )
