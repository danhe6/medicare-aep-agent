/** Health profile kept ONLY on this device (browser storage). It is sent with each chat turn so the helper
 *  doesn't ask again, and is never stored on the server. Shape:
 *  { people: [{ id, name, state, county, medicaid, conditions: [], hospital_stay_last_year,
 *               medicines: [{ rxnorm_name, display_name, qty_per_30d, directions, added }] }] } */
const KEY = "mh_profile_v1";

export function loadProfile() {
  try { return JSON.parse(localStorage.getItem(KEY)) || { people: [] }; } catch { return { people: [] }; }
}
export function saveProfile(p) { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* private mode */ } }
export function clearProfile() { try { localStorage.removeItem(KEY); } catch { /* ignore */ } }

const localDate = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const norm = (s) => (s || "me").trim().toLowerCase();

/** Merge an update_profile patch from the agent. Returns the new profile. */
export function applyPatch(profile, patch) {
  const people = [...(profile.people || [])];
  let i = people.findIndex((x) => norm(x.name) === norm(patch.person));
  if (i < 0) { people.push({ id: crypto.randomUUID?.() || String(Date.now()), name: patch.person || "Me", medicines: [], conditions: [] }); i = people.length - 1; }
  const p = { ...people[i] };
  for (const k of ["state", "county", "medicaid", "hospital_stay_last_year", "current_plan"]) if (patch[k] !== undefined) p[k] = patch[k];
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
