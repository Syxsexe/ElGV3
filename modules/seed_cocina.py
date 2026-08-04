"""
modules/seed_cocina.py — El G POS
Pobla la cocina (insumos crudos, preparaciones con receta+rendimiento, y platos
con receta) a partir de los datos canónicos del APU (modules/cocina_datos.py).

Idempotente: se puede correr varias veces sin duplicar (insumos/productos por
nombre; las recetas se reemplazan).

  • Crudos → insumos (stock real de 'Inventario - Import' si el nombre coincide,
    si no 1 kg / 1 L / 100 und por defecto).
  • Preparaciones → insumos + tabla preparaciones (rendimiento) + receta_preparacion.
  • Platos → productos de cocina (precio_venta 0, precio_costo del APU) + receta_insumos.
"""
from __future__ import annotations

from database import get_connection
from modules import cocina_datos as CD


def poblar_cocina() -> dict:
    res = {
        "categorias_creadas": 0, "insumos_nuevos": 0, "insumos_existentes": 0,
        "preparaciones": 0, "recetas_prep": 0,
        "platos_nuevos": 0, "platos_actualizados": 0, "recetas": 0,
        "errores": [],
    }
    conn = get_connection()
    try:
        # ── Categorías ──────────────────────────────────────────────────────
        cat_id = {n: i for i, n in conn.execute("SELECT id, nombre FROM categorias")}
        for nombre in CD.CATEGORIAS:
            if nombre not in cat_id:
                cur = conn.execute(
                    "INSERT INTO categorias (nombre, tipo) VALUES (?, 'cocina')",
                    (nombre,))
                cat_id[nombre] = cur.lastrowid
                res["categorias_creadas"] += 1

        # ── Insumos: crudos + preparaciones (como insumos) ──────────────────
        insumo_id = {n: i for i, n in conn.execute("SELECT id, nombre FROM insumos")}

        def _asegurar_insumo(nombre, unidad, stock, minimo):
            if nombre in insumo_id:
                res["insumos_existentes"] += 1
                return insumo_id[nombre]
            cur = conn.execute(
                "INSERT INTO insumos (nombre, stock, unidad, stock_minimo) VALUES (?, ?, ?, ?)",
                (nombre, stock, unidad, minimo))
            insumo_id[nombre] = cur.lastrowid
            res["insumos_nuevos"] += 1
            return insumo_id[nombre]

        # crudos con su stock (real o por defecto)
        for nombre, unidad in CD.CRUDOS.items():
            stock, minimo = CD.stock_crudo(nombre, unidad)
            _asegurar_insumo(nombre, unidad, stock, minimo)
        # preparaciones como insumos (unidad g); stock inicial = 1 rendimiento
        for nombre, (rendimiento, _receta) in CD.PREPARACIONES.items():
            _asegurar_insumo(nombre, "g", rendimiento, 0)

        # ── Recetas de preparación + rendimiento ────────────────────────────
        from modules.preparaciones import guardar_receta_prep
        for nombre, (rendimiento, receta) in CD.PREPARACIONES.items():
            pid = insumo_id[nombre]
            comps = []
            for comp_nombre, cant in receta:
                cid = insumo_id.get(comp_nombre)
                if not cid:
                    res["errores"].append(f"{nombre}: componente '{comp_nombre}' no existe")
                    continue
                comps.append({"insumo_id": cid, "cantidad": cant})
            guardar_receta_prep(pid, rendimiento, comps, conn=conn)
            res["preparaciones"] += 1
            res["recetas_prep"] += len(comps)

        # ── Platos con receta ───────────────────────────────────────────────
        prod_id = {n: i for i, n in conn.execute("SELECT id, nombre FROM productos")}
        for idx, (nombre, (categoria, costo, receta)) in enumerate(CD.PLATOS.items(), 1):
            cid = cat_id[categoria]
            codigo = CD.codigo_plato(idx)
            pid = prod_id.get(nombre)
            if pid is None:
                cur = conn.execute("""
                    INSERT INTO productos
                        (nombre, codigo, precio_venta, precio_costo, stock, stock_minimo, categoria_id)
                    VALUES (?, ?, 0, ?, 0, 0, ?)
                """, (nombre, codigo, costo, cid))
                pid = cur.lastrowid
                prod_id[nombre] = pid
                res["platos_nuevos"] += 1
            else:
                conn.execute(
                    "UPDATE productos SET precio_costo = ?, categoria_id = ?, activo = 1 WHERE id = ?",
                    (costo, cid, pid))
                res["platos_actualizados"] += 1

            conn.execute("DELETE FROM receta_insumos WHERE producto_id = ?", (pid,))
            for comp_nombre, cant in receta:
                iid = insumo_id.get(comp_nombre)
                if not iid:
                    res["errores"].append(f"{nombre}: insumo '{comp_nombre}' no encontrado")
                    continue
                conn.execute("""
                    INSERT INTO receta_insumos (producto_id, insumo_id, cantidad)
                    VALUES (?, ?, ?)
                """, (pid, iid, cant))
                res["recetas"] += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        res["errores"].append(str(e))
        raise
    finally:
        conn.close()

    return res
