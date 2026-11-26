"""Almacén de pueblos: una carpeta por pueblo con pueblo.json y sus fotos preparadas."""
import json
import re
import shutil
import time
import unicodedata
from pathlib import Path


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni signos: sirve para comparar nombres."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def slugify(texto: str) -> str:
    return normalizar(texto).replace(" ", "-") or "pueblo"


def pueblo_vacio(nombre: str = "") -> dict:
    return {
        "slug": "",
        "nombre": nombre,
        "provincia": "",
        "comunidad": "",
        "pais": "España",
        "lat": None,
        "lon": None,
        "fechas_visita": [],      # ["2024-05-12", ...]
        "wiki": {},               # titulo, url, extracto, poblacion, altitud, superficie, escudo, web
        "texto_ia": "",
        "notas": "",
        "fotos": [],              # [{"archivo": "0001.jpg", "fecha": "...", "pie": "", "original": "..."}]
        "portada": "",
        "publicar": True,
        "estado": "visitado",     # "visitado" o "pendiente" (por visitar)
        "bonito": False,          # miembro de «Los Pueblos más Bonitos de España»
        "magico": False,          # miembro de «Pueblos Mágicos de España»
        "revisado": False,        # lo doy por bueno: no aparece en «Revisar»
        "wikidata": "",           # id de Wikidata, si se conoce
        "creado": time.strftime("%Y-%m-%d %H:%M"),
        "modificado": "",
    }


class Almacen:
    def __init__(self, carpeta: Path):
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)

    # --- rutas ---
    def carpeta_pueblo(self, slug: str) -> Path:
        return self.carpeta / slug

    def carpeta_fotos(self, slug: str) -> Path:
        c = self.carpeta / slug / "fotos"
        c.mkdir(parents=True, exist_ok=True)
        return c

    def carpeta_minis(self, slug: str) -> Path:
        c = self.carpeta / slug / "mini"
        c.mkdir(parents=True, exist_ok=True)
        return c

    # --- lectura / escritura ---
    def listar(self) -> list:
        pueblos = []
        for f in sorted(self.carpeta.glob("*/pueblo.json")):
            try:
                p = pueblo_vacio()
                p.update(json.loads(f.read_text(encoding="utf-8")))
                pueblos.append(p)
            except (OSError, ValueError):
                continue
        return pueblos

    def cargar(self, slug: str) -> dict:
        p = pueblo_vacio()
        p.update(json.loads((self.carpeta / slug / "pueblo.json").read_text(encoding="utf-8")))
        return p

    def guardar(self, p: dict):
        if not p.get("slug"):
            p["slug"] = self.slug_libre(p["nombre"], p.get("provincia", ""))
        p["modificado"] = time.strftime("%Y-%m-%d %H:%M")
        if p["fotos"] and p["portada"] not in {f["archivo"] for f in p["fotos"]}:
            p["portada"] = p["fotos"][0]["archivo"]
        p["fechas_visita"] = sorted({f for f in p["fechas_visita"] if f})
        c = self.carpeta / p["slug"]
        c.mkdir(parents=True, exist_ok=True)
        tmp = c / "pueblo.json.tmp"
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(c / "pueblo.json")

    def eliminar(self, slug: str):
        """No borra: mueve el pueblo a datos/_papelera por si te arrepientes."""
        origen = self.carpeta / slug
        if not origen.exists():
            return
        papelera = self.carpeta / "_papelera"
        papelera.mkdir(exist_ok=True)
        destino = papelera / f"{slug}-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.move(str(origen), str(destino))

    def papelera(self) -> list:
        """Pueblos borrados que siguen en datos/_papelera, el más reciente primero."""
        pap = self.carpeta / "_papelera"
        res = []
        if not pap.exists():
            return res
        for c in sorted(pap.iterdir(), reverse=True):
            if not c.is_dir() or not (c / "pueblo.json").exists():
                continue
            try:
                d = json.loads((c / "pueblo.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                d = {}
            partes = c.name.rsplit("-", 2)
            cuando = c.name
            if len(partes) == 3 and len(partes[1]) == 8 and len(partes[2]) == 6:
                f, h = partes[1], partes[2]
                cuando = f"{f[6:8]}/{f[4:6]}/{f[0:4]} {h[0:2]}:{h[2:4]}"
            res.append({"carpeta": c.name, "nombre": d.get("nombre") or partes[0], "provincia": d.get("provincia", ""),
                        "estado": d.get("estado", "visitado"), "cuando": cuando})
        return res

    def restaurar(self, carpeta: str) -> str:
        """Saca un pueblo de la papelera y lo devuelve a tus pueblos. Devuelve su slug."""
        origen = self.carpeta / "_papelera" / carpeta
        if not origen.exists():
            return ""
        try:
            d = json.loads((origen / "pueblo.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        slug = self.slug_libre(d.get("nombre") or carpeta.rsplit("-", 2)[0], d.get("provincia", ""))
        destino = self.carpeta / slug
        shutil.move(str(origen), str(destino))
        if d and d.get("slug") != slug:
            d["slug"] = slug
            (destino / "pueblo.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        return slug

    def borrar_definitivo(self, carpeta: str):
        c = self.carpeta / "_papelera" / carpeta
        if c.exists() and c.parent.name == "_papelera":
            shutil.rmtree(c, ignore_errors=True)

    # --- utilidades ---
    def slug_libre(self, nombre: str, provincia: str = "") -> str:
        base = slugify(nombre)
        if not (self.carpeta / base).exists():
            return base
        if provincia:
            con_prov = f"{base}-{slugify(provincia)}"
            if not (self.carpeta / con_prov).exists():
                return con_prov
            base = con_prov
        n = 2
        while (self.carpeta / f"{base}-{n}").exists():
            n += 1
        return f"{base}-{n}"

    def buscar(self, nombre: str, provincia: str = ""):
        """Devuelve el pueblo existente con ese nombre (y provincia, si se indica)."""
        nn, np = normalizar(nombre), normalizar(provincia)
        for p in self.listar():
            if normalizar(p["nombre"]) == nn and (not np or not p["provincia"] or normalizar(p["provincia"]) == np):
                return p
        return None

    def siguiente_nombre_foto(self, p: dict) -> str:
        usados = {f["archivo"] for f in p["fotos"]}
        n = len(usados) + 1
        while f"{n:04d}.jpg" in usados or (self.carpeta_fotos(p["slug"]) / f"{n:04d}.jpg").exists():
            n += 1
        return f"{n:04d}.jpg"


def clave_original(ruta) -> str:
    """Identifica una foto ya importada sin guardar rutas de tu ordenador (el repositorio es público)."""
    ruta = Path(ruta)
    try:
        return f"{ruta.name}|{ruta.stat().st_size}"
    except OSError:
        return ruta.name


def reparar(almacen: "Almacen", json_remoto=None) -> int:
    """Tras unir cambios de dos sitios: arregla JSON rotos y que fotos y fichas cuadren.
    Devuelve cuántos pueblos se han tocado."""
    tocados = 0
    for c in sorted(almacen.carpeta.iterdir()) if almacen.carpeta.exists() else []:
        archivo = c / "pueblo.json"
        if not c.is_dir() or c.name.startswith("_") or not archivo.exists():
            continue
        cambiado = False
        try:
            p = json.loads(archivo.read_text(encoding="utf-8"))
        except ValueError:
            texto = json_remoto(f"datos/{c.name}/pueblo.json") if json_remoto else None
            try:
                p = json.loads(texto) if texto else None
            except ValueError:
                p = None
            if p is None:
                continue
            cambiado = True
        base = pueblo_vacio()
        base.update(p)
        p = base
        en_disco = {f.name for f in (c / "fotos").glob("*.jpg")} if (c / "fotos").exists() else set()
        referidas = [f for f in p["fotos"] if f.get("archivo") in en_disco]
        if len(referidas) != len(p["fotos"]):
            cambiado = True
        nombres = {f["archivo"] for f in referidas}
        for nuevo in sorted(en_disco - nombres):
            referidas.append({"archivo": nuevo, "fecha": "", "pie": "", "original": ""})
            cambiado = True
        p["fotos"] = referidas
        if cambiado:
            p["slug"] = p.get("slug") or c.name
            almacen.guardar(p)
            tocados += 1
    return tocados
