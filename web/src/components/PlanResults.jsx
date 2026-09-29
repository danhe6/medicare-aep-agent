import { useState } from "react";
import { Check, Lightbulb, Star, X } from "../icons.jsx";

const money = (v) => (v == null ? "—" : `$${Math.round(v).toLocaleString()}`);
const short = (name) => name.replace(/\s*\[.*?\]\s*/g, " ").replace(/\b(\d+(\.\d+)?)\s*MG\b/gi, "$1 mg").trim();
const brandOf = (name) => (name.match(/\[(.+?)\]/) || [])[1] || short(name);

function Stars({ v }) {
  if (!v) return null;
  return (
    <span aria-label={`${v} of 5 stars`} className="mt-1 inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => <Star key={i} className={`h-5 w-5 ${i <= Math.round(v) ? "text-gold" : "text-line"}`} />)}
      <span className="ml-2 text-base text-muted">{v.toFixed(1)}</span>
    </span>);
}

function PlanCard({ p, t, rank }) {
  const [open, setOpen] = useState(false);
  const lb = p.drug_oop_is_lower_bound;
  const wg = p.with_generics;
  return (
    <article className="rounded-3xl border border-line bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-bold uppercase tracking-wide text-muted">#{rank} · {p.organization || p.type}</div>
          <h3 className="text-2xl leading-snug">{p.plan_name}</h3>
          <Stars v={p.star_overall} />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-paper p-3">
          <div className="text-base text-muted">{t.typicalYear}</div>
          <div className="text-2xl font-bold">{lb && <span className="text-base font-normal">{t.atLeast} </span>}{money(p.total)}</div>
        </div>
        <div className="rounded-2xl bg-paper p-3">
          <div className="text-base text-muted">{t.badYear}</div>
          <div className="text-2xl font-bold">{p.bad_year_total == null ? <span className="text-base">{t.noMedicalCap}</span> : money(p.bad_year_total)}</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {p.not_covered?.length === 0 && <span className="inline-flex items-center gap-1 rounded-full bg-ok-soft px-3 py-1 text-base font-bold text-ok"><Check className="h-4 w-4" />{t.allCovered}</span>}
        {p.not_covered?.map((d) => <span key={d} className="inline-flex items-center gap-1 rounded-full bg-urgent-soft px-3 py-1 text-base font-bold text-urgent"><X className="h-4 w-4" />{t.notCovered}: {brandOf(d)}</span>)}
      </div>

      {p.generic_alerts?.length > 0 && (
        <div className="mt-3 rounded-2xl bg-warn-soft p-3 text-base">
          <div className="font-bold text-warn">{t.askDoctor}</div>
          <ul className="ml-5 list-disc">{p.generic_alerts.map((a) => <li key={a}>{a.replace(/ 24 MG \/ valsartan 26 MG Oral Tablet/g, "/valsartan")}</li>)}</ul>
          {wg && <div className="mt-1 font-bold">{t.ifGeneric}: {wg.drug_oop_is_lower_bound ? t.atLeast + " " : ""}{money(wg.total)}{t.perYear}{wg.not_covered.length === 0 ? ` · ${t.allCovered}` : ""}</div>}
        </div>
      )}

      <button onClick={() => setOpen(!open)} className="mt-3 min-h-12 text-base font-bold text-brand underline">{open ? t.showLess : t.showMore}</button>
      {open && <p className="mt-2 text-base text-muted">{p.plain_summary}</p>}
    </article>
  );
}

function PlanTable({ plans, t }) {
  return (
    <div className="overflow-x-auto rounded-3xl border border-line bg-card">
      <table className="w-full min-w-[720px] border-collapse text-left text-lg">
        <thead className="bg-paper text-base text-muted">
          <tr><th className="px-5 py-4">{t.colPlan}</th><th className="px-3 py-4">{t.colTypical}</th><th className="px-3 py-4">{t.colBad}</th><th className="px-3 py-4">{t.colStars}</th><th className="px-5 py-4">{t.colCheck}</th></tr>
        </thead>
        <tbody>
          {plans.map((p, i) => {
            const pa = Object.entries(p.drug_flags || {}).filter(([, f]) => f.includes("PA")).map(([d]) => brandOf(d));
            return (
              <tr key={p.plan_key} className={`border-t border-line align-top ${i === 0 ? "bg-brand-soft/50" : ""}`}>
                <td className="px-5 py-4">{i === 0 && <span className="block text-sm font-bold text-brand">{t.bestFit}</span>}<b>{p.plan_name}</b>
                  {p.with_generics && <span className="block text-sm font-bold text-warn">{t.ifGeneric}: {money(p.with_generics.total)}</span>}</td>
                <td className="px-3 py-4 font-display text-2xl font-[650]">{p.drug_oop_is_lower_bound ? "≥ " : ""}{money(p.total)}</td>
                <td className="px-3 py-4">{p.bad_year_total == null ? t.noMedicalCap : money(p.bad_year_total)}</td>
                <td className="px-3 py-4">{p.star_overall ? p.star_overall.toFixed(1) : "—"}</td>
                <td className="px-5 py-4 text-base">
                  {p.not_covered?.length ? <span className="font-bold text-urgent">{t.notCovered}: {p.not_covered.map(brandOf).join(", ")}</span> : <span className="text-ok">{t.allCoveredShort}</span>}
                  {pa.length > 0 && <span className="block">{pa.join(", ")} {t.needsApproval}</span>}
                </td>
              </tr>);
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function PlanResults({ data, t, table = false }) {
  if (!data) return null;
  const coversAll = data.a_regular_plan_covers_every_drug_as_prescribed;
  const best = (data.best_if_doctor_approves_generics || []).filter((p) => p.with_generics && p.with_generics.not_covered.length === 0);
  return (
    <section className="my-4 space-y-4">
      <div className={`rounded-3xl p-5 text-xl font-bold ${coversAll ? "bg-ok-soft text-ok" : "bg-warn-soft text-warn"}`}>
        {coversAll ? t.keyAllCovered : t.keyNoPlan}
      </div>

      {!coversAll && best.length > 0 && (
        <>
          <h2 className="flex items-center gap-2 text-2xl"><Lightbulb className="h-7 w-7 text-gold" />{t.bestIfGeneric}</h2>
          {best.slice(0, 2).map((p, i) => <PlanCard key={"g" + p.plan_key} p={p} t={t} rank={i + 1} />)}
        </>
      )}

      <h2 className="text-2xl">{t.topPlans}</h2>
      {table ? <PlanTable plans={data.top_plans.slice(0, 5)} t={t} /> : data.top_plans.slice(0, 3).map((p, i) => <PlanCard key={p.plan_key} p={p} t={t} rank={i + 1} />)}
      {data.ranking_notes?.length > 0 && <p className="text-base text-muted">{data.ranking_notes[0]}</p>}

      {data.special_needs_plan_options?.length > 0 && (
        <details className="rounded-3xl border border-line bg-card p-5">
          <summary className="cursor-pointer text-lg font-bold">{t.snpPlans}</summary>
          <div className="mt-3 space-y-4">{data.special_needs_plan_options.map((p, i) => <PlanCard key={p.plan_key} p={p} t={t} rank={i + 1} />)}</div>
        </details>
      )}
      {data.part_b_monthly_premium && <p className="text-base text-muted">{t.partB(data.part_b_monthly_premium.toFixed(2))}</p>}
    </section>
  );
}
