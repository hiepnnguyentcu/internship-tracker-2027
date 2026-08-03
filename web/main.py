"""FastAPI web app — sub-chunk A: queue view + auth gate + manual-apply flow
(feature parity with the removed PySide6 desktop app). Real auto-apply
automation lands in sub-chunk C.

Runs locally on the user's own Mac, reachable from other devices via
Tailscale (or similar) rather than public hosting — see the Phase 2 plan.

Usage:
    export TRACKER_WEB_PASSWORD='...'
    uvicorn web.main:app --reload --host 0.0.0.0 --port 8420
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Form, Request  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

from scripts.log_application import record_application  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402
from web.auth import (  # noqa: E402
    SESSION_COOKIE_NAME, check_password, create_session, invalidate_session, is_valid_session,
)
from web.queue_model import find_queue_item, load_queue, load_resumes  # noqa: E402

app = FastAPI(title="Internship Tracker")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _authed(request: Request) -> bool:
    return is_valid_session(request.cookies.get(SESSION_COOKIE_NAME))


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse("/queue" if _authed(request) else "/login")


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: str | None = None):
    message = "Wrong password." if error else None
    return templates.TemplateResponse(request, "login.html", {"error": message})


@app.post("/login")
def login_submit(password: str = Form(...)):
    if not check_password(password):
        return RedirectResponse("/login?error=1", status_code=303)
    response = RedirectResponse("/queue", status_code=303)
    response.set_cookie(SESSION_COOKIE_NAME, create_session(), httponly=True, samesite="lax")
    return response


@app.post("/logout")
def logout(request: Request):
    invalidate_session(request.cookies.get(SESSION_COOKIE_NAME))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, flash: str | None = None, error: str | None = None):
    if not _authed(request):
        return RedirectResponse("/login")

    sheets = SheetsClient()
    try:
        queue = load_queue(sheets)
        resumes = load_resumes(sheets)
    except Exception as exc:  # noqa: BLE001
        return templates.TemplateResponse(
            request, "queue.html", {"queue": [], "resumes": [], "flash": None, "error": str(exc)}
        )

    return templates.TemplateResponse(
        request, "queue.html", {"queue": queue, "resumes": resumes, "flash": flash, "error": error}
    )


@app.post("/apply/manual")
def apply_manual(request: Request, listing_key: str = Form(...), resume_id: str = Form(...)):
    if not _authed(request):
        return RedirectResponse("/login")

    sheets = SheetsClient()
    item = find_queue_item(listing_key, sheets)
    if item is None:
        return RedirectResponse("/queue?error=Listing+not+found+(already+applied+or+removed)", status_code=303)

    try:
        result = record_application(
            sheets,
            company=item.company,
            role=item.role,
            resume_id=resume_id,
            stage="Applied",
            job_url=item.url,
            source=item.source_repo,
        )
    except Exception as exc:  # noqa: BLE001
        return RedirectResponse(f"/queue?error=Failed+to+log:+{exc}", status_code=303)

    return RedirectResponse(f"/queue?flash=Logged+application+{result['app_id']}", status_code=303)
