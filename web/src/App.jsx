import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { STRINGS } from "./i18n.js";
import { chat, getMeta, newSession, uploadFile } from "./api.js";
import MicButton from "./components/MicButton.jsx";
import Steps from "./components/Steps.jsx";
import PlanResults from "./components/PlanResults.jsx";
import AppealCard from "./components/AppealCard.jsx";
import ProfilePanel from "./components/ProfilePanel.jsx";
import { LabelCard, SavedCard } from "./components/SavedCard.jsx";
import { applyPatch, clearProfile, loadProfile, removeMedicine, removePerson, saveProfile } from "./profile.js";
import { Camera, Compass, Pill, Send, Shield, Speaker, User } from "./icons.jsx";
import NextSteps from "./components/NextSteps.jsx";

const pref = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };

function speak(text, lang) {
  if (!("speechSynthesis" in window) || !text) return;
  const plain = text.replace(/[#*_`>|]/g, " ").replace(/\[(.*?)\]\(.*?\)/g, "$1").replace(/\s+/g, " ").slice(0, 1500);
  const u = new SpeechSynthesisUtterance(plain);
  u.lang = lang === "es" ? "es-US" : "en-US";
  u.rate = 0.92;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

export default function App() {
  const [lang, setLang] = useState(pref("lang", "en"));
  const [big, setBig] = useState(pref("big", "0") === "1");
  const [voice, setVoice] = useState(pref("voice", "1") === "1");
  const [sid, setSid] = useState(null);
  const [meta, setMeta] = useState(null);
  const [items, setItems] = useState([]);   // conversation: {kind: user|assistant|plans|appeal|steps, ...}
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [profile, setProfileState] = useState(loadProfile);
  const [showProfile, setShowProfile] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [mode, setModeState] = useState(() => {
    const q = new URLSearchParams(window.location.search).get("mode");
    return ["senior", "family"].includes(q) ? q : pref("mode", null);
  });
  function setMode(m) {
    setModeState(m);
    if (m) save("mode", m); else { try { localStorage.removeItem("mode"); } catch { /* ignore */ } }
    if (m === "senior") { setBig(true); setVoice(true); }
  }
  useEffect(() => { if (mode === "senior") { setBig(true); } }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const family = mode === "family";
  const profileRef = useRef(profile);
  const setProfile = (p) => { profileRef.current = p; saveProfile(p); setProfileState(p); };
  const bottom = useRef(null);
  const fileRef = useRef(null);
  const t = STRINGS[lang];

  useEffect(() => { newSession().then(setSid); getMeta().then(setMeta); }, []);
  const started_ = useRef(false);
  useEffect(() => {  // arriving from the landing page with ?start=choose|defend
    const start = new URLSearchParams(window.location.search).get("start");
    if (sid && start && !started_.current) {
      started_.current = true;
      window.history.replaceState(null, "", "/app");
      send(start === "defend" ? t.startDefend : t.startChoose);
    }
  }, [sid]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { document.documentElement.classList.toggle("big-text", big); save("big", big ? "1" : "0"); }, [big]);
  useEffect(() => { document.documentElement.lang = lang; save("lang", lang); }, [lang]);
  useEffect(() => { save("voice", voice ? "1" : "0"); if (!voice) window.speechSynthesis?.cancel(); }, [voice]);
  // Follow the conversation as it grows (thinking steps, cards, answers). Stop following only when the
  // person scrolls up themselves (wheel / touch / keys); start again when they return to the bottom or send.
  const follow = useRef(true);
  const hasItems = useRef(false);
  hasItems.current = items.length > 0;
  const mainRef = useRef(null);
  useEffect(() => {
    const toBottom = () => { if (follow.current && hasItems.current) window.scrollTo({ top: document.documentElement.scrollHeight }); };
    const distance = () => document.documentElement.scrollHeight - (window.innerHeight + window.scrollY);
    const userMoved = (e) => {
      if (e.type === "wheel" && e.deltaY > 0) return;               // scrolling down keeps following
      if (e.type === "keydown" && !["ArrowUp", "PageUp", "Home"].includes(e.key)) return;
      follow.current = false;
    };
    const onScroll = () => { if (distance() < 80) follow.current = true; };
    window.addEventListener("wheel", userMoved, { passive: true });
    window.addEventListener("touchmove", userMoved, { passive: true });
    window.addEventListener("keydown", userMoved);
    window.addEventListener("scroll", onScroll, { passive: true });
    const ro = new ResizeObserver(toBottom);
    if (mainRef.current) ro.observe(mainRef.current);
    return () => {
      ["wheel", "touchmove", "keydown"].forEach((t) => window.removeEventListener(t, userMoved));
      window.removeEventListener("scroll", onScroll);
      ro.disconnect();
    };
  }, []);
  useEffect(() => { if (follow.current) window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" }); }, [items, busy]);

  async function send(text) {
    if (!text.trim() || !sid || busy) return;
    setInput("");
    follow.current = true;
    setBusy(true);
    const stepsKey = Date.now();
    setItems((xs) => [...xs, { kind: "user", text }, { kind: "steps", key: stepsKey, steps: [] }]);
    const updSteps = (fn) => setItems((xs) => xs.map((x) => (x.key === stepsKey ? { ...x, steps: fn(x.steps) } : x)));
    try {
      await chat(sid, text, lang, (ev) => {
        if (ev.type === "tool_start") updSteps((s) => [...s, { id: ev.id, name: ev.name, args: ev.args, status: "run" }]);
        if (ev.type === "tool_done") updSteps((s) => s.map((x) => (x.id === ev.id ? { ...x, status: ev.ok ? "done" : "error" } : x)));
        if (ev.type === "plans") setItems((xs) => [...xs, { kind: "plans", data: ev.data }]);
        if (ev.type === "appeal") setItems((xs) => [...xs, { kind: "appeal", data: ev.data, at: Date.now() }]);
        if (ev.type === "label") setItems((xs) => [...xs, { kind: "label", data: ev.data }]);
        if (ev.type === "profile_update") {
          setProfile(applyPatch(profileRef.current, ev.patch));
          setItems((xs) => [...xs, { kind: "saved", patch: ev.patch }]);
        }
        if (ev.type === "message") { setItems((xs) => [...xs, { kind: "assistant", text: ev.text }]); if (voice) speak(ev.text, lang); }
        if (ev.type === "error") setItems((xs) => [...xs, { kind: "assistant", text: ev.text }]);
      }, profileRef.current, mode);
    } catch (e) {
      if (e.status === 404) {  // server restarted: sessions live in memory, so start a fresh one
        newSession().then(setSid);
        setItems((xs) => [...xs, { kind: "assistant", text: t.sessionLost }]);
      } else {
        setItems((xs) => [...xs, { kind: "assistant", text: t.netError }]);
      }
    } finally {
      setItems((xs) => xs.filter((x) => x.kind !== "steps" || x.steps.length > 0));
      setBusy(false);
    }
  }

  function onFile(e) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f && sid) setPendingFile(f);
  }

  async function uploadAs(kind) {
    const f = pendingFile;
    setPendingFile(null);
    if (!f) return;
    setUploading(true);
    try { const path = await uploadFile(sid, f); await send(kind === "label" ? t.uploadedLabelMsg(path) : t.uploadedMsg(path)); }
    catch (err) { setItems((xs) => [...xs, { kind: "assistant", text: err.message }]); }
    finally { setUploading(false); }
  }

  const started = items.length > 0;
  function reset() { window.speechSynthesis?.cancel(); setItems([]); newSession().then(setSid); }

  return (
    <div className={`mx-auto flex min-h-dvh flex-col px-4 ${family ? "max-w-6xl" : "max-w-2xl"}`}>
      <header className="sticky top-0 z-10 -mx-4 flex print:hidden flex-wrap items-center justify-between gap-2 border-b border-line bg-paper/95 px-4 py-3 backdrop-blur">
        <a href="/" className="flex items-center gap-2 text-ink no-underline" aria-label={t.appName}><Compass className="h-8 w-8 text-brand" /><span className="font-display text-xl font-[650]">{t.appName}</span></a>
        <div className="flex items-center gap-2">
          <button onClick={() => setLang(lang === "en" ? "es" : "en")} className="min-h-12 rounded-full border-2 border-brand px-4 text-base font-bold text-brand">
            {lang === "en" ? "Español" : "English"}
          </button>
          <button onClick={() => setBig(!big)} aria-pressed={big} title={t.bigText} className={`min-h-12 min-w-12 rounded-full border-2 border-brand px-3 text-base font-bold ${big ? "bg-brand text-white" : "text-brand"}`}>A+</button>
          <button onClick={() => setVoice(!voice)} aria-pressed={voice} title={t.voiceOn} aria-label={t.voiceOn} className={`flex min-h-12 min-w-12 items-center justify-center rounded-full border-2 border-brand px-3 ${voice ? "bg-brand text-white" : "text-brand"}`}><Speaker className="h-6 w-6" /></button>
          <button onClick={() => setShowProfile(true)} title={t.myInfo} aria-label={t.myInfo} className="relative flex min-h-12 min-w-12 items-center justify-center rounded-full border-2 border-brand px-3 text-brand">
            <User className="h-6 w-6" />
            {!!profile.people?.length && <span className="absolute -right-1 -top-1 h-4 w-4 rounded-full border-2 border-paper bg-gold" aria-hidden="true" />}
          </button>
          {mode && <button onClick={() => { reset(); setMode(null); }} title={t.switchMode} className="min-h-12 rounded-full bg-brand-soft px-4 text-base font-bold text-brand">{mode === "family" ? t.modeFamily : t.modeSenior} · {t.switchMode}</button>}
          {started && <button onClick={reset} className="min-h-12 rounded-full px-3 text-base font-bold text-brand underline">{t.home}</button>}
        </div>
      </header>

      <div className={family ? "flex-1 gap-8 md:grid md:grid-cols-[260px_1fr]" : "flex flex-1 flex-col"}>
      {family && (
        <aside className="hidden self-start pt-6 md:sticky md:top-24 md:block print:hidden">
          <div className="rounded-3xl bg-ink p-5 text-white">
            <div className="text-sm font-bold tracking-[0.08em] text-[#9FC2B7]">{t.people.toUpperCase()}</div>
            {!profile.people?.length && <p className="mt-3 text-base text-[#CFE2DC]">{t.noPeople}</p>}
            <ul className="mt-3 space-y-2">
              {(profile.people || []).map((p) => (
                <li key={p.id}>
                  <button onClick={() => send(t.useProfileMsg(p.name))} disabled={busy} className="w-full rounded-2xl bg-white/10 px-4 py-3 text-left hover:bg-white/20 disabled:opacity-60">
                    <span className="block text-lg font-bold">{p.name}</span>
                    <span className="text-sm text-[#CFE2DC]">{[p.county, (p.medicines || []).length + " Rx"].filter(Boolean).join(" · ")}</span>
                  </button>
                </li>
              ))}
            </ul>
            <button onClick={() => setShowProfile(true)} className="mt-4 text-base font-bold text-gold underline">{t.myInfo}</button>
          </div>
        </aside>
      )}
      <main ref={mainRef} className="min-w-0 flex-1 pt-6 pb-40">
        {!started && !mode && (
          <div className="mx-auto max-w-xl space-y-5">
            <h1 className="text-4xl leading-tight">{t.whoTitle}</h1>
            <p className="text-lg text-muted">{t.whoSub}</p>
            <button onClick={() => setMode("senior")} className="flex w-full items-center gap-4 rounded-3xl border-2 border-line bg-card p-6 text-left shadow-sm hover:border-brand">
              <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-brand-soft"><User className="h-9 w-9 text-brand" /></span>
              <span><span className="block text-2xl font-bold">{t.forMe}</span><span className="text-lg text-muted">{t.forMeSub}</span></span>
            </button>
            <button onClick={() => setMode("family")} className="flex w-full items-center gap-4 rounded-3xl border-2 border-line bg-card p-6 text-left shadow-sm hover:border-brand">
              <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gold-soft"><User className="h-9 w-9 text-warn" /></span>
              <span><span className="block text-2xl font-bold">{t.forOther}</span><span className="text-lg text-muted">{t.forOtherSub}</span></span>
            </button>
            <p className="rounded-2xl bg-brand-soft p-4 text-base">{t.whoPrivacy}</p>
          </div>
        )}
        {!started && mode && (
          <div className="mx-auto max-w-2xl space-y-5">
            <h1 className="text-4xl leading-tight">{t.hello}</h1>
            <p className="text-lg text-muted">{t.tagline}</p>
            <button onClick={() => send(t.startChoose)} className="w-full rounded-3xl border-2 border-line bg-card p-6 text-left shadow-sm hover:border-brand">
              <div className="flex items-center gap-3 text-2xl font-bold"><Pill className="h-8 w-8 text-brand" />{t.choose}</div><div className="text-lg text-muted">{t.chooseSub}</div>
            </button>
            <button onClick={() => send(t.startDefend)} className="w-full rounded-3xl border-2 border-line bg-card p-6 text-left shadow-sm hover:border-urgent">
              <div className="flex items-center gap-3 text-2xl font-bold"><Shield className="h-8 w-8 text-brand" />{t.defend}</div><div className="text-lg text-muted">{t.defendSub}</div>
            </button>
            <MicButton large lang={lang} onText={send} label={t.talk} listeningLabel={t.listening} />
          </div>
        )}

        {items.map((it, i) => {
          if (it.kind === "user") return <div key={i} className="my-3 ml-10 rounded-3xl rounded-br-md bg-brand px-5 py-3 text-lg text-white">{it.text}</div>;
          if (it.kind === "assistant") return <div key={i} className="md my-3 mr-6 rounded-3xl rounded-bl-md border border-line bg-card px-5 py-3 text-lg"><Markdown>{it.text}</Markdown></div>;
          if (it.kind === "steps") return <Steps key={i} steps={it.steps} t={t} />;
          if (it.kind === "plans") return <PlanResults key={i} data={it.data} t={t} table={family} />;
          if (it.kind === "appeal") return <AppealCard key={i} data={it.data} receivedAt={it.at} t={t} />;
          if (it.kind === "label") return <LabelCard key={i} data={it.data} t={t} />;
          if (it.kind === "saved") return <SavedCard key={i} patch={it.patch} t={t} />;
          return null;
        })}
        {!busy && items.some((x) => x.kind === "plans") && items[items.length - 1]?.kind === "assistant" && (
          <NextSteps t={t} onPick={send} />
        )}
        {!busy && mode === "senior" && items[items.length - 1]?.kind === "assistant" && /\?\s*$/.test(items[items.length - 1].text) && (
          <div className="my-4 grid grid-cols-2 gap-3">
            <button onClick={() => send(t.yes)} className="min-h-20 rounded-3xl bg-brand text-2xl font-bold text-white">{t.yes}</button>
            <button onClick={() => send(t.no)} className="min-h-20 rounded-3xl border-[3px] border-brand bg-card text-2xl font-bold text-brand">{t.no}</button>
          </div>
        )}
        {(busy || uploading) && <p className="my-3 animate-pulse text-lg text-muted">{uploading ? t.uploading : t.working}</p>}
        {pendingFile && (
          <div className="my-3 rounded-3xl border-2 border-brand bg-card p-5">
            <div className="text-xl font-bold">{t.photoWhat}</div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <button onClick={() => uploadAs("label")} className="flex min-h-16 items-center gap-3 rounded-2xl bg-brand px-5 text-lg font-bold text-white"><Pill className="h-7 w-7" />{t.photoLabel}</button>
              <button onClick={() => uploadAs("notice")} className="flex min-h-16 items-center gap-3 rounded-2xl border-2 border-brand px-5 text-lg font-bold text-brand"><Shield className="h-7 w-7" />{t.photoNotice}</button>
            </div>
            <button onClick={() => setPendingFile(null)} className="mt-3 text-base font-bold text-muted underline">{t.cancel}</button>
          </div>
        )}
        <div ref={bottom} />
      </main>
      </div>

      {started && (
        <footer className="sticky bottom-0 -mx-4 border-t print:hidden border-line bg-paper/95 px-4 py-3 backdrop-blur">
          <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-center gap-2">
            <button type="button" onClick={() => fileRef.current?.click()} title={t.upload} aria-label={t.upload}
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border-2 border-brand text-brand"><Camera className="h-7 w-7" /></button>
            <input ref={fileRef} type="file" accept="image/*,application/pdf" capture="environment" className="hidden" onChange={onFile} />
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={t.typeHere} aria-label={t.typeHere}
              className="min-h-14 w-full rounded-full border-2 border-line bg-card px-5 text-lg outline-none focus:border-brand" />
            <MicButton lang={lang} onText={send} label={t.talk} listeningLabel={t.listening} />
            <button type="submit" disabled={busy} aria-label={t.send} className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand text-white disabled:opacity-50"><Send className="h-6 w-6" /></button>
          </form>
          {meta && <p className="mt-2 text-center text-sm text-muted">{t.dataAsOf(meta.coverage_as_of)}</p>}
        </footer>
      )}
    {showProfile && (
        <ProfilePanel profile={profile} t={t} onClose={() => setShowProfile(false)}
          onRemoveMed={(pid, rx) => setProfile(removeMedicine(profile, pid, rx))}
          onRemovePerson={(pid) => setProfile(removePerson(profile, pid))}
          onClearAll={() => { clearProfile(); setProfile({ people: [] }); }}
          onUse={(p) => { setShowProfile(false); send(t.useProfileMsg(p.name)); }} />
      )}
    </div>
  );
}
