from __future__ import annotations

import json
from pathlib import Path
import unittest

from galafresh_baldwin.discovery import discover_visible_roots, find_category
from galafresh_baldwin.parsers import (
    ContractError,
    extract_frontend_data,
    merge_product_observations,
    normalize_catalog_product,
    normalize_promotions,
    verify_market_identity,
)

FIXTURES = Path(__file__).parent / "fixtures"


class BootstrapTests(unittest.TestCase):
    def test_balanced_extraction_and_root_visibility(self) -> None:
        data = extract_frontend_data((FIXTURES / "frontend_data.js").read_text())
        discovery = discover_visible_roots(data)
        self.assertEqual([root.name for root in discovery.roots], ["Produce", "Dairy"])
        self.assertEqual(discovery.tree_id, "129")
        self.assertEqual(discovery.total_nodes, 4)
        self.assertEqual(discovery.visible_nodes, 3)
        self.assertEqual(discovery.leaf_nodes, 3)
        self.assertEqual(discovery.visible_product_bearing_leaves, 2)
        self.assertEqual(find_category(data, "11").path_names, ("Produce", "Fruit"))

    def test_wrong_market_fails_closed(self) -> None:
        with self.assertRaises(ContractError):
            verify_market_identity({"retailerId": 1167, "branchId": 1331})


class NormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = json.loads((FIXTURES / "products_page.json").read_text())["products"]

    def test_identity_price_weight_and_multibuy_are_separate(self) -> None:
        catalog = normalize_catalog_product(self.raw[0], "2026-07-17T12:00:00Z", "10", "Produce")
        promotions = normalize_promotions(self.raw[0], catalog.observed_at)
        self.assertEqual(catalog.product_key, "gala:1165:1329:501")
        self.assertEqual(catalog.name, "Gala Apple")
        self.assertEqual(catalog.regular_price, 5.59)
        self.assertTrue(catalog.is_weighable)
        self.assertEqual(promotions[0].derived_effective_unit_price, 3.5)
        self.assertEqual(catalog.regular_price, 5.59)

    def test_catalog_id_collision_does_not_merge_retailer_listings(self) -> None:
        rows = [normalize_catalog_product(raw, "2026-07-17T12:00:00Z", "10", "Produce") for raw in self.raw]
        self.assertEqual(len(merge_product_observations(rows)), 2)
        self.assertEqual(rows[1].regular_price, 0.0)

    def test_overlapping_roots_merge_memberships(self) -> None:
        first = normalize_catalog_product(self.raw[0], "2026-07-17T12:00:00Z", "10", "Produce")
        second = normalize_catalog_product(self.raw[0], "2026-07-17T12:00:00Z", "30", "Fresh")
        merged = merge_product_observations([first, second])
        self.assertEqual(len(merged), 1)
        self.assertIn("Produce", merged[0].category_paths)
        self.assertIn("Fresh", merged[0].category_paths)
        self.assertEqual(merged[0].source_category_ids, ["10", "11", "30"])

    def test_live_localized_shapes_normalize_to_strings(self) -> None:
        raw = {
            "id": 99,
            "names": {"2": {"short": "Frozen Fish", "long": "Frozen Fish Fillets"}},
            "brand": {"names": {"2": "NAFCO"}},
            "unitOfMeasure": {"defaultName": "אוז", "names": {"2": "Oz"}},
            "family": {"categoriesPaths": [[
                {"id": 10, "names": {"2": "Meat & Seafood"}},
                {"id": 11, "names": {"2": "Frozen Fish"}}
            ]]},
            "branch": {"regularPrice": 12.99, "specials": [{
                "id": 4,
                "description": "Buy 2 units from products of Brand for $7",
                "names": {"2": {"name": "Buy 2 units from products of Brand for $7", "promotionTag": "2 for $7"}},
            }]},
        }
        catalog = normalize_catalog_product(raw, "2026-07-17T12:00:00Z", "1", "Frozen")
        promotion = normalize_promotions(raw, catalog.observed_at)[0]
        self.assertEqual((catalog.name, catalog.brand, catalog.unit_of_measure), ("Frozen Fish Fillets", "NAFCO", "Oz"))
        self.assertIn("Meat & Seafood > Frozen Fish", catalog.category_paths)
        self.assertEqual(catalog.source_category_ids, ["1", "10", "11"])
        self.assertEqual(promotion.promotion_tag, "2 for $7")
        self.assertEqual(promotion.derived_effective_unit_price, 3.5)

    def test_conditional_or_ambiguous_promotion_is_not_derived(self) -> None:
        raw = {"id": 1, "branch": {"specials": [{"id": 2, "description": "Save up to $3 with loyalty account"}]}}
        promotion = normalize_promotions(raw, "2026-07-17T12:00:00Z")[0]
        self.assertIsNone(promotion.derived_effective_unit_price)
        self.assertIsNone(promotion.derivation_basis)


if __name__ == "__main__":
    unittest.main()
