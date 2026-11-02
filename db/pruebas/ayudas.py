"""
db/pruebas/ayudas.py — Atajos para las pruebas del esquema.

Las reglas de cuadre son triggers diferidos (se revisan al confirmar). Para
revisarlas sin confirmar, confirmar() fuerza SET CONSTRAINTS ALL IMMEDIATE.
"""
import uuid
from contextlib import contextmanager

import psycopg
import pytest


def confirmar(conn):
    """Revisa ya los triggers diferidos (como si se confirmara) sin confirmar."""
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    conn.execute("SET CONSTRAINTS ALL DEFERRED")


@contextmanager
def falla(conn, coincide: str):
    """El bloque (y los triggers diferidos que dispare) debe fallar con un error
    cuyo mensaje contenga `coincide`. Corre en un savepoint para poder seguir."""
    with pytest.raises(psycopg.Error, match=coincide):
        with conn.transaction():
            yield
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    conn.execute("SET CONSTRAINTS ALL DEFERRED")


class Fabrica:
    """Atajos para armar datos válidos en las pruebas."""

    def __init__(self, conn):
        self.conn = conn
        self._n = 0

    def _sufijo(self) -> str:
        self._n += 1
        return f"{self._n}-{uuid.uuid4().hex[:6]}"

    def uno(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def id_de(self, tabla, columna, valor):
        return self.uno(f"SELECT id FROM {tabla} WHERE {columna} = %s", (valor,))["id"]

    def metodo(self, codigo):
        return self.id_de("metodos_pago", "codigo", codigo)

    def caja(self, nombre):
        return self.id_de("cajas", "nombre", nombre)

    def impuesto(self, codigo):
        return self.id_de("impuestos", "codigo", codigo)

    # ── Personas ────────────────────────────────────────────────────────────
    def tercero(self, nombre=None, documento=None):
        tipo = self.id_de("tipos_identificacion", "codigo", "13") if documento else None
        return self.uno(
            "INSERT INTO terceros (nombre, tipo_identificacion_id, numero_identificacion) "
            "VALUES (%s, %s, %s) RETURNING id",
            (nombre or f"Tercero {self._sufijo()}", tipo, documento))["id"]

    def usuario(self, rol="vendedor", tercero_id=None):
        rol_id = self.id_de("roles", "nombre", rol)
        return self.uno(
            "INSERT INTO usuarios (usuario, contrasena_hash, rol_id, tercero_id) "
            "VALUES (%s, 'x', %s, %s) RETURNING id",
            (f"u{self._sufijo()}", rol_id, tercero_id))["id"]

    def cliente(self, limite=100000, tercero_id=None):
        tid = tercero_id or self.tercero()
        self.conn.execute(
            "INSERT INTO clientes (tercero_id, limite_credito) VALUES (%s, %s)", (tid, limite))
        return tid

    def proveedor(self, tercero_id=None):
        tid = tercero_id or self.tercero()
        self.conn.execute("INSERT INTO proveedores (tercero_id) VALUES (%s)", (tid,))
        return tid

    # ── Caja ────────────────────────────────────────────────────────────────
    def turno(self, base_efectivo=0, base_digital=0, usuario_id=None):
        uid = usuario_id or self.usuario()
        sid = self.uno("INSERT INTO sesiones_caja (abierta_por) VALUES (%s) RETURNING id", (uid,))["id"]
        for caja, base in (("Efectivo", base_efectivo), ("Digital", base_digital)):
            self.conn.execute(
                "INSERT INTO sesion_cajas (sesion_id, caja_id, base) VALUES (%s, %s, %s)",
                (sid, self.caja(caja), base))
        return sid

    def cerrar_turno(self, sesion_id, efectivo: dict, digital, usuario_id=None):
        """efectivo = {denominación: cantidad}; el contado de Efectivo es su suma."""
        for valor, cantidad in efectivo.items():
            self.conn.execute(
                "INSERT INTO conteo_denominaciones (sesion_id, denominacion_id, cantidad) VALUES (%s, %s, %s)",
                (sesion_id, self.id_de("denominaciones", "valor", valor), cantidad))
        total = sum(v * c for v, c in efectivo.items())
        for caja, contado in (("Efectivo", total), ("Digital", digital)):
            self.conn.execute(
                "UPDATE sesion_cajas SET contado = %s WHERE sesion_id = %s AND caja_id = %s",
                (contado, sesion_id, self.caja(caja)))
        self.conn.execute(
            "UPDATE sesiones_caja SET cerrada_por = %s, cerrada_en = now() WHERE id = %s",
            (usuario_id or self.usuario(), sesion_id))

    # ── Catálogo ────────────────────────────────────────────────────────────
    def categoria(self, tipo="tienda"):
        return self.uno("INSERT INTO categorias (nombre, tipo) VALUES (%s, %s) RETURNING id",
                        (f"Cat {self._sufijo()}", tipo))["id"]

    def producto(self, precio=10000, impuesto="IVA19", tipo_categoria="tienda", costo=0):
        aid = self.uno(
            "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
            "VALUES ('producto', %s, %s, %s, %s) RETURNING id",
            (f"Prod {self._sufijo()}", self.categoria(tipo_categoria), self.impuesto(impuesto), precio))["id"]
        self.conn.execute("INSERT INTO productos (articulo_id, precio_costo) VALUES (%s, %s)", (aid, costo))
        return aid

    def insumo(self, costo=0, unidad="g"):
        return self.uno(
            "INSERT INTO insumos (nombre, unidad_medida_id, costo_unitario) VALUES (%s, %s, %s) RETURNING id",
            (f"Ins {self._sufijo()}", self.id_de("unidades_medida", "simbolo", unidad), costo))["id"]

    def inscripcion(self):
        return self.id_de("articulos", "nombre", "Inscripción a torneo")

    # ── Ventas ──────────────────────────────────────────────────────────────
    def venta(self, sesion_id, lineas, pagos=(), fiado=(), descuento=0, cliente_id=None, usuario_id=None):
        """lineas = [(articulo_id, cantidad, precio)], pagos = [(codigo, monto)],
        fiado = [(cliente_id, monto)]. Retorna el id de la venta."""
        vid = self.uno(
            "INSERT INTO ventas (sesion_id, usuario_id, cliente_id, descuento) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (sesion_id, usuario_id or self.usuario(), cliente_id, descuento))["id"]
        for articulo, cantidad, precio in lineas:
            self.conn.execute(
                "INSERT INTO detalle_venta (venta_id, articulo_id, cantidad, precio_unit, impuesto_id) "
                "SELECT %s, id, %s, %s, impuesto_id FROM articulos WHERE id = %s",
                (vid, cantidad, precio, articulo))
        for codigo, monto in pagos:
            self.pago_venta(vid, codigo, monto)
        for cliente, monto in fiado:
            self.cargo(cliente, monto, venta_id=vid)
        return vid

    def pago_venta(self, venta_id, codigo, monto):
        return self.uno(
            "INSERT INTO pagos_venta (venta_id, metodo_pago_id, monto) VALUES (%s, %s, %s) RETURNING id",
            (venta_id, self.metodo(codigo), monto))["id"]

    # ── Crédito ─────────────────────────────────────────────────────────────
    def cargo(self, cliente_id, monto, venta_id=None, notas=None, vence_en="2099-01-01"):
        return self.uno(
            "INSERT INTO cargos_credito (cliente_id, venta_id, monto, vence_en, notas) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (cliente_id, venta_id, monto, vence_en, notas if venta_id else (notas or "Saldo inicial")))["id"]

    def abono(self, cliente_id, aplicaciones, sesion_id=None, metodo="efectivo", egreso_id=None, monto=None):
        """aplicaciones = [(cargo_id, monto)]; con egreso_id es un cruce."""
        total = monto if monto is not None else sum(m for _, m in aplicaciones)
        aid = self.uno(
            "INSERT INTO abonos_credito (cliente_id, sesion_id, metodo_pago_id, egreso_id, usuario_id, monto) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (cliente_id, None if egreso_id else sesion_id, None if egreso_id else self.metodo(metodo),
             egreso_id, self.usuario(), total))["id"]
        for cargo_id, m in aplicaciones:
            self.conn.execute(
                "INSERT INTO abono_aplicaciones (abono_id, cargo_id, monto) VALUES (%s, %s, %s)",
                (aid, cargo_id, m))
        return aid

    # ── Gastos y compras ────────────────────────────────────────────────────
    def gasto(self, sesion_id, pagos, categoria="Otros", tercero_id=None, concepto="Gasto"):
        eid = self.uno(
            "INSERT INTO egresos (sesion_id, usuario_id, categoria_gasto_id, tercero_id, concepto) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (sesion_id, self.usuario(), self.id_de("categorias_gasto", "nombre", categoria),
             tercero_id, concepto))["id"]
        for codigo, monto in pagos:
            self.pago_egreso(eid, codigo, monto)
        return eid

    def pago_egreso(self, egreso_id, codigo, monto):
        self.conn.execute(
            "INSERT INTO pagos_egreso (egreso_id, metodo_pago_id, monto) VALUES (%s, %s, %s)",
            (egreso_id, self.metodo(codigo), monto))

    def compra(self, proveedor_id, lineas, **soporte):
        """lineas = [(producto_id | None, insumo_id | None, cantidad, costo_unit)]."""
        cid = self.uno(
            "INSERT INTO compras (proveedor_id, usuario_id, tipo_soporte, numero_soporte, cufe) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (proveedor_id, self.usuario(), soporte.get("tipo_soporte", "otro"),
             soporte.get("numero_soporte"), soporte.get("cufe")))["id"]
        for producto, insumo, cantidad, costo in lineas:
            self.conn.execute(
                "INSERT INTO compra_lineas (compra_id, producto_id, insumo_id, cantidad, costo_unit) "
                "VALUES (%s, %s, %s, %s, %s)", (cid, producto, insumo, cantidad, costo))
        return cid

    def pago_compra(self, sesion_id, compra_id, pagos):
        eid = self.uno(
            "INSERT INTO egresos (sesion_id, usuario_id, compra_id, concepto) "
            "VALUES (%s, %s, %s, 'Pago compra') RETURNING id",
            (sesion_id, self.usuario(), compra_id))["id"]
        for codigo, monto in pagos:
            self.pago_egreso(eid, codigo, monto)
        return eid
