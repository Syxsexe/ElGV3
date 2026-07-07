"""
ui/libros.py — El G POS
Libros contables de ventas y compras con filtro por fechas y exportación CSV.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, timedelta

from ui.base import (FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL,
                     FONT_BOLD, FONT_SMALL)


class FrameLibros(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Libros Contables",
                         "Registro contable de ventas y compras")
        self._build()

    def _build(self):
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Selector de libro ─────────────────────────────────────────────────
        top = tk.Frame(main, bg=COLORS["bg"])
        top.pack(fill="x", pady=(0, 12))

        self._libro_var = tk.StringVar(value="ventas")
        for txt, val in [("Libro de Ventas", "ventas"), ("Libro de Compras", "compras")]:
            tk.Radiobutton(
                top, text=txt, variable=self._libro_var, value=val,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._recargar, padx=14, pady=6,
            ).pack(side="left", padx=(0, 6))

        # ── Filtro de fechas ──────────────────────────────────────────────────
        filtro = tk.Frame(main, bg=COLORS["bg"])
        filtro.pack(fill="x", pady=(0, 12))

        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        tk.Label(filtro, text="Desde", font=FONT_SMALL, bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(side="left")
        self.entry_desde = self._input(filtro, width=12)
        self.entry_desde.insert(0, inicio_mes.isoformat())
        self.entry_desde.pack(side="left", padx=(6, 14), ipady=4)

        tk.Label(filtro, text="Hasta", font=FONT_SMALL, bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(side="left")
        self.entry_hasta = self._input(filtro, width=12)
        self.entry_hasta.insert(0, hoy.isoformat())
        self.entry_hasta.pack(side="left", padx=(6, 14), ipady=4)

        self._btn_primary(filtro, "Consultar", self._recargar).pack(
            side="left", ipadx=8, ipady=4)

        # Atajos de rango
        for txt, cmd in [("Hoy", lambda: self._set_rango(hoy, hoy)),
                         ("Este mes", lambda: self._set_rango(inicio_mes, hoy)),
                         ("Año", lambda: self._set_rango(hoy.replace(month=1, day=1), hoy))]:
            self._btn_secondary(filtro, txt, cmd).pack(side="left", padx=(6, 0), ipadx=4, ipady=4)

        self._btn_secondary(filtro, "⬇ Exportar CSV", self._exportar).pack(
            side="right", ipadx=6, ipady=4)

        # ── Tabla ─────────────────────────────────────────────────────────────
        tabla_wrap = tk.Frame(main, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)
        self._tabla_wrap = tabla_wrap
        self.tree = None
        self._construir_tabla()

        # ── Totales ───────────────────────────────────────────────────────────
        self.tot_card = self._card(main)
        self.tot_card.pack(fill="x", pady=(12, 0))
        self.lbl_totales = tk.Label(
            self.tot_card, text="", font=FONT_BOLD, bg=COLORS["surface"],
            fg=COLORS["text"], anchor="w", justify="left")
        self.lbl_totales.pack(fill="x", padx=16, pady=12)

        self._recargar()

    # ── Construcción dinámica de columnas según el libro ──────────────────────
    def _construir_tabla(self):
        if self.tree is not None:
            for w in self._tabla_wrap.winfo_children():
                w.destroy()
        if self._libro_var.get() == "ventas":
            cols = ("Fecha", "Documento", "Cliente", "NIT/CC", "Base", "IVA", "Total", "DIAN")
            anchos = {"Fecha": 130, "Documento": 130, "Cliente": 200, "NIT/CC": 130,
                      "Base": 100, "IVA": 90, "Total": 110, "DIAN": 90}
        else:
            cols = ("Fecha", "Documento", "Tercero", "Concepto", "Base", "IVA", "Total", "Método")
            anchos = {"Fecha": 130, "Documento": 110, "Tercero": 160, "Concepto": 200,
                      "Base": 100, "IVA": 90, "Total": 110, "Método": 100}
        self.tree = self._tabla(self._tabla_wrap, cols, alto=14)
        for c in cols:
            anchor = "e" if c in ("Base", "IVA", "Total") else ("w" if c in ("Cliente", "Concepto", "Tercero", "Documento") else "center")
            self.tree.column(c, width=anchos[c], anchor=anchor)

    # ── Datos ─────────────────────────────────────────────────────────────────
    def _set_rango(self, desde, hasta):
        self.entry_desde.delete(0, "end"); self.entry_desde.insert(0, desde.isoformat())
        self.entry_hasta.delete(0, "end"); self.entry_hasta.insert(0, hasta.isoformat())
        self._recargar()

    def _fechas(self):
        return self.entry_desde.get().strip() or None, self.entry_hasta.get().strip() or None

    def _recargar(self):
        from modules import libros
        from modules.caja import formatear_pesos
        self._construir_tabla()
        desde, hasta = self._fechas()
        es_ventas = self._libro_var.get() == "ventas"
        try:
            self._datos = (libros.libro_ventas(desde, hasta) if es_ventas
                           else libros.libro_compras(desde, hasta))
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
            return

        for r in self._datos:
            if es_ventas:
                valores = (r["fecha"], r["documento"], r["cliente"], r["nit"],
                           formatear_pesos(r["base"]), formatear_pesos(r["iva"]),
                           formatear_pesos(r["total"]), r["dian"])
            else:
                valores = (r["fecha"], r["documento"], r["tercero"], r["concepto"],
                           formatear_pesos(r["base"]), formatear_pesos(r["iva"]),
                           formatear_pesos(r["total"]), r["metodo"])
            self.tree.insert("", "end", values=valores)

        t = libros.totales(self._datos)
        self.lbl_totales.config(
            text=(f"Registros: {t['registros']}      "
                  f"Base gravable: {formatear_pesos(t['base'])}      "
                  f"IVA: {formatear_pesos(t['iva'])}      "
                  f"TOTAL: {formatear_pesos(t['total'])}"))

    def _exportar(self):
        from modules import libros
        if not getattr(self, "_datos", None):
            messagebox.showinfo("Exportar", "No hay datos para exportar.", parent=self)
            return
        es_ventas = self._libro_var.get() == "ventas"
        nombre = f"libro_{'ventas' if es_ventas else 'compras'}.csv"
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=nombre, parent=self)
        if not ruta:
            return
        if es_ventas:
            cols = ["fecha", "documento", "cliente", "nit", "base", "iva", "total", "metodo", "dian"]
        else:
            cols = ["fecha", "documento", "tercero", "concepto", "base", "iva", "total", "metodo"]
        libros.exportar_csv(self._datos, ruta, cols)
        messagebox.showinfo("Exportado", f"Libro exportado a:\n{ruta}", parent=self)
