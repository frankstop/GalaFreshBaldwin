from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable

from .models import (
    BRANCH_ID,
    CURRENCY,
    RETAILER_ID,
    CatalogObservation,
    PromotionObservation,
    finite_nonnegative,
)


class ContractError(ValueError):
    """Raised when the public storefront contract is incomplete or inconsistent."""


def balanced_object(text: str, start: int) -> str:
    """Extract one balanced JavaScript object/array while respecting strings."""
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] not in "[{":
        raise ContractError("frontendData assignment is not an object or array")
    pairs = {"{": "}", "[": "]"}
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "\"'`":
            quote = char
        elif char in pairs:
            stack.append(pairs[char])
        elif char in "}]":
            if not stack or stack.pop() != char:
                raise ContractError("unbalanced frontendData object")
            if not stack:
                return text[start : index + 1]
    raise ContractError("unterminated frontendData object")


def extract_frontend_data(script: str) -> dict[str, Any]:
    """Parse the JSON-compatible object assigned to window.sp.frontendData."""
    match = re.search(r"window\.sp\.frontendData\s*=\s*", script)
    if not match:
        raise ContractError("window.sp.frontendData assignment not found")
    raw = balanced_object(script, match.end())
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ContractError(f"frontendData is not strict JSON: {error}") from error
    if not isinstance(value, dict):
        raise ContractError("frontendData must be an object")
    return value


def _walk(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _find_scalar(data: Any, keys: set[str]) -> Any:
    normalized = {key.lower() for key in keys}
    for key, value in _walk(data):
        if key.lower() in normalized and not isinstance(value, (dict, list)):
            return value
    return None


def verify_market_identity(frontend: dict[str, Any]) -> None:
    """Fail closed unless the loaded bootstrap identifies Baldwin exactly."""
    retailer_object = frontend.get("retailer") if isinstance(frontend.get("retailer"), dict) else {}
    retailer = retailer_object.get("id") or _find_scalar(frontend, {"retailerId", "retailer_id"})
    branches = retailer_object.get("branches") if isinstance(retailer_object.get("branches"), list) else []
    branch = next((item.get("id") for item in branches if isinstance(item, dict) and str(item.get("id")) == str(BRANCH_ID)), None)
    branch = branch or _find_scalar(frontend, {"branchId", "branch_id"})
    if str(retailer) != str(RETAILER_ID) or str(branch) != str(BRANCH_ID):
        raise ContractError(f"unexpected market identity retailer={retailer!r} branch={branch!r}")


def _first(mapping: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value: Any = mapping
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value is not None:
            return value
    return None


def normalize_name(value: Any) -> str:
    """Normalize whitespace only, retaining spelling and punctuation."""
    return " ".join(str(value or "").split())


def _localized(value: Any) -> str:
    if isinstance(value, dict):
        names = value.get("names") if isinstance(value.get("names"), dict) else value
        localized = names.get("2") or names.get(2) or value.get("defaultName")
        if isinstance(localized, dict):
            localized = localized.get("name") or localized.get("long") or localized.get("short") or localized.get("displayName")
        return normalize_name(localized)
    return normalize_name(value)


def product_key(retailer_product_id: Any) -> str:
    if retailer_product_id is None or str(retailer_product_id).strip() == "":
        raise ContractError("product is missing retailer product id")
    return f"gala:{RETAILER_ID}:{BRANCH_ID}:{str(retailer_product_id).strip()}"


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if str(value).lower() in {"true", "1"}:
        return True
    if str(value).lower() in {"false", "0"}:
        return False
    return None


def _category_paths(raw: dict[str, Any]) -> tuple[list[str], list[str]]:
    paths: set[str] = set()
    ids: set[str] = set()
    categories = _first(raw, "family.categoriesPaths", "categories", "categoryPaths", "branch.categories") or []
    if isinstance(categories, dict):
        categories = [categories]
    for category in categories if isinstance(categories, list) else []:
        if isinstance(category, list):
            labels: list[str] = []
            for part in category:
                if isinstance(part, dict):
                    identifier = _first(part, "id", "categoryId", "categoryID")
                    if identifier is not None:
                        ids.add(str(identifier))
                    label = _localized(_first(part, "names", "displayName", "name"))
                    if label:
                        labels.append(label)
                elif part:
                    labels.append(normalize_name(part))
            if labels:
                paths.add(" > ".join(labels))
            continue
        if isinstance(category, str):
            paths.add(normalize_name(category))
            continue
        if not isinstance(category, dict):
            continue
        category_id = _first(category, "id", "categoryId", "categoryID")
        if category_id is not None:
            ids.add(str(category_id))
        labels = _first(category, "path", "names", "categoryPath")
        if isinstance(labels, list):
            paths.add(" > ".join(normalize_name(item.get("name") if isinstance(item, dict) else item) for item in labels))
        else:
            label = _localized(_first(category, "names", "displayName", "name"))
            if label:
                paths.add(label)
    return sorted(path for path in paths if path), sorted(ids)


def normalize_catalog_product(
    raw: dict[str, Any], observed_at: str, source_category_id: str, source_category_path: str
) -> CatalogObservation:
    retailer_product_id = _first(raw, "id", "retailerProductId")
    key = product_key(retailer_product_id)
    branch = raw.get("branch") if isinstance(raw.get("branch"), dict) else {}
    paths, ids = _category_paths(raw)
    paths.append(source_category_path)
    ids.append(str(source_category_id))
    price = finite_nonnegative(_first(raw, "branch.regularPrice", "branch.price", "regularPrice", "price"))
    specials = branch.get("specials") if isinstance(branch.get("specials"), list) else []
    promotion_ids = [str(_first(item, "id", "specialId", "promotionId")) for item in specials if isinstance(item, dict)]
    promotion_ids = [item for item in promotion_ids if item != "None"]
    image = _first(raw, "image.url", "imageUrl", "image", "images.0.url")
    if isinstance(image, dict):
        image = image.get("url")
    return CatalogObservation(
        product_key=key,
        retailer_product_id=str(retailer_product_id),
        catalog_product_id=str(_first(raw, "productId", "catalogProductId")) if _first(raw, "productId", "catalogProductId") is not None else None,
        branch_product_id=str(_first(raw, "branch.branchProductId", "branchProductId")) if _first(raw, "branch.branchProductId", "branchProductId") is not None else None,
        name=_localized(_first(raw, "names", "name", "displayName")),
        brand=_localized(_first(raw, "brand.names", "brand.name", "brand")) or None,
        regular_price=price,
        currency=str(_first(raw, "branch.currency", "currency") or CURRENCY),
        weight=_first(raw, "weight", "branch.weight"),
        unit_of_measure=_localized(_first(raw, "unitOfMeasure", "unit", "branch.unitOfMeasure")) or None,
        unit_resolution=_first(raw, "unitResolution", "branch.unitResolution"),
        is_weighable=_bool(_first(raw, "isWeighable", "weighable", "branch.isWeighable")),
        is_out_of_stock=_bool(_first(raw, "branch.isOutOfStock", "isOutOfStock")),
        is_active=_bool(_first(raw, "branch.isActive", "isActive", "active")),
        is_visible=_bool(_first(raw, "branch.isVisible", "isVisible", "visible")),
        category_paths=sorted(set(paths)),
        source_category_ids=sorted(set(ids)),
        image_url=str(image) if image else None,
        promotion_ids=sorted(set(promotion_ids)),
        sell_date_visible_until=_first(raw, "branch.sellDateVisibleUntil", "sellDateVisibleUntil"),
        observed_at=observed_at,
        source_url=f"https://www.shopgalafresh.com/v2/retailers/{RETAILER_ID}/branches/{BRANCH_ID}/categories/{source_category_id}/products",
    )


def _derive_multibuy(special: dict[str, Any]) -> tuple[float | None, str | None]:
    """Conservatively derive only explicit quantity-for-price offers."""
    candidates: list[dict[str, Any]] = []
    first = special.get("firstLevel")
    if isinstance(first, dict):
        candidates.append(first)
    levels = special.get("levels")
    if isinstance(levels, list):
        candidates.extend(level for level in levels if isinstance(level, dict))
    candidates.append(special)
    for value in candidates:
        quantity = finite_nonnegative(_first(value, "quantity", "requiredQuantity", "buyQuantity"))
        total = finite_nonnegative(_first(value, "price", "totalPrice", "offerPrice"))
        if quantity and quantity > 0 and total is not None and not _bool(_first(value, "isCoupon", "coupon")):
            return round(total / quantity, 4), f"explicit {quantity:g} units for ${total:g}"
    description = _localized(_first(special, "description", "names", "displayName"))
    match = re.fullmatch(
        r"(?i)(?:(?:buy\s+)?(\d+(?:\.\d+)?)\s+(?:units?.*?\s+)?for\s+\$?(\d+(?:\.\d{1,2})?))",
        description,
    )
    if match and float(match.group(1)) > 0:
        quantity, total = float(match.group(1)), float(match.group(2))
        return round(total / quantity, 4), f"unambiguous display text: {description}"
    return None, None


def normalize_promotions(raw: dict[str, Any], observed_at: str) -> list[PromotionObservation]:
    key = product_key(_first(raw, "id", "retailerProductId"))
    specials = _first(raw, "branch.specials") or []
    if not isinstance(specials, list):
        return []
    result: list[PromotionObservation] = []
    for index, special in enumerate(specials):
        if not isinstance(special, dict):
            continue
        promotion_id = _first(special, "id", "specialId", "promotionId")
        if promotion_id is None:
            promotion_id = hashlib.sha256(json.dumps(special, sort_keys=True).encode()).hexdigest()[:16]
        promotion_id = str(promotion_id)
        effective, basis = _derive_multibuy(special)
        first_level = special.get("firstLevel") if isinstance(special.get("firstLevel"), dict) else None
        levels = special.get("levels") if isinstance(special.get("levels"), list) else []
        result.append(
            PromotionObservation(
                promotion_key=f"{key}:{promotion_id}:{index}",
                promotion_id=promotion_id,
                product_key=key,
                description=_localized(special.get("description")) or None,
                display_name=_localized(_first(special, "names", "displayName")) or None,
                promotion_tag=_localized(_first(special, "names.2.promotionTag", "promotionTag", "tag")) or None,
                valid_from=_first(special, "validFrom", "startDate", "from"),
                valid_to=_first(special, "validTo", "endDate", "to"),
                is_coupon=_bool(_first(special, "isCoupon", "coupon")),
                limit=_first(special, "limit", "purchaseLimit"),
                first_level=copy.deepcopy(first_level),
                levels=copy.deepcopy([level for level in levels if isinstance(level, dict)]),
                raw_offer_structure=copy.deepcopy(special),
                derived_effective_unit_price=effective,
                derivation_basis=basis,
                observed_at=observed_at,
            )
        )
    return result


def merge_product_observations(observations: Iterable[CatalogObservation]) -> list[CatalogObservation]:
    """Deduplicate overlapping roots and union all observed memberships."""
    merged: dict[str, CatalogObservation] = {}
    for observation in observations:
        existing = merged.get(observation.product_key)
        if existing is None:
            merged[observation.product_key] = observation
            continue
        existing.category_paths = sorted(set(existing.category_paths) | set(observation.category_paths))
        existing.source_category_ids = sorted(set(existing.source_category_ids) | set(observation.source_category_ids))
        existing.promotion_ids = sorted(set(existing.promotion_ids) | set(observation.promotion_ids))
    return [merged[key] for key in sorted(merged)]
