"""
modules/respaldo.py — El G POS
Respaldo "en caliente" de la base de datos SQLite.

Usa la API de backup online de sqlite3 (`Connection.backup`), que produce una
copia CONSISTENTE aunque la app esté abierta y escribiendo — a diferencia de un
simple `copy` del archivo, que puede quedar corrupto si hay una escritura en curso.

Se invoca desde el propio ejecutable con `ElGV3.exe --backup [carpeta_destino]`,
para que la tarea programada de Windows no dependa de tener Python instalado.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from database import DB_PATH
from paths import carpeta_datos

PREFIJO = "elg_pos_"
CONSERVAR_POR_DEFECTO = 30  # nº de respaldos a mantener (rota los más viejos)


def carpeta_respaldos() -> Path:
    """Destino por defecto si no se indica otro: <datos>/respaldos."""
    dest = carpeta_datos() / "respaldos"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def respaldar(destino: str | Path | None = None,
              conservar: int = CONSERVAR_POR_DEFECTO) -> Path:
    """
    Crea una copia consistente de la BD en `destino` (o la carpeta por defecto),
    con nombre `elg_pos_AAAAMMDD_HHMMSS.db`. Rota los respaldos más antiguos.
    Devuelve la ruta del respaldo creado.
    """
    origen_path = Path(DB_PATH)
    if not origen_path.exists():
        raise FileNotFoundError(f"No existe la base de datos: {origen_path}")

    destino_dir = Path(destino) if destino else carpeta_respaldos()
    destino_dir.mkdir(parents=True, exist_ok=True)

    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = destino_dir / f"{PREFIJO}{marca}.db"

    origen = sqlite3.connect(str(origen_path))
    try:
        copia = sqlite3.connect(str(archivo))
        try:
            origen.backup(copia)  # backup online, atómico y consistente
        finally:
            copia.close()
    finally:
        origen.close()

    _rotar(destino_dir, conservar)
    return archivo


def _rotar(directorio: Path, conservar: int) -> None:
    """Mantiene solo los `conservar` respaldos más recientes en `directorio`."""
    if conservar is None or conservar <= 0:
        return
    respaldos = sorted(directorio.glob(f"{PREFIJO}*.db"))  # orden = cronológico por nombre
    for viejo in respaldos[:-conservar]:
        try:
            viejo.unlink()
        except OSError:
            pass
