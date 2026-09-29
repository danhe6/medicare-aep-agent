import { useEffect, useState } from "react";
import { S } from "./site_i18n.js";
import { L } from "../landing_i18n.js";
import { CheckTool } from "../Landing.jsx";
import { Arrow, Camera, Check, Compass, Lock, Mic, Phone } from "../icons.jsx";

const pref = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };
const wrap = "mx-auto w-full max-w-[1248px] px-5 md:px-12";

function Nav({ t, path, onLang }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-card/95 backdrop-blur">
      <div className={`${wrap} flex min-h-[76px] items-center justify-between gap-4`}>
        <a href="/" className="flex items-center gap-3 text-ink no-underline"><Compass className="h-9 w-9 text-brand" /><span className="whitespace-nowrap font-display text-2xl font-[650]">{t.brand}</span></a>
        <nav className="hidden items-center gap-7 whitespace-nowrap text-lg xl:flex" aria-label="Main">
          {t.nav.map(([href, label]) => (
            <a key={href} href={href} aria-current={path === href ? "page" : undefined}
              className={`text-ink no-underline ${path === href ? "border-b-[3px] border-gold pb-1 font-bold" : "hover:text-brand"}`}>{label}</a>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <button onClick={onLang} className="min-h-12 rounded-full border-2 border-brand px-4 font-bold text-brand">{t.lang}</button>
          <a href="/app" className="hidden min-h-12 items-center whitespace-nowrap rounded-full bg-brand px-6 font-bold text-white no-underline hover:bg-brand-dark sm:inline-flex">{t.start}</a>
          <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Menu" className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-line xl:hidden">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
          </button>
        </div>
      </div>
      {open && (
        <nav className={`${wrap} flex flex-col gap-1 pb-4 xl:hidden`} aria-label="Main">
          {t.nav.map(([href, label]) => <a key={href} href={href} className={`rounded-2xl px-4 py-3 text-xl no-underline ${path === href ? "bg-brand-soft font-bold text-ink" : "text-ink"}`}>{label}</a>)}
          <a href="/app" className="mt-2 rounded-full bg-brand px-6 py-4 text-center text-xl font-bold text-white no-underline">{t.start}</a>
        </nav>
      )}
    </header>
  );
}

function Footer({ t }) {
  return (
    <footer className="mt-24 bg-ink text-[#D5DED9]">
      <div className={`${wrap} flex flex-col gap-4 py-10 text-base md:flex-row md:justify-between`}>
        <p className="max-w-3xl">{t.footer}</p>
        <div className="space-y-2"><p className="font-display text-xl text-white">{t.brand}</p><p>{t.built}</p>
          <p className="inline-flex items-center gap-2"><Phone className="h-4 w-4" />1-800-MEDICARE (1-800-633-4227)</p></div>
      </div>
    </footer>
  );
}

function PhoneMock({ t }) {
  const p = t.phone;
  return (
    <div className="relative mx-auto flex h-[600px] w-full max-w-[460px] justify-center" aria-hidden="true">
      <div className="absolute inset-[40px_0_0_40px] rounded-[40px] bg-brand-soft" />
      <div className="relative h-[600px] w-[310px] rounded-[46px] bg-ink p-3 shadow-2xl">
        <div className="flex h-full flex-col gap-3 overflow-hidden rounded-[36px] bg-paper px-4 py-5">
          <div className="font-display text-base font-[650]">{p.title}</div>
          <div className="flex flex-col gap-1 rounded-2xl border-2 border-brand bg-card p-3">
            <span className="text-xs font-bold text-brand">{p.best}</span>
            <span className="text-base font-bold leading-tight">{p.plan}</span>
            <span className="font-display text-3xl font-[650]">{p.cost}<span className="font-sans text-sm font-normal text-muted">{p.per}</span></span>
            <span className="text-sm text-muted">{p.meta}</span>
          </div>
          <div className="rounded-2xl bg-gold-soft p-3 text-sm leading-snug">{p.tip}</div>
          {p.chips.map((c) => <span key={c} className="rounded-full border-2 border-brand px-3 py-2 text-sm font-bold text-brand">{c}</span>)}
          <div className="flex-1" />
          <div className="flex items-center gap-2"><span className="flex h-11 w-11 items-center justify-center rounded-full bg-gold"><Mic className="h-5 w-5" /></span>
            <span className="flex-1 rounded-full border-2 border-field bg-card px-3 py-2.5 text-sm text-muted">{p.ask}</span></div>
        </div>
      </div>
      <div className="absolute -left-6 top-6 hidden w-56 items-center gap-3 rounded-2xl bg-card p-3 shadow-xl xl:flex">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-soft"><Camera className="h-5 w-5 text-brand" /></span>
        <span className="text-sm leading-snug"><b>{t.floatPhoto[0]}</b><br />{t.floatPhoto[1]}</span></div>
      <div className="absolute -right-6 bottom-10 hidden w-52 items-center gap-3 rounded-2xl bg-card p-3 shadow-xl xl:flex">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-soft"><Lock className="h-5 w-5 text-brand" /></span>
        <span className="text-sm leading-snug"><b>{t.floatSaved[0]}</b><br />{t.floatSaved[1]}</span></div>
    </div>
  );
}

function Home({ t, lang }) {
  return (
    <>
      <section className={`${wrap} grid items-center gap-12 py-14 lg:grid-cols-[1.1fr_0.9fr] md:py-20`}>
        <div className="flex flex-col gap-7">
          <div className="flex flex-wrap gap-2">{t.chips.map((c) => <span key={c} className="rounded-full bg-brand-soft px-4 py-2 text-base font-bold text-brand">{c}</span>)}</div>
          <h1 className="text-5xl leading-[1.04] md:text-[4.1rem]">{t.h1[0]}<br />{t.h1[1]}</h1>
          <p className="max-w-xl text-xl leading-relaxed text-muted md:text-[1.4rem]">{t.sub}</p>
          <div className="flex flex-wrap items-center gap-5">
            <a href="/app" className="inline-flex min-h-16 items-center gap-3 rounded-full bg-brand px-8 text-xl font-bold text-white no-underline hover:bg-brand-dark"><Mic className="h-6 w-6" />{t.talk}</a>
            <a href="/features" className="text-xl font-bold">{t.seeAll}</a>
          </div>
        </div>
        <PhoneMock t={t} />
      </section>

      <Problem t={t} />
      <section className={`${wrap} pt-10`}>
        <div className="grid gap-8 rounded-[32px] bg-ink px-8 py-10 text-white sm:grid-cols-2 lg:grid-cols-4 md:px-14">
          {t.stats.map(([a, b]) => <div key={b} className="flex flex-col gap-2"><span className="font-display text-5xl font-[650] leading-none text-gold">{a}</span><span className="text-lg leading-snug">{b}</span></div>)}
        </div>
      </section>

      <section className={`${wrap} pt-24`}>
        <h2 className="text-4xl md:text-5xl">{t.whoTitle}</h2>
        <div className="mt-8 grid gap-8 md:grid-cols-2">
          {[[t.forYou, t.photoYou, "/app?mode=senior", "bg-brand-soft"], [t.forFam, t.photoFam, "/app?mode=family", "bg-gold-soft"]].map(([c, photo, href, bg]) => (
            <a key={href} href={href} className="flex flex-col gap-4 rounded-[32px] border border-line bg-card p-8 text-ink no-underline hover:border-brand">
              <div className={`flex h-48 items-center justify-center rounded-3xl p-6 text-center text-lg text-muted ${bg}`}>{photo}</div>
              <span className="font-display text-3xl font-[650]">{c[0]}</span>
              <span className="text-xl leading-relaxed text-muted">{c[1]}</span>
              <span className="text-xl font-bold text-brand">{c[2]}</span>
            </a>
          ))}
        </div>
      </section>

      <section className={`${wrap} pt-20`}>
        <div className="flex flex-wrap items-end justify-between gap-4"><h2 className="text-4xl md:text-5xl">{t.yearTitle}</h2><a href="/features" className="text-xl font-bold">{t.seeEvery}</a></div>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {t.year.map(([when, title, body, urgent]) => (
            <div key={title} className="flex flex-col gap-3 rounded-[28px] border border-line bg-card p-7">
              <span className={`text-sm font-bold tracking-[0.06em] ${urgent ? "text-urgent" : "text-brand"}`}>{when}</span>
              <span className="font-display text-2xl font-[650]">{title}</span>
              <span className="text-lg leading-relaxed text-muted">{body}</span>
            </div>
          ))}
        </div>
      </section>

      <section className={`${wrap} grid gap-10 pt-20 md:grid-cols-2 md:items-center`}>
        <div className="flex flex-col gap-4"><h2 className="text-4xl">{t.tryTitle}</h2><p className="text-xl text-muted">{t.featSub}</p></div>
        <CheckTool t={L[lang].tool} />
      </section>

      <section className={`${wrap} pt-20`}>
        <div className="grid gap-10 rounded-[32px] border border-line bg-card p-8 md:grid-cols-2 md:items-center md:p-14">
          <div className="flex flex-col gap-4"><h2 className="text-4xl">{t.privTitle}</h2><p className="text-xl leading-relaxed text-muted">{t.privSub}</p><a href="/privacy" className="text-xl font-bold">{t.privLink}</a></div>
          <ul className="flex flex-col gap-3">{t.privChecks.map((c) => <li key={c} className="flex items-center gap-3 rounded-2xl bg-paper px-5 py-4 text-lg"><Check className="h-6 w-6 shrink-0 text-ok" />{c}</li>)}</ul>
        </div>
      </section>
    </>
  );
}

function Problem({ t }) {
  const p = t.problem;
  return (
    <section className={`${wrap} pt-6`}>
      <p className="text-sm font-bold uppercase tracking-[0.1em] text-brand">{p.title}</p>
      <h2 className="mt-2 max-w-3xl text-3xl leading-tight md:text-4xl">{p.sub}</h2>
      <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {p.stats.map(([n, text, src, url]) => (
          <figure key={n} className="flex flex-col gap-2 rounded-3xl border border-line bg-card p-6">
            <span className="font-display text-5xl font-[650] leading-none text-brand">{n}</span>
            <span className="text-base leading-snug">{text}</span>
            <a href={url} target="_blank" rel="noreferrer" className="mt-auto pt-2 text-sm text-muted">{src} ↗</a>
          </figure>
        ))}
      </div>
    </section>
  );
}

function How({ t }) {
  const h = t.how;
  return (
    <>
      <header className={`${wrap} py-14 md:py-20`}><h1 className="text-5xl md:text-6xl">{h.title}</h1><p className="mt-4 max-w-3xl text-xl leading-relaxed text-muted">{h.sub}</p></header>
      <section className={wrap}>
        <h2 className="text-3xl">{h.archTitle}</h2>
        <ol className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {h.flow.map(([a, b], i) => (
            <li key={a} className={`relative flex flex-col gap-2 rounded-3xl p-6 ${i === 1 ? "bg-ink text-white" : i === 4 ? "border-2 border-dashed border-brand bg-card" : "border border-line bg-card"}`}>
              <span className={`text-sm font-bold ${i === 1 ? "text-gold" : "text-brand"}`}>{String(i + 1).padStart(2, "0")}</span>
              <b className="font-display text-xl">{a}</b>
              <span className={`text-base leading-relaxed ${i === 1 ? "text-[#D5DED9]" : "text-muted"}`}>{b}</span>
              {i < h.flow.length - 1 && <Arrow className="absolute -right-4 top-1/2 z-10 hidden h-7 w-7 -translate-y-1/2 rounded-full bg-paper text-brand xl:block" />}
            </li>
          ))}
        </ol>
      </section>
      <section className={`${wrap} pt-16`}>
        <div className="grid gap-8 rounded-[32px] bg-brand p-8 text-white md:p-12 xl:grid-cols-[1fr_1.2fr]">
          <div><h2 className="text-3xl text-white">{h.evalTitle}</h2><p className="mt-3 text-lg leading-relaxed text-white/85">{h.evalBody}</p><p className="mt-3 text-sm text-white/70">{h.evalNote}</p></div>
          <div className="grid gap-4 sm:grid-cols-3">
            {h.evalStats.map(([n, d]) => <div key={d} className="rounded-2xl bg-white/10 p-5"><span className="font-display text-4xl font-[650] text-gold">{n}</span><p className="mt-2 text-base">{d}</p></div>)}
          </div>
        </div>
      </section>
      <section className={`${wrap} pt-16`}>
        <h2 className="text-3xl">{h.stackTitle}</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {h.stack.map(([a, b]) => <div key={a} className="rounded-2xl border border-line bg-card p-5"><b className="text-lg">{a}</b><p className="text-base text-muted">{b}</p></div>)}
        </div>
      </section>
      <section className={`${wrap} pt-16`}>
        <h2 className="text-3xl">{h.roadTitle}</h2>
        <ol className="mt-6 grid gap-4 md:grid-cols-3">
          {h.road.map(([when, what], i) => (
            <li key={when} className={`rounded-3xl p-6 ${i === 0 ? "bg-brand-soft" : "border border-line bg-card"}`}>
              <span className="text-sm font-bold uppercase tracking-[0.08em] text-brand">{when}</span>
              <p className="mt-2 text-lg leading-relaxed">{what}</p>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}

function Feature({ f, children }) {
  return (
    <article className="flex flex-col gap-5 rounded-[32px] border border-line bg-card p-7 md:p-9">
      <div className="flex min-h-[230px] flex-col justify-center gap-3 rounded-3xl p-6">{children}</div>
      <h2 className="text-3xl">{f[0]}</h2>
      <p className="text-lg leading-relaxed text-muted">{f[1]}</p>
    </article>
  );
}

function Features({ t }) {
  const d = t.demo, F = t.feats;
  const bars = [["CareFree Platinum", 540, "bg-brand"], ["Freedom Máximo", 840, "bg-[#7FA89C]"], ["CareOne Plus", 900, "bg-[#7FA89C]"]];
  return (
    <>
      <header className={`${wrap} max-w-[1248px] py-14 md:py-20`}><h1 className="text-5xl md:text-6xl">{t.featTitle}</h1><p className="mt-4 max-w-3xl text-xl leading-relaxed text-muted">{t.featSub}</p></header>
      <div className={`${wrap} grid gap-8 md:grid-cols-2`}>
        <Feature f={F.snap}><div className="flex flex-wrap items-center justify-center gap-4 rounded-3xl bg-brand-soft p-5">
          <div className="flex w-40 flex-col gap-1 rounded-2xl border-2 border-dashed border-brand bg-card p-3 text-sm"><span className="text-xs font-bold text-muted">{d.label}</span><b>JARDIANCE 25 MG</b><span>TAKE 1 TABLET DAILY</span><span>QTY 90 · 90 DAYS</span></div>
          <Arrow className="h-8 w-8 text-brand" />
          <div className="flex w-44 flex-col gap-1 rounded-2xl bg-card p-3 shadow-lg"><span className="text-xs font-bold text-ok">{d.saved}</span><b className="text-lg">Jardiance 25 mg tablet</b><span className="text-sm text-muted">{d.perMonth}</span></div>
        </div></Feature>
        <Feature f={F.cost}><div className="flex flex-col gap-3 rounded-3xl bg-brand-soft p-5">
          {bars.map(([n, v, c]) => <div key={n} className="flex items-center gap-3"><span className="w-36 text-sm font-bold">{n}</span><span className={`h-6 rounded-lg ${c}`} style={{ width: `${(v / 900) * 55}%` }} /><b>${v}</b></div>)}
          <span className="text-sm text-muted">{d.sample}</span>
        </div></Feature>
        <Feature f={F.save}><div className="flex flex-col gap-2 rounded-3xl bg-gold-soft p-5">
          <span className="text-sm font-bold tracking-[0.06em] text-warn">{d.ask}</span><span className="text-xl leading-snug">{d.generic}</span>
          <span className="font-display text-3xl font-[650]">$840 → $360 <span className="font-sans text-base font-normal">{d.genericSub}</span></span>
        </div></Feature>
        <Feature f={F.whatif}><div className="flex flex-col gap-3 rounded-3xl bg-brand-soft p-5">
          <span className="max-w-xs self-end rounded-[20px] rounded-br-md bg-brand px-4 py-3 text-white">{d.q}</span>
          <span className="max-w-sm self-start rounded-[20px] rounded-bl-md bg-card px-4 py-3">{d.a}</span>
        </div></Feature>
        <Feature f={F.current}><div className="grid gap-3 rounded-3xl bg-brand-soft p-5 sm:grid-cols-2">
          <div className="flex flex-col gap-1 rounded-2xl bg-card p-4"><span className="text-xs font-bold text-muted">{d.herPlan}</span><span>{d.herPlanTxt}</span></div>
          <div className="flex flex-col gap-1 rounded-2xl border-2 border-brand bg-card p-4"><span className="text-xs font-bold text-brand">{d.better}</span><span>{d.betterTxt}</span></div>
        </div></Feature>
        <Feature f={F.appeal}><div className="flex flex-col items-center gap-1 rounded-3xl bg-urgent-soft p-5 text-center">
          <span className="font-bold text-muted">{d.before}</span><span className="font-display text-2xl font-[650]">{d.when}</span>
          <span className="font-display text-4xl font-[650] text-urgent">{d.left}</span><span className="text-sm text-muted">{d.sampleNotice}</span>
        </div></Feature>
      </div>
      <section className={`${wrap} pt-16`}><div className="flex flex-col items-start gap-6 rounded-[32px] bg-brand px-8 py-10 text-white md:flex-row md:items-center md:justify-between md:px-14">
        <span className="font-display text-4xl font-[650]">{t.ctaTitle}</span>
        <a href="/app" className="inline-flex min-h-16 items-center rounded-full bg-gold px-8 text-xl font-bold text-ink no-underline">{t.start}</a></div></section>
    </>
  );
}

function Audience({ page, href }) {
  return (
    <section className={`${wrap} py-14 md:py-20`}>
      <h1 className="max-w-4xl text-5xl leading-tight md:text-6xl">{page.title}</h1>
      <p className="mt-5 max-w-3xl text-xl leading-relaxed text-muted md:text-2xl">{page.sub}</p>
      <ul className="mt-12 grid gap-6 md:grid-cols-2">
        {page.points.map(([a, b]) => <li key={a} className="flex gap-4 rounded-[28px] border border-line bg-card p-7"><Check className="mt-1 h-7 w-7 shrink-0 text-brand" /><div><b className="text-2xl">{a}</b><p className="mt-1 text-lg text-muted">{b}</p></div></li>)}
      </ul>
      <a href={href} className="mt-12 inline-flex min-h-16 items-center gap-3 rounded-full bg-brand px-8 text-xl font-bold text-white no-underline">{page.cta}<Arrow className="h-6 w-6" /></a>
    </section>
  );
}

function Privacy({ t }) {
  return (
    <section className={`${wrap} py-14 md:py-20`}>
      <h1 className="text-5xl md:text-6xl">{t.privPage.title}</h1>
      <div className="mt-10 grid gap-6 md:grid-cols-2">
        {t.privPage.items.map(([a, b]) => <div key={a} className="flex gap-4 rounded-[28px] border border-line bg-card p-7"><Lock className="mt-1 h-7 w-7 shrink-0 text-brand" /><div><b className="text-2xl">{a}</b><p className="mt-1 text-lg text-muted">{b}</p></div></div>)}
      </div>
    </section>
  );
}

function Faq({ t, lang }) {
  return (
    <section className={`${wrap} py-14 md:py-20`}>
      <h1 className="text-5xl md:text-6xl">{t.faqTitle}</h1>
      <div className="mt-10 divide-y divide-line rounded-[28px] border border-line bg-card">
        {L[lang].faq.map(([q, a]) => (
          <details key={q} className="group px-7 py-5">
            <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 text-xl font-bold">{q}<Arrow className="h-5 w-5 shrink-0 transition group-open:rotate-90" /></summary>
            <p className="mt-3 text-lg text-muted">{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

export default function Site({ path }) {
  const [lang, setLang] = useState(pref("lang", "en"));
  useEffect(() => { document.documentElement.lang = lang; save("lang", lang); }, [lang]);
  const t = S[lang];
  const page = {
    "/features": <Features t={t} />,
    "/how": <How t={t} />,
    "/families": <Audience page={t.famPage} href="/app?mode=family" />,
    "/you": <Audience page={t.youPage} href="/app?mode=senior" />,
    "/privacy": <Privacy t={t} />,
    "/questions": <Faq t={t} lang={lang} />,
  }[path] || <Home t={t} lang={lang} />;
  return (
    <div className="flex min-h-dvh flex-col bg-paper text-ink">
      <Nav t={t} path={path} onLang={() => setLang(lang === "en" ? "es" : "en")} />
      <main className="flex-1">{page}</main>
      <Footer t={t} />
    </div>
  );
}
