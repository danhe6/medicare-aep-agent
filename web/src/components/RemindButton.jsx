import { useEffect, useState } from "react";
import { pushState, pushSupport, remind, sendTest, serverKey, stopReminders } from "../push.js";
import { Bell, Check } from "../icons.jsx";

/** One tap: "Remind me" before a deadline or for the enrollment season. Hidden when the server has reminders off. */
export default function RemindButton({ items, planYear = false, lang, t, className = "" }) {
  const R = t.rm;
  const [on, setOn] = useState(null);       // server key present?
  const [state, setState] = useState(pushState());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [tested, setTested] = useState(false);
  useEffect(() => { serverKey().then((k) => setOn(!!k)); }, []);
  if (!on) return null;
  const support = pushSupport();
  const fmt = (d) => new Date(d + "T12:00:00").toLocaleDateString(lang === "es" ? "es-US" : "en-US", { month: "short", day: "numeric" });
  const mine = state?.dates?.length ? state.dates.slice(0, 4).map(fmt).join(" · ") : "";
  const ask = JSON.stringify(items);
  const done = !!state?.asked?.includes(ask);   // this exact reminder was already set on this device

  async function go() {
    setBusy(true); setErr("");
    try {
      const out = await remind(items, { planYear, lang });
      const next = { ...out, asked: [...(state?.asked || []), ask] };
      try { localStorage.setItem("mh_push", JSON.stringify(next)); } catch { /* ignore */ }
      setState(next);
    } catch (e) {
      setErr(e.message === "denied" ? R.denied : R.failed);
    } finally { setBusy(false); }
  }

  if (support === "ios-install") return <p className={`rounded-2xl bg-paper p-4 text-base ${className}`}><Bell className="mr-2 inline h-5 w-5 text-brand" />{R.ios}</p>;
  if (support !== "ok") return null;
  return (
    <div className={`print:hidden ${className}`}>
      {done ? (
        <div className="flex flex-wrap items-center gap-3 text-base">
          <span className="inline-flex items-center gap-2 font-bold text-brand"><Check className="h-5 w-5" />{R.on}</span>
          {mine && <span className="text-muted">{R.next(mine)}</span>}
          <button onClick={() => sendTest().then(() => setTested(true))} className="font-bold text-brand underline">{tested ? R.tested : R.test}</button>
          <button onClick={() => stopReminders().then(() => setState(null))} className="font-bold text-muted underline">{R.off}</button>
        </div>
      ) : (
        <button onClick={go} disabled={busy} className="inline-flex min-h-12 items-center gap-2 rounded-full border-2 border-brand bg-card px-5 text-base font-bold text-brand disabled:opacity-60">
          <Bell className="h-5 w-5" />{busy ? R.working : R.button}
        </button>
      )}
      {err && <p className="mt-2 text-base text-warn">{err}</p>}
      {!done && <p className="mt-2 text-sm text-muted">{R.privacy}</p>}
    </div>
  );
}
