const CACHE_NAME = 'smartwaste-v2';
const urlsToCache = [
  '/',
  '/citoyen',
  '/static/citoyen.html',
  '/static/offline.js',
  '/static/i18n.js',
  '/static/manifest.webmanifest'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async cache => {
      for (const url of urlsToCache) {
        try { await cache.add(url); } catch (error) { /* réseau absent pendant l'installation */ }
      }
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    if (new URL(event.request.url).origin !== self.location.origin || event.request.method !== 'GET') return;
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
  );
});