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
