import tempfile
from pathlib import Path

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db

SAMPLE_CATALOG = """
pages:
  - key: quantities
    order: 10
    title: Quantities
    layout: count_only
    notes_label: "Anything else about quantities?"

  - key: tee_markers
    order: 20
    title: Tee Markers
    layout: design_blocks
    notes_label: "Anything else about tee markers?"

  - key: wayfinding
    order: 30
    title: Wayfinding
    layout: design_blocks

products:
  - key: quiet_paddles
    section: Course
    name: Quiet Paddles
    page: quantities
    entry_notes_label: "Notes for this entry"

  - key: trash_racks
    section: Course
    name: Trash Racks
    page: quantities
    entry_notes_label: "Notes for this entry"
    repeatable: false

  - key: tee_markers_blocks
    section: Course
    name: Tee Markers / Blocks
    page: tee_markers
    design_label: Tee Marker Design
    type_label: Tee Marker Type
    types: [Standard, Championship]
    hole_select: true
    entry_notes_label: "Notes for this design"
    product_notes_label: "Notes about your tee markers"

  - key: road_signs
    section: Wayfinding
    name: Road / Directional Signs
    page: wayfinding
    design_label: Road Sign Design
"""


@pytest.fixture
def catalog_path(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text(SAMPLE_CATALOG)
    return str(path)


@pytest.fixture
def app(catalog_path, tmp_path):
    class _Config(TestConfig):
        CATALOG_PATH = catalog_path
        UPLOAD_DIR = str(tmp_path / "uploads")
        ADMIN_PASSWORD = "secret"

    application = create_app(_Config)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
