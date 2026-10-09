import { useState } from "react";
import { summarize } from "../api.js";
import { Chat, Check } from "../icons.jsx";

// Native names, so a relative can find their own language.
export const SUMMARY_LANGS = [
  ["en", "English"], ["es", "Español"], ["zh", "简体中文"], ["zh-Hant", "繁體中文"], ["vi", "Tiếng Việt"],
  ["ht", "Kreyòl ayisyen"], ["pt", "Português"], ["ru", "Русский"], ["ko", "한국어"], ["tl", "Tagalog"],
  ["fr", "Français"], ["ar", "العربية"], ["hi", "हिन्दी"], ["pl", "Polski"], ["it", "Italiano"],
  ["ja", "日本語"], ["de", "Deutsch"], ["fa", "فارسی"],
];

/** "Send a summary to family": the server writes it from this conversation's results and checks every number. */
export default function ShareSummary({ sid, lang, t }) {
  const S = t.sm;
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState(lang);
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);

  async function go() {
    setBusy(true); setErr(""); setOut(null);
    try { setOut(await summarize(sid, target, lang)); }
    catch (e) { setErr(e.detail || S.error); }
    finally { setBusy(false); }
  }
  const rtl = ["ar", "fa"].includes(target);

  if (!open) return (
    <button onClick={() => setOpen(true)} className="my-3 flex min-h-12 items-center gap-2 rounded-full border-2 border-brand bg-card px-5 text-base font-bold text-brand print:hidden">
      <Chat className="h-5 w-5" />{S.button}
    </button>
  );
  return (
    <section className="my-4 rounded-3xl border-2 border-brand bg-card p-5" aria-label={S.title}>
      <div className="text-xl font-bold">{S.title}</div>
      <p className="mt-1 text-base text-muted">{S.sub}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3 print:hidden">
        <label className="text-base font-bold" htmlFor="sum-lang">{S.langLabel}</label>
        <select id="sum-lang" value={target} onChange={(e) => { setTarget(e.target.value); setOut(null); }}
          className="min-h-12 rounded-full border-2 border-line bg-paper px-4 text-lg">
          {SUMMARY_LANGS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
        </select>
        <button onClick={go} disabled={busy} className="min-h-12 rounded-full bg-brand px-5 text-lg font-bold text-white disabled:opacity-60">
          {busy ? S.writing : out ? S.again : S.write}
        </button>
        <button onClick={() => { setOpen(false); setOut(null); }} className="text-base font-bold text-muted underline">{t.cancel}</button>
      </div>
      {busy && <p className="mt-3 animate-pulse text-base text-muted">{S.writing}</p>}
      {err && <p className="mt-3 text-base text-urgent">{err}</p>}
      {out && (
        <div className="mt-4">
          <p dir={rtl ? "rtl" : "ltr"} className="whitespace-pre-line rounded-2xl bg-paper p-4 text-lg leading-relaxed">{out.text}</p>
          <p className="mt-2 flex items-center gap-2 text-sm text-muted"><Check className="h-4 w-4 text-ok" />{out.fallback ? S.fallback : S.checked}</p>
          <div className="mt-3 flex flex-wrap gap-3 print:hidden">
            <button onClick={() => navigator.clipboard?.writeText(out.text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}
              className="min-h-12 rounded-full bg-brand px-5 font-bold text-white">{copied ? t.lt.copied : t.lt.copy}</button>
            {typeof navigator !== "undefined" && navigator.share && (
              <button onClick={() => navigator.share({ text: out.text }).catch(() => {})} className="min-h-12 rounded-full border-2 border-brand px-5 font-bold text-brand">{S.share}</button>
            )}
            <a href={`sms:?&body=${encodeURIComponent(out.text)}`} className="flex min-h-12 items-center rounded-full border-2 border-brand px-5 font-bold text-brand no-underline">{S.text}</a>
            <a href={`mailto:?subject=${encodeURIComponent(S.subject)}&body=${encodeURIComponent(out.text)}`} className="flex min-h-12 items-center rounded-full border-2 border-brand px-5 font-bold text-brand no-underline">{S.email}</a>
          </div>
        </div>
      )}
    </section>
  );
}
