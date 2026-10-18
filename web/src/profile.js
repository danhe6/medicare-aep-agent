/** Health profile kept ONLY on this device (browser storage). It is sent with each chat turn so the helper
 *  doesn't ask again, and is never stored on the server. Shape:
 *  { people: [{ id, name, state, county, medicaid, conditions: [], hospital_stay_last_year,
 *               medicines: [{ rxnorm_name, display_name, qty_per_30d, directions, added }] }] } */
const KEY = "mh_profile_v1";

export function loadProfile() {
  try { return JSON.parse(localStorage.getItem(KEY)) || { people: [] }; } catch { return { people: [] }; }
}
export function saveProfile(p) {
  try {
    const before = localStorage.getItem(KEY), next = JSON.stringify(p);
    localStorage.setItem(KEY, next);
    if (before !== next) localStorage.setItem(CHANGED, String(Date.now()));
  } catch { /* private mode */ }
  if (p?.people?.length) askToKeep();
}
const CHANGED = "mh_profile_changed", EXPORTED = "mh_profile_exported";

/** Ask the browser not to clear our storage when space runs low (Chrome/Edge grant it quietly; Safari may still
 *  clear unused sites after 7 days unless the app is on the Home Screen - hence the backup file below). */
let asked = false;
export function askToKeep() {
  if (asked) return;
  asked = true;
  try { navigator.storage?.persist?.().catch(() => {}); } catch { /* old browser */ }
}

/** Has the profile changed since the last backup file? (null = no backup ever) */
export function backupInfo() {
  try {
    const changed = Number(localStorage.getItem(CHANGED) || 0), exported = Number(localStorage.getItem(EXPORTED) || 0);
    return { exported: exported || null, stale: changed > exported };
  } catch { return { exported: null, stale: true }; }
}

/** One-tap backup: a small JSON file the person keeps (Files app, email to self). Nothing goes to our server. */
export async function exportProfile(profile) {
  const body = JSON.stringify({ app: "medicare-helper", version: 1, exported: new Date().toISOString(), profile }, null, 2);
  const name = `medicare-helper-backup-${new Date().toISOString().slice(0, 10)}.json`;
  const file = new File([body], name, { type: "application/json" });
  let done = false;
  try {  // phones: the share sheet (Save to Files, AirDrop, email to myself)
    if (navigator.canShare?.({ files: [file] })) { await navigator.share({ files: [file] }); done = true; }
  } catch (e) { if (e?.name === "AbortError") return false; }
  if (!done) {
    const url = URL.createObjectURL(file), a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  try { localStorage.setItem(EXPORTED, String(Date.now())); } catch { /* ignore */ }
  return true;
}

/** Read a backup file and merge it into what is on this device (nothing here is overwritten or lost). */
export function importProfile(text, current) {
  const data = JSON.parse(text);
  const incoming = data?.app === "medicare-helper" ? data.profile : data;
  if (!incoming || !Array.isArray(incoming.people)) throw new Error("not a Medicare Helper backup");
  const people = [...(current?.people || [])];
  for (const q of incoming.people) {
    if (!q || typeof q !== "object") continue;
    const i = people.findIndex((x) => norm(x.name) === norm(q.name));
    if (i < 0) { people.push({ ...q, id: q.id || crypto.randomUUID?.() || String(Date.now() + people.length), medicines: q.medicines || [] }); continue; }
    const have = people[i], meds = [...(have.medicines || [])];
    for (const m of q.medicines || []) if (m?.rxnorm_name && !meds.some((x) => x.rxnorm_name === m.rxnorm_name)) meds.push(m);
    people[i] = { ...q, ...have, medicines: meds, conditions: [...new Set([...(q.conditions || []), ...(have.conditions || [])])] };
  }
  return { ...(current || {}), people };
}
export function clearProfile() { try { localStorage.removeItem(KEY); } catch { /* ignore */ } }

const localDate = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const norm = (s) => (s || "me").trim().toLowerCase();

/** Merge an update_profile patch from the agent. Returns the new profile. */
export function applyPatch(profile, patch) {
  const people = [...(profile.people || [])];
  let i = people.findIndex((x) => norm(x.name) === norm(patch.person));
  if (i < 0) { people.push({ id: crypto.randomUUID?.() || String(Date.now()), name: patch.person || "Me", medicines: [], conditions: [] }); i = people.length - 1; }
  const p = { ...people[i] };
  for (const k of ["state", "county", "medicaid", "hospital_stay_last_year", "current_plan", "current_plan_name"]) if (patch[k] !== undefined) p[k] = patch[k];
  if (patch.conditions) p.conditions = [...new Set([...(p.conditions || []), ...patch.conditions])];
  let meds = [...(p.medicines || [])];
  for (const s of patch.stop_medicines || []) meds = meds.filter((m) => m.rxnorm_name !== s);
  for (const m of patch.add_medicines || []) {
    meds = meds.filter((x) => x.rxnorm_name !== m.rxnorm_name);
    meds.push({ ...m, added: localDate() });
  }
  p.medicines = meds;
  people[i] = p;
  return { ...profile, people };
}

export function removeMedicine(profile, personId, rxnorm_name) {
  return { ...profile, people: profile.people.map((p) => p.id !== personId ? p :
    { ...p, medicines: p.medicines.filter((m) => m.rxnorm_name !== rxnorm_name) }) };
}
export function removePerson(profile, personId) {
  return { ...profile, people: profile.people.filter((p) => p.id !== personId) };
}

/** Remember what was done for a person (dates only, no results). key: compared | current_plan_checked | doctor_checked | extra_help_checked */
export function markStatus(profile, personId, key) {
  const today = localDate();
  return { ...profile, people: profile.people.map((p) => p.id !== personId ? p : { ...p, status: { ...(p.status || {}), [key]: today } }) };
}
/** Keep an appeal deadline so the home page and calendar can remind about it. */
export function setAppeal(profile, personId, appeal) {
  return { ...profile, people: profile.people.map((p) => p.id !== personId ? p : { ...p, appeal }) };
}

const normCounty = (s) => (s || "").toLowerCase().replace(/\s+(county|parish|borough)$/, "").trim();
/** Which saved person a tool call is about: same county, else the active person, else the only person. */
export function whoIsThis(profile, args, activeId) {
  const people = profile.people || [];
  if (args?.county) {
    const hits = people.filter((p) => normCounty(p.county) === normCounty(args.county) && (!args.state || !p.state || p.state.toUpperCase() === String(args.state).toUpperCase()));
    if (hits.length === 1) return hits[0].id;
    if (hits.some((p) => p.id === activeId)) return activeId;
  }
  if (people.some((p) => p.id === activeId)) return activeId;
  return people.length === 1 ? people[0].id : null;
}

const SELF = /^(me|myself|i|yo|mí|mi)$/i;
/** Senior mode is the person talking about themself: only their own saved record is used and shown.
 *  Family mode sees everyone they help. */
export function forMode(profile, mode) {
  if (mode !== "senior") return profile;
  return { ...profile, people: (profile.people || []).filter((p) => SELF.test((p.name || "").trim())) };
}
