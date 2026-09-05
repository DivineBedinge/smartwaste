const CACHE_NAME = 'smartwaste-v6';
const CACHE_PREFIX = 'smartwaste-';
const STATIC_URLS = ['/', '/citoyen', '/static/citoyen.html', '/static/offline.js', '/static/i18n.js', '/static/map-common.js', '/static/ui-shell.js', '/static/smartwaste.css', '/static/mascot-recycleur.svg', '/static/icon-192.png', '/static/icon-512.png', '/static/icon-maskable-512.png', '/static/manifest.webmanifest'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_URLS)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map(key => caches.delete(key))
  )));
  self.clients.claim();
});

self.addEventListener('message', event => {
  if (event.data?.type === 'PURGE_PRIVATE') {
    event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('smartwaste-private-')).map(key => caches.delete(key)))));
  }
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  event.respondWith(fetch(request).then(response => {
    if (response.ok && response.type === 'basic') {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
    }
    return response;
  }).catch(() => caches.match(request).then(cached => cached || caches.match('/citoyen'))));
});
