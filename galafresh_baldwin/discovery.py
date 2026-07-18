from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import BRANCH_ID, RETAILER_ID, CategoryRoot
from .parsers import ContractError, verify_market_identity


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    tree_id: str | None
    tree_index_timestamp: str | None
    roots: tuple[CategoryRoot, ...]
    total_nodes: int
    visible_nodes: int
    leaf_nodes: int = 0
    visible_product_bearing_leaves: int = 0


def _children(node: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for key in ("children", "categories", "subCategories", "nodes"):
        value = node.get(key)
        if isinstance(value, list):
            children.extend(child for child in value if isinstance(child, dict))
    return children


def _node_id(node: dict[str, Any]) -> str | None:
    for key in ("id", "categoryId", "categoryID", "identifier"):
        if node.get(key) is not None:
            return str(node[key])
    return None


def _name(node: dict[str, Any]) -> str:
    for key in ("displayName", "name", "title"):
        if node.get(key):
            return " ".join(str(node[key]).split())
    names = node.get("names")
    if isinstance(names, dict):
        value = names.get("2") or names.get(2) or next(iter(names.values()), "")
        return " ".join(str(value).split())
    return ""


def _visible(node: dict[str, Any]) -> bool:
    for key in ("isVisible", "visible", "isActive", "active"):
        if key in node:
            if node[key] is False or str(node[key]).lower() == "false":
                return False
    branches = node.get("branches")
    if isinstance(branches, dict):
        branch = branches.get(str(BRANCH_ID)) or branches.get(BRANCH_ID)
        if isinstance(branch, dict):
            if branch.get("isVisible") is False or branch.get("hasVisibleProducts") is False:
                return False
    return not bool(node.get("hidden", False))


def _has_visible_products(node: dict[str, Any]) -> bool:
    branches = node.get("branches")
    if isinstance(branches, dict):
        branch = branches.get(str(BRANCH_ID)) or branches.get(BRANCH_ID)
        if isinstance(branch, dict) and "hasVisibleProducts" in branch:
            return branch.get("hasVisibleProducts") is True
    return _visible(node)


def walk_categories(nodes: Iterable[dict[str, Any]], path_names: tuple[str, ...] = (), path_ids: tuple[str, ...] = ()):
    for node in nodes:
        name = _name(node)
        identifier = _node_id(node)
        next_names = path_names + ((name,) if name else ())
        next_ids = path_ids + ((identifier,) if identifier else ())
        yield node, next_names, next_ids
        yield from walk_categories(_children(node), next_names, next_ids)


def _candidate_lists(value: Any) -> Iterable[tuple[dict[str, Any], list[dict[str, Any]]]]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"categorytree", "categorytrees", "trees", "categories", "nodes"} and isinstance(child, list):
                dictionaries = [item for item in child if isinstance(item, dict)]
                if dictionaries:
                    yield value, dictionaries
            yield from _candidate_lists(child)
    elif isinstance(value, list):
        for child in value:
            yield from _candidate_lists(child)


def _best_tree(frontend: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    best_parent: dict[str, Any] | None = None
    best: list[dict[str, Any]] = []
    for parent, candidates in _candidate_lists(frontend):
        score = sum(1 for item in candidates if _node_id(item) and (_name(item) or _children(item)))
        if score > sum(1 for item in best if _node_id(item)):
            best = candidates
            best_parent = parent
    return best_parent, best


def discover_visible_roots(frontend: dict[str, Any]) -> DiscoveryResult:
    """Verify Baldwin and select visible top-level departments dynamically."""
    verify_market_identity(frontend)
    parent, roots = _best_tree(frontend)
    if not roots:
        raise ContractError(f"no category tree for retailer {RETAILER_ID} branch {BRANCH_ID}")
    all_nodes = list(walk_categories(roots))
    leaves = [(node, names, ids) for node, names, ids in all_nodes if not _children(node)]
    selected: list[CategoryRoot] = []
    for node in roots:
        identifier = _node_id(node)
        name = _name(node)
        if identifier and name and _visible(node):
            selected.append(CategoryRoot(identifier, name, (name,), (identifier,), True))
    if not selected:
        raise ContractError("category tree contains no visible root departments")
    parent = parent or {}
    tree_id = next((str(parent[key]) for key in ("treeId", "id", "categoryTreeId") if parent.get(key) is not None), None)
    timestamp = next((str(parent[key]) for key in ("_indexTimestamp", "indexTimestamp", "treeIndexTimestamp", "updatedAt") if parent.get(key)), None)
    return DiscoveryResult(
        tree_id=tree_id,
        tree_index_timestamp=timestamp,
        roots=tuple(selected),
        total_nodes=len(all_nodes),
        visible_nodes=sum(1 for node, _, _ in all_nodes if _visible(node)),
        leaf_nodes=len(leaves),
        visible_product_bearing_leaves=sum(
            1 for node, _, _ in leaves if _visible(node) and _has_visible_products(node)
        ),
    )


def find_category(frontend: dict[str, Any], category_id: str) -> CategoryRoot:
    """Resolve any discovered category to its live localized ID/name path."""
    _, roots = _best_tree(frontend)
    for node, path_names, path_ids in walk_categories(roots):
        if _node_id(node) == str(category_id):
            if not _visible(node):
                raise ContractError(f"category {category_id} is not visible for Baldwin")
            return CategoryRoot(str(category_id), _name(node), path_names, path_ids, True)
    raise ContractError(f"category {category_id} is absent from the current Baldwin tree")
