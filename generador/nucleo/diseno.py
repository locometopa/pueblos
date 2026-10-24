"""Opciones de diseño de la web: paletas, modo claro/oscuro, tipografías, cabeceras, fondo y secciones."""
import re
from urllib.parse import quote

DEFECTO = {
    "cabecera": "dibujo",        # dibujo | foto | collage | sencilla
    "paleta": "teja",            # teja | mediterraneo | norte | piedra | lavanda
    "modo": "auto",              # auto | claro | oscuro
    "tipografia": "clasica",     # clasica | moderna | redonda | elegante | sencilla
    "azulejos": True,
    "bandas": True,
    "mostrar_mapa": True,
    "mapa_primero": True,
    "mostrar_extra": True,       # «Qué ver» y «Para saber más» en cada pueblo
    "cronologia": True,          # línea del tiempo de viajes en la portada
    "compartir": True,           # foto y título al compartir por WhatsApp, Telegram…
    "instalable": True,          # se puede instalar en el móvil como una app
    "tiempo": True,              # el tiempo que hace en la ficha de cada pueblo
    "mapa_pueblo": True,         # mapa pequeño y «Cómo llegar» en cada pueblo
    "cercanos": True,            # «Cerca de aquí»: tus otros pueblos cercanos
    "fiestas": True,             # fiestas de cada pueblo y «Próximas fiestas» en la portada
    "notas_a_mano": True,        # «Mi cuaderno» con letra manuscrita
}

CABECERAS = {
    "dibujo": ("Dibujo", "Un pueblo dibujado; de noche en modo oscuro"),
    "foto": ("Foto grande", "Una de tus fotos a lo ancho, distinta en cada visita"),
    "collage": ("Collage", "Tus fotos como polaroids junto al título"),
    "sencilla": ("Sencilla", "Solo el título y las cifras"),
}

TIPOGRAFIAS = {
    "clasica": ("Clásica", '"Fraunces",Georgia,serif', '"Source Sans 3","Segoe UI",system-ui,sans-serif',
                "family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Source+Sans+3:wght@400;500;600"),
    "moderna": ("Moderna", '"Playfair Display",Georgia,serif', '"Inter","Segoe UI",system-ui,sans-serif',
                "family=Playfair+Display:wght@500;600;700&family=Inter:wght@400;500;600"),
    "redonda": ("Redonda", '"Nunito","Segoe UI",system-ui,sans-serif', '"Nunito","Segoe UI",system-ui,sans-serif',
                "family=Nunito:wght@400;600;700;800"),
    "elegante": ("Elegante", '"Cormorant Garamond",Georgia,serif', '"Work Sans","Segoe UI",system-ui,sans-serif',
                 "family=Cormorant+Garamond:wght@500;600;700&family=Work+Sans:wght@400;500;600"),
    "sencilla": ("Sencilla (del sistema)", 'Georgia,"Times New Roman",serif', 'system-ui,"Segoe UI",Roboto,sans-serif', ""),
}

_CLAVES = ("papel", "papel-2", "tinta", "tinta-2", "acento", "acento-2", "linea", "tarjeta", "banda",
           "rasca", "rasca-2", "pendiente", "mar", "vecino", "cielo-1", "cielo-2")


def _p(*valores):
    return dict(zip(_CLAVES, valores))


# (nombre, claro, oscuro)
PALETAS = {
    "teja": ("Teja", _p("#f5efe3", "#ece3d2", "#2a2621", "#6b6257", "#a8472a", "#7c6a3b", "#d8ccb6", "#fffaf0", "#efe4cf",
                        "#cfc6b4", "#bdb29c", "#2f6f6a", "#eef1ec", "#e4dccd", "#f7d9a8", "#f8ead2"),
             _p("#1c1a17", "#26231f", "#efe7d8", "#b3a893", "#e0835f", "#c9b27a", "#3a352e", "#24211d", "#24211d",
                "#3b3630", "#4a443c", "#7fc4bb", "#1f2326", "#2c2924", "#0f1830", "#1d2236")),
    "mediterraneo": ("Azul Mediterráneo",
                     _p("#f1f5f8", "#e1e9ef", "#1d2a35", "#566673", "#1f6aa5", "#b07d2b", "#cad7e1", "#ffffff", "#e4edf4",
                        "#cdd5dc", "#bac4cd", "#c25b35", "#e2eef7", "#e3e5e3", "#bfe0f5", "#e6f2fa"),
                     _p("#12181d", "#1b232a", "#e5edf3", "#9db0bf", "#5aa9e6", "#e0b25c", "#2a3640", "#18212a", "#161e25",
                        "#2e3a44", "#3a4752", "#f0916b", "#142029", "#222a31", "#0b1a2e", "#16283d")),
    "norte": ("Verde norte",
              _p("#f0f4ec", "#e0e8d9", "#1e2a20", "#5a6a5c", "#2e7a4d", "#8a6a34", "#cbd8c2", "#fbfdf8", "#e5ede0",
                 "#cbd2c3", "#b9c2b0", "#a8472a", "#e6efee", "#e2e2d6", "#d7ead2", "#edf4e8"),
              _p("#141a15", "#1c241d", "#e4ede5", "#9fb2a2", "#6cc391", "#d5b26e", "#2b372d", "#19211a", "#172019",
                 "#2f3a31", "#3b483d", "#e0835f", "#152024", "#232a24", "#0d1a18", "#172622")),
    "piedra": ("Piedra y mostaza",
               _p("#f2f1ee", "#e5e3de", "#252422", "#65625c", "#9c6b12", "#4f5b66", "#d4d0c8", "#fdfcfa", "#eae7e1",
                  "#ceccc6", "#bdbab3", "#3f6f8f", "#eceeef", "#e2e0db", "#e8e2d3", "#f1eee7"),
               _p("#181817", "#222220", "#ecebe7", "#aaa79f", "#e2b14f", "#9fb0c0", "#34332f", "#1f1f1d", "#1c1c1a",
                  "#353430", "#42413c", "#8fc0e0", "#1c1f21", "#282725", "#14161c", "#1f2128")),
    "lavanda": ("Lavanda",
                _p("#f5f2f7", "#e9e2ef", "#2a2430", "#6b6276", "#6a4c9c", "#a05f78", "#dbd0e5", "#fdfbff", "#eee7f4",
                   "#d4cddb", "#c3bacc", "#2f7a6e", "#eef0f6", "#e6e1e8", "#e5d6f0", "#f3ecf7"),
                _p("#19161d", "#231e29", "#ede6f3", "#b0a4bf", "#b69be8", "#e09ab5", "#352d3e", "#201b26", "#1d1923",
                   "#382f42", "#463b52", "#7fd1c2", "#1b1c26", "#29242f", "#120e24", "#1f1834")),
}


def normalizar(d) -> dict:
    res = dict(DEFECTO)
    res.update({k: v for k, v in (d or {}).items() if k in DEFECTO})
    if res["cabecera"] not in CABECERAS:
        res["cabecera"] = DEFECTO["cabecera"]
    if res["paleta"] not in PALETAS:
        res["paleta"] = DEFECTO["paleta"]
    if res["tipografia"] not in TIPOGRAFIAS:
        res["tipografia"] = DEFECTO["tipografia"]
    if res["modo"] not in ("auto", "claro", "oscuro"):
        res["modo"] = "auto"
    return res


def _vars(colores: dict) -> str:
    return ";".join(f"--{k}:{v}" for k, v in colores.items())


def _bloques_oscuros(css: str):
    """Posiciones (inicio, fin, interior) de cada @media (prefers-color-scheme:dark){...}."""
    for m in re.finditer(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{", css):
        nivel, i = 1, m.end()
        while i < len(css) and nivel:
            nivel += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        yield m.start(), i, css[m.end():i - 1]


def aplicar_modo(css: str, modo: str) -> str:
    if modo == "auto":
        return css
    trozos, ultimo = [], 0
    for ini, fin, interior in _bloques_oscuros(css):
        trozos.append(css[ultimo:ini])
        if modo == "oscuro":
            trozos.append(interior)
        ultimo = fin
    trozos.append(css[ultimo:])
    return "".join(trozos)


def css_final(css_base: str, d: dict) -> str:
    """Estilo de la web con el diseño elegido aplicado."""
    d = normalizar(d)
    _, claro, oscuro = PALETAS[d["paleta"]]
    css = css_base
    # el dibujo de azulejos toma el color de la paleta
    css = css.replace("%23a8472a", quote(claro["acento"])).replace("%23e0835f", quote(oscuro["acento"]))
    _, f_titulo, f_texto, _ = TIPOGRAFIAS[d["tipografia"]]
    extra = [f":root{{{_vars(claro)};--f-titulo:{f_titulo};--f-texto:{f_texto}}}",
             f"@media (prefers-color-scheme:dark){{:root{{{_vars(oscuro)}}}}}"]
    if not d["azulejos"]:
        extra.append("body{background-image:none!important}")
    if not d["bandas"]:
        extra.append(".banda,.comunidad:nth-of-type(odd),.pendientes{background:none!important;box-shadow:none!important}")
    css = css + "\n/* ---- diseño elegido ---- */\n" + "\n".join(extra) + "\n"
    return aplicar_modo(css, d["modo"])


def enlace_fuentes(d: dict) -> str:
    familias = TIPOGRAFIAS[normalizar(d)["tipografia"]][3]
    if not familias:
        return ""
    return ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link href="https://fonts.googleapis.com/css2?{familias}&display=swap" rel="stylesheet">')


def favicon_svg(d: dict) -> str:
    """Icono por defecto (una casita con campanario) en el color de la paleta."""
    acento = PALETAS[normalizar(d)["paleta"]][1]["acento"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="{acento}"/>'
            '<path d="M12 50 V32 L24 22 L36 32 V50Z M36 50 V26 L43 15 L50 26 V50Z" fill="#fff"/>'
            f'<rect x="21" y="38" width="6" height="12" rx="3" fill="{acento}"/><circle cx="43" cy="31" r="3" fill="{acento}"/></svg>')


def color_tema(d: dict) -> str:
    d = normalizar(d)
    return PALETAS[d["paleta"]][2 if d["modo"] == "oscuro" else 1]["papel"]
