"""
modules/migracion_clientes.py — El G POS

Importa los CLIENTES de una base de datos vieja (otro programa) a la base actual.

Mapea el esquema viejo (`clientes`: nombre, telefono, email, direccion,
documento, limite_credito, saldo_credito, activo, ...) al nuestro:

  - Con documento  → tipo_documento='CC' (cédula), se conserva el documento.
  - Sin documento  → tipo_documento='CONSUMIDOR_FINAL', documento en blanco.
  - Se aprovechan teléfono / email / dirección cuando existen.
  - El SALDO de fiado (`saldo_credito`) se migra como un cargo de apertura en el
    sistema de crédito nuevo (tabla `creditos`), y se ajusta `limite_credito` para
    que el cliente no quede "sobre el límite".

No importa filas placeholder tipo "Mesa N" (no son clientes reales).
Deduplica para ser idempotente: por documento cuando existe; por
(nombre + teléfono) cuando no hay documento. Abre la base vieja en solo lectura.
"""

import os
import sqlite3
from datetime import datetime, timedelta

from database import get_connection, DB_PATH


def _es_placeholder_mesa(nombre: str) -> bool:
    """True si el nombre es una fila basura tipo 'Mesa 1', 'MESA 9', etc."""
    n = (nombre or "").strip().lower()
    return n.startswith("mesa ") or n == "mesa" or n.startswith("mesa\t")


def migrar_clientes_desde(ruta_bd_vieja: str, migrar_saldos: bool = True) -> dict:
    """
    Lee la tabla `clientes` de `ruta_bd_vieja` y la vuelca en la base actual.

    migrar_saldos: si True, trae el saldo de fiado como cargo de apertura.

    Retorna:
        {
          "agregados":   [nombre, ...],
          "omitidos":    [(nombre, motivo), ...],
          "con_saldo":   [(nombre, saldo), ...],
          "total_saldo": float,
          "errores":     [str, ...],
        }
    """
    res = {"agregados": [], "omitidos": [], "con_saldo": [],
           "fusionados": [], "total_saldo": 0.0, "errores": []}

    ruta = os.path.abspath(os.path.expanduser(ruta_bd_vieja))
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No existe la base vieja: {ruta}")
    if os.path.abspath(str(DB_PATH)) == ruta:
        raise ValueError("La ruta indicada es la MISMA base actual; nada que migrar.")

    # ── Leer la base vieja en solo-lectura ────────────────────────────────────
    try:
        vieja = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        vieja = sqlite3.connect(ruta)
    vieja.row_factory = sqlite3.Row
    try:
        tiene = vieja.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='clientes'"
        ).fetchone()
        if not tiene:
            raise ValueError("La base vieja no tiene tabla 'clientes'.")
        cols = {r[1] for r in vieja.execute("PRAGMA table_info(clientes)")}
        if "nombre" not in cols:
            raise ValueError("La tabla 'clientes' vieja no tiene columna 'nombre'.")
        filas = vieja.execute("SELECT * FROM clientes").fetchall()
    finally:
        vieja.close()

    def col(fila, nombre):
        return fila[nombre] if nombre in fila.keys() else None

    # ── Asegurar esquema de crédito en la base nueva ──────────────────────────
    if migrar_saldos:
        from modules.creditos import migrar as migrar_creditos
        migrar_creditos()

    nueva = get_connection()
    try:
        cols_dest = {r[1] for r in nueva.execute("PRAGMA table_info(clientes)")}
        tiene_limite = "limite_credito" in cols_dest
        tiene_dias   = "dias_credito"   in cols_dest

        # Índices de deduplicación (para re-ejecución idempotente)
        docs_existentes = set()
        nombretel_existentes = set()
        for r in nueva.execute(
                "SELECT nombre, documento, telefono FROM clientes"):
            doc = (r["documento"] or "").strip()
            if doc:
                docs_existentes.add(doc)
            nombretel_existentes.add(
                ((r["nombre"] or "").strip().lower(), (r["telefono"] or "").strip()))

        # ── Fase 1: agrupar por nombre y fusionar homónimos (misma persona) ───
        import re
        def _norm(n):
            return re.sub(r"\s+", " ", (n or "").strip().lower())

        grupos = {}   # clave_nombre -> dict fusionado
        orden  = []   # conserva el orden de primera aparición
        for f in filas:
            nombre = (col(f, "nombre") or "").strip()
            if not nombre:
                res["omitidos"].append(("(sin nombre)", "nombre vacío"))
                continue
            if _es_placeholder_mesa(nombre):
                res["omitidos"].append((nombre, "placeholder de mesa"))
                continue

            documento = (str(col(f, "documento") or "")).strip()
            telefono  = (str(col(f, "telefono")  or "")).strip() or None
            email     = (str(col(f, "email")     or "")).strip() or None
            direccion = (str(col(f, "direccion") or "")).strip() or None
            act = col(f, "activo")
            act = 1 if act is None else int(act)
            try:
                saldo  = float(col(f, "saldo_credito")  or 0)
                limite = float(col(f, "limite_credito") or 0)
            except (TypeError, ValueError):
                saldo, limite = 0.0, 0.0

            k = _norm(nombre)
            g = grupos.get(k)
            if g is None:
                grupos[k] = {
                    "nombre": nombre, "documento": documento, "telefono": telefono,
                    "email": email, "direccion": direccion, "activo": act,
                    "saldo": saldo, "limite": limite,
                }
                orden.append(k)
            else:
                # Homónimo = misma persona: se conserva el mejor dato de cada campo,
                # se suman los saldos y se toma el límite mayor.
                if not g["documento"] and documento:
                    g["documento"] = documento
                if not g["telefono"]  and telefono:
                    g["telefono"] = telefono
                if not g["email"]     and email:
                    g["email"] = email
                if not g["direccion"] and direccion:
                    g["direccion"] = direccion
                g["activo"] = 1 if (g["activo"] or act) else 0
                g["saldo"] += saldo
                g["limite"] = max(g["limite"], limite)
                res["fusionados"].append(nombre)

        # ── Fase 2: insertar cada cliente ya fusionado ────────────────────────
        for k in orden:
            g = grupos[k]
            nombre    = g["nombre"]
            documento = g["documento"]
            telefono  = g["telefono"]
            email     = g["email"]
            direccion = g["direccion"]
            activo    = g["activo"]
            saldo     = g["saldo"]
            limite    = g["limite"]

            if documento:
                tipo_doc = "CC"
                if documento in docs_existentes:
                    res["omitidos"].append((nombre, f"documento {documento} ya existe"))
                    continue
            else:
                tipo_doc = "CONSUMIDOR_FINAL"
                clave = (nombre.lower(), telefono or "")
                if clave in nombretel_existentes:
                    res["omitidos"].append((nombre, "ya existe (nombre+teléfono)"))
                    continue

            # Si trae saldo, el límite debe alcanzarlo para no quedar sobre-límite.
            if migrar_saldos and saldo > 0:
                limite = max(limite, saldo)

            campos = ["nombre", "tipo_documento", "documento",
                      "direccion", "telefono", "email", "activo"]
            valores = [nombre, tipo_doc, documento, direccion, telefono, email, activo]
            if tiene_limite:
                campos.append("limite_credito"); valores.append(limite)
            if tiene_dias:
                campos.append("dias_credito");   valores.append(30)

            marcas = ", ".join("?" for _ in campos)
            cur = nueva.execute(
                f"INSERT INTO clientes ({', '.join(campos)}) VALUES ({marcas})",
                valores)
            cliente_id = cur.lastrowid

            # Migrar saldo de fiado como cargo de apertura.
            if migrar_saldos and saldo > 0:
                venc = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                nueva.execute("""
                    INSERT INTO creditos (cliente_id, tipo, monto, fecha_vencimiento, notas)
                    VALUES (?, 'cargo', ?, ?, ?)
                """, (cliente_id, saldo, venc,
                      "Saldo de fiado migrado del sistema anterior"))
                res["con_saldo"].append((nombre, saldo))
                res["total_saldo"] += saldo

            res["agregados"].append(nombre)
            # Actualiza los índices para que re-ejecutar la migración no duplique.
            if documento:
                docs_existentes.add(documento)
            else:
                nombretel_existentes.add((nombre.lower(), telefono or ""))

        nueva.commit()
    except Exception:
        nueva.rollback()
        raise
    finally:
        nueva.close()

    try:
        from modules.auditoria import registrar
        registrar(
            "clientes",
            f"Migración de clientes desde BD vieja: "
            f"{len(res['agregados'])} agregados, "
            f"{len(res['fusionados'])} homónimos fusionados, "
            f"{len(res['omitidos'])} omitidos, "
            f"{len(res['con_saldo'])} con saldo (${res['total_saldo']:,.0f})",
        )
    except Exception:
        pass

    return res
