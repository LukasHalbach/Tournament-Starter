"""Loads catalog.yaml and turns it into the pages/products the form is built from.

Nothing here infers behavior from a product's name or type. A product shows up
wherever its `page` says, rendered by whatever `layout` that page declares.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

LAYOUTS = {"count_only", "design_blocks", "yes_no_detail"}


class CatalogError(Exception):
    """Raised when catalog.yaml is invalid. Message is meant to be read by a human."""


@dataclass(frozen=True)
class Page:
    key: str
    order: int
    title: str
    layout: str
    intro: Optional[str] = None
    notes_label: Optional[str] = None
    notes_help: Optional[str] = None


@dataclass(frozen=True)
class Product:
    key: str
    section: str
    name: str
    page: str
    design_label: Optional[str] = None
    type_label: Optional[str] = None
    types: tuple = field(default_factory=tuple)
    hole_select: bool = False
    repeatable: bool = True
    entry_notes_label: Optional[str] = None
    product_notes_label: Optional[str] = None
    active: bool = True


class Catalog:
    def __init__(self, pages: list[Page], products: list[Product]):
        self.pages = {p.key: p for p in pages}
        self.products = {p.key: p for p in products}
        self._ordered_pages = tuple(sorted(pages, key=lambda p: p.order))

    def ordered_pages(self) -> list[Page]:
        return list(self._ordered_pages)

    def get_page(self, key: str) -> Optional[Page]:
        return self.pages.get(key)

    def get_product(self, key: str) -> Optional[Product]:
        return self.products.get(key)

    def active_products(self) -> list[Product]:
        return [p for p in self.products.values() if p.active]

    def products_for_page(self, page_key: str) -> list[Product]:
        return [p for p in self.active_products() if p.page == page_key]

    def sections(self) -> list[str]:
        """Section names in first-seen order, for the checklist grouping."""
        seen: list[str] = []
        for p in self.active_products():
            if p.section not in seen:
                seen.append(p.section)
        return seen

    def products_by_section(self) -> dict[str, list[Product]]:
        out: dict[str, list[Product]] = {}
        for p in self.active_products():
            out.setdefault(p.section, []).append(p)
        return out

    def dynamic_pages(self) -> list[Page]:
        """Configured pages that go through the checklist gate (i.e. not services)."""
        return [p for p in self.ordered_pages() if p.layout != "yes_no_detail"]

    def visible_pages(self, selections: dict[str, bool]) -> list[Page]:
        """Configured pages, in order, whose products include at least one Yes.

        `selections` maps product_key -> included (True/False/None-treated-as-False).
        A page skipped here never appears in navigation and deep links to it redirect.
        """
        visible = []
        for page in self.dynamic_pages():
            products = self.products_for_page(page.key)
            if any(selections.get(p.key) for p in products):
                visible.append(page)
        return visible


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogError(message)


def load_catalog(path: str | Path) -> Catalog:
    path = Path(path)
    _require(path.exists(), f"Catalog file not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}

    pages_raw = raw.get("pages") or []
    products_raw = raw.get("products") or []

    pages: list[Page] = []
    seen_page_keys: set[str] = set()
    seen_orders: dict[int, str] = {}
    layout_by_page: dict[str, str] = {}

    for entry in pages_raw:
        key = entry.get("key")
        _require(bool(key), "Every page needs a 'key'")
        _require(key not in seen_page_keys, f"Duplicate page key: '{key}'")
        seen_page_keys.add(key)

        layout = entry.get("layout")
        _require(
            layout in LAYOUTS,
            f"Page '{key}' has layout '{layout}', must be one of {sorted(LAYOUTS)}",
        )
        layout_by_page[key] = layout

        order = entry.get("order")
        _require(order is not None, f"Page '{key}' is missing 'order'")
        _require(
            order not in seen_orders,
            f"Duplicate order {order} on pages '{seen_orders.get(order)}' and '{key}'",
        )
        seen_orders[order] = key

        pages.append(
            Page(
                key=key,
                order=order,
                title=entry.get("title", key),
                layout=layout,
                intro=entry.get("intro"),
                notes_label=entry.get("notes_label"),
                notes_help=entry.get("notes_help"),
            )
        )

    products: list[Product] = []
    seen_product_keys: set[str] = set()

    for entry in products_raw:
        key = entry.get("key")
        _require(bool(key), "Every product needs a 'key'")
        _require(key not in seen_product_keys, f"Duplicate product key: '{key}'")
        seen_product_keys.add(key)

        page_key = entry.get("page")
        _require(bool(page_key), f"Product '{key}' is missing required 'page'")
        _require(
            page_key in seen_page_keys,
            f"Product '{key}' points at unknown page '{page_key}'",
        )

        if layout_by_page[page_key] == "design_blocks":
            _require(
                bool(entry.get("design_label")),
                f"Product '{key}' is on a design_blocks page and needs 'design_label'",
            )

        products.append(
            Product(
                key=key,
                section=entry.get("section", "Other"),
                name=entry.get("name", key),
                page=page_key,
                design_label=entry.get("design_label"),
                type_label=entry.get("type_label"),
                types=tuple(entry.get("types") or ()),
                hole_select=bool(entry.get("hole_select", False)),
                repeatable=bool(entry.get("repeatable", True)),
                entry_notes_label=entry.get("entry_notes_label"),
                product_notes_label=entry.get("product_notes_label"),
                active=bool(entry.get("active", True)),
            )
        )

    return Catalog(pages, products)
