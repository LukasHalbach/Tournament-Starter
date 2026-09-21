"""Computes the client's page list once, in one place.

Every Back/Next link, the progress indicator, and access control for the
dynamic pages all read from `build_steps()`. Templates never decide what
comes next — they only render the step they were given.
"""
from __future__ import annotations

from flask import url_for

STEP_INFO = "info"
STEP_CHECKLIST = "checklist"
STEP_SERVICES = "services"
STEP_REVIEW = "review"


def build_steps(catalog, selections: dict[str, bool | None]) -> list[str]:
    """Ordered list of step keys: info, checklist, <yes pages...>, services, review."""
    steps = [STEP_INFO, STEP_CHECKLIST]
    steps.extend(page.key for page in catalog.visible_pages(selections))
    steps.append(STEP_SERVICES)
    steps.append(STEP_REVIEW)
    return steps


def step_url(token: str, step_key: str) -> str:
    if step_key in (STEP_INFO, STEP_CHECKLIST, STEP_SERVICES, STEP_REVIEW):
        return url_for(f"public.{step_key}", token=token)
    return url_for("public.dynamic_page", token=token, page_key=step_key)

def step_title(catalog, step_key: str) -> str:
    titles = {
        STEP_INFO: "Tournament Info",
        STEP_CHECKLIST: "Product Checklist",
        STEP_SERVICES: "Services",
        STEP_REVIEW: "Review",
    }
    if step_key in titles:
        return titles[step_key]
    page = catalog.get_page(step_key)
    return page.title if page else step_key


def neighbors(steps: list[str], current: str) -> tuple[str | None, str | None]:
    idx = steps.index(current)
    prev_step = steps[idx - 1] if idx > 0 else None
    next_step = steps[idx + 1] if idx < len(steps) - 1 else None
    return prev_step, next_step


def progress(steps: list[str], current: str) -> tuple[int, int]:
    """1-based (position, total) for a 'Sponsor & Brand — 4 of 7' style indicator."""
    return steps.index(current) + 1, len(steps)
