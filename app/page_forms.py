"""Parses and validates the repeated-entry forms for count_only and design_blocks pages.

Field naming convention used by the templates:
  entry_count-<product_key>                      -> number of submitted rows
  entry-<product_key>-<i>-id                      -> DB id, blank for a new row
  entry-<product_key>-<i>-quantity                -> count_only
  entry-<product_key>-<i>-type / -type_other       -> design_blocks
  entry-<product_key>-<i>-count
  entry-<product_key>-<i>-holes                   -> multi
  entry-<product_key>-<i>-description
  entry-<product_key>-<i>-link_url
  entry-<product_key>-<i>-notes
  entry-<product_key>-<i>-files                   -> multi file input
  entry-<product_key>-<i>-remove_attachment        -> multi, attachment ids to drop
  product-notes-<product_key>
  page-notes
"""
from __future__ import annotations


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _blank_count_row():
    return {"id": None, "quantity": None, "notes": None}


def _blank_design_row():
    return {
        "id": None,
        "type_value": None,
        "type_other": None,
        "count": None,
        "holes": [],
        "description": None,
        "link_url": None,
        "notes": None,
        "files": [],
        "remove_attachment_ids": [],
    }


def parse_count_rows(form, product_key, drop_position=None, add_blank=False):
    count = _to_int(form.get(f"entry_count-{product_key}")) or 0
    rows = []
    for i in range(count):
        if i == drop_position:
            continue
        prefix = f"entry-{product_key}-{i}-"
        row_id = form.get(prefix + "id")
        rows.append(
            {
                "id": _to_int(row_id),
                "quantity": _to_int(form.get(prefix + "quantity")),
                "notes": form.get(prefix + "notes") or None,
            }
        )
    if add_blank:
        rows.append(_blank_count_row())
    if not rows:
        rows.append(_blank_count_row())
    return rows


def parse_design_rows(form, files, product_key, drop_position=None, add_blank=False):
    count = _to_int(form.get(f"entry_count-{product_key}")) or 0
    rows = []
    for i in range(count):
        if i == drop_position:
            continue
        prefix = f"entry-{product_key}-{i}-"
        row_id = form.get(prefix + "id")
        holes_raw = form.getlist(prefix + "holes")
        remove_ids = [x for x in (_to_int(v) for v in form.getlist(prefix + "remove_attachment")) if x]
        rows.append(
            {
                "id": _to_int(row_id),
                "type_value": form.get(prefix + "type") or None,
                "type_other": form.get(prefix + "type_other") or None,
                "count": _to_int(form.get(prefix + "count")),
                "holes": sorted({h for h in (_to_int(v) for v in holes_raw) if h}),
                "description": form.get(prefix + "description") or None,
                "link_url": form.get(prefix + "link_url") or None,
                "notes": form.get(prefix + "notes") or None,
                "files": files.getlist(prefix + "files") if files else [],
                "remove_attachment_ids": remove_ids,
            }
        )
    if add_blank:
        rows.append(_blank_design_row())
    if not rows:
        rows.append(_blank_design_row())
    return rows


def validate_count_rows(rows, product):
    errors = []
    for i, row in enumerate(rows):
        q = row["quantity"]
        if q is None or q < 1 or q > 500:
            errors.append((product.key, i, f'"{product.name}" entry {i + 1}: quantity must be between 1 and 500'))
    return errors


def validate_design_rows(rows, product):
    errors = []
    for i, row in enumerate(rows):
        if product.types:
            has_type = bool(row["type_value"]) and (
                row["type_value"] != "Other" or bool(row["type_other"])
            )
        else:
            has_type = bool(row["type_other"])
        if not has_type:
            errors.append(
                (product.key, i, f'{product.design_label or product.name} {i + 1}: type is required')
            )
        c = row["count"]
        if c is None or c < 1 or c > 500:
            errors.append(
                (product.key, i, f'{product.design_label or product.name} {i + 1}: count must be between 1 and 500')
            )
    return errors
