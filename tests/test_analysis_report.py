from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from galafresh_baldwin.analysis import build_daily_summary
from galafresh_baldwin.catalog_history import build_catalog_history
from galafresh_baldwin.parsers import normalize_catalog_product
from galafresh_baldwin.report import build_reports
from galafresh_baldwin.storage import write_snapshot_bundle


def row(identifier: int, price: float, observed: str):
    return normalize_catalog_product({"id": identifier, "name": f"Item {identifier}", "brand": "Brand", "branch": {"regularPrice": price}}, observed, "10", "Produce")


class AnalysisReportTests(unittest.TestCase):
    def test_second_fixture_day_produces_changes_and_explicit_calendar_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshots, docs = root / "data/snapshots", root / "docs"
            docs.mkdir()
            (docs / "METHODOLOGY.md").write_text("# Methodology\n\nMissing days remain gaps.")
            write_snapshot_bundle(snapshots, "2026-07-15", [row(1, 2, "2026-07-15T12:00:00Z"), row(2, 4, "2026-07-15T12:00:00Z")], [], {"status": "healthy", "observed_at": "2026-07-15T12:00:00Z"})
            write_snapshot_bundle(snapshots, "2026-07-17", [row(1, 3, "2026-07-17T12:00:00Z"), row(3, 5, "2026-07-17T12:00:00Z")], [], {"status": "healthy", "observed_at": "2026-07-17T12:00:00Z"})
            summary = build_daily_summary(snapshots)
            self.assertEqual(summary["comparison"]["price_increases"], 1)
            self.assertEqual(summary["comparison"]["additions"], 1)
            self.assertEqual(summary["assortment_changes"]["additions"][0]["product_key"], "gala:1165:1329:3")
            index = build_catalog_history(snapshots, root / "history")
            self.assertEqual(index["calendar_days"], 3)
            shard = index["items"][0]["shard"]
            import json
            detail = json.loads((root / "history" / f"{shard}.json").read_text())["items"][0]
            self.assertIsNone(detail["observations"][1]["catalog"])
            build_reports(snapshots, docs)
            for name in ("index.html", "daily-report.html", "weekly-report.html", "catalog-history.html", "METHODOLOGY.html"):
                self.assertTrue((docs / name).exists())
            self.assertIn("const esc", (docs / "catalog-history.html").read_text())
            self.assertTrue((docs / "data/daily-summary.json").exists())


if __name__ == "__main__":
    unittest.main()
