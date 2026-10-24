"""Provincias de España: en qué provincia cae un punto, nombres y proyección para dibujar."""
import json
import math
from functools import lru_cache
from pathlib import Path

from .datos import normalizar

ARCHIVO = Path(__file__).with_name("provincias.geojson")

# Nombres alternativos que pueden venir de OpenStreetMap o escribirse a mano
ALIAS = {
    "alacant": "03", "alicante alacant": "03", "illes balears": "07", "baleares": "07", "balears": "07",
    "castello": "12", "castellon castello": "12", "castello castellon": "12", "valencia valencia": "46",
    "araba": "01", "alava": "01", "araba alava": "01", "bizkaia": "48", "gipuzkoa": "20",
    "la coruna": "15", "coruna": "15", "a coruna": "15", "gerona": "17", "lerida": "25", "orense": "32",
    "navarra": "31", "nafarroa": "31", "asturias": "33", "principado de asturias": "33",
    "madrid": "28", "comunidad de madrid": "28", "murcia": "30", "region de murcia": "30",
    "cantabria": "39", "la rioja": "26", "rioja": "26",
}


@lru_cache(maxsize=1)
def provincias() -> list:
    """[{id, nombre, oficial, comunidad, poligonos: [[(lon,lat),...] anillos...], caja}]"""
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    res = []
    for f in datos["features"]:
        g = f["geometry"]
        polis = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        anillos = [[[tuple(pt) for pt in anillo] for anillo in poli] for poli in polis]
        xs = [p[0] for poli in anillos for p in poli[0]]
        ys = [p[1] for poli in anillos for p in poli[0]]
        res.append({"id": f["id"], **f["properties"], "poligonos": anillos,
                    "caja": (min(xs), min(ys), max(xs), max(ys))})
    return res


def por_id(pid: str):
    return next((p for p in provincias() if p["id"] == pid), None)


def _dentro_anillo(x, y, anillo) -> bool:
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i]
        xj, yj = anillo[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            dentro = not dentro
        j = i
    return dentro


def provincia_de_punto(lat, lon):
    if lat is None or lon is None:
        return None
    for p in provincias():
        x0, y0, x1, y1 = p["caja"]
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poli in p["poligonos"]:
            if _dentro_anillo(lon, lat, poli[0]) and not any(_dentro_anillo(lon, lat, h) for h in poli[1:]):
                return p["id"]
    # Costa: el punto puede caer un poco fuera del contorno simplificado -> la más cercana (< ~10 km)
    mejor, dist = None, 0.1
    for p in provincias():
        for poli in p["poligonos"]:
            for (x, y) in poli[0][::3]:
                d = math.hypot((x - lon) * math.cos(math.radians(lat)), y - lat)
                if d < dist:
                    mejor, dist = p["id"], d
    return mejor


def provincia_por_nombre(nombre: str):
    n = normalizar(nombre)
    if not n:
        return None
    if n in ALIAS:
        return ALIAS[n]
    for p in provincias():
        if n in (normalizar(p["nombre"]), normalizar(p["oficial"])) or n in normalizar(p["oficial"]).split(" "):
            return p["id"]
    return None


def provincia_de(pueblo: dict):
    """Provincia (id) de un pueblo: por coordenadas y, si no hay, por el nombre escrito."""
    return provincia_de_punto(pueblo.get("lat"), pueblo.get("lon")) or provincia_por_nombre(pueblo.get("provincia", ""))


# ---------------------------------------------------------------- dibujo (programa)
CANARIAS = ("35", "38")
DESPLAZA_CANARIAS = (6.0, 6.8)   # se dibujan abajo a la izquierda, como en los mapas habituales
COS = math.cos(math.radians(40))


def proyectar(lon, lat, canarias=None):
    if canarias is None:
        canarias = lon < -12.5 and lat < 30.5
    if canarias:
        lon, lat = lon + DESPLAZA_CANARIAS[0], lat + DESPLAZA_CANARIAS[1]
    return lon * COS, -lat


def limites():
    xs, ys = [], []
    for p in provincias():
        can = p["id"] in CANARIAS
        for poli in p["poligonos"]:
            for lon, lat in poli[0]:
                x, y = proyectar(lon, lat, can)
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def desproyectar(x, y):
    """Inverso de proyectar(): coordenadas de dibujo -> (lon, lat)."""
    lon, lat = x / COS, -y
    if lat < 37.2 and lon < -5.5 and lat > 34.5 and lon > -12.5:   # dentro del recuadro de Canarias
        lon2, lat2 = lon - DESPLAZA_CANARIAS[0], lat - DESPLAZA_CANARIAS[1]
        if provincia_de_punto(lat2, lon2) in CANARIAS:
            return lon2, lat2
    return lon, lat


@lru_cache(maxsize=1)
def proyectadas() -> list:
    """[(id, [anillo_exterior_proyectado, ...])] listo para dibujar."""
    res = []
    for p in provincias():
        can = p["id"] in CANARIAS
        res.append((p["id"], [[proyectar(lon, lat, can) for lon, lat in poli[0]] for poli in p["poligonos"]]))
    return res


def caja_canarias():
    xs, ys = [], []
    for pid, anillos in proyectadas():
        if pid in CANARIAS:
            for a in anillos:
                xs += [x for x, _ in a]
                ys += [y for _, y in a]
    return min(xs) - 0.35, min(ys) - 0.35, max(xs) + 0.35, max(ys) + 0.35
