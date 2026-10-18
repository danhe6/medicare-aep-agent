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
import { applyPatch, clearProfile, forMode, loadProfile, markStatus, removeMedicine, removePerson, saveProfile, setAppeal, whoIsThis } from "./profile.js";
import Dashboard from "./components/Dashboard.jsx";
import LetterCard from "./components/LetterCard.jsx";
import BillCard from "./components/BillCard.jsx";
import { isYesNoQuestion } from "./yesno.js";
import { Camera, Compass, Pill, Send, Shield, Speaker, User } from "./icons.jsx";
import NextSteps from "./components/NextSteps.jsx";
import DoctorCard from "./components/DoctorCard.jsx";
import CurrentPlanCard from "./components/CurrentPlanCard.jsx";
import ShareSummary from "./components/ShareSummary.jsx";
import QuickStart from "./components/QuickStart.jsx";

const RESULT_KINDS = ["plans", "current_plan", "doctor", "appeal", "letter", "bill"];  // results worth sending to family
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
  const [activeId, setActiveIdState] = useState(() => { try { return localStorage.getItem("mh_active") || null; } catch { return null; } });
  const activeRef = useRef(activeId);
  const setActiveId = (id) => { activeRef.current = id; setActiveIdState(id); try { localStorage.setItem("mh_active", id); } catch { /* ignore */ } };
  const [other, setOther] = useState(false);     // "Something else" on the home page shows the generic start options
  const [photoFor, setPhotoFor] = useState(null);
  // Remember what was done for whom (dates only), so the home page can show a checklist.
  const markDone = (args, key) => { const id = whoIsThis(forMode(profileRef.current, mode), args, activeRef.current); if (id) setProfile(markStatus(profileRef.current, id, key)); };
  const bottom = useRef(null);
  const fileRef = useRef(null);
  const base = STRINGS[lang];
  const t = mode === "senior" && base.senior ? { ...base, ...base.senior } : base;

  useEffect(() => { newSession().then(setSid); getMeta().then(setMeta); }, []);
  const started_ = useRef(false);
  useEffect(() => {  // arriving from the landing page with ?start=choose|defend
    const start = new URLSearchParams(window.location.search).get("start");
    if (sid && start && !started_.current) {
      started_.current = true;
      window.history.replaceState(null, "", "/app");
      if (start === "choose") setQuick(true);  // a short form beats an open question for "where + which medicines"
      else send({ defend: t.startDefend, recheck: t.startRecheck, letter: t.startLetter }[start] || t.startChoose);
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
  useEffect(() => { if (follow.current && items.length) window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" }); }, [items, busy]);

  async function send(text) {
    if (!text.trim() || !sid || busy) return;
    setInput("");
    follow.current = true;
    setBusy(true);
    const stepsKey = Date.now();
    setItems((xs) => [...xs, { kind: "user", text }, { kind: "steps", key: stepsKey, steps: [] }]);
    const updSteps = (fn) => setItems((xs) => xs.map((x) => (x.key === stepsKey ? { ...x, steps: fn(x.steps) } : x)));
    const argsById = {};
    const marks = [];  // applied at the end of the turn, after any profile save that creates the person
    const mark = (args, key) => marks.push([args, key]);
    const firstTurn = !items.some((x) => x.kind === "user");
    let useSid = sid;
    const run = (id) => chat(id, text, lang, (ev) => {
        if (ev.type === "tool_start") { argsById[ev.id] = ev.args; argsById[ev.name] = ev.args; }
        if (ev.type === "tool_done" && ev.ok && ev.name === "screen_extra_help") mark(argsById[ev.id], "extra_help_checked");
        if (ev.type === "plans") mark(argsById.compare_plans, "compared");
        if (ev.type === "current_plan") mark(argsById.check_current_plan, "current_plan_checked");
        if (ev.type === "doctor") mark(argsById.check_doctor_network, "doctor_checked");
        if (ev.type === "appeal" && ev.data?.appeal) {
          const id = whoIsThis(forMode(profileRef.current, mode), null, activeRef.current), a = ev.data.appeal;
          if (id) setProfile(setAppeal(profileRef.current, id, { deadline_at: Date.now() + a.hours_left * 3600000, deadline_local: a.deadline_local, effective_date: a.effective_date }));
        }
        if (ev.type === "tool_start") updSteps((s) => [...s, { id: ev.id, name: ev.name, args: ev.args, status: "run" }]);
        if (ev.type === "tool_done") updSteps((s) => s.map((x) => (x.id === ev.id ? { ...x, status: ev.ok ? "done" : "error" } : x)));
        if (ev.type === "plans") setItems((xs) => [...xs, { kind: "plans", data: ev.data }]);
        if (ev.type === "appeal") setItems((xs) => [...xs, { kind: "appeal", data: ev.data, at: Date.now() }]);
        if (ev.type === "current_plan") setItems((xs) => [...xs, { kind: "current_plan", data: ev.data }]);
        if (ev.type === "doctor") setItems((xs) => [...xs, { kind: "doctor", data: ev.data }]);
        if (ev.type === "label") setItems((xs) => [...xs, { kind: "label", data: ev.data }]);
        if (ev.type === "letter") setItems((xs) => [...xs, { kind: "letter", data: ev.data }]);
        if (ev.type === "bill") setItems((xs) => [...xs, { kind: "bill", data: ev.data }]);
        if (ev.type === "profile_update") {
          setProfile(applyPatch(profileRef.current, ev.patch));
          setItems((xs) => [...xs, { kind: "saved", patch: ev.patch }]);
        }
        if (ev.type === "message") { setItems((xs) => [...xs, { kind: "assistant", text: ev.text }]); if (voice) speak(ev.text, lang); }
        if (ev.type === "error") setItems((xs) => [...xs, { kind: "assistant", text: ev.text }]);
      }, forMode(profileRef.current, mode), mode);
    try {
      try {
        await run(useSid);
      } catch (e) {
        // The server restarted (sessions live in memory). On the first message nothing is lost: open a new
        // session and send the same message again, so the person never has to retype it.
        if (e.status !== 404 || !firstTurn) throw e;
        useSid = await newSession();
        setSid(useSid);
        await run(useSid);
      }
    } catch (e) {
      if (e.status === 404) {  // server restarted mid-conversation: start a fresh one
        newSession().then(setSid);
        setItems((xs) => [...xs, { kind: "assistant", text: t.sessionLost }]);
      } else if (e.status === 429 && e.detail) {  // rate limit: the server's message is already in the user's language
        setItems((xs) => [...xs, { kind: "assistant", text: e.detail }]);
      } else {
        setItems((xs) => [...xs, { kind: "assistant", text: t.netError }]);
      }
    } finally {
      for (const [args, key] of marks) markDone(args, key);
      setItems((xs) => xs.filter((x) => x.kind !== "steps" || x.steps.length > 0));
      setBusy(false);
    }
  }

  const [quick, setQuick] = useState(false);
  const photoKind = useRef(null);  // set when the person already said what the photo is (e.g. "photo a letter")
  function photoLetter() { photoKind.current = "notice"; fileRef.current?.click(); }
  function onFile(e) {
    const f = e.target.files?.[0];
    e.target.value = "";
    const kind = photoKind.current;
    photoKind.current = null;
    if (f && sid) { if (kind) uploadAs(kind, f); else setPendingFile(f); }
  }

  async function uploadAs(kind, file = null) {
    const f = file || pendingFile;
    setPendingFile(null);
    if (!f) return;
    setUploading(true);
    const who = photoFor; setPhotoFor(null);
    try { const path = await uploadFile(sid, f); await send(kind === "label" ? (who ? t.uploadedLabelFor(path, who) : t.uploadedLabelMsg(path)) : t.uploadedMsg(path)); }
    catch (err) { setItems((xs) => [...xs, { kind: "assistant", text: err.message }]); }
    finally { setUploading(false); }
  }

  const started = items.length > 0;
  function reset() { window.speechSynthesis?.cancel(); setItems([]); setOther(false); follow.current = false; window.scrollTo(0, 0); newSession().then(setSid); }
  const people = forMode(profile, mode).people || [];
  const active = people.find((p) => p.id === activeId) || people[0];
  const showDash = !started && mode && people.length > 0 && !other;

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
            <div className="text-sm font-bold tracking-[0.08em] text-[#B5CCC3]">{t.people.toUpperCase()}</div>
            {!profile.people?.length && <p className="mt-3 text-base text-[#DCE6E1]">{t.noPeople}</p>}
            <ul className="mt-3 space-y-2">
              {(profile.people || []).map((p) => (
                <li key={p.id}>
                  <button onClick={() => { setActiveId(p.id); if (started) send(t.useProfileMsg(p.name)); }} disabled={busy} className={`w-full rounded-2xl ${!started && p.id === active?.id ? "bg-brand" : "bg-white/10"} px-4 py-3 text-left hover:bg-white/20 disabled:opacity-60`}>
                    <span className="block text-lg font-bold">{/^(me|myself|i|yo|mí|mi)$/i.test(p.name.trim()) ? t.meLabel : p.name}</span>
                    <span className="text-sm text-[#DCE6E1]">{[p.county, (p.medicines || []).length + " Rx"].filter(Boolean).join(" · ")}</span>
                  </button>
                </li>
              ))}
            </ul>
            <button onClick={() => setShowProfile(true)} className="mt-4 text-base font-bold text-gold underline">{t.myInfo}</button>
          </div>
        </aside>
      )}
      <main ref={mainRef} className="min-w-0 flex-1 pt-6 pb-40">
        {!started && !mode && !quick && (
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
            <p className="text-sm text-muted">{t.disclaimer}</p>
          </div>
        )}
        {showDash && !quick && (
          <>
          <Dashboard profile={forMode(profile, mode)} activeId={active?.id} onPick={setActiveId} onSend={send} t={t} lang={lang} big={big}
            onPhoto={() => { setPhotoFor(active?.name || null); fileRef.current?.click(); }} onPhotoLetter={photoLetter}
            onAddMed={(pid, m) => { const who = profileRef.current.people.find((x) => x.id === pid); if (who) setProfile(applyPatch(profileRef.current, { person: who.name, add_medicines: [m] })); }} onOther={() => setOther(true)} />
          <p className="mx-auto mt-6 max-w-3xl text-sm text-muted">{t.disclaimer}</p></>
        )}
        {!started && quick && (
          <QuickStart t={t} lang={lang} profile={forMode(profile, mode)}
            onSubmit={({ state, county, meds }) => { setQuick(false); send(t.qs.msg(county, state, meds)); }}
            onPhoto={() => { setQuick(false); photoKind.current = "label"; fileRef.current?.click(); }}
            onTalk={() => { setQuick(false); send(t.startChoose); }} />
        )}
        {!started && !quick && mode && !showDash && (
          <div className="mx-auto max-w-2xl space-y-5">
            <h1 className="text-4xl leading-tight">{t.hello}</h1>
            <p className="text-lg text-muted">{t.tagline}</p>
            <button onClick={() => setQuick(true)} className="w-full rounded-3xl border-2 border-line bg-card p-6 text-left shadow-sm hover:border-brand">
              <div className="flex items-center gap-3 text-2xl font-bold"><Pill className="h-8 w-8 text-brand" />{t.choose}</div><div className="text-lg text-muted">{t.chooseSub}</div>
            </button>
            <button onClick={photoLetter} className="w-full rounded-3xl border-2 border-line bg-card p-6 text-left shadow-sm hover:border-brand">
              <div className="flex items-center gap-3 text-2xl font-bold"><Camera className="h-8 w-8 text-brand" />{t.letterStart}</div><div className="text-lg text-muted">{t.letterStartSub}</div>
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
          if (it.kind === "current_plan") return <CurrentPlanCard key={i} data={it.data} t={t} />;
          if (it.kind === "doctor") return <DoctorCard key={i} data={it.data} t={t} />;
          if (it.kind === "label") return <LabelCard key={i} data={it.data} t={t} />;
          if (it.kind === "letter") return <LetterCard key={i} data={it.data} t={t} onSend={busy ? null : send} />;
          if (it.kind === "bill") return <BillCard key={i} data={it.data} t={t} />;
          if (it.kind === "saved") return <SavedCard key={i} patch={it.patch} t={t} />;
          return null;
        })}
        {!busy && items.some((x) => x.kind === "plans") && items[items.length - 1]?.kind === "assistant"
          && !/\?/.test(items[items.length - 1].text.slice(-240)) && (  // the helper is waiting for an answer: no menu
          <NextSteps t={t} onPick={send} used={items.filter((x) => x.kind === "user").map((x) => x.text)} />
        )}
        {!busy && items.some((x) => RESULT_KINDS.includes(x.kind)) && items[items.length - 1]?.kind === "assistant" && (
          <ShareSummary key={sid} sid={sid} lang={lang} t={t} />
        )}
        {!busy && mode === "senior" && items[items.length - 1]?.kind === "assistant" && isYesNoQuestion(items[items.length - 1].text) && (
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

      <input ref={fileRef} type="file" accept="image/*,application/pdf" capture="environment" className="hidden" onChange={onFile} />
      {started && (
        <footer className="sticky bottom-0 -mx-4 border-t print:hidden border-line bg-paper/95 px-4 py-3 backdrop-blur">
          <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-center gap-2">
            <button type="button" onClick={() => fileRef.current?.click()} title={t.upload} aria-label={t.upload}
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border-2 border-brand text-brand"><Camera className="h-7 w-7" /></button>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={t.typeHere} aria-label={t.typeHere}
              className="min-h-14 w-full rounded-full border-2 border-line bg-card px-5 text-lg outline-none focus:border-brand" />
            <MicButton lang={lang} onText={send} label={t.talk} listeningLabel={t.listening} />
            <button type="submit" disabled={busy} aria-label={t.send} className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand text-white disabled:opacity-50"><Send className="h-6 w-6" /></button>
          </form>
          <p className="mt-1 text-center text-xs text-muted">{t.disclaimerShort}</p>
          {meta && <p className="mt-1 text-center text-sm text-muted">{t.dataAsOf(String(meta.coverage_as_of).replace(/^(\d{4})(\d{2})(\d{2})$/, "$2/$3/$1"))}</p>}
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
