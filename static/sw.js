const CACHE_NAME = 'smartwaste-v1';
const urlsToCache = [
  '/',
  '/citoyen',
  '/agent',
  '/gestionnaire',
  '/static/citoyen.html',
  '/static/agent.html',
  '/static/gestionnaire.html',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});