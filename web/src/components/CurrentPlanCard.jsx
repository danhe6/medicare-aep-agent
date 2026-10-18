import { Check, X } from "../icons.jsx";

const money = (v) => (v == null ? "—" : `$${Math.round(v).toLocaleString()}`);
const delta = (v) => (v == null || v === 0 ? null : `${v > 0 ? "+" : "−"}$${Math.abs(Math.round(v)).toLocaleString()}`);

/** Her current plan: this year, next year's published changes, track record, and the best alternative. */
export default function CurrentPlanCard({ data, t }) {
  const c = data.current_plan, n = data.next_year || {}, rec = data.track_record, alt = data.best_alternative;
  const save = data.typical_year_savings_if_switching;
  const worth = save != null && save > 100;
  const atLeast = c.drug_oop_is_lower_bound;
  return (
    <section className="my-4 space-y-3">
      <div className={`rounded-3xl p-5 text-xl font-bold ${worth ? "bg-warn-soft text-warn" : "bg-ok-soft text-ok"}`}>
        {worth ? t.cpWorthSwitching(money(save), atLeast) : t.cpStay}
      </div>
      <article className="rounded-3xl border border-line bg-card p-5">
        <div className="text-sm font-bold uppercase tracking-wide text-muted">{t.cpHerPlan}</div>
        <h3 className="text-2xl">{c.plan_name}</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl bg-paper p-3"><div className="text-base text-muted">{t.typicalYear}</div><div className="text-2xl font-bold">{atLeast ? "≥ " : ""}{money(c.total)}</div></div>
          <div className="rounded-2xl bg-paper p-3"><div className="text-base text-muted">{t.cpNextPremium(n.year)}</div>
            <div className="text-2xl font-bold">{n.published === false ? "—" : `${money(n.premium)}/mo`}</div>
            {delta(n.premium_change) && <div className="text-base font-bold text-warn">{delta(n.premium_change)}</div>}</div>
          <div className="rounded-2xl bg-paper p-3"><div className="text-base text-muted">{t.cpNextMoop(n.year)}</div>
            <div className="text-2xl font-bold">{n.published === false ? "—" : money(n.moop)}</div>
            {delta(n.moop_change) && <div className={`text-base font-bold ${n.moop_change > 0 ? "text-warn" : "text-ok"}`}>{delta(n.moop_change)}</div>}</div>
        </div>
        {n.published === false && <p className="mt-3 rounded-2xl bg-urgent-soft p-3 text-base font-bold text-urgent">{t.cpNotContinuing}</p>}
        {rec && (
          <p className="mt-3 text-base">
            {rec.her_drugs_affected?.length
              ? <span className="inline-flex items-center gap-1 font-bold text-urgent"><X className="h-4 w-4" />{t.cpDropped(rec.her_drugs_affected.map((h) => h.drug).join(", "))}</span>
              : <span className="inline-flex items-center gap-1 text-ok"><Check className="h-4 w-4" />{t.cpRecordOk(rec.pct_drugs_made_worse, rec.national_median_pct)}</span>}
          </p>
        )}
        {data.plan_news?.found_exit_news && (
          <div className="mt-3 rounded-2xl border-2 border-warn bg-card p-3">
            <div className="text-base font-bold text-warn">{t.cpNews(data.plan_news.insurer, data.plan_news.year)}</div>
            <ul className="mt-2 space-y-1 text-base">
              {data.plan_news.articles.map((a) => (
                <li key={a.url}><a href={a.url} target="_blank" rel="noreferrer" className="font-bold">{a.title}</a>
                  <span className="text-muted"> · {a.site}{a.published ? ` · ${String(a.published).slice(0, 16)}` : ""}</span></li>
              ))}
            </ul>
            <p className="mt-2 text-sm text-muted">{t.cpNewsNote}</p>
          </div>
        )}
      </article>
      {alt && worth && (
        <article className="rounded-3xl border-2 border-brand bg-card p-5">
          <div className="text-sm font-bold uppercase tracking-wide text-brand">{t.cpBetter}</div>
          <h3 className="text-2xl">{alt.plan_name}</h3>
          <p className="mt-1 text-lg">{t.typicalYear}: <b>{money(alt.total)}</b> · {t.badYear}: <b>{money(alt.bad_year_total)}</b></p>
        </article>
      )}
      <p className="text-sm text-muted">{t.cpNote}</p>
    </section>
  );
}
