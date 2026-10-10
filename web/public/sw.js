// Medicare Helper service worker: shows reminders (Web Push) and opens the app when one is tapped.
// No caching and no data: reminder texts say only what is due; the details stay in the app on this device.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { title: "Medicare Helper", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "Medicare Helper", {
    body: d.body || "", tag: d.tag, icon: "/icon-192.png", badge: "/icon-192.png", data: { url: d.url || "/app" },
  }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = new URL(e.notification.data?.url || "/app", self.location.origin).href;
  e.waitUntil((async () => {
    const tabs = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of tabs) if (c.url.startsWith(self.location.origin) && "focus" in c) { await c.navigate(url); return c.focus(); }
    return self.clients.openWindow(url);
  })());
});
