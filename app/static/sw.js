const CACHE_NAME = 'bantudulu-v1';
const STATIC_CACHE = 'bantudulu-static-v1';
const API_CACHE = 'bantudulu-api-v1';

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

const APP_SHELL = [
  '/masuk',
  '/daftar',
  '/beranda',
  '/cari',
  '/pesanan',
  '/profil',
];

/* ── Install: cache app shell & static assets ── */
self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
      caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)),
    ])
  );
  self.skipWaiting();
});

/* ── Activate: clean old caches ── */
self.addEventListener('activate', (event) => {
  const validCaches = [CACHE_NAME, STATIC_CACHE, API_CACHE];
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => !validCaches.includes(k)).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

/* ── Fetch: smart strategy ── */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only handle same-origin requests
  if (url.origin !== self.location.origin) return;

  const path = url.pathname;

  // ── API calls: Network First, fallback to cache ──
  if (path.startsWith('/api/')) {
    event.respondWith(networkFirst(event.request, API_CACHE));
    return;
  }

  // ── Static assets (images, css, fonts): Cache First ──
  if (path.startsWith('/static/') || path.match(/\.(png|jpg|jpeg|webp|svg|ico|css|js|woff2?)$/)) {
    event.respondWith(cacheFirst(event.request, STATIC_CACHE));
    return;
  }

  // ── Page navigations: Network First, fallback to cache ──
  if (event.request.mode === 'navigate') {
    event.respondWith(
      networkFirst(event.request, CACHE_NAME).catch(() => {
        // Ultimate fallback: serve login page
        return caches.match('/masuk');
      })
    );
    return;
  }
});

/* ── Cache Strategies ── */

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
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
    // Return a transparent pixel for images on fail
    if (request.destination === 'image') {
      return new Response(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><rect fill="#eee" width="1" height="1"/></svg>',
        { headers: { 'Content-Type': 'image/svg+xml' } }
      );
    }
    throw err;
  }
}
