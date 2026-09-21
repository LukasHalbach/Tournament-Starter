from app import navigation
from app.catalog import load_catalog


def test_build_steps_intersects_order_with_yes_answers(catalog_path):
    catalog = load_catalog(catalog_path)
    selections = {"quiet_paddles": True, "trash_racks": False, "tee_markers_blocks": True, "road_signs": False}
    steps = navigation.build_steps(catalog, selections)
    assert steps == ["info", "checklist", "quantities", "tee_markers", "services", "review"]


def test_build_steps_skips_all_no_page(catalog_path):
    catalog = load_catalog(catalog_path)
    selections = {"quiet_paddles": False, "trash_racks": False, "tee_markers_blocks": False, "road_signs": True}
    steps = navigation.build_steps(catalog, selections)
    assert "quantities" not in steps
    assert "tee_markers" not in steps
    assert "wayfinding" in steps


def test_neighbors():
    steps = ["info", "checklist", "quantities", "services", "review"]
    assert navigation.neighbors(steps, "quantities") == ("checklist", "services")
    assert navigation.neighbors(steps, "info") == (None, "checklist")
    assert navigation.neighbors(steps, "review") == ("services", None)
