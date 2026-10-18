import RemindButton from "./RemindButton.jsx";
import { useState } from "react";
import { Alert, Check } from "../icons.jsx";

/** Any Medicare letter: what it is, the deadline, the steps, and drafted letters to copy or print. */
function Draft({ title, hint, text, t }) {
  const [copied, setCopied] = useState(false);
  if (!text) return null;
  const print = () => {
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(`<pre style="font:16px/1.5 Georgia,serif;white-space:pre-wrap;margin:48px">${text.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</pre>`);
    w.document.close(); w.print();
  };
  return (
    <details className="rounded-3xl border border-line bg-card p-5" open={title === t.lt.letter}>
      <summary className="cursor-pointer text-lg font-bold">{title}</summary>
      {hint && <p className="mt-2 text-base text-muted">{hint}</p>}
      <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-2xl bg-paper p-4 font-sans text-base leading-relaxed">{text}</pre>
      <div className="mt-3 flex gap-2">
        <button onClick={() => navigator.clipboard?.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}
          className="min-h-12 rounded-full bg-brand px-5 font-bold text-white">{copied ? t.lt.copied : t.lt.copy}</button>
        <button onClick={print} className="min-h-12 rounded-full border-2 border-brand px-5 font-bold text-brand">{t.lt.print}</button>
      </div>
    </details>
  );
}

export default function LetterCard({ data, t, onSend }) {
  if (!data) return null;
  const L = t.lt, f = data.fields || {}, dl = data.deadline;
  const facts = ["item", "items_denied", "denial_reason", "plan_name", "plan_id", "notice_date", "premium_year", "tax_year_used"]
    .filter((k) => f[k] && (!Array.isArray(f[k]) || f[k].length))
    .map((k) => [L.facts[k], Array.isArray(f[k]) ? f[k].join("; ") : k === "notice_date" ? new Date(f[k] + "T12:00:00").toLocaleDateString(document.documentElement.lang === "es" ? "es-US" : "en-US", { month: "long", day: "numeric", year: "numeric" }) : f[k]]);
  const need = data.needs_user_confirmation || [];
  const missed = dl && dl.days_left < 0;
  return (
    <section className="my-4 space-y-4">
      <div className="rounded-3xl border border-line bg-card p-6">
        <div className="text-sm font-bold uppercase tracking-[0.06em] text-muted">{data.title}</div>
        {facts.length > 0 && (
          <dl className="mt-3 grid gap-x-6 gap-y-1 text-base sm:grid-cols-[auto_1fr]">
            {facts.map(([k, v]) => [<dt key={k + "k"} className="text-muted">{k}</dt>, <dd key={k + "v"} className="font-bold">{v}</dd>])}
          </dl>
        )}
      </div>

      {dl && (
        <div className={`rounded-3xl p-6 text-center ${missed || dl.status === "urgent" ? "bg-warn-soft" : "border border-line bg-card"}`}>
          <div className="text-lg font-bold text-muted">{missed ? L.missed : data.deadline_label || L.deadline}</div>
          <div className="font-display mt-1 text-2xl">{dl.date_text}</div>
          {!missed && <div className={`font-display mt-2 text-5xl ${dl.status === "urgent" ? "text-warn" : "text-brand"}`}>{L.daysLeft(dl.days_left)}</div>}
          {missed && <p className="mt-2 text-base">{data.missed_hint || L.missedHint}</p>}
          {!missed && dl.date && <RemindButton items={[{ kind: data.reminder_kind || "deadline", date: dl.date }]} lang={document.documentElement.lang} t={t} className="mt-4" />}
        </div>
      )}
      {data.needs_date && <div className="rounded-2xl border-2 border-warn bg-card p-4 text-base"><Alert className="mr-2 inline h-5 w-5 text-warn" />{data.needs_date}</div>}
      {need.length > 0 && <div className="rounded-2xl border-2 border-warn bg-card p-4 text-base"><b>{t.confirm}</b> {need.map((k) => t.confirmFields[k] || k).join(", ")}</div>}

      {data.steps?.length > 0 && (
        <div className="rounded-3xl border border-line bg-card p-6">
          <div className="text-lg font-bold">{L.steps}</div>
          <ol className="mt-3 space-y-3">
            {data.steps.map((s, i) => <li key={i} className="flex gap-3 text-lg"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft font-bold text-brand">{i + 1}</span><span>{s}</span></li>)}
          </ol>
          {data.decision_time && <p className="mt-4 text-base text-muted"><b>{L.decision}:</b> {data.decision_time}</p>}
          {data.offer_compare && onSend && (
            <button onClick={() => onSend(t.startChoose)} className="mt-4 min-h-12 rounded-full bg-brand px-5 text-lg font-bold text-white">{t.choose}</button>
          )}
        </div>
      )}

      <Draft title={L.letter} hint={L.letterHint} text={data.appeal_letter} t={t} />
      <Draft title={L.doctor} text={data.doctor_request} t={t} />
      {data.appeal_letter && <p className="flex items-center gap-2 text-sm text-muted"><Check className="h-4 w-4 text-ok" />{L.checked}</p>}
      {data.sources?.length > 0 && <p className="text-sm text-muted">{L.sources}: {data.sources.map((u) => <a key={u} href={u} target="_blank" rel="noreferrer" className="mr-2 underline">{new URL(u).hostname}</a>)}</p>}
    </section>
  );
}
