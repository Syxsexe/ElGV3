"""
pos_api/servicios/importacion.py — Importar productos o insumos desde un CSV.

El archivo se procesa completo dentro de una transacción: cada fila crea o
actualiza su producto (o insumo) con las mismas funciones de Inventario, así
que valen las mismas reglas y queda la misma auditoría. Sin confirmar (la
vista previa) todo se deshace al final; confirmado, se guarda solo si ninguna
fila tuvo error: todo o nada.

Una fila corresponde a un producto existente por su código o, sin código,
por su nombre (sin importar mayúsculas ni tildes); a un insumo, por su
nombre. Una celda vacía no cambia ese dato. El stock del archivo se fija como
un conteo (ajuste de stock con su antes y después en la auditoría).

Números: acepta "3500", "3.500", "3,500.50", "3.500,50" y "$ 3.500". Con un
solo separador, si agrupa de a tres cifras es de miles ("1.500" = 1500); si
no, es el decimal ("1,5" = 1.5).
"""
import csv
import io
import re
from decimal import Decimal, InvalidOperation

import psycopg

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado, SinPermiso, mensaje_de
from pos_api.seguridad import Usuario
from pos_api.servicios import catalogo
from pos_api.servicios.comun import pesos, sin_tildes

MAX_FILAS = 5000
MOTIVO = "importación CSV"

# Encabezados aceptados (sin tildes, en minúsculas, espacios como _) → campo.
COLUMNAS = {
    "productos": {
        "nombre": "nombre", "producto": "nombre", "articulo": "nombre",
        "codigo": "codigo", "codigo_de_barras": "codigo", "referencia": "codigo",
        "categoria": "categoria",
        "tipo": "tipo_categoria", "tipo_categoria": "tipo_categoria",
        "precio": "precio_venta", "precio_venta": "precio_venta", "precio_de_venta": "precio_venta",
        "costo": "precio_costo", "precio_costo": "precio_costo", "costo_unitario": "precio_costo",
        "stock": "stock", "cantidad": "stock", "existencias": "stock",
        "stock_minimo": "stock_minimo", "minimo": "stock_minimo",
        "impuesto": "impuesto",
    },
    "insumos": {
        "nombre": "nombre", "insumo": "nombre",
        "unidad": "unidad", "unidad_de_medida": "unidad",
        "costo": "costo_unitario", "costo_unitario": "costo_unitario", "costo_por_unidad": "costo_unitario",
        "stock": "stock", "cantidad": "stock", "existencias": "stock",
        "stock_minimo": "stock_minimo", "minimo": "stock_minimo",
    },
}
OBLIGATORIAS = {"productos": {"nombre"}, "insumos": {"nombre"}}
UNIDADES = {"g": "g", "gr": "g", "gramo": "g", "gramos": "g",
            "ml": "ml", "mililitro": "ml", "mililitros": "ml",
            "und": "und", "un": "und", "unidad": "und", "unidades": "und", "u": "und"}


def _clave(texto: str) -> str:
    """Para comparar nombres: sin tildes, sin mayúsculas, sin espacios de sobra."""
    return " ".join(sin_tildes(texto).split())


def _encabezado(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes(texto.strip().lstrip("﻿")).lower()).strip("_")


def numero(texto: str | None) -> Decimal | None:
    """Número de una celda en formato colombiano o internacional; None si vacía."""
    if texto is None or not texto.strip():
        return None
    t = texto.strip().replace("$", "").replace(" ", "").replace(" ", "")
    negativo = t.startswith("-")
    t = t.lstrip("-+")
    if "." in t and "," in t:
        decimal_sep = "." if t.rfind(".") > t.rfind(",") else ","
        t = t.replace("," if decimal_sep == "." else ".", "").replace(decimal_sep, ".")
    elif "," in t:
        t = t.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", t) else t.replace(",", ".")
    elif "." in t and re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    try:
        valor = Decimal(t)
    except InvalidOperation:
        raise ValueError(f'"{texto.strip()}" no es un número') from None
    if not valor.is_finite():
        raise ValueError(f'"{texto.strip()}" no es un número')
    return -valor if negativo else valor


def leer_csv(contenido: str, tipo: str) -> list[dict]:
    """Filas del archivo como dicts {campo: texto} con su número de línea en
    "_fila". El separador (coma, punto y coma o tabulador) se detecta solo."""
    lineas = contenido.lstrip("﻿").splitlines()
    if not lineas or not lineas[0].strip():
        raise ErrorNegocio("El archivo está vacío.")
    primera = lineas[0]
    separador = max((";", ",", "\t"), key=primera.count)
    lector = csv.reader(io.StringIO("\n".join(lineas)), delimiter=separador)
    encabezados = [_encabezado(h) for h in next(lector)]
    columnas = COLUMNAS[tipo]
    campos = [columnas.get(h) for h in encabezados]
    faltan = OBLIGATORIAS[tipo] - set(campos)
    if faltan:
        raise ErrorNegocio(f"Al archivo le falta la columna {', '.join(sorted(faltan))}. "
                           f"Columnas posibles: {', '.join(sorted(set(columnas.values())))}.")
    filas = []
    for n, valores in enumerate(lector, start=2):
        if not any(v.strip() for v in valores):
            continue
        fila = {"_fila": n}
        for campo, valor in zip(campos, valores):
            if campo and valor.strip():
                fila[campo] = valor.strip()
        filas.append(fila)
    if not filas:
        raise ErrorNegocio("El archivo no tiene filas debajo de los encabezados.")
    if len(filas) > MAX_FILAS:
        raise ErrorNegocio(f"El archivo tiene {len(filas)} filas; el máximo es {MAX_FILAS} por importación.")
    return filas


def _numeros(fila: dict, campos: tuple) -> dict:
    """Convierte las celdas numéricas presentes; los errores van en la fila."""
    resultado = {}
    for campo in campos:
        if campo in fila:
            valor = numero(fila[campo])
            if campo != "stock" and valor < 0:
                raise ValueError(f"{campo.replace('_', ' ')} no puede ser negativo")
            resultado[campo] = valor
    return resultado


def _cambio(nombre: str, antes, despues, plata: bool = False) -> str | None:
    if antes is not None and despues is not None and Decimal(antes) == Decimal(despues):
        return None
    f = pesos if plata else (lambda v: "—" if v is None else f"{Decimal(v).normalize():f}")
    return f"{nombre} {f(antes) if antes is not None else '—'} → {f(despues)}"


# ── Productos ───────────────────────────────────────────────────────────────

def _producto(conn, actor: Usuario, fila: dict, ctx: dict) -> dict:
    nums = _numeros(fila, ("precio_venta", "precio_costo", "stock", "stock_minimo"))
    codigo = fila.get("codigo")
    clave_nombre = _clave(fila["nombre"])

    existente = None
    if codigo:
        existente = ctx["por_codigo"].get(codigo)
    if existente is None:
        candidatos = ctx["por_nombre"].get(clave_nombre, [])
        if len(candidatos) > 1:
            raise ErrorNegocio("hay varios productos con ese nombre: agrega el código para saber cuál es")
        if candidatos:
            existente = candidatos[0]
            if codigo and existente["codigo"] and existente["codigo"] != codigo:
                raise ErrorNegocio(f"ya existe un producto con ese nombre y otro código ({existente['codigo']})")

    impuesto_id = None
    if "impuesto" in fila:
        impuesto_id = ctx["impuestos"].get(_clave(fila["impuesto"]))
        if impuesto_id is None:
            raise ErrorNegocio(f'el impuesto "{fila["impuesto"]}" no existe (usa {", ".join(ctx["codigos_impuesto"])})')

    categoria = None
    if "categoria" in fila:
        categoria = ctx["categorias"].get(_clave(fila["categoria"]))
        if categoria is None:
            tipo = "cocina" if _clave(fila.get("tipo_categoria", "")) == "COCINA" else "tienda"
            categoria = catalogo.crear_categoria(conn, actor, fila["categoria"], tipo)
            ctx["categorias"][_clave(fila["categoria"])] = categoria
            ctx["categorias_nuevas"].append(f"{categoria['nombre']} ({tipo})")
    avisos = []

    if existente is None:
        if categoria is None:
            raise ErrorNegocio("para crear el producto falta la categoría")
        if nums.get("precio_venta") is None:
            raise ErrorNegocio("para crear el producto falta el precio")
        es_cocina = categoria["tipo"] == "cocina"
        if es_cocina and nums.get("stock"):
            avisos.append("los platos de cocina no llevan stock propio: se ignora el stock")
        nuevo = catalogo.crear_articulo(conn, actor, {
            "tipo": "producto", "nombre": fila["nombre"], "categoria_id": categoria["id"],
            "precio_venta": nums["precio_venta"], "impuesto_id": impuesto_id,
            "codigo": codigo, "precio_costo": nums.get("precio_costo"),
            "stock": None if es_cocina else nums.get("stock"),
            "stock_minimo": None if es_cocina else nums.get("stock_minimo"),
        })
        ctx["por_nombre"].setdefault(clave_nombre, []).append(nuevo)
        if codigo:
            ctx["por_codigo"][codigo] = nuevo
        detalle = [f"{categoria['nombre']}", pesos(nuevo["precio_venta"])]
        if not es_cocina:
            detalle.append(f"stock {Decimal(nuevo['stock']).normalize():f}")
        return {"accion": "crear", "detalle": ", ".join(detalle), "avisos": avisos}

    if not existente["activo"]:
        avisos.append("el producto está inactivo: se actualiza pero sigue inactivo")
    antes = existente
    cambios = {}
    if codigo and codigo != antes["codigo"]:
        cambios["codigo"] = codigo
    if categoria is not None and categoria["id"] != antes["categoria_id"]:
        cambios["categoria_id"] = categoria["id"]
    if impuesto_id is not None and impuesto_id != antes["impuesto_id"]:
        cambios["impuesto_id"] = impuesto_id
    for campo in ("precio_venta", "stock_minimo"):
        if nums.get(campo) is not None and Decimal(antes[campo] or 0) != nums[campo]:
            cambios[campo] = nums[campo]
    if nums.get("precio_costo") is not None and Decimal(antes["precio_costo"] or 0) != nums["precio_costo"]:
        if antes["tiene_receta"]:
            avisos.append("el costo de un plato con receta se calcula solo: se ignora el costo")
        else:
            cambios["precio_costo"] = nums["precio_costo"]
    es_tienda = (categoria or {"tipo": antes["categoria_tipo"]})["tipo"] == "tienda"
    nuevo_stock = nums.get("stock") if es_tienda else None
    if nums.get("stock") is not None and not es_tienda:
        avisos.append("los platos de cocina no llevan stock propio: se ignora el stock")

    detalle = [d for d in (
        _cambio("código", antes["codigo"], cambios["codigo"]) if "codigo" in cambios else None,
        f"categoría → {categoria['nombre']}" if "categoria_id" in cambios else None,
        "impuesto cambiado" if "impuesto_id" in cambios else None,
        _cambio("precio", antes["precio_venta"], cambios.get("precio_venta"), True) if "precio_venta" in cambios else None,
        _cambio("costo", antes["precio_costo"], cambios.get("precio_costo"), True) if "precio_costo" in cambios else None,
        _cambio("stock mínimo", antes["stock_minimo"], cambios.get("stock_minimo")) if "stock_minimo" in cambios else None,
        _cambio("stock", antes["stock"], nuevo_stock) if nuevo_stock is not None else None,
    ) if d]
    if cambios:
        catalogo.editar_articulo(conn, actor, antes["id"], cambios)
    if nuevo_stock is not None and Decimal(antes["stock"] or 0) != nuevo_stock:
        catalogo.ajustar_stock(conn, actor, antes["id"], nuevo_stock, MOTIVO)
    if not detalle:
        return {"accion": "sin_cambios", "detalle": "", "avisos": avisos}
    return {"accion": "actualizar", "detalle": "; ".join(detalle), "avisos": avisos}


def _contexto_productos(conn) -> dict:
    productos = conn.execute("SELECT * FROM v_articulos WHERE tipo = 'producto'").fetchall()
    por_nombre = {}
    for p in productos:
        por_nombre.setdefault(_clave(p["nombre"]), []).append(p)
    impuestos = conn.execute("SELECT id, codigo, nombre FROM impuestos").fetchall()
    return {
        "por_codigo": {p["codigo"]: p for p in productos if p["codigo"]},
        "por_nombre": por_nombre,
        "categorias": {_clave(c["nombre"]): c for c in conn.execute("SELECT id, nombre, tipo FROM categorias")},
        "impuestos": {**{_clave(i["nombre"]): i["id"] for i in impuestos}, **{_clave(i["codigo"]): i["id"] for i in impuestos}},
        "codigos_impuesto": [i["codigo"] for i in impuestos],
        "categorias_nuevas": [],
    }


# ── Insumos ─────────────────────────────────────────────────────────────────

def _insumo(conn, actor: Usuario, fila: dict, ctx: dict) -> dict:
    nums = _numeros(fila, ("costo_unitario", "stock", "stock_minimo"))
    unidad = None
    if "unidad" in fila:
        simbolo = UNIDADES.get(fila["unidad"].strip().lower())
        unidad = ctx["unidades"].get(simbolo)
        if unidad is None:
            raise ErrorNegocio(f'la unidad "{fila["unidad"]}" no existe (usa g, ml o und)')
    existente = ctx["por_nombre"].get(_clave(fila["nombre"]))

    if existente is None:
        if unidad is None:
            raise ErrorNegocio("para crear el insumo falta la unidad (g, ml o und)")
        nuevo = catalogo.crear_insumo(conn, actor, fila["nombre"], unidad["id"], nums.get("costo_unitario") or Decimal(0),
                                      nums.get("stock"), nums.get("stock_minimo"))
        ctx["por_nombre"][_clave(fila["nombre"])] = nuevo
        return {"accion": "crear", "avisos": [],
                "detalle": f"{unidad['simbolo']}, costo {nuevo['costo_unitario'].normalize():f}/{unidad['simbolo']}, "
                           f"stock {Decimal(nuevo['stock']).normalize():f}"}

    antes, avisos, cambios = existente, [], {}
    if not antes["activo"]:
        avisos.append("el insumo está inactivo: se actualiza pero sigue inactivo")
    if unidad is not None and unidad["id"] != antes["unidad_medida_id"]:
        cambios["unidad_medida_id"] = unidad["id"]
    if nums.get("costo_unitario") is not None and Decimal(antes["costo_unitario"]) != nums["costo_unitario"]:
        if antes["es_preparacion"]:
            avisos.append("el costo de una preparación se calcula con su receta: se ignora el costo")
        else:
            cambios["costo_unitario"] = nums["costo_unitario"]
    if nums.get("stock_minimo") is not None and Decimal(antes["stock_minimo"]) != nums["stock_minimo"]:
        cambios["stock_minimo"] = nums["stock_minimo"]
    nuevo_stock = nums.get("stock")
    detalle = [d for d in (
        f"unidad → {unidad['simbolo']}" if "unidad_medida_id" in cambios else None,
        _cambio("costo", antes["costo_unitario"], cambios.get("costo_unitario")) if "costo_unitario" in cambios else None,
        _cambio("stock mínimo", antes["stock_minimo"], cambios.get("stock_minimo")) if "stock_minimo" in cambios else None,
        _cambio("stock", antes["stock"], nuevo_stock) if nuevo_stock is not None else None,
    ) if d]
    if cambios:
        catalogo.editar_insumo(conn, actor, antes["id"], cambios)
    if nuevo_stock is not None and Decimal(antes["stock"]) != nuevo_stock:
        catalogo.ajustar_stock_insumo(conn, actor, antes["id"], nuevo_stock, MOTIVO)
    if not detalle:
        return {"accion": "sin_cambios", "detalle": "", "avisos": avisos}
    return {"accion": "actualizar", "detalle": "; ".join(detalle), "avisos": avisos}


def _contexto_insumos(conn) -> dict:
    return {
        "por_nombre": {_clave(i["nombre"]): i for i in conn.execute("SELECT * FROM v_insumos")},
        "unidades": {u["simbolo"]: u for u in conn.execute("SELECT id, simbolo FROM unidades_medida")},
    }


# ── Importar ────────────────────────────────────────────────────────────────

class _Deshacer(Exception):
    """Para salir del bloque de la transacción deshaciéndola."""


def importar(conn, actor: Usuario, tipo: str, contenido: str, confirmar: bool) -> dict:
    """tipo: "productos" o "insumos". Retorna el resultado fila por fila y si
    quedó guardado (solo con confirmar y sin errores)."""
    if not actor.puede(catalogo.PERMISO_INVENTARIO):
        raise SinPermiso("No tienes permiso para importar al inventario.")
    filas = leer_csv(contenido, tipo)
    procesar = _producto if tipo == "productos" else _insumo
    resultado = {"tipo": tipo, "guardado": False, "filas": [], "categorias_nuevas": []}
    vistos = {}
    try:
        with conn.transaction():
            ctx = _contexto_productos(conn) if tipo == "productos" else _contexto_insumos(conn)
            for fila in filas:
                salida = {"fila": fila["_fila"], "nombre": fila["nombre"], "codigo": fila.get("codigo"),
                          "errores": [], "avisos": []}
                clave = ("codigo", fila["codigo"]) if fila.get("codigo") else ("nombre", _clave(fila["nombre"]))
                if clave in vistos:
                    salida.update(accion="error", detalle="",
                                  errores=[f"repetido: ya está en la fila {vistos[clave]}"])
                    resultado["filas"].append(salida)
                    continue
                vistos[clave] = fila["_fila"]
                try:
                    # Cada fila en su savepoint: si falla, se deshace solo ella y
                    # se sigue con las demás para mostrar todos los errores. Las
                    # reglas diferidas de la base se revisan aquí, no al final.
                    with conn.transaction():
                        salida.update(procesar(conn, actor, fila, ctx))
                        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                        conn.execute("SET CONSTRAINTS ALL DEFERRED")
                except ValueError as e:
                    salida.update(accion="error", detalle="", errores=[str(e)])
                except (ErrorNegocio, NoEncontrado) as e:
                    salida.update(accion="error", detalle="", errores=[str(e)])
                except psycopg.Error as e:
                    salida.update(accion="error", detalle="", errores=[mensaje_de(e)])
                resultado["filas"].append(salida)

            resultado["categorias_nuevas"] = ctx.get("categorias_nuevas", [])
            cuenta = {a: sum(1 for f in resultado["filas"] if f["accion"] == a)
                      for a in ("crear", "actualizar", "sin_cambios", "error")}
            resultado["resumen"] = cuenta
            if not confirmar or cuenta["error"]:
                raise _Deshacer
            auditar(conn, actor.id, "inventario",
                    f"Importó {tipo} desde CSV: {cuenta['crear']} nuevos, {cuenta['actualizar']} actualizados, "
                    f"{cuenta['sin_cambios']} sin cambios")
            resultado["guardado"] = True
    except _Deshacer:
        pass
    return resultado
