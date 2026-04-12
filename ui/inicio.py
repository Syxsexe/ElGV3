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

        # Estado de caja
        caja_card = self._card(row2)
        caja_card.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(caja_card, text="Estado de Caja", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 8))

        if sesion:
            tk.Label(caja_card, text="● Caja abierta", font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["success"]).pack(anchor="w", padx=20)
            tk.Label(caja_card, text=f"Cajero: {sesion['cajero']}",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=20, pady=2)
            tk.Label(caja_card, text=f"Desde: {sesion['apertura'][:16]}",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=20)
            tk.Label(caja_card,
                     text=f"Ventas acumuladas: {formatear_pesos(sesion['total_ventas'])}",
                     font=FONT_BOLD, bg=COLORS["surface"],
                     fg=COLORS["accent"]).pack(anchor="w", padx=20, pady=(8, 16))
        else:
            tk.Label(caja_card, text="● Caja cerrada", font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["danger"]).pack(anchor="w", padx=20, pady=(0, 16))

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

