"""
pos_api/configurar.py — Configuración inicial de una base nueva.

Crea los datos del negocio (su tercero + la fila de empresa) y el primer
usuario administrador. Se corre una sola vez, en el servidor, después de
migrar; se niega si la base ya tiene usuarios.

    ELG_DATABASE_URL=postgresql://elg:elg@localhost:5433/elg python -m pos_api.configurar
"""
import getpass
import sys
import unicodedata

import psycopg
from psycopg.rows import dict_row

from pos_api.auditoria import auditar
from pos_api.config import DATABASE_URL
from pos_api.db import migraciones_pendientes
from pos_api.errores import ErrorNegocio
from pos_api.seguridad import hash_contrasena

# Pesos del dígito de verificación del NIT (DIAN), de derecha a izquierda.
_PESOS_DV = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def digito_verificacion(nit: str) -> int:
    """Dígito de verificación DIAN de un NIT (sin el DV)."""
    if not nit.isdigit() or len(nit) > len(_PESOS_DV):
        raise ValueError("El NIT debe tener solo dígitos (máximo 15), sin el dígito de verificación.")
    residuo = sum(int(d) * p for d, p in zip(reversed(nit), _PESOS_DV)) % 11
    return residuo if residuo < 2 else 11 - residuo


def crear_configuracion(conn, negocio: dict, admin: dict) -> None:
    """Crea el tercero del negocio, la fila de empresa y el usuario admin.
    conn debe estar dentro de una transacción.

    negocio: tipo_identificacion (código DIAN), numero_identificacion, nombre,
             tipo_persona, municipio_id, direccion, telefono, email,
             responsable_iva, regimen_tributario, responsable_inc
    admin:   usuario, contrasena
    """
    if conn.execute("SELECT EXISTS (SELECT 1 FROM usuarios) OR EXISTS (SELECT 1 FROM empresa) AS hay").fetchone()["hay"]:
        raise ErrorNegocio("La base ya está configurada: tiene usuarios o datos del negocio.")

    tercero_id = conn.execute(
        """INSERT INTO terceros (tipo_persona, nombre, tipo_identificacion_id, numero_identificacion,
                                 direccion, municipio_id, telefono, email, responsable_iva)
           SELECT %(tipo_persona)s, %(nombre)s, ti.id, %(numero_identificacion)s,
                  %(direccion)s, %(municipio_id)s, %(telefono)s, %(email)s, %(responsable_iva)s
             FROM tipos_identificacion ti WHERE ti.codigo = %(tipo_identificacion)s
           RETURNING id""",
        negocio,
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO empresa (tercero_id, regimen_tributario, responsable_inc) VALUES (%s, %s, %s)",
        (tercero_id, negocio["regimen_tributario"], negocio["responsable_inc"]),
    )
    usuario_id = conn.execute(
        """INSERT INTO usuarios (usuario, contrasena_hash, rol_id)
           SELECT %s, %s, id FROM roles WHERE nombre = 'admin' RETURNING id""",
        (admin["usuario"].strip(), hash_contrasena(admin["contrasena"])),
    ).fetchone()["id"]
    auditar(conn, None, "sistema",
            f"Configuración inicial: negocio {negocio['nombre']} y administrador {admin['usuario'].strip()}",
            "empresa", tercero_id)
    auditar(conn, None, "usuario", "Usuario administrador inicial", "usuarios", usuario_id)


# ── Preguntas por terminal ──────────────────────────────────────────────────

def _preguntar(texto: str, opcional: bool = False) -> str | None:
    while True:
        valor = input(f"{texto}{' (opcional)' if opcional else ''}: ").strip()
        if valor or opcional:
            return valor or None
        print("  Este dato es obligatorio.")


def _si_no(texto: str, defecto: bool = False) -> bool:
    while True:
        valor = input(f"{texto} [{'S/n' if defecto else 's/N'}]: ").strip().lower()
        if not valor:
            return defecto
        if valor in ("s", "si", "sí", "n", "no"):
            return valor.startswith("s")
        print("  Responde s o n.")


def _elegir(texto: str, opciones: list[tuple[str, str]]) -> str:
    """opciones = [(valor, descripción)]; retorna el valor elegido."""
    for i, (_, descripcion) in enumerate(opciones, 1):
        print(f"  {i}. {descripcion}")
    while True:
        valor = input(f"{texto} [1-{len(opciones)}]: ").strip()
        if valor.isdigit() and 1 <= int(valor) <= len(opciones):
            return opciones[int(valor) - 1][0]
        print("  Elige un número de la lista.")


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.upper()) if unicodedata.category(c) != "Mn")


def _municipio(conn) -> str:
    while True:
        nombre = _preguntar("Municipio (nombre o código DIVIPOLA)")
        # Los nombres DIVIPOLA están en mayúsculas con tildes: se compara sin ellas.
        filas = conn.execute(
            """SELECT m.id, m.codigo, m.nombre, d.nombre AS depto
                 FROM municipios m JOIN departamentos d ON d.id = m.departamento_id
                WHERE m.codigo = %s OR translate(m.nombre, 'ÁÉÍÓÚÜÑ', 'AEIOUUN') LIKE %s
                ORDER BY m.nombre LIMIT 15""",
            (nombre, f"%{_sin_tildes(nombre)}%"),
        ).fetchall()
        if not filas:
            print("  No se encontró ese municipio.")
            continue
        if len(filas) == 1:
            f = filas[0]
            print(f"  → {f['nombre']} ({f['depto']}), {f['codigo']}")
            return f["id"]
        return _elegir("¿Cuál?", [(f["id"], f"{f['nombre']} ({f['depto']}), {f['codigo']}") for f in filas])


def _contrasena() -> str:
    while True:
        clave = getpass.getpass("Contraseña del administrador: ")
        try:
            hash_contrasena(clave)
        except ErrorNegocio as exc:
            print(f"  {exc}")
            continue
        if getpass.getpass("Repítela: ") == clave:
            return clave
        print("  No coinciden.")


def main() -> None:
    if not DATABASE_URL:
        sys.exit("Falta ELG_DATABASE_URL (ej. postgresql://elg:elg@localhost:5433/elg).")
    pendientes = migraciones_pendientes(DATABASE_URL)
    if pendientes:
        sys.exit(f"La base tiene migraciones pendientes ({', '.join(pendientes)}): corre db/migrar.py primero.")

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        if conn.execute("SELECT EXISTS (SELECT 1 FROM usuarios) AS hay").fetchone()["hay"]:
            sys.exit("La base ya está configurada: tiene usuarios.")
        conn.rollback()

        print("── Datos del negocio ──")
        tipo = _elegir("Tipo de documento", [("31", "NIT"), ("13", "Cédula de ciudadanía")])
        while True:
            numero = _preguntar("Número (sin dígito de verificación)" if tipo == "31" else "Número")
            if tipo != "31":
                break
            try:
                print(f"  → NIT {numero}-{digito_verificacion(numero)}")
                break
            except ValueError as exc:
                print(f"  {exc}")
        negocio = {
            "tipo_identificacion": tipo,
            "numero_identificacion": numero,
            "nombre": _preguntar("Nombre o razón social"),
            "tipo_persona": "juridica" if tipo == "31" and _si_no("¿Es persona jurídica (empresa)?") else "natural",
            "municipio_id": _municipio(conn),
            "direccion": _preguntar("Dirección", opcional=True),
            "telefono": _preguntar("Teléfono", opcional=True),
            "email": _preguntar("Email", opcional=True),
            "responsable_iva": _si_no("¿Es responsable de IVA?"),
            "regimen_tributario": _elegir("Régimen", [("ordinario", "Ordinario"), ("simple", "Simple (RST)")]),
            "responsable_inc": _si_no("¿Es responsable de INC (impuesto al consumo)?"),
        }
        conn.rollback()

        print("── Usuario administrador ──")
        admin = {"usuario": _preguntar("Usuario"), "contrasena": _contrasena()}

        with conn.transaction():
            crear_configuracion(conn, negocio, admin)
    print(f"Listo: {negocio['nombre']} configurado y usuario {admin['usuario']} creado.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit("\nCancelado: no se guardó nada.")
