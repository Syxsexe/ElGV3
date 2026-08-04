"""
modules/preparaciones.py — El G POS
Producción de cocina ("Preparé un lote").

Una preparación es un insumo que se fabrica a partir de otros insumos (crudos
y/o otras preparaciones). Al preparar N lotes:
  • se DESCUENTA de cada componente su cantidad × N, y
  • se SUMA al stock de la preparación su rendimiento × N.

Todo en una sola transacción. Permite anidar (preparar el filete apanado
descuenta el adobo, que a su vez se preparó antes).
"""
from __future__ import annotations

from database import get_connection


def listar_preparaciones() -> list[dict]:
    """
    Lista las preparaciones con su rendimiento, stock actual y nº de componentes.
    Ordenadas por nombre.
    """
    conn = get_connection()
    try:
        filas = conn.execute("""
            SELECT i.id, i.nombre, i.unidad, i.stock, i.stock_minimo,
                   p.rendimiento,
                   (SELECT COUNT(*) FROM receta_preparacion rp
                     WHERE rp.preparacion_id = i.id) AS num_componentes
            FROM preparaciones p
            JOIN insumos i ON i.id = p.insumo_id
            WHERE i.activo = 1
            ORDER BY i.nombre
        """).fetchall()
        return [dict(f) for f in filas]
    finally:
        conn.close()


def obtener_receta_prep(preparacion_id: int) -> dict | None:
    """
    Retorna la preparación con su rendimiento y la lista de componentes
    (cada uno con stock actual, para ver si alcanza).
    """
    conn = get_connection()
    try:
        cab = conn.execute("""
            SELECT i.id, i.nombre, i.unidad, i.stock, i.stock_minimo, p.rendimiento
            FROM preparaciones p JOIN insumos i ON i.id = p.insumo_id
            WHERE p.insumo_id = ?
        """, (preparacion_id,)).fetchone()
        if not cab:
            return None
        d = dict(cab)
        d["componentes"] = [dict(c) for c in conn.execute("""
            SELECT rp.insumo_id, rp.cantidad,
                   i.nombre, i.unidad, i.stock,
                   (rp.insumo_id IN (SELECT insumo_id FROM preparaciones)) AS es_prep
            FROM receta_preparacion rp
            JOIN insumos i ON i.id = rp.insumo_id
            WHERE rp.preparacion_id = ?
            ORDER BY i.nombre
        """, (preparacion_id,)).fetchall()]
        return d
    finally:
        conn.close()


def guardar_receta_prep(preparacion_id: int, rendimiento: float,
                        componentes: list[dict], conn=None) -> None:
    """
    Marca un insumo como preparación (rendimiento) y reemplaza su receta.
    componentes: [{"insumo_id", "cantidad"}, ...]. Idempotente.
    Acepta conexión externa para correr dentro de una transacción.
    """
    cerrar = conn is None
    if cerrar:
        conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO preparaciones (insumo_id, rendimiento) VALUES (?, ?)
            ON CONFLICT(insumo_id) DO UPDATE SET rendimiento = excluded.rendimiento
        """, (preparacion_id, rendimiento))
        conn.execute("DELETE FROM receta_preparacion WHERE preparacion_id = ?",
                     (preparacion_id,))
        conn.executemany("""
            INSERT INTO receta_preparacion (preparacion_id, insumo_id, cantidad)
            VALUES (?, ?, ?)
        """, [(preparacion_id, c["insumo_id"], c["cantidad"])
              for c in componentes if c["cantidad"] > 0])
        if cerrar:
            conn.commit()
    except Exception:
        if cerrar:
            conn.rollback()
        raise
    finally:
        if cerrar:
            conn.close()


def preparar_lote(preparacion_id: int, num_lotes: float, notas: str | None = None) -> dict:
    """
    Registra la producción de N lotes de una preparación en una transacción:
    descuenta los componentes y sube el stock de la preparación.

    Retorna: {preparacion, rendimiento_total, componentes:[{nombre, unidad,
              consumido, stock_antes, stock_despues, insuficiente}], stock_final,
              faltantes:[nombres]}.
    """
    num_lotes = float(num_lotes or 0)
    if num_lotes <= 0:
        raise ValueError("El número de lotes debe ser mayor que cero.")

    from auth import get_usuario_id
    usuario_id = get_usuario_id()

    conn = get_connection()
    try:
        cab = conn.execute("""
            SELECT i.id, i.nombre, i.unidad, i.stock, p.rendimiento
            FROM preparaciones p JOIN insumos i ON i.id = p.insumo_id
            WHERE p.insumo_id = ?
        """, (preparacion_id,)).fetchone()
        if not cab:
            raise ValueError("La preparación no existe.")
        if (cab["rendimiento"] or 0) <= 0:
            raise ValueError(
                f"'{cab['nombre']}' no tiene rendimiento definido; no se puede producir.")

        comps = conn.execute("""
            SELECT rp.insumo_id, rp.cantidad, i.nombre, i.unidad, i.stock
            FROM receta_preparacion rp JOIN insumos i ON i.id = rp.insumo_id
            WHERE rp.preparacion_id = ? ORDER BY i.nombre
        """, (preparacion_id,)).fetchall()
        if not comps:
            raise ValueError(
                f"'{cab['nombre']}' no tiene receta cargada; no se puede producir.")

        detalle = []
        faltantes = []
        for c in comps:
            consumido = round(c["cantidad"] * num_lotes, 4)
            antes = c["stock"] or 0
            despues = round(antes - consumido, 4)
            insuf = consumido > antes
            if insuf:
                faltantes.append(c["nombre"])
            detalle.append({
                "insumo_id": c["insumo_id"], "nombre": c["nombre"],
                "unidad": c["unidad"], "consumido": consumido,
                "stock_antes": antes, "stock_despues": despues,
                "insuficiente": insuf,
            })

        # Descontar componentes y subir el stock de la preparación.
        for d in detalle:
            conn.execute("UPDATE insumos SET stock = stock - ? WHERE id = ?",
                         (d["consumido"], d["insumo_id"]))
        rendimiento_total = round(cab["rendimiento"] * num_lotes, 4)
        conn.execute("UPDATE insumos SET stock = stock + ? WHERE id = ?",
                     (rendimiento_total, preparacion_id))
        stock_final = round((cab["stock"] or 0) + rendimiento_total, 4)

        conn.execute("""
            INSERT INTO producciones
                (preparacion_id, num_lotes, rendimiento_total, usuario_id, notas)
            VALUES (?, ?, ?, ?, ?)
        """, (preparacion_id, num_lotes, rendimiento_total, usuario_id,
              (notas or "").strip() or None))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar(
            "produccion",
            f"Preparé {num_lotes:g} lote(s) de '{cab['nombre']}' "
            f"(+{rendimiento_total:g} {cab['unidad']})",
            referencia_id=preparacion_id,
        )
    except Exception:
        pass

    return {
        "preparacion": cab["nombre"], "unidad": cab["unidad"],
        "num_lotes": num_lotes, "rendimiento_total": rendimiento_total,
        "componentes": detalle, "stock_final": stock_final,
        "faltantes": faltantes,
    }
