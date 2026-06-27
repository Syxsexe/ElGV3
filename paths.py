"""
paths.py — El G POS
Rutas de datos de la aplicación.

En desarrollo, los archivos escribibles (base de datos, configuración, colas)
viven en la carpeta del proyecto. Cuando la app está empaquetada con PyInstaller
(`sys.frozen`), `__file__` apunta a una carpeta temporal de solo lectura que se
borra al cerrar, así que esos archivos se redirigen a una carpeta estable por
usuario:
  - Windows:      %APPDATA%\\ElGV3
  - Linux/macOS:  ~/.local/share/ElGV3
"""
import os
import sys
from pathlib import Path

APP_NAME = "ElGV3"


def _carpeta_proyecto() -> Path:
    return Path(__file__).resolve().parent


def esta_empaquetado() -> bool:
    """True si la app corre como ejecutable congelado (PyInstaller)."""
    return getattr(sys, "frozen", False)


def carpeta_datos() -> Path:
    """Carpeta donde se guardan los archivos escribibles (DB, config, colas)."""
    if not esta_empaquetado():
        return _carpeta_proyecto()
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    destino = base / APP_NAME
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def carpeta_recursos() -> Path:
    """Carpeta de recursos de solo lectura empaquetados (sys._MEIPASS)."""
    if esta_empaquetado():
        return Path(getattr(sys, "_MEIPASS", _carpeta_proyecto()))
    return _carpeta_proyecto()


def ruta_datos(nombre: str) -> Path:
    """Ruta de un archivo escribible dentro de la carpeta de datos."""
    return carpeta_datos() / nombre
