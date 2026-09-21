import os
import sys

from flask import Flask

from app.config import Config
from app.extensions import csrf, db, migrate
from app.storage import LocalStorage
from app.catalog import CatalogError, load_catalog


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    app.storage = LocalStorage(app.config["UPLOAD_DIR"])

    try:
        app.catalog = load_catalog(app.config["CATALOG_PATH"])
    except CatalogError as exc:
        sys.stderr.write(f"\ncatalog.yaml is invalid: {exc}\n\n")
        raise

    from app.routes.public import public_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app import cli as cli_module

    cli_module.register(app)

    @app.template_filter("yesno")
    def yesno_filter(value, labels="Yes,No,—"):
        yes, no, unset = labels.split(",")
        if value is True:
            return yes
        if value is False:
            return no
        return unset

    return app
