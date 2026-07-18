from __future__ import annotations

from datetime import date, timedelta
import hashlib
from pathlib import Path
from typing import Any

from .storage import read_jsonl_gz, snapshot_files, write_json


def _date_range(start: str, end: str) -> list[str]:
    current, finish = date.fromisoformat(start), date.fromisoformat(end)
    result: list[str] = []
    while current <= finish:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def build_catalog_history(snapshot_dir: Path, output_dir: Path) -> dict[str, Any]:
    files = snapshot_files(snapshot_dir, "catalog")
    if not files:
        raise ValueError("no catalog snapshots found")
    dated = [(path.name[:10], read_jsonl_gz(path)) for path in files]
    days = _date_range(dated[0][0], dated[-1][0])
    items: dict[str, dict[str, Any]] = {}
    observations: dict[str, dict[str, dict[str, Any]]] = {}
    for snapshot_date, rows in dated:
        for row in rows:
            key = str(row["product_key"])
            items[key] = {
                "product_key": key,
                "name": row.get("name"),
                "brand": row.get("brand"),
                "category_paths": row.get("category_paths", []),
                "retailer_product_id": row.get("retailer_product_id"),
                "catalog_product_id": row.get("catalog_product_id"),
                "branch_product_id": row.get("branch_product_id"),
            }
            observations.setdefault(key, {})[snapshot_date] = {
                "regular_price": row.get("regular_price"),
                "promotion_ids": row.get("promotion_ids", []),
                "is_out_of_stock": row.get("is_out_of_stock"),
            }
    promotions: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for path in snapshot_files(snapshot_dir, "promotions"):
        snapshot_date = path.name[:10]
        for row in read_jsonl_gz(path):
            promotions.setdefault(str(row["product_key"]), {}).setdefault(snapshot_date, []).append({
                "promotion_id": row.get("promotion_id"),
                "description": row.get("description") or row.get("display_name"),
                "derived_effective_unit_price": row.get("derived_effective_unit_price"),
                "derivation_basis": row.get("derivation_basis"),
            })
    shards: dict[str, list[dict[str, Any]]] = {}
    index_items: list[dict[str, Any]] = []
    for key in sorted(items):
        shard = hashlib.sha256(key.encode()).hexdigest()[:2]
        item = {
            **items[key],
            "observations": [
                {
                    "date": day,
                    "catalog": observations.get(key, {}).get(day),
                    "promotions": promotions.get(key, {}).get(day, []),
                }
                for day in days
            ],
        }
        shards.setdefault(shard, []).append(item)
        index_items.append({**items[key], "shard": shard})
    output_dir.mkdir(parents=True, exist_ok=True)
    for shard, rows in sorted(shards.items()):
        write_json(output_dir / f"{shard}.json", {"schema_version": "1.0", "items": rows})
    index = {
        "schema_version": "1.0",
        "from_date": days[0],
        "to_date": days[-1],
        "calendar_days": len(days),
        "items": index_items,
    }
    write_json(output_dir / "index.json", index)
    return index

