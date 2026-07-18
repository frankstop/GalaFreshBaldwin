from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from galafresh_baldwin.analysis import build_daily_summary
from galafresh_baldwin.catalog_history import build_catalog_history
from galafresh_baldwin.parsers import normalize_catalog_product, normalize_promotions
from galafresh_baldwin.report import build_reports
from galafresh_baldwin.storage import write_snapshot_bundle


def row(identifier: int, price: float, observed: str, *, brand: str = "Brand"):
    return normalize_catalog_product(
        {
            "id": identifier,
            "name": f"Item {identifier}",
            "brand": brand,
            "imageUrl": f"https://images.example/items/{{{{size}}}}/{identifier}.{{{{extension||'jpg'}}}}",
            "branch": {"regularPrice": price, "isActive": True, "isVisible": True},
        },
        observed,
        "10",
        "Produce > Fresh",
    )


class AnalysisReportTests(unittest.TestCase):
    def test_second_fixture_day_produces_changes_and_explicit_calendar_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshots, docs = root / "data/snapshots", root / "docs"
            docs.mkdir()
            (docs / "METHODOLOGY.md").write_text("# Methodology\n\nMissing days remain gaps.")
            first = [row(1, 2, "2026-07-15T12:00:00Z"), row(2, 4, "2026-07-15T12:00:00Z", brand="Other Brand")]
            second = [row(1, 3, "2026-07-17T12:00:00Z"), row(3, 5, "2026-07-17T12:00:00Z")]
            promoted_raw = {
                "id": 1,
                "branch": {
                    "specials": [{"id": "offer-1", "description": "2 for $5", "firstLevel": {"quantity": 2, "price": 5}}]
                },
            }
            promotions = normalize_promotions(promoted_raw, "2026-07-17T12:00:00Z")
            write_snapshot_bundle(snapshots, "2026-07-15", first, [], {"status": "healthy", "observed_at": "2026-07-15T12:00:00Z"})
            write_snapshot_bundle(snapshots, "2026-07-17", second, promotions, {"status": "healthy", "observed_at": "2026-07-17T12:00:00Z"})
            summary = build_daily_summary(snapshots)
            self.assertEqual(summary["comparison"]["price_increases"], 1)
            self.assertEqual(summary["comparison"]["additions"], 1)
            self.assertEqual(summary["assortment_changes"]["additions"][0]["product_key"], "gala:1165:1329:3")
            index = build_catalog_history(snapshots, root / "history")
            self.assertEqual(index["calendar_days"], 3)
            self.assertEqual(index["total_items"], 3)
            self.assertEqual(index["filters"]["departments"], ["Produce"])
            self.assertEqual(index["filters"]["brands"], ["Brand", "Other Brand"])
            self.assertEqual(index["filters"]["price_range"], {"min": 3.0, "max": 5.0})
            item_one = next(item for item in index["items"] if item["retailer_product_id"] == "1")
            item_two = next(item for item in index["items"] if item["retailer_product_id"] == "2")
            self.assertEqual(item_one["latest_regular_price"], 3.0)
            self.assertEqual(item_one["latest_promotion_count"], 1)
            self.assertTrue(item_one["has_price_change"])
            self.assertEqual(item_one["observed_days"], 2)
            self.assertTrue(item_one["is_current"])
            self.assertFalse(item_two["is_current"])
            self.assertEqual(item_two["last_seen"], "2026-07-15")
            shard = item_one["shard"]
            import json
            detail = next(
                item
                for item in json.loads((root / "history" / f"{shard}.json").read_text())["items"]
                if item["product_key"] == item_one["product_key"]
            )
            self.assertIsNone(detail["observations"][1]["catalog"])
            self.assertEqual(detail["image_url"], "https://images.example/items/500/1.jpg")
            build_reports(snapshots, docs)
            for name in ("index.html", "daily-report.html", "weekly-report.html", "catalog.html", "catalog-history.html", "METHODOLOGY.html"):
                self.assertTrue((docs / name).exists())
            catalog_html = (docs / "catalog.html").read_text()
            catalog_js = (docs / "assets/catalog.js").read_text()
            self.assertIn('<dd id="total-items">3</dd>', catalog_html)
            self.assertIn('id="detail-panel"', catalog_html)
            self.assertIn('id="department-filter"', catalog_html)
            self.assertIn("downloadFilteredCsv", catalog_js)
            self.assertNotIn("slice(0,100)", catalog_js)
            self.assertIn("catalog.html", (docs / "catalog-history.html").read_text())
            self.assertTrue((docs / "data/daily-summary.json").exists())


if __name__ == "__main__":
    unittest.main()
