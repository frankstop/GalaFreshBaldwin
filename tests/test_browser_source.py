from __future__ import annotations

from email.message import Message
from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from galafresh_baldwin.browser_source import BrowserSource, PaginationError, SourceError, paginate_category, parse_robots
from galafresh_baldwin.models import CategoryRoot


ROOT = CategoryRoot("10", "Produce", ("Produce",), ("10",))


class FakeResponse:
    def __init__(self, body: str, content_type: str = "text/plain; charset=utf-8") -> None:
        self.status = 200
        self.headers = Message()
        self.headers["content-type"] = content_type
        self._body = body.encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self._body


class PaginationTests(unittest.TestCase):
    def test_reconciles_more_than_one_hundred_products(self) -> None:
        products = [{"id": index} for index in range(205)]

        def fetch(offset: int, size: int):
            return {"total": len(products), "products": products[offset : offset + size]}

        result = paginate_category(ROOT, fetch)
        self.assertEqual(len(result.products), 205)
        self.assertEqual(result.total, 205)
        self.assertEqual(result.offsets, (0, 100, 200))

    def test_repeated_page_is_rejected(self) -> None:
        page = [{"id": index} for index in range(100)]
        with self.assertRaisesRegex(PaginationError, "repeated page"):
            paginate_category(ROOT, lambda offset, size: {"total": 200, "products": page})

    def test_inconsistent_total_and_empty_intermediate_page_are_rejected(self) -> None:
        calls = 0

        def inconsistent(offset: int, size: int):
            nonlocal calls
            calls += 1
            return {"total": 101 if calls == 1 else 102, "products": [{"id": offset + i} for i in range(100 if calls == 1 else 2)]}

        with self.assertRaisesRegex(PaginationError, "inconsistent total"):
            paginate_category(ROOT, inconsistent)
        with self.assertRaisesRegex(PaginationError, "empty intermediate"):
            paginate_category(ROOT, lambda offset, size: {"total": 1, "products": []})

    def test_robots_delay_is_enforced_and_restriction_fails_closed(self) -> None:
        allowed = "User-agent: *\nDisallow: /cart\nCrawl-delay: 4\n"
        self.assertEqual(parse_robots(allowed, 0.1).crawl_delay, 4.0)
        with self.assertRaises(SourceError):
            parse_robots("User-agent: *\nDisallow: /v2\n", 0)

    def test_robots_are_fetched_directly_and_http_errors_fail_closed(self) -> None:
        allowed = "User-agent: *\nDisallow: /cart\nCrawl-delay: 4\n"
        source = BrowserSource(request_delay=0)
        with patch("galafresh_baldwin.browser_source.urlopen", return_value=FakeResponse(allowed)):
            policy = source._fetch_robots()
        self.assertEqual(policy.crawl_delay, 4.0)
        self.assertEqual(source.requests, 1)

        forbidden = HTTPError(
            "https://www.shopgalafresh.com/robots.txt",
            403,
            "Forbidden",
            {"content-type": "text/html; charset=UTF-8"},
            BytesIO(b"forbidden"),
        )
        with patch("galafresh_baldwin.browser_source.urlopen", side_effect=forbidden):
            with self.assertRaisesRegex(SourceError, "HTTP 403"):
                BrowserSource(request_delay=0)._fetch_robots()


if __name__ == "__main__":
    unittest.main()
