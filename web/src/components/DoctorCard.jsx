import { Check, Phone, X } from "../icons.jsx";

const STYLE = {
  listed_online: ["bg-ok-soft text-ok", Check],
  listed_in_older_directory: ["bg-warn-soft text-warn", null],
  mentioned_online: ["bg-warn-soft text-warn", null],
  no_evidence_found: ["bg-paper text-muted", X],
};

/** Per-plan evidence that a doctor is listed in the network. Evidence only; always "call to confirm". */
export default function DoctorCard({ data, t }) {
  const who = data.npi_registry_matches?.[0];
  return (
    <section className="my-4 rounded-3xl border border-line bg-card p-5">
      <h2 className="text-xl">{t.docTitle(data.doctor_query)}</h2>
      {who && <p className="mt-1 text-base text-muted">{[who.name, who.credential, who.specialty, who.city].filter(Boolean).join(" · ")}</p>}
      <ul className="mt-4 space-y-2">
        {data.plans.map((p) => {
          const [cls, Icon] = STYLE[p.status] || STYLE.no_evidence_found;
          const ev = p.evidence?.[0];
          return (
            <li key={p.organization} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-line px-4 py-3">
              <span className="text-lg font-bold">{p.organization}</span>
              <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-base font-bold ${cls}`}>
                {Icon && <Icon className="h-4 w-4" />}{t.docStatus[p.status]}{ev?.directory_year ? ` (${ev.directory_year})` : ""}
              </span>
              {ev && <a href={ev.url} target="_blank" rel="noreferrer" className="w-full truncate text-sm">{ev.title || ev.url}</a>}
            </li>);
        })}
      </ul>
      <p className="mt-4 flex items-start gap-2 rounded-2xl bg-gold-soft p-3 text-base"><Phone className="mt-1 h-5 w-5 shrink-0" />{t.docConfirm}</p>
    </section>
  );
}
