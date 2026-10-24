// Panel de gestión instalable. No guarda nada sin conexión: siempre trabaja con los datos
// más recientes de GitHub. Solo guarda el «esqueleto» del panel para que abra rápido.
const CACHE = 'gestion-v1';
const ESQUELETO = ['./', 'index.html', 'estilo.css', 'app.js', 'exifr.lite.umd.js', 'icono-192.png'];
self.addEventListener('install', e => { self.skipWaiting(); e.waitUntil(caches.open(CACHE).then(c => c.addAll(ESQUELETO)).catch(() => {})); });
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(ks => Promise.all(
  ks.filter(k => k.startsWith('gestion-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;     // GitHub, Wikipedia…: siempre en directo
  if (/\/(config|acceso)\.json$/.test(u.pathname)) return;
  // primero la red (versión nueva); sin conexión, la copia guardada
  e.respondWith(fetch(r).then(res => {
    if (res.ok) { const c = res.clone(); caches.open(CACHE).then(x => x.put(r, c)); }
    return res;
  }).catch(() => caches.match(r, { ignoreSearch: true })));
});
