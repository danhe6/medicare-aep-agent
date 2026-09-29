import { Lock, Pill, X } from "../icons.jsx";

/** "Saved on this device" panel: what the helper remembers, with delete controls. */
export default function ProfilePanel({ profile, onRemoveMed, onRemovePerson, onClearAll, onClose, onUse, t }) {
  const people = profile.people || [];
  return (
    <div role="dialog" aria-modal="true" aria-label={t.profileTitle}
      className="fixed inset-0 z-30 flex items-end justify-center bg-ink/40 sm:items-center" onClick={onClose}>
      <div className="max-h-[90dvh] w-full max-w-xl overflow-y-auto rounded-t-3xl bg-paper p-6 sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-3xl">{t.profileTitle}</h2>
          <button onClick={onClose} aria-label={t.close} className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-line"><X className="h-6 w-6" /></button>
        </div>
        <p className="mt-2 flex items-start gap-2 text-base text-muted"><Lock className="mt-1 h-5 w-5 shrink-0 text-brand" />{t.profilePrivacy}</p>
        {!people.length && <p className="mt-6 rounded-2xl border border-line bg-card p-5 text-lg">{t.profileEmpty}</p>}
        {people.map((p) => (
          <section key={p.id} className="mt-6 rounded-3xl border border-line bg-card p-5">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-2xl">{p.name}</h3>
              <button onClick={() => onUse(p)} className="min-h-12 rounded-full bg-brand px-5 text-base font-bold text-white">{t.profileUse}</button>
            </div>
            <p className="mt-1 text-base text-muted">
              {[p.county && p.state ? `${p.county}, ${p.state}` : null, p.current_plan ? `${t.currentPlanShort}: ${p.current_plan}` : null,
                p.medicaid === true ? t.profileMedicaid : null,
                ...(p.conditions || [])].filter(Boolean).join(" · ") || t.profileNoPlace}
            </p>
            <ul className="mt-4 space-y-2">
              {(p.medicines || []).map((m) => (
                <li key={m.rxnorm_name} className="flex items-center gap-3 rounded-2xl bg-paper px-4 py-3">
                  <Pill className="h-6 w-6 shrink-0 text-brand" />
                  <div className="flex-1"><div className="text-lg font-bold">{m.display_name || m.rxnorm_name}</div>
                    <div className="text-base text-muted">{t.perMonth(m.qty_per_30d)}{m.added ? ` · ${t.addedOn(m.added)}` : ""}</div></div>
                  <button onClick={() => onRemoveMed(p.id, m.rxnorm_name)} aria-label={t.remove} className="flex h-11 w-11 items-center justify-center rounded-full text-muted hover:text-urgent"><X className="h-5 w-5" /></button>
                </li>
              ))}
            </ul>
            <button onClick={() => onRemovePerson(p.id)} className="mt-3 text-base font-bold text-urgent underline">{t.removePerson(p.name)}</button>
          </section>
        ))}
        {!!people.length && <button onClick={onClearAll} className="mt-6 min-h-12 w-full rounded-full border-2 border-urgent text-lg font-bold text-urgent">{t.clearAll}</button>}
      </div>
    </div>
  );
}
