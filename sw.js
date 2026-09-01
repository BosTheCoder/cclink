// Service worker for the installable app shell.
//
// Every URL below is derived from this worker's own registration scope rather
// than hard-coded, because the app is served at "/" on Fly and under a
// Tailscale-stripped "/<name>" prefix locally. Whatever prefix the browser
// registered this worker under is the prefix these URLs use too.
//
// Caching is deliberately conservative: demo data changes constantly and must
// never look stale.
//   - "/api/"      -> network only, never cached.
//   - navigations  -> network first; the cached shell is an offline fallback.
//   - other assets -> cache first, refreshed in the background.

const CACHE_NAME = "app-shell-v1";
const SCOPE_URL = new URL(self.registration.scope);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.add(SCOPE_URL.href))
      // Best effort: a failed precache (first install while offline) must not
      // block installation.
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
      )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // never intercept mutating requests

  if (new URL(request.url).pathname.includes("/api/")) {
    event.respondWith(fetch(request));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(SCOPE_URL.href).then((r) => r || Response.error())
      )
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok) {
            caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
