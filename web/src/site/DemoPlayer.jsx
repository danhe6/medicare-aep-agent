import { useEffect, useRef, useState } from "react";
import { Calendar, Camera, Chat, Check, Lightbulb, Lock, Mail, Receipt, Shield, Star, Stethoscope } from "../icons.jsx";

const ICON = { compare: Star, label: Camera, current: Check, doctor: Stethoscope, extra: Lightbulb, defend: Shield, dates: Calendar, letter: Mail, bill: Receipt, family: Chat };

/** Home-page demo: every feature in one auto-playing window. Sample data only; numbers match real engine runs
 *  (Orange County FL compare = Plan Finder #1; Humana Gold Plus check; sample notice, denial letter, bill + EOB). */
const P = {
  en: {
    label: "TEN THINGS IT DOES · SAMPLE DATA", chooseLabel: "CHOOSING A PLAN, STEP BY STEP · SAMPLE DATA", play: "Play all", pause: "Pause",
    foot: "Every number comes from Medicare's public data and a rules engine, never from the AI. Bracketed items are examples.",
    scenes: [
      { key: "compare", short: "Compare plans", title: "Compare every plan", line: "Ranked for the medicines you take", tag: "COMPARE PLANS",
        say: "I take Eliquis 5 mg twice a day and atorvastatin 40 mg at night. I live in Orlando.", think: "Checking every plan in Orange County against both medicines…" },
      { key: "label", short: "Pill bottle", photo: true, title: "Read a pill bottle", line: "Snap a photo instead of typing", tag: "PHOTO OF A LABEL",
        say: "Here is my new prescription.", think: "Reading the label…" },
      { key: "current", short: "Your plan", title: "Check your current plan", line: "Stay or switch, with a verdict first", tag: "YOUR PLAN, NEXT YEAR",
        say: "I have Humana Gold Plus. Should I stay with it next year?", think: "Looking up next year's costs and the insurer's track record…" },
      { key: "doctor", short: "Doctor", title: "Find your doctor", line: "Is the doctor in the plan's network?", tag: "DOCTOR CHECK",
        say: "Is my doctor in network for this plan?", think: "Searching the national registry and insurer directories…" },
      { key: "extra", short: "Extra Help", title: "Get help paying", line: "A private Extra Help check", tag: "EXTRA HELP",
        say: "Could I get help paying for my medicines?", think: "A few private questions, nothing saved…" },
      { key: "letter", short: "Letters", photo: true, title: "Understand any letter", line: "A denial becomes a deadline and a draft appeal", tag: "MEDICARE LETTER",
        say: "My drug plan sent me this letter. What does it mean?", think: "Reading the letter and the appeal rules…" },
      { key: "bill", short: "Bills", photo: true, title: "Check a bill", line: "Compared line by line with your plan's statement", tag: "BILL VS. EOB",
        say: "Should I pay this bill? Here's the statement from my plan too.", think: "Comparing every line on the bill with the plan's statement…" },
      { key: "defend", short: "Appeal", photo: true, title: "Fight a care cutoff", line: "A notice becomes a deadline and a script", tag: "CARE-ENDING NOTICE",
        say: "The rehab center gave us this notice.", think: "Reading the notice and the appeal rules…" },
      { key: "dates", short: "Dates", title: "Never miss a date", line: "Enrollment deadlines in your calendar", tag: "CALENDAR",
        say: "Remind me of the deadlines.", think: "Making a calendar file…" },
      { key: "family", short: "Family", title: "Keep family in the loop", line: "A short summary in their language", tag: "SUMMARY FOR FAMILY",
        say: "Send a summary to my sister, in Chinese.", think: "Writing it, then checking every number against the results…" },
    ],
    r: {
      bestFit: "BEST FIT FOR THESE MEDICINES · ORANGE COUNTY, FL", typical: "Typical year", bad: "Bad year, at most", stars: "Stars",
      sameAsPF: "Same #1 and same numbers as Medicare's Plan Finder.",
      labelTag: "READ FROM THE LABEL · MATCHED IN THE NATIONAL DRUG LIST", labelDose: "1 a day · 30 a month", savedDevice: "Saved on this device only",
      goodFit: "Your current plan is a good fit for next year.", premium27: "2027 premium", max27: "2027 out-of-pocket max",
      track: "Track record: this insurer dropped or restricted 5.5% of drugs last year (typical 4.2%). None of yours.",
      docTag: "NATIONAL PROVIDER REGISTRY + INSURER DIRECTORIES", docName: "[Doctor name], [specialty]", docListed: "Listed in [insurer]'s [year] provider directory",
      docLead: "A lead, not a promise: call the office to confirm before you switch.",
      ehTag: "EXTRA HELP CHECK · NOTHING IS SAVED", ehTitle: "You may qualify for Extra Help", ehBody: "Lower drug copays, and it's free to apply through Social Security.",
      ehCost: "Your drugs with Extra Help: [estimated $ a year]",
      apTag: "APPEAL DEADLINE · SAMPLE NOTICE", apWhen: "Thursday, Oct 8, 12:00 noon", apCall: "Call Acentra Health, 1-888-317-0751",
      apSay: "Say: \"I want a fast-track appeal of a Notice of Medicare Non-Coverage.\" Care continues while they review.",
      ltTag: "DRUG COVERAGE DENIED · SAMPLE LETTER", ltWhen: "Appeal by Dec 6, 2026", ltWhat: "Ozempic 1 mg pen · 65 days from the letter's date",
      ltDraft: "Drafted for you: the appeal letter and a request for the doctor. You add the medical details.",
      blTag: "BILL CHECK · SAMPLE BILL AND EOB", blOver: "The bill asks for $60 more than you owe", blRow: "X-ray, knee", blBilled: "Bill asks", blOwe: "You owe",
      blNext: "Pay the $55 that matches. A call script for the $60 is ready.",
      fmTag: "简体中文 · ONE OF 18 LANGUAGES", fmText: "账单要 $115.00，按保险公司的说明只该付 $55.00，X 光多收了 $60.00。下一步：先付 $55.00，再打电话要求更正。",
      fmCheck: "Every number checked against the results before it's shown.",
      calTag: "ADDED TO YOUR CALENDAR, WITH REMINDERS",
      cal: [["Oct 15", "Open Enrollment starts"], ["Dec 7", "Last day to change"], ["Jan 1", "New plan starts"], ["Mar 31", "Advantage switch window ends"]],
    },
  },
  es: {
    label: "DIEZ COSAS QUE HACE · DATOS DE EJEMPLO", chooseLabel: "ELEGIR UN PLAN, PASO A PASO · DATOS DE EJEMPLO", play: "Ver todo", pause: "Pausa",
    foot: "Cada número viene de los datos públicos de Medicare y de un motor de reglas, nunca de la IA. Lo que está entre corchetes es un ejemplo.",
    scenes: [
      { key: "compare", short: "Comparar", title: "Compare todos los planes", line: "Ordenados según sus medicinas", tag: "COMPARAR PLANES",
        say: "Tomo Eliquis 5 mg dos veces al día y atorvastatina 40 mg en la noche. Vivo en Orlando.", think: "Revisando cada plan del condado Orange con ambas medicinas…" },
      { key: "label", short: "Frasco", photo: true, title: "Lea un frasco de pastillas", line: "Tome una foto en vez de escribir", tag: "FOTO DE UNA ETIQUETA",
        say: "Esta es mi nueva receta.", think: "Leyendo la etiqueta…" },
      { key: "current", short: "Su plan", title: "Revise su plan actual", line: "Quedarse o cambiar, con una respuesta clara", tag: "SU PLAN, EL PRÓXIMO AÑO",
        say: "Tengo Humana Gold Plus. ¿Me conviene quedarme el próximo año?", think: "Buscando los costos del próximo año y el historial de la aseguradora…" },
      { key: "doctor", short: "Médico", title: "Encuentre a su médico", line: "¿Está su médico en la red del plan?", tag: "REVISAR MÉDICO",
        say: "¿Está mi médico en la red de este plan?", think: "Buscando en el registro nacional y los directorios de las aseguradoras…" },
      { key: "extra", short: "Ayuda Adicional", title: "Ayuda para pagar", line: "Una revisión privada de Ayuda Adicional", tag: "AYUDA ADICIONAL",
        say: "¿Podría recibir ayuda para pagar mis medicinas?", think: "Unas preguntas privadas, nada se guarda…" },
      { key: "letter", short: "Cartas", photo: true, title: "Entienda cualquier carta", line: "Una negación se vuelve una fecha límite y una apelación en borrador", tag: "CARTA DE MEDICARE",
        say: "Mi plan de medicinas me mandó esta carta. ¿Qué significa?", think: "Leyendo la carta y las reglas de apelación…" },
      { key: "bill", short: "Facturas", photo: true, title: "Revise una factura", line: "Comparada línea por línea con el resumen de su plan", tag: "FACTURA VS. EOB",
        say: "¿Debo pagar esta factura? Aquí está también el resumen de mi plan.", think: "Comparando cada línea de la factura con el resumen del plan…" },
      { key: "defend", short: "Apelar", photo: true, title: "Defienda su atención", line: "Un aviso se vuelve una fecha límite y un guion", tag: "AVISO DE FIN DE ATENCIÓN",
        say: "El centro de rehabilitación nos dio este aviso.", think: "Leyendo el aviso y las reglas de apelación…" },
      { key: "dates", short: "Fechas", title: "No pierda ninguna fecha", line: "Fechas de inscripción en su calendario", tag: "CALENDARIO",
        say: "Recuérdeme las fechas límite.", think: "Creando un archivo de calendario…" },
      { key: "family", short: "Familia", title: "Mantenga informada a la familia", line: "Un resumen corto en su idioma", tag: "RESUMEN PARA LA FAMILIA",
        say: "Mande un resumen a mi hermana, en chino.", think: "Escribiéndolo y revisando cada número contra los resultados…" },
    ],
    r: {
      bestFit: "LA MEJOR OPCIÓN PARA ESTAS MEDICINAS · CONDADO ORANGE, FL", typical: "Año típico", bad: "Año difícil, máximo", stars: "Estrellas",
      sameAsPF: "El mismo #1 y los mismos números que el Buscador de Planes de Medicare.",
      labelTag: "LEÍDO DE LA ETIQUETA · ENCONTRADO EN LA LISTA NACIONAL DE MEDICINAS", labelDose: "1 al día · 30 al mes", savedDevice: "Guardado solo en este dispositivo",
      goodFit: "Su plan actual le conviene para el próximo año.", premium27: "Prima 2027", max27: "Gasto máximo 2027",
      track: "Historial: esta aseguradora quitó o restringió el 5.5% de las medicinas el año pasado (lo típico: 4.2%). Ninguna de las suyas.",
      docTag: "REGISTRO NACIONAL DE PROVEEDORES + DIRECTORIOS", docName: "[Nombre del médico], [especialidad]", docListed: "Aparece en el directorio [año] de [aseguradora]",
      docLead: "Es una pista, no una garantía: llame al consultorio para confirmar antes de cambiar.",
      ehTag: "AYUDA ADICIONAL · NADA SE GUARDA", ehTitle: "Podría calificar para Ayuda Adicional", ehBody: "Copagos más bajos en medicinas, y solicitarla en el Seguro Social es gratis.",
      ehCost: "Sus medicinas con Ayuda Adicional: [$ estimado al año]",
      apTag: "FECHA LÍMITE PARA APELAR · AVISO DE EJEMPLO", apWhen: "Jueves 8 de oct, 12:00 del mediodía", apCall: "Llame a Acentra Health, 1-888-317-0751",
      apSay: "Diga: \"Quiero una apelación rápida de un Aviso de No Cobertura de Medicare.\" La atención continúa mientras revisan.",
      ltTag: "COBERTURA DE MEDICINA NEGADA · CARTA DE EJEMPLO", ltWhen: "Apele antes del 6 dic 2026", ltWhat: "Ozempic 1 mg pluma · 65 días desde la fecha de la carta",
      ltDraft: "Borradores listos: la carta de apelación y una solicitud para el médico. Usted agrega los detalles médicos.",
      blTag: "REVISIÓN DE FACTURA · FACTURA Y EOB DE EJEMPLO", blOver: "La factura pide $60 más de lo que debe", blRow: "Radiografía, rodilla", blBilled: "Factura pide", blOwe: "Usted debe",
      blNext: "Pague los $55 que coinciden. Hay un guion listo para llamar por los $60.",
      fmTag: "简体中文 · UNO DE 18 IDIOMAS", fmText: "账单要 $115.00，按保险公司的说明只该付 $55.00，X 光多收了 $60.00。下一步：先付 $55.00，再打电话要求更正。",
      fmCheck: "Cada número se revisa contra los resultados antes de mostrarse.",
      calTag: "AGREGADO A SU CALENDARIO, CON RECORDATORIOS",
      cal: [["15 oct", "Empieza la Inscripción Abierta"], ["7 dic", "Último día para cambiar"], ["1 ene", "Empieza el nuevo plan"], ["31 mar", "Termina el cambio de Advantage"]],
    },
  },
};

const SCENE_MS = 5200, THINK_MS = 1100;
const Big = ({ k, v }) => <div className="flex flex-col"><span className="text-sm text-muted">{k}</span><span className="font-display text-4xl font-[650]">{v}</span></div>;
const Tag = ({ children, cls = "text-muted" }) => <span className={`font-mono text-xs tracking-[0.06em] ${cls}`}>{children}</span>;

function Result({ k, r }) {
  const box = "flex flex-col gap-2.5 rounded-3xl border border-line p-6 md:p-7";
  if (k === "compare") return (
    <div className={`${box} border-2 border-brand`}>
      <Tag cls="text-brand">{r.bestFit}</Tag>
      <span className="font-display text-3xl font-[650]">DrSelect-CFL (HMO)</span>
      <div className="flex flex-wrap gap-x-10 gap-y-2"><Big k={r.typical} v="$0" /><Big k={r.bad} v="$3,500" /><Big k={r.stars} v="4.5" /></div>
      <span className="font-bold text-brand">{r.sameAsPF}</span>
    </div>);
  if (k === "label") return (
    <div className={box}>
      <Tag>{r.labelTag}</Tag>
      <span className="font-display text-3xl font-[650]">Jardiance 25 mg tablet</span>
      <span className="text-xl">{r.labelDose}</span>
      <span className="inline-flex items-center gap-2 self-start rounded-full bg-brand-soft px-4 py-2 text-sm font-bold text-brand"><Lock className="h-4 w-4" />{r.savedDevice}</span>
    </div>);
  if (k === "current") return (
    <div className={box}>
      <span className="text-xl font-bold text-brand">{r.goodFit}</span>
      <span className="text-muted">Humana Gold Plus H1036-054C (HMO) · Miami-Dade, FL</span>
      <div className="flex flex-wrap gap-x-10 gap-y-2"><Big k={r.premium27} v="$0" /><Big k={r.max27} v="$500" /></div>
      <span className="text-muted">{r.track}</span>
    </div>);
  if (k === "doctor") return (
    <div className={box}>
      <Tag>{r.docTag}</Tag>
      <span className="font-display text-3xl font-[650]">{r.docName}</span>
      <span className="text-lg">{r.docListed}</span>
      <span className="font-bold text-warn">{r.docLead}</span>
    </div>);
  if (k === "extra") return (
    <div className={box}>
      <Tag>{r.ehTag}</Tag>
      <span className="font-display text-3xl font-[650]">{r.ehTitle}</span>
      <span className="text-lg">{r.ehBody}</span>
      <span className="text-muted">{r.ehCost}</span>
    </div>);
  if (k === "defend") return (
    <div className={`${box} border-2 border-warn`}>
      <Tag cls="text-warn">{r.apTag}</Tag>
      <span className="font-display text-3xl font-[650]">{r.apWhen}</span>
      <span className="text-lg">{r.apCall}</span>
      <span className="text-muted">{r.apSay}</span>
    </div>);
  if (k === "letter") return (
    <div className={`${box} border-2 border-warn`}>
      <Tag cls="text-warn">{r.ltTag}</Tag>
      <span className="font-display text-3xl font-[650]">{r.ltWhen}</span>
      <span className="text-lg">{r.ltWhat}</span>
      <span className="text-muted">{r.ltDraft}</span>
    </div>);
  if (k === "bill") return (
    <div className={`${box} bg-warn-soft`}>
      <Tag cls="text-warn">{r.blTag}</Tag>
      <span className="font-display text-3xl font-[650]">{r.blOver}</span>
      <div className="flex flex-wrap items-baseline gap-x-8 gap-y-1 text-lg"><span>{r.blRow}</span><span>{r.blBilled} <b>$75.00</b></span><span>{r.blOwe} <b>$15.00</b></span></div>
      <span className="font-bold text-brand">{r.blNext}</span>
    </div>);
  if (k === "family") return (
    <div className={box}>
      <Tag>{r.fmTag}</Tag>
      <p lang="zh-Hans" className="rounded-2xl bg-paper p-4 text-xl leading-relaxed">{r.fmText}</p>
      <span className="inline-flex items-center gap-2 text-muted"><Check className="h-4 w-4 text-ok" />{r.fmCheck}</span>
    </div>);
  return (
    <div className={box}>
      <Tag>{r.calTag}</Tag>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {r.cal.map(([d, what], i) => <div key={d} className={`flex flex-col gap-1 rounded-2xl p-4 ${i === 1 ? "bg-gold-soft" : "bg-paper"}`}><span className="font-display text-2xl font-[650]">{d}</span><span className="text-sm text-muted">{what}</span></div>)}
      </div>
    </div>);
}

export default function DemoPlayer({ lang, compact = false, only = null }) {
  const base = P[lang] || P.en;
  const p = only ? { ...base, label: base.chooseLabel, scenes: only.map((k) => base.scenes.find((x) => x.key === k)).filter(Boolean) } : base;
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(!reduced);
  const [shown, setShown] = useState(false);
  const timers = useRef([]);
  useEffect(() => {
    timers.current.forEach(clearTimeout);
    setShown(false);
    timers.current = [setTimeout(() => setShown(true), reduced ? 0 : THINK_MS)];
    if (playing) timers.current.push(setTimeout(() => setI((x) => (x + 1) % p.scenes.length), SCENE_MS));
    return () => timers.current.forEach(clearTimeout);
  }, [i, playing, p.scenes.length, reduced]);
  const s = p.scenes[i];
  const bar = (
    <span key={`${i}-${playing}`} className="block h-full bg-gold" style={{ width: playing ? undefined : "100%", animation: playing ? `mhfill ${SCENE_MS}ms linear forwards` : "none" }} />
  );
  const windowEl = (
    <div className={`flex flex-col gap-5 rounded-[28px] bg-card p-6 shadow-[0_1px_0_var(--color-line),0_24px_60px_-30px_rgba(47,58,53,0.25)] md:p-8 ${compact ? "min-h-[440px]" : "min-h-[460px] md:p-9"}`} aria-live="polite">
      <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-line" /><span className="h-2.5 w-2.5 rounded-full bg-line" /><span className="h-2.5 w-2.5 rounded-full bg-line" />
        <span className="ml-3 font-mono text-xs text-muted">{s.tag}</span>
        <button onClick={() => setPlaying(!playing)} className="ml-auto min-h-9 rounded-full border border-line px-3 text-xs font-bold text-muted hover:border-ink hover:text-ink">{playing ? p.pause : p.play}</button></div>
      <div key={`say-${i}`} className="mh-rise flex justify-end">
        <span className="flex max-w-[560px] items-center gap-3 rounded-[22px] rounded-br-md bg-brand px-5 py-4 text-lg leading-snug text-white">
          {s.photo && <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/90"><Camera className="h-6 w-6 text-brand" /></span>}
          {s.say}
        </span>
      </div>
      {!shown && <span key={`t-${i}`} className="mh-rise text-muted">{s.think}</span>}
      {shown && <div key={`r-${i}`} className="mh-rise"><Result k={s.key} r={p.r} /></div>}
    </div>
  );
  if (compact) return (
    <div id="demo" className="flex min-w-0 flex-col gap-4">
      {windowEl}
      <div role="tablist" aria-label={p.label} className={`grid gap-2 ${p.scenes.length === 6 ? "grid-cols-3 sm:grid-cols-6" : "grid-cols-5"}`}>
        {p.scenes.map((x, n) => {
          const Icon = ICON[x.key];
          return (
            <button key={x.key} role="tab" aria-selected={n === i} title={x.title} onClick={() => { setI(n); setPlaying(false); }}
              className={`relative flex min-h-[76px] flex-col items-center justify-center gap-1.5 overflow-hidden rounded-2xl px-1 py-2 text-center text-[13px] font-bold leading-tight transition-colors ${n === i ? "bg-ink text-white" : "bg-card text-ink hover:bg-brand-soft"}`}>
              <Icon className={`h-5 w-5 ${n === i ? "text-gold" : "text-brand"}`} />
              {x.short}
              {n === i && <span className="absolute inset-x-3 bottom-1.5 h-[2px] overflow-hidden rounded bg-white/25">{bar}</span>}
            </button>
          );
        })}
      </div>
      <p className="text-sm text-muted">{p.foot}</p>
    </div>
  );
  return (
    <section id="demo" className="mx-auto w-full max-w-[1440px] px-5 md:px-12">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="font-mono text-xs tracking-[0.06em] text-muted">{p.label}</span>
      </div>
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <div role="tablist" aria-label={p.label} aria-orientation="vertical" className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible">
          {p.scenes.map((x, n) => (
            <button key={x.key} role="tab" aria-selected={n === i} onClick={() => { setI(n); setPlaying(false); }}
              className={`flex min-w-[220px] flex-col gap-1 rounded-2xl px-4 py-3 text-left transition-colors lg:min-w-0 ${n === i ? "bg-ink text-white" : "hover:bg-brand-soft"}`}>
              <span className="flex items-baseline justify-between gap-3"><span className="text-lg font-bold">{x.title}</span><span className="font-mono text-xs opacity-60">0{n + 1}</span></span>
              <span className="text-sm opacity-80">{x.line}</span>
              {n === i && <span className="mt-1 block h-[3px] overflow-hidden rounded bg-white/25">{bar}</span>}
            </button>
          ))}
        </div>
        {windowEl}
      </div>
      <p className="mt-3 text-sm text-muted">{p.foot}</p>
    </section>
  );
}
