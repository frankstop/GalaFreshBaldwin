from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from galafresh_baldwin.models import CatalogObservation
from galafresh_baldwin.parsers import normalize_catalog_product
from galafresh_baldwin.storage import read_jsonl_gz, write_snapshot_bundle
from galafresh_baldwin.validation import ValidationError, validate_collection


def product(identifier: int, price: float | None = 2.0) -> CatalogObservation:
    return normalize_catalog_product(
        {"id": identifier, "name": f"Item {identifier}", "branch": {"regularPrice": price}},
        "2026-07-17T12:00:00Z", "10", "Produce",
    )


class StorageTests(unittest.TestCase):
    def test_same_day_healthy_rerun_replaces_all_channels_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = {"status": "healthy", "unique_products": 1}
            paths = write_snapshot_bundle(root, "2026-07-17", [product(1)], [], manifest)
            first_bytes = paths[0].read_bytes()
            write_snapshot_bundle(root, "2026-07-17", [product(2)], [], manifest)
            self.assertEqual(read_jsonl_gz(paths[0])[0]["retailer_product_id"], "2")
            write_snapshot_bundle(root, "2026-07-17", [product(1)], [], manifest)
            self.assertEqual(paths[0].read_bytes(), first_bytes)
            self.assertFalse(list(root.glob("*.tmp")))

    def test_failed_staging_preserves_existing_bundle_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = write_snapshot_bundle(root, "2026-07-17", [product(1)], [], {"status": "healthy"})
            original = [path.read_bytes() for path in paths]
            with self.assertRaises(TypeError):
                write_snapshot_bundle(root, "2026-07-17", [object()], [], {"status": "healthy"})
            self.assertEqual([path.read_bytes() for path in paths], original)
            self.assertFalse(list(root.glob(".*.stage-*")))


class ValidationTests(unittest.TestCase):
    def test_first_baseline_has_no_overlap_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            metrics = validate_collection(
                [product(index) for index in range(20)], snapshot_dir=Path(temporary), snapshot_date="2026-07-17",
                visible_root_count=19, visible_node_count=700, all_roots_succeeded=True, api_totals_reconciled=True,
            )
            self.assertIsNone(metrics.prior_overlap_percentage)
            self.assertIsNone(metrics.adaptive_product_floor)

    def test_prior_overlap_and_drop_gates_reject_partial_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior = [product(index) for index in range(100)]
            write_snapshot_bundle(root, "2026-07-16", prior, [], {
                "status": "healthy", "unique_products": 100, "visible_root_categories": [{}] * 19,
                "discovered_visible_nodes": 700,
            })
            baseline_bytes = (root / "2026-07-16.catalog.jsonl.gz").read_bytes()
            with self.assertRaises(ValidationError):
                validate_collection(
                    [product(index) for index in range(50, 100)], snapshot_dir=root, snapshot_date="2026-07-17",
                    visible_root_count=19, visible_node_count=700, all_roots_succeeded=True, api_totals_reconciled=True,
                )
            self.assertEqual((root / "2026-07-16.catalog.jsonl.gz").read_bytes(), baseline_bytes)

    def test_visible_tree_contraction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior = [product(index) for index in range(20)]
            write_snapshot_bundle(root, "2026-07-16", prior, [], {
                "status": "healthy", "unique_products": 20, "visible_root_categories": [{}] * 20,
                "discovered_visible_nodes": 800,
            })
            with self.assertRaisesRegex(ValidationError, "contraction"):
                validate_collection(
                    prior, snapshot_dir=root, snapshot_date="2026-07-17", visible_root_count=10,
                    visible_node_count=400, all_roots_succeeded=True, api_totals_reconciled=True,
                )

    def test_missing_and_invalid_prices_are_not_treated_as_zero_valid_prices(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            rows = [product(index) for index in range(18)] + [product(19, None), product(20, float("nan"))]
            with self.assertRaisesRegex(ValidationError, "price rate"):
                validate_collection(
                    rows, snapshot_dir=Path(temporary), snapshot_date="2026-07-17", visible_root_count=1,
                    visible_node_count=1, all_roots_succeeded=True, api_totals_reconciled=True,
                )

    def test_missing_product_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            rows = [product(index) for index in range(20)]
            rows[0].name = ""
            with self.assertRaisesRegex(ValidationError, "missing normalized names"):
                validate_collection(
                    rows, snapshot_dir=Path(temporary), snapshot_date="2026-07-17", visible_root_count=1,
                    visible_node_count=1, all_roots_succeeded=True, api_totals_reconciled=True,
                )


if __name__ == "__main__":
    unittest.main()
