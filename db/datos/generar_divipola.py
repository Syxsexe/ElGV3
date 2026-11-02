"""
db/datos/generar_divipola.py — El G POS

Genera db/migraciones/0014_divipola.sql a partir de db/datos/divipola.csv
(departamentos y municipios oficiales del DANE, publicados en datos.gov.co,
conjunto gdxc-w37w). Solo hace falta correrlo si se actualiza el CSV; la
migración generada queda versionada.

    python db/datos/generar_divipola.py
"""
import csv
from pathlib import Path

DB = Path(__file__).resolve().parent.parent
CSV = DB / "datos" / "divipola.csv"
SALIDA = DB / "migraciones" / "0014_divipola.sql"


def literal(texto: str) -> str:
    return "'" + texto.replace("'", "''") + "'"


def generar() -> str:
    with CSV.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))

    departamentos = {}
    for f in filas:
        departamentos.setdefault(f["codigo_departamento"], f["departamento"])

    lineas = [
        "-- 0014_divipola.sql — Departamentos y municipios de Colombia (DIVIPOLA, DANE).",
        "-- GENERADO por db/datos/generar_divipola.py desde db/datos/divipola.csv: no editar a mano.",
        "",
        "INSERT INTO departamentos (codigo, nombre) VALUES",
        ",\n".join(f"    ({literal(c)}, {literal(n)})" for c, n in sorted(departamentos.items())) + ";",
        "",
        "INSERT INTO municipios (codigo, nombre, departamento_id)",
        "SELECT m.codigo, m.nombre, d.id",
        "  FROM (VALUES",
        ",\n".join(
            f"    ({literal(f['codigo_municipio'])}, {literal(f['municipio'])}, {literal(f['codigo_departamento'])})"
            for f in filas
        ),
        "  ) AS m (codigo, nombre, codigo_departamento)",
        "  JOIN departamentos d ON d.codigo = m.codigo_departamento;",
        "",
    ]
    return "\n".join(lineas)


if __name__ == "__main__":
    SALIDA.write_text(generar(), encoding="utf-8")
    print(f"✓ {SALIDA.relative_to(DB.parent)}")
