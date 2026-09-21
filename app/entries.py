"""Generic repeat mechanics shared by every layout.

A product's entries (Design rows on a design_blocks page, CountLine rows on a
count_only page) are saved, added to, and removed from the same way
regardless of layout. `repeatable: false` is the only thing that ever turns
the add/remove controls off — it is checked here, once, not per layout.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.extensions import db
from app.models import Attachment, CountLine, Design, ProductNote


@dataclass
class EntryError:
    product_key: str
    position: int
    message: str


def get_entries(model, submission_id: int, product_key: str) -> list:
    query = model.query.filter_by(submission_id=submission_id, product_key=product_key)
    return query.order_by(model.position).all()


def get_or_create_product_note(submission_id: int, product_key: str) -> ProductNote:
    note = ProductNote.query.filter_by(submission_id=submission_id, product_key=product_key).first()
    if note is None:
        note = ProductNote(submission_id=submission_id, product_key=product_key, notes="")
        db.session.add(note)
    return note


def set_product_note(submission_id: int, product_key: str, text: str) -> None:
    text = (text or "").strip()
    note = ProductNote.query.filter_by(submission_id=submission_id, product_key=product_key).first()
    if not text:
        if note is not None:
            db.session.delete(note)
        return
    if note is None:
        note = ProductNote(submission_id=submission_id, product_key=product_key)
        db.session.add(note)
    note.notes = text


def reconcile_count_lines(submission_id: int, product_key: str, rows: list[dict], repeatable: bool) -> None:
    """rows: list of {"id": Optional[int], "quantity": Optional[int], "notes": str}."""
    existing = {e.id: e for e in get_entries(CountLine, submission_id, product_key)}
    keep_ids = set()

    if not repeatable:
        rows = rows[:1]

    for position, row in enumerate(rows):
        row_id = row.get("id")
        if row_id and row_id in existing:
            line = existing[row_id]
        else:
            line = CountLine(submission_id=submission_id, product_key=product_key)
            db.session.add(line)
        line.position = position
        line.quantity = row.get("quantity")
        line.notes = row.get("notes")
        db.session.flush()
        keep_ids.add(line.id)

    for entry_id, line in existing.items():
        if entry_id not in keep_ids:
            db.session.delete(line)


def reconcile_designs(submission_id: int, product_key: str, rows: list[dict], repeatable: bool, storage, submission_token: str) -> None:
    """rows: list of dicts with design fields plus optional "files" (list of FileStorage) and "remove_attachment_ids"."""
    existing = {e.id: e for e in get_entries(Design, submission_id, product_key)}
    keep_ids = set()

    if not repeatable:
        rows = rows[:1]

    for position, row in enumerate(rows):
        row_id = row.get("id")
        if row_id and row_id in existing:
            design = existing[row_id]
        else:
            design = Design(submission_id=submission_id, product_key=product_key)
            db.session.add(design)
        design.position = position
        design.type_value = row.get("type_value")
        design.type_other = row.get("type_other")
        design.count = row.get("count")
        design.holes = row.get("holes") or []
        design.description = row.get("description")
        design.link_url = row.get("link_url")
        design.notes = row.get("notes")
        db.session.flush()
        keep_ids.add(design.id)

        for attachment_id in row.get("remove_attachment_ids", []):
            attachment = Attachment.query.filter_by(id=attachment_id, design_id=design.id).first()
            if attachment:
                storage.delete(attachment.storage_key)
                db.session.delete(attachment)

        for file_storage in row.get("files", []):
            if not file_storage or not file_storage.filename:
                continue
            storage_key, size = storage.save(file_storage, submission_token)
            db.session.add(
                Attachment(
                    design_id=design.id,
                    storage_key=storage_key,
                    original_filename=file_storage.filename,
                    size=size,
                    content_type=file_storage.content_type,
                )
            )

    for entry_id, design in existing.items():
        if entry_id not in keep_ids:
            for attachment in design.attachments:
                storage.delete(attachment.storage_key)
            db.session.delete(design)
