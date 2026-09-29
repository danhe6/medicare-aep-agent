import { useEffect, useRef, useState } from "react";

const SR = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

/** Big push-to-talk button using the browser's built-in speech recognition. */
export default function MicButton({ lang, onText, label, listeningLabel, large = false }) {
  const [on, setOn] = useState(false);
  const rec = useRef(null);
  useEffect(() => () => rec.current?.abort(), []);
  if (!SR) return null;

  const toggle = () => {
    if (on) { rec.current?.stop(); return; }
    const r = new SR();
    r.lang = lang === "es" ? "es-US" : "en-US";
    r.interimResults = false;
    r.continuous = false;
    r.onresult = (e) => onText(Array.from(e.results).map((x) => x[0].transcript).join(" "));
    r.onend = () => setOn(false);
    r.onerror = () => setOn(false);
    rec.current = r;
    setOn(true);
    r.start();
  };

  return (
    <button onClick={toggle} aria-pressed={on}
      className={`flex items-center justify-center gap-3 rounded-full font-bold transition
        ${on ? "bg-urgent text-white listening" : "bg-brand text-white hover:bg-brand-dark"}
        ${large ? "w-full min-h-20 text-xl px-8" : "h-14 w-14 shrink-0"}`}
      aria-label={on ? listeningLabel : label}>
      <svg viewBox="0 0 24 24" className={large ? "h-8 w-8" : "h-7 w-7"} fill="currentColor" aria-hidden="true">
        <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.93V22h2v-3.07A7 7 0 0 0 19 12h-2Z" />
      </svg>
      {large && <span>{on ? listeningLabel : label}</span>}
    </button>
  );
}
