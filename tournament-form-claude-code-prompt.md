# Build: TSi Tournament Starter Form (Flask app on Railway)

## Context
I'm the Systems Analyst at TSi Events, a Phoenix event signage and production company. Golf tournament clients need to tell us what signage they need for an event. Off-the-shelf form builders can't do this flow at a price we want, so we're building a small custom web app.

**The core pattern — this is the heart of the app:**

1. **Page 1 is a checklist of every product we commonly make**, grouped by section, each with a simple **Yes / No**. Nothing is preselected — every product starts blank, and the client has to answer each one before moving on.
2. **Products marked Yes appear later on a page I assign them to. Products marked No are hidden entirely** — no page, nothing in the summary.
3. **Pages are defined in configuration, and I assign each product to one by hand.** The app must never try to infer what kind of answer a product needs. I write `page: tee_markers` (or whatever) on the product, and that's where it shows up. Several products can share a page, and a page that ends up with no Yes products is skipped automatically.
4. **Each page has a layout** — one of a small set the app knows how to render. Products that only need a quantity all sit together on one count page. Products that need artwork get a page with repeating design blocks. I decide which is which.
5. **Every product can repeat, on every layout — available everywhere by default, switched off per product where it doesn't make sense.** A product holds one or more entries and shows an "Add another" control. If a client wants a different logo or color on each hole, they add an entry per variation; if all 18 are identical, they leave it at one entry with a count of 18. Build the repeat mechanics once, generically, so `repeatable: false` on a product is the only thing that ever turns it off — never a limitation of a layout or a template.
6. **Notes fields are everywhere and always optional, and each one names what it attaches to.** Clients will have special requests, and I'd rather collect them in the right place than find them buried in one giant comment box at the end.

Here's the design-block layout, which I mocked up for Tee Markers:

```
Tee Markers

  ┌ Tee Marker Design 1 ────────────────────────── (x) remove ┐
  │  Tee Marker Type *  [ dropdown        v ]   Count * [ - 12 + ] │
  │  Description                                                   │
  │  [ multi-line textbox                                        ] │
  │  Design File Upload                                            │
  │  [ Upload | or drag files here.                              ] │
  └────────────────────────────────────────────────────────────────┘

  [ + Add Tee Marker Design ]

  [ Back ]  [ Next ]
```

One design with a count of 18 means the same artwork on 18 signs; three designs means three different artworks. The client controls how many blocks exist by clicking "Add [design label]" — we never generate blocks from an earlier number.

And here's the count layout, with several products sharing one page. Note that these repeat too:

```
Quantities

  Quiet Paddles
    [ - 24 + ]  [ notes                              ]  (x)
    [ +  8  + ]  [ notes                              ]  (x)
    [ + Add Quiet Paddles entry ]

  Trash Racks
    [ -  8 + ]  [ notes                              ]  (x)
    [ + Add Trash Racks entry ]

  [ Back ]  [ Next ]
```

Before writing code, read this whole prompt, then give me a short plan (file structure, data model, page flow, anything you'd change or need clarified). Wait for my OK, then build Phase 1.

## Tech stack
- Python 3.12, Flask, Jinja2 templates, SQLAlchemy.
- Database: SQLite for local dev, Postgres on Railway (read `DATABASE_URL`; fall back to SQLite when it's unset).
- File storage: S3-compatible bucket (Railway bucket in prod) via boto3. Use **presigned direct-to-bucket uploads** from the browser so large print files (AI, EPS, PDF, often 50–500 MB) never pass through Flask. Local dev uses a local folder behind the same storage interface.
- Frontend: server-rendered pages with small vanilla JS (or htmx) for the repeating design blocks and uploads. No React/SPA build step.
- Deploy target: Railway (gunicorn, `Procfile` or `railway.json`, config from environment variables).
- Include `requirements.txt`, `.env.example`, and a `README.md` with local setup and Railway deploy steps.

## The catalog and the page map are configuration, not code
This is a hard requirement. I need to add, remove, rename, and reorder products **and pages** without touching application code or running a migration. Put both in **`catalog.yaml`**, load it at startup, and drive the entire form from it.

The file has two top-level keys: `pages` and `products`.

### `pages` — I define these and their order
```yaml
pages:
  - key: quantities
    order: 10                   # position in the form; gaps are fine, so I can insert later
    title: Quantities
    layout: count_only
    intro: "Just tell us how many of each you need."   # optional

  - key: tee_markers
    order: 20
    title: Tee Markers
    layout: design_blocks

  - key: course_signage
    order: 30
    title: Course Signage
    layout: design_blocks
```

**`layout` must be one of a fixed set the app implements.** Build these three:

- **`count_only`** — each entry is a required integer stepper (min 1, max 500) plus an optional notes field. No uploads.
- **`design_blocks`** — each entry is the block from the mockup: type, count, optional holes, description, file uploads, link.
- **`yes_no_detail`** — a question and a notes field, for things that aren't really products. Used by the Services page; this is the one layout that doesn't repeat.

In both `count_only` and `design_blocks`, every Yes product on the page gets its own headed section holding its entries and its own "Add another" control, so the repeat behavior is identical across layouts and only the fields differ. If a page ends up with just one Yes product, skip the redundant heading.

Adding a fourth layout later should mean writing one entry template and registering it — not touching the navigation, the repeat mechanics, or the save logic.

Pages may also carry two optional keys:

```yaml
  - key: course_signage
    order: 30
    title: Course Signage
    layout: design_blocks
    notes_label: "Anything else about your course signage?"   # optional page-level notes
    notes_help: "Course access, cart path restrictions, anything our install crew should know."
```

When `notes_label` is set, the page ends with an optional multi-line notes field carrying that label. Omit it and the page has none.

### `products` — each one names the page it belongs to
```yaml
products:
  - key: tee_markers_blocks     # stable id, never changes; this is what's stored in the DB
    section: Course             # grouping on the yes/no checklist only
    name: Tee Markers / Blocks  # client-facing label
    page: tee_markers           # REQUIRED — which page this shows up on. I set this by hand.
    design_label: Tee Marker Design   # block headings and the "Add ..." button
    type_label: Tee Marker Type       # label for the dropdown inside each design
    types:                      # optional; omit for a free-text field instead
      - Standard
      - Championship
      - Custom Shape
    hole_select: true           # optional, see below
    repeatable: true            # optional, defaults to TRUE; set false to lock at one entry
    entry_notes_label: "Notes for this design"        # optional, per-entry notes
    product_notes_label: "Notes about your tee markers"   # optional, per-product notes
    default_material: "Overlaminate - 1.3mil - UV - Gloss - 54\""
    uom: SquareFeet
    active: true                # false hides it from the checklist without deleting history
```

Notes on the fields:

- **`page`** — required on every product, and must match a `pages` key. This is the whole point: I assign pages manually, the app never guesses. The fields a product renders come from its page's `layout`, so `design_label`, `type_label`, `types`, and `hole_select` are only read on a `design_blocks` page and can be omitted elsewhere.
- **`types`** — populates the dropdown inside each design block. If the list is missing or empty, render a plain text field with the same label instead. When `types` is present, include an "Other" choice that reveals a text field.
- **`hole_select: true`** — adds a hole picker (checkboxes 1..N, where N is the course hole count from page 1) inside each design block, labeled "Which holes use this design?". Selecting holes auto-fills Count but leaves it editable. For hole-tied items: Hole/Yard/Par signs, tee fences, tee markers, pin flags, hole-in-one signage.
- **`repeatable`** — defaults to `true`, so the "Add another" control is available on every product unless I deliberately switch it off. Setting `false` locks the product to a single entry and hides both the add and remove controls. Implement the repeat once, generically, and gate only the controls on this flag — I want it available everywhere just in case, since for some products a second entry makes no sense and I'd rather not offer it.
- **`entry_notes_label` / `product_notes_label`** — optional labels that turn on notes fields at those two levels (see the notes section below). Omit either one and that field doesn't render.
- **`section`** — used only for grouping on the yes/no checklist and in the admin summary. It has nothing to do with which page a product lands on. Two products in the same section can sit on different pages, and one page can mix sections.
- **`active: false`** — keeps the item out of new forms while preserving old submissions that reference it.

Because `key` is what gets stored, renaming `name` must not break existing submissions. Unknown keys found in old submissions should render with a fallback label rather than crashing.

### Notes fields
Every notes field is optional, is a multi-line textbox, and must be labeled so both the client and we can tell what it's attached to. Never use a bare "Notes" label. There are four levels:

1. **Per entry** — on when the product sets `entry_notes_label`. Attaches to one design or one count row. For "this one goes on the halfway house wall, not a stake."
2. **Per product** — on when the product sets `product_notes_label`. Attaches to all of that product's entries. For "all tee markers need to match last year's."
3. **Per page** — on when the page sets `notes_label`.
4. **Whole order** — always present, on the Review page, labeled "Anything else we should know about this tournament?"

Seed the config so that on a `design_blocks` product both `entry_notes_label` and `product_notes_label` are set, on a `count_only` product only `entry_notes_label` is, and every page has a `notes_label`. I'd rather start with too many prompts for special requests and remove the ones nobody uses.

In the admin view, **any note a client actually filled in must be impossible to miss**: render it with a distinct background, right next to whatever it attaches to, and put a "has notes" indicator on the submissions list. The whole reason for scoping notes is so a special request lands next to the sign it's about instead of in a pile at the end.

**Startup validation, failing loudly with a clear message:** unique page keys and product keys; every product's `page` resolves to a real page; every page's `layout` is one implemented; no duplicate `order` values; `design_blocks` products have a `design_label`. Also add a `flask validate-catalog` CLI command so I can check my edits before restarting.

### Seed catalog
Seed `catalog.yaml` with the products below. I've put `tournament_core_items_v2.csv` in the project folder — it has `section`, `item`, `default_material`, and `uom` columns. Pull material and UOM from it and ignore the order-stat columns. Leave `types` empty everywhere for now; I'll fill those in myself. Set sensible `design_label` and `type_label` values from each name.

The page assignments below are a **starting point that I will rearrange** — that's the point of the design. Give me sane `order` values with gaps of 10.

**Page `quantities`** (`count_only`) — Quiet Paddles; Trash Racks; Green Exits / Crossovers; Restroom Signs; First Aid Signage; Policy & Rules Signage; Standards (frames / rental)

**Page `course_signage`** (`design_blocks`) — Tee Fences (+centers/wings) `hole_select`; Tee Markers / Blocks `hole_select`; Hole Signs / IDs / Fairway Boards (Hole/Yard/Par) `hole_select`; Pin Flags `hole_select`

**Page `wayfinding`** (`design_blocks`) — Road / Directional Signs; Parking Signage; Course Maps; Welcome Signage; Check-In / Admissions; WiFi / Info Signs

**Page `sponsor_brand`** (`design_blocks`) — Standard / Range / Locker Names; Standard & Range Headers; Sponsor Boards; Banners (+light pole); Structure Wraps / Clubhouse; Step and Repeat; Feather / Suite / Expo Flags

**Page `hospitality`** (`design_blocks`) — Tent Gables / Eaves; Concession / Bar Menus; Concession / Hospitality Signage; Suite IDs / Signs; Drink Rails; Cooler Decals / Stands; Bar Fronts

**Page `practice_range`** (`design_blocks`) — A-Frames; Range Signage (misc); Putting Green Sponsor

**Page `credentials_people`** (`design_blocks`) — Volunteer Signage / HQ; Caddie Backs (+names); Credentials / Cred Boards; Caddie Bibs; Office / Committee Signs; Locker Room Names / Rental

**Page `operations_vehicles`** (`design_blocks`) — Ops Boards (pairings / scoring / media); Cart Decals / Stickers; Vehicle / Trailer Decals & Numbers

**Page `ceremony_fan`** (`design_blocks`) — Winners / Charity Check; Trophy Stand (+wrap/rental); Hole-in-One Signage `hole_select`; Autograph Flags; Fan Experience Features; Mic Flags

Keep each product's `section` set to its section from the CSV, since that drives the checklist grouping independently of these pages.

Installation, Rope and Stake, and Freight / Float are not products. They live on a `services` page using the `yes_no_detail` layout, and they're always shown rather than gated by the checklist.

## Page flow

**1. Tournament Info**
Tournament name, course name, start/end dates, install deadline, number of holes on the course (default 18), primary contact name/email/phone, notes.

**2. Product Checklist** (the yes/no page)
Every `active` product, grouped by section with section headings, each a Yes / No control that **starts blank — neither option selected.** Don't default to No; an unanswered product is a different thing from one the client deliberately declined, and I want to know which is which.

- Every product must be answered before Next. On submit, scroll to the first unanswered product and highlight it.
- Each section header shows its progress ("6 of 9 answered") and how many Yes answers it holds.
- Sections are collapsible, with a "Mark remaining as No" action per section so a client can clear a section they don't need in one click.
- This page can be long — make it scannable and fast on mobile.
- Short intro text: "Tell us what you need. You'll give us the details for each one on the following pages."

**3. The configured pages, in `order`, skipping any page whose products were all answered No**

Each page renders a headed section per Yes product. Every section holds one or more entries, starts with a single empty entry, and ends with an "Add another" control — unlimited, on every product and every layout, unless that product sets `repeatable: false`. A product's own notes field, when configured, sits at the end of its section; the page's notes field, when configured, sits above Back/Next.

On a `count_only` page each entry is a count stepper plus its optional notes field.

On a `design_blocks` page each entry is a design block with:
- Type (dropdown from `types`, or a text field when `types` is absent), required
- Count, integer stepper, required, min 1, max 500
- Which holes use this design? (only when `hole_select`), checkboxes 1..N; selecting holes auto-fills Count
- Description, multi-line textbox, with help text "Size, placement, wording, sponsor details"
- Design File Upload: multiple files, drag-and-drop, per-file progress bar. Allowed: pdf, ai, eps, psd, svg, png, jpg, jpeg, tif, tiff, zip. Max size per file from an env var, default 1 GB.
- Optional "Link to files" URL field, for clients who'd rather send a Drive or Dropbox link
- The entry notes field, when the product configures one
- A remove (x) control on each block, disabled when only one block remains and hidden entirely when `repeatable: false`
- A "Copy from previous design" action that duplicates the block above except for files

Entries on both layouts are numbered within their product ("Tee Marker Design 2"), stay in the order the client added them, and keep their data when a sibling entry is removed. The page footer has Back and Next, and the page number.

A worked example of why this matters: a client needs tee markers on all 18 holes, but holes 1–9 carry the title sponsor's logo and 10–18 carry a second sponsor's. They add two Tee Marker entries, each with its own artwork, description, and holes. Nothing about the product configuration changes — the client just clicks "Add Tee Marker Design" a second time.

**4. Services** (`yes_no_detail`)
Need installation? (Y/N + notes). Need rope and stake? (Y/N + notes). Need freight/delivery? (Y/N + address + notes).

**5. Review**
Read-only summary grouped by section: each product, its entries, type, count, holes, description, notes at every level, and attached file names, plus a total sign count per product and for the whole order. Each product has an "Edit" link back to its page. Ends with the always-present order-level notes field ("Anything else we should know about this tournament?"), then a required "I confirm this is accurate" checkbox, then Submit.

**6. Confirmation page.**

### Behavior requirements
- **Save and resume with no accounts.** Starting a form creates a draft at an unguessable token URL (`/f/<token>`). Every Next saves. Show the client their resume link, and email it to the primary contact once the contact info exists.
- **Changing the checklist must not destroy work.** If a client goes back and flips a product from Yes to No after filling in designs, soft-hide that product's data rather than deleting it, warn them first, and restore it if they flip back to Yes.
- **Navigation is computed, in one place.** Build the client's page list once, from the configured pages in `order` intersected with the Yes answers, and drive Back, Next, the progress indicator ("Sponsor & Brand — 4 of 7"), and access control from that single list. A page whose products were all answered No never appears, and deep-linking to it redirects. Keep this logic out of the templates so adding a layout later doesn't touch it.
- **A product marked No is invisible on its page**, even when other products on that page were marked Yes.
- **Server-side validation is authoritative**; client-side validation is a convenience only.
- **Mobile-friendly.** Clients will fill this out on phones and iPads.
- TSi branding, with logo placeholder and colors in a single CSS variables block.

## Admin side (TSi staff)
- `/admin`, protected by a password from env var `ADMIN_PASSWORD` via session login. One role is enough for Phase 1.
- **Submissions list:** tournament, course, contact, dates, status (Draft / Submitted / In Review / Complete), submitted date, product count, total sign count, and a "has notes" indicator. Filter by status.
- **Submission detail:** everything the client entered, grouped by section, with image thumbnails and download links. Notes are highlighted next to what they attach to, and a "Client notes" panel at the top collects every note the client filled in, each labeled with its scope, so nothing gets missed on a long submission.
- **Download all files as a ZIP**, organized `Section/Product/Design-N/filename`.
- **Export to Excel (.xlsx)**: one row per entry, with columns tournament, section, product, type, count, holes, description, entry notes, product notes, page notes, file count, file links, default_material, uom. This is the future bridge into Striven.
- Staff can change status and add internal notes.
- A read-only view of the loaded catalog and page map, so staff can see which products sit on which page without opening the YAML.

## Notifications
Email over SMTP (settings from env vars, skipped gracefully when unset): resume link to the client, submission confirmation to the client, and a new-submission alert to `TSI_NOTIFY_EMAIL`.

## Data model (suggested; improve it if you see better)
- `Submission` — id, token, status, tournament fields, contact fields, course_holes, services fields, order_notes, timestamps, confirmed_at
- `PageNote` — submission_id, page_key, notes
- `ProductNote` — submission_id, product_key, notes
- `ProductSelection` — submission_id, product_key, included (**nullable** bool: null = unanswered, true = Yes, false = No), hidden (bool, for the soft-hide on flipping to No)
- `Design` — submission_id, product_key, position, type_value, type_other, count, holes (JSON list), description, link_url, notes  *(from `design_blocks` pages)*
- `Attachment` — design_id, storage_key, original_filename, size, content_type, uploaded_at
- `CountLine` — submission_id, product_key, **position**, quantity, notes  *(from `count_only` pages; repeats per product exactly like `Design` does)*
- `AdminNote`

Use Flask-Migrate/Alembic. Store `product_key` as a string rather than a foreign key to a products table, so the catalog stays in YAML. **Don't store the page key on submission rows** — a product's page assignment is current configuration, not history, so moving a product to a different page must not alter or orphan existing submissions.

## Security
- CSRF protection on all forms.
- `secrets.token_urlsafe` for draft tokens.
- Validate file type by extension and content type; presigned URLs are short-lived and scoped to that submission's prefix.
- Never expose storage keys belonging to another submission.
- Rate-limit new form creation.

## Phases
- **Phase 1 (build now):** everything above except the Excel export, ZIP download, and email. Client flow, checklist-driven navigation, design repeaters, uploads, save/resume, and the admin list/detail working end to end locally, with a seeded demo submission.
- **Phase 2:** Excel export, ZIP download, email notifications, Railway deploy.
- **Phase 3 (don't build, just don't design it out):** push submissions into Striven via its API; prefill a new form from last year's tournament.

## Definition of done for Phase 1
- `flask run` works locally against SQLite with local file storage.
- I mark Yes on products spread across three pages, see exactly those three pages and no others, add multiple designs with multi-file uploads, close the browser, resume from the link, flip a product to No and back without losing its designs, and submit.
- Marking Yes on two products that share a page gives me one page with both on it.
- **Every Yes product on every page lets me add a second, third, and fourth entry, and remove any of them without disturbing the others** — including on a `count_only` page.
- Setting `repeatable: false` on one product hides its add and remove controls and rejects a second entry server-side, while every other product on that same page still repeats normally.
- Notes I type at the entry, product, page, and order levels all survive a resume and a submit, and every one of them is visible and labeled in the admin view without hunting.
- Two Tee Marker designs with different holes and different uploaded artwork survive a save, a resume, and a submit, and show as two separate line items in the admin view.
- Admin logs in and sees the submission with working file links.
- **I can move a product to a different page, change a page's title or order, or add a whole new page, by editing `catalog.yaml` and restarting — no code changes, no migration, and existing submissions still render correctly.**
- I can add a product to `catalog.yaml`, restart, and see it on the checklist and on its assigned page.
- `flask validate-catalog` catches a product pointing at a nonexistent page, a duplicate key, and an unknown layout.
- Leaving any product unanswered on the checklist blocks Next and jumps me to the first blank one.
- pytest covers catalog and page-map loading and validation, page-list computation from the Yes answers, a page correctly skipped when all its products are No, add/remove of entries on both layouts, unanswered-product validation, the soft-hide round trip, and token access control.
- README explains how to run it and, with worked examples, how to edit `catalog.yaml` to add a product, move one between pages, and add a page.
