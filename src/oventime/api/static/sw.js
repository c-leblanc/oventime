// sw.js — Service Worker OvenTime

const APP_URL = new URL(self.location.href).searchParams.get("appUrl")
             ?? "https://oventime.up.railway.app";

// ── Réception d'un push ──────────────────────────────────────────────────────
self.addEventListener("push", (event) => {
  let payload = { title: "OvenTime", body: "Alerte réseau électrique", tag: "oventime" };

  try {
    if (event.data) payload = { ...payload, ...event.data.json() };
  } catch (_) {}

  const options = {
    body:      payload.body,
    icon:      "/static/logo.png",
    badge:     "/static/logo.png",
    tag:       payload.tag,
    renotify:  true,
    data:      { url: APP_URL },
    actions: [
      { action: "open",    title: "Voir le réseau" },
      { action: "dismiss", title: "Ignorer" },
    ],
  };

  event.waitUntil(self.registration.showNotification(payload.title, options));
});

// ── Clic sur la notification ─────────────────────────────────────────────────
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  if (event.action === "dismiss") return;

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((list) => {
        for (const client of list) {
          if (client.url.startsWith(APP_URL) && "focus" in client) {
            return client.focus();
          }
        }
        if (clients.openWindow) return clients.openWindow(APP_URL);
      })
  );
});