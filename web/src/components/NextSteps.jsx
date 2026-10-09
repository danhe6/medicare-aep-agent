/** Big follow-up buttons after plan results, so nobody has to think up the next question. */
export default function NextSteps({ t, onPick, used = [] }) {
  const chips = t.nextChips.filter(([, msg]) => !used.includes(msg));  // hide what was already asked
  return (
    <section className="my-5 rounded-3xl border border-line bg-card p-5 print:hidden" aria-label={t.nextTitle}>
      <h2 className="text-xl">{t.nextTitle}</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {chips.map(([label, msg]) => (
          <button key={label} onClick={() => onPick(msg)}
            className="min-h-14 rounded-2xl border-2 border-brand px-4 py-3 text-left text-lg font-bold text-brand hover:bg-brand-soft">{label}</button>
        ))}
        <button onClick={() => window.print()} className="min-h-14 rounded-2xl bg-brand px-4 py-3 text-left text-lg font-bold text-white sm:col-span-2">{t.printPage}</button>
      </div>
    </section>
  );
}
