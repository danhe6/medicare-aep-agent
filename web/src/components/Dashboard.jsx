import { Camera, Check, Pill, Shield, Alert, Arrow } from "../icons.jsx";
import { season, daysUntil, windows, buildIcs, downloadIcs } from "../dates.js";

/** Home page for a saved person: what we know, what's next, and one-tap actions into the chat.
 *  Everything shown here comes from the profile on this device. */
export default function Dashboard({ profile, activeId, onPick, onSend, onPhoto, onOther, t, lang, big }) {
  const people = profile.people || [];
  const p = people.find((x) => x.id === activeId) || people[0];
  if (!p) return null;
  const now = new Date();
  const s = season(now);
  const target = s.end || s.start;
  const seasonText = t.season[s.key](daysUntil(target, now), s.year);
  const locale = lang === "es" ? "es-US" : "en-US";
  const fmt = (iso) => new Date(iso + "T12:00:00").toLocaleDateString(locale, { month: "short", day: "numeric" });
  const appealLive = p.appeal?.deadline_at && p.appeal.deadline_at > Date.now();
  const st = p.status || {};
  const planYear = s.year;  // the plan year people are choosing for right now

  const todos = [
    { key: "compared", label: t.todoCompare(planYear), msg: t.msgCompare(p.name) },
    { key: "current_plan_checked", label: t.todoCurrent, msg: p.current_plan ? t.msgCurrent(p.name, p.current_plan) : t.msgTellPlan(p.name) },
    { key: "doctor_checked", label: t.todoDoctor, msg: t.msgDoctor(p.name) },
    { key: "extra_help_checked", label: t.todoExtra, msg: t.msgExtra(p.name) },
  ];

  function calendar() {
    const ev = windows(now).map((w) => { const [title, detail] = t.cal[w.key](w.year); return { title, detail, date: w.date, remind: [{ days: w.key === "aep_end" ? 7 : 1 }] }; });
    for (const x of people) {
      if (x.appeal?.deadline_at > Date.now()) {
        const [title, detail] = t.cal.appeal(x.name);
        ev.push({ title, detail, at: new Date(x.appeal.deadline_at), remind: [{ hours: 12 }, { hours: 2 }] });
      }
    }
    downloadIcs(buildIcs(ev));
  }

  const card = "rounded-3xl border border-line bg-card p-5 shadow-sm";
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      {people.length > 1 && (
        <div role="tablist" className="flex flex-wrap gap-2">
          {people.map((x) => (
            <button key={x.id} role="tab" aria-selected={x.id === p.id} onClick={() => onPick(x.id)}
              className={`min-h-12 rounded-full px-5 text-lg font-bold ${x.id === p.id ? "bg-brand text-white" : "border-2 border-line bg-card text-ink"}`}>{x.name}</button>
          ))}
        </div>
      )}
      <div>
        <h1 className="text-4xl leading-tight">{t.dashTitle(p.name)}</h1>
        <p className="mt-1 text-lg text-muted">{p.county && p.state ? `${p.county}, ${p.state}` : t.dashNoPlace}</p>
      </div>

      {appealLive ? (
        <div className="flex items-start gap-3 rounded-3xl border-2 border-urgent bg-card p-5">
          <Alert className="mt-1 h-7 w-7 shrink-0 text-urgent" />
          <div><div className="text-xl font-bold text-urgent">{t.dashAppealTitle}</div>
            <div className="text-lg">{t.dashAppealWhen(p.appeal.deadline_local || new Date(p.appeal.deadline_at).toLocaleString(locale))}</div></div>
        </div>
      ) : (
        <div className="rounded-3xl bg-gold-soft p-5">
          <div className="text-sm font-bold tracking-[0.08em] text-warn">{t.seasonLabel.toUpperCase()}</div>
          <div className="mt-1 text-xl font-bold">{seasonText}</div>
        </div>
      )}

      <div className={`grid gap-4 ${big ? "" : "md:grid-cols-2"}`}>
        <section className={card}>
          <h2 className="flex items-center gap-2 text-2xl"><Pill className="h-7 w-7 text-brand" />{t.dashMeds}</h2>
          {!(p.medicines || []).length && <p className="mt-3 text-lg text-muted">{t.dashNoMeds}</p>}
          <ul className="mt-3 space-y-2">
            {(p.medicines || []).map((m) => (
              <li key={m.rxnorm_name} className="rounded-2xl bg-paper px-4 py-2 text-lg"><b>{m.display_name || m.rxnorm_name}</b>
                <span className="text-base text-muted"> · {t.perMonth(m.qty_per_30d)}</span></li>
            ))}
          </ul>
          <button onClick={onPhoto} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-brand text-lg font-bold text-brand">
            <Camera className="h-6 w-6" />{t.dashAddPhoto}</button>
        </section>

        <section className={card}>
          <h2 className="flex items-center gap-2 text-2xl"><Shield className="h-7 w-7 text-brand" />{t.dashPlan}</h2>
          <p className={`mt-3 text-xl ${p.current_plan ? "font-bold" : "text-muted"}`}>{p.current_plan ? (p.current_plan_name ? `${p.current_plan_name} · ${p.current_plan.replace(/-000$/, "")}` : p.current_plan.replace(/-000$/, "")) : t.dashNoPlan}</p>
          <button onClick={() => onSend(p.current_plan ? t.msgCurrent(p.name, p.current_plan) : t.msgTellPlan(p.name))}
            className="mt-4 min-h-12 w-full rounded-2xl bg-brand px-4 text-lg font-bold text-white">
            {p.current_plan ? t.dashCheckNext : t.dashTellPlan}</button>
        </section>
      </div>

      <section className={card}>
        <h2 className="text-2xl">{t.dashTodo}</h2>
        <ul className="mt-3 divide-y divide-line">
          {todos.map((x) => (
            <li key={x.key} className="flex flex-wrap items-center gap-3 py-3">
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${st[x.key] ? "bg-brand text-white" : "border-2 border-line"}`}>
                {st[x.key] && <Check className="h-5 w-5" />}</span>
              <span className="min-w-0 flex-1 text-lg">{x.label}
                {st[x.key] && <span className="block text-base text-muted">{t.dashDone(fmt(st[x.key]))}</span>}</span>
              <button onClick={() => onSend(x.msg)} className="flex min-h-12 items-center gap-1 rounded-full border-2 border-brand px-4 text-base font-bold text-brand">
                {t.dashDo}<Arrow className="h-5 w-5" /></button>
            </li>
          ))}
        </ul>
      </section>

      <button onClick={calendar} className={`${card} block w-full text-left hover:border-brand`}>
        <span className="block text-xl font-bold text-brand">{t.dashCalendar}</span>
        <span className="text-base text-muted">{t.dashCalendarSub}</span>
      </button>

      <button onClick={onOther} className="text-lg font-bold text-brand underline">{t.dashStartOver}</button>
    </div>
  );
}
