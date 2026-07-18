from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .discovery import DiscoveryResult, discover_visible_roots, find_category
from .models import BRANCH_ID, RETAILER_ID, CategoryRoot
from .parsers import ContractError

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://www.shopgalafresh.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = "GalaFreshBaldwinResearch/1.0 (+https://github.com/frankstop/GalaFreshBaldwin)"
FORBIDDEN_PREFIXES = (
    "/search", "/cart", "/user", "/account", "/coupons", "/orders-history",
    "/recent-purchases", "/smart-list", "/product-tags/",
)


class SourceError(RuntimeError):
    """Browser acquisition failed closed."""


class PaginationError(SourceError):
    """A category page sequence violated the API contract."""


@dataclass(frozen=True, slots=True)
class CategoryCollection:
    root: CategoryRoot
    total: int
    products: tuple[dict[str, Any], ...]
    offsets: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RobotsPolicy:
    text: str
    sha256: str
    crawl_delay: float


@dataclass(slots=True)
class RawCollection:
    frontend_data: dict[str, Any]
    discovery: DiscoveryResult
    categories: list[CategoryCollection]
    robots: RobotsPolicy
    bootstrap_url: str
    requests: int
    retries: int
    elapsed_seconds: float


class GlobalRateLimiter:
    """One serial minimum interval shared by every storefront request."""

    def __init__(self, minimum_delay: float) -> None:
        self.minimum_delay = max(0.0, minimum_delay)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            remaining = self.minimum_delay - (time.monotonic() - self._last)
            if remaining > 0:
                time.sleep(remaining)
            self._last = time.monotonic()

    def raise_minimum(self, minimum_delay: float) -> None:
        self.minimum_delay = max(self.minimum_delay, minimum_delay)


def paginate_category(
    root: CategoryRoot,
    fetch_page: Callable[[int, int], dict[str, Any]],
    page_size: int = 100,
) -> CategoryCollection:
    """Fetch and exactly reconcile one root category's offset pagination."""
    offset = 0
    expected_total: int | None = None
    products: list[dict[str, Any]] = []
    offsets: list[int] = []
    page_hashes: set[str] = set()
    product_ids: set[str] = set()
    while expected_total is None or len(products) < expected_total:
        if offset in offsets:
            raise PaginationError(f"pagination loop at offset {offset} for category {root.category_id}")
        offsets.append(offset)
        response = fetch_page(offset, page_size)
        if not isinstance(response, dict) or "total" not in response or "products" not in response:
            raise PaginationError(f"missing total/products for category {root.category_id} offset {offset}")
        total = response["total"]
        page = response["products"]
        if not isinstance(total, int) or total < 0 or not isinstance(page, list):
            raise PaginationError(f"invalid total/products types for category {root.category_id} offset {offset}")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise PaginationError(f"inconsistent total for category {root.category_id}: {expected_total} then {total}")
        if not page and len(products) < expected_total:
            raise PaginationError(f"empty intermediate page for category {root.category_id} offset {offset}")
        ids = [str(item.get("id")) for item in page if isinstance(item, dict)]
        fingerprint = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
        if page and fingerprint in page_hashes:
            raise PaginationError(f"repeated page for category {root.category_id} offset {offset}")
        page_hashes.add(fingerprint)
        duplicates = product_ids.intersection(ids)
        if duplicates:
            raise PaginationError(f"duplicate pagination product ids for category {root.category_id}: {sorted(duplicates)[:3]}")
        product_ids.update(ids)
        products.extend(item for item in page if isinstance(item, dict))
        returned_count = len(page)
        if len(products) > expected_total:
            raise PaginationError(f"collected count exceeds API total for category {root.category_id}")
        if returned_count == 0:
            break
        offset += returned_count
    if expected_total is None or len(products) != expected_total:
        raise PaginationError(
            f"count mismatch for category {root.category_id}: collected={len(products)} total={expected_total}"
        )
    return CategoryCollection(root, expected_total, tuple(products), tuple(offsets))


def parse_robots(text: str, requested_delay: float) -> RobotsPolicy:
    parser = RobotFileParser()
    parser.set_url(ROBOTS_URL)
    parser.parse(text.splitlines())
    paths = [
        f"{BASE_URL}/",
        f"{BASE_URL}/categories/",
        f"{BASE_URL}/v2/retailers/{RETAILER_ID}/branches/{BRANCH_ID}/categories/1/products",
    ]
    if not all(parser.can_fetch(USER_AGENT, path) for path in paths):
        raise SourceError("robots.txt does not permit the configured public category and /v2 collection paths")
    delay = parser.crawl_delay(USER_AGENT)
    if delay is None:
        delay = parser.crawl_delay("*")
    delay_value = float(delay or 0)
    return RobotsPolicy(text, hashlib.sha256(text.encode()).hexdigest(), max(delay_value, requested_delay))


class BrowserSource:
    """Clean-context, same-origin Playwright source for the anonymous public catalog."""

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 4.0,
        retry_count: int = 2,
        timeout_seconds: float = 45.0,
        diagnostic_limit: int | None = None,
    ) -> None:
        self.headless = headless
        self.request_delay = request_delay
        self.retry_count = max(0, retry_count)
        self.timeout_ms = int(timeout_seconds * 1000)
        self.diagnostic_limit = diagnostic_limit
        self.requests = 0
        self.retries = 0
        self._limiter = GlobalRateLimiter(request_delay)

    def _route(self, route: Any) -> None:
        request = route.request
        parsed = urlparse(request.url)
        if parsed.hostname and parsed.hostname.endswith("shopgalafresh.com"):
            if any(parsed.path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
                route.abort("blockedbyclient")
                return
            self._limiter.wait()
            self.requests += 1
        elif parsed.path.endswith("data.js") or "/data.js" in parsed.path:
            self._limiter.wait()
            self.requests += 1
        if request.resource_type in {"image", "font", "media"}:
            route.abort("blockedbyclient")
        else:
            route.continue_()

    def _fetch_robots(self) -> RobotsPolicy:
        """Fetch policy outside Chromium so bot screening cannot replace it with an HTML challenge."""
        self._limiter.wait()
        self.requests += 1
        request = Request(
            ROBOTS_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain, text/*;q=0.9, */*;q=0.1"},
        )
        try:
            with urlopen(request, timeout=self.timeout_ms / 1000) as response:
                status = int(response.status)
                content_type = str(response.headers.get("content-type", ""))
                charset = response.headers.get_content_charset() or "utf-8"
                text = response.read().decode(charset)
        except HTTPError as error:
            content_type = str(error.headers.get("content-type", ""))
            raise SourceError(
                f"robots.txt returned HTTP {error.code} content type {content_type!r}"
            ) from error
        except (URLError, TimeoutError, UnicodeDecodeError) as error:
            raise SourceError(f"robots.txt request failed: {error}") from error
        if status >= 400 or "text" not in content_type.lower():
            raise SourceError(f"robots.txt returned HTTP {status} content type {content_type!r}")
        return parse_robots(text, self.request_delay)

    def _bootstrap(self, page: Page) -> tuple[dict[str, Any], str]:
        response = page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=self.timeout_ms)
        if response is None or response.status >= 400:
            raise SourceError(f"homepage returned HTTP {response.status if response else 'no response'}")
        page.wait_for_function("() => window.sp && window.sp.frontendData", timeout=self.timeout_ms)
        urls = page.evaluate(
            r"""() => Array.from(new Set([
                ...performance.getEntriesByType('resource').map(x => x.name),
                ...Array.from(document.scripts).map(x => x.src).filter(Boolean)
            ])).filter(x => /(?:^|\/)data(?:[._-][^/]*)?\.js(?:\?|$)/i.test(x))"""
        )
        if not isinstance(urls, list) or not urls:
            raise SourceError("loaded data.js bootstrap asset could not be identified")
        data = page.evaluate("() => JSON.parse(JSON.stringify(window.sp.frontendData))")
        if not isinstance(data, dict):
            raise SourceError("window.sp.frontendData is unavailable or not serializable")
        return data, str(urls[-1])

    def _product_url(self, root: CategoryRoot, offset: int, size: int) -> str:
        params: list[tuple[str, str]] = [
            ("appId", "4"), ("from", str(offset)), ("size", str(size)), ("languageId", "2"), ("minScore", "0")
        ]
        params.extend(("names", name) for name in root.path_names)
        params.append(("filters", json.dumps({"mustNot": {"term": {"branch.isOutOfStock": True}}}, separators=(",", ":"))))
        return f"/v2/retailers/{RETAILER_ID}/branches/{BRANCH_ID}/categories/{root.category_id}/products?{urlencode(params)}"

    def _fetch_json(self, page: Page, path: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            if attempt:
                self.retries += 1
                time.sleep(min(2 ** (attempt - 1), 8))
            try:
                result = page.evaluate(
                    """async (path) => {
                      const response = await fetch(path, {credentials: 'omit', headers: {'accept': 'application/json'}});
                      return {status: response.status, type: response.headers.get('content-type') || '', text: await response.text()};
                    }""",
                    path,
                )
                status, content_type, text = int(result["status"]), str(result["type"]), str(result["text"])
                if status == 403:
                    raise SourceError("repeated HTTP 403 from public endpoint; failing closed")
                if status >= 400:
                    raise SourceError(f"product endpoint returned HTTP {status}")
                if "json" not in content_type.lower():
                    raise SourceError(f"product endpoint returned non-JSON content type {content_type!r}")
                value = json.loads(text)
                if not isinstance(value, dict):
                    raise SourceError("product endpoint JSON is not an object")
                return value
            except (json.JSONDecodeError, SourceError, Exception) as error:
                last_error = error
                if isinstance(error, SourceError) and "403" in str(error):
                    break
        raise SourceError(f"request failed after bounded retries: {last_error}") from last_error

    def collect(self, category_id: str | None = None) -> RawCollection:
        started = time.monotonic()
        playwright: Playwright | None = None
        browser: Browser | None = None
        context: BrowserContext | None = None
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(user_agent=USER_AGENT, storage_state=None)
            context.set_default_timeout(self.timeout_ms)
            context.route("**/*", self._route)
            page = context.new_page()
            robots = self._fetch_robots()
            self._limiter.raise_minimum(robots.crawl_delay)
            frontend, bootstrap_url = self._bootstrap(page)
            discovery = discover_visible_roots(frontend)
            roots = list(discovery.roots)
            if category_id is not None:
                roots = [root for root in roots if root.category_id == str(category_id)]
                if not roots:
                    roots = [find_category(frontend, str(category_id))]
            if self.diagnostic_limit is not None:
                roots = roots[: self.diagnostic_limit]
            categories: list[CategoryCollection] = []
            for index, root in enumerate(roots, 1):
                LOGGER.info("category_start", extra={"category_id": root.category_id, "index": index, "total_roots": len(roots)})
                category = paginate_category(root, lambda offset, size: self._fetch_json(page, self._product_url(root, offset, size)))
                categories.append(category)
                LOGGER.info("category_complete", extra={"category_id": root.category_id, "products": category.total})
            return RawCollection(
                frontend_data=frontend,
                discovery=discovery,
                categories=categories,
                robots=robots,
                bootstrap_url=bootstrap_url,
                requests=self.requests,
                retries=self.retries,
                elapsed_seconds=round(time.monotonic() - started, 3),
            )
        except Exception as error:
            if "captcha" in str(error).lower() or "authentication" in str(error).lower():
                raise SourceError(f"public anonymous contract unavailable: {error}") from error
            raise
        finally:
            if context is not None:
                context.close()
            if browser is not None:
                browser.close()
            if playwright is not None:
                playwright.stop()
