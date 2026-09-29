import { useEffect, useState } from "react";
import { L } from "./landing_i18n.js";
import { Arrow, Chat, Check, Compass, Mic, Phone, Pill, Shield } from "./icons.jsx";

const pref = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };
const fmtDate = (s) => (s && s.length === 8 ? `${s.slice(4, 6)}/${s.slice(6)}/${s.slice(0, 4)}` : s);

export function CheckTool({ t }) {
  const [drug, setDrug] = useState("");
  const [states, setStates] = useState([]);
  const [state, setState] = useState("Florida");
  const [counties, setCounties] = useState([]);
  const [county, setCounty] = useState("Miami-Dade");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => { fetch("/api/states").then((r) => r.json()).then(setStates).catch(() => {}); }, []);
  useEffect(() => {
    fetch(`/api/counties?state=${encodeURIComponent(state)}`).then((r) => r.json()).then((cs) => {
      setCounties(cs);
      if (!cs.includes(county)) setCounty(cs[0] || "");
    }).catch(() => {});
  }, [state]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(e) {
    e.preventDefault();
    if (!drug.trim()) return;
    setBusy(true); setErr(""); setRes(null);
    try {
      const r = await fetch(`/api/check?drug=${encodeURIComponent(drug)}&state=${encodeURIComponent(state)}&county=${encodeURIComponent(county)}`);
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "Something went wrong");
      setRes(j);
    } catch (e2) { setErr(e2.message); } finally { setBusy(false); }
  }

  const field = "w-full rounded-2xl border-2 border-field bg-card px-4 py-3 text-lg text-ink outline-none focus:border-brand";
  return (
    <form onSubmit={run} className="flex flex-col gap-4 rounded-[28px] border border-line bg-card p-7 shadow-[0_24px_60px_rgba(20,48,43,0.08)] md:p-9">
      <h2 className="text-3xl">{t.title}</h2>
      <label className="flex flex-col gap-2 text-base font-bold">{t.drug}
        <input value={drug} onChange={(e) => setDrug(e.target.value)} placeholder={t.drugPh} className={field + " font-normal"} />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-2 text-base font-bold">{t.state}
          <select value={state} onChange={(e) => setState(e.target.value)} className={field + " font-normal"}>{states.map((s) => <option key={s}>{s}</option>)}</select>
        </label>
        <label className="flex flex-col gap-2 text-base font-bold">{t.county}
          <select value={county} onChange={(e) => setCounty(e.target.value)} className={field + " font-normal"}>{counties.map((c) => <option key={c}>{c}</option>)}</select>
        </label>
      </div>
      <button disabled={busy} className="min-h-16 rounded-full bg-gold text-xl font-bold text-ink hover:brightness-95 disabled:opacity-60">{busy ? t.checking : t.go}</button>
      {err && <p className="text-base text-urgent" role="alert">{err}</p>}
      {res && (
        <div className="space-y-2 border-t border-line pt-4 text-lg" aria-live="polite">
          <p className="text-base text-muted">{t.matched}: <b className="text-ink">{res.drug}</b></p>
          <p className="text-xl font-bold">{t.result(res.covered, res.plans_total, county)}</p>
          {res.generic && <p>{t.generic(res.generic.covered, res.plans_total)}</p>}
          <a href="/app?start=choose" className="inline-flex items-center gap-2 font-bold text-brand underline">{t.next} <Arrow className="h-5 w-5" /></a>
          <p className="text-sm text-muted">{t.asOf(fmtDate(res.data_as_of))}</p>
        </div>
      )}
    </form>
  );
}

function Bubble({ who, children }) {
  const you = who === "you";
  return (
    <div className={`max-w-[90%] rounded-[22px] px-5 py-4 text-lg leading-snug ${you ? "self-end rounded-br-md bg-card border border-line" : "self-start rounded-bl-md bg-brand text-white"}`}>{children}</div>
  );
}

export default function Landing() {
  const [lang, setLang] = useState(pref("lang", "en"));
  useEffect(() => { document.documentElement.lang = lang; save("lang", lang); }, [lang]);
  const t = L[lang];
  const TrustIcons = [Shield, Check, Chat, Shield];

  return (
    <div className="min-h-dvh bg-paper text-ink">
      <header className="mx-auto flex max-w-[1248px] flex-wrap items-center justify-between gap-4 border-b border-line px-6 py-5 md:px-12">
        <a href="/" className="flex items-center gap-3 text-ink no-underline">
          <Compass className="h-9 w-9 text-brand" />
          <span className="font-display text-2xl font-[650]">{lang === "es" ? "Ayuda con Medicare" : "Medicare Helper"}</span>
        </a>
        <nav className="flex flex-wrap items-center gap-6 text-lg">
          <a href="#how" className="hidden text-brand no-underline md:inline">{t.nav.how}</a>
          <a href="#stories" className="hidden text-brand no-underline md:inline">{t.nav.families}</a>
          <a href="#faq" className="hidden text-brand no-underline md:inline">{t.nav.faq}</a>
          <button onClick={() => setLang(lang === "en" ? "es" : "en")} className="min-h-12 rounded-full border-2 border-brand px-4 font-bold text-brand">{t.nav.lang}</button>
          <a href="/app" className="min-h-12 rounded-full bg-brand px-6 py-3 font-bold text-white no-underline hover:bg-brand-dark">{t.nav.cta}</a>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-[1248px] items-center gap-12 px-6 py-14 md:grid-cols-2 md:gap-20 md:px-12 md:py-20">
          <div className="flex flex-col gap-7">
            <p className="text-base font-bold uppercase tracking-[0.08em] text-brand">{t.eyebrow}</p>
            <h1 className="text-5xl leading-[1.04] md:text-[3.4rem]">{t.h1}</h1>
            <p className="max-w-xl text-xl leading-relaxed text-muted">{t.sub}</p>
            <div className="flex flex-wrap gap-4">
              <a href="/app?start=choose" className="inline-flex min-h-16 items-center gap-3 rounded-full bg-brand px-8 text-xl font-bold text-white no-underline hover:bg-brand-dark"><Pill className="h-6 w-6" />{t.ctaChoose}</a>
              <a href="/app?start=defend" className="inline-flex min-h-16 items-center gap-3 rounded-full border-2 border-brand px-7 text-xl font-bold text-brand no-underline"><Shield className="h-6 w-6" />{t.ctaDefend}</a>
            </div>
          </div>
          <CheckTool t={t.tool} />
        </section>

        <section className="border-y border-line bg-card/60">
          <div className="mx-auto grid max-w-[1248px] gap-8 px-6 py-8 sm:grid-cols-2 md:grid-cols-4 md:px-12">
            {t.trust.map(([a, b], i) => { const I = TrustIcons[i]; return (
              <div key={a} className="flex gap-3"><I className="mt-1 h-6 w-6 shrink-0 text-brand" /><div><b className="text-lg">{a}</b><p className="text-base text-muted">{b}</p></div></div>
            ); })}
          </div>
        </section>

        <section id="how" className="mx-auto max-w-[1248px] px-6 py-20 md:px-12">
          <h2 className="text-4xl">{t.howTitle}</h2>
          <ol className="mt-10 grid gap-10 md:grid-cols-3">
            {t.steps.map(([a, b], i) => (
              <li key={a} className="flex flex-col gap-3">
                <span className="font-display text-5xl text-gold">{i + 1}</span>
                <h3 className="text-2xl">{a}</h3>
                <p className="text-lg text-muted">{b}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="stories" className="bg-brand-soft/60">
          <div className="mx-auto max-w-[1248px] px-6 py-20 md:px-12">
            <h2 className="text-4xl">{t.storiesTitle}</h2>
            <div className="mt-10 grid gap-8 md:grid-cols-2">
              {[[t.storyChoose, Pill], [t.storyDefend, Shield]].map(([s, I]) => (
                <article key={s.tag} className="flex flex-col gap-4 rounded-[28px] border border-line bg-paper p-7">
                  <p className="inline-flex items-center gap-2 text-base font-bold uppercase tracking-[0.06em] text-brand"><I className="h-5 w-5" />{s.tag}</p>
                  <div className="flex flex-col gap-3">
                    <Bubble who="you">{s.you}</Bubble>
                    <Bubble who="helper">{s.helper}</Bubble>
                  </div>
                  <p className="text-lg text-muted">{s.point}</p>
                </article>
              ))}
            </div>
            <p className="mt-6 text-base text-muted">{t.storiesNote}</p>
          </div>
        </section>

        <section className="mx-auto max-w-[1248px] px-6 py-20 md:px-12">
          <h2 className="text-4xl">{t.promiseTitle}</h2>
          <ul className="mt-10 grid gap-8 md:grid-cols-2">
            {t.promises.map(([a, b]) => (
              <li key={a} className="flex gap-4"><Check className="mt-1 h-7 w-7 shrink-0 text-brand" /><div><b className="text-xl">{a}</b><p className="text-lg text-muted">{b}</p></div></li>
            ))}
          </ul>
        </section>

        <section id="faq" className="mx-auto max-w-[1248px] px-6 pb-20 md:px-12">
          <h2 className="text-4xl">{t.faqTitle}</h2>
          <div className="mt-8 divide-y divide-line rounded-[28px] border border-line bg-card">
            {t.faq.map(([q, a]) => (
              <details key={q} className="group px-7 py-5">
                <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 text-xl font-bold">{q}<Arrow className="h-5 w-5 shrink-0 transition group-open:rotate-90" /></summary>
                <p className="mt-3 text-lg text-muted">{a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="bg-brand text-white">
          <div className="mx-auto flex max-w-[1248px] flex-col items-start gap-6 px-6 py-16 md:flex-row md:items-center md:justify-between md:px-12">
            <div><h2 className="text-4xl text-white">{t.finalTitle}</h2><p className="mt-2 text-xl text-white/85">{t.finalSub}</p></div>
            <a href="/app" className="inline-flex min-h-16 items-center gap-3 rounded-full bg-gold px-8 text-xl font-bold text-ink no-underline"><Mic className="h-6 w-6" />{t.nav.cta}</a>
          </div>
        </section>
      </main>

      <footer className="mx-auto max-w-[1248px] space-y-3 px-6 py-10 text-base text-muted md:px-12">
        <p>{t.footer}</p>
        <p>{t.built} · <span className="inline-flex items-center gap-1"><Phone className="h-4 w-4" /> 1-800-MEDICARE (1-800-633-4227)</span></p>
      </footer>
    </div>
  );
}
