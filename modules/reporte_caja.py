"""
modules/reporte_caja.py — El G POS
Genera el PDF de cierre de caja usando ReportLab.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from modules.caja import formatear_pesos

# Paleta de colores
COLOR_PRIMARIO  = colors.HexColor("#1a1a2e")
COLOR_ACENTO    = colors.HexColor("#4f8ef7")
COLOR_EXITO     = colors.HexColor("#22c55e")
COLOR_PELIGRO   = colors.HexColor("#ef4444")
COLOR_FONDO     = colors.HexColor("#f8fafc")
COLOR_BORDE     = colors.HexColor("#e2e8f0")
COLOR_TEXTO_MUT = colors.HexColor("#64748b")


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo", fontSize=20, textColor=COLOR_PRIMARIO,
            fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=2
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo", fontSize=10, textColor=COLOR_TEXTO_MUT,
            fontName="Helvetica", alignment=TA_CENTER, spaceAfter=12
        ),
        "seccion": ParagraphStyle(
            "seccion", fontSize=11, textColor=COLOR_ACENTO,
            fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4
        ),
        "seccion_dig": ParagraphStyle(
            "seccion_dig", fontSize=11, textColor=COLOR_EXITO,
            fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4
        ),
        "label": ParagraphStyle(
            "label", fontSize=9, textColor=COLOR_TEXTO_MUT,
            fontName="Helvetica"
        ),
        "valor": ParagraphStyle(
            "valor", fontSize=9, textColor=COLOR_PRIMARIO,
            fontName="Helvetica-Bold", alignment=TA_RIGHT
        ),
        "diferencia_pos": ParagraphStyle(
            "diferencia_pos", fontSize=10, textColor=COLOR_EXITO,
            fontName="Helvetica-Bold", alignment=TA_RIGHT
        ),
        "diferencia_neg": ParagraphStyle(
            "diferencia_neg", fontSize=10, textColor=COLOR_PELIGRO,
            fontName="Helvetica-Bold", alignment=TA_RIGHT
        ),
        "nota": ParagraphStyle(
            "nota", fontSize=8, textColor=COLOR_TEXTO_MUT,
            fontName="Helvetica-Oblique", spaceBefore=4
        ),
        "pie": ParagraphStyle(
            "pie", fontSize=7, textColor=COLOR_TEXTO_MUT,
            fontName="Helvetica", alignment=TA_CENTER
        ),
    }


def _tabla_resumen(filas_data, col_widths=None):
    col_widths = col_widths or [10 * cm, 6 * cm]
    tabla = Table(filas_data, colWidths=col_widths)
    tabla.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 0), (0, -1), COLOR_TEXTO_MUT),
        ("TEXTCOLOR",   (1, 0), (1, -1), COLOR_PRIMARIO),
        ("FONTNAME",    (1, 0), (1, -1), "Helvetica-Bold"),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [COLOR_FONDO, colors.white]),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW",   (0, -1), (-1, -1), 0.5, COLOR_BORDE),
    ]))
    return tabla


def _tabla_denominaciones(denominaciones: list):
    """Tabla de denominaciones con dos columnas de pares."""
    items = [d for d in denominaciones if d["cantidad"] > 0]
    if not items:
        return None

    encabezado_style = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), COLOR_PRIMARIO),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",       (2, 1), (2, -1), "RIGHT"),
        ("ALIGN",       (3, 1), (3, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_FONDO, colors.white]),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID",        (0, 0), (-1, -1), 0.3, COLOR_BORDE),
    ])

    filas = [["Denominación", "Cantidad", "Subtotal"]]
    for d in items:
        filas.append([
            formatear_pesos(d["denominacion"]),
            str(d["cantidad"]),
            formatear_pesos(d["subtotal"]),
        ])

    tabla = Table(filas, colWidths=[5 * cm, 3 * cm, 5 * cm])
    tabla.setStyle(encabezado_style)
    return tabla


def generar_pdf_cierre(resumen: dict, ruta: str = None) -> str:
    """
    Genera el PDF de cierre de caja.
    resumen: dict retornado por cerrar_caja()
    ruta:    ruta destino. Si es None, genera en el directorio del usuario.
    Retorna la ruta del archivo generado.
    """
    if ruta is None:
        carpeta = os.path.join(os.path.expanduser("~"), "Documents", "ElG_Reportes")
        os.makedirs(carpeta, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = os.path.join(carpeta, f"cierre_caja_{ts}.pdf")

    doc = SimpleDocTemplate(
        ruta,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    es    = _estilos()
    ancho = A4[0] - 4 * cm
    elems = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    elems.append(Paragraph("EL G", es["titulo"]))
    elems.append(Paragraph("TCG · Juegos de Mesa · Comidas", es["subtitulo"]))
    elems.append(HRFlowable(width="100%", thickness=2, color=COLOR_ACENTO))
    elems.append(Spacer(1, 0.3 * cm))

    elems.append(Paragraph("CIERRE DE CAJA", ParagraphStyle(
        "titulo2", fontSize=14, fontName="Helvetica-Bold",
        textColor=COLOR_PRIMARIO, alignment=TA_CENTER
    )))
    elems.append(Spacer(1, 0.2 * cm))

    # Info del turno
    apertura_raw = resumen.get("apertura", "")
    apertura_fmt = apertura_raw[:16] if apertura_raw else "—"
    cierre_fmt   = datetime.now().strftime("%d/%m/%Y  %H:%M")

    info_turno = [
        ["Cajero:",   resumen.get("cajero", "—")],
        ["Apertura:", apertura_fmt],
        ["Cierre:",   cierre_fmt],
        ["Sesión #:", str(resumen.get("sesion_id", "—"))],
    ]
    elems.append(_tabla_resumen(info_turno))
    elems.append(Spacer(1, 0.4 * cm))

    # ── CAJA EFECTIVO ─────────────────────────────────────────────────────────
    elems.append(Paragraph("CAJA EFECTIVO", es["seccion"]))

    base_ef     = resumen.get("monto_base", 0)
    total_ef    = resumen.get("total_efectivo", 0)
    esperado_ef = resumen.get("esperado_efectivo", 0)
    contado_ef  = resumen.get("monto_contado", 0)
    dif_ef      = resumen.get("diferencia", 0)
    gastos_ef   = base_ef + total_ef - esperado_ef  # todos los egresos efectivo

    filas_ef = [
        ["Monto inicial:",      formatear_pesos(base_ef)],
        ["Ventas en efectivo:", formatear_pesos(total_ef)],
        ["Gastos / egresos:",   f"- {formatear_pesos(gastos_ef)}"],
        ["Esperado en caja:",   formatear_pesos(esperado_ef)],
        ["Contado:",            formatear_pesos(contado_ef)],
    ]
    elems.append(_tabla_resumen(filas_ef))

    signo_ef = "+" if dif_ef >= 0 else ""
    color_ef = COLOR_EXITO if dif_ef >= 0 else COLOR_PELIGRO
    elems.append(Spacer(1, 0.15 * cm))
    elems.append(Table(
        [[f"Diferencia efectivo:", f"{signo_ef}{formatear_pesos(dif_ef)}"]],
        colWidths=[10 * cm, 6 * cm],
        style=TableStyle([
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("TEXTCOLOR",     (0, 0), (0, 0),  COLOR_TEXTO_MUT),
            ("TEXTCOLOR",     (1, 0), (1, 0),  color_ef),
            ("ALIGN",         (1, 0), (1, 0),  "RIGHT"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("BACKGROUND",    (0, 0), (-1, -1), COLOR_FONDO),
        ])
    ))

    # ── Denominaciones ────────────────────────────────────────────────────────
    denominaciones = resumen.get("denominaciones", [])
    tabla_denom    = _tabla_denominaciones(denominaciones)
    if tabla_denom:
        elems.append(Spacer(1, 0.3 * cm))
        elems.append(Paragraph("Detalle de denominaciones", ParagraphStyle(
            "sub2", fontSize=9, fontName="Helvetica-Bold",
            textColor=COLOR_PRIMARIO, spaceAfter=4
        )))
        elems.append(tabla_denom)

    # ── CAJA DIGITAL ──────────────────────────────────────────────────────────
    elems.append(Spacer(1, 0.3 * cm))
    elems.append(Paragraph("CAJA DIGITAL", es["seccion_dig"]))

    base_dig     = resumen.get("monto_base_digital", 0)
    total_dig    = resumen.get("total_digital", 0)
    esperado_dig = resumen.get("esperado_digital", 0)
    contado_dig  = resumen.get("monto_contado_digital", 0)
    dif_dig      = resumen.get("diferencia_digital", 0)
    gastos_dig   = base_dig + total_dig - esperado_dig  # todos los egresos digitales

    filas_dig = [
        ["Saldo inicial digital:", formatear_pesos(base_dig)],
        ["Ventas digitales:",      formatear_pesos(total_dig)],
        ["Gastos / egresos:",      f"- {formatear_pesos(gastos_dig)}"],
        ["Esperado en caja:",      formatear_pesos(esperado_dig)],
        ["Saldo contado:",         formatear_pesos(contado_dig)],
    ]
    elems.append(_tabla_resumen(filas_dig))

    signo_dig = "+" if dif_dig >= 0 else ""
    color_dig  = COLOR_EXITO if dif_dig >= 0 else COLOR_PELIGRO
    elems.append(Spacer(1, 0.15 * cm))
    elems.append(Table(
        [["Diferencia digital:", f"{signo_dig}{formatear_pesos(dif_dig)}"]],
        colWidths=[10 * cm, 6 * cm],
        style=TableStyle([
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("TEXTCOLOR",     (0, 0), (0, 0),  COLOR_TEXTO_MUT),
            ("TEXTCOLOR",     (1, 0), (1, 0),  color_dig),
            ("ALIGN",         (1, 0), (1, 0),  "RIGHT"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("BACKGROUND",    (0, 0), (-1, -1), COLOR_FONDO),
        ])
    ))

    # ── Total general ─────────────────────────────────────────────────────────
    total_ventas = resumen.get("total_ventas", 0)
    elems.append(Spacer(1, 0.4 * cm))
    elems.append(HRFlowable(width="100%", thickness=1, color=COLOR_BORDE))
    elems.append(Spacer(1, 0.2 * cm))
    elems.append(Table(
        [["TOTAL VENTAS DEL TURNO:", formatear_pesos(total_ventas)]],
        colWidths=[10 * cm, 6 * cm],
        style=TableStyle([
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 12),
            ("TEXTCOLOR",     (0, 0), (0, 0),  COLOR_PRIMARIO),
            ("TEXTCOLOR",     (1, 0), (1, 0),  COLOR_ACENTO),
            ("ALIGN",         (1, 0), (1, 0),  "RIGHT"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ])
    ))

    # ── Gastos generales del turno ────────────────────────────────────────────
    sesion_id = resumen.get("sesion_id")
    if sesion_id:
        from modules.gastos import resumen_gastos_sesion
        gastos = resumen_gastos_sesion(sesion_id)
        if gastos:
            elems.append(Spacer(1, 0.4 * cm))
            elems.append(Paragraph(
                "GASTOS GENERALES DEL TURNO  "
                "<font size='7' color='#888888'>(excluye pagos a proveedores)</font>",
                ParagraphStyle(
                    "sec_gastos", fontSize=11, textColor=colors.HexColor("#FFB547"),
                    fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4,
                    allowMarkup=1,
                )))
            filas_g = [["Concepto", "Categoría", "Método", "Monto"]]
            total_gastos = 0.0
            for g in gastos:
                filas_g.append([
                    g["concepto"],
                    g["categoria"] or "Otros",
                    g["metodo_pago"],
                    formatear_pesos(g["total"]),
                ])
                total_gastos += g["total"]
            filas_g.append(["", "", "TOTAL GASTOS:", formatear_pesos(total_gastos)])

            tg = Table(filas_g, colWidths=[6 * cm, 4 * cm, 3 * cm, 3 * cm])
            tg.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#FFB547")),
                ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.black),
                ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 8),
                ("ALIGN",         (3, 0), (3, -1),  "RIGHT"),
                ("ALIGN",         (2, -1), (3, -1), "RIGHT"),
                ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [COLOR_FONDO, colors.white]),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ("GRID",          (0, 0), (-1, -1), 0.3, COLOR_BORDE),
                ("LINEABOVE",     (0, -1), (-1, -1), 1, colors.HexColor("#FFB547")),
            ]))
            elems.append(tg)

    # ── Notas ─────────────────────────────────────────────────────────────────
    notas = resumen.get("notas") or ""
    if notas:
        elems.append(Spacer(1, 0.3 * cm))
        elems.append(Paragraph(f"Notas: {notas}", es["nota"]))

    # ── Pie de página ─────────────────────────────────────────────────────────
    elems.append(Spacer(1, 1 * cm))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDE))
    elems.append(Spacer(1, 0.2 * cm))
    elems.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M:%S')} · El G POS",
        es["pie"]
    ))

    doc.build(elems)
    return ruta
