// Reminders (Web Push). The server stores only this browser's push address and a few dates.
const KEY = "mh_push";
const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; } };
const store = (v) => { try { v ? localStorage.setItem(KEY, JSON.stringify(v)) : localStorage.removeItem(KEY); } catch { /* private mode */ } };

export const pushState = () => load();  // {id, dates, plan_year} | null

/** "ok" | "ios-install" (iPhone: add to Home Screen first) | "unsupported" */
export function pushSupport() {
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone;
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return ios && !standalone ? "ios-install" : "unsupported";
  return "ok";
}

let keyPromise = null;
export function serverKey() {
  keyPromise = keyPromise || fetch("/api/push/key").then((r) => (r.ok ? r.json() : null)).then((j) => j?.key || null).catch(() => null);
  return keyPromise;
}

const toBytes = (b64) => { const s = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/")); return Uint8Array.from(s, (c) => c.charCodeAt(0)); };

/** Ask permission (first time), subscribe this browser, and add reminders. Throws Error("denied") if blocked. */
export async function remind(items, { planYear = false, lang = "en" } = {}) {
  const key = await serverKey();
  if (!key) throw new Error("off");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("denied");
  const reg = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const sub = (await reg.pushManager.getSubscription()) || (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toBytes(key) }));
  const prev = load();
  const r = await fetch("/api/reminders", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subscription: sub.toJSON(), items, plan_year: planYear || !!prev?.plan_year, lang, id: prev?.id }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "failed");
  const out = await r.json();
  store(out);
  return out;
}

export async function sendTest() {
  const s = load();
  if (s) await fetch(`/api/reminders/${s.id}/test`, { method: "POST" });
}

export async function stopReminders() {
  const s = load();
  if (s) await fetch(`/api/reminders/${s.id}`, { method: "DELETE" }).catch(() => {});
  try { const reg = await navigator.serviceWorker?.getRegistration("/sw.js"); const sub = await reg?.pushManager.getSubscription(); await sub?.unsubscribe(); } catch { /* ignore */ }
  store(null);
}
