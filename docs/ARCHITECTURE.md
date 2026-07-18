# Architecture

## Fixed market boundary

The repository accepts only Gala Fresh Baldwin retailer `1165`, branch `1329`. Riverhead (`1167`/`1331`) is a different market and cannot enter these snapshots. Keys include retailer and branch so a future separately partitioned dataset can use the same model without collision.

## Raw → derived → published

### Raw evidence

`browser_source.py` opens one clean headless Chromium context. The request router blocks forbidden paths and image/font/media downloads, counts requests, and serializes every GalaFresh or `data.js` request through one rate limiter. The browser loads `robots.txt` first, raises the configured delay to its current `Crawl-delay`, then loads the homepage and identifies the cache-busted Azure Blob `data.js` from actual resource entries.

`discovery.py` reads the serializable `window.sp.frontendData`, verifies `retailer.id=1165` and a branch with `id=1329`, finds the current tree and localized English names, and selects visible top-level roots with Baldwin-visible products. A smoke category is resolved from that same live tree, including its complete name path.

Root requests use `appId=4`, offsets, `size=100`, `languageId=2`, `minScore=0`, repeated live path names, and the public out-of-stock exclusion. Pagination advances by the actual returned count. Missing/inconsistent totals, non-JSON responses, empty intermediate pages, repeated pages, duplicate page IDs, offset loops, 403s, and count mismatches are fatal.

Overlapping roots are expected. `parsers.py` normalizes each observation, then merges duplicate retailer listing keys and unions every category path/source ID. Nested promotions are normalized to a separate channel. Promotion failure can become a manifest warning; catalog completion cannot.

`storage.py` emits deterministic JSON and gzip (`mtime=0`). The pipeline builds the full next `data/snapshots/` and `docs/` trees in a same-filesystem staging area. Only after validation and report generation pass are both directories replaced transactionally with rollback backups.

### Derived research

`analysis.py` is the sole business-metric layer. It reads checked-in gzip snapshots without Playwright or network access and produces stable daily, weekly, and complete price-change contracts. It preserves missing prices and dates, matches on `product_key`, separates first additions from later returns, compares regular prices only when both observations are valid, and compares promotion structures independently. Price movements are sharded by comparison end date so an arbitrary date range can load complete records without one permanently growing payload.

`catalog_history.py` constructs the union catalog. Every item receives an observation slot for every calendar day from first to latest snapshot, with `catalog: null` for gaps. The index includes tested browse fields such as latest known price, current-snapshot presence, first/last seen dates, promotion count, departments, and recorded-price-change state. Shards are selected by the first two characters of SHA-256 over the stable key.

### Published views

`report.py` writes `daily-summary.json`, `weekly-summary.json`, the price-change index/daily shards, the catalog index/shards, and accessible responsive HTML. The Price Changes page exposes date ranges, direction/department/brand/threshold/anomaly filters, complete filtered exports, and item movement timelines. The Catalog page makes every union item reachable with filtering and transparent pagination, while detailed daily evidence loads from a deterministic shard into a side inspector. Page JavaScript only selects, filters, and formats already-derived contract fields. It does not recalculate catalog or change metrics.

## Failure rules

- Robots, CAPTCHA/authentication, repeated 403, wrong market, missing tree, or public-contract ambiguity: close Chromium and publish nothing.
- Any incomplete root or pagination mismatch: publish nothing.
- Any validation gate or report-generation failure: keep the prior snapshot and Pages tree.
- Same-day healthy rerun: replace all three same-day channels and all derived pages together.
- Offline report rebuild: read snapshots and replace only the derived Pages tree; never mutate raw snapshots.
- Workflow failure: do not stage/commit data; expose the exception and latest healthy manifest in the GitHub step summary.

## Dependency boundary

Python's standard library handles models, gzip, JSON, validation, analysis, and HTML generation. Playwright is the only runtime dependency because the public product endpoint is browser-only at the edge.
