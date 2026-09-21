import click

from app.catalog import CatalogError, load_catalog


def register(app):
    @app.cli.command("validate-catalog")
    @click.option("--path", default=None, help="Path to catalog.yaml (defaults to CATALOG_PATH).")
    def validate_catalog(path):
        """Validate catalog.yaml without starting the server."""
        catalog_path = path or app.config["CATALOG_PATH"]
        try:
            catalog = load_catalog(catalog_path)
        except CatalogError as exc:
            click.secho(f"INVALID: {exc}", fg="red")
            raise SystemExit(1)
        click.secho(
            f"OK: {len(catalog.pages)} page(s), {len(catalog.products)} product(s)",
            fg="green",
        )

    @app.cli.command("seed-demo")
    def seed_demo():
        """Create a demo draft submission so you can click through the flow."""
        from app.models import ProductSelection, Submission
        from app.extensions import db

        submission = Submission(tournament_name="Demo Invitational", course_name="Demo Golf Club")
        db.session.add(submission)
        db.session.flush()
        for product in app.catalog.active_products():
            db.session.add(
                ProductSelection(submission_id=submission.id, product_key=product.key, included=None)
            )
        db.session.commit()
        click.secho(f"Created draft: /f/{submission.token}", fg="green")
