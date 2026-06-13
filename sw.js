// McGee Family Website — Service Worker
// Caches key pages and assets for offline use
// Especially useful for baby shower guests with spotty venue WiFi

const CACHE_NAME = `mcgee-family-${CACHE_VERSION}`;
const CACHE_VERSION = '2026-06-12p';

// Pages and assets to cache immediately on install
const PRECACHE = [
  '/',
  '/index.html',
  '/family.html',
  '/gallery.html',
  '/events.html',
  '/baby-shower.html',
  '/updates.html',
  '/our-story.html',
  '/timeline.html',
  '/contact.html',
  '/bentley.html',
  '/vows.html',
  '/letters.html',
  '/year-in-review.html',
  '/baby-mcgee.html',
  '/archive.html',
  '/css/style.css',
  '/js/main.js',
  '/favicon.svg',
  // Key photos
  '/photos/baby-mcgee/5E66EA05-9500-401F-BDC1-C846EEFDE67C.jpeg',
  '/photos/wedding/7DD5E8DD-7A51-4109-87DF-B45FF9146695.jpg',
  '/photos/baby-mcgee/F3F407BA-5449-4FD4-925D-EDBE66834741.jpeg',
];

// Install — precache core assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// Activate — clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch — stale-while-revalidate for HTML, cache-first for assets
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and cross-origin requests
  if (request.method !== 'GET' || url.origin !== location.origin) return;

  // Skip API calls (JSONBin, Formspree)
  if (url.hostname.includes('jsonbin') || url.hostname.includes('formspree')) return;

  // HTML pages — stale-while-revalidate
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache =>
        cache.match(request).then(cached => {
          const network = fetch(request).then(response => {
            if (response.ok) cache.put(request, response.clone());
            return response;
          }).catch(() => cached);
          return cached || network;
        })
      )
    );
    return;
  }

  // Assets (CSS, JS, images) — cache-first
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;
      return fetch(request).then(response => {
        if (response.ok) {
          caches.open(CACHE_NAME).then(cache => cache.put(request, response.clone()));
        }
        return response;
      }).catch(() => new Response('', { status: 408 }));
    })
  );
});
