from __future__ import annotations

import unittest

from galafresh_baldwin.browser_source import PaginationError, SourceError, paginate_category, parse_robots
from galafresh_baldwin.models import CategoryRoot


ROOT = CategoryRoot("10", "Produce", ("Produce",), ("10",))


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


if __name__ == "__main__":
    unittest.main()
