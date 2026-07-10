"""
CALIBER v3 — FastAPI web application.

Four views: Library, Deep, Compare, Batch + Flag-resolution.
Auth: single APP_PASSWORD checked against a session cookie (HMAC-derived token).

Run:
  cd caliber
  uvicorn web.app:app --reload --port 8000
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import Cookie, FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

from store.models import (
    get_conflicts, get_evaluation, get_overrides_by_key,
    init_db, list_evaluations, list_grades, list_overrides, save_override,
)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
_TICKERS_FILE = _ROOT / "tickers.txt"

app = FastAPI(title="CALIBER v3", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

init_db()  # ensure tables exist at startup


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _make_token(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()[:32]


def _is_authed(session: Optional[str]) -> bool:
    if not _APP_PASSWORD:
        return True
    return bool(session) and hmac.compare_digest(session, _make_token(_APP_PASSWORD))


def _redirect_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


# ── Jinja2 filters ────────────────────────────────────────────────────────────

def _f_conf_dot(conf: str) -> str:
    return {"high": "●", "medium": "◑", "low": "○"}.get(str(conf).lower(), "?")

def _f_conf_cls(conf: str) -> str:
    return f"conf-{str(conf).lower()}"

def _f_er_fmt(v) -> str:
    if v is None:
        return "—"
    sign = "+" if float(v) >= 0 else ""
    return f"{sign}{float(v):.1f}%"

def _f_score_segs(score) -> list:
    s = int(score or 0)
    return [i < s for i in range(5)]

def _f_fmt_dt(dt_str: str) -> str:
    if not dt_str:
        return "—"
    return str(dt_str)[:16].replace("T", " ")

def _f_fmt_date(dt_str: str) -> str:
    return str(dt_str)[:10] if dt_str else "—"

def _f_prob_fmt(p) -> str:
    if p is None:
        return "—"
    return f"{int(p)}%"

def _f_target_fmt(v) -> str:
    if v is None:
        return "—"
    return f"${float(v):.0f}"

def _f_ret_fmt(price, target) -> str:
    """Return % from current price to target."""
    try:
        price, target = float(price), float(target)
        if price > 0 and target is not None:
            pct = (target / price - 1) * 100
            sign = "+" if pct >= 0 else ""
            return f"{sign}{pct:.1f}%"
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return "—"

def _f_lens_cls(lens: str) -> str:
    return f"lens-{(lens or 'standard').lower()}"

def _f_lens_label(lens: str) -> str:
    return {
        "cyclical": "CYCLICAL / MID-CYCLE",
        "compounder": "QUALITY COMPOUNDER",
        "growth": "GROWTH / RULE-OF-40",
        "bank": "BANK / INSURER",
        "standard": "STANDARD",
    }.get((lens or "").lower(), (lens or "STANDARD").upper())

def _f_score_color(score) -> str:
    s = int(score or 0)
    if s >= 4: return "score-high"
    if s >= 3: return "score-mid"
    return "score-low"

templates.env.filters.update({
    "conf_dot": _f_conf_dot,
    "conf_cls": _f_conf_cls,
    "er_fmt": _f_er_fmt,
    "score_segs": _f_score_segs,
    "fmt_dt": _f_fmt_dt,
    "fmt_date": _f_fmt_date,
    "prob_fmt": _f_prob_fmt,
    "target_fmt": _f_target_fmt,
    "ret_fmt": _f_ret_fmt,
    "lens_cls": _f_lens_cls,
    "lens_label": _f_lens_label,
    "score_color": _f_score_color,
})


# ── Data helpers ──────────────────────────────────────────────────────────────

def _prep_eval(row: dict) -> dict:
    """Parse JSON blobs; normalise an evaluation row for templates."""
    pillars = json.loads(row["pillars_json"]) if row.get("pillars_json") else []
    synthesis = json.loads(row["synthesis_json"]) if row.get("synthesis_json") else None
    return {
        **row,
        "pillars": pillars,
        "synthesis": synthesis,
        "run_at_short": str(row.get("run_at") or "")[:10],
    }


def _read_universe() -> list:
    try:
        lines = _TICKERS_FILE.read_text(encoding="utf-8").splitlines()
        return [l.split("#")[0].strip().upper() for l in lines if l.split("#")[0].strip()]
    except FileNotFoundError:
        return []


# ── Login / Logout ────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_get(
    request: Request,
    caliber_session: Optional[str] = Cookie(None),
    error: str = "",
):
    if _is_authed(caliber_session):
        return RedirectResponse("/library", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    password: str = Form(...),
):
    if not _APP_PASSWORD or hmac.compare_digest(password, _APP_PASSWORD):
        resp = RedirectResponse("/library", status_code=303)
        resp.set_cookie("caliber_session", _make_token(password or _APP_PASSWORD), httponly=True, samesite="lax")
        return resp
    return templates.TemplateResponse(request, "login.html", {"error": "Wrong password."})


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("caliber_session")
    return resp


@app.get("/", response_class=HTMLResponse)
async def root(caliber_session: Optional[str] = Cookie(None)):
    if not _is_authed(caliber_session):
        return _redirect_login()
    return RedirectResponse("/library", status_code=303)


# ── Library ───────────────────────────────────────────────────────────────────

@app.get("/library", response_class=HTMLResponse)
async def library(
    request: Request,
    caliber_session: Optional[str] = Cookie(None),
    ticker: str = "",
    status: str = "",
    msg: str = "",
):
    if not _is_authed(caliber_session):
        return _redirect_login()

    rows = list_evaluations(ticker=ticker.upper() if ticker else None, limit=200)
    if status:
        rows = [r for r in rows if r.get("status") == status]

    return templates.TemplateResponse(request, "library.html", {
        "evals": rows,
        "filter_ticker": ticker,
        "filter_status": status,
        "msg": msg,
    })


# ── Deep view ─────────────────────────────────────────────────────────────────

@app.get("/eval/{eval_id}", response_class=HTMLResponse)
async def deep_view(
    request: Request,
    eval_id: int,
    caliber_session: Optional[str] = Cookie(None),
    override_msg: str = "",
):
    if not _is_authed(caliber_session):
        return _redirect_login()

    row = get_evaluation(eval_id)
    if not row:
        return HTMLResponse("<h2>Evaluation not found</h2>", status_code=404)

    ev = _prep_eval(row)
    conflicts = get_conflicts(eval_id=eval_id)
    overrides = get_overrides_by_key(ev["ticker"])

    # Annotate conflicts with existing override
    for c in conflicts:
        c["override"] = overrides.get(c["field_key"])

    return templates.TemplateResponse(request, "deep.html", {
        "ev": ev,
        "conflicts": conflicts,
        "overrides": list(overrides.values()),
        "override_msg": override_msg,
    })


# ── Compare ───────────────────────────────────────────────────────────────────

@app.get("/compare", response_class=HTMLResponse)
async def compare(
    request: Request,
    caliber_session: Optional[str] = Cookie(None),
    ids: str = "",
):
    if not _is_authed(caliber_session):
        return _redirect_login()

    evals = []
    if ids:
        for id_str in ids.split(","):
            id_str = id_str.strip()
            if id_str.isdigit():
                row = get_evaluation(int(id_str))
                if row and row.get("status") == "ok":
                    evals.append(_prep_eval(row))

    # For selecting which evals to compare
    all_evals = list_evaluations(limit=100)
    ok_evals = [r for r in all_evals if r.get("status") == "ok"]

    return templates.TemplateResponse(request, "compare.html", {
        "evals": evals,
        "all_evals": ok_evals,
        "selected_ids": ids,
    })


# ── Batch + Flag-resolution ───────────────────────────────────────────────────

@app.get("/batch", response_class=HTMLResponse)
async def batch_view(
    request: Request,
    caliber_session: Optional[str] = Cookie(None),
    msg: str = "",
):
    if not _is_authed(caliber_session):
        return _redirect_login()

    recent = list_evaluations(limit=30)
    universe = _read_universe()
    conflicts = get_conflicts()          # all conflicts across all evals
    overrides = list_overrides()

    # Deduplicate conflicts by field_key (show most recent per ticker+field)
    seen: set = set()
    deduped = []
    for c in conflicts:
        key = f"{c['ticker']}::{c['field_key']}"
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    return templates.TemplateResponse(request, "batch.html", {
        "recent": recent,
        "universe": universe,
        "conflicts": deduped,
        "overrides": overrides,
        "msg": msg,
    })


@app.post("/batch/run")
async def batch_run(
    request: Request,
    caliber_session: Optional[str] = Cookie(None),
):
    if not _is_authed(caliber_session):
        return _redirect_login()

    def _run():
        try:
            from batch.runner import run_batch, read_universe
            tickers = read_universe()
            run_batch(tickers, fixture_mode=False, run_synthesis=False, verbose=False)
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return RedirectResponse("/batch?msg=Batch+started+in+background", status_code=303)


# ── Override (save) ───────────────────────────────────────────────────────────

# ── Grading ───────────────────────────────────────────────────────────────────

@app.get("/grading", response_class=HTMLResponse)
async def grading_view(
    request: Request,
    caliber_session: Optional[str] = Cookie(None),
    ticker: str = "",
):
    if not _is_authed(caliber_session):
        return _redirect_login()

    grades_raw = list_grades(ticker=ticker.upper() if ticker else None, limit=200)

    # Join with evaluations to get lens + eval_id
    all_evals = {r["id"]: r for r in list_evaluations(limit=500)}
    grades = []
    for g in grades_raw:
        ev = all_evals.get(g["evaluation_id"], {})
        grades.append({**g, "lens": ev.get("lens"), "eval_id": g["evaluation_id"]})

    # Distribution
    dist = {}
    for g in grades:
        dist[g["grade"]] = dist.get(g["grade"], 0) + 1

    # Count how many ok evals with E(R) have no grade yet (pending window)
    graded_ids = {g["evaluation_id"] for g in grades_raw}
    pending_count = sum(
        1 for r in list_evaluations(limit=500)
        if r.get("status") == "ok"
        and r.get("expected_return") is not None
        and r["id"] not in graded_ids
    )

    return templates.TemplateResponse(request, "grading.html", {
        "grades": grades,
        "dist": dist,
        "pending_count": pending_count,
        "filter_ticker": ticker,
    })


@app.post("/override")
async def override_save(
    request: Request,
    caliber_session: Optional[str] = Cookie(None),
    ticker: str = Form(...),
    field_key: str = Form(...),
    override_value: str = Form(...),
    note: str = Form(""),
    redirect_to: str = Form("/batch"),
):
    if not _is_authed(caliber_session):
        return _redirect_login()

    ticker = ticker.upper().strip()
    if ticker and field_key and override_value.strip():
        save_override(ticker, field_key, override_value.strip(), note.strip())

    sep = "&" if "?" in redirect_to else "?"
    return RedirectResponse(
        f"{redirect_to}{sep}msg=Override+saved+for+{ticker}",
        status_code=303,
    )
