"""
modules/ticket.py — El G POS
Generación e impresión de tickets para impresora térmica (58mm / 80mm).
Usa texto plano con caracteres ASCII — compatible con cualquier térmica.
Imprime directo en Windows vía win32print o guarda como .txt.
"""

from database import get_connection
from modules.caja import formatear_pesos
from datetime import datetime
import platform

# Plataforma / disponibilidad de pywin32
IS_WINDOWS = platform.system() == "Windows"
try:
    if IS_WINDOWS:
        import win32print  # type: ignore
        HAS_WIN32 = True
    else:
        HAS_WIN32 = False
except Exception:
    HAS_WIN32 = False


# ── Ancho de papel ────────────────────────────────────────────────────────────
ANCHO_58 = 32   # caracteres por línea en papel 58mm
ANCHO_80 = 48   # caracteres por línea en papel 80mm
ANCHO    = ANCHO_80   # cambiar a ANCHO_58 si usan papel de 58mm


# ── Helpers de formato ────────────────────────────────────────────────────────

def _centrar(texto: str) -> str:
    return texto.center(ANCHO)

def _separador(caracter: str = "-") -> str:
    return caracter * ANCHO

def _linea_dos_col(izq: str, der: str) -> str:
    """Línea con texto izquierdo y derecho en el mismo renglón."""
    espacio = ANCHO - len(izq) - len(der)
    if espacio < 1:
        espacio = 1
    return izq + " " * espacio + der

def _truncar(texto: str, max_len: int) -> str:
    return texto[:max_len] if len(texto) > max_len else texto


# ── Construcción del ticket ───────────────────────────────────────────────────

def _cabecera() -> list[str]:
    return [
        _separador("="),
        _centrar("EL G"),
        _centrar("TCG • Juegos de Mesa • Comidas"),
        _separador("-"),
        _centrar(datetime.now().strftime("%d/%m/%Y  %H:%M")),
        _separador("-"),
    ]

def _pie(metodos_pago: list[dict] = None, notas: str = None) -> list[str]:
    lineas = [_separador("-")]
    if metodos_pago:
        for p in metodos_pago:
            lineas.append(_linea_dos_col(
                f"  {p['metodo'].upper()}",
                formatear_pesos(p['monto'])
            ))
    lineas += [
        _separador("="),
        _centrar("Gracias por su visita!"),
        _centrar("El G - Para siempre jugando"),
        _separador("="),
        "",
        "",   # espacio para corte
    ]
    if notas:
        lineas.insert(-2, _centrar(notas))
    return lineas


def generar_ticket_venta(venta_id: int) -> str:
    """
    Genera el texto del ticket para una venta.
    Retorna el ticket como string listo para imprimir.
    """
    conn   = get_connection()
    venta  = conn.execute("""
        SELECT v.*, u.usuario AS vendedor
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        WHERE v.id = ?
    """, (venta_id,)).fetchone()

    if not venta:
        conn.close()
        raise ValueError(f"Venta #{venta_id} no encontrada.")

    detalle = conn.execute("""
        SELECT
            COALESCE(p.nombre, cb.nombre) AS nombre,
            dv.cantidad, dv.precio_unit, dv.subtotal
        FROM detalle_venta dv
        LEFT JOIN productos p  ON dv.producto_id = p.id
        LEFT JOIN combos    cb ON dv.combo_id    = cb.id
        WHERE dv.venta_id = ?
    """, (venta_id,)).fetchall()

    factura = conn.execute(
        "SELECT numero, tipo_documento, documento, total_base, iva, iva_porcentaje"
        " FROM facturas WHERE venta_id = ?",
        (venta_id,)
    ).fetchone()

    pagos = conn.execute(
        "SELECT metodo, monto FROM pagos_venta WHERE venta_id = ?",
        (venta_id,)
    ).fetchall()
    conn.close()

    lineas = _cabecera()
    lineas.append(_linea_dos_col(f"  Venta #{venta_id}", f"Vendedor: {venta['vendedor']}"))
    if factura:
        lineas.append(_linea_dos_col("  Factura:", factura["numero"]))
        lineas.append(_linea_dos_col(f"  {factura['tipo_documento']}", factura['documento'] or ""))
    lineas.append(_separador("-"))

    # Encabezado columnas
    lineas.append(f"{'Producto':<{ANCHO-18}}{'Cant':>4}{'Subtotal':>14}")
    lineas.append(_separador("-"))

    for item in detalle:
        nombre   = _truncar(item["nombre"], ANCHO - 18)
        cant     = f"x{int(item['cantidad']) if item['cantidad'] == int(item['cantidad']) else item['cantidad']}"
        subtotal = formatear_pesos(item["subtotal"])
        lineas.append(f"{nombre:<{ANCHO-18}}{cant:>4}{subtotal:>14}")

    lineas.append(_separador("-"))

    # Descuento si aplica
    if venta["descuento"] and venta["descuento"] > 0:
        lineas.append(_linea_dos_col("  Descuento:", f"-{formatear_pesos(venta['descuento'])}"))

    lineas.append(_linea_dos_col("  TOTAL:", formatear_pesos(venta["total"])))

    pagos_fmt = [dict(p) for p in pagos] if pagos else [
        {"metodo": venta["metodo_pago"], "monto": venta["total"]}
    ]
    lineas += _pie(pagos_fmt, venta["notas"])

    return "\n".join(lineas)


def generar_ticket_cuenta(cuenta_id: int, venta_id: int = None) -> str:
    """
    Genera el ticket para una cuenta de mesa (antes o después de cobrar).
    Si se pasa venta_id, incluye el detalle de pago.
    """
    conn   = get_connection()
    cuenta = conn.execute("""
        SELECT c.*, u.usuario AS cajero
        FROM cuentas c
        JOIN usuarios u ON c.usuario_id = u.id
        WHERE c.id = ?
    """, (cuenta_id,)).fetchone()

    if not cuenta:
        conn.close()
        raise ValueError(f"Cuenta #{cuenta_id} no encontrada.")

    items = conn.execute("""
        SELECT nombre, cantidad, precio_unit, subtotal
        FROM cuenta_items WHERE cuenta_id = ?
        ORDER BY agregado_en
    """, (cuenta_id,)).fetchall()

    pagos = []
    if venta_id:
        pagos = conn.execute("""
            SELECT metodo, monto FROM pagos_venta WHERE venta_id = ?
        """, (venta_id,)).fetchall()
    conn.close()

    lineas = _cabecera()
    lineas.append(_centrar(f"Mesa: {cuenta['mesa']}"))
    lineas.append(_centrar(f"Cliente: {cuenta['cliente']}"))
    lineas.append(_separador("-"))
    lineas.append(f"{'Producto':<{ANCHO-18}}{'Cant':>4}{'Subtotal':>14}")
    lineas.append(_separador("-"))

    total = 0
    for item in items:
        nombre   = _truncar(item["nombre"], ANCHO - 18)
        cant     = f"x{int(item['cantidad']) if item['cantidad'] == int(item['cantidad']) else item['cantidad']}"
        subtotal = formatear_pesos(item["subtotal"])
        lineas.append(f"{nombre:<{ANCHO-18}}{cant:>4}{subtotal:>14}")
        total += item["subtotal"]

    lineas.append(_separador("-"))
    lineas.append(_linea_dos_col("  TOTAL:", formatear_pesos(total)))

    pagos_fmt = [dict(p) for p in pagos] if pagos else None
    lineas += _pie(pagos_fmt)
    return "\n".join(lineas)


def generar_ticket_pedido(pedido_id: int) -> str:
    """
    Genera el ticket de recepción de un pedido a proveedor.
    """
    conn   = get_connection()
    pedido = conn.execute("""
        SELECT p.*, pr.nombre AS proveedor_nombre
        FROM pedidos p
        JOIN proveedores pr ON p.proveedor_id = pr.id
        WHERE p.id = ?
    """, (pedido_id,)).fetchone()

    if not pedido:
        conn.close()
        raise ValueError(f"Pedido #{pedido_id} no encontrado.")

    detalle = conn.execute("""
        SELECT
            COALESCE(prod.nombre, ins.nombre) AS nombre,
            dp.cantidad, dp.precio_unit,
            CASE WHEN dp.producto_id IS NOT NULL THEN 'Producto'
                 ELSE 'Insumo' END AS tipo
        FROM detalle_pedido dp
        LEFT JOIN productos prod ON dp.producto_id = prod.id
        LEFT JOIN insumos   ins  ON dp.insumo_id   = ins.id
        WHERE dp.pedido_id = ?
    """, (pedido_id,)).fetchall()

    conn.close()
    pagos = []

    lineas = _cabecera()
    lineas.append(_centrar("RECIBO DE PEDIDO"))
    lineas.append(_linea_dos_col(f"  Pedido #{pedido_id}", pedido["fecha"][:10]))
    lineas.append(_linea_dos_col("  Proveedor:", _truncar(pedido["proveedor_nombre"], 20)))
    lineas.append(_separador("-"))
    lineas.append(f"{'Item':<{ANCHO-20}}{'Tipo':>8}{'Cant':>5}{'Precio':>7}")
    lineas.append(_separador("-"))

    for item in detalle:
        nombre = _truncar(item["nombre"], ANCHO - 20)
        cant   = str(int(item["cantidad"]) if item["cantidad"] == int(item["cantidad"])
                     else round(item["cantidad"], 1))
        precio = formatear_pesos(item["precio_unit"]) if item["precio_unit"] else "$0"
        lineas.append(f"{nombre:<{ANCHO-20}}{item['tipo']:>8}{cant:>5}{precio:>7}")

    lineas.append(_separador("-"))
    if pedido["total"]:
        lineas.append(_linea_dos_col("  TOTAL PEDIDO:", formatear_pesos(pedido["total"])))

    pagos_fmt = [dict(p) for p in pagos] if pagos else None
    lineas += _pie(pagos_fmt, pedido["notas"])
    return "\n".join(lineas)


# ── Impresión ─────────────────────────────────────────────────────────────────

def imprimir_ticket(texto: str, impresora: str = None) -> bool:
    """
    Envía el ticket a la impresora térmica.
    En Windows usa win32print.
    impresora: nombre de la impresora. Si es None usa la predeterminada.
    Retorna True si tuvo éxito.
    """
    # Si no está disponible pywin32, solo mostramos el ticket en consola
    if not HAS_WIN32:
        print(texto)
        return False

    try:
        printer_name = impresora or win32print.GetDefaultPrinter()
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            hJob = win32print.StartDocPrinter(hPrinter, 1,
                                               ("Ticket El G", None, "RAW"))
            win32print.StartPagePrinter(hPrinter)
            # Codificar en cp437 (estándar para térmicas)
            data = (texto + "\n\x1b\x69").encode("cp437", errors="replace")
            win32print.WritePrinter(hPrinter, data)
            win32print.EndPagePrinter(hPrinter)
            win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)
        return True
    except Exception as e:
        raise RuntimeError(f"Error al imprimir: {e}")


def listar_impresoras() -> list[str]:
    """Retorna las impresoras instaladas en Windows."""
    if not HAS_WIN32:
        return []
    try:
        return [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )]
    except Exception:
        return []


def guardar_ticket(texto: str, ruta: str) -> str:
    """Guarda el ticket como archivo .txt. Retorna la ruta."""
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return ruta


# ── Prueba directa ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from database import inicializar
    from auth import iniciar_sesion
    inicializar()
    iniciar_sesion("admin", "admin123")

    conn = get_connection()
    venta = conn.execute("SELECT id FROM ventas ORDER BY id DESC LIMIT 1").fetchone()
    cuenta = conn.execute("SELECT id FROM cuentas ORDER BY id DESC LIMIT 1").fetchone()
    pedido = conn.execute("SELECT id FROM pedidos ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    if venta:
        print("── TICKET VENTA ──")
        ticket = generar_ticket_venta(venta["id"])
        print(ticket)
        guardar_ticket(ticket, "/tmp/ticket_venta.txt")
        print(f"\nGuardado en /tmp/ticket_venta.txt")

    if cuenta:
        print("\n── TICKET CUENTA ──")
        ticket = generar_ticket_cuenta(cuenta["id"])
        print(ticket)

    if pedido:
        print("\n── TICKET PEDIDO ──")
        ticket = generar_ticket_pedido(pedido["id"])
        print(ticket)
