import { useEffect, useState } from "react";
import { Phone } from "../icons.jsx";

/** Defend mode: countdown + one-tap call + script + checklist. */
export default function AppealCard({ data, receivedAt, t }) {
  const a = data?.appeal;
  const f = data?.fields || {};
  const [now, setNow] = useState(Date.now());
  const [done, setDone] = useState({});
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(id); }, []);
  if (!a) return null;

  const deadlineMs = receivedAt + a.hours_left * 3600 * 1000;
  const left = Math.max(0, (deadlineMs - now) / 3600000);
  const missed = deadlineMs <= now;
  const urgent = !missed && left <= 24;
  const phone = (f.qio_phone || "").replace(/[^\d]/g, "");
  const tel = phone.length === 10 ? "+1" + phone : phone.length === 11 ? "+" + phone : "";
  const qio = f.qio_name || "QIO";
  const need = data.checks?.needs_user_confirmation || [];

  return (
    <section className="my-4 space-y-4">
      <div className={`rounded-3xl p-6 text-center ${missed || urgent ? "bg-urgent-soft" : "bg-card border border-line"}`}>
        <div className="text-lg font-bold text-muted">{missed ? t.missed : t.deadline}</div>
        {!missed && <div className="font-display mt-1 text-2xl">{a.deadline_local}</div>}
        {!missed && (
          <div className={`font-display mt-2 text-5xl ${urgent ? "text-urgent" : "text-warn"}`}>
            {left >= 24 ? t.daysLeft(Math.floor(left / 24), Math.floor(left % 24)) : t.hoursLeft(Math.floor(left))}
          </div>
        )}
        <div className="mt-2 text-base text-muted">{t.careEnds}: {new Date(a.effective_date + "T12:00:00").toLocaleDateString(document.documentElement.lang === "es" ? "es-US" : "en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</div>
      </div>

      {need.length > 0 && <div className="rounded-2xl border-2 border-warn bg-card p-4 text-base"><b>{t.confirm}</b> {need.map((k) => t.confirmFields[k] || k).join(", ")}</div>}

      {tel && !missed && (
        <a href={`tel:${tel}`} className="flex min-h-20 w-full items-center justify-center gap-3 rounded-full bg-brand px-6 text-xl font-bold text-white no-underline hover:bg-brand-dark">
          <Phone className="h-7 w-7" />{t.callNow(qio)} · {f.qio_phone}
        </a>
      )}

      <div className="rounded-3xl border border-line bg-card p-5">
        <h3 className="mb-2 text-xl font-bold">{missed ? t.ifMissed : t.whatToSay}</h3>
        <ol className="ml-6 list-decimal space-y-2 text-lg">{(missed ? a.if_missed : a.call_script).map((s) => <li key={s}>{s}</li>)}</ol>
      </div>

      <div className="rounded-3xl border border-line bg-card p-5">
        <h3 className="mb-2 text-xl font-bold">{t.todo}</h3>
        <ul className="space-y-3">
          {a.checklist.map((s, i) => (
            <li key={s}>
              <label className="flex cursor-pointer items-start gap-3 text-lg">
                <input type="checkbox" className="mt-1 h-7 w-7 shrink-0 accent-brand" checked={!!done[i]} onChange={() => setDone({ ...done, [i]: !done[i] })} />
                <span className={done[i] ? "text-muted line-through" : ""}>{s}</span>
              </label>
            </li>
          ))}
        </ul>
      </div>

      <details className="rounded-3xl border border-line bg-card p-5 text-lg">
        <summary className="cursor-pointer font-bold">{t.whatNext}</summary>
        <ul className="ml-6 mt-2 list-disc space-y-1">{a.what_happens_next.map((s) => <li key={s}>{s}</li>)}</ul>
        <p className="mt-3 text-base text-muted">{t.sources}: {a.sources.join(" · ")}</p>
      </details>
    </section>
  );
}
