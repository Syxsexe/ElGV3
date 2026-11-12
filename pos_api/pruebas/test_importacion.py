"""Importar productos e insumos desde CSV: vista previa, todo o nada, actualizar."""
import uuid
from decimal import Decimal

import pytest

from pos_api.servicios.importacion import numero


def _u(prefijo):
    return f"{prefijo} {uuid.uuid4().hex[:6]}"


@pytest.fixture
def admin(sesion):
    return sesion("admin")


def _importar(api, h, tipo, contenido, confirmar=False):
    return api.post(f"/catalogo/importar/{tipo}", headers=h, json={"contenido": contenido, "confirmar": confirmar})


@pytest.mark.parametrize("texto, valor", [
    ("3500", 3500), ("3.500", 3500), ("$ 3.500", 3500), ("1.234.567", 1234567), ("3,500", 3500),
    ("3.500,50", Decimal("3500.5")), ("3,500.50", Decimal("3500.5")), ("1,5", Decimal("1.5")),
    ("12.5", Decimal("12.5")), ("-2", -2), ("", None),
])
def test_numeros_colombianos_e_internacionales(texto, valor):
    assert numero(texto) == valor


def test_productos_vista_previa_y_confirmar(api, admin, bd):
    cat, codigo = _u("Bebidas"), uuid.uuid4().hex[:8]
    gaseosa, plato = _u("Gaseosa"), _u("Arepa")
    # La categoría del plato es nueva y de cocina: se indica con la columna tipo.
    csv = (f"nombre,codigo,categoria,tipo,precio,costo,stock\n"
           f"{gaseosa},{codigo},{cat},,\"3.500\",\"1.800\",24\n"
           f"{plato},,{cat} cocina,cocina,8000,3000,5\n")

    r = _importar(api, admin, "productos", csv)
    assert r.status_code == 200, r.text
    vista = r.json()
    assert (vista["guardado"], vista["resumen"]) == (False, {"crear": 2, "actualizar": 0, "sin_cambios": 0, "error": 0})
    assert len(vista["categorias_nuevas"]) == 2
    assert "no llevan stock" in vista["filas"][1]["avisos"][0]
    # La vista previa no guardó nada.
    assert bd.execute("SELECT count(*) AS n FROM articulos WHERE nombre = %s", (gaseosa,)).fetchone()["n"] == 0

    r = _importar(api, admin, "productos", csv, confirmar=True)
    assert r.json()["guardado"] is True
    fila = bd.execute("SELECT * FROM v_articulos WHERE nombre = %s", (gaseosa,)).fetchone()
    assert (fila["codigo"], fila["precio_venta"], fila["precio_costo"], fila["stock"], fila["impuesto"]) == (
        codigo, 3500, 1800, 24, "IVA19")
    assert bd.execute("SELECT impuesto FROM v_articulos WHERE nombre = %s", (plato,)).fetchone()["impuesto"] == "INC8"

    # Otra vez con cambios: por código actualiza; el stock queda como un ajuste auditado.
    csv2 = f"codigo;nombre;precio;stock\n{codigo};{gaseosa};3800;20\n"
    r = _importar(api, admin, "productos", csv2, confirmar=True)
    salida = r.json()
    assert (salida["guardado"], salida["resumen"]["actualizar"]) == (True, 1)
    assert "precio $3.500 → $3.800" in salida["filas"][0]["detalle"] and "stock 24 → 20" in salida["filas"][0]["detalle"]
    fila = bd.execute("SELECT * FROM v_articulos WHERE id = %s", (fila["id"],)).fetchone()
    assert (fila["precio_venta"], fila["stock"], fila["precio_costo"]) == (3800, 20, 1800)  # costo vacío: no cambia
    assert bd.execute("SELECT count(*) AS n FROM auditoria WHERE entidad_id = %s AND detalle LIKE %s",
                      (fila["id"], "%importación CSV%")).fetchone()["n"] == 1
    # Igual que lo guardado: sin cambios.
    assert _importar(api, admin, "productos", csv2).json()["resumen"]["sin_cambios"] == 1


def test_con_un_error_no_guarda_nada(api, admin, bd):
    bueno, cat = _u("Bueno"), _u("Cat")
    csv = (f"nombre;categoria;precio;impuesto\n"
           f"{bueno};{cat};1000;\n"
           f"{_u('Sin precio')};{cat};;\n"
           f"{_u('Mal número')};{cat};abc;\n"
           f"{_u('Impuesto raro')};{cat};1000;IVA99\n"
           f"{bueno};{cat};2000;\n")
    r = _importar(api, admin, "productos", csv, confirmar=True)
    salida = r.json()
    assert salida["guardado"] is False
    assert [f["accion"] for f in salida["filas"]] == ["crear", "error", "error", "error", "error"]
    errores = [f["errores"][0] for f in salida["filas"][1:]]
    assert "falta el precio" in errores[0] and "no es un número" in errores[1]
    assert "IVA99" in errores[2] and "repetido: ya está en la fila 2" in errores[3]
    assert bd.execute("SELECT count(*) AS n FROM articulos WHERE nombre = %s", (bueno,)).fetchone()["n"] == 0
    assert bd.execute("SELECT count(*) AS n FROM categorias WHERE nombre = %s", (cat,)).fetchone()["n"] == 0


def test_archivo_sin_columna_obligatoria_o_vacio(api, admin):
    r = _importar(api, admin, "productos", "precio;stock\n1000;3\n")
    assert r.status_code == 400 and "falta la columna nombre" in r.json()["detail"]
    r = _importar(api, admin, "productos", "nombre;precio\n")
    assert r.status_code == 400 and "no tiene filas" in r.json()["detail"]


def test_insumos(api, admin, bd):
    harina = _u("Harina")
    csv = f"Insumo,Unidad,Costo por unidad,Stock,Mínimo\n{harina},gramos,\"2,5\",5000,1000\n"
    r = _importar(api, admin, "insumos", csv, confirmar=True)
    assert r.json()["guardado"] is True, r.text
    ins = bd.execute("SELECT * FROM v_insumos WHERE nombre = %s", (harina,)).fetchone()
    assert (ins["unidad"], ins["costo_unitario"], ins["stock"], ins["stock_minimo"]) == ("g", Decimal("2.5"), 5000, 1000)

    r = _importar(api, admin, "insumos", f"nombre;stock\n{harina.upper()};4200\n{_u('Nuevo')};10\n", confirmar=True)
    salida = r.json()
    assert salida["guardado"] is False
    assert salida["filas"][0]["accion"] == "actualizar"  # encontrado sin importar mayúsculas
    assert "falta la unidad" in salida["filas"][1]["errores"][0]


def test_vendedor_no_importa(api, sesion):
    r = _importar(api, sesion("vendedor"), "productos", "nombre;precio\nX;1\n")
    assert r.status_code == 403
