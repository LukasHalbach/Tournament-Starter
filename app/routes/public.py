from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from app import entries as entry_ops
from app import navigation
from app.extensions import db
from app.models import (
    Attachment,
    CountLine,
    Design,
    PageNote,
    ProductNote,
    ProductSelection,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    Submission,
)
from app.page_forms import (
    parse_count_rows,
    parse_design_rows,
    validate_count_rows,
    validate_design_rows,
)

public_bp = Blueprint("public", __name__)


def catalog():
    return current_app.catalog


def get_submission_or_404(token: str) -> Submission:
    submission = Submission.query.filter_by(token=token).first()
    if submission is None:
        abort(404)
    return submission


def ensure_selection_rows(submission: Submission) -> None:
    """Lazily create ProductSelection rows for any active product missing one
    (covers products added to the catalog after this draft started)."""
    existing = {s.product_key for s in submission.product_selections}
    changed = False
    for product in catalog().active_products():
        if product.key not in existing:
            db.session.add(
                ProductSelection(submission_id=submission.id, product_key=product.key, included=None)
            )
            changed = True
    if changed:
        db.session.commit()
        db.session.refresh(submission)


def current_steps(submission: Submission) -> list[str]:
    return navigation.build_steps(catalog(), submission.selection_map())


def require_draft(submission: Submission):
    if submission.status != STATUS_DRAFT:
        return redirect(url_for("public.review", token=submission.token))
    return None


def allowed_extension(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]


# --- Start a new form -------------------------------------------------

@public_bp.route("/")
def start():
    submission = Submission(course_holes=current_app.config["DEFAULT_COURSE_HOLES"])
    db.session.add(submission)
    db.session.commit()
    return redirect(url_for("public.info", token=submission.token))


# --- Step 1: Tournament Info -------------------------------------------

@public_bp.route("/f/<token>/info", methods=["GET", "POST"])
def info(token):
    submission = get_submission_or_404(token)
    redirect_resp = require_draft(submission)
    if redirect_resp:
        return redirect_resp

    if request.method == "POST":
        submission.tournament_name = request.form.get("tournament_name", "").strip()
        submission.course_name = request.form.get("course_name", "").strip()
        submission.start_date = _parse_date(request.form.get("start_date"))
        submission.end_date = _parse_date(request.form.get("end_date"))
        submission.install_deadline = _parse_date(request.form.get("install_deadline"))
        submission.course_holes = _to_int(request.form.get("course_holes")) or current_app.config[
            "DEFAULT_COURSE_HOLES"
        ]
        submission.contact_name = request.form.get("contact_name", "").strip()
        submission.contact_email = request.form.get("contact_email", "").strip()
        submission.contact_phone = request.form.get("contact_phone", "").strip()
        submission.info_notes = request.form.get("info_notes", "").strip() or None
        db.session.commit()
        return redirect(url_for("public.checklist", token=token))

    return render_template("info.html", submission=submission, resume_url=url_for("public.info", token=token, _external=True))


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --- Step 2: Product Checklist ------------------------------------------

@public_bp.route("/f/<token>/checklist", methods=["GET", "POST"])
def checklist(token):
    submission = get_submission_or_404(token)
    redirect_resp = require_draft(submission)
    if redirect_resp:
        return redirect_resp

    ensure_selection_rows(submission)
    sections = catalog().products_by_section()

    if request.method == "POST":
        action = request.form.get("action", "next")

        if action.startswith("mark-no:"):
            section = action.split(":", 1)[1]
            for product in sections.get(section, []):
                sel = submission.get_selection(product.key)
                if sel and sel.included is None:
                    sel.included = False
            db.session.commit()
            return redirect(url_for("public.checklist", token=token))

        # Normal save: read every product's radio value.
        unanswered_key = None
        for section_products in sections.values():
            for product in section_products:
                sel = submission.get_selection(product.key)
                raw = request.form.get(f"product-{product.key}")
                if raw in ("yes", "no"):
                    new_value = raw == "yes"
                    if sel.included is True and new_value is False:
                        sel.hidden = True  # soft-hide, keep the data
                    elif new_value is True and sel.hidden:
                        sel.hidden = False  # restore on flip back to Yes
                    sel.included = new_value
                elif action == "next" and sel.included is None and unanswered_key is None:
                    unanswered_key = product.key
        db.session.commit()

        if action == "next":
            # Re-check after saving whatever was answered this round.
            for section_products in sections.values():
                for product in section_products:
                    sel = submission.get_selection(product.key)
                    if sel.included is None and unanswered_key is None:
                        unanswered_key = product.key
            if unanswered_key:
                flash("Please answer every product before continuing.", "error")
                return render_template(
                    "checklist.html",
                    submission=submission,
                    sections=sections,
                    catalog=catalog(),
                    scroll_to=unanswered_key,
                )
            steps = current_steps(submission)
            _, next_step = navigation.neighbors(steps, navigation.STEP_CHECKLIST)
            return redirect(navigation.step_url(token, next_step))

        return redirect(url_for("public.checklist", token=token))

    return render_template(
        "checklist.html", submission=submission, sections=sections, catalog=catalog(), scroll_to=None
    )


# --- Step 3: Configured pages -------------------------------------------

@public_bp.route("/f/<token>/page/<page_key>", methods=["GET", "POST"])
def dynamic_page(token, page_key):
    submission = get_submission_or_404(token)
    redirect_resp = require_draft(submission)
    if redirect_resp:
        return redirect_resp

    page = catalog().get_page(page_key)
    if page is None or page.layout == "yes_no_detail":
        abort(404)

    selections = submission.selection_map()
    visible_keys = {p.key for p in catalog().visible_pages(selections)}
    if page_key not in visible_keys:
        return redirect(url_for("public.checklist", token=token))

    products = [p for p in catalog().products_for_page(page_key) if selections.get(p.key)]
    steps = current_steps(submission)

    if request.method == "POST":
        action = request.form.get("action", "next")
        errors = []

        drop = {}
        add = {}
        if action.startswith("remove:"):
            _, pkey, pos = action.split(":", 2)
            drop[pkey] = int(pos)
        elif action.startswith("add:"):
            add[action.split(":", 1)[1]] = True

        for product in products:
            if page.layout == "count_only":
                rows = parse_count_rows(
                    request.form, product.key, drop_position=drop.get(product.key), add_blank=add.get(product.key, False)
                )
                if action == "next":
                    errors.extend(validate_count_rows(rows, product))
                entry_ops.reconcile_count_lines(submission.id, product.key, rows, product.repeatable)
            else:
                rows = parse_design_rows(
                    request.form,
                    request.files,
                    product.key,
                    drop_position=drop.get(product.key),
                    add_blank=add.get(product.key, False),
                )
                if action == "next":
                    errors.extend(validate_design_rows(rows, product))
                entry_ops.reconcile_designs(
                    submission.id, product.key, rows, product.repeatable, current_app.storage, submission.token
                )

            if product.product_notes_label:
                entry_ops.set_product_note(submission.id, product.key, request.form.get(f"product-notes-{product.key}", ""))

        if page.notes_label:
            _set_page_note(submission.id, page.key, request.form.get("page-notes", ""))

        db.session.commit()

        if action == "next":
            if errors:
                flash("Please fix the highlighted fields.", "error")
                return render_template(
                    "dynamic_page.html",
                    submission=submission,
                    page=page,
                    products=products,
                    steps=steps,
                    errors={(e[0], e[1]): e[2] for e in errors},
                    error_messages=[e[2] for e in errors],
                    catalog=catalog(),
                )
            prev_step, next_step = navigation.neighbors(steps, page_key)
            return redirect(navigation.step_url(token, next_step))

        if action == "back":
            prev_step, _ = navigation.neighbors(steps, page_key)
            return redirect(navigation.step_url(token, prev_step))

        return redirect(url_for("public.dynamic_page", token=token, page_key=page_key))

    return render_template(
        "dynamic_page.html",
        submission=submission,
        page=page,
        products=products,
        steps=steps,
        errors={},
        error_messages=[],
        catalog=catalog(),
    )


def _set_page_note(submission_id: int, page_key: str, text: str) -> None:
    text = (text or "").strip()
    note = PageNote.query.filter_by(submission_id=submission_id, page_key=page_key).first()
    if not text:
        if note is not None:
            db.session.delete(note)
        return
    if note is None:
        note = PageNote(submission_id=submission_id, page_key=page_key)
        db.session.add(note)
    note.notes = text


# --- Step 4: Services -----------------------------------------------------

@public_bp.route("/f/<token>/services", methods=["GET", "POST"])
def services(token):
    submission = get_submission_or_404(token)
    redirect_resp = require_draft(submission)
    if redirect_resp:
        return redirect_resp

    steps = current_steps(submission)

    if request.method == "POST":
        action = request.form.get("action", "next")
        submission.needs_installation = _bool_or_none(request.form.get("needs_installation"))
        submission.installation_notes = request.form.get("installation_notes", "").strip() or None
        submission.needs_rope_stake = _bool_or_none(request.form.get("needs_rope_stake"))
        submission.rope_stake_notes = request.form.get("rope_stake_notes", "").strip() or None
        submission.needs_freight = _bool_or_none(request.form.get("needs_freight"))
        submission.freight_address = request.form.get("freight_address", "").strip() or None
        submission.freight_notes = request.form.get("freight_notes", "").strip() or None
        db.session.commit()

        if action == "back":
            prev_step, _ = navigation.neighbors(steps, navigation.STEP_SERVICES)
            return redirect(navigation.step_url(token, prev_step))

        _, next_step = navigation.neighbors(steps, navigation.STEP_SERVICES)
        return redirect(navigation.step_url(token, next_step))

    return render_template("services.html", submission=submission, steps=steps)


def _bool_or_none(raw):
    if raw == "yes":
        return True
    if raw == "no":
        return False
    return None


# --- Step 5: Review --------------------------------------------------------

@public_bp.route("/f/<token>/review", methods=["GET", "POST"])
def review(token):
    submission = get_submission_or_404(token)
    steps = current_steps(submission)

    summary = _build_summary(submission)

    if request.method == "POST":
        if submission.status != STATUS_DRAFT:
            return redirect(url_for("public.confirmation", token=token))

        submission.order_notes = request.form.get("order_notes", "").strip() or None
        if not request.form.get("confirm_accurate"):
            flash("Please confirm the information is accurate before submitting.", "error")
            return render_template("review.html", submission=submission, steps=steps, summary=summary)

        submission.confirmed = True
        submission.confirmed_at = datetime.utcnow()
        submission.status = STATUS_SUBMITTED
        submission.submitted_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("public.confirmation", token=token))

    return render_template("review.html", submission=submission, steps=steps, summary=summary)


def _build_summary(submission: Submission):
    """Groups every entered product by section for the read-only review page."""
    selections = submission.selection_map()
    by_section = {}
    grand_total = 0
    for product in catalog().active_products():
        if not selections.get(product.key):
            continue
        page = catalog().get_page(product.page)
        product_note = next((n.notes for n in submission.product_notes if n.product_key == product.key), None)

        if page.layout == "count_only":
            lines = [l for l in submission.count_lines if l.product_key == product.key]
            total = sum(l.quantity or 0 for l in lines)
            entries = lines
        else:
            entries = [d for d in submission.designs if d.product_key == product.key]
            total = sum(d.count or 0 for d in entries)

        grand_total += total
        by_section.setdefault(product.section, []).append(
            {
                "product": product,
                "page": page,
                "entries": entries,
                "total": total,
                "note": product_note,
            }
        )

    page_notes = {n.page_key: n.notes for n in submission.page_notes}
    return {"by_section": by_section, "grand_total": grand_total, "page_notes": page_notes}


# --- Step 6: Confirmation ---------------------------------------------------

@public_bp.route("/f/<token>/confirmation")
def confirmation(token):
    submission = get_submission_or_404(token)
    if submission.status == STATUS_DRAFT:
        return redirect(url_for("public.review", token=token))
    return render_template("confirmation.html", submission=submission)


# --- File downloads (used by both client review and admin) -----------------

@public_bp.route("/f/<token>/files/<int:attachment_id>")
def download_file(token, attachment_id):
    submission = get_submission_or_404(token)
    attachment = Attachment.query.get_or_404(attachment_id)
    design = Design.query.get_or_404(attachment.design_id)
    if design.submission_id != submission.id:
        abort(404)
    return send_file(
        current_app.storage.open_stream(attachment.storage_key),
        download_name=attachment.original_filename,
        as_attachment=True,
    )
