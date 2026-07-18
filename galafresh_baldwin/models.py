from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any

SCHEMA_VERSION = "1.0"
RETAILER = "Gala Fresh Baldwin"
RETAILER_ID = 1165
BRANCH_ID = 1329
MARKET_REFERENCE = "2485 Grand Ave, Baldwin, NY 11510"
PRICE_SCOPE = "public_online_catalog"
CURRENCY = "USD"


def finite_nonnegative(value: Any) -> float | None:
    """Return a finite non-negative float, preserving missing as None."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number >= 0 else None


@dataclass(frozen=True, slots=True)
class CategoryRoot:
    category_id: str
    name: str
    path_names: tuple[str, ...]
    path_ids: tuple[str, ...]
    visible: bool = True


@dataclass(slots=True)
class CatalogObservation:
    product_key: str
    retailer_product_id: str
    catalog_product_id: str | None
    branch_product_id: str | None
    name: str
    brand: str | None
    regular_price: float | None
    currency: str
    weight: str | float | None
    unit_of_measure: str | None
    unit_resolution: str | float | None
    is_weighable: bool | None
    is_out_of_stock: bool | None
    is_active: bool | None
    is_visible: bool | None
    category_paths: list[str]
    source_category_ids: list[str]
    image_url: str | None
    promotion_ids: list[str]
    sell_date_visible_until: str | None
    observed_at: str
    retailer: str = RETAILER
    retailer_id: int = RETAILER_ID
    branch_id: int = BRANCH_ID
    market_reference: str = MARKET_REFERENCE
    price_scope: str = PRICE_SCOPE
    source_url: str = "https://www.shopgalafresh.com/"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["category_paths"] = sorted(set(self.category_paths))
        value["source_category_ids"] = sorted(set(self.source_category_ids))
        value["promotion_ids"] = sorted(set(self.promotion_ids))
        return value


@dataclass(slots=True)
class PromotionObservation:
    promotion_key: str
    promotion_id: str
    product_key: str
    description: str | None
    display_name: str | None
    promotion_tag: str | None
    valid_from: str | None
    valid_to: str | None
    is_coupon: bool | None
    limit: float | int | None
    first_level: dict[str, Any] | None
    levels: list[dict[str, Any]]
    raw_offer_structure: dict[str, Any]
    derived_effective_unit_price: float | None
    derivation_basis: str | None
    observed_at: str
    retailer_id: int = RETAILER_ID
    branch_id: int = BRANCH_ID
    price_scope: str = PRICE_SCOPE
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Manifest:
    snapshot_date: str
    observed_at: str
    status: str
    retailer_id: int
    branch_id: int
    tree_id: str | None
    tree_index_timestamp: str | None
    visible_root_categories: list[dict[str, Any]]
    successful_root_categories: list[str]
    expected_products_from_api_totals: int
    raw_product_records: int
    unique_products: int
    promotions: int
    valid_price_percentage: float
    prior_overlap_percentage: float | None
    product_count_change_percentage: float | None
    duplicate_key_count: int
    requests: int
    retries: int
    elapsed_seconds: float
    robots_sha256: str
    robots_crawl_delay: float
    bootstrap_url: str
    errors: list[str] = field(default_factory=list)
    discovered_category_nodes: int = 0
    discovered_visible_nodes: int = 0
    discovered_leaf_nodes: int = 0
    visible_product_bearing_leaf_nodes: int = 0
    root_coverage_mode: str = "visible_roots_with_descendants"
    rolling_14_day_median_products: float | None = None
    adaptive_product_floor: int | None = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
