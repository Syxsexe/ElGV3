"""
ui/inicio.py — El G POS
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI

class FrameInicio(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Inicio",
                         "Resumen del día — El G")
        self._build()

    def _build(self):
        from modules.ventas import resumen_del_dia
        from modules.inventario import productos_bajo_stock, insumos_bajo_stock
        from modules.caja import get_sesion_activa, formatear_pesos

        resumen = resumen_del_dia()
        sesion  = get_sesion_activa()

        # ── Fila de KPIs ─────────────────────────────────────────────────────
        kpi_row = tk.Frame(self, bg=COLORS["bg"])
        kpi_row.pack(fill="x", padx=32, pady=(0, 20))

        kpis = [
            ("Ventas hoy",     formatear_pesos(resumen["total"]),       COLORS["accent"]),
            ("Transacciones",  str(resumen["num_ventas"]),               COLORS["success"]),
            ("Tienda",         formatear_pesos(resumen["por_tipo"].get("tienda", 0)), COLORS["accent2"]),
            ("Cocina",         formatear_pesos(resumen["por_tipo"].get("cocina", 0)), COLORS["warning"]),
        ]

        for titulo, valor, color in kpis:
            card = tk.Frame(kpi_row, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            card.pack(side="left", expand=True, fill="both",
                      padx=(0, 12), ipady=16)
            tk.Label(card, text=valor, font=FONT_KPI,
                     bg=COLORS["surface"], fg=color).pack(pady=(16, 4))
            tk.Label(card, text=titulo, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 16))

        # ── Fila inferior ─────────────────────────────────────────────────────
        row2 = tk.Frame(self, bg=COLORS["bg"])
        row2.pack(fill="both", expand=True, padx=32, pady=(0, 28))

        # Estado de caja — dos tarjetas visuales
        caja_frame = tk.Frame(row2, bg=COLORS["bg"])
        caja_frame.pack(side="left", fill="both", expand=True, padx=(0, 12))

        if sesion:
            from modules.caja import migrar_dos_cajas
            from modules.proveedores import migrar_egresos
            from database import get_connection
            migrar_dos_cajas()
            migrar_egresos()

            base_ef   = sesion.get("monto_base", 0) or 0
            base_dig  = sesion.get("monto_base_digital", 0) or 0
            total_ef  = sesion.get("total_efectivo", 0) or 0
            total_dig = sesion.get("total_digital",  0) or 0

            # Egresos del turno
            conn = get_connection()
            row_eg = conn.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN metodo_pago='efectivo'
                                     THEN total ELSE 0 END), 0) AS eg_ef,
                    COALESCE(SUM(CASE WHEN metodo_pago!='efectivo'
                                     THEN total ELSE 0 END), 0) AS eg_dig
                FROM egresos WHERE sesion_id = ?
            """, (sesion["id"],)).fetchone()
            conn.close()
            eg_ef  = row_eg["eg_ef"]  if row_eg else 0
            eg_dig = row_eg["eg_dig"] if row_eg else 0

            saldo_ef  = base_ef  + total_ef  - eg_ef
            saldo_dig = base_dig + total_dig - eg_dig

            def mini_card(parent, titulo, color_fondo, color_acento, items, saldo, label_saldo):
                """Tarjeta visual estilo imagen proporcionada."""
                card = tk.Frame(parent, bg=color_fondo,
                                highlightbackground=color_acento,
                                highlightthickness=2)
                card.pack(side="left", fill="both", expand=True,
                          padx=(0, 6), ipady=8)

                tk.Label(card, text=titulo, font=FONT_BOLD,
                         bg=color_fondo, fg=COLORS["text"]).pack(pady=(10, 8))

                for lbl, val, icono in items:
                    fila = tk.Frame(card, bg=color_fondo)
                    fila.pack(fill="x", padx=16, pady=2)
                    tk.Label(fila, text=f"{icono} {lbl}",
                             font=FONT_SMALL, bg=color_fondo,
                             fg=COLORS["text_muted"]).pack(side="left")
                    tk.Label(fila, text=formatear_pesos(val),
                             font=FONT_SMALL, bg=color_fondo,
                             fg=COLORS["text"]).pack(side="right")

                # Saldo neto
                saldo_frame = tk.Frame(card, bg=color_acento)
                saldo_frame.pack(fill="x", padx=0, pady=(10, 0))
                tk.Label(saldo_frame, text=label_saldo,
                         font=FONT_SMALL, bg=color_acento,
                         fg=COLORS["text"]).pack(pady=(6, 0))
                tk.Label(saldo_frame, text=formatear_pesos(saldo),
                         font=("Segoe UI", 18, "bold"),
                         bg=color_acento, fg=COLORS["text"]).pack(pady=(0, 8))

            # Info turno
            tk.Label(caja_frame,
                     text=f"● Caja abierta  |  {sesion['cajero']}  |  Desde {sesion['apertura'][11:16]}",
                     font=FONT_SMALL, bg=COLORS["bg"],
                     fg=COLORS["success"]).pack(anchor="w", pady=(0, 6))

            cards_row = tk.Frame(caja_frame, bg=COLORS["bg"])
            cards_row.pack(fill="both", expand=True)

            # Tarjeta efectivo
            mini_card(
                cards_row,
                "CAJA EFECTIVO",
                "#1A3A2A",   # verde oscuro
                "#2E8B57",   # verde medio
                [
                    ("Inicial:",  base_ef,  "💵"),
                    ("Ventas:",   total_ef, "🛒"),
                    ("Gastos:",   eg_ef,    "📦"),
                ],
                saldo_ef,
                "EFECTIVO EN CAJA"
            )

            # Tarjeta digital
            mini_card(
                cards_row,
                "CAJA TRANSFERENCIAS",
                "#1A1A3A",   # azul/morado oscuro
                "#4B4BCC",   # azul/morado medio
                [
                    ("Inicial:",  base_dig,  "📱"),
                    ("Ventas:",   total_dig, "🛒"),
                    ("Gastos:",   eg_dig,    "📦"),
                ],
                saldo_dig,
                "TRANSFERENCIAS EN CAJA"
            )

        else:
            caja_card = self._card(caja_frame)
            caja_card.pack(fill="both", expand=True)
            tk.Label(caja_card, text="Estado de Caja", font=FONT_BOLD,
                     bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 8))
            tk.Label(caja_card, text="● Caja cerrada", font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["danger"]).pack(
                         anchor="w", padx=20, pady=(0, 16))

        # Alertas de stock
        alertas_card = self._card(row2)
        alertas_card.pack(side="left", fill="both", expand=True)
        tk.Label(alertas_card, text="Alertas de Stock", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 8))

        productos_bajos = productos_bajo_stock()
        insumos_bajos   = insumos_bajo_stock()
        alertas = [(p["nombre"], f"Stock: {p['stock']} / Mín: {p['stock_minimo']}")
                   for p in productos_bajos[:3]]
        alertas += [(i["nombre"], f"Stock: {i['stock']} {i['unidad']}")
                    for i in insumos_bajos[:3]]

        if alertas:
            for nombre, detalle in alertas:
                fila = tk.Frame(alertas_card, bg=COLORS["surface"])
                fila.pack(fill="x", padx=20, pady=3)
                tk.Label(fila, text="⚠", font=FONT_LABEL,
                         bg=COLORS["surface"], fg=COLORS["warning"]).pack(side="left")
                tk.Label(fila, text=f" {nombre}",
                         font=FONT_BOLD, bg=COLORS["surface"],
                         fg=COLORS["text"]).pack(side="left")
                tk.Label(fila, text=f"  {detalle}",
                         font=FONT_SMALL, bg=COLORS["surface"],
                         fg=COLORS["text_muted"]).pack(side="left")
        else:
            tk.Label(alertas_card, text="✓ Todo el stock en orden",
                     font=FONT_LABEL, bg=COLORS["surface"],
                     fg=COLORS["success"]).pack(anchor="w", padx=20, pady=(0, 16))