from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from app.extensions import db
from app.models import AdminNote, Attachment, STATUSES, Submission

admin_bp = Blueprint("admin", __name__)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        expected = current_app.config["ADMIN_PASSWORD"]
        if expected and password == expected:
            session["admin_logged_in"] = True
            return redirect(request.args.get("next") or url_for("admin.submission_list"))
        flash("Incorrect password.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def submission_list():
    status_filter = request.args.get("status")
    query = Submission.query.order_by(Submission.created_at.desc())
    if status_filter in STATUSES:
        query = query.filter_by(status=status_filter)
    submissions = query.all()

    rows = []
    for submission in submissions:
        selections = submission.selection_map()
        product_count = sum(1 for v in selections.values() if v)
        total_signs = sum((l.quantity or 0) for l in submission.count_lines) + sum(
            (d.count or 0) for d in submission.designs
        )
        has_notes = bool(
            submission.order_notes
            or submission.info_notes
            or submission.product_notes
            or submission.page_notes
            or any(l.notes for l in submission.count_lines)
            or any(d.notes for d in submission.designs)
        )
        rows.append(
            {
                "submission": submission,
                "product_count": product_count,
                "total_signs": total_signs,
                "has_notes": has_notes,
            }
        )

    return render_template("admin/list.html", rows=rows, statuses=STATUSES, status_filter=status_filter)


@admin_bp.route("/submissions/<int:submission_id>", methods=["GET", "POST"])
@admin_required
def submission_detail(submission_id):
    submission = Submission.query.get_or_404(submission_id)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "set-status":
            new_status = request.form.get("status")
            if new_status in STATUSES:
                submission.status = new_status
                db.session.commit()
                flash("Status updated.", "success")
        elif action == "add-note":
            body = request.form.get("body", "").strip()
            if body:
                db.session.add(AdminNote(submission_id=submission.id, author="Staff", body=body))
                db.session.commit()
        return redirect(url_for("admin.submission_detail", submission_id=submission.id))

    catalog = current_app.catalog
    selections = submission.selection_map()
    by_section = {}
    for product in catalog.active_products():
        if not selections.get(product.key):
            continue
        page = catalog.get_page(product.page)
        product_note = next((n.notes for n in submission.product_notes if n.product_key == product.key), None)
        if page.layout == "count_only":
            entries = [l for l in submission.count_lines if l.product_key == product.key]
            total = sum(l.quantity or 0 for l in entries)
        else:
            entries = [d for d in submission.designs if d.product_key == product.key]
            total = sum(d.count or 0 for d in entries)
        by_section.setdefault(product.section, []).append(
            {"product": product, "page": page, "entries": entries, "total": total, "note": product_note}
        )

    page_notes = {n.page_key: n.notes for n in submission.page_notes}

    client_notes = []
    if submission.info_notes:
        client_notes.append(("Tournament info", submission.info_notes))
    for pkey, text in page_notes.items():
        if text:
            page = catalog.get_page(pkey)
            client_notes.append((f"Page: {page.title if page else pkey}", text))
    for note in submission.product_notes:
        if note.notes:
            product = catalog.get_product(note.product_key)
            client_notes.append((f"Product: {product.name if product else note.product_key}", note.notes))
    for line in submission.count_lines:
        if line.notes:
            product = catalog.get_product(line.product_key)
            client_notes.append((f"{product.name if product else line.product_key} entry", line.notes))
    for design in submission.designs:
        if design.notes:
            product = catalog.get_product(design.product_key)
            client_notes.append((f"{product.name if product else design.product_key} design {design.position + 1}", design.notes))
    if submission.order_notes:
        client_notes.append(("Whole order", submission.order_notes))

    return render_template(
        "admin/detail.html",
        submission=submission,
        by_section=by_section,
        client_notes=client_notes,
        statuses=STATUSES,
    )


@admin_bp.route("/submissions/<int:submission_id>/files/<int:attachment_id>")
@admin_required
def download_file(submission_id, attachment_id):
    from app.models import Design

    attachment = Attachment.query.get_or_404(attachment_id)
    design = Design.query.get_or_404(attachment.design_id)
    if design.submission_id != submission_id:
        return redirect(url_for("admin.submission_list"))
    return send_file(
        current_app.storage.open_stream(attachment.storage_key),
        download_name=attachment.original_filename,
        as_attachment=True,
    )


@admin_bp.route("/catalog")
@admin_required
def catalog_view():
    catalog = current_app.catalog
    return render_template("admin/catalog.html", catalog=catalog)
