const CACHE_NAME = "doccraft-shell-v2";
const APP_SHELL = ["/static/manifest.json", "/static/doccraft-icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key.startsWith("doccraft-shell-") && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname === "/health" ||
    url.pathname === "/service-worker.js"
  ) return;

  // Always fetch navigations from the server. Never serve a stale or unrelated
  // cached homepage, and do not save HTML pages in the offline asset cache.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request));
    return;
  }

  // Cache only the versioned static shell assets; fetch other resources normally.
  if (APP_SHELL.includes(url.pathname)) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        const response = await fetch(request);
        if (response && response.ok) await cache.put(request, response.clone());
        return response;
      })
    );
  }
});
