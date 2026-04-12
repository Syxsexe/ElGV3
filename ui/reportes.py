"""
ui/reportes.py — El G POS
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI

class FrameReportes(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Reportes", "KPIs y análisis de ventas")
        self._build()

    def _build(self):
        from datetime import date, timedelta
        from modules.caja import formatear_pesos

        filtros = tk.Frame(self, bg=COLORS["bg"])
        filtros.pack(fill="x", padx=32, pady=(0, 16))

        tk.Label(filtros, text="Desde:", font=FONT_LABEL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_ini = self._input(filtros, width=12)
        hoy = date.today()
        self.entry_ini.insert(0, (hoy - timedelta(days=7)).isoformat())
        self.entry_ini.pack(side="left", padx=(4, 16), ipady=4)

        tk.Label(filtros, text="Hasta:", font=FONT_LABEL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_fin = self._input(filtros, width=12)
        self.entry_fin.insert(0, hoy.isoformat())
        self.entry_fin.pack(side="left", padx=(4, 16), ipady=4)

        self._btn_primary(filtros, "Consultar", self._consultar).pack(
            side="left", padx=(0, 8), ipady=4)
        tk.Button(filtros, text="Exportar CSV", font=FONT_BOLD,
                  bg=COLORS["surface"], fg=COLORS["text"],
                  activebackground=COLORS["surface2"],
                  relief="flat", cursor="hand2",
                  command=self._exportar).pack(side="left", ipady=4, padx=4)

        # KPIs rápidos
        self.kpi_frame = tk.Frame(self, bg=COLORS["bg"])
        self.kpi_frame.pack(fill="x", padx=32, pady=(0, 16))

        # Tabla productos más vendidos
        tk.Label(self, text="Productos más vendidos", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", padx=32)
        tabla_wrap = tk.Frame(self, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True, padx=32, pady=(8, 24))
        cols = ("Producto", "Categoría", "Tipo", "Unidades", "Ingresos")
        self.tree = self._tabla(tabla_wrap, cols, alto=12)
        self.tree.column("Producto",   width=200, anchor="w")
        self.tree.column("Categoría",  width=140, anchor="w")
        self.tree.column("Tipo",       width=80)
        self.tree.column("Unidades",   width=80)
        self.tree.column("Ingresos",   width=120)

        self._consultar()

    def _consultar(self):
        from modules.reportes import kpis_generales, productos_mas_vendidos
        from modules.caja import formatear_pesos

        ini = self.entry_ini.get().strip()
        fin = self.entry_fin.get().strip()

        # KPIs
        for w in self.kpi_frame.winfo_children():
            w.destroy()
        try:
            kpis = kpis_generales(ini, fin)
            datos_kpi = [
                ("Ingresos",        formatear_pesos(kpis["ingresos"]["actual"]),      COLORS["accent"]),
                ("Ventas",          str(kpis["num_ventas"]["actual"]),                COLORS["success"]),
                ("Ticket Prom.",    formatear_pesos(kpis["ticket_promedio"]["actual"]), COLORS["accent2"]),
                ("Tienda",          formatear_pesos(kpis["por_linea"]["tienda"]),     COLORS["text"]),
                ("Cocina",          formatear_pesos(kpis["por_linea"]["cocina"]),     COLORS["warning"]),
            ]
            for titulo, valor, color in datos_kpi:
                card = tk.Frame(self.kpi_frame, bg=COLORS["surface"],
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
                card.pack(side="left", expand=True, fill="both",
                          padx=(0, 8), ipady=8)
                tk.Label(card, text=valor, font=("Segoe UI", 18, "bold"),
                         bg=COLORS["surface"], fg=color).pack(pady=(10, 2))
                tk.Label(card, text=titulo, font=FONT_SMALL,
                         bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 10))
        except Exception:
            pass

        # Tabla
        self.tree.delete(*self.tree.get_children())
        try:
            for p in productos_mas_vendidos(ini, fin):
                self.tree.insert("", "end", values=(
                    p["nombre"], p["categoria"],
                    p["tipo_negocio"],
                    p["unidades_vendidas"],
                    formatear_pesos(p["ingresos_totales"])
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _exportar(self):
        from tkinter.filedialog import asksaveasfilename
        from modules.reportes import exportar_ventas_excel
        ini = self.entry_ini.get().strip()
        fin = self.entry_fin.get().strip()
        ruta = asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"ventas_{ini}_{fin}.xlsx"
        )
        if ruta:
            try:
                exportar_ventas_excel(ini, fin, ruta)
                messagebox.showinfo("Exportado", f"✓ Archivo Excel guardado en:\n{ruta}")
            except Exception as e:
                messagebox.showerror("Error al exportar", str(e))

