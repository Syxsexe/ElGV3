"""
db/migrar.py — El G POS

Aplica en orden las migraciones SQL de db/migraciones/ que aún no se hayan
aplicado a la base indicada en DATABASE_URL. Cada archivo corre en su propia
transacción (o todas en una con --todo-o-nada) y queda anotado en
`schema_migraciones`, así que correrlo de nuevo solo aplica lo pendiente.

    DATABASE_URL=postgresql://elg:elg@localhost:5433/elg python db/migrar.py
"""
import contextlib
import os
import sys
from pathlib import Path

import psycopg

CARPETA = Path(__file__).resolve().parent / "migraciones"


def migraciones_disponibles() -> list[Path]:
    return sorted(CARPETA.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def aplicar(url: str, verbose: bool = True, todo_o_nada: bool = False) -> list[str]:
    """Aplica las migraciones pendientes y retorna las versiones aplicadas.

    Normalmente cada archivo va en su propia transacción. Con todo_o_nada (el
    arranque del contenedor en el servidor) van todas en una sola: si una
    falla, la base queda como estaba y la versión anterior de la API sigue
    funcionando sobre ella."""
    aplicadas = []
    # autocommit: así cada `conn.transaction()` es una transacción real (y no un
    # savepoint de una transacción implícita que se confirmaría toda al final).
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migraciones (
                version     text        PRIMARY KEY,
                aplicada_en timestamptz NOT NULL DEFAULT now()
            )
        """)
        hechas = {r[0] for r in conn.execute("SELECT version FROM schema_migraciones")}
        pendientes = [a for a in migraciones_disponibles() if a.stem not in hechas]

        with conn.transaction() if todo_o_nada else contextlib.nullcontext():
            for archivo in pendientes:
                with conn.transaction():  # dentro de todo_o_nada es un savepoint
                    conn.execute(archivo.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO schema_migraciones (version) VALUES (%s)", (archivo.stem,))
                aplicadas.append(archivo.stem)
        if verbose:
            for version in aplicadas:
                print(f"✓ {version}")

    if verbose and not aplicadas:
        print("Sin migraciones pendientes.")
    return aplicadas


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Falta DATABASE_URL (ej. postgresql://elg:elg@localhost:5433/elg).")
    # --todo-o-nada: todas las pendientes en una sola transacción (servidor).
    aplicar(url, todo_o_nada="--todo-o-nada" in sys.argv[1:])
