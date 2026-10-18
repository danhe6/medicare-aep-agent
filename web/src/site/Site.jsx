import { useEffect, useState } from "react";
import { S } from "./site_i18n.js";
import { L } from "../landing_i18n.js";
import { CheckTool } from "../Landing.jsx";
import DemoPlayer from "./DemoPlayer.jsx";
import { Arrow, Check, Compass, Lock, Mic, Phone, Pill } from "../icons.jsx";

const pref = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };
const wrap = "mx-auto w-full max-w-[1560px] px-5 md:px-12 xl:px-20";

function Nav({ t, path, onLang }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-card/95 backdrop-blur">
      <div className={`${wrap} flex min-h-[68px] items-center justify-between gap-2 sm:min-h-[76px] sm:gap-4`}>
        <a href="/" className="flex items-center gap-3 text-ink no-underline"><Compass className="h-8 w-8 shrink-0 text-brand sm:h-9 sm:w-9" /><span className="whitespace-nowrap font-display text-xl font-[650] sm:text-2xl">{t.brand}</span></a>
        <nav className="hidden items-center gap-7 whitespace-nowrap text-lg xl:flex" aria-label="Main">
          {t.nav.map(([href, label]) => (
            <a key={href} href={href} aria-current={path === href ? "page" : undefined}
              className={`text-ink no-underline ${path === href ? "border-b-[3px] border-gold pb-1 font-bold" : "hover:text-brand"}`}>{label}</a>
          ))}
        </nav>
        <div className="flex items-center gap-2 sm:gap-3">
          <button onClick={onLang} className="min-h-11 rounded-full border-2 border-brand px-3 text-sm font-bold text-brand sm:min-h-12 sm:px-4 sm:text-base">{t.lang}</button>
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
    <footer className="mt-24 bg-ink text-[#DCE3DF]">
      <div className={`${wrap} flex flex-col gap-4 py-10 text-base md:flex-row md:justify-between`}>
        <p className="max-w-3xl">{t.footer}</p>
        <div className="space-y-2"><p className="font-display text-xl text-white">{t.brand}</p><p>{t.built}</p>
          <p className="inline-flex items-center gap-2"><Phone className="h-4 w-4" />1-800-MEDICARE (1-800-633-4227)</p></div>
      </div>
    </footer>
  );
}

function Home({ t, lang }) {
  return (
    <>
      <section className={`${wrap} grid items-center gap-10 py-12 md:py-16 lg:grid-cols-2 xl:gap-16`}>
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap gap-2">{t.chips.map((c) => <span key={c} className="rounded-full bg-gold-soft px-4 py-1.5 text-sm font-bold tracking-[0.04em] text-warn">{c}</span>)}</div>
          <h1 className="text-5xl leading-[1.04] md:text-[3rem] 2xl:text-[3.5rem]" style={{ textWrap: "balance" }}>{t.h1[0]}<br /><span className="text-brand">{t.h1[1]}</span></h1>
          <p className="max-w-xl text-xl leading-relaxed text-muted">{t.sub}</p>
          <div className="flex flex-wrap gap-3">
            <a href="/app?start=choose" className="inline-flex min-h-14 items-center gap-3 rounded-full bg-brand px-7 text-lg font-bold text-white no-underline hover:bg-brand-dark"><Pill className="h-5 w-5" />{t.compareCta}</a>
            <a href="/features" className="inline-flex min-h-14 items-center rounded-full border-2 border-ink px-7 text-lg font-bold text-ink no-underline">{t.seeAll}</a>
          </div>
        </div>
        <DemoPlayer lang={lang} compact only={["compare", "label", "doctor", "extra", "family", "dates"]} />
      </section>

      <section className={`${wrap} pt-16`}>
        <div className="rounded-[32px] border border-line bg-card p-8 md:p-12">
          <h2 className="text-3xl md:text-4xl">{t.letterTitle}</h2>
          <p className="mt-2 text-xl text-muted">{t.letterSub}</p>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {t.letterCards.map(([a, b, start]) => (
              <a key={a} href={`/app?start=${start}`} className="flex flex-col gap-2 rounded-3xl bg-paper p-6 text-ink no-underline hover:bg-brand-soft">
                <span className="text-xl font-bold">{a}</span><span className="text-lg text-muted">{b}</span>
              </a>
            ))}
          </div>
        </div>
      </section>

      <div className="pt-20"><Problem t={t} /></div>
      <section className={`${wrap} pt-10`}>
        <div className="grid gap-8 rounded-[32px] bg-brand-soft px-8 py-10 sm:grid-cols-2 lg:grid-cols-4 md:px-14">
          {t.stats.map(([a, b]) => <div key={b} className="flex flex-col gap-2"><span className="font-display text-5xl font-[650] leading-none text-brand">{a}</span><span className="text-lg leading-snug">{b}</span></div>)}
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
              <span className={`text-base leading-relaxed ${i === 1 ? "text-[#DCE3DF]" : "text-muted"}`}>{b}</span>
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
  const bars = [["CareFree Platinum", 540, "bg-brand"], ["Freedom Máximo", 840, "bg-[#9DBBB0]"], ["CareOne Plus", 900, "bg-[#9DBBB0]"]];
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
        <Feature f={F.letter}><div className="flex flex-col gap-1 rounded-3xl bg-gold-soft p-5">
          <span className="text-sm font-bold tracking-[0.06em] text-warn">{d.ltTag}</span><span className="font-display text-3xl font-[650]">{d.ltWhen}</span>
          <span className="text-sm text-muted">{d.ltDays}</span>
        </div></Feature>
        <Feature f={F.bill}><div className="flex flex-col gap-1 rounded-3xl bg-warn-soft p-5">
          <span className="font-display text-4xl font-[650] text-warn">{d.blOver}</span><span className="text-lg">{d.blLine}</span>
        </div></Feature>
        <Feature f={F.family}><div className="flex flex-col gap-2 rounded-3xl bg-brand-soft p-5">
          <span lang="zh-Hans" className="max-w-sm self-end rounded-[20px] rounded-br-md bg-brand px-4 py-3 text-white">账单多收了 $60.00。先付 $55.00，再打电话要求更正。</span>
          <span className="text-sm text-muted">{d.fmLang}</span>
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
