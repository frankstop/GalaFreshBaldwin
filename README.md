# Gala Fresh Baldwin Catalog Research

Daily longitudinal research on the anonymous public digital storefront for **Gala Fresh Baldwin**, retailer `1165`, branch `1329`, at 2485 Grand Ave, Baldwin, NY 11510.

This project records the public **online** catalog: products, regular online prices, exposed availability, category memberships, and public promotions at collection time. It does not claim that online values are physical shelf prices. Gala Fresh states that website prices may differ from branch prices and that variable-weight totals are estimates. This is independent research and is not affiliated with Gala Fresh, stor.ai, or SelfPoint.

## Status and published research

The reviewed 2026-07-17 healthy crawl establishes the baseline: 9,606 unique Baldwin listings and 775 separate promotion observations. Comparisons begin with the second healthy crawl; no prior history is fabricated.

- Pages: <https://frankstop.github.io/GalaFreshBaldwin/>
- Daily report: <https://frankstop.github.io/GalaFreshBaldwin/daily-report.html>
- Weekly report: <https://frankstop.github.io/GalaFreshBaldwin/weekly-report.html>
- Catalog history: <https://frankstop.github.io/GalaFreshBaldwin/catalog-history.html>

## Architecture

The pipeline has three boundaries:

1. **Raw evidence** — Playwright Chromium reads the current `window.sp.frontendData`, dynamically selects visible root departments, and calls the anonymous same-origin products API serially. Daily catalog and promotion observations are stored separately as deterministic gzip JSONL with a manifest.
2. **Derived research** — one tested Python analysis layer calculates daily/weekly changes, gaps, churn, regular-price movements, promotion transitions, summaries, and conservative anomalies entirely offline.
3. **Published views** — static HTML reads stable JSON contracts. JavaScript renders metrics; it does not independently calculate them.

Acquisition, parsing, discovery, models, validation, storage, analysis, catalog history, and rendering are separate modules under `galafresh_baldwin/`. See [Architecture](docs/ARCHITECTURE.md), [Data dictionary](docs/DATA_DICTIONARY.md), and [Methodology](docs/METHODOLOGY.md).

## Commands

Requires Python 3.11+.

```bash
python -m pip install -e .
python -m playwright install chromium
python -m galafresh_baldwin run --verbose
python -m galafresh_baldwin report
python -m galafresh_baldwin smoke --category-id 94013 --root /tmp/galafresh-smoke
python -m unittest discover -v
python scripts/check.py
```

`run` and `smoke` accept `--root`, `--snapshot-date`, `--headed`, `--request-delay`, `--retry-count`, `--timeout`, and `--diagnostic-limit`. Production always enforces the robots-derived minimum delay even when the CLI requests less. A diagnostic root limit causes production validation to fail rather than publish a partial snapshot. Smoke mode requires an isolated root and lowers integrity thresholds; it can never write the production snapshot directory.

## Snapshot contract

Healthy dates produce:

```text
data/snapshots/YYYY-MM-DD.catalog.jsonl.gz
data/snapshots/YYYY-MM-DD.promotions.jsonl.gz
data/snapshots/YYYY-MM-DD.manifest.json
```

Files are staged and the complete snapshot/report directories are transactionally replaced only after collection, normalization, validation, and offline report generation succeed. A failed or partial run leaves the prior healthy state intact. A same-day healthy manual rerun may replace that date. Report generation never rewrites an earlier healthy raw observation.

Status meanings:

- `awaiting_baseline`: no reviewed production snapshot is checked in.
- `healthy`: all collection and integrity gates passed.
- `baseline_established`: one healthy day is available; no comparison is possible.
- `comparison_available`: at least two healthy observations can be compared.
- workflow failure: no new manifest is published; the Actions summary exposes the failure.

## Responsible-access boundary

Every collection starts in one clean, non-persistent Chromium context. It fetches and parses `robots.txt`, verifies both category and `/v2` paths remain permitted, and applies one serial global limiter to storefront requests, bootstrap resources, product calls, and retries. The current crawl delay is observed dynamically (four seconds at implementation time).

The collector never visits or automates search, carts, accounts, coupons, order history, recent purchases, smart lists, or product-tag paths. It never submits an address, creates an account, signs in, adds to a cart, places an order, or uses customer cookies. There are no stealth plugins, CAPTCHA bypasses, proxies, persisted profiles, or authenticated sessions. Robots restrictions, CAPTCHA/authentication, repeated 403 responses, identity mismatches, or contract changes fail closed.

## Integrity gates

A production run is rejected unless robots permits collection; Baldwin identity and tree data exist; all 19-or-currently-visible roots complete; each root exactly reconciles its API `total`; pagination is unique and terminating; normalized keys are unique; at least 95% of products have finite positive regular prices; prior overlap is at least 80%; product count does not fall by more than 25%; and the root/tree shape does not suspiciously contract.

There is no invented initial product minimum. The first checked-in healthy run becomes the reviewed baseline. Later runs also use a floor at 75% of the rolling median of up to 14 prior healthy product counts.

## Automation

The daily workflow runs at `10:15 UTC`, supports explicit `verify` and `collect` dispatch modes, installs Playwright Chromium with Linux dependencies, runs all offline tests and `scripts/check.py`, always writes a step summary, and commits raw and derived outputs together only after success. Concurrency is serialized and the initial timeout is 90 minutes.

## Identity and missingness

The stable key is `gala:1165:1329:{retailer_product_id}`. All three source IDs are retained. `catalog_product_id` is neither assumed to be a UPC nor unique across retailer listings. Daily absence is missingness, not automatic deletion; gaps remain explicit and are never converted to zero or interpolated.

## License

MIT. Source storefront content remains attributable to its respective owners.
