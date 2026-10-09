"""Web API + static front end.

    PYTHONPATH=src uvicorn api.server:app --reload --port 8000

POST /api/session            -> {"session_id"}
POST /api/chat   (SSE)       {session_id, message, lang} -> stream of agent events (see agent.run_turn_events)
POST /api/upload (multipart) session_id + file -> {"path"}  (photo/PDF of a notice)
POST /api/summary            {session_id, lang, ui_lang} -> {text, language, checked}
GET  /api/meta               -> data release info
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.agent import SYSTEM, run_turn_events
from agent import summary
from agent.llm import client
from engine import data, datasync, rxnorm
from engine.estimate import friendly_name
from api import limits

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = ROOT / "uploads"
WEB_DIST = ROOT / "web" / "dist"
MAX_UPLOAD = 15 * 1024 * 1024

app = FastAPI(title="Medicare helper")
SESSIONS: dict[str, list[dict]] = {}   # in memory; oldest dropped past MAX_SESSIONS
MAX_SESSIONS = int(os.environ.get("MAX_SESSIONS", "3000"))
MAX_TURNS = 60  # user messages per session
LLM = None


REFRESH_HOURS = float(os.environ.get("DATA_REFRESH_HOURS", "6"))


def _refresh_loop() -> None:
    """Pick up new weekly data releases while the server keeps running (demo stays live through judging)."""
    while True:
        time.sleep(REFRESH_HOURS * 3600)
        try:
            datasync.ensure_current()
        except Exception as e:
            print("datasync:", e)


def _purge_uploads_loop() -> None:
    """Production: bills and statements are kept at most 30 minutes (so a bill can be compared with its EOB/MSN)."""
    while True:
        time.sleep(600)
        if os.environ.get("TRACE_LOG", "1") != "0":
            continue
        cutoff = time.time() - 1800
        for f in UPLOADS.glob("*/*"):
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass


@app.on_event("startup")
def startup() -> None:
    global LLM
    try:
        datasync.ensure_current()
    except Exception as e:  # keep serving local data if GitHub is unreachable
        print("datasync:", e)
    LLM = client()
    threading.Thread(target=_refresh_loop, daemon=True).start()
    threading.Thread(target=_purge_uploads_loop, daemon=True).start()


class ChatIn(BaseModel):
    session_id: str
    message: str
    lang: str = "en"
    mode: str | None = None       # "senior" | "family"
    profile: dict | None = None   # health profile held on the user's device; used for this turn, never stored


@app.post("/api/session")
def new_session(request: Request) -> dict:
    limits.check(request, "session")
    while len(SESSIONS) >= MAX_SESSIONS:
        SESSIONS.pop(next(iter(SESSIONS)))
    sid = uuid.uuid4().hex
    SESSIONS[sid] = [{"role": "system", "content": SYSTEM}]
    return {"session_id": sid}


@app.get("/api/meta")
def meta() -> dict:
    m = data.manifest()
    return {"plan_year": m["benefit_year"], "coverage_as_of": m["sources"]["monthly"]["release"],
            "prices_as_of": m["sources"]["quarterly"]["release"], "release_id": m["release_id"]}


@app.get("/api/states")
def states() -> list[str]:
    con = data.connect()
    return sorted({s for s, _ in data.counties(con)})


@app.get("/api/counties")
def counties(state: str) -> list[str]:
    con = data.connect()
    return [c for _, c in data.counties(con, state)]


@app.get("/api/drugs/suggest")
def drug_suggest(q: str, request: Request) -> list[str]:
    limits.check(request, "lookup")
    """Search-as-you-type drug names, so nobody has to spell 'atorvastatin' right."""
    return rxnorm.suggest(q[:60])


@app.get("/api/drugs/products")
def drug_products(name: str, request: Request, lang: str = "en") -> list[dict]:
    limits.check(request, "lookup", lang)
    """Strengths and forms for a chosen drug name, with plain labels ('Eliquis 5 mg tablet')."""
    import re
    items = rxnorm.products_for(name[:80])
    out = [{**x, "label": re.sub(r"\b(12|24) HR ", "", friendly_name(x["rxnorm_name"], lang))} for x in items]
    seen = {}
    for x in out:
        seen[x["label"]] = seen.get(x["label"], 0) + 1
    for x in out:  # two pens with the same strength differ only by size: say so ("3 mL")
        m = re.match(r"^(\d+(?:\.\d+)?) ML ", x["rxnorm_name"])
        if seen[x["label"]] > 1 and m:
            x["label"] += f" · {m.group(1)} mL"
    num = lambda x: float((re.search(r"\d+(?:\.\d+)?", x["label"]) or [0])[0])  # 5 mg before 10 mg
    out.sort(key=lambda x: (x["type"] != "generic", x["label"].split(" ")[0 if x["type"] == "brand" else 1].lower(), num(x)))
    return out


@app.get("/api/check")
def check(drug: str, state: str, county: str, request: Request, lang: str = "en", rxnorm_name: str | None = None) -> dict:
    """Landing-page quick check: how many regular plans in the county cover this medicine (and its generic).
    `rxnorm_name` (picked from the strength list) is used exactly; otherwise `drug` is free text."""
    limits.check(request, "lookup", lang)
    if rxnorm_name and rxnorm.exact_rxcui(rxnorm_name):
        info = rxnorm.lookup(rxnorm_name)
    else:
        matches = rxnorm.search(drug[:80], limit=1)
        if not matches:
            raise HTTPException(404, "We couldn't find that medicine. Try the name on the bottle, e.g. 'Eliquis 5 mg'.")
        info = rxnorm.lookup(matches[0]["rxnorm_name"])
    con = data.connect()
    try:
        data.load_market(con, state, county)
    except LookupError as e:
        raise HTTPException(404, str(e))
    regular = [p for p in data.plans(con) if p.snp_type is None]

    def count(concept: dict) -> int:
        ids = [concept["rxcui"], *concept.get("equivalents", [])]
        return sum(1 for p in regular if data.formulary_entry(con, p.formulary_id, ids))

    out = {"drug": friendly_name(info["name"], lang), "plans_total": len(regular), "covered": count(info), "generic": None,
           "data_as_of": data.manifest()["sources"]["monthly"]["release"]}
    g = info.get("generic")
    # Only report a generic that is actually sold here (priced under generic NDCs), not a brand listed under
    # the generic's code (e.g. apixaban before any generic launch).
    if g and g["ndcs"] and con.execute("SELECT count(*) FROM market_pricing WHERE ndc IN (SELECT unnest(?::VARCHAR[]))",
                                       [g["ndcs"]]).fetchone()[0]:
        out["generic"] = {"name": friendly_name(g["name"], lang), "covered": count(g)}
    return out


@app.post("/api/chat")
def chat(body: ChatIn, request: Request) -> StreamingResponse:
    msgs = SESSIONS.get(body.session_id)
    if msgs is None:
        raise HTTPException(404, "Unknown session")
    limits.check(request, "chat", body.lang)
    if sum(1 for m in msgs if m.get("role") == "user") >= MAX_TURNS:
        raise HTTPException(429, "This conversation is very long. Please tap Home and start a new one."
                            if body.lang != "es" else "Esta conversación es muy larga. Toque Inicio y empiece una nueva.")
    msgs.append({"role": "user", "content": body.message[:4000]})

    def stream():
        try:
            for ev in run_turn_events(msgs, LLM, lang=body.lang, profile=body.profile, mode=body.mode):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)[:300]})}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


class SummaryIn(BaseModel):
    session_id: str
    lang: str = "en"      # language to write the summary in (any code in summary.LANGS)
    ui_lang: str = "en"   # language of the app, for messages and the fallback


@app.post("/api/summary")
def family_summary(body: SummaryIn, request: Request) -> dict:
    """A short summary of this conversation's results to send to family, in any language (numbers checked)."""
    limits.check(request, "chat", body.ui_lang)
    msgs = SESSIONS.get(body.session_id)
    if msgs is None:
        raise HTTPException(404, "Unknown session")
    out = summary.write(msgs, lang=body.lang, ui_lang=body.ui_lang, llm=LLM)
    if out.get("error") == "nothing_yet":
        raise HTTPException(400, "Nothing to summarize yet." if body.ui_lang != "es" else "Todavía no hay nada que resumir.")
    return out


@app.post("/api/upload")
async def upload(request: Request, session_id: str = Form(...), file: UploadFile = File(...)) -> dict:
    limits.check(request, "upload")
    if session_id not in SESSIONS:
        raise HTTPException(404, "Unknown session")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".heic", ".webp", ".pdf"):
        raise HTTPException(400, "Please upload a photo (JPG/PNG) or PDF")
    body = await file.read()
    if len(body) > MAX_UPLOAD:
        raise HTTPException(400, "File too large (max 15 MB)")
    d = UPLOADS / session_id
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{uuid.uuid4().hex[:8]}{ext}"
    dest.write_bytes(body)
    return {"path": str(dest.relative_to(ROOT))}


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        f = WEB_DIST / full_path
        return FileResponse(f if f.is_file() else WEB_DIST / "index.html")
