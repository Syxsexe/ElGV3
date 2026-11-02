"""
db/migrar.py — El G POS

Aplica en orden las migraciones SQL de db/migraciones/ que aún no se hayan
aplicado a la base indicada en DATABASE_URL. Cada archivo corre en su propia
transacción y queda anotado en `schema_migraciones`, así que correrlo de nuevo
solo aplica lo pendiente.

    DATABASE_URL=postgresql://elg:elg@localhost:5433/elg python db/migrar.py
"""
import os
import sys
from pathlib import Path

import psycopg

CARPETA = Path(__file__).resolve().parent / "migraciones"


def migraciones_disponibles() -> list[Path]:
    return sorted(CARPETA.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def aplicar(url: str, verbose: bool = True) -> list[str]:
    """Aplica las migraciones pendientes y retorna las versiones aplicadas."""
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

        for archivo in migraciones_disponibles():
            version = archivo.stem
            if version in hechas:
                continue
            with conn.transaction():
                conn.execute(archivo.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migraciones (version) VALUES (%s)", (version,)
                )
            aplicadas.append(version)
            if verbose:
                print(f"✓ {version}")

    if verbose and not aplicadas:
        print("Sin migraciones pendientes.")
    return aplicadas


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Falta DATABASE_URL (ej. postgresql://elg:elg@localhost:5433/elg).")
    aplicar(url)
