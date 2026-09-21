import secrets
from datetime import datetime

from app.extensions import db

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_IN_REVIEW = "in_review"
STATUS_COMPLETE = "complete"
STATUSES = (STATUS_DRAFT, STATUS_SUBMITTED, STATUS_IN_REVIEW, STATUS_COMPLETE)


def generate_token() -> str:
    return secrets.token_urlsafe(24)


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, default=generate_token, index=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT)

    tournament_name = db.Column(db.String(255))
    course_name = db.Column(db.String(255))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    install_deadline = db.Column(db.Date)
    course_holes = db.Column(db.Integer, default=18)

    contact_name = db.Column(db.String(255))
    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(50))
    info_notes = db.Column(db.Text)

    # Services page (fixed questions, not catalog-driven).
    needs_installation = db.Column(db.Boolean)
    installation_notes = db.Column(db.Text)
    needs_rope_stake = db.Column(db.Boolean)
    rope_stake_notes = db.Column(db.Text)
    needs_freight = db.Column(db.Boolean)
    freight_address = db.Column(db.Text)
    freight_notes = db.Column(db.Text)

    order_notes = db.Column(db.Text)
    confirmed = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    confirmed_at = db.Column(db.DateTime)

    product_selections = db.relationship(
        "ProductSelection", backref="submission", cascade="all, delete-orphan", lazy="selectin"
    )
    product_notes = db.relationship(
        "ProductNote", backref="submission", cascade="all, delete-orphan", lazy="selectin"
    )
    page_notes = db.relationship(
        "PageNote", backref="submission", cascade="all, delete-orphan", lazy="selectin"
    )
    designs = db.relationship(
        "Design", backref="submission", cascade="all, delete-orphan", lazy="selectin",
        order_by="Design.position",
    )
    count_lines = db.relationship(
        "CountLine", backref="submission", cascade="all, delete-orphan", lazy="selectin",
        order_by="CountLine.position",
    )
    admin_notes = db.relationship(
        "AdminNote", backref="submission", cascade="all, delete-orphan", lazy="selectin",
        order_by="AdminNote.created_at",
    )

    def selection_map(self) -> dict[str, bool | None]:
        """product_key -> included (True/False/None=unanswered)."""
        return {sel.product_key: sel.included for sel in self.product_selections}

    def get_selection(self, product_key: str) -> "ProductSelection | None":
        for sel in self.product_selections:
            if sel.product_key == product_key:
                return sel
        return None


class ProductSelection(db.Model):
    __tablename__ = "product_selection"
    __table_args__ = (db.UniqueConstraint("submission_id", "product_key"),)

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    product_key = db.Column(db.String(120), nullable=False)
    included = db.Column(db.Boolean, nullable=True)  # None = unanswered
    hidden = db.Column(db.Boolean, nullable=False, default=False)  # soft-hide on flip to No


class ProductNote(db.Model):
    __tablename__ = "product_note"
    __table_args__ = (db.UniqueConstraint("submission_id", "product_key"),)

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    product_key = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text)


class PageNote(db.Model):
    __tablename__ = "page_note"
    __table_args__ = (db.UniqueConstraint("submission_id", "page_key"),)

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    page_key = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text)


class Design(db.Model):
    """One repeated entry on a design_blocks page."""

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    product_key = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    type_value = db.Column(db.String(255))
    type_other = db.Column(db.String(255))
    count = db.Column(db.Integer)
    holes = db.Column(db.JSON, default=list)
    description = db.Column(db.Text)
    link_url = db.Column(db.String(500))
    notes = db.Column(db.Text)

    attachments = db.relationship(
        "Attachment", backref="design", cascade="all, delete-orphan", lazy="selectin"
    )


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    design_id = db.Column(db.Integer, db.ForeignKey("design.id"), nullable=False)
    storage_key = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(500), nullable=False)
    size = db.Column(db.Integer)
    content_type = db.Column(db.String(120))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class CountLine(db.Model):
    """One repeated entry on a count_only page."""

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    product_key = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    quantity = db.Column(db.Integer)
    notes = db.Column(db.Text)


class AdminNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    author = db.Column(db.String(120))
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
