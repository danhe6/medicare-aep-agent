"""Reminders that reach people when the app is closed (Web Push). Opt-in, one tap, no account.

What the server keeps per subscriber: the browser's push address, the language, and a few dates
(a deadline, the enrollment season). Never names, medicines, plans or letter contents: those stay on the device.
A reminder says only what is due and when; tapping it opens the app, which has the details locally.

    PYTHONPATH=src python -m api.push keys     # make VAPID keys for .env (once)

.env: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT=mailto:you@example.com
Without keys reminders are simply off and the app hides the button.

Web Push is implemented here directly (RFC 8291 message encryption, RFC 8292 VAPID) with `cryptography`, so there
is no extra push library; the payload is encrypted for that one browser, so the push service cannot read it.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import struct
import time
import sqlite3
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("PUSH_DB", ROOT / "data" / "state" / "push.db"))
ET = ZoneInfo("America/New_York")
SEND_HOUR = 9           # reminders go out from 9 am Eastern
KINDS = {"deadline", "nomnc", "enrollment", "choose"}
_lock = threading.Lock()

TEXT = {
    "en": {
        "deadline": lambda d, n: ("Appeal deadline " + ("today" if n == 0 else "tomorrow" if n == 1 else f"in {n} days"),
                                  f"The deadline is {d}. Open Medicare Helper for the steps and your drafted letter."),
        "choose": lambda d, n: ("Your plan ends " + ("today" if n == 0 else "tomorrow" if n == 1 else f"in {n} days"),
                                f"Choose a new plan by {d} so there is no gap. Tap to compare plans."),
        "nomnc": lambda d, n: ("Fast appeal: call " + ("by noon today" if n == 0 else "by noon tomorrow"),
                               "To keep care going, call the number on the notice before noon. Open Medicare Helper for the script."),
        "aep_start": lambda d, n: ("Open enrollment starts today", "Check that the plan still fits the medicines before Dec 7."),
        "aep_week": lambda d, n: ("One week left to change plans", "Open enrollment ends Dec 7."),
        "aep_last": lambda d, n: ("Last day tomorrow to change plans", "Open enrollment ends Dec 7."),
        "oep_week": lambda d, n: ("One week left to switch Medicare Advantage plans", "The Medicare Advantage switch window ends Mar 31."),
        "plan_year": lambda d, n: (f"{d} Medicare plans are in", "See if the current plan still fits. Tap to check."),
        "test": lambda d, n: ("Reminders are on", "This is how a Medicare Helper reminder looks."),
    },
    "es": {
        "deadline": lambda d, n: ("Fecha límite para apelar " + ("hoy" if n == 0 else "mañana" if n == 1 else f"en {n} días"),
                                  f"La fecha límite es {d}. Abra Ayuda con Medicare para ver los pasos y su carta."),
        "choose": lambda d, n: ("Su plan termina " + ("hoy" if n == 0 else "mañana" if n == 1 else f"en {n} días"),
                                f"Elija un plan nuevo antes del {d} para no quedarse sin cobertura. Toque para comparar."),
        "nomnc": lambda d, n: ("Apelación rápida: llame " + ("antes del mediodía de hoy" if n == 0 else "antes del mediodía de mañana"),
                               "Para que la atención continúe, llame al número del aviso antes del mediodía. Abra la app para ver el guion."),
        "aep_start": lambda d, n: ("Hoy empieza la inscripción abierta", "Revise si el plan sigue sirviendo para sus medicinas antes del 7 de dic."),
        "aep_week": lambda d, n: ("Queda una semana para cambiar de plan", "La inscripción abierta termina el 7 de dic."),
        "aep_last": lambda d, n: ("Mañana es el último día para cambiar de plan", "La inscripción abierta termina el 7 de dic."),
        "oep_week": lambda d, n: ("Queda una semana para cambiar de plan Medicare Advantage", "El periodo termina el 31 de mar."),
        "plan_year": lambda d, n: (f"Llegaron los planes de Medicare {d}", "Vea si el plan actual sigue sirviendo. Toque para revisar."),
        "test": lambda d, n: ("Recordatorios activados", "Así se ve un recordatorio de Ayuda con Medicare."),
    },
}
URL = {"choose": "/app?start=choose", "deadline": "/app", "nomnc": "/app", "plan_year": "/app?start=recheck", "test": "/app"}


def today() -> date:
    return datetime.now(ET).date()


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
      CREATE TABLE IF NOT EXISTS subs (id TEXT PRIMARY KEY, sub TEXT NOT NULL, lang TEXT, plan_year INTEGER, created TEXT);
      CREATE TABLE IF NOT EXISTS items (sub_id TEXT, kind TEXT, msg TEXT, due TEXT, send_on TEXT, sent INTEGER DEFAULT 0,
                                        UNIQUE(sub_id, msg, due, send_on));
      CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);""")
    return con


def schedule(kind: str, due: date | None, now: date | None = None) -> list[tuple[str, date, date]]:
    """(message key, due date, send date) for one reminder request. Pure: easy to test."""
    now = now or today()
    out = []
    if kind in ("deadline", "choose") and due:
        out = [(kind, due, due - timedelta(days=k)) for k in (14, 7, 2, 0)] if kind == "choose" else \
              [("deadline", due, due - timedelta(days=k)) for k in (7, 2, 0)]
    elif kind == "nomnc" and due:
        out = [("nomnc", due, due - timedelta(days=1)), ("nomnc", due, due)]
    elif kind == "enrollment":
        for y in (now.year, now.year + 1):
            out += [("aep_start", date(y, 10, 15), date(y, 10, 15)), ("aep_week", date(y, 12, 7), date(y, 11, 30)),
                    ("aep_last", date(y, 12, 7), date(y, 12, 6)), ("oep_week", date(y, 3, 31), date(y, 3, 24))]
        out = [x for x in out if x[2] <= now + timedelta(days=365)]
    return sorted({x for x in out if x[2] >= now}, key=lambda x: x[2])


def message(msg: str, due: date | str | None, lang: str, now: date | None = None) -> dict:
    now = now or today()
    lang = lang if lang in TEXT else "en"
    if isinstance(due, str):
        due = date.fromisoformat(due) if "-" in due else due
    if isinstance(due, date):
        months = (["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"] if lang == "es" else
                  ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        dtext = f"{due.day} {months[due.month - 1]} {due.year}" if lang == "es" else f"{months[due.month - 1]} {due.day}, {due.year}"
        n = (due - now).days
    else:
        dtext, n = str(due or ""), 0
    title, body = TEXT[lang][msg](dtext, n)
    return {"title": title, "body": body, "url": URL.get(msg, "/app"), "tag": f"mh-{msg}-{due}"}


def configured() -> bool:
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("VAPID_PUBLIC_KEY") and os.environ.get("VAPID_PRIVATE_KEY"))


def why_off() -> str:
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return "pip install cryptography"
    return "add VAPID keys to .env: PYTHONPATH=src python -m api.push keys"


def public_key() -> str | None:
    return os.environ.get("VAPID_PUBLIC_KEY") if configured() else None


def _valid_sub(sub: dict) -> bool:
    ep = str(sub.get("endpoint", ""))
    keys = sub.get("keys") or {}
    return ep.startswith("https://") and len(ep) < 1000 and bool(keys.get("p256dh")) and bool(keys.get("auth"))


def save(sub: dict, items: list[dict], lang: str = "en", plan_year: bool = False, sub_id: str | None = None) -> dict:
    """Add reminders for this browser. Returns {id, dates}: the days reminders will arrive."""
    if not _valid_sub(sub):
        raise ValueError("bad subscription")
    lang = lang if lang in TEXT else "en"
    rows = []
    for it in items[:10]:
        kind = it.get("kind")
        if kind not in KINDS:
            continue
        due = None
        if it.get("date"):
            due = date.fromisoformat(str(it["date"])[:10])
            if not (today() - timedelta(days=1) <= due <= today() + timedelta(days=400)):
                continue
        rows += schedule(kind, due)
    with _lock, _db() as con:
        row = con.execute("SELECT id FROM subs WHERE sub = ?", (json.dumps(sub, sort_keys=True),)).fetchone()
        sid = (row[0] if row else None) or (sub_id if sub_id and con.execute("SELECT 1 FROM subs WHERE id=?", (sub_id,)).fetchone() else None) \
            or secrets.token_urlsafe(16)
        con.execute("INSERT INTO subs (id, sub, lang, plan_year, created) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET sub=excluded.sub, lang=excluded.lang, plan_year=MAX(plan_year, excluded.plan_year)",
                    (sid, json.dumps(sub, sort_keys=True), lang, int(plan_year), today().isoformat()))
        con.executemany("INSERT OR IGNORE INTO items (sub_id, kind, msg, due, send_on) VALUES (?,?,?,?,?)",
                        [(sid, m.split("_")[0], m, d.isoformat(), s.isoformat()) for m, d, s in rows])
        dates = [r[0] for r in con.execute("SELECT DISTINCT send_on FROM items WHERE sub_id=? AND sent=0 ORDER BY send_on", (sid,))]
    return {"id": sid, "dates": dates, "plan_year": bool(plan_year)}


def delete(sub_id: str) -> None:
    with _lock, _db() as con:
        con.execute("DELETE FROM items WHERE sub_id=?", (sub_id,))
        con.execute("DELETE FROM subs WHERE id=?", (sub_id,))


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _hkdf(salt: bytes, ikm: bytes, info: bytes, n: int) -> bytes:
    from cryptography.hazmat.primitives import hashes, hmac
    h = hmac.HMAC(salt, hashes.SHA256()); h.update(ikm); prk = h.finalize()          # extract
    h = hmac.HMAC(prk, hashes.SHA256()); h.update(info + b"\x01")                   # expand (one block is enough)
    return h.finalize()[:n]


def encrypt(payload: bytes, p256dh: str, auth: str, salt: bytes | None = None, private_key=None) -> bytes:
    """RFC 8291 (aes128gcm): one record, readable only by the browser that owns p256dh/auth."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    ua_pub = _b64d(p256dh)
    as_key = private_key or ec.generate_private_key(ec.SECP256R1())
    as_pub = as_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    secret = as_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = _hkdf(_b64d(auth), secret, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    body = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + struct.pack("!IB", 4096, len(as_pub)) + as_pub + body


def _vapid(endpoint: str) -> str:
    """RFC 8292: a short signed token so the push service knows this server sent it."""
    from urllib.parse import urlsplit
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    u = urlsplit(endpoint)
    claims = {"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600,
              "sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")}
    signing = _b64e(json.dumps({"typ": "JWT", "alg": "ES256"}).encode()) + "." + _b64e(json.dumps(claims).encode())
    key = serialization.load_der_private_key(_b64d(os.environ["VAPID_PRIVATE_KEY"]), None)
    r, s_ = decode_dss_signature(key.sign(signing.encode(), ec.ECDSA(hashes.SHA256())))
    return f"vapid t={signing}.{_b64e(r.to_bytes(32, 'big') + s_.to_bytes(32, 'big'))}, k={os.environ['VAPID_PUBLIC_KEY']}"


def _send(sub_json: str, payload: dict) -> str:
    """'ok' | 'gone' (unsubscribed: delete) | 'error'."""
    import httpx
    try:
        sub = json.loads(sub_json)
        body = encrypt(json.dumps(payload).encode(), sub["keys"]["p256dh"], sub["keys"]["auth"])
        r = httpx.post(sub["endpoint"], content=body, timeout=15, headers={
            "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": str(24 * 3600),
            "Urgency": "high", "Authorization": _vapid(sub["endpoint"])})
        if r.status_code in (404, 410):
            return "gone"
        return "ok" if r.status_code < 300 else "error"
    except Exception:  # noqa: BLE001 - one bad address must not stop the others
        return "error"


def send_test(sub_id: str) -> str:
    with _db() as con:
        row = con.execute("SELECT sub, lang FROM subs WHERE id=?", (sub_id,)).fetchone()
    if not row:
        return "gone"
    return _send(row[0], message("test", None, row[1]))


def send_due(now: datetime | None = None) -> int:
    """Send every reminder whose day has come (after SEND_HOUR Eastern). Returns how many went out."""
    if not configured():
        return 0
    now = now or datetime.now(ET)
    if now.hour < SEND_HOUR:
        return 0
    sent = 0
    with _lock, _db() as con:
        due = con.execute("SELECT i.rowid, i.sub_id, i.msg, i.due, i.send_on, s.sub, s.lang FROM items i JOIN subs s ON s.id=i.sub_id "
                          "WHERE i.sent=0 AND i.send_on <= ?", (now.date().isoformat(),)).fetchall()
        for rowid, sid, msg, d, send_on, sub, lang in due:
            if date.fromisoformat(send_on) < now.date() - timedelta(days=1) or date.fromisoformat(d) < now.date():
                # missed while the server was down: skip rather than send a stale "one week left"
                con.execute("UPDATE items SET sent=2 WHERE rowid=?", (rowid,))
                continue
            r = _send(sub, message(msg, d, lang, now.date()))
            if r == "gone":
                con.execute("DELETE FROM items WHERE sub_id=?", (sid,))
                con.execute("DELETE FROM subs WHERE id=?", (sid,))
                continue
            con.execute("UPDATE items SET sent=? WHERE rowid=?", (1 if r == "ok" else 2, rowid))
            sent += r == "ok"
        # forget browsers with nothing left to send and no plan-year alert
        con.execute("DELETE FROM subs WHERE plan_year=0 AND id NOT IN (SELECT sub_id FROM items WHERE sent=0)")
        con.execute("DELETE FROM items WHERE sub_id NOT IN (SELECT id FROM subs)")
    return sent


def plan_year_changed(year: int) -> int:
    """Called after a data refresh. The first time a new plan year appears, tell everyone who asked."""
    if not configured():
        return 0
    with _lock, _db() as con:
        row = con.execute("SELECT v FROM kv WHERE k='plan_year'").fetchone()
        con.execute("INSERT INTO kv (k, v) VALUES ('plan_year', ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (str(year),))
        if row is None or int(row[0]) >= year:
            return 0
        subs = con.execute("SELECT id, sub, lang FROM subs WHERE plan_year=1").fetchall()
    n = 0
    for sid, sub, lang in subs:
        r = _send(sub, message("plan_year", str(year), lang))
        if r == "gone":
            delete(sid)
        n += r == "ok"
    return n


def _keys() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    b64 = _b64e
    pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    priv = k.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    print(f"VAPID_PUBLIC_KEY={b64(pub)}\nVAPID_PRIVATE_KEY={b64(priv)}\nVAPID_SUBJECT=mailto:you@example.com")


if __name__ == "__main__":
    if sys.argv[1:] == ["keys"]:
        _keys()
