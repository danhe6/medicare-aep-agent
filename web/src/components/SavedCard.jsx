import { Camera, Lock, Pill } from "../icons.jsx";

/** Shown when the helper read a label, or saved something to the on-device profile. */
export function LabelCard({ data, t }) {
  const m = data.rxnorm_matches?.[0];
  const l = data.label || {};
  return (
    <div className="my-3 rounded-3xl border border-line bg-card p-5">
      <div className="flex items-center gap-2 text-base font-bold text-muted"><Camera className="h-5 w-5 text-brand" />{t.labelRead}</div>
      <div className="mt-2 text-2xl font-bold">{m?.display_name || [l.drug_name, l.strength].filter(Boolean).join(" ")}</div>
      {l.directions && <div className="mt-1 text-lg">{l.directions}</div>}
      {data.qty_per_30d != null && <div className="mt-1 text-lg text-muted">{t.perMonth(data.qty_per_30d)}</div>}
      {!!data.needs_user_confirmation?.length && <div className="mt-3 rounded-2xl bg-gold-soft px-4 py-2 text-base">{t.labelCheck}</div>}
    </div>
  );
}

export function SavedCard({ patch, t }) {
  const added = patch.add_medicines || [];
  const stopped = patch.stop_medicines || [];
  const other = ["county", "medicaid", "conditions", "hospital_stay_last_year"].filter((k) => patch[k] !== undefined);
  return (
    <div className="my-3 flex items-start gap-3 rounded-3xl border border-brand/30 bg-brand-soft px-5 py-4 text-lg" role="status">
      <Lock className="mt-1 h-5 w-5 shrink-0 text-brand" />
      <div>
        <div className="font-bold">{t.savedTo(patch.person)}</div>
        {added.map((m) => <div key={m.rxnorm_name} className="flex items-center gap-2"><Pill className="h-5 w-5 text-brand" />{m.display_name || m.rxnorm_name}</div>)}
        {stopped.length > 0 && <div>{t.stoppedN(stopped.length)}</div>}
        {other.length > 0 && <div className="text-base text-muted">{t.savedDetails}</div>}
      </div>
    </div>
  );
}
