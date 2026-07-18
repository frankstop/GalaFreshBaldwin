# Data dictionary

All timestamps are ISO 8601 strings from the public source or UTC collector clock. Schema versions are strings. Missing values are JSON `null`, never a numeric zero substitute.

## Catalog observation (`*.catalog.jsonl.gz`)

| Field | Type | Meaning |
|---|---|---|
| `product_key` | string | Stable `gala:1165:1329:{retailer_product_id}` listing key. |
| `retailer_product_id` | string | Source `product.id`; primary listing identity. |
| `catalog_product_id` | string/null | Source `product.productId`; not a UPC and not necessarily unique. |
| `branch_product_id` | string/null | Source `product.branch.branchProductId`. |
| `name` | string | English public name with whitespace normalized only. |
| `brand` | string/null | English public brand spelling. |
| `regular_price` | number/null | Public online regular price; missing remains null. |
| `currency` | string | Currency code, expected `USD`. |
| `weight` | string/number/null | Source package or variable weight value. |
| `unit_of_measure` | string/null | Localized public unit label. |
| `unit_resolution` | string/number/null | Source unit increment. |
| `is_weighable` | boolean/null | Source variable-weight flag. |
| `is_out_of_stock` | boolean/null | Exposed branch stock flag; endpoint normally filters true values. |
| `is_active` | boolean/null | Exposed branch/listing active flag. |
| `is_visible` | boolean/null | Exposed branch/listing visibility flag. |
| `category_paths` | string[] | Sorted union of all observed localized category paths. |
| `source_category_ids` | string[] | Sorted union of root and response category IDs. |
| `image_url` | string/null | Public source image template/URL. |
| `promotion_ids` | string[] | Nested public promotion IDs, without changing regular price. |
| `sell_date_visible_until` | string/null | Source visibility end timestamp if exposed. |
| `observed_at` | string | UTC collection observation time. |
| `retailer` | string | `Gala Fresh Baldwin`. |
| `retailer_id` | integer | Fixed `1165`. |
| `branch_id` | integer | Fixed `1329`. |
| `market_reference` | string | Fixed Baldwin address. |
| `price_scope` | string | `public_online_catalog`. |
| `source_url` | string | Public storefront attribution URL. |
| `schema_version` | string | Catalog schema version. |

## Promotion observation (`*.promotions.jsonl.gz`)

| Field | Type | Meaning |
|---|---|---|
| `promotion_key` | string | Product key plus promotion ID and stable source-list index. |
| `promotion_id` | string | Source promotion ID or deterministic hash when absent. |
| `product_key` | string | Related catalog listing key. |
| `description` | string/null | Source promotion description. |
| `display_name` | string/null | Localized public display name. |
| `promotion_tag` | string/null | Localized short label such as “2 for $7”. |
| `valid_from`, `valid_to` | string/null | Source validity interval. |
| `is_coupon` | boolean/null | Source coupon flag. |
| `limit` | number/null | Exposed offer limit. |
| `first_level` | object/null | Preserved source first-level structure. |
| `levels` | object[] | Preserved source offer levels. |
| `raw_offer_structure` | object | Complete sanitized public nested special object. |
| `derived_effective_unit_price` | number/null | Conservative explicit quantity/total derivation. |
| `derivation_basis` | string/null | Human-readable evidence for the derivation. |
| `observed_at` | string | UTC collection observation time. |
| `retailer_id`, `branch_id` | integer | Fixed `1165` and `1329`. |
| `price_scope` | string | `public_online_catalog`. |
| `schema_version` | string | Promotion schema version. |

## Manifest (`*.manifest.json`)

| Field | Meaning |
|---|---|
| `snapshot_date`, `observed_at`, `status` | Daily identity, UTC observation time, and `healthy` publication state. |
| `retailer_id`, `branch_id`, `tree_id`, `tree_index_timestamp` | Verified market/tree evidence. |
| `visible_root_categories` | Current root IDs, names, and name paths. |
| `successful_root_categories` | Root IDs completing exact pagination. |
| `expected_products_from_api_totals` | Sum of per-root totals before cross-root deduplication. |
| `raw_product_records`, `unique_products`, `promotions` | Raw, deduplicated, and separate promotion counts. |
| `valid_price_percentage` | Share with finite positive regular prices. |
| `prior_overlap_percentage` | Prior keys present now; null for first baseline. |
| `product_count_change_percentage` | Change from prior healthy day; null for first baseline. |
| `duplicate_key_count` | Duplicates in final normalized key set; must be zero. |
| `requests`, `retries`, `elapsed_seconds` | Collection operations and duration. |
| `robots_sha256`, `robots_crawl_delay` | Access-policy evidence and enforced minimum delay. |
| `bootstrap_url` | Actually loaded cache-busted `data.js` asset. |
| `errors` | Nonfatal promotion warnings; catalog errors prevent manifest publication. |
| `discovered_category_nodes`, `discovered_visible_nodes` | Tree-shape contraction evidence. |
| `discovered_leaf_nodes`, `visible_product_bearing_leaf_nodes` | Evidence that visible-root descendant coverage remains a sound acquisition assumption. |
| `root_coverage_mode` | `visible_roots_with_descendants`; records why hundreds of leaves are not individually crawled. |
| `rolling_14_day_median_products`, `adaptive_product_floor` | Adaptive baseline metrics; null initially. |
| `schema_version` | Manifest schema version. |

## Daily summary

Top-level fields: `schema_version`, `report`, `status`, `scope`, `latest_healthy_observation`, `latest`, `previous`, `comparison`, `daily_history`, `comparison_history`, `price_increases`, `price_decreases`, `anomalies`, `assortment_changes`, `promotion_changes`, `active_promotions`, `category_summary`, `brand_summary`, `price_history_windows`, `snapshot_health_history`, and `methodology`.

Daily observations contain catalog size, valid-price rate, median/average regular price, and promoted-product count. Comparisons contain prior overlap, union-based assortment churn, matched count, increases/decreases, uncomparable/unchanged count, additions, returns, missing products, and anomaly count. Change rows retain old/new regular prices and category/brand context. Promotion changes provide exact start/end/change keys.

## Weekly summary

Top-level fields: `schema_version`, `report`, `status`, `scope`, `from_date`, `to_date`, `snapshot_days`, `latest_catalog_size`, median catalog/valid-price values, aggregate `price_increases`, `price_decreases`, `additions`, `returns`, `missing_products`, seven-day history/comparisons, category/brand summaries, health history, and methodology.

## Price-change contracts

`docs/data/price-changes/index.json` describes the complete archive without embedding every event. It contains archive dates, snapshot/comparison-day counts, total movements, increase/decrease counts, distinct products, global filter options, methodology, and `files`. Each file entry identifies one adjacent healthy comparison and its complete `YYYY-MM-DD.json` shard.

Each change event contains:

| Field | Type | Meaning |
|---|---|---|
| `event_key` | string | Stable comparison interval plus `product_key`. |
| `from_date`, `to_date` | date string | Adjacent healthy snapshot dates compared. |
| `calendar_gap_days` | integer | Calendar distance between those healthy observations. |
| `product_key`, source IDs | string/null | Stable retailer listing identity and retained source identifiers. |
| `name`, `brand`, `category_paths`, `departments` | mixed | Item context from the later observation. |
| `previous_regular_price`, `current_regular_price` | number | Finite positive public online regular prices compared. |
| `change`, `absolute_change` | number | Signed and absolute dollar movement. |
| `change_percentage`, `absolute_change_percentage` | number | Signed and absolute percentage movement from the previous price. |
| `direction` | string | `increase` or `decrease`. |
| `is_anomaly` | boolean | Whether the conservative documented anomaly rule matched. |

Items missing from either date and items without two valid positive prices do not become price-change events. Missingness remains represented in catalog history rather than being interpreted as a price movement.

## Catalog contracts

`docs/data/catalog-history/index.json` is the complete browse index. It contains `schema_version`, `from_date`, `to_date`, `calendar_days`, `total_items`, `filters`, and `items`. `filters` provides sorted `departments`, sorted `brands`, and the latest-known `price_range`. Each index item contains source identity and display fields plus:

| Field | Type | Meaning |
|---|---|---|
| `departments` | string[] | Top-level labels derived from all preserved category paths. |
| `latest_regular_price` | number/null | Regular price on the listing's most recent observed day; it may predate the latest snapshot when `is_current` is false. |
| `latest_promotion_count` | integer | Separate promotion observations on the archive's latest day. |
| `is_current` | boolean | Whether the item appears in the latest catalog snapshot. |
| `first_seen`, `last_seen` | date string | First and most recent healthy observation dates. |
| `observed_days` | integer | Count of healthy snapshot days containing this item. |
| `has_price_change` | boolean | Whether at least two distinct nonmissing regular prices appear in the item's archive. |
| `shard` | string | First two SHA-256 characters for the item detail file. |

Each `{shard}.json` contains complete items with the same browse fields, package/source metadata, and one observation slot per calendar date. An observation has `date`, nullable `catalog` (`regular_price`, `promotion_ids`, `is_out_of_stock`), and separate promotion entries. A null catalog is an explicit gap, not deletion or zero.
