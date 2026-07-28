// Minimal app-shell service worker.
// - Static shell (index.html, manifest, icons): cache-first
// - /data/*.json: stale-while-revalidate (show cached instantly, refresh in background)
// - /api/*: never cached, always network (dynamic, per-request)

var CACHE_NAME = "briefing-app-v1";
var APP_SHELL = ["./", "./index.html", "./manifest.json", "./icon.svg", "./icon-maskable.svg"];

self.addEventListener("install", function(event){
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache){ return cache.addAll(APP_SHELL); })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function(event){
  event.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(
        keys.filter(function(key){ return key !== CACHE_NAME; })
            .map(function(key){ return caches.delete(key); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function(event){
  if(event.request.method !== "GET") return;

  var url = new URL(event.request.url);
  if(url.pathname.indexOf("/api/") !== -1) return; // always network, never cached

  if(url.pathname.indexOf("/data/") !== -1){
    event.respondWith(
      caches.open(CACHE_NAME).then(function(cache){
        return cache.match(event.request).then(function(cached){
          var network = fetch(event.request).then(function(res){
            cache.put(event.request, res.clone());
            return res;
          }).catch(function(){ return cached; });
          return cached || network;
        });
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(function(cached){
      return cached || fetch(event.request);
    })
  );
});
