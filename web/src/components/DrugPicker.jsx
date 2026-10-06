import { useEffect, useId, useRef, useState } from "react";

/** Type a few letters, pick the medicine, then pick its strength and form from a list.
 *  No free-typed drug names reach the engine, so a typo can't turn into the wrong drug. */
export default function DrugPicker({ t, onChange, field }) {
  const [q, setQ] = useState("");
  const [names, setNames] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [name, setName] = useState("");
  const [products, setProducts] = useState(null);
  const [pick, setPick] = useState("");
  const id = useId();
  const seq = useRef(0);

  useEffect(() => {
    if (name && q === name) return;
    const s = ++seq.current;
    if (q.trim().length < 2) { setNames([]); return; }
    const h = setTimeout(() => {
      fetch(`/api/drugs/suggest?q=${encodeURIComponent(q.trim())}`).then((r) => r.json())
        .then((xs) => { if (s === seq.current) { setNames(xs); setActive(xs.length ? 0 : -1); setOpen(true); } }).catch(() => {});
    }, 150);
    return () => clearTimeout(h);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  function choose(n) {
    setName(n); setQ(n); setOpen(false); setNames([]); setProducts(null); setPick(""); onChange(null);
    const lang = document.documentElement.lang === "es" ? "es" : "en";
    fetch(`/api/drugs/products?name=${encodeURIComponent(n)}&lang=${lang}`).then((r) => r.json()).then((ps) => {
      setProducts(ps);
      if (ps.length === 1) { setPick(ps[0].rxnorm_name); onChange(ps[0]); }
    }).catch(() => setProducts([]));
  }

  function onKey(e) {
    if (!open || !names.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, names.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    if (e.key === "Enter" && active >= 0) { e.preventDefault(); choose(names[active]); }
    if (e.key === "Escape") setOpen(false);
  }

  const listId = `${id}-list`;
  return (
    <div className="flex flex-col gap-3">
      <label className="relative flex flex-col gap-2 text-base font-bold">{t.drugName}
        <input value={q} onChange={(e) => { setQ(e.target.value); if (name) { setName(""); setProducts(null); setPick(""); onChange(null); } }}
          onKeyDown={onKey} onFocus={() => names.length && setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder={t.drugPh} autoComplete="off" role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${id}-o${active}` : undefined} className={field + " font-normal"} />
        {open && (
          <ul id={listId} role="listbox" className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-auto rounded-2xl border border-line bg-card py-1 font-normal shadow-lg">
            {names.length ? names.map((n, i) => (
              <li key={n} id={`${id}-o${i}`} role="option" aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); choose(n); }} onMouseEnter={() => setActive(i)}
                className={`cursor-pointer px-4 py-2.5 text-lg ${i === active ? "bg-brand-soft" : ""}`}>{n}</li>
            )) : <li className="px-4 py-2.5 text-base text-muted">{t.noMatch}</li>}
          </ul>
        )}
      </label>
      {name && (
        <label className="flex flex-col gap-2 text-base font-bold">{t.strength}
          <select value={pick} disabled={!products} onChange={(e) => { setPick(e.target.value); onChange(products.find((p) => p.rxnorm_name === e.target.value) || null); }}
            className={field + " font-normal"}>
            <option value="">{products ? (products.length ? t.pickStrength : t.noStrength) : "…"}</option>
            {(products || []).map((p) => <option key={p.rxcui} value={p.rxnorm_name}>{p.label}</option>)}
          </select>
        </label>
      )}
    </div>
  );
}
