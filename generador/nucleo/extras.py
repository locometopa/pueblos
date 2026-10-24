"""Extras de la web: vista previa al compartir (WhatsApp…), web instalable en el móvil y línea del tiempo."""
import html
import json
import os
import re
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:          # sin Pillow la web se genera igual, solo sin las imágenes para compartir
    Image = None

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def e(t) -> str:
    return html.escape(str(t or ""), quote=True)


# ---------------------------------------------------------------------------- dirección pública
def url_base(cfg) -> str:
    """https://usuario.github.io/repo/ (para que WhatsApp encuentre las imágenes)."""
    if cfg.get("url_web"):
        u = cfg["url_web"].strip()
        return u if u.endswith("/") else u + "/"
    origen = cfg.get("repo_url") or ""
    if not origen and os.environ.get("GITHUB_REPOSITORY"):
        origen = "github.com/" + os.environ["GITHUB_REPOSITORY"]
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", origen.strip())
    if not m:
        return ""
    usuario, repo = m.group(1), m.group(2)
    if repo.lower() == f"{usuario.lower()}.github.io":
        return f"https://{usuario.lower()}.github.io/"
    return f"https://{usuario.lower()}.github.io/{repo}/"


def meta_compartir(base: str, titulo: str, descripcion: str, ruta: str, imagen: str, sitio: str) -> str:
    """Etiquetas Open Graph: así WhatsApp, Telegram, Facebook… muestran foto, título y texto."""
    if not base:
        return ""
    partes = [
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="es_ES">',
        f'<meta property="og:site_name" content="{e(sitio)}">',
        f'<meta property="og:title" content="{e(titulo)}">',
        f'<meta property="og:description" content="{e(descripcion)}">',
        f'<meta property="og:url" content="{e(base + ruta)}">',
        f'<link rel="canonical" href="{e(base + ruta)}">',
    ]
    if imagen:
        partes += [f'<meta property="og:image" content="{e(base + imagen)}">',
                   '<meta property="og:image:width" content="1200">',
                   '<meta property="og:image:height" content="630">',
                   '<meta name="twitter:card" content="summary_large_image">']
    return "\n".join(partes)


# ---------------------------------------------------------------------------- imágenes para compartir
def _fuente(tam, negrita=True):
    candidatos = (["DejaVuSerif-Bold.ttf", "georgiab.ttf", "Georgia Bold.ttf"] if negrita
                  else ["DejaVuSans.ttf", "segoeui.ttf", "arial.ttf"])
    carpetas = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "C:/Windows/Fonts",
                "/Library/Fonts", "/System/Library/Fonts/Supplemental"]
    for c in carpetas:
        for n in candidatos:
            p = Path(c) / n
            if p.exists():
                return ImageFont.truetype(str(p), tam)
    try:
        return ImageFont.load_default(size=tam)
    except TypeError:
        return ImageFont.load_default()


def _rgb(hexa):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def _guardar_si_cambia(im, destino: Path, firma: str):
    """Solo reescribe si cambian las fotos o el diseño (así no se sube lo mismo cada vez)."""
    marca = destino.with_name("." + destino.stem + ".firma")
    if destino.exists() and marca.exists() and marca.read_text(encoding="utf-8") == firma:
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(destino, "JPEG", quality=82, optimize=True, progressive=True)
    marca.write_text(firma, encoding="utf-8")


def imagen_pueblo(foto: Path, destino: Path, nombre: str, colores: dict) -> bool:
    """1200×630 con la portada del pueblo y su nombre."""
    if Image is None or not foto.exists():
        return False
    firma = f"{foto.stat().st_size}-{foto.stat().st_mtime}-{nombre}-{colores['acento']}-v1"
    try:
        with Image.open(foto) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im = ImageOps.fit(im, (1200, 630), Image.LANCZOS)
        capa = Image.new("RGBA", (1200, 630), (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        for y in range(380, 630):    # degradado oscuro abajo para que se lea el nombre
            d.line([(0, y), (1200, y)], fill=(0, 0, 0, int(170 * (y - 380) / 250)))
        im = Image.alpha_composite(im.convert("RGBA"), capa)
        d = ImageDraw.Draw(im)
        f = _fuente(78)
        d.text((56, 560), nombre, font=f, fill="white", anchor="ls")
        d.rectangle([56, 582, 156, 590], fill=_rgb(colores["acento"]))
        _guardar_si_cambia(im, destino, firma)
        return True
    except Exception:  # noqa: BLE001  (una foto rara no debe parar la web)
        return False


def imagen_portada(fotos: list, destino: Path, titulo: str, subtitulo: str, cifras: str, colores: dict) -> bool:
    """1200×630 de la portada de la web: título, cifras y unas polaroids de tus fotos."""
    if Image is None:
        return False
    fotos = [f for f in fotos if f.exists()][:3]
    firma = "|".join(f"{f}-{f.stat().st_mtime}" for f in fotos) + f"|{titulo}|{subtitulo}|{cifras}|{colores}|v1"
    try:
        im = Image.new("RGB", (1200, 630), _rgb(colores["papel"]))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 1200, 14], fill=_rgb(colores["acento"]))
        ancho_texto = 600 if fotos else 1080
        f_t = _fuente(84)
        while f_t.getlength(titulo) > ancho_texto and f_t.size > 40:
            f_t = _fuente(f_t.size - 4)
        d.text((60, 110), "CUADERNO DE VIAJE", font=_fuente(22, False), fill=_rgb(colores["acento"]))
        d.text((60, 150), titulo, font=f_t, fill=_rgb(colores["tinta"]))
        y = 150 + f_t.size + 30
        f_s = _fuente(32, False)
        palabras, linea = subtitulo.split(), ""
        for p in palabras:            # reparto en líneas
            prueba = (linea + " " + p).strip()
            if f_s.getlength(prueba) > ancho_texto and linea:
                d.text((60, y), linea, font=f_s, fill=_rgb(colores["tinta-2"]))
                y += 44
                linea = p
            else:
                linea = prueba
        if linea:
            d.text((60, y), linea, font=f_s, fill=_rgb(colores["tinta-2"]))
        d.text((60, 540), cifras, font=_fuente(30), fill=_rgb(colores["acento"]))
        posiciones = [(700, 70, -6), (880, 210, 5), (690, 330, 3)]
        for foto, (x, y, giro) in zip(fotos, posiciones):
            with Image.open(foto) as f:
                f = ImageOps.fit(ImageOps.exif_transpose(f).convert("RGB"), (280, 210), Image.LANCZOS)
            marco = Image.new("RGB", (304, 262), "white")
            marco.paste(f, (12, 12))
            marco = marco.convert("RGBA").rotate(giro, expand=True, resample=Image.BICUBIC)
            sombra = Image.new("RGBA", marco.size, (0, 0, 0, 0))
            sombra.paste((0, 0, 0, 60), mask=marco.split()[3])
            im.paste(sombra, (x + 6, y + 8), sombra)
            im.paste(marco, (x, y), marco)
        _guardar_si_cambia(im, destino, firma)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------- web instalable
def iconos(destino: Path, logo: Path, colores: dict) -> bool:
    """icono-192.png e icono-512.png (los móviles necesitan PNG para instalar la web)."""
    if Image is None:
        return False
    firma = f"{logo.stat().st_mtime if logo and logo.exists() else 'casita'}-{colores['acento']}-v1"
    for lado in (192, 512):
        try:
            if logo and logo.exists():
                with Image.open(logo) as im:
                    im = ImageOps.fit(im.convert("RGBA"), (lado, lado), Image.LANCZOS)
                fondo = Image.new("RGBA", (lado, lado), _rgb(colores["papel"]) + (255,))
                im = Image.alpha_composite(fondo, im)
            else:     # la misma casita con campanario del favicon
                k = lado / 64
                im = Image.new("RGBA", (lado, lado), _rgb(colores["acento"]) + (255,))
                d = ImageDraw.Draw(im)
                sc = lambda pts: [(x * k, y * k) for x, y in pts]  # noqa: E731
                d.polygon(sc([(12, 50), (12, 32), (24, 22), (36, 32), (36, 50)]), fill="white")
                d.polygon(sc([(36, 50), (36, 26), (43, 15), (50, 26), (50, 50)]), fill="white")
                d.rounded_rectangle([21 * k, 38 * k, 27 * k, 50 * k], radius=3 * k, fill=_rgb(colores["acento"]))
                d.ellipse([40 * k, 28 * k, 46 * k, 34 * k], fill=_rgb(colores["acento"]))
            _guardar_png(im, destino / f"icono-{lado}.png", firma)
        except Exception:  # noqa: BLE001
            return False
    return True


def _guardar_png(im, destino: Path, firma: str):
    marca = destino.with_name("." + destino.stem + ".firma")
    if destino.exists() and marca.exists() and marca.read_text(encoding="utf-8") == firma:
        return
    im.save(destino, "PNG", optimize=True)
    marca.write_text(firma, encoding="utf-8")


def manifiesto(titulo: str, descripcion: str, colores: dict, con_png: bool) -> str:
    iconos_ = [{"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml"}]
    if con_png:
        iconos_ = [{"src": "icono-192.png", "sizes": "192x192", "type": "image/png"},
                   {"src": "icono-512.png", "sizes": "512x512", "type": "image/png"},
                   {"src": "icono-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}] + iconos_
    corto = titulo if len(titulo) <= 14 else titulo.split()[-1][:14]
    return json.dumps({"name": titulo, "short_name": corto, "description": descripcion, "lang": "es",
                       "start_url": "./", "scope": "./", "display": "standalone",
                       "background_color": colores["papel"], "theme_color": colores["acento"],
                       "icons": iconos_}, ensure_ascii=False, indent=1)


def service_worker(version: str) -> str:
    """Guarda lo que ya has visto para que la web abra rápido y funcione sin cobertura."""
    return """const CACHE='pueblos-%s';
self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(
  ks.filter(k=>k.startsWith('pueblos-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  const r=e.request, u=new URL(r.url);
  if(r.method!=='GET'||u.origin!==location.origin||u.pathname.includes('/gestion/')||u.pathname.endsWith('/sw.js')) return;
  if(r.mode==='navigate'||(r.headers.get('accept')||'').includes('text/html')){
    e.respondWith(fetch(r).then(res=>{const c=res.clone();caches.open(CACHE).then(x=>x.put(r,c));return res;})
      .catch(()=>caches.match(r).then(m=>m||caches.match('./'))));
    return;
  }
  e.respondWith(caches.match(r).then(m=>{
    const red=fetch(r).then(res=>{if(res.ok){const c=res.clone();caches.open(CACHE).then(x=>x.put(r,c));}return res;});
    return m||red;
  }));
});
""" % version


SW_APAGADO = """// La opción «instalable» está desactivada: se borra lo guardado y se quita.
self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.map(k=>caches.delete(k))))
  .then(()=>self.registration.unregister())));
"""


def js_instalar(raiz: str) -> str:
    return ("(function(){if('serviceWorker'in navigator&&/^https?:/.test(location.protocol))"
            f"navigator.serviceWorker.register('{raiz}sw.js').catch(function(){{}});"
            "var b=document.querySelector('.instalar'),a=document.querySelector('.ayuda-ios');if(!b)return;var ev=null;"
            "var solo=matchMedia('(display-mode: standalone)').matches||navigator.standalone;if(solo)return;"
            "window.addEventListener('beforeinstallprompt',function(x){x.preventDefault();ev=x;b.hidden=false;});"
            "var ios=/iphone|ipad|ipod/i.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);"
            "if(ios)b.hidden=false;"
            "b.addEventListener('click',function(){if(ev){ev.prompt();ev.userChoice.then(function(){ev=null;b.hidden=true;});}"
            "else if(a){a.hidden=!a.hidden;}});"
            "window.addEventListener('appinstalled',function(){b.hidden=true;});})();")


BOTON_INSTALAR = ('<div class="instalar-caja"><button class="instalar" type="button" hidden>📲 Instalar en el móvil</button>'
                  '<p class="ayuda-ios" hidden>En el iPhone: pulsa <b>Compartir</b> '
                  '(el cuadrado con la flecha) y luego <b>«Añadir a pantalla de inicio»</b>.</p></div>')


# ---------------------------------------------------------------------------- línea del tiempo
def _fecha(iso: str) -> str:
    p = (iso or "").split("-")
    try:
        if len(p) == 3:
            return f"{int(p[2])} de {MESES[int(p[1]) - 1]}"
        if len(p) == 2:
            return MESES[int(p[1]) - 1].capitalize()
    except (ValueError, IndexError):
        pass
    return "Durante el año"


def cronologia(visitados: list) -> str:
    visitas = []
    for p in visitados:
        for f in p.get("fechas_visita") or []:
            if re.match(r"^\d{4}", f or ""):
                visitas.append((f, p))
    if not visitas:
        return ""
    visitas.sort(key=lambda x: (x[0][:4], x[0]), reverse=True)
    anios = {}
    for f, p in visitas:
        anios.setdefault(f[:4], []).append((f, p))
    bloques = []
    for i, (anio, lista) in enumerate(anios.items()):
        hitos = []
        for f, p in lista:
            if p.get("portada"):
                img = f'<img src="pueblos/{e(p["slug"])}/mini/{e(p["portada"])}" alt="" loading="lazy">'
            else:
                img = f'<span class="sinfoto">{e(p["nombre"][:1])}</span>'
            lugar = p.get("provincia") or p.get("comunidad") or ""
            hitos.append(f'<li><a class="hito" href="pueblos/{e(p["slug"])}/index.html">{img}'
                         f'<span><b>{e(p["nombre"])}</b><small>{e(_fecha(f))}{" · " + e(lugar) if lugar else ""}</small></span></a></li>')
        n = len(lista)
        bloque = (f'<div class="anio"><h3>{anio} <small>{n} {"visita" if n == 1 else "visitas"}</small></h3>'
                  f'<ol>{"".join(hitos)}</ol></div>')
        bloques.append(bloque)
    visibles, resto = bloques[:2], bloques[2:]
    mas = (f'<details class="mas-anios"><summary>Ver {len(resto)} {"año" if len(resto) == 1 else "años"} más</summary>'
           f'{"".join(resto)}</details>') if resto else ""
    return (f'<section class="cronologia envoltorio" id="viajes"><h2>Mis viajes, año a año</h2>'
            f'<p>{len(visitas)} {"visita" if len(visitas) == 1 else "visitas"} en {len(anios)} '
            f'{"año" if len(anios) == 1 else "años"}.</p>{"".join(visibles)}{mas}</section>')


CSS = """
.cronologia{padding-top:44px;padding-bottom:10px}
.cronologia>h2{font:600 34px/1.1 var(--f-titulo);margin:0 0 4px}
.cronologia>p{color:var(--tinta-2);margin:0 0 20px}
.anio{position:relative;padding-left:28px;margin-bottom:22px}
.anio::before{content:"";position:absolute;left:8px;top:10px;bottom:-12px;width:2px;background:var(--linea)}
.anio h3{font:600 26px var(--f-titulo);margin:0 0 10px;position:relative}
.anio h3::before{content:"";position:absolute;left:-26px;top:9px;width:14px;height:14px;border-radius:50%;
  background:var(--acento);box-shadow:0 0 0 4px var(--papel)}
.anio h3 small{font:500 14px var(--f-texto);color:var(--tinta-2);margin-left:6px}
.anio ol{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.hito{display:flex;gap:12px;align-items:center;padding:8px;border-radius:12px;background:var(--tarjeta);
  text-decoration:none;color:var(--tinta);box-shadow:var(--sombra);transition:transform .15s}
.hito:hover{transform:translateY(-2px)}
.hito img,.hito .sinfoto{width:56px;height:56px;border-radius:9px;object-fit:cover;flex:none}
.hito .sinfoto{display:grid;place-items:center;background:var(--papel-2);font:600 24px var(--f-titulo);color:var(--acento)}
.hito b{display:block;font:600 17px var(--f-titulo)}
.hito small{color:var(--tinta-2);font-size:14px}
.mas-anios summary{cursor:pointer;display:inline-block;margin:0 0 16px 28px;padding:7px 16px;border-radius:99px;
  border:1px solid var(--linea);color:var(--tinta);list-style:none}
.mas-anios summary::-webkit-details-marker{display:none}
.mas-anios[open] summary{display:none}
.instalar-caja{margin-top:14px}
.instalar{font:inherit;font-size:15px;padding:9px 18px;border-radius:99px;border:0;background:var(--acento);color:#fff;cursor:pointer}
.ayuda-ios{margin:10px 0 0;max-width:420px}
@media (max-width:600px){.anio ol{grid-template-columns:1fr}.cronologia>h2{font-size:28px}}
"""


# ---------------------------------------------------------------------------- ficha del pueblo: tiempo, mapa, cerca
def bloque_tiempo(lat, lon) -> str:
    if lat is None or lon is None:
        return ""
    return (f'<section class="caja tiempo" data-lat="{lat}" data-lon="{lon}" hidden><h3>El tiempo ahora</h3>'
            '<div class="t-ahora"></div><ol class="t-dias"></ol><p class="t-sol"></p>'
            '<p class="fuente">Previsión de <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a></p></section>')


def bloque_mapa(lat, lon, nombre) -> str:
    if lat is None or lon is None:
        return ""
    d = 0.035
    bbox = f"{lon - d * 1.4},{lat - d},{lon + d * 1.4},{lat + d}"
    return (f'<section class="caja mapa-pueblo"><h3>Dónde está</h3>'
            f'<iframe title="Mapa de {e(nombre)}" loading="lazy" referrerpolicy="no-referrer" '
            f'src="https://www.openstreetmap.org/export/embed.html?bbox={bbox}&amp;layer=mapnik&amp;marker={lat},{lon}"></iframe>'
            f'<div class="fila-botones"><a class="boton" target="_blank" rel="noopener" '
            f'href="https://www.google.com/maps/dir/?api=1&amp;destination={lat},{lon}">🚗 Cómo llegar</a>'
            f'<a class="boton sec" target="_blank" rel="noopener" '
            f'href="https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=14/{lat}/{lon}">Mapa grande</a></div></section>')


def distancia_km(a, b) -> float:
    from math import radians, sin, cos, asin, sqrt
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def cercanos(p: dict, todos: list, maximo=5, radio=80) -> list:
    if p.get("lat") is None or p.get("lon") is None:
        return []
    res = []
    for q in todos:
        if q is p or q.get("slug") == p.get("slug") or q.get("lat") is None or q.get("lon") is None:
            continue
        km = distancia_km((p["lat"], p["lon"]), (q["lat"], q["lon"]))
        if km <= radio:
            res.append((km, q))
    res.sort(key=lambda x: x[0])
    return res[:maximo]


def bloque_cercanos(lista) -> str:
    if not lista:
        return ""
    items = "".join(
        f'<li><a href="../{e(q["slug"])}/index.html"><b>{e(q["nombre"])}</b>'
        f'<small>{round(km) if km >= 1 else "< 1"} km{" · por visitar" if q.get("estado") == "pendiente" else ""}</small></a></li>'
        for km, q in lista)
    return f'<section class="caja cerca"><h3>Cerca de aquí</h3><ul>{items}</ul></section>'


JS_TIEMPO = r"""
(function(){
  var c=document.querySelector('.tiempo-mini'); if(!c) return;
  var W={0:['☀️','Despejado'],1:['🌤','Casi despejado'],2:['⛅','Nubes y claros'],3:['☁️','Nublado'],45:['🌫','Niebla'],48:['🌫','Niebla'],
    51:['🌦','Llovizna'],53:['🌦','Llovizna'],55:['🌧','Llovizna fuerte'],56:['🌧','Llovizna helada'],57:['🌧','Llovizna helada'],
    61:['🌦','Lluvia débil'],63:['🌧','Lluvia'],65:['🌧','Lluvia fuerte'],66:['🌧','Lluvia helada'],67:['🌧','Lluvia helada'],
    71:['🌨','Nieve débil'],73:['🌨','Nieve'],75:['❄️','Nieve fuerte'],77:['🌨','Granizo fino'],80:['🌦','Chubascos'],81:['🌧','Chubascos'],
    82:['⛈','Chubascos fuertes'],85:['🌨','Chubascos de nieve'],86:['❄️','Chubascos de nieve'],95:['⛈','Tormenta'],96:['⛈','Tormenta con granizo'],99:['⛈','Tormenta con granizo']};
  function w(n,dia){var x=W[n]||['🌡','—']; if(!dia&&(n===0||n===1)) x=['🌙',x[1]]; return x;}
  var DS=['dom','lun','mar','mié','jue','vie','sáb'];
  var b=c.querySelector('.t-boton'), panel=c.querySelector('.t-panel');
  function abrir(si){panel.hidden=!si;b.setAttribute('aria-expanded',si?'true':'false');c.classList.toggle('abierto',si);}
  b.addEventListener('click',function(ev){ev.stopPropagation();abrir(panel.hidden);});
  document.addEventListener('click',function(ev){if(!c.contains(ev.target))abrir(false);});
  document.addEventListener('keydown',function(ev){if(ev.key==='Escape')abrir(false);});
  var url='https://api.open-meteo.com/v1/forecast?latitude='+c.dataset.lat+'&longitude='+c.dataset.lon+
    '&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m,is_day'+
    '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset&timezone=auto&forecast_days=5';
  fetch(url).then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(d){
    var a=d.current, x=w(a.weather_code,a.is_day);
    b.querySelector('.t-icono').textContent=x[0];
    b.querySelector('.t-grados').textContent=Math.round(a.temperature_2m)+'°';
    b.querySelector('.t-txt').textContent=x[1];
    c.querySelector('.t-detalle').innerHTML='<b>'+x[0]+' '+Math.round(a.temperature_2m)+'° · '+x[1]+'</b><br>Sensación '+Math.round(a.apparent_temperature)+
      '° · viento '+Math.round(a.wind_speed_10m)+' km/h · humedad '+Math.round(a.relative_humidity_2m)+'%';
    var D=d.daily, h='';
    for(var i=0;i<D.time.length;i++){var f=new Date(D.time[i]+'T12:00:00'), y=w(D.weather_code[i],1);
      var ll=D.precipitation_probability_max&&D.precipitation_probability_max[i]>=30?'<em>💧'+D.precipitation_probability_max[i]+'%</em>':'<em></em>';
      h+='<li><b>'+(i===0?'Hoy':i===1?'Mañana':DS[f.getDay()])+'</b><span title="'+y[1]+'">'+y[0]+'</span>'+ll+
         '<span>'+Math.round(D.temperature_2m_max[i])+'° <small>'+Math.round(D.temperature_2m_min[i])+'°</small></span></li>';}
    c.querySelector('.t-dias').innerHTML=h;
    var hora=function(s){return s?s.slice(11,16):'';};
    c.querySelector('.t-sol').textContent='🌅 '+hora(D.sunrise[0])+'    🌇 '+hora(D.sunset[0]);
    c.hidden=false;
  }).catch(function(){});
})();
"""

CSS_FICHA = """
.lateral{align-self:start;min-width:0}
.lateral .datos{position:static}
.caja{margin-top:18px;padding:16px;border-radius:14px;background:var(--tarjeta);box-shadow:var(--sombra)}
.caja h3{font:600 19px var(--f-titulo);margin:0 0 10px}
.caja .fuente{margin:10px 0 0;font-size:12px;color:var(--tinta-2)}
.t-ahora{display:flex;align-items:center;gap:10px}
.t-icono{font-size:40px;line-height:1}
.t-grados{font:600 40px/1 var(--f-titulo)}
.t-txt{display:flex;flex-direction:column;font-weight:600}
.t-txt small{font-weight:400;color:var(--tinta-2);font-size:13px}
.t-dias{list-style:none;margin:14px 0 0;padding:0;display:grid;grid-template-columns:repeat(5,1fr);gap:4px;text-align:center;font-size:13px}
.t-dias li{display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 0;border-radius:10px;background:var(--papel-2)}
.t-dias b{font-weight:600;text-transform:capitalize}
.t-dias span:first-of-type{font-size:22px}
.t-dias em{font-style:normal;font-size:11px;color:var(--pendiente);min-height:14px}
.t-dias small{color:var(--tinta-2)}
.t-sol{margin:10px 0 0;font-size:14px;color:var(--tinta-2);white-space:pre}
.mapa-pueblo iframe{width:100%;height:220px;border:0;border-radius:10px;display:block;background:var(--papel-2)}
.fila-botones{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.boton{display:inline-block;padding:8px 14px;border-radius:99px;background:var(--acento);color:#fff!important;text-decoration:none;font-size:14px;font-weight:600}
.boton.sec{background:transparent;color:var(--tinta)!important;border:1px solid var(--linea)}
.cerca ul{list-style:none;margin:0;padding:0}
.cerca li a{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid var(--linea);text-decoration:none;color:var(--tinta)}
.cerca li:first-child a{border-top:0}
.cerca small{color:var(--tinta-2);white-space:nowrap}
"""


# ---------------------------------------------------------------------------- fiestas
_MES_CORTO = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _insignia(regla: dict):
    t = regla.get("t")
    if t == "dia":
        return str(regla["d"]), _MES_CORTO[regla["m"] - 1]
    if t == "nsem":
        orden = {1: "1.er", 2: "2.º", 3: "3.er", 4: "4.º", -1: "últ.", -2: "penúlt."}.get(regla["n"], "")
        dia = "finde" if regla.get("finde") else ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"][regla["wd"]]
        return f"{orden} {dia}", _MES_CORTO[regla["m"] - 1]
    if t == "mes":
        return _MES_CORTO[regla["m"] - 1], {"inicio": "princ.", "mitad": "mitad", "final": "final"}.get(regla.get("parte"), "")
    if t == "pascua":
        return "🌼", "móvil"
    return "🎉", ""


def bloque_fiestas(lista: list, nombre_pueblo: str) -> str:
    if not lista:
        return ""
    items = []
    for f in lista:
        a, b = _insignia(f.get("regla") or {})
        regla = json.dumps(f.get("regla") or {}, separators=(",", ":"))
        detalle = f'<p class="f-detalle">{e(f["detalle"])}</p>' if f.get("detalle") else ""
        items.append(f'<li data-regla="{e(regla)}"><div class="f-insignia"><b>{e(a)}</b><span>{e(b)}</span></div>'
                     f'<div class="f-texto"><h3>{e(f["nombre"])}</h3><p class="f-cuando">{e(f.get("cuando"))}'
                     f'<span class="f-prox"></span></p>{detalle}</div></li>')
    fuentes = sorted({f.get("fuente") for f in lista if f.get("fuente") in ("Wikipedia", "Wikidata")})
    pie = (f"Datos de {' y '.join(fuentes)}. " if fuentes else "") + "Las fechas pueden cambiar de un año a otro: confírmalas antes de ir."
    return (f'<section class="fiestas"><h2>Fiestas de {e(nombre_pueblo)}</h2><ol class="lista-fiestas">{"".join(items)}</ol>'
            f'<p class="fuente">{pie}</p></section>')


def datos_proximas(pueblos: list) -> list:
    """Para «Próximas fiestas» de la portada (la fecha se calcula en el navegador)."""
    from .fiestas import del_pueblo
    res = []
    for p in pueblos:
        for f in del_pueblo(p):
            if (f.get("regla") or {}).get("t") in ("dia", "nsem", "pascua", "mes"):
                res.append({"n": f["nombre"], "c": f.get("cuando", ""), "r": f["regla"], "p": p["nombre"],
                            "u": f"pueblos/{p['slug']}/index.html", "e": p.get("estado", "visitado"),
                            "f": f"pueblos/{p['slug']}/mini/{p['portada']}" if p.get("portada") else ""})
    return res


def seccion_proximas(pueblos: list) -> str:
    datos = datos_proximas(pueblos)
    if not datos:
        return ""
    j = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (f'<section class="proximas envoltorio" id="proximas-fiestas" hidden><h2>Próximas fiestas</h2>'
            f'<p>En mis pueblos, en los próximos dos meses.</p><div class="rejilla-fiestas"></div>'
            f'<script type="application/json" id="datos-fiestas">{j}</script></section>')


JS_FIESTAS = r"""
(function(){
  var MESES=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
  var MC=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
  var DS=['domingo','lunes','martes','miércoles','jueves','viernes','sábado'];
  function pascua(y){var a=y%19,b=Math.floor(y/100),c=y%100,d=Math.floor(b/4),e=b%4,f=Math.floor((b+8)/25),g=Math.floor((b-f+1)/3),
    h=(19*a+b-d-g+15)%30,i=Math.floor(c/4),k=c%4,l=(32+2*e+2*i-h-k)%7,m=Math.floor((a+11*h+22*l)/451),
    mes=Math.floor((h+l-7*m+114)/31),dia=(h+l-7*m+114)%31+1; return new Date(y,mes-1,dia);}
  function sum(d,n){var x=new Date(d);x.setDate(x.getDate()+n);return x;}
  function en(r,y){
    if(r.t==='dia'){var i=new Date(y,r.m-1,r.d),f=new Date(y,(r.m2||r.m)-1,r.d2||r.d);return [i,f<i?i:f];}
    if(r.t==='pascua'){var p=sum(pascua(y),r.o);return [p,sum(p,r.o===-7?7:0)];}
    if(r.t==='nsem'){var d;
      if(r.n>0){d=new Date(y,r.m-1,1);d=sum(d,((r.wd-d.getDay())+7)%7+7*(r.n-1));}
      else{d=new Date(y,r.m,0);d=sum(d,-(((d.getDay()-r.wd)+7)%7)-7*(-r.n-1));}
      if(d.getMonth()!==r.m-1)return null;return [d,sum(d,r.finde?1:0)];}
    if(r.t==='mes'){var di={inicio:1,mitad:10,final:20}[r.parte]||1;return [new Date(y,r.m-1,di),new Date(y,r.m-1,28)];}
    return null;}
  var hoy=new Date();hoy.setHours(0,0,0,0);
  function proxima(r){for(var y=hoy.getFullYear();y<=hoy.getFullYear()+1;y++){var x=en(r,y);if(x&&x[1]>=hoy)return x;}return null;}
  function faltan(x,r){var n=Math.round((x[0]-hoy)/864e5);
    if(n<=0) return x[1]>hoy||n===0?(n===0&&+x[0]===+x[1]?'¡es hoy!':'¡ahora mismo!'):'';
    if(r.t==='mes') return n<=31?'este mes':'en '+MESES[x[0].getMonth()];
    if(n===1) return 'mañana';
    return n<45?'faltan '+n+' días':DS[x[0].getDay()]+' '+x[0].getDate()+' de '+MESES[x[0].getMonth()]+(x[0].getFullYear()!==hoy.getFullYear()?' de '+x[0].getFullYear():'');}
  // ficha del pueblo
  var lista=document.querySelector('.lista-fiestas');
  if(lista){var lis=[].slice.call(lista.children),orden=[];
    lis.forEach(function(li){var r;try{r=JSON.parse(li.dataset.regla);}catch(e){r={};}
      var x=proxima(r),sp=li.querySelector('.f-prox');
      if(x){var t=faltan(x,r); if(t){sp.textContent=' · '+t; if(/hoy|ahora|mañana|faltan/.test(t)&&(x[0]-hoy)/864e5<15) li.classList.add('cerca');}
        if(r.t==='dia'||r.t==='nsem'||r.t==='pascua'){li.querySelector('.f-insignia b').textContent=x[0].getDate();
          li.querySelector('.f-insignia span').textContent=MC[x[0].getMonth()];}}
      orden.push([x?+x[0]:9e15,li]);});
    orden.sort(function(a,b){return a[0]-b[0];}).forEach(function(o){lista.appendChild(o[1]);});}
  // portada
  var sec=document.getElementById('proximas-fiestas');
  if(sec){var datos=[];try{datos=JSON.parse(document.getElementById('datos-fiestas').textContent);}catch(e){}
    var lim=sum(hoy,62),sel=[];
    datos.forEach(function(f){var x=proxima(f.r);if(x&&x[0]<=lim&&f.r.t!=='mes')sel.push([x,f]);});
    sel.sort(function(a,b){return a[0][0]-b[0][0];});
    if(sel.length){var h='';sel.slice(0,8).forEach(function(s){var x=s[0],f=s[1];
      h+='<a class="tarjeta-fiesta'+(f.e==='pendiente'?' pend':'')+'" href="'+f.u+'">'+
        '<div class="f-insignia"><b>'+x[0].getDate()+'</b><span>'+MC[x[0].getMonth()]+'</span></div>'+
        '<div class="f-texto"><h3>'+f.n.replace(/</g,'&lt;')+'</h3><p>'+f.p.replace(/</g,'&lt;')+(f.e==='pendiente'?' · por visitar':'')+
        '</p><small>'+faltan(x,f.r)+'</small></div></a>';});
      sec.querySelector('.rejilla-fiestas').innerHTML=h;sec.hidden=false;}}
})();
"""

CSS_FIESTAS = """
.fiestas .lista-fiestas{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.lista-fiestas li{display:flex;gap:14px;align-items:flex-start;padding:12px;border-radius:14px;background:var(--tarjeta);box-shadow:var(--sombra)}
.lista-fiestas li.cerca{outline:2px solid var(--acento)}
.f-insignia{flex:none;width:62px;border-radius:12px;overflow:hidden;text-align:center;background:var(--papel);border:1px solid var(--linea)}
.f-insignia b{display:block;font:600 22px/1.15 var(--f-titulo);padding:7px 2px 3px;color:var(--tinta)}
.f-insignia span{display:block;background:var(--acento);color:#fff;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;padding:2px 0}
.f-texto h3{font:600 18px/1.25 var(--f-titulo);margin:2px 0 3px}
.f-cuando{margin:0;color:var(--tinta-2);font-size:14px}
.f-prox{color:var(--acento);font-weight:600}
.f-detalle{margin:5px 0 0;font-size:14px;color:var(--tinta-2)}
.proximas{padding-top:44px}
.proximas>h2{font:600 34px/1.1 var(--f-titulo);margin:0 0 4px}
.proximas>p{color:var(--tinta-2);margin:0 0 18px}
.rejilla-fiestas{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.tarjeta-fiesta{display:flex;gap:12px;align-items:center;padding:12px;border-radius:14px;background:var(--tarjeta);box-shadow:var(--sombra);
  text-decoration:none;color:var(--tinta);transition:transform .15s}
.tarjeta-fiesta:hover{transform:translateY(-2px)}
.tarjeta-fiesta.pend .f-insignia span{background:var(--pendiente)}
.tarjeta-fiesta p{margin:0;color:var(--tinta-2);font-size:14px}
.tarjeta-fiesta small{color:var(--acento);font-weight:600}
"""


# ---------------------------------------------------------------------------- notas: «Mi cuaderno»
def _formato_nota(texto: str) -> str:
    """Párrafos, listas («- »), frases destacadas («> » o «★») y **negrita**."""
    def linea(t):
        t = e(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        return t
    bloques = [b.strip() for b in (texto or "").replace("\r", "").split("\n\n") if b.strip()]
    html_ = []
    for b in bloques:
        lineas = [l.strip() for l in b.split("\n") if l.strip()]
        if all(re.match(r"^[-•*]\s+", l) for l in lineas):
            html_.append("<ul>" + "".join(f"<li>{linea(re.sub(r'^[-•*]\s+', '', l))}</li>" for l in lineas) + "</ul>")
        elif all(l.startswith((">", "★", "⭐")) for l in lineas):
            html_.append('<p class="destacado"><span>' + "<br>".join(linea(l.lstrip(">★⭐ ")) for l in lineas) + "</span></p>")
        else:
            html_.append("<p>" + "<br>".join(linea(l) for l in lineas) + "</p>")
    return "\n".join(html_)


def bloque_notas(p: dict, autor: str, cuando: str, a_mano: bool) -> str:
    if not (p.get("notas") or "").strip():
        return ""
    propias = [f for f in p.get("fotos", []) if not f.get("credito")]
    foto = next((f for f in propias if f["archivo"] != p.get("portada")), propias[0] if propias else None)
    polaroid = (f'<figure class="polaroid"><img src="mini/{e(foto["archivo"])}" alt="" loading="lazy">'
                f'<figcaption>{e(foto.get("pie") or p["nombre"])}</figcaption></figure>') if foto else ""
    firma = f'<p class="firma">— {e(autor)}</p>' if autor else ""
    return (f'<section class="cuaderno{" a-mano" if a_mano else ""}"><div class="hoja"><span class="cinta"></span>{polaroid}'
            f'<header><h2>Mi cuaderno</h2>{f"<time>{e(cuando)}</time>" if cuando else ""}</header>'
            f'<div class="escrito">{_formato_nota(p["notas"])}{firma}</div></div></section>')


FUENTE_MANO = ('<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&display=swap" rel="stylesheet">')

CSS_NOTAS = """
.cuaderno{margin:6px 0 30px}
.cuaderno .hoja{position:relative;padding:30px 30px 26px 56px;border-radius:6px 16px 16px 6px;
  background:color-mix(in srgb,var(--tarjeta) 92%,#f3d98b);box-shadow:var(--sombra),0 1px 0 var(--linea);
  --renglon:30px;background-image:linear-gradient(90deg,transparent 38px,color-mix(in srgb,var(--acento) 45%,transparent) 38px,
  color-mix(in srgb,var(--acento) 45%,transparent) 40px,transparent 40px),
  repeating-linear-gradient(180deg,transparent 0,transparent calc(var(--renglon) - 1px),color-mix(in srgb,var(--linea) 80%,transparent) calc(var(--renglon) - 1px),
  color-mix(in srgb,var(--linea) 80%,transparent) var(--renglon));background-position:0 0,0 18px}
.cuaderno .cinta{position:absolute;top:-12px;left:50%;width:120px;height:28px;transform:translateX(-50%) rotate(-3deg);
  background:color-mix(in srgb,var(--acento-2) 45%,transparent);box-shadow:0 1px 2px rgba(0,0,0,.08)}
.cuaderno header{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:8px}
.cuaderno h2{margin:0;font:600 28px var(--f-titulo)}
.cuaderno time{color:var(--tinta-2);font-size:14px}
.cuaderno .escrito{font-size:17px;line-height:var(--renglon)}
.cuaderno .escrito p,.cuaderno .escrito ul{margin:0 0 var(--renglon)}
.cuaderno .escrito ul{list-style:none;padding:0}
.cuaderno .escrito li::before{content:"✓";color:var(--acento);font-weight:700;margin-right:10px}
.cuaderno .destacado{font-style:italic}
.cuaderno .destacado::before{content:"★";color:var(--acento);font-style:normal;margin-right:8px}
.cuaderno .destacado span{background:linear-gradient(transparent 60%,color-mix(in srgb,var(--acento-2) 32%,transparent) 60%);
  -webkit-box-decoration-break:clone;box-decoration-break:clone;padding:0 3px}
.cuaderno .firma{text-align:right;color:var(--tinta-2);font-style:italic}
.cuaderno .polaroid{float:right;width:190px;margin:-4px -6px 12px 22px;padding:9px 9px 6px;background:#fff;transform:rotate(3deg);
  box-shadow:0 6px 18px rgba(0,0,0,.18)}
.cuaderno .polaroid img{width:100%;aspect-ratio:1;object-fit:cover;display:block}
.cuaderno .polaroid figcaption{font:600 18px "Caveat",cursive;color:#444;text-align:center;line-height:1.4;padding-top:4px}
.cuaderno.a-mano .escrito{font-family:"Caveat",cursive;font-size:24px}
.cuaderno.a-mano .escrito p,.cuaderno.a-mano .escrito li{letter-spacing:.01em}
.cuaderno::after{content:"";display:table;clear:both}
@media (max-width:600px){.cuaderno .hoja{padding:26px 18px 20px 46px;background-position:-8px 0,0 18px}
  .cuaderno .polaroid{width:120px;margin:-2px -4px 8px 12px}}
"""


def tiempo_mini(lat, lon) -> str:
    """Píldora pequeña en la cabecera del pueblo; al pulsarla se despliega la previsión."""
    if lat is None or lon is None:
        return ""
    return (f'<div class="tiempo-mini" data-lat="{lat}" data-lon="{lon}" hidden>'
            '<button class="t-boton" type="button" aria-expanded="false" title="Ver la previsión">'
            '<span class="t-icono"></span><b class="t-grados"></b><span class="t-txt"></span><span class="t-flecha">▾</span></button>'
            '<div class="t-panel" hidden><h3>El tiempo ahora</h3><p class="t-detalle"></p><ol class="t-dias"></ol><p class="t-sol"></p>'
            '<p class="fuente">Previsión de <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a></p></div></div>')


JS_FICHA_LUGAR = r"""
(function(){
  var tarjetas=document.querySelectorAll('.lugar[data-ficha]'); if(!tarjetas.length) return;
  var caja=document.createElement('div'); caja.className='ficha-lugar'; caja.hidden=true;
  caja.innerHTML='<div class="fl-hoja" role="dialog" aria-modal="true"><button class="fl-cerrar" aria-label="Cerrar">✕</button>'+
    '<div class="fl-foto"></div><div class="fl-cuerpo"><h3></h3><p class="fl-desc"></p><div class="fl-texto"></div>'+
    '<div class="fl-botones"></div><p class="fl-fuente"></p></div></div>';
  document.body.appendChild(caja);
  var $=function(s){return caja.querySelector(s);};
  function cerrar(){caja.hidden=true;document.body.classList.remove('sin-scroll');}
  $('.fl-cerrar').onclick=cerrar;
  caja.addEventListener('click',function(ev){if(ev.target===caja)cerrar();});
  document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&!caja.hidden)cerrar();});
  function esc(t){return String(t||'').replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function botones(url,lat,lon){var h='';
    if(lat!=null) h+='<a class="boton" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination='+lat+','+lon+'">🚗 Cómo llegar</a>';
    if(url) h+='<a class="boton sec" target="_blank" rel="noopener" href="'+esc(url)+'">Leer más</a>';
    $('.fl-botones').innerHTML=h;}
  function resumen(titulo){
    return fetch('https://es.wikipedia.org/api/rest_v1/page/summary/'+encodeURIComponent(titulo)).then(function(r){if(!r.ok)throw 0;return r.json();});}
  function pintarWiki(s,url){
    if(s.description) $('.fl-desc').textContent=s.description;
    if(s.extract) $('.fl-texto').innerHTML='<p>'+esc(s.extract)+'</p>';
    var img=(s.originalimage&&s.originalimage.width<=1600?s.originalimage.source:(s.thumbnail&&s.thumbnail.source));
    if(img&&!$('.fl-foto img')) $('.fl-foto').innerHTML='<img alt="" src="'+esc(img)+'">';
    var c=s.coordinates||{}; if(c.lat!=null) botones(url,c.lat,c.lon);
    $('.fl-fuente').textContent='Texto de Wikipedia (CC BY-SA 4.0).';}
  [].forEach.call(tarjetas,function(t){t.addEventListener('click',function(ev){
    ev.preventDefault();
    var url=t.getAttribute('href'), img=t.querySelector('img'), cred=t.querySelector('.credito');
    $('h3').textContent=t.querySelector('b').textContent;
    $('.fl-desc').textContent=''; $('.fl-texto').innerHTML='<p class="fl-cargando">Cargando…</p>'; $('.fl-fuente').textContent='';
    $('.fl-foto').innerHTML=img?'<img alt="" src="'+esc(img.getAttribute('src'))+'">'+(cred?'<small>'+esc(cred.textContent)+'</small>':''):'';
    caja.classList.toggle('sin-foto',!img);
    var la=t.dataset.lat?+t.dataset.lat:null, lo=t.dataset.lon?+t.dataset.lon:null;
    botones(url,la,lo);
    caja.hidden=false; document.body.classList.add('sin-scroll');
    if(/openstreetmap\.org/.test(url||'')){ $('.fl-texto').innerHTML=''; $('.fl-fuente').textContent='Datos de OpenStreetMap.';
      $('.fl-botones a.sec')&&($('.fl-botones a.sec').textContent='Ver en el mapa'); return; }
    var m=/wikipedia\.org\/wiki\/(.+)$/.exec(url||''), q=/wikidata\.org\/wiki\/(Q\d+)/.exec(url||'');
    var p;
    if(m) p=resumen(decodeURIComponent(m[1])).then(function(s){pintarWiki(s,url);});
    else if(q) p=fetch('https://www.wikidata.org/wiki/Special:EntityData/'+q[1]+'.json').then(function(r){return r.json();}).then(function(d){
        var e=d.entities[q[1]]||{}, desc=((e.descriptions||{}).es||{}).value, co=(((e.claims||{}).P625||[])[0]||{}).mainsnak;
        var v=co&&co.datavalue&&co.datavalue.value, wl=((e.sitelinks||{}).eswiki||{}).title;
        if(desc) $('.fl-desc').textContent=desc.charAt(0).toUpperCase()+desc.slice(1);
        $('.fl-texto').innerHTML=''; if(v) botones(url,v.latitude,v.longitude);
        $('.fl-fuente').textContent='Datos de Wikidata.';
        if(wl) return resumen(wl).then(function(s){pintarWiki(s,'https://es.wikipedia.org/wiki/'+encodeURIComponent(wl.replace(/ /g,'_')));});
      });
    else p=Promise.reject();
    p.catch(function(){ if($('.fl-cargando')) $('.fl-texto').innerHTML='<p>No he podido cargar más información ahora.</p>'; });
  });});
})();
"""

CSS_MINI = """
.tiempo-mini{position:relative;display:inline-block;margin-top:14px;z-index:6}
.tiempo-mini[hidden],.t-panel[hidden]{display:none}
.t-boton{display:inline-flex;align-items:center;gap:7px;padding:6px 12px 6px 10px;border-radius:99px;border:1px solid rgba(255,255,255,.35);
  background:rgba(0,0,0,.32);color:#fff;font:500 15px var(--f-texto);cursor:pointer;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
.t-boton:hover{background:rgba(0,0,0,.45)}
.heroe.sin-foto .t-boton{background:var(--tarjeta);color:var(--tinta);border-color:var(--linea)}
.t-boton .t-icono{font-size:18px;line-height:1}
.t-boton .t-grados{font:700 16px/1 var(--f-texto)}
.t-boton .t-txt{font-weight:500}
.t-boton .t-flecha{font-size:12px;opacity:.8;transition:transform .2s}
.tiempo-mini.abierto .t-flecha{transform:rotate(180deg)}
.t-panel{position:absolute;left:0;top:calc(100% + 8px);width:min(340px,calc(100vw - 40px));padding:14px;border-radius:14px;
  background:var(--tarjeta);color:var(--tinta);box-shadow:0 12px 32px rgba(0,0,0,.25)}
.t-panel h3{font:600 17px var(--f-titulo);margin:0 0 6px}
.t-panel .t-detalle{margin:0;font-size:14px;color:var(--tinta-2)}
.t-panel .t-detalle b{color:var(--tinta);font-size:15px}
.t-panel .fuente{margin:8px 0 0;font-size:12px;color:var(--tinta-2)}
.t-panel .fuente a{color:inherit}
.ficha-lugar{position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;padding:18px}
.ficha-lugar[hidden]{display:none}
.fl-hoja{position:relative;width:min(560px,100%);max-height:88vh;overflow:auto;background:var(--tarjeta);color:var(--tinta);border-radius:18px;
  box-shadow:0 20px 50px rgba(0,0,0,.35)}
.fl-cerrar{position:absolute;top:10px;right:10px;z-index:2;width:36px;height:36px;border-radius:50%;border:0;background:rgba(0,0,0,.5);color:#fff;font-size:16px;cursor:pointer}
.fl-foto img{display:block;width:100%;max-height:300px;object-fit:cover}
.fl-foto small{display:block;padding:4px 16px 0;font-size:11px;color:var(--tinta-2)}
.ficha-lugar.sin-foto .fl-cerrar{background:var(--papel-2);color:var(--tinta)}
.fl-cuerpo{padding:14px 20px 18px}
.fl-cuerpo h3{font:600 24px/1.2 var(--f-titulo);margin:0 40px 4px 0}
.fl-desc{margin:0 0 10px;color:var(--tinta-2);font-style:italic}
.fl-texto p{margin:0 0 10px;line-height:1.55}
.fl-botones{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
.fl-fuente{margin:12px 0 0;font-size:12px;color:var(--tinta-2)}
body.sin-scroll{overflow:hidden}
@media (max-width:600px){.ficha-lugar{align-items:flex-end;padding:0}.fl-hoja{border-radius:18px 18px 0 0;max-height:85vh}}
"""


# ---------------------------------------------------------------------------- otras fuentes
def chips_distinciones(lista) -> str:
    if not lista:
        return ""
    return '<ul class="distinciones">' + "".join(f"<li>🏅 {e(d)}</li>" for d in lista[:5]) + "</ul>"


def bloque_oficial(of) -> str:
    if not of or not of.get("url"):
        return ""
    from urllib.parse import urlparse
    dominio = urlparse(of["url"]).netloc.replace("www.", "")
    titulo = of.get("titulo") or dominio
    desc = f'<p>{e(of["descripcion"])}</p>' if of.get("descripcion") else ""
    return (f'<section class="caja oficial"><h3>🏛 Web oficial</h3><b class="of-titulo">{e(titulo)}</b>{desc}'
            f'<a class="boton sec" href="{e(of["url"])}" target="_blank" rel="noopener">Visitar {e(dominio)} →</a></section>')


ICONOS_GUIA = {"entender": "🧭", "llegar": "🚆", "ver": "👀", "hacer": "🥾", "comprar": "🛍", "comer": "🍽",
               "beber": "🍷", "dormir": "🛏", "alrededores": "🗺"}


def bloque_guia(guia: dict) -> str:
    def parr(t):
        return "".join(f"<p>{e(b.strip()).replace(chr(10), '<br>')}</p>" for b in t.split("\n\n") if b.strip())
    bloques = "".join(f'<details><summary><span>{ICONOS_GUIA.get(s["clave"], "•")}</span> {e(s["titulo"])}</summary>'
                      f'{parr(s["texto"])}</details>' for s in guia["secciones"])
    return (f'<section class="saber-mas guia"><h2>Guía de viaje</h2>{bloques}'
            f'<p class="fuente">De <a href="{e(guia.get("url"))}" target="_blank" rel="noopener">Wikivoyage</a>, '
            f'la guía de viaje libre (CC BY-SA 4.0).</p></section>')


CSS_FUENTES = """
.otra-wiki details{border-radius:12px;background:var(--tarjeta);box-shadow:var(--sombra);padding:2px 18px}
.otra-wiki summary{cursor:pointer;padding:12px 0;font:600 18px var(--f-titulo);list-style:none}
.otra-wiki summary::after{content:" +";color:var(--tinta-2)}
.otra-wiki details[open] summary::after{content:" –"}
.distinciones{list-style:none;margin:0 0 14px;padding:0;display:flex;flex-direction:column;gap:6px}
.distinciones li{font-size:13px;font-weight:600;padding:6px 10px;border-radius:10px;background:color-mix(in srgb,var(--acento-2) 14%,var(--tarjeta));
  color:var(--tinta)}
.oficial .of-titulo{display:block;font-size:15px;margin-bottom:4px}
.oficial p{margin:0 0 10px;font-size:14px;color:var(--tinta-2);line-height:1.5}
"""


# ---------------------------------------------------------------------------- última visita (portada)
def bloque_ultima(visitados: list, fecha_larga) -> str:
    con_fecha = [p for p in visitados if p.get("fechas_visita")]
    if not con_fecha:
        return ""
    p = max(con_fecha, key=lambda x: max(x["fechas_visita"]))
    fecha = max(p["fechas_visita"])
    slug = p["slug"]
    texto = (p.get("notas") or "").strip()
    origen = "notas"
    if not texto:
        texto = (p.get("texto_ia") or (p.get("wiki") or {}).get("extracto") or "").strip()
        origen = "info"
    texto = re.sub(r"\*\*|^[-•★>]\s*", "", texto.split("\n\n")[0], flags=re.M).replace("\n", " ")
    if len(texto) > 260:
        texto = texto[:texto.rfind(" ", 0, 250)] + "…"
    fotos = [f for f in p.get("fotos", []) if f["archivo"] != p.get("portada")][:3]
    portada = (f'<img src="pueblos/{e(slug)}/fotos/{e(p["portada"])}" alt="{e(p["nombre"])}" loading="lazy">'
               if p.get("portada") else f'<span class="u-sinfoto">{e(p["nombre"][:1])}</span>')
    tira = "".join(f'<img src="pueblos/{e(slug)}/mini/{e(f["archivo"])}" alt="" loading="lazy">' for f in fotos)
    n_visitas = len(p["fechas_visita"])
    return (f'<section class="ultima envoltorio" id="ultima-visita"><a class="u-tarjeta" href="pueblos/{e(slug)}/index.html">'
            f'<div class="u-foto">{portada}</div><div class="u-texto"><span class="u-sello">Última visita</span>'
            f'<h2>{e(p["nombre"])}</h2><p class="u-lugar">{e(p.get("provincia") or p.get("comunidad") or "")} · '
            f'<time data-fecha="{e(fecha)}">{e(fecha_larga(fecha))}</time>'
            f'{f" · {n_visitas}.ª visita" if n_visitas > 1 else ""}</p>'
            f'<p class="u-nota{" mia" if origen == "notas" else ""}">{e(texto)}</p>'
            f'{f"<div class={chr(34)}u-tira{chr(34)}>{tira}</div>" if tira else ""}'
            f'<span class="u-ver">Ver el pueblo →</span></div></a></section>')


JS_ULTIMA = r"""
(function(){var t=document.querySelector('.ultima time[data-fecha]');if(!t)return;
  var p=t.dataset.fecha.split('-'),d=new Date(+p[0],(+p[1]||1)-1,+p[2]||1),h=new Date();h.setHours(0,0,0,0);
  var n=Math.round((h-d)/864e5);if(p.length<3||n<0)return;
  var r=n===0?'hoy':n===1?'ayer':n<7?'hace '+n+' días':n<35?'hace '+Math.round(n/7)+' semanas':n<365?'hace '+Math.round(n/30)+' meses':'';
  if(r)t.textContent+=' ('+r+')';})();
"""

CSS_ULTIMA = """
.ultima{padding-top:34px}
.u-tarjeta{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:0;border-radius:var(--radio);overflow:hidden;
  background:var(--tarjeta);box-shadow:var(--sombra);text-decoration:none;color:var(--tinta);transition:transform .2s}
.u-tarjeta:hover{transform:translateY(-3px)}
.u-foto{min-height:280px;background:var(--papel-2)}
.u-foto img{width:100%;height:100%;object-fit:cover;display:block}
.u-sinfoto{display:grid;place-items:center;height:100%;font:600 80px var(--f-titulo);color:var(--linea)}
.u-texto{padding:26px 28px;display:flex;flex-direction:column;gap:8px;min-width:0}
.u-sello{font:600 12px/1 var(--f-texto);letter-spacing:.18em;text-transform:uppercase;color:var(--acento)}
.u-texto h2{font:600 clamp(30px,4vw,44px)/1.05 var(--f-titulo);margin:2px 0 0}
.u-lugar{margin:0;color:var(--tinta-2);font-size:15px}
.u-nota{margin:6px 0 0;line-height:1.55;color:var(--tinta-2)}
.u-nota.mia{color:var(--tinta);font-style:italic}
.u-nota.mia::before{content:"“";font:600 2.2em/0 var(--f-titulo);color:var(--acento);vertical-align:-.35em;margin-right:4px}
.u-tira{display:flex;gap:8px;margin-top:8px}
.u-tira img{width:72px;height:72px;object-fit:cover;border-radius:10px}
.u-ver{margin-top:auto;padding-top:10px;font-weight:600;color:var(--acento)}
@media (max-width:760px){.u-tarjeta{grid-template-columns:1fr}.u-foto{min-height:0;aspect-ratio:16/10}.u-texto{padding:20px}}
.m-revista .u-tarjeta,.m-album .u-tarjeta{border-radius:2px}
.m-album .u-tarjeta{background:#fbf8f1;color:#2f2a25;transform:rotate(-.6deg)}
.m-moderna .u-tarjeta{border-radius:28px}
"""
