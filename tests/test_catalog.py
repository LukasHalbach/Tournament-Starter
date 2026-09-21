import pytest

from app.catalog import CatalogError, load_catalog


def write(tmp_path, text):
    path = tmp_path / "catalog.yaml"
    path.write_text(text)
    return str(path)


def test_loads_valid_catalog(catalog_path):
    catalog = load_catalog(catalog_path)
    assert catalog.get_page("quantities").layout == "count_only"
    assert catalog.get_product("tee_markers_blocks").page == "tee_markers"
    assert catalog.get_product("trash_racks").repeatable is False


def test_duplicate_page_key_rejected(tmp_path):
    path = write(
        tmp_path,
        """
pages:
  - {key: a, order: 10, title: A, layout: count_only}
  - {key: a, order: 20, title: A2, layout: count_only}
products: []
""",
    )
    with pytest.raises(CatalogError, match="Duplicate page key"):
        load_catalog(path)


def test_duplicate_order_rejected(tmp_path):
    path = write(
        tmp_path,
        """
pages:
  - {key: a, order: 10, title: A, layout: count_only}
  - {key: b, order: 10, title: B, layout: count_only}
products: []
""",
    )
    with pytest.raises(CatalogError, match="Duplicate order"):
        load_catalog(path)


def test_unknown_layout_rejected(tmp_path):
    path = write(
        tmp_path,
        """
pages:
  - {key: a, order: 10, title: A, layout: not_a_real_layout}
products: []
""",
    )
    with pytest.raises(CatalogError, match="layout"):
        load_catalog(path)


def test_product_pointing_at_missing_page_rejected(tmp_path):
    path = write(
        tmp_path,
        """
pages:
  - {key: a, order: 10, title: A, layout: count_only}
products:
  - {key: p1, name: P1, page: nonexistent}
""",
    )
    with pytest.raises(CatalogError, match="unknown page"):
        load_catalog(path)


def test_duplicate_product_key_rejected(tmp_path):
    path = write(
        tmp_path,
        """
pages:
  - {key: a, order: 10, title: A, layout: count_only}
products:
  - {key: p1, name: P1, page: a}
  - {key: p1, name: P1 dup, page: a}
""",
    )
    with pytest.raises(CatalogError, match="Duplicate product key"):
        load_catalog(path)


def test_design_blocks_product_requires_design_label(tmp_path):
    path = write(
        tmp_path,
        """
pages:
  - {key: a, order: 10, title: A, layout: design_blocks}
products:
  - {key: p1, name: P1, page: a}
""",
    )
    with pytest.raises(CatalogError, match="design_label"):
        load_catalog(path)


def test_visible_pages_only_show_yes_products(catalog_path):
    catalog = load_catalog(catalog_path)

    selections = {"quiet_paddles": True, "trash_racks": False, "tee_markers_blocks": False, "road_signs": False}
    visible = catalog.visible_pages(selections)
    assert [p.key for p in visible] == ["quantities"]

    selections["tee_markers_blocks"] = True
    visible = catalog.visible_pages(selections)
    assert [p.key for p in visible] == ["quantities", "tee_markers"]

    all_no = {"quiet_paddles": False, "trash_racks": False, "tee_markers_blocks": False, "road_signs": False}
    assert catalog.visible_pages(all_no) == []


def test_page_shared_by_two_yes_products_appears_once(catalog_path):
    catalog = load_catalog(catalog_path)
    selections = {"quiet_paddles": True, "trash_racks": True, "tee_markers_blocks": False, "road_signs": False}
    visible = catalog.visible_pages(selections)
    assert [p.key for p in visible] == ["quantities"]
    assert len(catalog.products_for_page("quantities")) == 2
