from app.extensions import db
from app.models import CountLine, Design, Submission


def start_submission(client):
    resp = client.get("/")
    token = resp.headers["Location"].split("/f/")[1].split("/")[0]
    return token


def fill_info(client, token):
    return client.post(
        f"/f/{token}/info",
        data={
            "tournament_name": "Test Open",
            "course_name": "Test Club",
            "contact_name": "Jane Doe",
            "contact_email": "jane@example.com",
            "course_holes": "18",
        },
    )


def answer_checklist(client, token, yes_keys):
    all_keys = ["quiet_paddles", "trash_racks", "tee_markers_blocks", "road_signs"]
    data = {"action": "next"}
    for k in all_keys:
        data[f"product-{k}"] = "yes" if k in yes_keys else "no"
    return client.post(f"/f/{token}/checklist", data=data)


def test_unknown_token_is_404(client):
    resp = client.get("/f/does-not-exist/info")
    assert resp.status_code == 404


def test_full_flow_reaches_review_and_submit(app, client):
    token = start_submission(client)
    fill_info(client, token)
    resp = answer_checklist(client, token, ["quiet_paddles", "tee_markers_blocks"])
    assert resp.headers["Location"].endswith(f"/f/{token}/page/quantities")

    resp = client.post(
        f"/f/{token}/page/quantities",
        data={"action": "next", "entry_count-quiet_paddles": "1", "entry-quiet_paddles-0-quantity": "24"},
    )
    assert resp.headers["Location"].endswith(f"/f/{token}/page/tee_markers")

    resp = client.post(
        f"/f/{token}/page/tee_markers",
        data={
            "action": "next",
            "entry_count-tee_markers_blocks": "1",
            "entry-tee_markers_blocks-0-type": "Standard",
            "entry-tee_markers_blocks-0-count": "5",
        },
    )
    assert resp.headers["Location"].endswith(f"/f/{token}/services")

    resp = client.post(
        f"/f/{token}/services",
        data={"action": "next", "needs_installation": "no", "needs_rope_stake": "no", "needs_freight": "no"},
    )
    assert resp.headers["Location"].endswith(f"/f/{token}/review")

    resp = client.get(f"/f/{token}/review")
    assert b"Test Open" in resp.data
    assert b"24" in resp.data

    resp = client.post(f"/f/{token}/review", data={"order_notes": "handle with care", "confirm_accurate": "on"})
    assert resp.headers["Location"].endswith(f"/f/{token}/confirmation")

    submission = Submission.query.filter_by(token=token).first()
    assert submission.status == "submitted"
    assert submission.confirmed is True


def test_checklist_blocks_next_when_unanswered(client):
    token = start_submission(client)
    fill_info(client, token)
    resp = client.post(
        f"/f/{token}/checklist",
        data={"action": "next", "product-quiet_paddles": "yes"},  # rest unanswered
    )
    assert resp.status_code == 200  # re-rendered, no redirect
    assert b"answer every product" in resp.data


def test_add_and_remove_entries_preserve_siblings(app, client):
    token = start_submission(client)
    fill_info(client, token)
    answer_checklist(client, token, ["quiet_paddles"])

    client.post(
        f"/f/{token}/page/quantities",
        data={"action": "add:quiet_paddles", "entry_count-quiet_paddles": "1", "entry-quiet_paddles-0-quantity": "24"},
    )
    with app.app_context():
        submission = Submission.query.filter_by(token=token).first()
        lines = CountLine.query.filter_by(submission_id=submission.id, product_key="quiet_paddles").order_by(
            CountLine.position
        ).all()
        assert len(lines) == 2
        assert lines[0].quantity == 24

    client.post(
        f"/f/{token}/page/quantities",
        data={
            "action": "add:quiet_paddles",
            "entry_count-quiet_paddles": "2",
            "entry-quiet_paddles-0-id": str(lines[0].id),
            "entry-quiet_paddles-0-quantity": "24",
            "entry-quiet_paddles-1-id": str(lines[1].id),
            "entry-quiet_paddles-1-quantity": "8",
        },
    )
    with app.app_context():
        submission = Submission.query.filter_by(token=token).first()
        lines = CountLine.query.filter_by(submission_id=submission.id, product_key="quiet_paddles").order_by(
            CountLine.position
        ).all()
        assert len(lines) == 3
        keep_id, remove_id = lines[0].id, lines[1].id

    client.post(
        f"/f/{token}/page/quantities",
        data={
            "action": f"remove:quiet_paddles:1",
            "entry_count-quiet_paddles": "3",
            "entry-quiet_paddles-0-id": str(keep_id),
            "entry-quiet_paddles-0-quantity": "24",
            "entry-quiet_paddles-1-id": str(remove_id),
            "entry-quiet_paddles-1-quantity": "8",
            "entry-quiet_paddles-2-id": "",
            "entry-quiet_paddles-2-quantity": "",
        },
    )
    with app.app_context():
        submission = Submission.query.filter_by(token=token).first()
        lines = CountLine.query.filter_by(submission_id=submission.id, product_key="quiet_paddles").order_by(
            CountLine.position
        ).all()
        assert len(lines) == 2
        assert lines[0].quantity == 24
        assert lines[0].id == keep_id


def test_non_repeatable_product_rejects_second_entry(app, client):
    token = start_submission(client)
    fill_info(client, token)
    answer_checklist(client, token, ["trash_racks"])

    client.post(
        f"/f/{token}/page/quantities",
        data={
            "action": "next",
            "entry_count-trash_racks": "2",
            "entry-trash_racks-0-quantity": "8",
            "entry-trash_racks-1-quantity": "99",
        },
    )
    with app.app_context():
        submission = Submission.query.filter_by(token=token).first()
        lines = CountLine.query.filter_by(submission_id=submission.id, product_key="trash_racks").all()
        assert len(lines) == 1
        assert lines[0].quantity == 8


def test_soft_hide_round_trip_on_flip_to_no_and_back(app, client):
    token = start_submission(client)
    fill_info(client, token)
    answer_checklist(client, token, ["tee_markers_blocks"])

    client.post(
        f"/f/{token}/page/tee_markers",
        data={
            "action": "next",
            "entry_count-tee_markers_blocks": "1",
            "entry-tee_markers_blocks-0-type": "Standard",
            "entry-tee_markers_blocks-0-count": "9",
            "entry-tee_markers_blocks-0-notes": "special request",
        },
    )

    # Flip to No.
    answer_checklist(client, token, [])
    with app.app_context():
        submission = Submission.query.filter_by(token=token).first()
        sel = submission.get_selection("tee_markers_blocks")
        assert sel.included is False
        assert sel.hidden is True
        designs = Design.query.filter_by(submission_id=submission.id, product_key="tee_markers_blocks").all()
        assert len(designs) == 1
        assert designs[0].notes == "special request"

    # Flip back to Yes.
    answer_checklist(client, token, ["tee_markers_blocks"])
    with app.app_context():
        submission = Submission.query.filter_by(token=token).first()
        sel = submission.get_selection("tee_markers_blocks")
        assert sel.included is True
        assert sel.hidden is False
        designs = Design.query.filter_by(submission_id=submission.id, product_key="tee_markers_blocks").all()
        assert len(designs) == 1
        assert designs[0].count == 9
        assert designs[0].notes == "special request"


def test_deep_link_to_hidden_page_redirects_to_checklist(client):
    token = start_submission(client)
    fill_info(client, token)
    answer_checklist(client, token, ["quiet_paddles"])  # tee_markers stays all-No

    resp = client.get(f"/f/{token}/page/tee_markers")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/f/{token}/checklist")


def test_notes_at_every_level_survive_a_resume(app, client):
    token = start_submission(client)
    fill_info(client, token)
    answer_checklist(client, token, ["tee_markers_blocks"])

    client.post(
        f"/f/{token}/page/tee_markers",
        data={
            "action": "next",
            "entry_count-tee_markers_blocks": "1",
            "entry-tee_markers_blocks-0-type": "Standard",
            "entry-tee_markers_blocks-0-count": "9",
            "entry-tee_markers_blocks-0-notes": "entry note",
            "product-notes-tee_markers_blocks": "product note",
            "page-notes": "page note",
        },
    )
    client.post(f"/f/{token}/services", data={"action": "next"})
    client.post(f"/f/{token}/review", data={"order_notes": "order note", "confirm_accurate": "on"})

    with app.app_context():
        submission = Submission.query.filter_by(token=token).first()
        assert submission.order_notes == "order note"
        assert submission.designs[0].notes == "entry note"
        assert submission.product_notes[0].notes == "product note"
        assert submission.page_notes[0].notes == "page note"
