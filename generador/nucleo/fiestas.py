"""Fiestas de cada pueblo, sin IA.

Fuentes:
  1. El artículo de Wikipedia: el apartado de fiestas y cualquier frase con «fiesta, romería, feria…» y una fecha.
  2. Wikidata: el día del santo patrón (P417 → P841 «festividad») y las fiestas registradas en el municipio.

Cada fiesta queda así:
  {"nombre": "Fiestas de La Cruz", "cuando": "14 de septiembre", "regla": {...}, "fuente": "Wikipedia"}
La «regla» sirve para calcular la próxima fecha (también en la web, con JavaScript):
  {"t": "dia", "m": 9, "d": 14, "m2": 9, "d2": 17}      del 14 al 17 de septiembre
  {"t": "nsem", "n": -1, "wd": 0, "m": 8, "finde": 0}     último domingo de agosto  (wd: 0 = domingo)
  {"t": "mes", "m": 8, "parte": "final"}                  a finales de agosto
  {"t": "pascua", "o": -2}                                 Viernes Santo (días desde el Domingo de Resurrección)
"""
import re
from datetime import date, timedelta

from .datos import normalizar

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
_M = "(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
DIAS_SEM = {"domingo": 0, "lunes": 1, "martes": 2, "miercoles": 3, "jueves": 4, "viernes": 5, "sabado": 6}
ORDINAL = {"primer": 1, "primero": 1, "primera": 1, "segundo": 2, "segunda": 2, "tercer": 3, "tercero": 3,
           "tercera": 3, "cuarto": 4, "cuarta": 4, "ultimo": -1, "ultima": -1, "penultimo": -2}
MOVILES = [   # (texto normalizado, desplazamiento desde el Domingo de Resurrección, nombre)
    ("miercoles de ceniza", -46, "Miércoles de Ceniza"), ("carnavales", -49, "Carnaval"), ("carnaval", -49, "Carnaval"),
    ("domingo de ramos", -7, "Domingo de Ramos"), ("jueves santo", -3, "Jueves Santo"),
    ("viernes santo", -2, "Viernes Santo"), ("semana santa", -7, "Semana Santa"),
    ("lunes de pascua", 1, "Lunes de Pascua"), ("domingo de resurreccion", 0, "Domingo de Resurrección"),
    ("pascua de resurreccion", 0, "Pascua"), ("ascension", 39, "Ascensión"),
    ("pentecostes", 49, "Pentecostés"), ("corpus christi", 60, "Corpus Christi"), ("corpus", 60, "Corpus Christi"),
]
CLAVES = ("fiesta", "festividad", "romeria", "feria", "procesion", "verbena", "carnaval", "semana santa",
          "festival", "patron", "patrona", "celebra", "corpus", "fiestas", "jira", "mercado medieval", "encierro",
          "pascua", "san juan", "noche de", "hogueras", "moros y cristianos")


def _plano(t: str) -> str:
    """Minúsculas y sin tildes, con la misma longitud (para poder recortar el texto original)."""
    import unicodedata
    return "".join((unicodedata.normalize("NFKD", c)[0] if c.strip() else " ").lower() for c in t)


def _mes(t: str) -> int:
    t = normalizar(t).replace("setiembre", "septiembre")
    return MESES.index(t) + 1 if t in MESES else 0


# ---------------------------------------------------------------------------- reconocer fechas
_RANGO2 = re.compile(rf"(?:del?|entre el)\s+(\d{{1,2}})\s+de\s+{_M}\s+(?:al|y el|hasta el)\s+(\d{{1,2}})\s+de\s+{_M}", re.I)
_RANGO = re.compile(rf"(?:del?|entre el|los d[ií]as)\s+(\d{{1,2}})\s+(?:al|y el|y|-|a)\s+(\d{{1,2}})\s+de\s+{_M}", re.I)
_DIA = re.compile(rf"\b(\d{{1,2}})\s+de\s+{_M}", re.I)
_NSEM = re.compile(r"\b(primer[oa]?|segund[oa]|tercer[oa]?|cuart[oa]|[uú]ltim[oa]|pen[uú]ltimo)\s+"
                   r"(fin de semana|domingo|s[aá]bado|lunes|martes|mi[eé]rcoles|jueves|viernes)\s+(?:del? mes de\s+|de\s+)"
                   + _M, re.I)
_PARTE = re.compile(rf"\b(a principios|a comienzos|al comienzo|a primeros|a mediados|a finales|al final)\s+de(?:l mes de)?\s+{_M}", re.I)
_SOLO_MES = re.compile(rf"\b(?:en|durante|el mes de|mes de)\s+{_M}\b", re.I)


def reconocer_fecha(texto: str):
    """Busca una fecha en el texto. Devuelve (regla, 'cuando' legible, (inicio, fin) del trozo) o None."""
    m = _RANGO2.search(texto)
    if m:
        d, m1, d2, m2 = int(m.group(1)), _mes(m.group(2)), int(m.group(3)), _mes(m.group(4))
        if m1 and m2 and 1 <= d <= 31 and 1 <= d2 <= 31:
            return ({"t": "dia", "m": m1, "d": d, "m2": m2, "d2": d2},
                    f"del {d} de {MESES[m1 - 1]} al {d2} de {MESES[m2 - 1]}", m.span())
    m = _RANGO.search(texto)
    if m:
        d, d2, mes = int(m.group(1)), int(m.group(2)), _mes(m.group(3))
        if mes and 1 <= d < d2 <= 31:
            return ({"t": "dia", "m": mes, "d": d, "m2": mes, "d2": d2},
                    f"del {d} al {d2} de {MESES[mes - 1]}", m.span())
    m = _NSEM.search(texto)
    if m:
        n = ORDINAL.get(normalizar(m.group(1)).replace(" ", ""), 0)
        que = normalizar(m.group(2))
        mes = _mes(m.group(3))
        if n and mes:
            finde = que == "fin de semana"
            wd = 6 if finde else DIAS_SEM.get(que, 0)
            return ({"t": "nsem", "n": n, "wd": wd, "m": mes, "finde": int(finde)},
                    f"{m.group(1).lower()} {m.group(2).lower()} de {MESES[mes - 1]}", m.span())
    m = _DIA.search(texto)
    if m:
        d, mes = int(m.group(1)), _mes(m.group(2))
        if mes and 1 <= d <= 31:
            return {"t": "dia", "m": mes, "d": d}, f"{d} de {MESES[mes - 1]}", m.span()
    n = _plano(texto)
    for clave, o, nombre in MOVILES:
        m = re.search(rf"\b{clave}\b", n)
        if m:
            return {"t": "pascua", "o": o}, nombre, m.span()
    m = _PARTE.search(texto)
    if m:
        mes = _mes(m.group(2))
        parte = {"a mediados": "mitad"}.get(m.group(1).lower(), "inicio" if "princip" in m.group(1).lower()
                                             or "comienz" in m.group(1).lower() or "primeros" in m.group(1).lower() else "final")
        if mes:
            return {"t": "mes", "m": mes, "parte": parte}, f"{m.group(1).lower()} de {MESES[mes - 1]}", m.span()
    m = _SOLO_MES.search(texto)
    if m and _mes(m.group(1)):
        mes = _mes(m.group(1))
        return {"t": "mes", "m": mes, "parte": ""}, f"en {MESES[mes - 1]}", m.span()
    return None


# ---------------------------------------------------------------------------- texto de Wikipedia
def _unidades(texto: str):
    """Trozos con sentido: líneas de lista o frases."""
    for linea in texto.splitlines():
        linea = linea.strip(" \t•▸-–*")
        if not linea or linea.startswith("=="):
            continue
        for frase in re.split(r"(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ¡¿])", linea):
            if frase.strip():
                yield frase.strip()


def _limpiar(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip(" ,:;.-–")
    t = re.sub(r"\s+(que\s+)?(se\s+(celebra|realiza|festeja|organiza|conmemora|hace|representa)n?|tiene[n]? lugar)\b", "", t, flags=re.I)
    t = re.sub(r"^(que\s+)?(se\s+(celebra|realiza|festeja|organiza|conmemora|hace|representa)n?|tiene[n]? lugar)\s+", "", t, flags=re.I)
    t = re.sub(r"^(el|la|los|las|en|durante|y|también|además)\s+", "", t, flags=re.I)
    t = re.sub(r"\s+(el|la|los|las|en|del|de|y)$", "", t, flags=re.I)
    return t.strip(" ,:;.-–")


def _nombre_y_detalle(unidad: str, tramo):
    """«Procesión de La Santuca, patrona de Liébana; desde Aniezo…» -> ('Procesión de La Santuca', 'patrona de…')."""
    t = _nombre(unidad, tramo)
    m = re.match(r"^(.{3,60}?):\s+(.+)$", t)          # «en años que terminan en 0 o 5: fiesta del…»
    if m and not re.search(r"fiesta|romer|feria|procesi|virgen|san |santa ", normalizar(m.group(1))):
        t, previo = m.group(2), m.group(1)
    else:
        previo = ""
    partes = re.split(r"\s*;\s*|\s+[—–]\s+", t, maxsplit=1)
    nombre, detalle = partes[0], (partes[1] if len(partes) > 1 else "")
    if len(nombre) > 60 and "," in nombre[15:]:
        i = nombre.index(",", 15)
        nombre, detalle = nombre[:i], (nombre[i + 1:] + ("; " + detalle if detalle else "")).strip()
    nombre, detalle = _limpiar(nombre), _limpiar(" ".join(x for x in (detalle, previo) if x))
    nombre = nombre[:1].upper() + nombre[1:]
    detalle = detalle[:1].upper() + detalle[1:] if detalle else ""
    return nombre, detalle[:160]


def _nombre(unidad: str, tramo) -> str:
    t = unidad
    if tramo:
        a, b = tramo
        antes, despues = t[:a].strip(" ,:;-–("), t[b:].strip(" ,:;-–).")
        # «14 de septiembre: fiestas de La Cruz»  /  «Las fiestas de La Cruz se celebran el 14 de septiembre»
        t = despues if (not antes or len(antes) < 4) and despues else antes if not despues else f"{antes} {despues}"
    t = _limpiar(t)
    if len(t) > 140:
        corte = t.rfind(" ", 0, 136)
        t = t[:corte] + "…"
    return t[:1].upper() + t[1:] if t else ""


def de_wikipedia(texto_articulo: str) -> list:
    """Fiestas que aparecen en el texto completo de un artículo (con '== Títulos ==')."""
    res = []
    actual_fiestas = False
    trozos_fiestas, resto = [], []
    for linea in (texto_articulo or "").splitlines():
        m = re.match(r"^(={2,6})\s*(.*?)\s*\1\s*$", linea.strip())
        if m:
            t = normalizar(m.group(2))
            if len(m.group(1)) == 2:
                actual_fiestas = any(k in t for k in ("fiesta", "festividad", "celebracion", "romeria", "tradicion",
                                                       "folclore", "cultura"))
            elif any(k in t for k in ("fiesta", "festividad", "celebracion", "romeria", "feria")):
                actual_fiestas = True
            continue
        (trozos_fiestas if actual_fiestas else resto).append(linea)
    for origen, exigir_clave in (("\n".join(trozos_fiestas), False), ("\n".join(resto), True)):
        for u in _unidades(origen):
            n = normalizar(u)
            if exigir_clave and not any(k in n for k in CLAVES):
                continue
            if not exigir_clave and not any(k in n for k in CLAVES) and not re.match(r"^\d{1,2} de ", u):
                continue
            # descartar fechas históricas («el 3 de mayo de 1808»)
            if re.search(rf"\d{{1,2}}\s+de\s+{_M}\s+de\s+\d{{3,4}}", u, re.I) and not any(
                    k in n for k in ("se celebra", "cada ano", "anualmente", "todos los anos")):
                continue
            r = reconocer_fecha(u)
            if not r:
                continue
            regla, cuando, tramo = r
            nombre, detalle = _nombre_y_detalle(u, tramo)
            if regla["t"] == "pascua":          # «Semana Santa» como nombre; lo demás, de detalle
                detalle = " ".join(x for x in (nombre, detalle) if x)
                detalle = detalle[:1].upper() + detalle[1:]
                nombre = cuando
            if len(nombre) < 5:
                continue
            f = {"nombre": nombre, "cuando": cuando, "regla": regla, "fuente": "Wikipedia"}
            if detalle:
                f["detalle"] = detalle
            res.append(f)
    return _sin_repetir(res)


def _sin_repetir(lista: list) -> list:
    vistos, salida = set(), []
    for f in lista:
        r = f["regla"]
        clave = (r.get("t"), r.get("m"), r.get("d"), r.get("o"), r.get("n"), normalizar(f["nombre"])[:25])
        clave_fecha = (r.get("t"), r.get("m"), r.get("d"), r.get("o"), r.get("n"))
        if clave in vistos or (clave_fecha in vistos and r.get("t") != "mes"):
            continue
        vistos.add(clave)
        vistos.add(clave_fecha)
        salida.append(f)
    return salida


# ---------------------------------------------------------------------------- Wikidata
def de_wikidata(sesion, wikidata_api: str, sparql: str, qid: str) -> list:
    """Festividad del patrón (P417 → P841) y fiestas registradas en el municipio."""
    res = []
    js = sesion.get(wikidata_api, params={"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"},
                    timeout=30).json()
    claims = js.get("entities", {}).get(qid, {}).get("claims", {})
    patrones = [c["mainsnak"]["datavalue"]["value"]["id"] for c in claims.get("P417", [])
                if c.get("mainsnak", {}).get("datavalue")][:4]
    if patrones:
        ent = sesion.get(wikidata_api, params={"action": "wbgetentities", "ids": "|".join(patrones),
                                               "props": "labels|claims", "languages": "es", "format": "json"},
                         timeout=30).json().get("entities", {})
        dias = {}
        for pid, e in ent.items():
            for c in e.get("claims", {}).get("P841", []):
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
                if v.get("id"):
                    dias.setdefault(pid, []).append(v["id"])
        todos = sorted({d for v in dias.values() for d in v})
        etiquetas = {}
        if todos:
            et = sesion.get(wikidata_api, params={"action": "wbgetentities", "ids": "|".join(todos[:40]),
                                                  "props": "labels", "languages": "es", "format": "json"},
                            timeout=30).json().get("entities", {})
            etiquetas = {k: v.get("labels", {}).get("es", {}).get("value", "") for k, v in et.items()}
        for pid, e in ent.items():
            santo = e.get("labels", {}).get("es", {}).get("value")
            for d in dias.get(pid, [])[:1]:
                r = reconocer_fecha(etiquetas.get(d, ""))
                if santo and r and r[0]["t"] == "dia":
                    res.append({"nombre": f"Fiesta de {santo} (patrón)", "cuando": r[1], "regla": r[0],
                                "fuente": "Wikidata"})
    consulta = f"""SELECT ?f ?fLabel ?diaLabel ?mesLabel WHERE {{
  {{ ?f wdt:P131 wd:{qid} }} UNION {{ ?f wdt:P276 wd:{qid} }}
  ?f wdt:P31/wdt:P279* ?tipo . VALUES ?tipo {{ wd:Q132241 wd:Q15275719 wd:Q1478437 wd:Q2006483 }}
  OPTIONAL {{ ?f wdt:P837 ?dia }} OPTIONAL {{ ?f wdt:P2922 ?mes }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "es,en". }}
}} LIMIT 30"""
    try:
        r = sesion.get(sparql, params={"query": consulta, "format": "json"}, timeout=40)
        r.raise_for_status()
        for b in r.json().get("results", {}).get("bindings", []):
            nombre = b.get("fLabel", {}).get("value", "")
            if not nombre or re.fullmatch(r"Q\d+", nombre):
                continue
            texto = b.get("diaLabel", {}).get("value") or (f"en {b['mesLabel']['value']}" if b.get("mesLabel") else "")
            fe = reconocer_fecha(texto) or reconocer_fecha(nombre)
            if fe:
                res.append({"nombre": nombre, "cuando": fe[1], "regla": fe[0], "fuente": "Wikidata"})
    except Exception:  # noqa: BLE001  (Wikidata a veces tarda: lo de arriba ya vale)
        pass
    return res


def juntar(*listas) -> list:
    return _sin_repetir([f for lista in listas for f in (lista or [])])


# ---------------------------------------------------------------------------- escritas a mano (editor)
def a_texto(lista: list) -> str:
    return "\n".join(f"{f['cuando']}: {f['nombre']}" + (f" — {f['detalle']}" if f.get("detalle") else "")
                     if f.get("cuando") else f["nombre"] for f in lista or [])


def del_pueblo(p: dict) -> list:
    """Las tuyas (si las has corregido en el editor) o las encontradas en internet."""
    if isinstance(p.get("fiestas"), list):
        return p["fiestas"]
    return (p.get("wiki") or {}).get("fiestas") or []


def de_texto(texto: str) -> list:
    """Una por línea: «14 de septiembre: Fiestas de La Cruz», «último domingo de agosto: San Tirso»…"""
    res = []
    for linea in (texto or "").splitlines():
        linea = linea.strip(" -•\t")
        if not linea:
            continue
        r = reconocer_fecha(linea)
        detalle = ""
        if r:
            regla, cuando, tramo = r
            nombre, detalle = _nombre_y_detalle(linea, tramo)
            nombre = nombre or linea
        else:
            regla, cuando, nombre = {"t": "nada"}, "", linea
            if ":" in linea:
                cuando, nombre = [x.strip() for x in linea.split(":", 1)]
        fi = {"nombre": nombre, "cuando": cuando, "regla": regla, "fuente": "Mía"}
        if detalle:
            fi["detalle"] = detalle
        res.append(fi)
    return res


# ---------------------------------------------------------------------------- próxima fecha (para pruebas y la app)
def pascua(anio: int) -> date:
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = (h + l_ - 7 * m + 114) % 31 + 1
    return date(anio, mes, dia)


def fecha_en(regla: dict, anio: int):
    t = regla.get("t")
    try:
        if t == "dia":
            ini = date(anio, regla["m"], regla["d"])
            fin = date(anio, regla.get("m2", regla["m"]), regla.get("d2", regla["d"]))
            return ini, max(fin, ini)
        if t == "pascua":
            d = pascua(anio) + timedelta(days=regla["o"])
            return d, d + timedelta(days=7 if regla["o"] == -7 else 0)
        if t == "nsem":
            m, wd, n = regla["m"], regla["wd"], regla["n"]
            py_wd = (wd - 1) % 7          # Python: lunes = 0
            if n > 0:
                d = date(anio, m, 1)
                d += timedelta(days=(py_wd - d.weekday()) % 7 + 7 * (n - 1))
            else:
                ult = (date(anio + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
                d = ult - timedelta(days=(ult.weekday() - py_wd) % 7 + 7 * (-n - 1))
            if d.month != m:
                return None
            return d, d + timedelta(days=1 if regla.get("finde") else 0)
        if t == "mes":
            dia = {"inicio": 1, "mitad": 10, "final": 20}.get(regla.get("parte"), 1)
            return date(anio, regla["m"], dia), date(anio, regla["m"], 28)
    except (ValueError, KeyError):
        return None
    return None


def proxima(regla: dict, hoy: date = None):
    hoy = hoy or date.today()
    for anio in (hoy.year, hoy.year + 1):
        r = fecha_en(regla, anio)
        if r and r[1] >= hoy:
            return r
    return None
