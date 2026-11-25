"""PUEBLOS — programa para crear y publicar la web de los pueblos que has visitado."""
import io
import queue
import threading
import traceback
import webbrowser
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps, ImageTk

from nucleo import fotos as F
from nucleo import importar as I
from nucleo import mapa
from nucleo import tema
from nucleo import web
from nucleo import diseno as D
from nucleo import actualizar
from nucleo import accesos
from nucleo.github import GitHubAPI
from nucleo.tema import boton, color, fuente, fuente_titulo
from nucleo.commons import Commons
from nucleo.config import Config, COMUNIDADES, VERSION, NOMBRE_PROGRAMA, BASE
from nucleo.datos import Almacen, normalizar, pueblo_vacio
from nucleo.geo import Geocodificador
from nucleo import ia as IA
from nucleo import fiestas as FI
from nucleo.ia import generar_texto, ErrorIA
from nucleo.publicar import url_web, ErrorPublicar, git_disponible, configurar_token
from nucleo.sincronizar import Sincronizador
from nucleo.wiki import Wikipedia

TIPOS_FOTO = [("Fotos", " ".join(f"*{x}" for x in sorted(F.EXTENSIONES))), ("Todos", "*.*")]
TEMAS = {"Sistema": "System", "Claro": "Light", "Oscuro": "Dark"}


def fecha_ok(t: str) -> bool:
    """'2024-05-12', '2024-05' o '2024', con mes y día reales."""
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            datetime.strptime(t, fmt)
            return len(t) in (4, 7, 10)
        except ValueError:
            continue
    return False


def recorte(img: Image.Image, ancho: int, alto: int) -> Image.Image:
    """Recorta la imagen para llenar exactamente ancho x alto (como object-fit: cover)."""
    return ImageOps.fit(img.convert("RGB"), (ancho, alto), Image.LANCZOS)


# ============================================================================ mapa pequeño (fichas y «¿Cuál es?»)
def mini_mapa(coordenadas, ancho, alto):
    """España con su provincia resaltada y una chincheta en el punto. Sin internet: con los contornos del programa."""
    S = 3
    W, H = ancho * S, alto * S
    fondo, tapada = color(tema.MAPA_FONDO), color(tema.MAPA_TAPADA)
    borde, acento = color(tema.MAPA_BORDE), color(tema.ACENTO)
    img = Image.new("RGB", (W, H), fondo)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = mapa.limites()
    m = 6 * S
    esc = min((W - 2 * m) / (x1 - x0), (H - 2 * m) / (y1 - y0))
    ox = (W - (x1 - x0) * esc) / 2 - x0 * esc
    oy = (H - (y1 - y0) * esc) / 2 - y0 * esc
    pid = mapa.provincia_de_punto(*coordenadas) if coordenadas else None
    for prov, anillos in mapa.proyectadas():
        for a in anillos:
            if len(a) > 2:
                pts = [(x * esc + ox, y * esc + oy) for x, y in a]
                d.polygon(pts, fill=acento if prov == pid else tapada, outline=borde)
    if coordenadas:
        x, y = mapa.proyectar(coordenadas[1], coordenadas[0])
        x, y = x * esc + ox, y * esc + oy
        r = 5 * S
        d.ellipse([x - r, y - r, x + r, y + r], fill="#ffffff", outline=acento, width=2 * S)
        d.ellipse([x - 2 * S, y - 2 * S, x + 2 * S, y + 2 * S], fill=acento)
    else:
        try:
            d.text((W / 2, H - 10 * S), "Sin ubicación", fill=borde, anchor="mm", font_size=13 * S)
        except TypeError:          # Pillow antiguo
            pass
    return img.resize((ancho * 2, alto * 2), Image.LANCZOS)


# ============================================================================ vista: mapa
class VistaMapa(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.contenedor, fg_color="transparent")
        self.app = app
        self.pueblos = []
        self.visitadas = {}
        self._foto_mapa = None
        self._trabajo = None
        self._geometria = None
        self._prov_resaltada = None

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", padx=28, pady=(22, 6))
        ctk.CTkLabel(cab, text="Mi mapa de España", font=fuente_titulo(28)).pack(anchor="w")
        self.lbl_sub = ctk.CTkLabel(cab, text="", text_color=tema.TINTA_2, font=fuente(14))
        self.lbl_sub.pack(anchor="w")

        self.cifras = ctk.CTkFrame(self, fg_color="transparent")
        self.cifras.pack(fill="x", padx=22, pady=(8, 10))
        self.tarjetas = {}
        for i, (clave, texto) in enumerate((("pueblos", "pueblos visitados"), ("provincias", "provincias destapadas"),
                                            ("comunidades", "comunidades"), ("pendientes", "por visitar"))):
            t = ctk.CTkFrame(self.cifras, corner_radius=12)
            t.grid(row=0, column=i, sticky="ew", padx=6)
            self.cifras.columnconfigure(i, weight=1)
            n = ctk.CTkLabel(t, text="0", font=fuente_titulo(30),
                             text_color=tema.PENDIENTE if clave == "pendientes" else tema.TINTA)
            n.pack(anchor="w", padx=16, pady=(12, 0))
            ctk.CTkLabel(t, text=texto, text_color=tema.TINTA_2, font=fuente(12)).pack(anchor="w", padx=16, pady=(0, 12))
            self.tarjetas[clave] = n
        self.barra = ctk.CTkProgressBar(self, height=8)
        self.barra.pack(fill="x", padx=28, pady=(0, 12))
        self.barra.set(0)

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.rowconfigure(0, weight=1)
        self.marco = ctk.CTkFrame(cuerpo, corner_radius=14)
        self.marco.grid(row=0, column=0, sticky="nsew", padx=6)
        self.lienzo = tk.Canvas(self.marco, highlightthickness=0, borderwidth=0, cursor="hand2")
        self.lienzo.pack(fill="both", expand=True, padx=8, pady=8)
        self.lienzo.bind("<Configure>", lambda e: self.programar())
        self.lienzo.bind("<Motion>", self._mover)
        self.lienzo.bind("<Leave>", lambda e: self._ocultar_globo())
        self.lienzo.bind("<Button-1>", self._clic)

        self.panel = ctk.CTkScrollableFrame(cuerpo, width=270, corner_radius=14)
        self.panel.grid(row=0, column=1, sticky="ns", padx=6)
        self._panel_inicio()

    # ------------------------------------------------------------------ datos
    def refrescar(self):
        self.pueblos = [p for p in self.app.almacen.listar() if p.get("nombre")]
        self.visitadas = {}
        for p in self.pueblos:
            p["_prov"] = mapa.provincia_de(p)
        vis = [p for p in self.pueblos if p.get("estado") != "pendiente"]
        pen = [p for p in self.pueblos if p.get("estado") == "pendiente"]
        for p in sorted(vis, key=lambda x: (x.get("fechas_visita") or [""])[-1]):
            if p["_prov"]:
                info = self.visitadas.setdefault(p["_prov"], {"n": 0, "foto": None})
                info["n"] += 1
                if p.get("portada"):
                    info["foto"] = self.app.almacen.carpeta_pueblo(p["slug"]) / "mini" / p["portada"]
        total = len(mapa.provincias())
        self.tarjetas["pueblos"].configure(text=str(len(vis)))
        self.tarjetas["provincias"].configure(text=f"{len(self.visitadas)} / {total}")
        self.tarjetas["comunidades"].configure(text=str(len({p['comunidad'] for p in vis if p['comunidad']})))
        self.tarjetas["pendientes"].configure(text=str(len(pen)))
        porc = len(self.visitadas) / total if total else 0
        self.barra.set(porc)
        self.lbl_sub.configure(text=f"Has destapado el {round(porc * 100)}% de las provincias. "
                                    "Haz clic en una provincia o en una chincheta.")
        if getattr(self, "_prov_sel", None):
            self._panel_provincia(self._prov_sel)      # que la lista de la provincia elegida esté al día
        self.programar()

    def programar(self):
        if self._trabajo:
            self.after_cancel(self._trabajo)
        self._trabajo = self.after(120, self.dibujar)

    # ------------------------------------------------------------------ dibujo
    def dibujar(self):
        self._trabajo = None
        c = self.lienzo
        W, H = c.winfo_width(), c.winfo_height()
        if W < 60 or H < 60:
            return
        c.configure(background=color(tema.MAPA_FONDO))
        x0, y0, x1, y1 = mapa.limites()
        m = 14
        esc = min((W - 2 * m) / (x1 - x0), (H - 2 * m) / (y1 - y0))
        ox = (W - (x1 - x0) * esc) / 2 - x0 * esc
        oy = (H - (y1 - y0) * esc) / 2 - y0 * esc
        self._geometria = (esc, ox, oy)
        S = 2  # se dibuja al doble y se reduce: bordes suaves

        def px(pt, k=S):
            return (pt[0] * esc + ox) * k, (pt[1] * esc + oy) * k

        img = Image.new("RGB", (W * S, H * S), color(tema.MAPA_FONDO))
        d = ImageDraw.Draw(img)
        tapada, raya = color(tema.MAPA_TAPADA), color(tema.MAPA_TAPADA_RAYA)
        borde, acento = color(tema.MAPA_BORDE), color(tema.ACENTO)
        # rayado de fondo para las tapadas (se recorta con una máscara)
        rayado = Image.new("RGB", img.size, tapada)
        dr = ImageDraw.Draw(rayado)
        for k in range(-img.size[1], img.size[0], 14):
            dr.line([(k, img.size[1]), (k + img.size[1], 0)], fill=raya, width=2)
        mascara_tapadas = Image.new("L", img.size, 0)
        dm = ImageDraw.Draw(mascara_tapadas)

        for pid, anillos in mapa.proyectadas():
            puntos = [[px(p) for p in a] for a in anillos]
            info = self.visitadas.get(pid)
            if info and info["foto"] and Path(info["foto"]).exists():
                xs = [x for a in puntos for x, _ in a]
                ys = [y for a in puntos for _, y in a]
                bx0, by0, bx1, by1 = int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1
                try:
                    with Image.open(info["foto"]) as f:
                        foto = recorte(f, max(1, bx1 - bx0), max(1, by1 - by0))
                    masc = Image.new("L", foto.size, 0)
                    md = ImageDraw.Draw(masc)
                    for a in puntos:
                        if len(a) > 2:
                            md.polygon([(x - bx0, y - by0) for x, y in a], fill=255)
                    img.paste(foto, (bx0, by0), masc)
                except Exception:  # noqa: BLE001
                    for a in puntos:
                        if len(a) > 2:
                            d.polygon(a, fill=acento)
            elif info:
                for a in puntos:
                    if len(a) > 2:
                        d.polygon(a, fill=acento)
            else:
                for a in puntos:
                    if len(a) > 2:
                        dm.polygon(a, fill=255)
        img.paste(rayado, (0, 0), mascara_tapadas)
        for pid, anillos in mapa.proyectadas():
            for a in anillos:
                if len(a) > 2:
                    d.line([px(p) for p in a] + [px(a[0])], fill=borde, width=2 if pid in self.visitadas else 1)
        cx0, cy0, cx1, cy1 = mapa.caja_canarias()
        d.rectangle([px((cx0, cy0)), px((cx1, cy1))], outline=color(tema.LINEA), width=2)

        # chinchetas (dibujadas en la imagen para que salgan redondas y suaves)
        self._pins = []
        pend_col, fondo_pin = color(tema.PENDIENTE), color(tema.TARJETA)
        orden = sorted((p for p in self.pueblos if p.get("lat") is not None),
                       key=lambda p: p.get("estado") != "pendiente")  # las visitadas encima
        for p in orden:
            x, y = px(mapa.proyectar(p["lon"], p["lat"]))
            if p.get("estado") == "pendiente":
                r = 6.5 * S
                d.ellipse([x - r, y - r, x + r, y + r], fill=fondo_pin, outline=pend_col, width=int(2.5 * S))
                d.ellipse([x - 2 * S, y - 2 * S, x + 2 * S, y + 2 * S], fill=pend_col)
            else:
                r = 6 * S
                d.ellipse([x - r, y - r, x + r, y + r], fill=acento, outline="#ffffff", width=int(2 * S))
            self._pins.append((x / S, y / S, p["slug"]))

        self._foto_mapa = ImageTk.PhotoImage(img.resize((W, H), Image.LANCZOS))
        c.delete("all")
        c.create_image(0, 0, image=self._foto_mapa, anchor="nw")
        self._prov_resaltada = None

    # ------------------------------------------------------------------ interacción
    def _a_lonlat(self, x, y):
        if not self._geometria:
            return None
        esc, ox, oy = self._geometria
        return mapa.desproyectar((x - ox) / esc, (y - oy) / esc)

    def _pin_en(self, x, y):
        mejor, dist = None, 9 ** 2
        for px_, py_, slug in getattr(self, "_pins", []):
            d = (px_ - x) ** 2 + (py_ - y) ** 2
            if d <= dist:
                mejor, dist = slug, d
        return mejor

    def _mover(self, ev):
        slug = self._pin_en(ev.x, ev.y)
        if slug:
            p = next((q for q in self.pueblos if q["slug"] == slug), None)
            if p:
                extra = "Por visitar" if p.get("estado") == "pendiente" else (
                    ", ".join(p.get("fechas_visita") or []) or "Visitado")
                self._globo(ev.x, ev.y, p["nombre"], extra)
            self._resaltar(None)
            return
        ll = self._a_lonlat(ev.x, ev.y)
        pid = mapa.provincia_de_punto(ll[1], ll[0]) if ll else None
        if not pid:
            self._ocultar_globo()
            self._resaltar(None)
            return
        prov = mapa.por_id(pid)
        info = self.visitadas.get(pid)
        n_pen = sum(1 for p in self.pueblos if p.get("_prov") == pid and p.get("estado") == "pendiente")
        texto = (f"{info['n']} {'pueblo visitado' if info['n'] == 1 else 'pueblos visitados'}" if info
                 else "Sin destapar")
        if n_pen:
            texto += f" · {n_pen} por visitar"
        self._globo(ev.x, ev.y, prov["nombre"], texto)
        self._resaltar(pid)

    def _resaltar(self, pid):
        if pid == self._prov_resaltada:
            return
        self.lienzo.delete("resalte")
        self._prov_resaltada = pid
        if not pid or not self._geometria:
            return
        esc, ox, oy = self._geometria
        for p_id, anillos in mapa.proyectadas():
            if p_id == pid:
                for a in anillos:
                    if len(a) > 2:
                        pts = [v for x, y in a for v in (x * esc + ox, y * esc + oy)]
                        self.lienzo.create_polygon(pts, outline=color(tema.TINTA), fill="", width=2, tags="resalte")
        self.lienzo.tag_raise("globo")

    def _globo(self, x, y, titulo, texto):
        c = self.lienzo
        c.delete("globo")
        fondo, letra = color(tema.TINTA), color(tema.PAPEL)
        t1 = c.create_text(x, y - 34, text=titulo, fill=letra, font=(tema.FUENTE_TITULO, 12, "bold"),
                           anchor="s", tags="globo")
        t2 = c.create_text(x, y - 18, text=texto, fill=letra, font=(tema.FUENTE, 10), anchor="s", tags="globo")
        bx = c.bbox(t1)
        bx2 = c.bbox(t2)
        caja = (min(bx[0], bx2[0]) - 10, bx[1] - 6, max(bx[2], bx2[2]) + 10, bx2[3] + 6)
        desp = 0
        if caja[0] < 4:
            desp = 4 - caja[0]
        elif caja[2] > c.winfo_width() - 4:
            desp = c.winfo_width() - 4 - caja[2]
        r = c.create_rectangle(caja[0] + desp, caja[1], caja[2] + desp, caja[3], fill=fondo, outline=fondo, tags="globo")
        c.move(t1, desp, 0)
        c.move(t2, desp, 0)
        c.tag_lower(r, t1)

    def _ocultar_globo(self):
        self.lienzo.delete("globo")

    def _clic(self, ev):
        slug = self._pin_en(ev.x, ev.y)
        if slug:
            self.app.abrir(slug)
            return
        ll = self._a_lonlat(ev.x, ev.y)
        pid = mapa.provincia_de_punto(ll[1], ll[0]) if ll else None
        if pid:
            self._panel_provincia(pid)

    # ------------------------------------------------------------------ panel lateral
    def _limpiar_panel(self):
        for w in self.panel.winfo_children():
            w.destroy()

    def _panel_inicio(self):
        self._prov_sel = None
        self._limpiar_panel()
        ctk.CTkLabel(self.panel, text="Provincias", font=fuente_titulo(20)).pack(anchor="w", padx=10, pady=(10, 2))
        ctk.CTkLabel(self.panel, text="Haz clic en una provincia del mapa\npara ver sus pueblos.",
                     text_color=tema.TINTA_2, justify="left").pack(anchor="w", padx=10)
        leyenda = ctk.CTkFrame(self.panel, fg_color="transparent")
        leyenda.pack(fill="x", padx=10, pady=16)
        for texto, col in (("Visitado", tema.ACENTO), ("Por visitar", tema.PENDIENTE), ("Sin destapar", tema.MAPA_TAPADA)):
            fila = ctk.CTkFrame(leyenda, fg_color="transparent")
            fila.pack(anchor="w", pady=2)
            ctk.CTkFrame(fila, width=14, height=14, corner_radius=7, fg_color=col).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(fila, text=texto).pack(side="left")

    def _panel_provincia(self, pid):
        self._prov_sel = pid
        self._limpiar_panel()
        prov = mapa.por_id(pid)
        ctk.CTkLabel(self.panel, text=prov["nombre"], font=fuente_titulo(22), wraplength=240,
                     justify="left").pack(anchor="w", padx=10, pady=(10, 0))
        ctk.CTkLabel(self.panel, text=prov["comunidad"], text_color=tema.TINTA_2).pack(anchor="w", padx=10)
        vis = [p for p in self.pueblos if p.get("_prov") == pid and p.get("estado") != "pendiente"]
        pen = [p for p in self.pueblos if p.get("_prov") == pid and p.get("estado") == "pendiente"]
        for titulo, lista in (("Visitados", vis), ("Por visitar", pen)):
            if not lista:
                continue
            ctk.CTkLabel(self.panel, text=titulo.upper(), font=fuente(11, "bold"),
                         text_color=tema.ACENTO if titulo == "Visitados" else tema.PENDIENTE).pack(
                anchor="w", padx=10, pady=(16, 4))
            for p in sorted(lista, key=lambda x: normalizar(x["nombre"])):
                boton(self.panel, p["nombre"], lambda s=p["slug"]: self.app.abrir(s), "secundario", anchor="w").pack(
                    fill="x", padx=8, pady=2)
        if not vis and not pen:
            ctk.CTkLabel(self.panel, text="Todavía no has estado aquí.", text_color=tema.TINTA_2).pack(
                anchor="w", padx=10, pady=(16, 6))
        boton(self.panel, "＋ Añadir un pueblo por visitar", lambda: self.app.nuevo("pendiente", prov["nombre"]),
              "fantasma", text_color=tema.PENDIENTE).pack(fill="x", padx=8, pady=(18, 4))


# ============================================================================ vista: lista de pueblos
class VistaLista(ctk.CTkFrame):
    ANCHO_FICHA = 230

    def __init__(self, app, estado):
        super().__init__(app.contenedor, fg_color="transparent")
        self.app = app
        self.estado = estado
        self._columnas = 0
        self._imagenes = []

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", padx=28, pady=(22, 10))
        izq = ctk.CTkFrame(cab, fg_color="transparent")
        izq.pack(side="left")
        ctk.CTkLabel(izq, text="Pueblos visitados" if estado == "visitado" else "Por visitar",
                     font=fuente_titulo(28)).pack(anchor="w")
        self.lbl_n = ctk.CTkLabel(izq, text="", text_color=tema.TINTA_2, font=fuente(14))
        self.lbl_n.pack(anchor="w")
        self.buscador = ctk.CTkEntry(cab, placeholder_text="🔎  Buscar pueblo o provincia…", width=240, height=34)
        self.buscador.pack(side="right", padx=(8, 0))
        self.buscador.bind("<KeyRelease>", lambda e: self.refrescar())

        self.rejilla = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.rejilla.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self.bind("<Configure>", self._al_redimensionar)

    def _al_redimensionar(self, ev):
        if ev.widget is not self:
            return
        cols = max(1, (ev.width - 70) // (self.ANCHO_FICHA + 16))
        if cols != self._columnas:
            self._columnas = cols
            self.refrescar()

    def refrescar(self):
        for w in self.rejilla.winfo_children():
            w.destroy()
        self._imagenes = []
        texto_buscar = self.buscador.get()
        filtro = normalizar(texto_buscar)
        todos = [p for p in self.app.almacen.listar()
                 if (p.get("estado") == "pendiente") == (self.estado == "pendiente")]
        pueblos = [p for p in todos if not filtro
                   or filtro in normalizar(f"{p['nombre']} {p['provincia']} {p['comunidad']}")]
        self.lbl_n.configure(text=f"{len(todos)} {'pueblo' if len(todos) == 1 else 'pueblos'}"
                                  + (f" · {len(pueblos)} con «{texto_buscar}»" if filtro else ""))
        cols = max(1, self._columnas or 4)
        for c in range(cols):
            self.rejilla.columnconfigure(c, weight=1, uniform="col")
        if not pueblos:
            texto = ("Todavía no hay pueblos. Importa las fotos de un viaje o crea uno nuevo." if self.estado == "visitado"
                     else "Tu lista de pendientes está vacía. Añade los pueblos que quieres conocer.")
            ctk.CTkLabel(self.rejilla, text=texto if not filtro else "No hay pueblos que coincidan.",
                         text_color=tema.TINTA_2, font=fuente(14)).grid(row=0, column=0, columnspan=cols, pady=60)
            return
        orden = sorted(pueblos, key=lambda x: (normalizar(x["comunidad"] or "zzz"), normalizar(x["nombre"])))
        for i, p in enumerate(orden):
            self._ficha(p).grid(row=i // cols, column=i % cols, padx=8, pady=8, sticky="n")

    def _ficha(self, p):
        pend = p.get("estado") == "pendiente"
        f = ctk.CTkFrame(self.rejilla, corner_radius=12, border_width=2 if pend else 0,
                         border_color=tema.PENDIENTE if pend else tema.LINEA)
        img = self.app.miniatura(p["slug"], p.get("portada"), self.ANCHO_FICHA, 150)
        if img:
            foto = ctk.CTkLabel(f, text="", image=img, corner_radius=10)
            self._imagenes.append(img)
        else:
            foto = ctk.CTkLabel(f, text=p["nombre"][:1], width=self.ANCHO_FICHA, height=150, corner_radius=10,
                                fg_color=tema.TARJETA_2, text_color=tema.LINEA, font=fuente_titulo(48))
        foto.pack(padx=6, pady=(6, 0))
        nombre = ctk.CTkLabel(f, text=p["nombre"], font=fuente(15, "bold"), anchor="w")
        nombre.pack(fill="x", padx=12, pady=(8, 0))
        if pend:
            sub = p["provincia"] or "Por visitar"
        else:
            visita = (p.get("fechas_visita") or [""])[-1]
            propias = sum(1 for x in p["fotos"] if not x.get("credito"))
            fotos = f"{propias} 📷" if propias else "🌐 sin fotos tuyas"
            sub = " · ".join(x for x in (p["provincia"] or p["comunidad"], visita, fotos) if x)
        detalle = ctk.CTkLabel(f, text=sub, text_color=tema.TINTA_2, font=fuente(12), anchor="w")
        detalle.pack(fill="x", padx=12, pady=(0, 10))
        for w in (f, foto, nombre, detalle):
            w.bind("<Button-1>", lambda ev, s=p["slug"]: self.app.abrir(s))
            w.configure(cursor="hand2")
        return f


# ============================================================================ vista: editor
class VistaEditor(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.contenedor, fg_color="transparent")
        self.app = app
        self.sel = set()
        self._imagenes = []
        self._columnas = 0

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=22, pady=(18, 6))
        boton(barra, "←  Volver", app.volver, "fantasma", width=90).pack(side="left")
        self.lbl_titulo = ctk.CTkLabel(barra, text="", font=fuente_titulo(26))
        self.lbl_titulo.pack(side="left", padx=(12, 0))
        boton(barra, "Eliminar", self.eliminar, "peligro", width=90).pack(side="right")
        boton(barra, "💾  Guardar", self.guardar, width=110).pack(side="right", padx=8)
        self.seg_estado = ctk.CTkSegmentedButton(barra, values=["Visitado", "Por visitar"], command=self._cambiar_estado,
                                                 height=32, font=fuente(13))
        self.seg_estado.pack(side="right", padx=8)

        # ---- datos
        form = ctk.CTkFrame(self, corner_radius=14)
        form.pack(fill="x", padx=28, pady=(6, 10))
        for c in (1, 3, 5):
            form.columnconfigure(c, weight=1)
        self.v = {k: tk.StringVar() for k in ("nombre", "provincia", "comunidad", "fechas", "lat", "lon")}
        self.v_publicar = tk.BooleanVar(value=True)

        def campo(fila, col, etiqueta, var, **kw):
            ctk.CTkLabel(form, text=etiqueta, text_color=tema.TINTA_2).grid(row=fila, column=col, sticky="w",
                                                                            padx=(16, 8), pady=8)
            e = ctk.CTkEntry(form, textvariable=var, height=32, **kw)
            e.grid(row=fila, column=col + 1, sticky="ew", padx=(0, 10), pady=8)
            return e
        e_nombre = campo(0, 0, "Nombre", self.v["nombre"])
        e_prov = campo(0, 2, "Provincia", self.v["provincia"])
        self._campos_lugar = (e_nombre, e_prov)
        for e in self._campos_lugar:     # si cambias el nombre o la provincia, se vuelve a buscar dónde está
            e.bind("<FocusOut>", lambda ev: self.after(250, self._quizas_reubicar))
            e.bind("<Return>", lambda ev: self._quizas_reubicar(ya=True))
        self.lbl_minimapa = ctk.CTkLabel(form, text="", width=200, height=150, corner_radius=10, cursor="hand2")
        self.lbl_minimapa.grid(row=0, column=6, rowspan=3, padx=(0, 14), pady=10, sticky="ne")
        self.lbl_minimapa.bind("<Button-1>", lambda ev: self._abrir_osm())
        self._mm_trabajo = None
        for k in ("lat", "lon"):
            self.v[k].trace_add("write", lambda *a: self._programar_minimapa())
        ctk.CTkLabel(form, text="Comunidad", text_color=tema.TINTA_2).grid(row=0, column=4, sticky="w", padx=(16, 8))
        ctk.CTkComboBox(form, variable=self.v["comunidad"], values=COMUNIDADES, height=32).grid(
            row=0, column=5, sticky="ew", padx=(0, 16))
        campo(1, 0, "Visitas", self.v["fechas"])
        campo(1, 2, "Latitud", self.v["lat"])
        campo(1, 4, "Longitud", self.v["lon"])
        pie = ctk.CTkFrame(form, fg_color="transparent")
        pie.grid(row=2, column=0, columnspan=6, sticky="ew", padx=10, pady=(0, 10))
        boton(pie, "🔎  Buscar ubicación", self.buscar_ubicacion, "secundario").pack(side="left", padx=6)
        boton(pie, "📅  Hoy", self._anadir_hoy, "fantasma", width=70).pack(side="left")
        ctk.CTkLabel(pie, text="Fechas como AAAA-MM-DD, separadas por comas", text_color=tema.TINTA_2,
                     font=fuente(11)).pack(side="left", padx=8)
        ctk.CTkSwitch(pie, text="Publicar en la web", variable=self.v_publicar).pack(side="right", padx=8)

        # ---- pestañas
        self.tabs = ctk.CTkTabview(self, corner_radius=14)
        self.tabs.pack(fill="both", expand=True, padx=28, pady=(0, 14))
        for nombre in ("Fotos", "Wikipedia", "Texto IA", "Fiestas", "Mis notas"):
            self.tabs.add(nombre)

        tf = self.tabs.tab("Fotos")
        bf = ctk.CTkFrame(tf, fg_color="transparent")
        bf.pack(fill="x")
        boton(bf, "＋ Mis fotos…", self.anadir_fotos).pack(side="left", padx=(0, 6))
        boton(bf, "🌐 Fotos de internet…", self.app.fotos_internet, "secundario").pack(side="left", padx=6)
        boton(bf, "★ Portada", self.hacer_portada, "fantasma", width=90).pack(side="left", padx=(16, 0))
        boton(bf, "Pie de foto…", self.pie_foto, "fantasma", width=100).pack(side="left")
        boton(bf, "Quitar", self.quitar_fotos, "fantasma", width=70, text_color=tema.PELIGRO).pack(side="left")
        ctk.CTkLabel(bf, text="Clic para elegir · Ctrl+clic para varias · doble clic para verla",
                     text_color=tema.TINTA_2, font=fuente(12)).pack(side="right")
        self.galeria = ctk.CTkScrollableFrame(tf, fg_color="transparent")
        self.galeria.pack(fill="both", expand=True, pady=(8, 0))
        self._tab_fotos = tf
        tf.bind("<Configure>", self._al_redimensionar)

        tw = self.tabs.tab("Wikipedia")
        bw = ctk.CTkFrame(tw, fg_color="transparent")
        bw.pack(fill="x")
        boton(bw, "⬇  Traer datos de Wikipedia", self.traer_wiki).pack(side="left")
        self.lbl_wiki = ctk.CTkLabel(tw, text="", text_color=tema.TINTA_2, wraplength=900, justify="left", anchor="w")
        self.lbl_wiki.pack(fill="x", pady=(6, 0))
        self.txt_wiki = ctk.CTkTextbox(tw, wrap="word", font=fuente(14))
        self.txt_wiki.pack(fill="both", expand=True, pady=(8, 0))

        ti = self.tabs.tab("Texto IA")
        bi = ctk.CTkFrame(ti, fg_color="transparent")
        bi.pack(fill="x")
        boton(bi, "✨  Generar texto con IA", self.generar_ia).pack(side="left")
        ctk.CTkLabel(bi, text="Se basa en Wikipedia y tus notas. Puedes corregirlo a mano.",
                     text_color=tema.TINTA_2).pack(side="left", padx=12)
        self.txt_ia = ctk.CTkTextbox(ti, wrap="word", font=fuente(14))
        self.txt_ia.pack(fill="both", expand=True, pady=(8, 0))

        tfi = self.tabs.tab("Fiestas")
        bfi = ctk.CTkFrame(tfi, fg_color="transparent")
        bfi.pack(fill="x")
        boton(bfi, "⬇  Buscar fiestas en internet", self.buscar_fiestas).pack(side="left")
        boton(bfi, "Volver a las de internet", self.fiestas_originales, "fantasma", width=170).pack(side="left", padx=8)
        ctk.CTkLabel(tfi, text="Una por línea, con su fecha delante:  «14 de septiembre: Fiestas de La Cruz», "
                               "«último domingo de agosto: San Tirso», «del 14 al 17 de agosto: Fiestas patronales», "
                               "«Semana Santa: Pasión viviente»…  Puedes corregirlas, quitar o añadir.",
                     text_color=tema.TINTA_2, wraplength=900, justify="left").pack(anchor="w", pady=(6, 0))
        self.lbl_fiestas = ctk.CTkLabel(tfi, text="", text_color=tema.TINTA_2, font=fuente(12))
        self.lbl_fiestas.pack(anchor="w")
        self.txt_fiestas = ctk.CTkTextbox(tfi, wrap="word", font=fuente(14))
        self.txt_fiestas.pack(fill="both", expand=True, pady=(8, 0))

        tn = self.tabs.tab("Mis notas")
        ctk.CTkLabel(tn, text="Tus impresiones: con quién fuiste, qué viste, dónde comiste…  En la web salen como "
                              "una hoja de cuaderno.  Deja una línea en blanco entre párrafos.\n"
                              "Trucos:  «- » al empezar la línea hace una lista  ·  «★ » o «> » destaca una frase  ·  "
                              "**palabras** en negrita.", text_color=tema.TINTA_2, justify="left").pack(anchor="w")
        self.txt_notas = ctk.CTkTextbox(tn, wrap="word", font=fuente(14))
        self.txt_notas.pack(fill="both", expand=True, pady=(8, 0))

    @property
    def p(self):
        return self.app.actual

    def refrescar(self):
        pass

    # ------------------------------------------------------------------ cargar / leer
    def cargar(self):
        p = self.p
        self.sel.clear()
        self.lbl_titulo.configure(text=p["nombre"] or "Pueblo nuevo")
        self.v["nombre"].set(p["nombre"])
        self.v["provincia"].set(p["provincia"])
        self.v["comunidad"].set(p["comunidad"])
        self.v["fechas"].set(", ".join(p["fechas_visita"]))
        self.v["lat"].set("" if p["lat"] is None else str(p["lat"]))
        self.v["lon"].set("" if p["lon"] is None else str(p["lon"]))
        self._ubicado_para = (normalizar(p["nombre"]), normalizar(p["provincia"]))
        self._programar_minimapa()
        self.v_publicar.set(p.get("publicar", True))
        self.seg_estado.set("Por visitar" if p.get("estado") == "pendiente" else "Visitado")
        for t, valor in ((self.txt_wiki, p["wiki"].get("extracto", "")), (self.txt_ia, p["texto_ia"]),
                         (self.txt_notas, p["notas"]), (self.txt_fiestas, FI.a_texto(FI.del_pueblo(p)))):
            t.delete("1.0", "end")
            t.insert("1.0", valor or "")
        self._etiqueta_wiki()
        self._etiqueta_fiestas()
        self.pintar_fotos()

    def leer(self):
        p = self.p
        p["nombre"] = self.v["nombre"].get().strip()
        p["provincia"] = self.v["provincia"].get().strip()
        p["comunidad"] = self.v["comunidad"].get().strip()
        p["fechas_visita"] = [x.strip() for x in self.v["fechas"].get().replace(";", ",").split(",") if x.strip()]
        for k in ("lat", "lon"):
            try:
                p[k] = float(self.v[k].get().replace(",", ".")) if self.v[k].get().strip() else None
            except ValueError:
                pass
        p["publicar"] = self.v_publicar.get()
        p["estado"] = "pendiente" if self.seg_estado.get() == "Por visitar" else "visitado"
        p["wiki"]["extracto"] = self.txt_wiki.get("1.0", "end").strip()
        p["texto_ia"] = self.txt_ia.get("1.0", "end").strip()
        p["notas"] = self.txt_notas.get("1.0", "end").strip()
        texto_f = self.txt_fiestas.get("1.0", "end").strip()
        if texto_f != FI.a_texto(FI.del_pueblo(p)).strip():
            p["fiestas"] = FI.de_texto(texto_f)       # corregidas a mano: mandan sobre las de internet

    def _etiqueta_fiestas(self):
        p = self.p
        if isinstance(p.get("fiestas"), list):
            t = "Corregidas por ti (las de internet no se usan)."
        elif "fiestas" in (p.get("wiki") or {}):
            n = len(p["wiki"]["fiestas"])
            t = f"{n} encontradas en Wikipedia y Wikidata." if n else "No he encontrado fiestas con fecha en internet: puedes escribirlas tú."
        else:
            t = "Aún no se han buscado: pulsa «Buscar fiestas en internet»."
        self.lbl_fiestas.configure(text=t)

    def buscar_fiestas(self):
        if not self.p:
            return
        self.leer()
        p = self.p
        w = p.get("wiki") or {}

        def tarea():
            if w.get("titulo"):
                d = self.app.wiki.ampliar(self.app.wiki.datos(w["titulo"]) or {"titulo": w["titulo"], "wikidata": w.get("wikidata")},
                                          p["nombre"], p["provincia"], p["lat"], p["lon"])
            else:
                d = self.app.wiki.todo(p["nombre"], p["provincia"], p["lat"], p["lon"])
            return (d or {}).get("fiestas")

        def fin(lista):
            if lista is None:
                messagebox.showinfo(NOMBRE_PROGRAMA, "No he encontrado el artículo de Wikipedia de este pueblo.")
                return
            p.setdefault("wiki", {})["fiestas"] = lista
            if isinstance(p.get("fiestas"), list) and messagebox.askyesno(
                    NOMBRE_PROGRAMA, f"He encontrado {len(lista)} fiestas en internet. ¿Sustituyen a las que escribiste tú?"):
                p.pop("fiestas", None)
            self.app.almacen.guardar(p)
            self.cargar()
            self.tabs.set("Fiestas")
            self.app.estado(f"{len(lista)} fiestas encontradas." if lista else "No he encontrado fiestas con fecha.")
        self.app.en_segundo_plano("Buscando las fiestas…", tarea, fin)

    def fiestas_originales(self):
        if self.p and isinstance(self.p.get("fiestas"), list):
            self.p.pop("fiestas", None)
            self.app.almacen.guardar(self.p)
            self.cargar()
            self.tabs.set("Fiestas")

    def _etiqueta_wiki(self):
        w = self.p["wiki"]
        partes = []
        if w.get("titulo"):
            partes.append(f"Artículo: {w['titulo']}")
        if w.get("poblacion"):
            partes.append(f"{w['poblacion']:,} hab.".replace(",", "."))
        if w.get("altitud") not in (None, ""):
            partes.append(f"{w['altitud']} m")
        if w.get("secciones"):
            partes.append(f"Apartados: {', '.join(x['titulo'] for x in w['secciones'])}")
        if w.get("que_ver"):
            partes.append(f"{len(w['que_ver'])} lugares que ver")
        self.lbl_wiki.configure(text="  ·  ".join(partes) or "Sin datos todavía")

    def _cambiar_estado(self, valor):
        if valor == "Visitado" and not self.v["fechas"].get().strip():
            f = self.app.pedir_fecha("¡Enhorabuena! ¿Cuándo lo visitaste?", date.today().isoformat())
            if f:
                self.v["fechas"].set(f)

    def _anadir_hoy(self):
        hoy = date.today().isoformat()
        fechas = [x.strip() for x in self.v["fechas"].get().split(",") if x.strip()]
        if hoy not in fechas:
            fechas.append(hoy)
        self.v["fechas"].set(", ".join(sorted(fechas)))

    def guardar(self, silencioso=False):
        if not self.p:
            return False
        self.leer()
        if not self.p["nombre"]:
            if not silencioso:
                messagebox.showwarning(NOMBRE_PROGRAMA, "El pueblo necesita un nombre.")
            return False
        malas = [f for f in self.p["fechas_visita"] if not fecha_ok(f)]
        if malas and not silencioso:
            messagebox.showwarning(NOMBRE_PROGRAMA, f"La fecha «{malas[0]}» no es válida. Usa 2024-05-12, 2024-05 o 2024.")
            return False
        self.p["fechas_visita"] = [f for f in self.p["fechas_visita"] if fecha_ok(f)]
        self.app.almacen.guardar(self.p)
        self.lbl_titulo.configure(text=self.p["nombre"])
        if not silencioso:
            self.app.estado(f"Guardado «{self.p['nombre']}».")
        return True

    def eliminar(self):
        if not self.p:
            return
        if not messagebox.askyesno(NOMBRE_PROGRAMA, f"¿Quitar «{self.p['nombre']}» del programa?\n\n"
                                   "No se borra del todo: se guarda en datos\\_papelera.\n"
                                   "Desaparecerá de la web la próxima vez que publiques."):
            return
        self.app.almacen.eliminar(self.p["slug"])
        self.app.actual = None
        self.app.volver(guardar=False)

    # ------------------------------------------------------------------ fotos
    def _al_redimensionar(self, ev):
        if ev.widget is not self._tab_fotos:
            return
        cols = max(1, (ev.width - 30) // 172)
        if cols != self._columnas:
            self._columnas = cols
            self.pintar_fotos()

    def pintar_fotos(self):
        for w in self.galeria.winfo_children():
            w.destroy()
        self._imagenes = []
        if not self.p:
            return
        p = self.p
        if not p["fotos"]:
            ctk.CTkLabel(self.galeria, text="Sin fotos todavía. Añade las tuyas o busca fotos libres en internet.",
                         text_color=tema.TINTA_2, font=fuente(14)).grid(row=0, column=0, pady=40, padx=20)
            return
        cols = max(1, self._columnas or 5)
        for i, f in enumerate(p["fotos"]):
            elegida = f["archivo"] in self.sel
            caja = ctk.CTkFrame(self.galeria, corner_radius=10, border_width=3,
                                border_color=tema.ACENTO if elegida else tema.TARJETA,
                                fg_color=tema.TARJETA_2 if elegida else tema.TARJETA)
            caja.grid(row=i // cols, column=i % cols, padx=5, pady=5)
            img = self.app.miniatura(p["slug"], f["archivo"], 150, 150)
            lbl = ctk.CTkLabel(caja, text="" if img else "?", image=img, width=150, height=150)
            if img:
                self._imagenes.append(img)
            lbl.pack(padx=4, pady=(4, 0))
            marca = ("★ " if f["archivo"] == p["portada"] else "") + ("🌐 " if f.get("credito") else "")
            texto = marca + (f.get("pie") or f.get("fecha") or (f["credito"]["autor"] if f.get("credito") else ""))
            pie = ctk.CTkLabel(caja, text=texto[:22], font=fuente(11), text_color=tema.TINTA_2, height=20)
            pie.pack(fill="x", padx=4, pady=(0, 4))
            for w in (caja, lbl, pie):
                w.bind("<Button-1>", lambda ev, a=f["archivo"]: self._clic_foto(a, ev))
                w.bind("<Double-Button-1>", lambda ev, a=f["archivo"]: self._ver_foto(a))

    def _clic_foto(self, archivo, ev):
        if ev.state & 0x0004:
            self.sel.symmetric_difference_update({archivo})
        else:
            self.sel = {archivo}
        self.pintar_fotos()

    def _ver_foto(self, archivo):
        ruta = self.app.almacen.carpeta_pueblo(self.p["slug"]) / "fotos" / archivo
        if ruta.exists():
            webbrowser.open(ruta.as_uri())

    def anadir_fotos(self):
        if not self.p:
            return
        rutas = filedialog.askopenfilenames(parent=self, title="Elige las fotos del pueblo", filetypes=TIPOS_FOTO)
        if not rutas:
            return
        self.guardar(silencioso=True)
        p = self.p

        def fin(n):
            self.app.abrir(p["slug"], recargar=True)
            self.app.estado(f"Añadidas {n} fotos.")
        self.app.en_segundo_plano("Preparando fotos…", lambda: I.anadir_fotos(
            self.app.almacen, p, rutas, int(self.app.cfg["lado_foto"]), self.app._progreso), fin)

    def hacer_portada(self):
        if self.p and len(self.sel) == 1:
            self.p["portada"] = next(iter(self.sel))
            self.guardar(silencioso=True)
            self.pintar_fotos()
        else:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Elige una sola foto.")

    def pie_foto(self):
        if not self.p or len(self.sel) != 1:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Elige una sola foto.")
            return
        a = next(iter(self.sel))
        f = next(x for x in self.p["fotos"] if x["archivo"] == a)
        texto = self.app.pedir_texto("Pie de foto", "Escribe el pie de foto:", f.get("pie", ""))
        if texto is not None:
            f["pie"] = texto.strip()
            self.guardar(silencioso=True)
            self.pintar_fotos()

    def quitar_fotos(self):
        if not self.p or not self.sel:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Elige las fotos que quieras quitar.")
            return
        if not messagebox.askyesno(NOMBRE_PROGRAMA, f"¿Quitar {len(self.sel)} foto(s) de este pueblo?\n"
                                                  "Tus fotos originales no se tocan."):
            return
        self.p["fotos"] = [f for f in self.p["fotos"] if f["archivo"] not in self.sel]
        for a in self.sel:
            for sub in ("fotos", "mini"):
                ruta = self.app.almacen.carpeta_pueblo(self.p["slug"]) / sub / a
                if ruta.exists():
                    ruta.unlink()
        self.sel.clear()
        self.guardar(silencioso=True)
        self.pintar_fotos()

    # ------------------------------------------------------------------ ubicación / wiki / IA
    def _quizas_reubicar(self, ya=False):
        """Nombre o provincia cambiados a mano: la ubicación (y el mapa) se ponen al día."""
        if not self.p or self.app.ocupado or self.app.vista != "editor":
            return
        if not ya:
            try:
                foco = self.focus_get()
            except (KeyError, tk.TclError):
                foco = None
            if foco is not None and any(foco in (c, getattr(c, "_entry", None)) for c in self._campos_lugar):
                return                          # aún está escribiendo el nombre o la provincia
        clave = (normalizar(self.v["nombre"].get()), normalizar(self.v["provincia"].get()))
        if not clave[0] or clave == getattr(self, "_ubicado_para", None):
            return
        self._ubicado_para = clave
        self.buscar_ubicacion(automatico=True)

    def buscar_ubicacion(self, despues=None, automatico=False):
        if not self.p:
            return
        self.leer()
        texto = ", ".join(x for x in (self.p["nombre"], self.p["provincia"]) if x)
        if not texto:
            return
        p = self.p

        def fin(resultados):
            if not resultados:
                if automatico:
                    self.app.estado(f"No encuentro «{texto}» en el mapa: la ubicación sigue como estaba.")
                else:
                    messagebox.showinfo(NOMBRE_PROGRAMA, f"No encuentro «{texto}» en el mapa.\n"
                                        "Prueba con otra forma del nombre o escribe la provincia.")
                if despues:
                    despues()
                return
            seguro = len(resultados) == 1 or resultados[0].get("seguro")
            elegido = resultados[0] if seguro else self.app.elegir_lugar(resultados, texto)
            if not elegido:
                return
            p["provincia"] = elegido["provincia"] or p["provincia"]
            p["comunidad"] = elegido["comunidad"] or p["comunidad"]
            p["lat"], p["lon"] = round(elegido["lat"], 6), round(elegido["lon"], 6)
            self.app.almacen.guardar(p)
            self.cargar()
            self.app.estado(f"Ubicado: {elegido.get('tipo', 'lugar').lower()} de {p['nombre']}, "
                            f"{p['provincia']} ({p['comunidad']}). Lo ves en el mapa pequeño.")
            if despues:
                despues()
        self.app.en_segundo_plano("Buscando en el mapa…", lambda: self.app.geo.buscar(
            p["nombre"], provincia=p["provincia"], espana=(p.get("pais") or "España") == "España"), fin)

    # ------------------------------------------------------------------ mapa pequeño de la ficha
    def _programar_minimapa(self):
        if self._mm_trabajo:
            self.after_cancel(self._mm_trabajo)
        self._mm_trabajo = self.after(150, self._pintar_minimapa)

    def _coordenadas(self):
        try:
            return float(self.v["lat"].get().replace(",", ".")), float(self.v["lon"].get().replace(",", "."))
        except ValueError:
            return None

    def _pintar_minimapa(self):
        self._mm_trabajo = None
        c = self._coordenadas()
        img = mini_mapa(c, 200, 150)
        self._img_minimapa = ctk.CTkImage(light_image=img, dark_image=img, size=(200, 150))
        self.lbl_minimapa.configure(image=self._img_minimapa, text="")

    def _abrir_osm(self):
        c = self._coordenadas()
        if c:
            webbrowser.open(f"https://www.openstreetmap.org/?mlat={c[0]}&mlon={c[1]}#map=14/{c[0]}/{c[1]}")

    def traer_wiki(self, despues=None):
        if not self.p:
            return
        self.leer()
        p = self.p
        if p["wiki"].get("extracto") and not despues and not messagebox.askyesno(
                NOMBRE_PROGRAMA, "Ya hay texto de Wikipedia. ¿Lo sustituyo por el actual de Wikipedia?"):
            return

        def fin(d):
            if not self.app.aplicar_wiki(p, d):
                messagebox.showinfo(NOMBRE_PROGRAMA, "No he encontrado el artículo en Wikipedia.\n"
                                    "Revisa el nombre y la provincia, o pega tú el texto.")
            else:
                self.app.almacen.guardar(p)
                self.cargar()
                self.tabs.set("Wikipedia")
                self.app.estado(f"Datos de Wikipedia: «{d.get('titulo')}».")
            if despues:
                despues()
        def tarea():
            self.app.wiki._comunidad = p.get("comunidad", "")
            return self.app.traducir_otra(self.app.wiki.todo(p["nombre"], p["provincia"], p["lat"], p["lon"]))
        self.app.en_segundo_plano("Consultando Wikipedia y otras fuentes…", tarea, fin)

    def generar_ia(self):
        if not self.p:
            return
        if not IA.configurada(self.app.cfg):
            messagebox.showinfo(NOMBRE_PROGRAMA, "Para escribir con IA elige una IA (Claude, ChatGPT, Gemini…) "
                                "y pon su clave en Ajustes → Inteligencia artificial.\n\n"
                                "Gemini tiene uso gratuito: es la forma más fácil de empezar.")
            return
        self.leer()
        p = self.p
        if p["texto_ia"] and not messagebox.askyesno(NOMBRE_PROGRAMA, "¿Sustituyo el texto actual por uno nuevo?"):
            return

        def fin(texto):
            p["texto_ia"] = texto
            self.app.almacen.guardar(p)
            self.cargar()
            self.tabs.set("Texto IA")
            self.app.estado("Texto generado. Revísalo antes de publicar.")
        self.app.en_segundo_plano(f"Escribiendo con {IA.nombre(self.app.cfg)}…",
                                  lambda: generar_texto(self.app.cfg, p), fin)




# ============================================================================ vista: revisar lo que falta
class VistaRevisar(ctk.CTkFrame):
    """Lo que le falta a cada pueblo, para dejar la web completa escribiendo lo mínimo."""
    COMPROBACIONES = [
        # (clave, texto, a quién aplica, cómo saber si falta)
        ("ubicacion", "Sin ubicación en el mapa", "todos", lambda p: p.get("lat") is None),
        ("fecha", "Sin fecha de visita", "visitado", lambda p: not p.get("fechas_visita")),
        ("fotos", "Sin fotos tuyas", "visitado", lambda p: not any(not f.get("credito") for f in p.get("fotos", []))),
        ("portada", "Sin ninguna foto", "todos", lambda p: not p.get("fotos")),
        ("info", "Sin información de internet", "todos",
         lambda p: not (p.get("wiki") or {}).get("extracto") or "fuentes_v2" not in (p.get("wiki") or {})),
        ("notas", "Sin una línea tuya", "visitado", lambda p: not (p.get("notas") or "").strip()),
        ("oculto", "No se publica en la web", "todos", lambda p: not p.get("publicar", True)),
    ]

    def __init__(self, app):
        super().__init__(app.contenedor, fg_color="transparent")
        self.app = app
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", padx=28, pady=(22, 6))
        izq = ctk.CTkFrame(cab, fg_color="transparent")
        izq.pack(side="left")
        ctk.CTkLabel(izq, text="Revisar", font=fuente_titulo(28)).pack(anchor="w")
        self.lbl = ctk.CTkLabel(izq, text="", text_color=tema.TINTA_2, font=fuente(14))
        self.lbl.pack(anchor="w")
        boton(cab, "📚  Completar la información de todos", app.ampliar_todos, "secundario").pack(side="right")
        self.cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.cuerpo.pack(fill="both", expand=True, padx=18, pady=(4, 12))

    def refrescar(self):
        for w in self.cuerpo.winfo_children():
            w.destroy()
        pueblos = [p for p in self.app.almacen.listar() if p.get("nombre")]
        grupos = {c[0]: [] for c in self.COMPROBACIONES}
        for p in pueblos:
            for clave, _, quien, falta in self.COMPROBACIONES:
                if quien != "todos" and p.get("estado", "visitado") != quien:
                    continue
                try:
                    if falta(p):
                        grupos[clave].append(p)
                except Exception:  # noqa: BLE001
                    pass
        total = sum(len(v) for k, v in grupos.items() if k not in ("notas", "oculto"))
        capturas = self._leer_capturas()
        self.lbl.configure(text=(f"{len(capturas)} capturados en el móvil por revisar. " if capturas else "") +
                           ("¡Todo completo! Tu web está al día." if not total else
                            f"{total} cosas por completar en {len(pueblos)} pueblos. Pulsa un pueblo para arreglarlo."))
        if capturas:
            self._pintar_capturas(capturas)
        for clave, texto, _, _ in self.COMPROBACIONES:
            lista = grupos[clave]
            if not lista:
                continue
            caja = ctk.CTkFrame(self.cuerpo, corner_radius=14)
            caja.pack(fill="x", padx=8, pady=6)
            fila = ctk.CTkFrame(caja, fg_color="transparent")
            fila.pack(fill="x", padx=16, pady=(12, 4))
            ctk.CTkLabel(fila, text=f"{texto}  ·  {len(lista)}", font=fuente_titulo(17)).pack(side="left")
            if clave == "notas":
                ctk.CTkLabel(fila, text="Opcional: con una frase basta", text_color=tema.TINTA_2,
                             font=fuente(12)).pack(side="right")
            chips = ctk.CTkFrame(caja, fg_color="transparent")
            chips.pack(fill="x", padx=12, pady=(2, 12))
            for i, p in enumerate(sorted(lista, key=lambda x: normalizar(x["nombre"]))[:40]):
                img = self.app.miniatura(p["slug"], p.get("portada"), 34, 34)
                b = ctk.CTkButton(chips, text=f"  {p['nombre']}", image=img, compound="left", height=40, corner_radius=20,
                                  fg_color=tema.TARJETA_2, hover_color=tema.LINEA,
                                  text_color=tema.TINTA, font=fuente(13), anchor="w",
                                  command=lambda s=p["slug"]: self.app.abrir(s))
                b.grid(row=i // 4, column=i % 4, padx=4, pady=4, sticky="ew")
            for c in range(4):
                chips.columnconfigure(c, weight=1)

    # ------------------------------------------------------------------ capturados con el móvil («📌 Capturar»)
    def _ruta_capturas(self) -> Path:
        return Path(self.app.almacen.carpeta).parent / "capturas.json"

    def _leer_capturas(self) -> list:
        import json as _json
        try:
            datos = _json.loads(self._ruta_capturas().read_text(encoding="utf-8"))
            return [c for c in datos if isinstance(c, dict) and c.get("nombre")] if isinstance(datos, list) else []
        except (OSError, ValueError):
            return []

    def _quitar_captura(self, ident):
        import json as _json
        resto = [c for c in self._leer_capturas() if c.get("id") != ident]
        self._ruta_capturas().write_text(_json.dumps(resto, ensure_ascii=False, indent=2), encoding="utf-8")

    def _pintar_capturas(self, capturas):
        caja = ctk.CTkFrame(self.cuerpo, corner_radius=14, border_width=2, border_color=tema.PENDIENTE)
        caja.pack(fill="x", padx=8, pady=6)
        fila = ctk.CTkFrame(caja, fg_color="transparent")
        fila.pack(fill="x", padx=16, pady=(12, 2))
        ctk.CTkLabel(fila, text=f"📌 Capturados por el camino  ·  {len(capturas)}", font=fuente_titulo(17)).pack(side="left")
        ctk.CTkLabel(caja, text="Pueblos por los que pasaste, apuntados con «Capturar» en el móvil. Decide qué hacer con cada uno.",
                     text_color=tema.TINTA_2, font=fuente(12)).pack(anchor="w", padx=16)
        for c in sorted(capturas, key=lambda x: x.get("fecha", ""), reverse=True):
            f = ctk.CTkFrame(caja, fg_color=tema.TARJETA_2, corner_radius=10)
            f.pack(fill="x", padx=12, pady=4)
            fecha = c.get("fecha", "")
            try:
                a, m, d = fecha[:10].split("-")
                fecha_txt = f"{int(d)}/{int(m)}/{a}" + (f" · {fecha[11:16]}" if len(fecha) > 10 else "")
            except ValueError:
                fecha_txt = fecha
            ya = self.app.almacen.buscar(c["nombre"], c.get("provincia", ""))
            extra = (" · ya lo tienes (" + ("por visitar" if ya.get("estado") == "pendiente" else "visitado") + ")") if ya else ""
            txt = ctk.CTkFrame(f, fg_color="transparent")
            txt.pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(txt, text=c["nombre"], font=fuente(14, "bold")).pack(anchor="w")
            ctk.CTkLabel(txt, text=" · ".join(x for x in (c.get("provincia", ""), fecha_txt) if x) + extra,
                         text_color=tema.TINTA_2, font=fuente(12)).pack(anchor="w")
            boton(f, "✕", lambda c=c: self._captura(c, "quitar"), "fantasma", width=36).pack(side="right", padx=(0, 8))
            boton(f, "🗺", lambda c=c: webbrowser.open(
                f"https://www.openstreetmap.org/?mlat={c['lat']}&mlon={c['lon']}#map=14/{c['lat']}/{c['lon']}"),
                "fantasma", width=36).pack(side="right")
            boton(f, "Por visitar", lambda c=c: self._captura(c, "pendiente"), "pendiente", width=100).pack(side="right", padx=4)
            boton(f, "✓ Visitado", lambda c=c: self._captura(c, "visitado"), width=100).pack(side="right", padx=4)

    def _captura(self, c, que):
        app = self.app
        if que == "quitar":
            self._quitar_captura(c.get("id"))
            app.contar_cambios()
            self.refrescar()
            return
        fecha = (c.get("fecha") or date.today().isoformat())[:10]

        def tarea():
            p = app.almacen.buscar(c["nombre"], c.get("provincia", ""))
            if p:
                p = app.almacen.cargar(p["slug"])
            else:
                from nucleo.wiki import _todo_basico
                p = pueblo_vacio(c["nombre"])
                p.update(provincia=c.get("provincia", ""), comunidad=c.get("comunidad", ""), pais=c.get("pais") or "España",
                         estado=que, lat=c.get("lat"), lon=c.get("lon"))
                try:
                    d = _todo_basico(app.wiki, p["nombre"], p["provincia"], p["lat"], p["lon"])
                    if d:
                        app.aplicar_wiki(p, d)
                except Exception:  # noqa: BLE001  (sin conexión: se completa luego)
                    pass
                p.update(lat=c.get("lat"), lon=c.get("lon"))
            if que == "visitado":
                p["estado"] = "visitado"
                p["fechas_visita"] = sorted(set(p.get("fechas_visita") or []) | {fecha})
            if p.get("lat") is None:
                p.update(lat=c.get("lat"), lon=c.get("lon"))
            app.almacen.guardar(p)
            self._quitar_captura(c.get("id"))
            return p["slug"]

        def fin(slug):
            app.contar_cambios()
            app.estado(f"{c['nombre']}: " + (f"visitado el {fecha}." if que == "visitado" else "en «Por visitar»."))
            app.abrir(slug)
        app.en_segundo_plano(f"Añadiendo {c['nombre']}…", tarea, fin)


# ============================================================================ vista: diseño de la web
class VistaDiseno(ctk.CTkFrame):
    MINIATURAS = Path(__file__).resolve().parent / "nucleo" / "previas"

    def __init__(self, app):
        super().__init__(app.contenedor, fg_color="transparent")
        self.app = app
        self._imgs = {}
        self._tarjetas = {}
        self._programado = None

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", padx=28, pady=(22, 6))
        izq = ctk.CTkFrame(cab, fg_color="transparent")
        izq.pack(side="left")
        ctk.CTkLabel(izq, text="Diseño de la web", font=fuente_titulo(28)).pack(anchor="w")
        ctk.CTkLabel(izq, text="Abre «Vista previa» (abajo a la izquierda) y verás cada cambio al momento; «Publicar» lo sube a tu web.",
                     text_color=tema.TINTA_2, font=fuente(14)).pack(anchor="w")

        self.cuerpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.cuerpo.pack(fill="both", expand=True, padx=18, pady=(4, 12))
        self._construir()

    # ------------------------------------------------------------------ util
    @property
    def d(self):
        return D.normalizar(self.app.cfg.get("diseno"))

    def poner(self, clave, valor):
        d = dict(self.app.cfg.get("diseno") or {})
        d[clave] = valor
        self.app.cfg["diseno"] = d
        self.app.cfg.guardar()
        self._marcar()
        self.app.previa_cambiada()

    def _seccion(self, titulo, ayuda=""):
        t = ctk.CTkFrame(self.cuerpo, corner_radius=14)
        t.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(t, text=titulo, font=fuente_titulo(19)).pack(anchor="w", padx=18, pady=(14, 0))
        if ayuda:
            ctk.CTkLabel(t, text=ayuda, text_color=tema.TINTA_2).pack(anchor="w", padx=18)
        dentro = ctk.CTkFrame(t, fg_color="transparent")
        dentro.pack(fill="x", padx=12, pady=(8, 14))
        return dentro

    def _opcion(self, padre, grupo, valor, col, crear):
        """Tarjeta seleccionable; 'crear' rellena su interior."""
        f = ctk.CTkFrame(padre, corner_radius=12, border_width=3, fg_color=tema.TARJETA_2, cursor="hand2")
        f.grid(row=0, column=col, padx=6, pady=4, sticky="nsew")
        padre.columnconfigure(col, weight=1)
        crear(f)
        for w in [f] + list(f.winfo_children()) + [x for c in f.winfo_children() for x in c.winfo_children()]:
            w.bind("<Button-1>", lambda ev, g=grupo, v=valor: self.poner(g, v))
        self._tarjetas.setdefault(grupo, {})[valor] = f

    def _marcar(self):
        d = self.d
        for grupo, opciones in self._tarjetas.items():
            for valor, f in opciones.items():
                f.configure(border_color=tema.ACENTO if d.get(grupo) == valor else tema.TARJETA_2)
        for clave, var in getattr(self, "_vars", {}).items():
            var.set(bool(d.get(clave)))
        if hasattr(self, "seg_modo"):
            self.seg_modo.set({"auto": "Automático", "claro": "Siempre claro", "oscuro": "Siempre oscuro"}[d["modo"]])
            self.seg_orden.set("Mapa arriba" if d["mapa_primero"] else "Pueblos arriba")

    # ------------------------------------------------------------------ construcción
    def _construir(self):
        cfg = self.app.cfg
        # --- textos
        t = self._seccion("Textos", "Título, subtítulo y autor que aparecen en la web.")
        t.columnconfigure(1, weight=1)
        self._textos = {}
        for i, (clave, etiqueta) in enumerate((("titulo_web", "Título"), ("subtitulo_web", "Subtítulo"), ("autor", "Autor (pie de página)"))):
            ctk.CTkLabel(t, text=etiqueta, text_color=tema.TINTA_2).grid(row=i, column=0, sticky="w", padx=8, pady=5)
            e = ctk.CTkEntry(t, height=32)
            e.insert(0, cfg.get(clave, "") or "")
            e.grid(row=i, column=1, sticky="ew", padx=8, pady=5)
            e.bind("<KeyRelease>", lambda ev, c=clave, w=e: self._texto_cambiado(c, w))
            self._textos[clave] = e

        # --- estilo de página entera
        from nucleo.maquetas import MAQUETAS
        t = self._seccion("Estilo de página", "El aspecto de toda la web: portada, lista de pueblos y fichas.")
        for col, (valor, (nombre, desc)) in enumerate(MAQUETAS.items()):
            def crear(f, valor=valor, nombre=nombre, desc=desc):
                ruta = self.MINIATURAS / f"maqueta_{valor}.png"
                if ruta.exists():
                    with Image.open(ruta) as im:
                        pil = im.convert("RGB")
                    self._imgs["m_" + valor] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(220, int(220 * pil.height / pil.width)))
                    ctk.CTkLabel(f, text="", image=self._imgs["m_" + valor]).pack(padx=6, pady=(6, 0))
                ctk.CTkLabel(f, text=nombre, font=fuente(14, "bold")).pack(anchor="w", padx=10, pady=(6, 0))
                ctk.CTkLabel(f, text=desc, text_color=tema.TINTA_2, font=fuente(11), wraplength=210,
                             justify="left").pack(anchor="w", padx=10, pady=(0, 8))
            self._opcion(t, "maqueta", valor, col, crear)

        # --- cabecera
        t = self._seccion("Cabecera", "Cómo empieza tu página principal.")
        for col, (valor, (nombre, desc)) in enumerate(D.CABECERAS.items()):
            def crear(f, valor=valor, nombre=nombre, desc=desc):
                ruta = self.MINIATURAS / f"cabecera_{valor}.png"
                if ruta.exists():
                    with Image.open(ruta) as im:
                        pil = im.convert("RGB")
                    self._imgs[valor] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(220, int(220 * pil.height / pil.width)))
                    ctk.CTkLabel(f, text="", image=self._imgs[valor]).pack(padx=6, pady=(6, 0))
                ctk.CTkLabel(f, text=nombre, font=fuente(14, "bold")).pack(anchor="w", padx=10, pady=(6, 0))
                ctk.CTkLabel(f, text=desc, text_color=tema.TINTA_2, font=fuente(11), wraplength=210,
                             justify="left").pack(anchor="w", padx=10, pady=(0, 8))
            self._opcion(t, "cabecera", valor, col, crear)

        # --- colores
        t = self._seccion("Colores", "La paleta de toda la web (y del mapa).")
        for col, (valor, (nombre, claro, oscuro)) in enumerate(D.PALETAS.items()):
            def crear(f, nombre=nombre, claro=claro, oscuro=oscuro):
                fila = ctk.CTkFrame(f, fg_color="transparent")
                fila.pack(padx=10, pady=(10, 2))
                for k in ("papel", "acento", "acento-2", "pendiente", "tinta"):
                    ctk.CTkFrame(fila, width=26, height=26, corner_radius=13, fg_color=claro[k],
                                 border_width=1, border_color="#bbbbbb").pack(side="left", padx=2)
                fila2 = ctk.CTkFrame(f, fg_color="transparent")
                fila2.pack(padx=10, pady=(2, 4))
                for k in ("papel", "acento", "acento-2", "pendiente", "tinta"):
                    ctk.CTkFrame(fila2, width=14, height=14, corner_radius=7, fg_color=oscuro[k]).pack(side="left", padx=3)
                ctk.CTkLabel(f, text=nombre, font=fuente(13, "bold")).pack(pady=(2, 10))
            self._opcion(t, "paleta", valor, col, crear)
        ctk.CTkLabel(t, text="Arriba los colores de día; abajo, los de modo oscuro.", text_color=tema.TINTA_2,
                     font=fuente(11)).grid(row=1, column=0, columnspan=5, sticky="w", padx=8)

        # --- modo
        t = self._seccion("Modo claro / oscuro", "Cómo se ve al entrar. «Automático» sigue el móvil u ordenador de quien visita; con el botón ☀/☾ cada uno puede cambiarlo.")
        self.seg_modo = ctk.CTkSegmentedButton(t, values=["Automático", "Siempre claro", "Siempre oscuro"], height=34,
                                               command=lambda v: self.poner("modo", {"Automático": "auto", "Siempre claro": "claro", "Siempre oscuro": "oscuro"}[v]))
        self.seg_modo.pack(anchor="w", padx=8)

        # --- tipografía
        t = self._seccion("Tipografía", "Letra de los títulos y del texto.")
        for col, (valor, (nombre, f_tit, f_txt, _)) in enumerate(D.TIPOGRAFIAS.items()):
            def crear(f, nombre=nombre, f_tit=f_tit, f_txt=f_txt):
                ctk.CTkLabel(f, text="Aa", font=ctk.CTkFont(family=f_tit.split(",")[0].strip('"'), size=30, weight="bold")).pack(pady=(8, 0))
                ctk.CTkLabel(f, text=nombre, font=fuente(13, "bold")).pack()
                ctk.CTkLabel(f, text=f"{f_tit.split(',')[0].strip(chr(34))} + {f_txt.split(',')[0].strip(chr(34))}",
                             text_color=tema.TINTA_2, font=fuente(11), wraplength=150).pack(padx=8, pady=(0, 10))
            self._opcion(t, "tipografia", valor, col, crear)

        # --- fondo y secciones
        t = self._seccion("Fondo, secciones y extras")
        self._vars = {}
        opciones = (("azulejos", "Fondo de azulejos"), ("bandas", "Bandas de color"), ("mostrar_mapa", "Mostrar el mapa"),
                    ("mostrar_extra", "«Qué ver» y «Para saber más» en cada pueblo"),
                    ("cronologia", "Línea del tiempo de mis viajes"),
                    ("compartir", "Foto y título al compartir por WhatsApp"),
                    ("instalable", "Se puede instalar en el móvil como una app"),
                    ("ultima_visita", "«Última visita» al principio de la portada"),
                    ("rutas", "«Escapadas posibles» con mis pendientes"),
                    ("cielo_hora", "El dibujo de la cabecera cambia con la hora (día, atardecer, noche)"),
                    ("boton_tema", "Botón ☀/☾ para cambiar entre claro y oscuro"),
                    ("tiempo", "El tiempo que hace en cada pueblo"),
                    ("mapa_pueblo", "Mapa y «Cómo llegar» en cada pueblo"),
                    ("cercanos", "«Cerca de aquí»: mis pueblos cercanos"),
                    ("fiestas", "Fiestas de cada pueblo y «Próximas fiestas»"),
                    ("notas_a_mano", "Mis notas con letra manuscrita"))
        for i, (clave, texto) in enumerate(opciones):
            var = tk.BooleanVar(value=bool(self.d.get(clave)))
            ctk.CTkSwitch(t, text=texto, variable=var, command=lambda c=clave, v=var: self.poner(c, v.get())).grid(
                row=i // 2, column=i % 2, sticky="w", padx=10, pady=6)
            self._vars[clave] = var
        self.var_pend = tk.BooleanVar(value=self.app.cfg.get("mostrar_pendientes", True))
        ctk.CTkSwitch(t, text="Mostrar mis pueblos «por visitar»", variable=self.var_pend,
                      command=self._pendientes).grid(row=9, column=0, sticky="w", padx=10, pady=6)
        fila = ctk.CTkFrame(t, fg_color="transparent")
        fila.grid(row=10, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0))
        ctk.CTkLabel(fila, text="Orden:").pack(side="left", padx=(4, 10))
        self.seg_orden = ctk.CTkSegmentedButton(fila, values=["Mapa arriba", "Pueblos arriba"], height=32,
                                                command=lambda v: self.poner("mapa_primero", v == "Mapa arriba"))
        self.seg_orden.pack(side="left")

        # --- logo
        t = self._seccion("Logo / icono", "Se ve junto al título y en la pestaña del navegador. Mejor una imagen cuadrada.")
        fila = ctk.CTkFrame(t, fg_color="transparent")
        fila.pack(anchor="w", padx=6)
        self.lbl_logo = ctk.CTkLabel(fila, text="", width=72, height=72, fg_color=tema.TARJETA_2, corner_radius=14)
        self.lbl_logo.pack(side="left", padx=(4, 14))
        boton(fila, "Elegir imagen…", self._elegir_logo, "secundario").pack(side="left", padx=4)
        boton(fila, "Quitar", self._quitar_logo, "fantasma", width=80).pack(side="left", padx=4)
        self._pintar_logo()
        self._marcar()

    # ------------------------------------------------------------------ acciones
    def refrescar(self):
        self._marcar()

    def _texto_cambiado(self, clave, entrada):
        self.app.cfg[clave] = entrada.get().strip()
        self.app.cfg.guardar()
        self.app.previa_cambiada()

    def _pendientes(self):
        self.app.cfg["mostrar_pendientes"] = self.var_pend.get()
        self.app.cfg.guardar()
        self.app.previa_cambiada()

    def _pintar_logo(self):
        ruta = self.app.cfg.get("logo_ruta")
        if ruta and Path(ruta).exists():
            with Image.open(ruta) as im:
                pil = im.convert("RGBA")
            self._imgs["logo"] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(72, 72))
            self.lbl_logo.configure(image=self._imgs["logo"], text="")
        else:
            self.lbl_logo.configure(image=None, text="Sin logo", text_color=tema.TINTA_2)

    def _elegir_logo(self):
        ruta = filedialog.askopenfilename(parent=self, title="Elige tu logo o icono",
                                          filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            with Image.open(ruta) as im:
                im = ImageOps.exif_transpose(im).convert("RGBA")
                lado = min(im.size)
                im = im.crop(((im.width - lado) // 2, (im.height - lado) // 2,
                              (im.width + lado) // 2, (im.height + lado) // 2)).resize((256, 256), Image.LANCZOS)
            destino = BASE / "diseno" / "logo.png"
            destino.parent.mkdir(parents=True, exist_ok=True)
            im.save(destino, "PNG", optimize=True)
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror(NOMBRE_PROGRAMA, f"No he podido abrir esa imagen:\n{ex}")
            return
        self.app.cfg["logo_ruta"] = str(destino)
        self.app.cfg.guardar()
        self._pintar_logo()
        self.app.previa_cambiada()

    def _quitar_logo(self):
        self.app.cfg["logo_ruta"] = ""
        self.app.cfg.guardar()
        self._pintar_logo()
        self.app.previa_cambiada()

# ============================================================================ aplicación
class App(ctk.CTk):
    def __init__(self):
        self.cfg = Config()
        tema.aplicar(self.cfg.get("tema", "System"))
        super().__init__()
        self.title(f"{NOMBRE_PROGRAMA} {VERSION} — Mis pueblos")
        accesos.poner_icono_ventana(self)
        self.after(300, lambda: accesos.poner_icono_ventana(self))   # (customtkinter pone el suyo a los 200 ms)
        self.geometry("1320x860")
        self.minsize(1080, 700)
        self.almacen = Almacen(self.cfg.datos)
        self.geo = Geocodificador(self.cfg.user_agent, self.cfg.datos / "_cache_geo.json")
        self.wiki = Wikipedia(self.cfg.user_agent)
        self.commons = Commons(self.cfg.user_agent)
        self.actual = None
        self.vista = None
        self.vista_anterior = "mapa"
        self._cache_img = {}
        self.cola = queue.Queue()
        self.ocupado = False

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._barra_lateral()
        derecha = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        derecha.grid(row=0, column=1, sticky="nsew")
        derecha.rowconfigure(0, weight=1)
        derecha.columnconfigure(0, weight=1)
        self.contenedor = ctk.CTkFrame(derecha, fg_color="transparent", corner_radius=0)
        self.contenedor.grid(row=0, column=0, sticky="nsew")
        estado = ctk.CTkFrame(derecha, fg_color=tema.TARJETA_2, corner_radius=0, height=34)
        estado.grid(row=1, column=0, sticky="ew")
        self.lbl_estado = ctk.CTkLabel(estado, text="Listo.", text_color=tema.TINTA_2, font=fuente(12))
        self.lbl_estado.pack(side="left", padx=16, pady=4)
        self.progreso = ctk.CTkProgressBar(estado, width=220, height=6)
        self.progreso.set(0)

        self.vistas = {"mapa": VistaMapa(self), "visitados": VistaLista(self, "visitado"),
                       "pendientes": VistaLista(self, "pendiente"), "revisar": VistaRevisar(self), "diseno": VistaDiseno(self),
                       "editor": VistaEditor(self)}
        self._previa_abierta = False
        self._previa_trabajo = None
        self._previa_hilo = None
        self._actualizacion_preguntada = False
        configurar_token(self.cfg.get("github_token"))
        self.mostrar("mapa")
        self.after(100, self._atender_cola)
        self.protocol("WM_DELETE_WINDOW", self.salir)
        self.after(600, lambda: self.sincronizar(silencioso=True))
        self.after(4000, self._vigilar_cambios)
        self.after(6000, self._acceso_directo_inicial)
        self.after(20000, self._copia_automatica)

    # ------------------------------------------------------------------ barra lateral
    def _barra_lateral(self):
        lat = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=tema.LATERAL)
        lat.grid(row=0, column=0, sticky="nsw")
        lat.grid_propagate(False)
        lat.pack_propagate(False)
        t1 = ctk.CTkLabel(lat, text="PUEBLOS", font=fuente_titulo(24), text_color=tema.LATERAL_TEXTO, cursor="hand2")
        t1.pack(anchor="w", padx=22, pady=(24, 0))
        self.lbl_version = ctk.CTkLabel(lat, text=f"cuaderno de viaje · {VERSION}", font=fuente(11), cursor="hand2",
                                        text_color=tema.LATERAL_TEXTO_2)
        self.lbl_version.pack(anchor="w", padx=22, pady=(0, 22))
        for w in (t1, self.lbl_version):
            w.bind("<Button-1>", lambda e: self.ajustes("Programa"))
        self.nav = {}
        for clave, texto in (("mapa", "🗺   Mapa"), ("visitados", "🏘   Visitados"), ("pendientes", "📌   Por visitar"),
                             ("revisar", "✔   Revisar"), ("diseno", "🎨   Diseño")):
            b = ctk.CTkButton(lat, text=texto, anchor="w", height=40, corner_radius=8, font=fuente(14),
                              fg_color="transparent", hover_color=tema.LATERAL_HOVER, text_color=tema.LATERAL_TEXTO,
                              command=lambda c=clave: self.mostrar(c))
            b.pack(fill="x", padx=12, pady=2)
            self.nav[clave] = b
        ctk.CTkFrame(lat, height=1, fg_color=tema.LATERAL_HOVER).pack(fill="x", padx=20, pady=14)
        self.btn_anadir = ctk.CTkButton(lat, text="＋   Añadir", anchor="w", height=38, corner_radius=8, font=fuente(14, "bold"),
                                        fg_color=tema.LATERAL_HOVER, hover_color=tema.ACENTO_HOVER, text_color=tema.LATERAL_TEXTO,
                                        command=lambda: self._menu(self.btn_anadir, [
                                            ("📷  Fotos de un viaje (crea los pueblos solos)…", self.importar),
                                            ("🏘  Un pueblo visitado", lambda: self.nuevo("visitado")),
                                            ("📌  Un pueblo por visitar", lambda: self.nuevo("pendiente")),
                                            (None, None),
                                            ("💡  Ideas de pueblos para visitar…", self.ideas)]))
        self.btn_anadir.pack(fill="x", padx=12, pady=2)

        abajo = ctk.CTkFrame(lat, fg_color="transparent")
        abajo.pack(side="bottom", fill="x", padx=12, pady=16)
        self.btn_publicar = ctk.CTkButton(abajo, text="🚀   Publicar", height=42, corner_radius=10, font=fuente(14, "bold"),
                                          command=self.publicar)
        self.btn_publicar.pack(fill="x", pady=(0, 2))
        self.lbl_cambios = ctk.CTkLabel(abajo, text="", font=fuente(11), text_color=tema.LATERAL_TEXTO_2, height=16)
        self.lbl_cambios.pack(fill="x", pady=(0, 6))
        ctk.CTkButton(abajo, text="👁   Vista previa", height=36, corner_radius=8, font=fuente(13),
                      fg_color=tema.LATERAL_HOVER, hover_color=tema.ACENTO_HOVER, text_color=tema.LATERAL_TEXTO,
                      command=self.vista_previa).pack(fill="x", pady=3)
        fila = ctk.CTkFrame(abajo, fg_color="transparent")
        fila.pack(fill="x", pady=(4, 0))
        estilo = dict(height=36, corner_radius=8, font=fuente(13), fg_color=tema.LATERAL_HOVER,
                      hover_color=tema.ACENTO_HOVER, text_color=tema.LATERAL_TEXTO)
        self.btn_web = ctk.CTkButton(fila, text="🌐  Mi web  ▾", anchor="w", width=60, **estilo,
                                     command=lambda: self._menu(self.btn_web, [
                                         ("Mi web", None),
                                         ("🌐  Abrir mi web", self.abrir_web),
                                         ("📋  Copiar el enlace", self._copiar_enlace),
                                         ("Panel del móvil", None),
                                         ("📱  Abrir el panel", self.abrir_panel),
                                         ("⟳  Traer ya lo hecho en el móvil", self.sincronizar),
                                         ("GitHub", None),
                                         ("🗂  Ver mis archivos en GitHub", self._abrir_github)], arriba=True))
        self.btn_web.pack(side="left", fill="x", expand=True)
        self.btn_sinc = self.btn_web       # (lo usa la sincronización para mostrar que está ocupada)
        ctk.CTkButton(fila, text="⚙", width=36, **estilo, command=self.ajustes).pack(side="left", padx=(4, 0))
        ctk.CTkButton(fila, text="?", width=36, **dict(estilo, font=fuente(14, "bold")), command=self.ayuda).pack(side="left", padx=(4, 0))


    def _menu(self, boton_, opciones, arriba=False):
        """Menú desplegable con el aspecto del programa. (texto, None) = encabezado; (None, None) = separador."""
        self._cerrar_menu()
        p = ctk.CTkToplevel(self)
        p.withdraw()
        p.overrideredirect(True)
        p.configure(fg_color=tema.LINEA)
        marco = ctk.CTkFrame(p, corner_radius=0, fg_color=tema.TARJETA)
        marco.pack(fill="both", expand=True, padx=1, pady=1)
        for texto, cmd in opciones:
            if texto is None:
                ctk.CTkFrame(marco, height=1, fg_color=tema.LINEA).pack(fill="x", padx=10, pady=5)
            elif cmd is None:
                ctk.CTkLabel(marco, text=texto, font=fuente(10, "bold"), text_color=tema.TINTA_2, anchor="w",
                             height=22).pack(fill="x", padx=16, pady=(8, 0))
            else:
                ctk.CTkButton(marco, text=texto, anchor="w", height=34, corner_radius=8, font=fuente(13),
                              fg_color="transparent", hover_color=tema.TARJETA_2, text_color=tema.TINTA,
                              command=lambda c=cmd: (self._cerrar_menu(), self.after(10, c))).pack(fill="x", padx=6, pady=1)
        ctk.CTkFrame(marco, height=6, fg_color="transparent").pack()
        p.update_idletasks()
        w, h = max(270, p.winfo_reqwidth()), p.winfo_reqheight()
        x = boton_.winfo_rootx()
        y = boton_.winfo_rooty() - h - 4 if arriba else boton_.winfo_rooty() + boton_.winfo_height() + 4
        p.geometry(f"{w}x{h}+{x}+{max(0, y)}")
        p.deiconify()
        p.lift()
        self._popup = p

        def fuera(ev):
            try:
                if self._popup and str(ev.widget).startswith(str(self._popup)):
                    return
            except Exception:  # noqa: BLE001
                pass
            self._cerrar_menu()
        self._popup_clic = self.bind_all("<Button-1>", fuera, add="+")
        self.bind_all("<Escape>", lambda e: self._cerrar_menu(), add="+")
        self.bind("<Configure>", lambda e: self._cerrar_menu() if e.widget is self else None, add="+")

    def _cerrar_menu(self):
        p = getattr(self, "_popup", None)
        self._popup = None
        if p is not None:
            try:
                p.destroy()
            except tk.TclError:
                pass
        if getattr(self, "_popup_clic", None):
            try:
                self.unbind_all("<Button-1>")
            except tk.TclError:
                pass
            self._popup_clic = None

    def _abrir_github(self):
        url = (self.cfg.get("repo_url") or "").removesuffix(".git")
        if url:
            webbrowser.open(url)
        else:
            self.ajustes("GitHub")

    # ------------------------------------------------------------------ acerca de / buscar actualizaciones
    def _texto_comprobado(self):
        hecho = self.cfg.get("ultima_busqueda_act")
        return f"Última comprobación: {hecho}" if hecho else "Se comprueba sola cada vez que abres el programa."

    def _historial(self) -> str:
        try:
            texto = (BASE / "LEEME.md").read_text(encoding="utf-8")
        except OSError:
            return "(No encuentro LEEME.md)"
        parte = texto.split("## Historial", 1)[-1].strip()
        import re as _re
        parte = _re.sub(r"\*\*([^*]+)\*\*", r"\1", parte)
        lineas = []
        for l in parte.splitlines():
            if l.startswith("- "):
                lineas.append("• " + l[2:].strip())
            elif l.strip() and lineas:
                lineas[-1] += " " + l.strip()          # el LEEME parte las líneas largas: se juntan
        return "\n\n".join(lineas)

    def ayuda(self):
        """Las instrucciones del LEEME, en una ventana del programa (sin depender de qué abre los .md)."""
        import re as _re
        try:
            texto = (BASE / "LEEME.md").read_text(encoding="utf-8")
        except OSError:
            texto = ""
        secciones = _re.split(r"^## ", texto, flags=_re.M)[1:]
        v = self.dialogo("Ayuda", 760, min(700, self.winfo_screenheight() - 100))
        ctk.CTkLabel(v, text="❓ Ayuda", font=fuente_titulo(24)).pack(anchor="w", padx=24, pady=(18, 4))
        caja = ctk.CTkTextbox(v, wrap="word", font=fuente(14))
        caja.pack(fill="both", expand=True, padx=20, pady=(4, 10))
        caja.tag_config("titulo", spacing1=14, spacing3=6)
        orden = []
        for sec in secciones:
            titulo, _, cuerpo = sec.partition("\n")
            t = titulo.strip()
            if t.lower().startswith(("historial", "qué hay")):
                continue
            orden.append((1 if t.lower().startswith("instalar") else 0, t, cuerpo))
        for _, titulo, cuerpo in sorted(orden, key=lambda x: x[0]):
            caja.insert("end", titulo.upper() + "\n", "titulo")
            parrafos_ = []
            for linea in cuerpo.strip().splitlines():
                l = _re.sub(r"\*\*([^*]+)\*\*", r"\1", linea)
                l = _re.sub(r"\*([^*]+)\*", r"\1", l).replace("`", "")
                if not l.strip():
                    parrafos_.append("")
                elif l.startswith("- ") or _re.match(r"^\d+\. ", l):
                    parrafos_.append(("•  " + l[2:]) if l.startswith("- ") else l)
                elif parrafos_ and parrafos_[-1]:
                    parrafos_[-1] += " " + l.strip()      # continuación de la línea anterior
                else:
                    parrafos_.append(l.strip())
            caja.insert("end", "\n".join(p for p in parrafos_ if p is not None).strip() + "\n\n")
        if not secciones:
            caja.insert("end", "No encuentro el archivo de instrucciones (LEEME.md).")
        caja.configure(state="disabled")
        pie = ctk.CTkFrame(v, fg_color="transparent")
        pie.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkLabel(pie, text="¿Algo no va? Ajustes (⚙) → Programa → Buscar actualizaciones.",
                     text_color=tema.TINTA_2, font=fuente(12)).pack(side="left")
        boton(pie, "Cerrar", v.destroy, "secundario", width=100).pack(side="right")

    def buscar_actualizaciones(self, ventana=None):
        if not self.cfg.get("repo_url") or not git_disponible():
            messagebox.showinfo(NOMBRE_PROGRAMA, "Para buscar actualizaciones necesitas git y tu repositorio de GitHub en Ajustes.",
                                parent=ventana)
            return
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        repo = Path(self.cfg.get("carpeta_repo") or (Path(self.cfg.sitio).parent / "repo"))

        def tarea():
            nuevo = Sincronizador(self.cfg, lambda t: self.cola.put(("estado", t))).traer()
            return nuevo, actualizar.disponible(repo, VERSION)

        def fin(res):
            import time as _t
            nuevo, info = res
            self.cfg["ultima_busqueda_act"] = _t.strftime("%d/%m/%Y %H:%M")
            self.cfg.guardar()
            try:
                self.lbl_buscar.configure(text=self._texto_comprobado())
            except (tk.TclError, AttributeError):
                pass
            self._actualizacion_preguntada = False     # que vuelva a preguntar aunque antes dijeras que no
            self._tras_sincronizar(nuevo)              # (si hay versión nueva, aquí se pregunta si instalarla)
            if not info:
                messagebox.showinfo(NOMBRE_PROGRAMA, f"Tienes la última versión ({VERSION}). ✅", parent=ventana)
        self.en_segundo_plano("Buscando actualizaciones…", tarea, fin)

    def _copiar_enlace(self):
        url = url_web(self.cfg.get("repo_url") or "")
        if url:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.estado(f"Enlace copiado: {url}")

    # ------------------------------------------------------------------ cambios sin publicar
    def contar_cambios(self):
        """Cuántos pueblos (y si el diseño) han cambiado desde la última publicación. Sin bloquear la ventana."""
        if getattr(self, "_contando", False):
            return
        self._contando = True

        def hilo():
            n = 0
            try:
                from nucleo.publicar import _git
                import json as _json
                repo = Path(self.cfg.get("carpeta_repo") or (Path(self.cfg.sitio).parent / "repo"))
                if not (repo / ".git").exists():
                    n = -1
                else:
                    r = _git(["status", "--porcelain", "--", "datos"], repo, comprobar=False)
                    slugs = {l[3:].strip().strip('"').split("/")[1] for l in r.stdout.splitlines()
                             if l[3:].strip().strip('"').startswith("datos/") and "/" in l[3:].strip().strip('"')[6:]}
                    n = len({x for x in slugs if not x.startswith("_")})
                    if _git(["status", "--porcelain", "--", "capturas.json"], repo, comprobar=False).stdout.strip():
                        n += 1          # capturas del móvil ya revisadas aquí
                    try:
                        hay = _json.loads((repo / "ajustes_web.json").read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        hay = {}
                    quiero = {k: self.cfg.get(k) for k in ("titulo_web", "subtitulo_web", "autor", "mostrar_pendientes")}
                    quiero["diseno"] = self.cfg.get("diseno") or {}
                    if any(hay.get(k) != v for k, v in quiero.items()):
                        n += 1
            except Exception:  # noqa: BLE001
                n = -1
            self.cola.put(("llamar", lambda: self._pintar_cambios(n)))
        threading.Thread(target=hilo, daemon=True).start()

    def _pintar_cambios(self, n):
        self._contando = False
        self.cambios = max(n, 0)
        if n > 0:
            self.btn_publicar.configure(text=f"🚀   Publicar  ·  {n}")
            self.lbl_cambios.configure(text=f"{n} {'cambio' if n == 1 else 'cambios'} sin publicar")
        else:
            self.btn_publicar.configure(text="🚀   Publicar")
            self.lbl_cambios.configure(text="Todo publicado" if n == 0 else "")

    def _acceso_directo_inicial(self):
        """La primera vez (y tras actualizar a la versión que lo trae): acceso directo con el icono."""
        import sys as _s
        if _s.platform != "win32" or self.cfg.get("acceso_directo_hecho"):
            return

        def hilo():
            try:
                hechos = accesos.crear(BASE)
                self.cola.put(("estado", "Acceso directo «PUEBLOS» creado en el escritorio y en el menú Inicio."))
                self.cola.put(("llamar", lambda: (self.cfg.__setitem__("acceso_directo_hecho", True), self.cfg.guardar())))
            except Exception as ex:  # noqa: BLE001
                self.cola.put(("estado", f"No se pudo crear el acceso directo: {ex}"))
        threading.Thread(target=hilo, daemon=True).start()

    def crear_acceso_directo(self, ventana=None):
        try:
            hechos = accesos.crear(BASE)
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror(NOMBRE_PROGRAMA, f"No se pudo crear el acceso directo:\n{ex}", parent=ventana)
            return
        if not hechos:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Los accesos directos solo se pueden crear en Windows.", parent=ventana)
            return
        self.cfg["acceso_directo_hecho"] = True
        self.cfg.guardar()
        messagebox.showinfo(NOMBRE_PROGRAMA, "Listo: tienes «PUEBLOS» con su icono en el escritorio y en el menú Inicio.",
                            parent=ventana)

    def _copia_automatica(self):
        from nucleo import copia as CO
        if CO.toca(self.cfg):
            self.copia_seguridad(silenciosa=True)

    def _vigilar_cambios(self):
        self.contar_cambios()
        self.after(12000, self._vigilar_cambios)

    def _cambiar_tema(self, nombre):
        self.cfg["tema"] = TEMAS[nombre]
        self.cfg.guardar()
        ctk.set_appearance_mode(TEMAS[nombre])
        self.after(150, self.vistas["mapa"].programar)

    # ------------------------------------------------------------------ navegación
    def mostrar(self, clave, recargar=True):
        if self.vista == "editor" and clave != "editor":
            self.vistas["editor"].guardar(silencioso=True)
        for v in self.vistas.values():
            v.pack_forget()
        self.vistas[clave].pack(fill="both", expand=True)
        if clave != "editor":
            self.vista_anterior = clave
            if recargar:
                self.vistas[clave].refrescar()
        self.vista = clave
        if clave == "editor" and self.actual:
            seccion = "pendientes" if self.actual.get("estado") == "pendiente" else "visitados"
        else:
            seccion = clave
        for k, b in self.nav.items():
            activo = k == seccion
            b.configure(fg_color=tema.ACENTO if activo else "transparent")

    def volver(self, guardar=True):
        if guardar and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        self.actual = None
        self.vista = None
        self.mostrar(self.vista_anterior)

    def abrir(self, slug, recargar=False):
        if self.vista == "editor" and self.actual and self.actual.get("slug") != slug:
            self.vistas["editor"].guardar(silencioso=True)
        try:
            self.actual = self.almacen.cargar(slug)
        except OSError:
            return
        if recargar:
            self._cache_img = {k: v for k, v in self._cache_img.items() if k[0] != slug}
        self.mostrar("editor")
        self.vistas["editor"].cargar()

    # ------------------------------------------------------------------ imágenes
    def miniatura(self, slug, archivo, ancho, alto):
        if not archivo:
            return None
        clave = (slug, archivo, ancho, alto)
        if clave not in self._cache_img:
            ruta = self.almacen.carpeta_pueblo(slug) / "mini" / archivo
            if not ruta.exists():
                ruta = self.almacen.carpeta_pueblo(slug) / "fotos" / archivo
            try:
                with Image.open(ruta) as im:
                    pil = recorte(im, ancho * 2, alto * 2)
                self._cache_img[clave] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(ancho, alto))
            except Exception:  # noqa: BLE001
                return None
        return self._cache_img[clave]

    # ------------------------------------------------------------------ diálogos genéricos
    def dialogo(self, titulo, ancho, alto):
        v = ctk.CTkToplevel(self)
        v.title(titulo)
        v.after(300, lambda: accesos.poner_icono_ventana(v))
        v.geometry(f"{ancho}x{alto}+{self.winfo_rootx() + 120}+{self.winfo_rooty() + 60}")
        v.transient(self)

        def enfocar():
            try:
                v.lift()
                v.focus_force()
                v.grab_set()
            except tk.TclError:
                pass
        v.after(150, enfocar)
        return v

    def pedir_texto(self, titulo, texto, inicial=""):
        v = self.dialogo(titulo, 480, 210 if "\n" in texto else 190)
        ctk.CTkLabel(v, text=texto, font=fuente(14), justify="left").pack(anchor="w", padx=20, pady=(20, 6))
        var = tk.StringVar(value=inicial)
        e = ctk.CTkEntry(v, textvariable=var, height=36)
        e.pack(fill="x", padx=20)
        e.after(250, e.focus_set)
        res = {}

        def ok(_=None):
            res["t"] = var.get()
            v.destroy()
        e.bind("<Return>", ok)
        b = ctk.CTkFrame(v, fg_color="transparent")
        b.pack(fill="x", padx=20, pady=18)
        boton(b, "Aceptar", ok, width=100).pack(side="right")
        boton(b, "Cancelar", v.destroy, "secundario", width=100).pack(side="right", padx=8)
        self.wait_window(v)
        return res.get("t")

    def elegir_lugar(self, resultados, texto=""):
        v = self.dialogo("¿Cuál es?", 720, 480)
        ctk.CTkLabel(v, text=f"Hay varios lugares que se llaman «{texto.split(',')[0]}»" if texto else
                     "Hay varios lugares con ese nombre", font=fuente_titulo(19)).pack(anchor="w", padx=20, pady=(18, 0))
        ctk.CTkLabel(v, text="El primero es el más probable. Elige el tuyo:", text_color=tema.TINTA_2).pack(
            anchor="w", padx=20, pady=(0, 8))
        lista = ctk.CTkScrollableFrame(v)
        lista.pack(fill="both", expand=True, padx=20)
        res = {}
        actual = (self.actual or {}).get("slug")
        mios = [q for q in self.almacen.listar() if q.get("lat") is not None and q.get("slug") != actual]

        def elegir(r):
            res["r"] = r
            v.destroy()
        for r in resultados:
            fila = ctk.CTkFrame(lista, corner_radius=10, fg_color=tema.TARJETA_2, cursor="hand2")
            fila.pack(fill="x", pady=3, padx=2)
            img = mini_mapa((r["lat"], r["lon"]), 96, 72)
            foto = ctk.CTkImage(light_image=img, dark_image=img, size=(96, 72))
            mapa_lbl = ctk.CTkLabel(fila, text="", image=foto)
            mapa_lbl.pack(side="left", padx=8, pady=6)
            txt = ctk.CTkFrame(fila, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True, pady=6)
            cerca = ""
            if mios:
                from nucleo.extras import distancia_km
                q = min(mios, key=lambda q: distancia_km((r["lat"], r["lon"]), (q["lat"], q["lon"])))
                km = distancia_km((r["lat"], r["lon"]), (q["lat"], q["lon"]))
                if km < 1 and normalizar(q["nombre"]) == normalizar(r["nombre"]):
                    cerca = " · ya lo tienes"
                elif km < 150:
                    cerca = f" · a {'menos de 1' if km < 1 else round(km)} km de {q['nombre']}"
            ctk.CTkLabel(txt, text=r["nombre"], font=fuente(15, "bold"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(txt, text=r.get("descripcion", "") + cerca, text_color=tema.TINTA_2, anchor="w",
                         font=fuente(12)).pack(anchor="w")
            boton(fila, "Este", lambda r=r: elegir(r), width=70).pack(side="right", padx=10)
            for w in (fila, mapa_lbl, txt) + tuple(txt.winfo_children()):
                w.bind("<Button-1>", lambda ev, r=r: elegir(r))
        boton(v, "Cancelar", v.destroy, "secundario", width=100).pack(anchor="e", padx=20, pady=14)
        self.wait_window(v)
        return res.get("r")

    # ------------------------------------------------------------------ pueblos nuevos
    def nuevo(self, estado="visitado", provincia=""):
        titulo = "Nuevo pueblo visitado" if estado == "visitado" else "Pueblo por visitar"
        nombre = self.pedir_texto(titulo, "Nombre del pueblo:")
        if not nombre or not nombre.strip():
            return
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        fecha = ""
        if estado == "visitado":
            fecha = self.pedir_fecha("¿Cuándo lo visitaste? (opcional)")
            if fecha is None:
                return
        p = pueblo_vacio(nombre.strip())
        p["estado"] = estado
        p["provincia"] = provincia
        if fecha:
            p["fechas_visita"] = [fecha]
        self.almacen.guardar(p)
        if estado == "pendiente":
            self.vista_anterior = "pendientes"
        elif self.vista_anterior == "pendientes":
            self.vista_anterior = "visitados"
        self.abrir(p["slug"])
        ed = self.vistas["editor"]
        # Ubicación -> Wikipedia -> fotos de internet (si no tiene)
        ed.buscar_ubicacion(despues=lambda: ed.traer_wiki(despues=self._ofrecer_fotos_internet))

    # ------------------------------------------------------------------ ideas de pueblos
    def ideas(self):
        from nucleo import ideas as IDE
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        pueblos = self.almacen.listar()
        self.en_segundo_plano("Buscando ideas en Wikidata (Los Pueblos más Bonitos de España y pueblos con patrimonio "
                              "cerca de los tuyos)…", lambda: IDE.sugerencias(self.wiki.sesion, pueblos), self._dialogo_ideas)

    def _dialogo_ideas(self, ideas):
        if not ideas:
            messagebox.showinfo(NOMBRE_PROGRAMA, "No he encontrado ideas nuevas ahora mismo. Prueba más tarde.")
            return
        v = self.dialogo("Ideas de pueblos para visitar", 820, 700)
        ctk.CTkLabel(v, text="💡 Ideas de pueblos para visitar", font=fuente_titulo(22)).pack(anchor="w", padx=22, pady=(18, 0))
        ctk.CTkLabel(v, text="Marca los que te apetezcan y se añaden a «Por visitar» (con su ubicación y datos de Wikipedia). "
                     "Salen ordenados por cercanía a los pueblos que ya visitaste.", text_color=tema.TINTA_2,
                     wraplength=760, justify="left").pack(anchor="w", padx=22, pady=(0, 8))
        filtro = ctk.CTkSegmentedButton(v, values=["Todas", "Pueblos más bonitos", "Cerca de mis pueblos"])
        filtro.set("Todas")
        filtro.pack(anchor="w", padx=22, pady=(0, 8))
        lista = ctk.CTkScrollableFrame(v)
        lista.pack(fill="both", expand=True, padx=20)
        marcas = []

        def pintar(_=None):
            for w in lista.winfo_children():
                w.destroy()
            marcas.clear()
            modo = filtro.get()
            for it in ideas:
                if modo == "Pueblos más bonitos" and "Bonitos" not in it["motivo"]:
                    continue
                if modo == "Cerca de mis pueblos" and "cerca" not in it["motivo"].lower():
                    continue
                fila = ctk.CTkFrame(lista, corner_radius=10, fg_color=tema.TARJETA_2)
                fila.pack(fill="x", pady=3, padx=2)
                var = tk.BooleanVar(value=False)
                ctk.CTkCheckBox(fila, text=it["nombre"], variable=var, font=fuente(14, "bold")).pack(side="left", padx=10, pady=8)
                etiquetas = (["🏅 Más bonitos"] if "Bonitos" in it["motivo"] else []) + (
                    ["🏛 Patrimonio"] if "atrimonio" in it["motivo"] else [])
                detalle = " · ".join([it.get("zona", "")] + etiquetas if it.get("zona") else etiquetas)
                ctk.CTkLabel(fila, text=detalle, text_color=tema.TINTA_2, font=fuente(12)).pack(side="left", padx=6)
                if it.get("km") is not None:
                    ctk.CTkLabel(fila, text=f"a {it['km']} km de {it['cerca_de']}", text_color=tema.TINTA_2,
                                 font=fuente(12)).pack(side="right", padx=12)
                marcas.append((var, it))
        filtro.configure(command=pintar)
        pintar()
        abajo = ctk.CTkFrame(v, fg_color="transparent")
        abajo.pack(fill="x", padx=20, pady=14)

        def aceptar():
            elegidos = [it for var, it in marcas if var.get()]
            if not elegidos:
                messagebox.showinfo(NOMBRE_PROGRAMA, "No has marcado ninguno.", parent=v)
                return
            v.destroy()
            from nucleo.wiki import _todo_basico

            def tarea():
                hechos = 0
                for i, it in enumerate(elegidos, 1):
                    self._progreso(i, len(elegidos), it["nombre"])
                    p = pueblo_vacio(it["nombre"])
                    p.update(estado="pendiente", lat=it["lat"], lon=it["lon"])
                    try:
                        lugar = self.geo.inverso(it["lat"], it["lon"]) or {}
                        p["provincia"] = lugar.get("provincia", "")
                        p["comunidad"] = lugar.get("comunidad", "")
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        d = _todo_basico(self.wiki, p["nombre"], p["provincia"], p["lat"], p["lon"])
                        if d:
                            self.aplicar_wiki(p, d)
                    except Exception:  # noqa: BLE001
                        pass
                    self.almacen.guardar(p)
                    hechos += 1
                return hechos

            def fin(n):
                self.estado(f"Añadidos {n} pueblos a «Por visitar». En «Revisar» puedes completarlos.")
                self.mostrar("pendientes")
                self.contar_cambios()
            self.en_segundo_plano("Añadiendo a «Por visitar»…", tarea, fin)
        boton(abajo, "Añadir a «Por visitar»", aceptar, "pendiente").pack(side="right")
        boton(abajo, "Cancelar", v.destroy, "secundario", width=100).pack(side="right", padx=8)
        ctk.CTkLabel(abajo, text=f"{len(ideas)} ideas · datos de Wikidata", text_color=tema.TINTA_2).pack(side="left")

    # ------------------------------------------------------------------ copia de seguridad
    def copia_seguridad(self, silenciosa=False):
        from nucleo import copia as CO
        destino = self.cfg.get("copia_carpeta")
        if not destino:
            return
        repo = Path(self.cfg.get("carpeta_repo") or (Path(self.cfg.sitio).parent / "repo"))

        def tarea():
            return CO.hacer_copia(repo, BASE, Path(destino), avisar=lambda t: self.cola.put(("estado", t)))

        def fin(ruta):
            import time as _t
            self.cfg["copia_ultima"] = _t.strftime("%Y-%m-%d %H:%M")
            self.cfg.guardar()
            self.estado(f"💾 Copia de seguridad guardada: {ruta}")
            if not silenciosa:
                messagebox.showinfo(NOMBRE_PROGRAMA, f"Copia de seguridad guardada en:\n{ruta}")

        if silenciosa:
            def hilo():
                try:
                    ruta = tarea()
                    self.cola.put(("llamar", lambda: fin(ruta)))
                except Exception as ex:  # noqa: BLE001  (p. ej., el NAS está apagado)
                    self.cola.put(("estado", f"No se pudo hacer la copia de seguridad automática: {ex}"))
            threading.Thread(target=hilo, daemon=True).start()
        else:
            self.en_segundo_plano("Haciendo la copia de seguridad…", tarea, fin)

    def _ofrecer_fotos_internet(self):
        if self.actual and not self.actual["fotos"] and messagebox.askyesno(
                NOMBRE_PROGRAMA, "Este pueblo aún no tiene fotos. Si no tienes fotos tuyas, puedes poner fotos libres "
                                 "de internet (Wikimedia Commons).\n\n¿Las busco ahora?"):
            self.fotos_internet()

    def pedir_fecha(self, texto, inicial=""):
        """Devuelve 'AAAA-MM-DD', 'AAAA-MM', 'AAAA', '' (no lo recuerda) o None (cancelado)."""
        import re
        while True:
            t = self.pedir_texto("Fecha de la visita", texto + "\nAAAA-MM-DD, AAAA-MM o solo el año. "
                                 "Déjalo vacío si no lo recuerdas.", inicial)
            if t is None:
                return None
            t = t.strip()
            if not t or fecha_ok(t):
                return t
            messagebox.showwarning(NOMBRE_PROGRAMA, "Escribe la fecha como 2024-05-12, 2024-05 o 2024.")
            inicial = t

    def aplicar_wiki(self, p, d):
        if not d:
            return False
        d = dict(d)
        lat, lon = d.pop("lat", None), d.pop("lon", None)
        if p.get("lat") is None and lat is not None:
            p["lat"], p["lon"] = round(lat, 6), round(lon, 6)
        p["wiki"] = d
        return True

    # ------------------------------------------------------------------ fotos de internet
    def fotos_internet(self):
        if not self.actual:
            return
        self.vistas["editor"].leer()
        p = self.actual
        if not p["nombre"]:
            return

        def fin(items):
            ya = {f.get("original") for f in p["fotos"]}
            items = [it for it in items if it["pagina"] not in ya]
            if not items:
                messagebox.showinfo(NOMBRE_PROGRAMA, "No he encontrado fotos libres nuevas de este pueblo.\n"
                                    "Comprueba el nombre, la provincia y la ubicación.")
                return
            self._dialogo_commons(p, items)
        self.en_segundo_plano("Buscando fotos libres (Wikimedia Commons, Flickr y más)…",
                              lambda: self.commons.buscar(p["nombre"], p["provincia"], p["lat"], p["lon"],
                                                          categoria=(p.get("wiki") or {}).get("commons_cat", "")), fin)

    def _dialogo_commons(self, p, items):
        v = self.dialogo(f"Fotos de internet — {p['nombre']}", 1040, 720)
        ctk.CTkLabel(v, text="Fotos de uso libre (Wikimedia Commons, Flickr y otras)", font=fuente_titulo(20)).pack(
            anchor="w", padx=20, pady=(16, 0))
        ctk.CTkLabel(v, text="Marca las que quieras. En la web se mostrará su autor y licencia, como exigen. "
                             "Algunas pueden no ser del pueblo exacto: revísalas.", text_color=tema.TINTA_2).pack(
            anchor="w", padx=20, pady=(0, 8))
        rejilla = ctk.CTkScrollableFrame(v)
        rejilla.pack(fill="both", expand=True, padx=20)
        columnas = 5
        for c in range(columnas):
            rejilla.columnconfigure(c, weight=1)
        imagenes, marcas, etiquetas = {}, [], []
        v._imagenes = imagenes  # que no se borren de memoria mientras la ventana esté abierta
        for i, it in enumerate(items):
            caja = ctk.CTkFrame(rejilla, corner_radius=10, fg_color=tema.TARJETA_2)
            caja.grid(row=i // columnas, column=i % columnas, padx=5, pady=5, sticky="n")
            lbl = ctk.CTkLabel(caja, text="cargando…", width=170, height=170, text_color=tema.TINTA_2)
            lbl.pack(padx=4, pady=(4, 0))
            var = tk.BooleanVar(value=False)
            ctk.CTkCheckBox(caja, variable=var, text=it["autor"][:22], font=fuente(12)).pack(anchor="w", padx=8, pady=(6, 0))
            ctk.CTkLabel(caja, text=f'{it["licencia"][:22]} · {it.get("origen", "Commons").replace("Wikimedia ", "")}'[:34],
                         text_color=tema.TINTA_2, font=fuente(11)).pack(
                anchor="w", padx=8, pady=(0, 6))
            lbl.bind("<Button-1>", lambda ev, x=var: x.set(not x.get()))
            lbl.bind("<Double-Button-1>", lambda ev, u=it["pagina"]: webbrowser.open(u))
            marcas.append((var, it))
            etiquetas.append(lbl)

        def poner(n, datos):
            try:
                if not v.winfo_exists():
                    return
                with Image.open(io.BytesIO(datos)) as im:
                    pil = recorte(im, 340, 340)
                imagenes[n] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(170, 170))
                etiquetas[n].configure(image=imagenes[n], text="")
            except Exception:  # noqa: BLE001
                try:
                    etiquetas[n].configure(text="(sin vista previa)")
                except tk.TclError:
                    pass

        cerrado = threading.Event()
        v.bind("<Destroy>", lambda ev: cerrado.set() if ev.widget is v else None)

        def cargar():
            for n, it in enumerate(items):
                if cerrado.is_set():
                    return
                try:
                    datos = self.commons.miniatura(it["miniatura"])
                except Exception:  # noqa: BLE001
                    continue
                self.cola.put(("llamar", lambda n=n, d=datos: poner(n, d)))
        threading.Thread(target=cargar, daemon=True).start()

        abajo = ctk.CTkFrame(v, fg_color="transparent")
        abajo.pack(fill="x", padx=20, pady=14)
        ctk.CTkLabel(abajo, text=f"{len(items)} fotos encontradas · doble clic para ver su página original",
                     text_color=tema.TINTA_2).pack(side="left")

        def aceptar():
            elegidas = [it for var, it in marcas if var.get()]
            if not elegidas:
                messagebox.showinfo(NOMBRE_PROGRAMA, "No has marcado ninguna foto.", parent=v)
                return
            v.destroy()
            if self.vista == "editor":
                self.vistas["editor"].guardar(silencioso=True)
            pueblo = self.actual or p

            def tarea():
                return I.anadir_fotos_internet(self.almacen, pueblo, elegidas, self.commons,
                                               int(self.cfg["lado_foto"]), self._progreso)

            def fin(res):
                n, fallos = res
                self.abrir(pueblo["slug"], recargar=True)
                self.estado(f"Añadidas {n} fotos de internet" + (f" ({fallos} no se pudieron bajar)." if fallos else "."))
            self.en_segundo_plano("Descargando fotos…", tarea, fin)
        boton(abajo, "Añadir las marcadas", aceptar).pack(side="right")
        boton(abajo, "Cancelar", v.destroy, "secundario", width=100).pack(side="right", padx=8)

    # ------------------------------------------------------------------ importar
    def importar(self):
        carpeta = filedialog.askdirectory(parent=self, title="Elige la carpeta con las fotos del viaje")
        if not carpeta:
            return
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        rutas = F.buscar_fotos(Path(carpeta))
        if not rutas:
            messagebox.showinfo(NOMBRE_PROGRAMA, "No he encontrado fotos en esa carpeta.")
            return
        self._carpeta_import = Path(carpeta).name
        self.en_segundo_plano(f"Leyendo la ubicación de {len(rutas)} fotos…",
                              lambda: I.analizar(rutas, self.geo, self._progreso), self._confirmar_importacion)

    def _confirmar_importacion(self, resultado):
        grupos, sin_asignar, por_hora = resultado
        v = self.dialogo("Pueblos encontrados en las fotos", 760, 620)
        ctk.CTkLabel(v, text="Pueblos encontrados", font=fuente_titulo(22)).pack(anchor="w", padx=20, pady=(18, 0))
        marcas = []
        cuerpo = ctk.CTkScrollableFrame(v, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=12, pady=(6, 0))
        if grupos:
            ctk.CTkLabel(cuerpo, text="Marca los que quieras añadir:", text_color=tema.TINTA_2).pack(anchor="w", padx=8)
            for clave, g in sorted(grupos.items(), key=lambda kv: -len(kv[1]["fotos"])):
                info = g["info"]
                existente = self.almacen.buscar(info["nombre"], info["provincia"])
                var = tk.BooleanVar(value=True)
                fechas = ", ".join(sorted(g["fechas"])) or "sin fecha"
                extra = f" (de ellas {g['por_hora']} sin GPS, por la hora)" if g["por_hora"] else ""
                aviso = ""
                if existente and existente.get("estado") == "pendiente":
                    aviso = "   ✓ ¡estaba en tu lista de pendientes!"
                elif existente:
                    aviso = "   · ya existe: se añaden las fotos"
                tarjeta = ctk.CTkFrame(cuerpo, corner_radius=10)
                tarjeta.pack(fill="x", padx=6, pady=4)
                ctk.CTkCheckBox(tarjeta, variable=var, font=fuente(14, "bold"),
                                text=f"{info['nombre']}  ·  {info['provincia']}").pack(anchor="w", padx=12, pady=(10, 0))
                ctk.CTkLabel(tarjeta, text=f"{len(g['fotos'])} fotos{extra} · {fechas}{aviso}",
                             text_color=tema.TINTA_2).pack(anchor="w", padx=44, pady=(0, 10))
                marcas.append((var, clave, g))
        else:
            ctk.CTkLabel(cuerpo, text="Ninguna foto tiene ubicación GPS (o no hay conexión a Internet).",
                         text_color=tema.TINTA_2).pack(anchor="w", padx=8)
        if por_hora:
            ctk.CTkLabel(cuerpo, text=f"{por_hora} fotos sin GPS se han colocado en su pueblo por la hora en que se hicieron.",
                         text_color=tema.TINTA_2).pack(anchor="w", padx=8, pady=(6, 0))

        opciones_resto = [("nada", None, "No añadirlas")]
        for clave, g in sorted(grupos.items(), key=lambda kv: -len(kv[1]["fotos"])):
            opciones_resto.append(("grupo", clave, f"A {g['info']['nombre']} (encontrado ahora)"))
        for p in sorted(self.almacen.listar(), key=lambda x: normalizar(x["nombre"])):
            opciones_resto.append(("existente", p["slug"], f"A {p['nombre']} ({p['provincia'] or 'sin provincia'})"))
        opciones_resto.append(("nuevo", None, "A un pueblo nuevo…"))
        v_resto = tk.StringVar()
        v_nombre_nuevo = tk.StringVar(value=getattr(self, "_carpeta_import", ""))
        if sin_asignar:
            caja = ctk.CTkFrame(cuerpo, corner_radius=10, border_width=1, border_color=tema.LINEA)
            caja.pack(fill="x", padx=6, pady=(12, 4))
            ctk.CTkLabel(caja, text=f"{len(sin_asignar)} fotos sin ubicación", font=fuente(14, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))
            ctk.CTkLabel(caja, text="¿A qué pueblo las añado?").grid(row=1, column=0, sticky="w", padx=12, pady=4)
            entrada = ctk.CTkEntry(caja, textvariable=v_nombre_nuevo, width=300)
            etiqueta_nuevo = ctk.CTkLabel(caja, text="Nombre del pueblo nuevo:")

            def al_cambiar(valor=None):
                if v_resto.get() == opciones_resto[-1][2]:
                    etiqueta_nuevo.grid(row=2, column=0, sticky="w", padx=12, pady=(4, 12))
                    entrada.grid(row=2, column=1, sticky="w", padx=8, pady=(4, 12))
                else:
                    etiqueta_nuevo.grid_remove()
                    entrada.grid_remove()
            combo = ctk.CTkComboBox(caja, variable=v_resto, values=[o[2] for o in opciones_resto], width=340,
                                    state="readonly", command=al_cambiar)
            combo.grid(row=1, column=1, sticky="w", padx=8, pady=4)
            v_resto.set(opciones_resto[-1][2] if not grupos else opciones_resto[0][2])
            al_cambiar()

        opc = ctk.CTkFrame(v, fg_color="transparent")
        opc.pack(fill="x", padx=20, pady=(10, 0))
        v_wiki = tk.BooleanVar(value=self.cfg["traer_wiki_al_importar"])
        v_ia = tk.BooleanVar(value=self.cfg["generar_ia_al_importar"] and IA.configurada(self.cfg))
        ctk.CTkCheckBox(opc, text="Traer datos de Wikipedia de los pueblos nuevos", variable=v_wiki).pack(anchor="w", pady=2)
        cb_ia = ctk.CTkCheckBox(opc, text="Escribir el texto con IA de los pueblos nuevos", variable=v_ia)
        cb_ia.pack(anchor="w", pady=2)
        if not IA.configurada(self.cfg):
            cb_ia.configure(state="disabled")

        def aceptar():
            elegidos = {clave: g for var, clave, g in marcas if var.get()}
            resto = None
            if sin_asignar:
                tipo, ref, _ = next(o for o in opciones_resto if o[2] == v_resto.get())
                if tipo == "grupo":
                    elegidos.setdefault(ref, grupos[ref])
                    resto = ("grupo", ref, sin_asignar)
                elif tipo == "existente":
                    resto = ("existente", ref, sin_asignar)
                elif tipo == "nuevo":
                    nombre = v_nombre_nuevo.get().strip()
                    if not nombre:
                        messagebox.showwarning(NOMBRE_PROGRAMA, "Escribe el nombre del pueblo nuevo.", parent=v)
                        return
                    resto = ("nuevo", nombre, sin_asignar)
            self.cfg["traer_wiki_al_importar"] = v_wiki.get()
            self.cfg["generar_ia_al_importar"] = v_ia.get()
            self.cfg.guardar()
            v.destroy()
            if elegidos or resto:
                self._aplicar_importacion(elegidos, resto, v_wiki.get(), v_ia.get())
        b = ctk.CTkFrame(v, fg_color="transparent")
        b.pack(fill="x", padx=20, pady=16)
        boton(b, "Añadir", aceptar, width=120).pack(side="right")
        boton(b, "Cancelar", v.destroy, "secundario", width=100).pack(side="right", padx=8)

    def _completar_nuevo(self, p, con_wiki, con_ia, avisos):
        if con_wiki and not p["wiki"].get("extracto"):
            self.cola.put(("estado", f"{p['nombre']}: Wikipedia…"))
            try:
                self.aplicar_wiki(p, self.wiki.todo(p["nombre"], p["provincia"], p["lat"], p["lon"]))
            except Exception as ex:  # noqa: BLE001
                avisos.append(f"{p['nombre']}: Wikipedia ({ex})")
        if con_ia and not p["texto_ia"]:
            self.cola.put(("estado", f"{p['nombre']}: texto con IA…"))
            try:
                p["texto_ia"] = generar_texto(self.cfg, p)
            except ErrorIA as ex:
                avisos.append(f"{p['nombre']}: IA ({ex})")

    def _aplicar_importacion(self, grupos, resto, con_wiki, con_ia):
        lado = int(self.cfg["lado_foto"])
        if resto and resto[0] == "grupo":
            grupos[resto[1]]["fotos"].extend(resto[2])

        def tarea():
            hechos, avisos, cumplidos = [], [], []
            lista = list(grupos.values())
            for i, g in enumerate(lista, 1):
                nombre = g["info"]["nombre"]
                self.cola.put(("estado", f"({i}/{len(lista)}) {nombre}: preparando fotos…"))
                previo = self.almacen.buscar(nombre, g["info"]["provincia"])
                p = I.crear_o_actualizar(self.almacen, g, lado, self._progreso)
                if previo is None:
                    self._completar_nuevo(p, con_wiki, con_ia, avisos)
                elif previo.get("estado") == "pendiente":
                    cumplidos.append(p["nombre"])
                self.almacen.guardar(p)
                hechos.append(p)
            if resto and resto[0] == "existente":
                p = self.almacen.cargar(resto[1])
                I.anadir_fotos(self.almacen, p, resto[2], lado, self._progreso)
                hechos.append(p)
            elif resto and resto[0] == "nuevo":
                nombre = resto[1]
                p = self.almacen.buscar(nombre)
                es_nuevo = p is None
                if es_nuevo:
                    p = pueblo_vacio(nombre)
                    self.cola.put(("estado", f"{nombre}: buscando en el mapa…"))
                    try:
                        lugares = self.geo.buscar(nombre)
                        lugar = next((x for x in lugares if x.get("pais") == "España"), lugares[0] if lugares else None)
                        if lugar:
                            p["provincia"], p["comunidad"] = lugar["provincia"], lugar["comunidad"]
                            p["lat"], p["lon"] = round(lugar["lat"], 6), round(lugar["lon"], 6)
                    except Exception as ex:  # noqa: BLE001
                        avisos.append(f"{nombre}: no lo encuentro en el mapa ({ex})")
                    self.almacen.guardar(p)
                I.anadir_fotos(self.almacen, p, resto[2], lado, self._progreso)
                if es_nuevo:
                    self._completar_nuevo(p, con_wiki, con_ia, avisos)
                    avisos.append(f"{nombre}: revisa que provincia y comunidad sean correctas.")
                self.almacen.guardar(p)
                hechos.append(p)
            return hechos, avisos, cumplidos

        def fin(res):
            hechos, avisos, cumplidos = res
            self._cache_img.clear()
            msg = f"Listo: {len(hechos)} pueblos actualizados."
            if cumplidos:
                msg += "\n\n🎉 Tachados de tu lista de pendientes: " + ", ".join(cumplidos)
            self.estado(msg.split("\n")[0])
            self.vista = None
            self.mostrar("mapa")
            if avisos or cumplidos:
                messagebox.showinfo(NOMBRE_PROGRAMA, msg + ("\n\nAvisos:\n" + "\n".join(avisos[:15]) if avisos else ""))
        self.en_segundo_plano("Añadiendo pueblos…", tarea, fin)

    # ------------------------------------------------------------------ web
    def _cfg_previa(self):
        c = dict(self.cfg)
        c["_previa"] = True
        return c

    def vista_previa(self):
        """Genera la web en local y la abre; se recarga sola cada vez que cambias algo."""
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)

        def fin(n):
            webbrowser.open((self.cfg.sitio / "index.html").as_uri())
            self._previa_abierta = True
            self.estado(f"Vista previa con {n} pueblos (aún no publicada). Se actualiza sola mientras cambias el diseño.")
        self.en_segundo_plano("Generando la web…", lambda: web.generar(
            self.almacen, self._cfg_previa(), self.cfg.sitio, lambda t: self.cola.put(("estado", t))), fin)

    def previa_cambiada(self):
        """Tras un cambio de diseño: rehace la vista previa (si está abierta) al cabo de un momento."""
        if not self._previa_abierta:
            return
        if self._previa_trabajo:
            self.after_cancel(self._previa_trabajo)
        self._previa_trabajo = self.after(700, self._rehacer_previa)

    def _rehacer_previa(self):
        self._previa_trabajo = None
        if self._previa_hilo and self._previa_hilo.is_alive():
            self._previa_trabajo = self.after(500, self._rehacer_previa)
            return

        def hilo():
            try:
                web.generar(self.almacen, self._cfg_previa(), self.cfg.sitio, lambda t: None)
                self.cola.put(("estado", "Vista previa actualizada."))
            except Exception as ex:  # noqa: BLE001
                self.cola.put(("estado", f"No se pudo actualizar la vista previa: {ex}"))
        self._previa_hilo = threading.Thread(target=hilo, daemon=True)
        self._previa_hilo.start()

    def publicar(self):
        if not self.cfg["repo_url"]:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Primero pon la dirección de tu repositorio de GitHub en Ajustes.")
            self.ajustes()
            return
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        avisar = lambda t: self.cola.put(("estado", t))  # noqa: E731

        def tarea():
            s = Sincronizador(self.cfg, avisar)
            return s.subir(), s.ultimo_sha

        def fin(res):
            msg, sha = res
            self._tras_sincronizar()
            if getattr(self, "_cerrar_tras_publicar", False):
                self.after(300, self.destroy)
                return
            if sha:
                self._seguir_publicacion(sha)
            url = url_web(self.cfg["repo_url"])
            self.estado(msg)
            if not self.cfg.get("aviso_actions"):
                self.cfg["aviso_actions"] = True
                self.cfg.guardar()
                messagebox.showinfo(NOMBRE_PROGRAMA, "Un último paso, solo esta vez:\n\n"
                                    "En GitHub, abre tu repositorio → Settings → Pages y en «Source» elige "
                                    "«GitHub Actions».\n\nDesde entonces GitHub rehará la web sola cada vez que "
                                    "publiques desde aquí o guardes desde el panel del móvil:\n"
                                    f"{url}gestion/")
                webbrowser.open(self.cfg["repo_url"].removesuffix(".git") + "/settings/pages")
            self.contar_cambios()
        self.en_segundo_plano("Publicando…", tarea, fin)

    def _seguir_publicacion(self, sha):
        """Pregunta a GitHub cómo va la publicación de la web y lo cuenta en la barra de abajo."""
        api = GitHubAPI(self.cfg.get("github_token"), self.cfg.get("repo_url"))

        def hilo():
            import time
            for intento in range(48):            # hasta unos 6 minutos
                try:
                    r = api.publicacion(sha)
                except Exception:  # noqa: BLE001
                    r = None
                if r:
                    estado, resultado, url = r
                    if estado == "completed":
                        if resultado == "success":
                            self.cola.put(("llamar", lambda: self._estado_web("✅ Web publicada en internet.", None)))
                        else:
                            self.cola.put(("llamar", lambda u=url: self._estado_web(
                                "❌ GitHub no pudo publicar la web. Haz clic aquí para ver por qué.", u)))
                        return
                    self.cola.put(("estado", "🟡 GitHub está publicando la web…"))
                time.sleep(8)
            self.cola.put(("estado", "GitHub está tardando en publicar; mira la pestaña Actions de tu repositorio."))
        threading.Thread(target=hilo, daemon=True).start()

    def _comprobar_actualizacion(self):
        if self._actualizacion_preguntada:
            return
        repo = Path(self.cfg.get("carpeta_repo") or (Path(self.cfg.sitio).parent / "repo"))
        info = actualizar.disponible(repo, VERSION)
        if not info:
            return
        self._actualizacion_preguntada = True
        base = BASE
        notas = info.get("notas") or ""
        if not messagebox.askyesno(NOMBRE_PROGRAMA, f"Hay una versión nueva de PUEBLOS: {info['version']} "
                                   f"(tienes la {VERSION}).\n\n{notas}\n\n¿Actualizar ahora? El programa se reiniciará. "
                                   "Tus pueblos y tu configuración no se tocan."):
            return
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        try:
            n = actualizar.instalar(info, base)
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror(NOMBRE_PROGRAMA, f"No se pudo actualizar: {ex}")
            return
        self.estado(f"Actualizado ({n} archivos). Reiniciando…")
        if actualizar.reiniciar(base):
            self.after(400, self.destroy)
        else:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Actualizado. Cierra el programa y vuelve a abrirlo con PUEBLOS.bat.")

    def _estado_web(self, texto, url):
        self.estado(texto)
        self.lbl_estado.unbind("<Button-1>")
        if url:
            self.lbl_estado.configure(cursor="hand2")
            self.lbl_estado.bind("<Button-1>", lambda e: webbrowser.open(url))
        else:
            self.lbl_estado.configure(cursor="")

    # ------------------------------------------------------------------ sincronizar con GitHub
    def sincronizar(self, silencioso=False):
        if not self.cfg.get("repo_url") or not git_disponible():
            if not silencioso:
                messagebox.showinfo(NOMBRE_PROGRAMA, "Para sincronizar necesitas git y la dirección del repositorio "
                                    "de GitHub en Ajustes.")
            return
        if self.ocupado:
            return
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        if silencioso:
            def hilo():
                try:
                    nuevo = Sincronizador(self.cfg, lambda t: self.cola.put(("estado", t))).traer()
                    self.cola.put(("llamar", lambda: self._tras_sincronizar(nuevo)))
                except Exception as ex:  # noqa: BLE001  sin conexión, etc.: se sigue trabajando en local
                    self.cola.put(("estado", f"Sin sincronizar con GitHub ({str(ex).splitlines()[0][:80]})"))
            threading.Thread(target=hilo, daemon=True).start()
            return

        def fin(nuevo):
            self._tras_sincronizar(nuevo)
        self.en_segundo_plano("Sincronizando con GitHub…",
                              lambda: Sincronizador(self.cfg, lambda t: self.cola.put(("estado", t))).traer(), fin)

    def _tras_sincronizar(self, nuevo=False):
        """Tras sincronizar, la carpeta de datos puede haber cambiado (la primera vez pasa al repositorio)."""
        if Path(self.almacen.carpeta).resolve() != Path(self.cfg.datos).resolve():
            self.almacen = Almacen(self.cfg.datos)
            self.geo = Geocodificador(self.cfg.user_agent, self.cfg.datos / "_cache_geo.json")
        self._cache_img.clear()
        self.estado("Sincronizado con GitHub." + (" Han llegado cambios del panel web." if nuevo else ""))
        self.after(300, self._comprobar_actualizacion)
        if self.vista == "editor" and self.actual:
            try:
                self.actual = self.almacen.cargar(self.actual["slug"])
                self.vistas["editor"].cargar()
            except OSError:
                self.volver(guardar=False)
        elif self.vista:
            self.vistas[self.vista].refrescar()

    def abrir_panel(self):
        url = url_web(self.cfg["repo_url"])
        if url:
            webbrowser.open(url + "gestion/")
        else:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Aún no has configurado el repositorio de GitHub.")

    def abrir_web(self):
        url = url_web(self.cfg["repo_url"])
        if url:
            webbrowser.open(url)
        else:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Aún no has configurado el repositorio de GitHub.")

    def ajustes(self, pestana=None):
        v = self.dialogo("Ajustes", 760, min(700, self.winfo_screenheight() - 100))
        ctk.CTkLabel(v, text="Ajustes", font=fuente_titulo(22)).pack(anchor="w", padx=22, pady=(18, 6))
        cont = ctk.CTkTabview(v, corner_radius=12)
        cont.pack(fill="both", expand=True, padx=16)
        for nombre in ("GitHub", "Inteligencia artificial", "Copias", "Programa"):
            cont.add(nombre)

        # --- GitHub (conexión) ---
        f = ctk.CTkFrame(cont.tab("GitHub"), corner_radius=12)
        f.pack(fill="x", padx=4, pady=6)
        f.columnconfigure(1, weight=1)
        ctk.CTkLabel(f, text="Conexión con GitHub", font=fuente_titulo(17)).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(f, text="Donde se guardan y publican tus pueblos. El token se guarda solo en este ordenador.",
                     text_color=tema.TINTA_2, font=fuente(12), wraplength=620, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))
        vars_ = {}
        campos = [
            ("repo_url", "Repositorio", "https://github.com/locometopa/pueblos.git", False),
            ("github_token", "Token", "Para publicar y ver el estado", True),
        ]
        for i, (clave, etiqueta, ayuda, oculto) in enumerate(campos, start=2):
            ctk.CTkLabel(f, text=etiqueta, text_color=tema.TINTA_2).grid(row=i, column=0, sticky="w", padx=16, pady=7)
            vars_[clave] = tk.StringVar(value=str(self.cfg.get(clave, "")))
            ctk.CTkEntry(f, textvariable=vars_[clave], show="\u2022" if oculto else "", placeholder_text=ayuda,
                         height=32).grid(row=i, column=1, sticky="ew", padx=(0, 16), pady=7)
        fila_token = ctk.CTkFrame(f, fg_color="transparent")
        fila_token.grid(row=4, column=1, sticky="w", pady=(2, 4))
        boton(fila_token, "Crear token\u2026",
              lambda: webbrowser.open("https://github.com/settings/personal-access-tokens/new"),
              "fantasma", width=110).pack(side="left")

        def comprobar_token():
            api = GitHubAPI(vars_["github_token"].get().strip(), vars_["repo_url"].get().strip())
            try:
                messagebox.showinfo(NOMBRE_PROGRAMA, api.comprobar(), parent=v)
            except Exception as ex:  # noqa: BLE001
                messagebox.showerror(NOMBRE_PROGRAMA, str(ex), parent=v)
        boton(fila_token, "Comprobar", comprobar_token, "fantasma", width=100).pack(side="left", padx=8)
        ctk.CTkLabel(f, text="Permiso del token: Contents \u00b7 Read and write.",
                     text_color=tema.TINTA_2, font=fuente(11)).grid(row=5, column=1, sticky="w", pady=(0, 10))

        # --- inteligencia artificial
        fi = ctk.CTkFrame(cont.tab("Inteligencia artificial"), corner_radius=12)
        fi.pack(fill="x", padx=4, pady=6)
        fi.columnconfigure(1, weight=1)
        ctk.CTkLabel(fi, text="Inteligencia artificial", font=fuente_titulo(17)).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(fi, text="Escribe el texto de cada pueblo a partir de Wikipedia. Elige cuál usar; "
                     "las claves se guardan solo en este ordenador.", text_color=tema.TINTA_2, font=fuente(12),
                     wraplength=600, justify="left").grid(row=1, column=0, columnspan=3, sticky="w", padx=16)
        nombres = {datos[0]: k for k, datos in IA.PROVEEDORES.items()}
        temp = {k: {"clave": self.cfg.get(IA.CAMPO_CLAVE[k], "") or "",
                    "modelo": self.cfg.get(IA.CAMPO_MODELO[k], "") or IA.PROVEEDORES[k][1]} for k in IA.PROVEEDORES}
        actual = {"p": IA.proveedor(self.cfg)}
        v_clave = tk.StringVar(value=temp[actual["p"]]["clave"])
        v_modelo = tk.StringVar(value=temp[actual["p"]]["modelo"])
        v_url = tk.StringVar(value=self.cfg.get("url_compatible", "") or "")
        ctk.CTkLabel(fi, text="Usar", text_color=tema.TINTA_2).grid(row=2, column=0, sticky="w", padx=16, pady=6)
        menu = ctk.CTkOptionMenu(fi, values=list(nombres), width=260)
        menu.grid(row=2, column=1, sticky="w", pady=6)
        lbl_ayuda = ctk.CTkLabel(fi, text="", text_color=tema.TINTA_2, font=fuente(12), wraplength=600, justify="left")
        lbl_ayuda.grid(row=3, column=0, columnspan=3, sticky="w", padx=16)
        ctk.CTkLabel(fi, text="Clave", text_color=tema.TINTA_2).grid(row=4, column=0, sticky="w", padx=16, pady=6)
        ctk.CTkEntry(fi, textvariable=v_clave, show="•", height=32).grid(row=4, column=1, sticky="ew", pady=6)
        b_clave = boton(fi, "Conseguir clave…", lambda: webbrowser.open(IA.PROVEEDORES[actual["p"]][2]), "fantasma", width=130)
        b_clave.grid(row=4, column=2, padx=(6, 16))
        ctk.CTkLabel(fi, text="Modelo", text_color=tema.TINTA_2).grid(row=5, column=0, sticky="w", padx=16, pady=6)
        ctk.CTkEntry(fi, textvariable=v_modelo, height=32).grid(row=5, column=1, sticky="ew", pady=6)
        lbl_url = ctk.CTkLabel(fi, text="Dirección", text_color=tema.TINTA_2)
        e_url = ctk.CTkEntry(fi, textvariable=v_url, height=32, placeholder_text="https://api.deepseek.com/v1")

        def cfg_prueba():
            c = dict(self.cfg)
            c["ia_proveedor"] = actual["p"]
            c[IA.CAMPO_CLAVE[actual["p"]]] = v_clave.get().strip()
            c[IA.CAMPO_MODELO[actual["p"]]] = v_modelo.get().strip()
            c["url_compatible"] = v_url.get().strip()
            return c

        def ver_modelos():
            try:
                lista = IA.modelos(cfg_prueba())
            except ErrorIA as ex:
                messagebox.showerror(NOMBRE_PROGRAMA, str(ex), parent=v)
                return
            if not lista:
                messagebox.showinfo(NOMBRE_PROGRAMA, "No he encontrado modelos con esa clave.", parent=v)
                return
            m = tk.Menu(v, tearoff=0)
            for nombre_m in lista[:40]:
                m.add_command(label=nombre_m, command=lambda x=nombre_m: v_modelo.set(x))
            m.tk_popup(b_modelos.winfo_rootx(), b_modelos.winfo_rooty() + b_modelos.winfo_height())
        b_modelos = boton(fi, "Ver modelos", ver_modelos, "fantasma", width=130)
        b_modelos.grid(row=5, column=2, padx=(6, 16))

        def probar():
            try:
                messagebox.showinfo(NOMBRE_PROGRAMA, IA.probar(cfg_prueba()), parent=v)
            except ErrorIA as ex:
                messagebox.showerror(NOMBRE_PROGRAMA, str(ex), parent=v)
        boton(fi, "Probar", probar, "secundario", width=100).grid(row=7, column=1, sticky="w", pady=(6, 14))

        def cambiar(nombre_p):
            temp[actual["p"]] = {"clave": v_clave.get(), "modelo": v_modelo.get()}
            actual["p"] = nombres[nombre_p]
            v_clave.set(temp[actual["p"]]["clave"])
            v_modelo.set(temp[actual["p"]]["modelo"])
            lbl_ayuda.configure(text=IA.PROVEEDORES[actual["p"]][3])
            if actual["p"] == "compatible":
                lbl_url.grid(row=6, column=0, sticky="w", padx=16, pady=6)
                e_url.grid(row=6, column=1, sticky="ew", pady=6)
                b_clave.grid_remove()
            else:
                lbl_url.grid_remove()
                e_url.grid_remove()
                b_clave.grid()
        menu.configure(command=cambiar)
        menu.set(IA.PROVEEDORES[actual["p"]][0])
        cambiar(IA.PROVEEDORES[actual["p"]][0])

        # --- copia de seguridad
        fc = ctk.CTkFrame(cont.tab("Copias"), corner_radius=12)
        fc.pack(fill="x", padx=4, pady=6)
        fc.columnconfigure(1, weight=1)
        ctk.CTkLabel(fc, text="Copia de seguridad", font=fuente_titulo(17)).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(fc, text="Además de GitHub: un .zip con tus pueblos, fotos y ajustes en la carpeta que elijas "
                     "(tu NAS, un disco USB, OneDrive…). Se guardan las 5 últimas.", text_color=tema.TINTA_2,
                     font=fuente(12), wraplength=620, justify="left").grid(row=1, column=0, columnspan=3, sticky="w", padx=16)
        v_copia = tk.StringVar(value=self.cfg.get("copia_carpeta", "") or "")
        ctk.CTkLabel(fc, text="Carpeta", text_color=tema.TINTA_2).grid(row=2, column=0, sticky="w", padx=16, pady=6)
        ctk.CTkEntry(fc, textvariable=v_copia, height=32, placeholder_text="Ej.: \\\\NAS\\copias  o  E:\\Copias").grid(
            row=2, column=1, sticky="ew", pady=6)

        def elegir_copia():
            c = filedialog.askdirectory(parent=v, title="¿Dónde guardo las copias de seguridad?")
            if c:
                v_copia.set(c)
        boton(fc, "Elegir…", elegir_copia, "fantasma", width=90).grid(row=2, column=2, padx=(6, 16))
        v_auto = tk.BooleanVar(value=self.cfg.get("copia_auto", True))
        ctk.CTkCheckBox(fc, text="Hacerla sola cada semana al abrir el programa", variable=v_auto).grid(
            row=3, column=1, sticky="w", pady=(0, 6))
        hecha = self.cfg.get("copia_ultima")
        ctk.CTkLabel(fc, text=f"Última copia: {hecha}" if hecha else "Aún no hay ninguna copia.", text_color=tema.TINTA_2,
                     font=fuente(12)).grid(row=4, column=1, sticky="w")

        def copia_ya():
            if not v_copia.get().strip():
                messagebox.showinfo(NOMBRE_PROGRAMA, "Elige primero la carpeta de las copias.", parent=v)
                return
            self.cfg["copia_carpeta"] = v_copia.get().strip()
            self.cfg["copia_auto"] = v_auto.get()
            self.cfg.guardar()
            v.destroy()
            self.copia_seguridad()
        boton(fc, "💾  Hacer una copia ahora", copia_ya, "secundario").grid(row=5, column=1, sticky="w", pady=(6, 14))

        # --- Programa (aspecto, fotos, acceso directo, versión) ---
        fp = ctk.CTkFrame(cont.tab("Programa"), corner_radius=12)
        fp.pack(fill="both", expand=True, padx=4, pady=6)
        fp.columnconfigure(1, weight=1)
        ctk.CTkLabel(fp, text="Aspecto", font=fuente_titulo(17)).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 6))
        ctk.CTkLabel(fp, text="Claro, oscuro o como Windows", text_color=tema.TINTA_2).grid(
            row=1, column=0, sticky="w", padx=16, pady=6)
        menu_tema = ctk.CTkOptionMenu(fp, values=list(TEMAS), command=self._cambiar_tema, height=30, width=160)
        menu_tema.set(next((k for k, v2 in TEMAS.items() if v2 == self.cfg.get("tema", "System")), "Sistema"))
        menu_tema.grid(row=1, column=1, sticky="w", pady=6)
        ctk.CTkLabel(fp, text="Tama\u00f1o de las fotos (px)", text_color=tema.TINTA_2).grid(
            row=2, column=0, sticky="w", padx=16, pady=6)
        vars_["lado_foto"] = tk.StringVar(value=str(self.cfg.get("lado_foto", "")))
        ctk.CTkEntry(fp, textvariable=vars_["lado_foto"], height=32, width=120).grid(row=2, column=1, sticky="w", pady=6)
        boton(fp, "\U0001f5a5  Crear acceso directo en el escritorio", lambda: self.crear_acceso_directo(v),
              "secundario").grid(row=3, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 12))
        ctk.CTkFrame(fp, height=1, fg_color=tema.LINEA).grid(row=4, column=0, columnspan=2, sticky="ew", padx=16, pady=10)
        ctk.CTkLabel(fp, text="Versi\u00f3n y novedades", font=fuente_titulo(17)).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 6))
        filav = ctk.CTkFrame(fp, fg_color="transparent")
        filav.grid(row=6, column=0, columnspan=2, sticky="ew", padx=16)
        ctk.CTkLabel(filav, text=f" Versi\u00f3n {VERSION} ", font=fuente(13, "bold"), corner_radius=10,
                     fg_color=tema.TARJETA_2, text_color=tema.TINTA).pack(side="left")
        boton(filav, "\U0001f504  Buscar actualizaciones", lambda: self.buscar_actualizaciones(v)).pack(side="right")
        self.lbl_buscar = ctk.CTkLabel(fp, text=self._texto_comprobado(), text_color=tema.TINTA_2, font=fuente(11))
        self.lbl_buscar.grid(row=7, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 6))
        caja = ctk.CTkTextbox(fp, wrap="word", font=fuente(12), corner_radius=10, height=150)
        caja.grid(row=8, column=0, columnspan=2, sticky="nsew", padx=16, pady=(0, 12))
        caja.insert("1.0", self._historial())
        caja.configure(state="disabled")
        fp.rowconfigure(8, weight=1)

        def guardar():
            for clave, var in vars_.items():
                valor = var.get().strip()
                if clave == "lado_foto":
                    try:
                        valor = max(800, min(4000, int(valor)))
                    except ValueError:
                        valor = 1600
                self.cfg[clave] = valor
            temp[actual["p"]] = {"clave": v_clave.get(), "modelo": v_modelo.get()}
            self.cfg["ia_proveedor"] = actual["p"]
            for k, d in temp.items():
                self.cfg[IA.CAMPO_CLAVE[k]] = d["clave"].strip()
                self.cfg[IA.CAMPO_MODELO[k]] = d["modelo"].strip() or IA.PROVEEDORES[k][1]
            self.cfg["url_compatible"] = v_url.get().strip()
            self.cfg["copia_carpeta"] = v_copia.get().strip()
            self.cfg["copia_auto"] = v_auto.get()
            self.cfg.guardar()
            configurar_token(self.cfg.get("github_token"))
            v.destroy()
            self.estado("Ajustes guardados.")
        b = ctk.CTkFrame(v, fg_color="transparent")
        b.pack(fill="x", padx=20, pady=14, side="bottom", before=cont)
        if pestana:
            cont.set(pestana)
        boton(b, "Guardar", guardar, width=110).pack(side="right")
        boton(b, "Cancelar", v.destroy, "secundario", width=100).pack(side="right", padx=8)

    def traducir_otra(self, d):
        """Si se ha traído el artículo de otra Wikipedia (gallego, catalán, inglés…) y hay IA, se traduce."""
        otra = (d or {}).get("extracto_otro")
        if otra and not otra.get("texto_es") and IA.configurada(self.cfg):
            try:
                otra["texto_es"] = IA.traducir(self.cfg, otra["texto"], otra["idioma"])
            except ErrorIA:
                pass
        return d

    def ampliar_todos(self):
        """Añade historia, fiestas (con fecha), qué ver, gentilicio… a los pueblos que aún no lo tienen."""
        if self.vista == "editor" and self.actual:
            self.vistas["editor"].guardar(silencioso=True)
        faltan = [p for p in self.almacen.listar()
                  if not all(k in (p.get("wiki") or {}) for k in ("secciones", "fiestas", "fuentes_v2"))]
        if not faltan:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Todos tus pueblos tienen ya la información ampliada.")
            return

        def tarea():
            hechos = 0
            for i, p in enumerate(faltan, 1):
                self._progreso(i, len(faltan), p["nombre"])
                try:
                    w = p.get("wiki") or {}
                    self.wiki._comunidad = p.get("comunidad", "")
                    d = self.wiki.datos(w["titulo"]) if w.get("titulo") else self.wiki.todo(
                        p["nombre"], p["provincia"], p["lat"], p["lon"])
                    if not d:
                        continue
                    if w.get("titulo"):
                        d = self.wiki.ampliar(d, p["nombre"], p["provincia"], p["lat"], p["lon"])
                    d = self.traducir_otra(d)
                    for k in ("secciones", "que_ver", "gentilicio", "patron", "fiestas", "oficial", "guia",
                              "distinciones", "commons_cat", "web", "fuentes_v1", "fuentes_v2", "mas_datos",
                              "extracto_otro"):
                        if d.get(k):
                            w[k] = d[k]
                    w.setdefault("secciones", [])          # marcado como revisado aunque no haya nada
                    w.setdefault("fiestas", [])
                    for k, v in d.items():                # lo que faltara (sin pisar tu texto)
                        if k not in w and k not in ("lat", "lon"):
                            w[k] = v
                    p["wiki"] = w
                    self.almacen.guardar(p)
                    hechos += 1
                except Exception:  # noqa: BLE001
                    continue
            return hechos

        def fin(n):
            self.estado(f"Información ampliada en {n} de {len(faltan)} pueblos. Publica para verla en la web.")
            if self.vista:
                self.vistas[self.vista].refrescar()
        self.en_segundo_plano("Recopilando información de internet…", tarea, fin)

    # ------------------------------------------------------------------ segundo plano
    def estado(self, texto):
        self.lbl_estado.configure(text=texto)

    def _progreso(self, i, total, nombre=""):
        self.cola.put(("progreso", (i, total, nombre)))

    def en_segundo_plano(self, texto, tarea, al_terminar=None):
        if self.ocupado:
            messagebox.showinfo(NOMBRE_PROGRAMA, "Espera a que termine lo que está haciendo.")
            return
        self.ocupado = True
        self.configure(cursor="watch")
        self.estado(texto)
        self.progreso.pack(side="right", padx=16)
        self.progreso.configure(mode="indeterminate")
        self.progreso.start()

        def hilo():
            try:
                self.cola.put(("fin", (al_terminar, tarea(), None)))
            except Exception as ex:  # noqa: BLE001
                traceback.print_exc()
                self.cola.put(("fin", (al_terminar, None, ex)))
        threading.Thread(target=hilo, daemon=True).start()

    def _atender_cola(self):
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "estado":
                    self.estado(dato)
                elif tipo == "llamar":
                    dato()
                elif tipo == "progreso":
                    i, total, nombre = dato
                    self.progreso.stop()
                    self.progreso.configure(mode="determinate")
                    self.progreso.set(i / total if total else 0)
                    if nombre:
                        self.estado(f"{i}/{total}  {nombre}")
                elif tipo == "fin":
                    al_terminar, resultado, error = dato
                    self.ocupado = False
                    self.configure(cursor="")
                    self.progreso.stop()
                    self.progreso.configure(mode="determinate")
                    self.progreso.set(0)
                    self.progreso.pack_forget()
                    if error is not None:
                        self.estado("Algo ha fallado.")
                        msg = str(error)
                        if not isinstance(error, (ErrorIA, ErrorPublicar)):
                            msg = f"{type(error).__name__}: {msg}\n\n¿Hay conexión a Internet?"
                        messagebox.showerror(NOMBRE_PROGRAMA, msg)
                    elif al_terminar:
                        al_terminar(resultado)
        except queue.Empty:
            pass
        self.after(100, self._atender_cola)

    def salir(self):
        if self.vista == "editor" and self.actual:
            try:
                self.vistas["editor"].guardar(silencioso=True)
            except Exception:  # noqa: BLE001
                pass
        n = getattr(self, "cambios", 0)
        if n and self.cfg.get("repo_url"):
            r = messagebox.askyesnocancel(NOMBRE_PROGRAMA, f"Tienes {n} {'cambio' if n == 1 else 'cambios'} sin publicar.\n\n"
                                          "¿Los publico antes de cerrar?")
            if r is None:
                return
            if r:
                self._cerrar_tras_publicar = True
                self.publicar()
                return
        self.destroy()


def _abrir_version_nueva() -> bool:
    """Desde el .exe: si en la carpeta hay una versión más nueva (llegada por actualización), se abre esa."""
    import sys
    import subprocess
    if not getattr(sys, "frozen", False):
        return False
    nueva = actualizar.version_en_carpeta(BASE)
    exe = actualizar.lanzador()
    if nueva and exe and actualizar.numero(nueva) > actualizar.numero(VERSION) and (BASE / "pueblos.py").exists():
        subprocess.Popen([exe, str(BASE / "pueblos.py")], cwd=str(BASE))
        return True
    return False


if __name__ == "__main__":
    if not _abrir_version_nueva():
        App().mainloop()
