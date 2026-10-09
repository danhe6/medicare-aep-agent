import { useState } from "react";
import { Alert, Check } from "../icons.jsx";

const usd = (n) => (n == null ? "—" : `$${Number(n).toFixed(2)}`);

/** Bill vs EOB/MSN, line by line. The comparison is done in code; this only shows it. */
const fmtDate = (d) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || ""); return m ? `${m[2]}/${m[3]}/${m[1]}` : (d || "—"); };

export default function BillCard({ data, t }) {
  const [copied, setCopied] = useState(false);
  if (!data?.lines) return null;
  const B = t.bl, over = data.verdict === "overbilled";
  return (
    <section className="my-4 space-y-4">
      <div className={`rounded-3xl p-6 ${over ? "bg-warn-soft" : "border border-line bg-card"}`}>
        <div className="text-sm font-bold uppercase tracking-[0.06em] text-muted">{B.title} · {data.provider_name || ""} · {B[data.statement_kind] || ""}</div>
        <div className="mt-2 flex items-start gap-3 text-2xl font-bold">
          {over ? <Alert className="mt-1 h-7 w-7 shrink-0 text-warn" /> : <Check className="mt-1 h-7 w-7 shrink-0 text-ok" />}
          <span>{over ? B.over(data.over_by.toFixed(2)) : data.verdict === "ok" ? B.ok : B.unmatched}</span>
        </div>
        {over && <p className="mt-2 text-base">{B.note}</p>}
      </div>
      <div className="overflow-x-auto rounded-3xl border border-line bg-card">
        <table className="w-full text-left text-base">
          <thead className="bg-paper text-sm text-muted"><tr><th className="px-4 py-3">{B.date}</th><th className="px-4 py-3">{B.service}</th><th className="px-4 py-3 text-right">{B.billed}</th><th className="px-4 py-3 text-right">{B.owe}</th></tr></thead>
          <tbody>
            {data.lines.map((r, i) => (
              <tr key={i} className={`border-t border-line ${r.status === "overbilled" ? "bg-warn-soft" : ""}`}>
                <td className="px-4 py-3 whitespace-nowrap">{fmtDate(r.date)}</td>
                <td className="px-4 py-3">{r.description}</td>
                <td className="px-4 py-3 text-right font-bold">{usd(r.billed)}</td>
                <td className="px-4 py-3 text-right">{usd(r.you_owe)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.call_script && (
        <div className="rounded-3xl border border-line bg-card p-5">
          <div className="text-lg font-bold">{B.script}</div>
          <p className="mt-2 rounded-2xl bg-paper p-4 text-lg leading-relaxed">{data.call_script}</p>
          <button onClick={() => navigator.clipboard?.writeText(data.call_script).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}
            className="mt-3 min-h-12 rounded-full bg-brand px-5 font-bold text-white">{copied ? t.lt.copied : t.lt.copy}</button>
        </div>
      )}
    </section>
  );
}
