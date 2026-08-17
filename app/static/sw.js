const CACHE_NAME = 'bantudulu-v2';
const STATIC_CACHE = 'bantudulu-static-v2';

const STATIC_ASSETS = [
  '/static/manifest.json',
  '/static/images/logo.png',
  '/static/images/pwa/icon-72x72.png',
  '/static/images/pwa/icon-96x96.png',
  '/static/images/pwa/icon-128x128.png',
  '/static/images/pwa/icon-144x144.png',
  '/static/images/pwa/icon-152x152.png',
  '/static/images/pwa/icon-192x192.png',
  '/static/images/pwa/icon-384x384.png',
  '/static/images/pwa/icon-512x512.png',
];

const PUBLIC_SHELL = [
  '/masuk',
  '/daftar',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(CACHE_NAME).then((cache) => cache.addAll(PUBLIC_SHELL)),
      caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)),
    ])
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  const validCaches = [CACHE_NAME, STATIC_CACHE];
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => !validCaches.includes(key)).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  const path = url.pathname;

  // Never cache authenticated or business API responses.
  if (path.startsWith('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Static assets may be cached safely.
  if (path.startsWith('/static/') || path.match(/\.(png|jpg|jpeg|webp|svg|ico|css|js|woff2?)$/)) {
    event.respondWith(cacheFirst(event.request, STATIC_CACHE));
    return;
  }

  // Public auth pages may fall back to cache. Authenticated pages stay network-only
  // to prevent one account's HTML from being exposed to another user on the device.
  if (event.request.mode === 'navigate') {
    if (PUBLIC_SHELL.includes(path)) {
      event.respondWith(networkFirstPublic(event.request));
    } else {
      event.respondWith(fetch(event.request));
    }
  }
});

async function networkFirstPublic(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    if (request.destination === 'image') {
      return new Response(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><rect fill="#eee" width="1" height="1"/></svg>',
        { headers: { 'Content-Type': 'image/svg+xml' } }
      );
    }
    throw err;
  }
}
