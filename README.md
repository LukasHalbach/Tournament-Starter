# TSi Tournament Starter Form

A small Flask app that collects golf tournament signage requirements from
clients. Everything about which products exist, which page they show up on,
and how that page renders lives in **`catalog.yaml`** — not in the code.

## Phase 1 (this build)

Client flow (Tournament Info → Product Checklist → the configured pages, in
order, for whatever the client said Yes to → Services → Review → Confirmation),
save/resume with no accounts, catalog-driven navigation, generic repeat
mechanics on every layout, local file uploads, and a password-protected admin
list/detail view — all working end to end against SQLite and local file
storage.

Not in Phase 1 (see the prompt file for the full plan): Excel export, ZIP
download, email notifications, and the Railway/S3 deploy path. The storage
and config layers are already shaped so those are additive later, not a
rewrite.

**The catalog ships empty.** `catalog.yaml` has the two top-level keys
(`pages: []`, `products: []`) commented with examples, but no real products —
add your own tournament signage catalog by editing that file.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — at minimum set SECRET_KEY and ADMIN_PASSWORD
export $(grep -v '^#' .env | xargs)   # or use python-dotenv / direnv

flask db upgrade      # creates instance/tournament.db (SQLite)
flask validate-catalog
flask run
```

Visit `http://127.0.0.1:5000/` to start a new form, or `/admin` to log in as
staff (password from `ADMIN_PASSWORD`).

`flask seed-demo` creates one draft submission with every active product
unanswered, and prints its resume link.

## Editing `catalog.yaml`

Nothing about a product's page assignment or rendering is inferred from its
name — you set it explicitly with `page:` and the page's `layout:` decides
what fields the product gets.

### Add a product

```yaml
products:
  - key: pin_flags              # stable id — never rename this once submissions exist
    section: Course              # groups it on the checklist and in reports
    name: Pin Flags              # what the client sees
    page: course_signage         # must match a pages[].key
    design_label: Pin Flag Design
    type_label: Flag Style
    hole_select: true
    entry_notes_label: "Notes for this flag"
    product_notes_label: "Notes about pin flags overall"
```

Restart the app (or just re-run `flask run` in dev, which reloads). It
appears on the checklist under `Course`, and once answered Yes, on whatever
page `course_signage` is.

### Move a product to a different page

Change its `page:` value to another page's `key`. That's the whole
operation — no code change, no migration. Existing submissions keep their
data; only *current* forms pick up the new placement, because the page a
submission's data belongs to is never stored on the row, only the
`product_key`.

### Add a whole new page

```yaml
pages:
  - key: hospitality
    order: 45                    # gaps are fine — insert between existing pages
    title: Hospitality
    layout: design_blocks        # count_only | design_blocks | yes_no_detail
    notes_label: "Anything else about hospitality signage?"
```

Point one or more products at `page: hospitality` and it's live. A page with
no Yes products on it is skipped automatically — it never shows up in
navigation for that client.

Run `flask validate-catalog` after any edit — it catches duplicate keys,
unknown layouts, products pointing at pages that don't exist, duplicate
`order` values, and `design_blocks` products missing a `design_label`,
before you restart the server.

## Layouts

- **`count_only`** — a required integer stepper (1–500) plus optional notes,
  repeated per entry.
- **`design_blocks`** — type (dropdown or free text), count, optional hole
  picker, description, file uploads, an optional link, and per-entry notes.
- **`yes_no_detail`** — a fixed Yes/No + notes question; used by the built-in
  Services page and not driven by the catalog.

`repeatable: false` on a product is the only thing that ever turns off
"Add another" for it — every product gets the repeat controls by default, on
every layout.

## Notes fields

There are four levels, and each is independently optional except the
order-level one on Review:

1. Per entry (`entry_notes_label` on a product)
2. Per product (`product_notes_label` on a product)
3. Per page (`notes_label` on a page)
4. Whole order (always present on Review)

In the admin view, any note a client actually filled in shows in a
highlighted box next to what it attaches to, plus a "Client notes" summary
panel at the top of each submission.

## Running tests

```bash
pytest
```

Covers catalog loading/validation, the computed page list (skipping all-No
pages, showing a shared page once), add/remove of entries on both layouts,
`repeatable: false` rejection, unanswered-checklist blocking, the soft-hide
round trip on a Yes→No→Yes flip, and token access control.

## Deploying to Railway

1. Create a Postgres database and a bucket (Phase 2, once S3 storage lands)
   on Railway; set `DATABASE_URL` from the Postgres plugin.
2. Set `SECRET_KEY`, `ADMIN_PASSWORD`, and the rest of `.env.example`'s keys
   as Railway environment variables.
3. `railway.json` runs `flask db upgrade` before `gunicorn wsgi:app` on
   every deploy — no manual migration step.

## Project layout

```
app/
  catalog.py       # loads + validates catalog.yaml
  navigation.py     # computes the client's page list, once, in one place
  entries.py        # generic add/remove/save for repeated entries
  page_forms.py     # parses & validates the count_only / design_blocks forms
  storage.py        # local-folder file storage behind a swappable interface
  models.py
  routes/
    public.py        # the client-facing form
    admin.py          # /admin
  templates/
tests/
catalog.yaml
```
