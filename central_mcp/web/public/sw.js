// Image cache for listing photos. Cache-first with background revalidation, capped in size.
// Only image requests are intercepted; API and MCP traffic always goes to the network.

const CACHE_NAME = "central-mcp-images-v1";
const MAX_ENTRIES = 200;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET" || request.destination !== "image") {
    return;
  }
  event.respondWith(serveImage(request));
});

async function serveImage(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) {
    fetchAndStore(cache, request).catch(() => undefined);
    return cached;
  }
  return fetchAndStore(cache, request);
}

async function fetchAndStore(cache, request) {
  const response = await fetch(request);
  if (response.ok || response.type === "opaque") {
    await store(cache, request, response.clone());
  }
  return response;
}

async function store(cache, request, response) {
  try {
    await cache.put(request, response);
    await trim(cache);
  } catch {
    // Quota exceeded or storage unavailable: the image still reaches the page.
  }
}

async function trim(cache) {
  const keys = await cache.keys();
  const excess = keys.length - MAX_ENTRIES;
  for (let index = 0; index < excess; index += 1) {
    await cache.delete(keys[index]);
  }
}
