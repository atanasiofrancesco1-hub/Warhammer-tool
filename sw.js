// WH40K 11th Edition Companion — Service Worker
// Cache + auto-update check on launch

var CACHE_NAME = 'wh40k-companion-v2';
var ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './data.json'
];

// Install: pre-cache core assets
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(ASSETS).catch(function(err) {
        console.log('Cache error (non-blocking):', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches + notify page
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(names) {
      return Promise.all(
        names.filter(function(n) { return n !== CACHE_NAME; })
             .map(function(n) { return caches.delete(n); })
      );
    }).then(function() {
      return self.clients.claim();
    }).then(function() {
      // Notifica tutte le pagine aperte che c'è una nuova versione
      return self.clients.matchAll();
    }).then(function(clients) {
      clients.forEach(function(c) {
        c.postMessage({ type: 'sw-activated' });
      });
    })
  );
});

// Fetch: cache-first for app shell, network-first for data.json (auto-update)
self.addEventListener('fetch', function(e) {
  var url = new URL(e.request.url);

  // data.json: network-first (always get latest data when online)
  if (url.pathname.endsWith('data.json')) {
    e.respondWith(
      fetch(e.request)
        .then(function(resp) {
          var copy = resp.clone();
          caches.open(CACHE_NAME).then(function(cache) { cache.put(e.request, copy); });
          return resp;
        })
        .catch(function() {
          return caches.match(e.request);
        })
    );
    return;
  }

  // Everything else: cache-first, fallback to network
  e.respondWith(
    caches.match(e.request).then(function(cached) {
      if (cached) return cached;
      return fetch(e.request).then(function(resp) {
        if (resp.status === 200) {
          var copy = resp.clone();
          caches.open(CACHE_NAME).then(function(cache) { cache.put(e.request, copy); });
        }
        return resp;
      }).catch(function() {
        return caches.match(e.request);
      });
    })
  );
});

// Listen for messages from the page
self.addEventListener('message', function(e) {
  if (e.data === 'check-update') {
    // Controlla se c'è una nuova versione di index.html
    fetch('./', { cache: 'no-store' }).then(function(resp) {
      return resp.text();
    }).then(function(text) {
      caches.open(CACHE_NAME).then(function(cache) {
        // Salva la nuova versione nella cache
        var newResp = new Response(text, { headers: { 'Content-Type': 'text/html' } });
        cache.put('./index.html', newResp.clone());
        cache.put('./', newResp.clone());
        e.source.postMessage({ type: 'update-ready' });
      });
    }).catch(function() {
      // Offline — notifica che non ci sono aggiornamenti
      e.source.postMessage({ type: 'no-update' });
    });
  }
});
