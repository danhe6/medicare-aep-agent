import { Check } from "../icons.jsx";

/** Live view of what the agent is doing ("Looking up Entresto ✓"). */
export default function Steps({ steps, t }) {
  if (!steps.length) return null;
  return (
    <ol className="my-3 space-y-2 rounded-2xl border border-line bg-card p-4" aria-live="polite">
      {steps.map((s) => (
        <li key={s.id} className="flex items-center gap-3 text-base text-muted">
          <span aria-hidden="true" className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-sm font-bold
            ${s.status === "done" ? "bg-ok-soft text-ok" : s.status === "error" ? "bg-warn-soft text-warn" : "bg-brand-soft text-brand"}`}>
            {s.status === "done" ? <Check className="h-4 w-4" /> : s.status === "error" ? "!" : <span className="animate-pulse">•</span>}
          </span>
          <span>{(t.steps[s.name] || (() => t.working))(s.args || {})}</span>
        </li>
      ))}
    </ol>
  );
}
