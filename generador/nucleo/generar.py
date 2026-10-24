"""Genera la web completa (para GitHub Actions o para probar en local).

Uso:  python -m nucleo.generar --datos ../datos --salida ../_site [--ajustes ../ajustes_web.json]
"""
import argparse
import json
import os
import shutil
from pathlib import Path

from . import web
from .datos import Almacen

AJUSTES_DEFECTO = {
    "titulo_web": "Mis pueblos",
    "subtitulo_web": "Cuaderno de los pueblos que he visitado",
    "autor": "",
    "mostrar_pendientes": True,
}
CARPETA_GESTION = Path(__file__).with_name("gestion")


def leer_ajustes(ruta: Path) -> dict:
    ajustes = dict(AJUSTES_DEFECTO)
    if ruta and Path(ruta).exists():
        try:
            ajustes.update(json.loads(Path(ruta).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return ajustes


def copiar_gestion(salida: Path, repo: str = "", rama: str = "main", acceso: Path = None):
    """Copia el panel de gestión a <salida>/gestion con su configuración (y el token cifrado, si hay)."""
    destino = Path(salida) / "gestion"
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(CARPETA_GESTION, destino)
    (destino / "config.json").write_text(json.dumps({"repo": repo, "rama": rama}, ensure_ascii=False),
                                         encoding="utf-8")
    if acceso and Path(acceso).exists():
        shutil.copy2(acceso, destino / "acceso.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default="datos")
    ap.add_argument("--salida", default="_site")
    ap.add_argument("--ajustes", default="ajustes_web.json")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--rama", default=os.environ.get("GITHUB_REF_NAME", "main"))
    a = ap.parse_args()
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    datos = Path(a.datos)
    datos.mkdir(parents=True, exist_ok=True)
    n = web.generar(Almacen(datos), leer_ajustes(Path(a.ajustes)), salida, print)
    copiar_gestion(salida, a.repo, a.rama, datos.resolve().parent / "acceso_panel.json")
    print(f"Web generada con {n} pueblos en {salida}")


if __name__ == "__main__":
    main()
