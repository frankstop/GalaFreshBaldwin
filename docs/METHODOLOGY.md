# Methodology

## Scope

The observation scope is every anonymously visible product in the Gala Fresh Baldwin public online catalog, its online regular price, public category memberships, availability fields exposed by the storefront, and nested public promotions at collection time. Online values are not asserted as physical shelf prices. The storefront warns that website and branch prices may differ and variable-weight totals are estimates.

This is independent research and is not affiliated with Gala Fresh or stor.ai/SelfPoint.

## Collection and matching

One clean, non-persistent Playwright Chromium context reads the current public bootstrap and performs same-origin anonymous fetches. Visible root departments are discovered each run; observed counts are monitoring evidence, never hard-coded completion targets. Root results overlap and are deduplicated using `gala:1165:1329:{retailer_product_id}` while category memberships are unioned.

`retailer_product_id`, `catalog_product_id`, and `branch_product_id` are all retained. Public catalog IDs are not assumed to be UPCs. Live data has shown distinct retailer listings sharing a catalog product ID and URL, so catalog product ID is not the matching key. No UPC is invented.

## Prices, promotions, and variable weight

Regular prices must be finite and non-negative; missing and zero are distinct. A valid-price gate specifically requires finite **positive** prices for at least 95% of products. Missing prices stay null and are never interpolated.

Promotions are independent observations. A “2 for $7” offer never overwrites a $5.59 regular price. The source offer, levels, validity, limits, coupon status, and labels are preserved. An effective unit price is derived only from an explicit quantity/total structure or unambiguous display statement; the basis is recorded beside the derived value. Conditional or ambiguous offers remain underived.

Variable-weight flags, weight, unit of measure, and resolution are preserved. Observed prices and cart estimates are not converted into shelf-unit claims.

## Missingness and longitudinal interpretation

The storefront currently filters out out-of-stock products. A missing product therefore means only “not observed in that day's public result,” not deletion or confirmed unavailability. Item histories contain explicit null gaps for missing calendar days. Missing observations are never zero-filled or interpolated.

The first reviewed healthy run establishes the baseline. Comparisons start with the second healthy run. Additions have never appeared previously; returns appeared earlier but were absent on the immediately preceding observed day. Regular-price changes require valid observations on both comparison days.

The price-change archive compares each pair of adjacent healthy snapshot dates. It preserves the actual start and end dates and reports calendar gaps; it does not fabricate observations for dates with no healthy snapshot. Every comparable regular-price movement is stored in a daily derived shard without a display cap. Date-range filtering changes which shards are loaded, not how price changes are calculated.

## Validation and anomalies

Every selected root must reconcile exactly to its API total, and the final key set must be unique. After baseline, overlap must remain at least 80%, unexplained product-count drops over 25% are rejected, and major root/tree contractions are rejected. A rolling floor is 75% of the median of up to 14 prior healthy checked-in counts; no fixed floor is invented for the initial crawl.

An anomaly is a descriptive flag, not a prediction: absolute regular-price change of at least 20% and absolute robust median-absolute-deviation z-score of at least 3.5. No predictive claims are made.

## Responsible access

Before collection, the browser fetches `robots.txt`, verifies category and `/v2` access, and enforces the current crawl delay globally. Forbidden search, cart, user/account, coupon, order, recent-purchase, smart-list, and product-tag routes are blocked. The project does not authenticate, submit addresses, retain profiles/cookies, automate carts, use stealth, solve CAPTCHAs, rotate proxies, or collect customer information. Any access-policy or anonymous-contract change fails closed.

## Limitations

The research reflects only what the anonymous Baldwin storefront returned at observation time. It cannot establish in-store availability, shelf price, transaction eligibility, inventory quantity, promotion eligibility for a specific shopper, or why an item is absent. Source schemas, category trees, merchandising, and robots policy may change.
