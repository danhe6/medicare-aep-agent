import { useEffect, useState } from "react";
import DrugPicker from "./DrugPicker.jsx";
import { L } from "../landing_i18n.js";
import { Camera, Pill, X } from "../icons.jsx";

const QTY = [[30, 1], [60, 2], [90, 3], [120, 4]];  // tablets a month, per day

/** The fast start for choosing a plan: place + medicines picked from lists (no typos, no back-and-forth),
 *  then one tap. A fixed form where a form works; the agent takes over for everything after. */
export default function QuickStart({ t, lang, profile, onSubmit, onPhoto, onTalk }) {
  const Q = t.qs, tool = L[lang]?.tool || L.en.tool;
  const me = (profile?.people || [])[0] || {};  // prefill from the saved profile, if any
  const [states, setStates] = useState([]);
  const [state, setState] = useState(me.state || "");
  const [counties, setCounties] = useState([]);
  const [county, setCounty] = useState(me.county || "");
  const [meds, setMeds] = useState([]);
  const [drug, setDrug] = useState(null);
  const [qty, setQty] = useState(30);
  const [pickerKey, setPickerKey] = useState(0);
  const [err, setErr] = useState("");

  useEffect(() => { fetch("/api/states").then((r) => r.json()).then(setStates).catch(() => {}); }, []);
  useEffect(() => {
    if (!state) { setCounties([]); return; }
    fetch(`/api/counties?state=${encodeURIComponent(state)}`).then((r) => r.json()).then((cs) => {
      setCounties(cs);
      if (!cs.includes(county)) setCounty("");
    }).catch(() => {});
  }, [state]); // eslint-disable-line react-hooks/exhaustive-deps

  const pack = drug && /pen|inhaler|injector|ml|kit|patch|cream|solution|spray/i.test(drug.label || drug.rxnorm_name);
  function add() {
    if (!drug) { setErr(tool.pickFirst); return; }
    setMeds((m) => [...m.filter((x) => x.rxnorm_name !== drug.rxnorm_name), { ...drug, qty: pack ? 1 : qty }]);
    setDrug(null); setQty(30); setErr(""); setPickerKey((k) => k + 1);
  }
  function go(e) {
    e.preventDefault();
    const list = drug ? [...meds.filter((x) => x.rxnorm_name !== drug.rxnorm_name), { ...drug, qty: pack ? 1 : qty }] : meds;
    if (!state || !county) { setErr(Q.needPlace); return; }
    if (!list.length) { setErr(Q.needMed); return; }
    onSubmit({ state, county, meds: list });
  }

  const field = "w-full rounded-2xl border-2 border-field bg-card px-4 py-3 text-lg text-ink outline-none focus:border-brand";
  return (
    <form onSubmit={go} className="mx-auto flex max-w-2xl flex-col gap-5 rounded-[28px] border border-line bg-card p-6 shadow-sm md:p-8">
      <h1 className="text-3xl leading-tight md:text-4xl">{Q.title}</h1>
      <fieldset className="grid gap-3 sm:grid-cols-2">
        <legend className="mb-2 text-lg font-bold">{Q.where}</legend>
        <select aria-label={tool.state} value={state} onChange={(e) => setState(e.target.value)} className={field}>
          <option value="">{tool.state}</option>{states.map((s) => <option key={s}>{s}</option>)}</select>
        <select aria-label={tool.county} value={county} onChange={(e) => setCounty(e.target.value)} disabled={!state} className={field}>
          <option value="">{tool.county}</option>{counties.map((c) => <option key={c}>{c}</option>)}</select>
      </fieldset>

      <div className="flex flex-col gap-3">
        <div className="text-lg font-bold">{Q.meds}</div>
        {meds.length > 0 && (
          <ul className="space-y-2">
            {meds.map((m) => (
              <li key={m.rxnorm_name} className="flex items-center gap-3 rounded-2xl bg-brand-soft px-4 py-2 text-lg">
                <Pill className="h-5 w-5 shrink-0 text-brand" /><span className="flex-1"><b>{m.label}</b> · {Q.perMonth(m.qty)}</span>
                <button type="button" aria-label={Q.remove} onClick={() => setMeds((xs) => xs.filter((x) => x !== m))} className="p-1 text-muted"><X className="h-5 w-5" /></button>
              </li>
            ))}
          </ul>
        )}
        <DrugPicker key={pickerKey} t={tool} field={field} onChange={(p) => { setDrug(p); setErr(""); }} />
        {drug && !pack && (
          <div role="radiogroup" aria-label={Q.howMany} className="flex flex-wrap gap-2">
            {QTY.map(([n, perDay]) => (
              <button type="button" key={n} role="radio" aria-checked={qty === n} onClick={() => setQty(n)}
                className={`min-h-12 rounded-full px-4 text-base font-bold ${qty === n ? "bg-brand text-white" : "border-2 border-line bg-card"}`}>{Q.perDay(perDay)}</button>
            ))}
          </div>
        )}
        {drug && <button type="button" onClick={add} className="min-h-12 self-start rounded-full border-2 border-brand px-5 text-base font-bold text-brand">{Q.addAnother}</button>}
      </div>

      {err && <p className="text-base text-urgent" role="alert">{err}</p>}
      <button className="min-h-16 rounded-full bg-brand text-xl font-bold text-white">{Q.go}</button>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-base">
        <button type="button" onClick={onPhoto} className="inline-flex items-center gap-2 font-bold text-brand underline"><Camera className="h-5 w-5" />{Q.photo}</button>
        <button type="button" onClick={onTalk} className="font-bold text-brand underline">{Q.talk}</button>
      </div>
    </form>
  );
}
