"""
ui/reportes.py — El G POS
Panel de reportes con pestañas: Ventas · Productos · Inventario · Caja.
Solo accesible para administradores.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import (
    FrameBase, COLORS,
    FONT_BOLD, FONT_SMALL, FONT_LABEL, FONT_KPI,
)


class FrameReportes(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Reportes", "Análisis de ventas, inventario y caja")
        self._tab_actual = tk.StringVar(value="ventas")
        self._build()

    # ── Estructura principal ──────────────────────────────────────────────────

    def _build(self):
        from datetime import date, timedelta
        hoy = date.today()

        # Barra de filtros
        bar = tk.Frame(self, bg=COLORS["bg"])
        bar.pack(fill="x", padx=32, pady=(0, 12))

        tk.Label(bar, text="Desde:", font=FONT_LABEL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_ini = self._input(bar, width=12)
        self.entry_ini.insert(0, (hoy - timedelta(days=6)).isoformat())
        self.entry_ini.pack(side="left", padx=(4, 12), ipady=4)

        tk.Label(bar, text="Hasta:", font=FONT_LABEL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_fin = self._input(bar, width=12)
        self.entry_fin.insert(0, hoy.isoformat())
        self.entry_fin.pack(side="left", padx=(4, 14), ipady=4)

        def preset(dias):
            from datetime import date, timedelta
            self.entry_ini.delete(0, "end")
            self.entry_ini.insert(0, (date.today() - timedelta(days=dias - 1)).isoformat())
            self.entry_fin.delete(0, "end")
            self.entry_fin.insert(0, date.today().isoformat())
            self._consultar()

        for lbl, d in [("Hoy", 1), ("7 días", 7), ("30 días", 30)]:
            tk.Button(bar, text=lbl, font=FONT_SMALL,
                      bg=COLORS["surface"], fg=COLORS["text_muted"],
                      activebackground=COLORS["surface2"],
                      relief="flat", cursor="hand2",
                      command=lambda d=d: preset(d)).pack(
                          side="left", padx=(0, 4), ipady=4, ipadx=8)

        self._btn_primary(bar, "Consultar", self._consultar).pack(
            side="left", padx=(10, 6), ipady=4, ipadx=8)
        tk.Button(bar, text="Exportar Excel", font=FONT_BOLD,
                  bg=COLORS["surface"], fg=COLORS["text"],
                  activebackground=COLORS["surface2"],
                  relief="flat", cursor="hand2",
                  command=self._exportar).pack(side="left", ipady=4, ipadx=8)

        # KPI strip
        self._kpi_frame = tk.Frame(self, bg=COLORS["bg"])
        self._kpi_frame.pack(fill="x", padx=32, pady=(0, 12))

        # Barra de pestañas
        tab_bar = tk.Frame(self, bg=COLORS["bg"])
        tab_bar.pack(fill="x", padx=32, pady=(0, 10))
        for texto, valor in [("Ventas", "ventas"), ("Productos", "productos"),
                              ("Inventario", "inventario"), ("Caja", "caja")]:
            tk.Radiobutton(
                tab_bar, text=texto, variable=self._tab_actual, value=valor,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._cambiar_tab, padx=14, pady=6,
            ).pack(side="left", padx=(0, 4))

        # Contenedor dinámico de pestaña
        self._tab_outer = tk.Frame(self, bg=COLORS["bg"])
        self._tab_outer.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        self._consultar()

    # ── Consulta ─────────────────────────────────────────────────────────────

    def _consultar(self):
        if not auth.es_admin():
            for w in self._kpi_frame.winfo_children():
                w.destroy()
            tk.Label(self._kpi_frame,
                     text="⚠  Los reportes están disponibles solo para administradores.",
                     font=FONT_LABEL, bg=COLORS["bg"], fg=COLORS["warning"]).pack(anchor="w")
            for w in self._tab_outer.winfo_children():
                w.destroy()
            return

        ini = self.entry_ini.get().strip()
        fin = self.entry_fin.get().strip()
        self._render_kpis(ini, fin)
        self._cambiar_tab()

    def _cambiar_tab(self):
        for w in self._tab_outer.winfo_children():
            w.destroy()
        if not auth.es_admin():
            return
        ini = self.entry_ini.get().strip()
        fin = self.entry_fin.get().strip()
        tab = self._tab_actual.get()
        if tab == "ventas":
            self._tab_ventas(ini, fin)
        elif tab == "productos":
            self._tab_productos(ini, fin)
        elif tab == "inventario":
            self._tab_inventario()
        elif tab == "caja":
            self._tab_caja(ini, fin)

    # ── KPI strip ─────────────────────────────────────────────────────────────

    def _render_kpis(self, ini, fin):
        from modules.reportes import kpis_generales
        from modules.caja import formatear_pesos

        for w in self._kpi_frame.winfo_children():
            w.destroy()

        try:
            kpis = kpis_generales(ini, fin)
        except Exception as e:
            tk.Label(self._kpi_frame, text=f"Error al cargar KPIs: {e}",
                     font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["danger"]).pack(anchor="w")
            return

        def var_label(parent, variacion):
            if variacion is None:
                return
            sym = "▲" if variacion >= 0 else "▼"
            col = COLORS["success"] if variacion >= 0 else COLORS["danger"]
            tk.Label(parent, text=f"{sym} {abs(variacion):.1f}%  vs período anterior",
                     font=("Segoe UI", 8), bg=COLORS["surface"], fg=col).pack(pady=(2, 8))

        items = [
            ("Ingresos",     formatear_pesos(kpis["ingresos"]["actual"]),
             kpis["ingresos"]["variacion"],        COLORS["accent"]),
            ("Ventas",       str(kpis["num_ventas"]["actual"]),
             kpis["num_ventas"]["variacion"],      COLORS["success"]),
            ("Ticket prom.", formatear_pesos(kpis["ticket_promedio"]["actual"]),
             kpis["ticket_promedio"]["variacion"], COLORS["accent2"]),
            ("Tienda",       formatear_pesos(kpis["por_linea"]["tienda"]),
             None, COLORS["accent"]),
            ("Cocina",       formatear_pesos(kpis["por_linea"]["cocina"]),
             None, COLORS["warning"]),
        ]

        for i, (titulo, valor, var, color) in enumerate(items):
            card = tk.Frame(self._kpi_frame, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side="left", expand=True, fill="both",
                      padx=(0, 8 if i < 4 else 0), ipady=4)
            tk.Frame(card, bg=color, height=3).pack(fill="x")
            tk.Label(card, text=valor, font=("Segoe UI", 15, "bold"),
                     bg=COLORS["surface"], fg=color).pack(pady=(10, 1))
            tk.Label(card, text=titulo, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack()
            var_label(card, var)
            if var is None:
                tk.Frame(card, bg=COLORS["surface"], height=16).pack()

        # Estrella + mejor día
        estrella = kpis.get("producto_estrella")
        mejor    = kpis.get("mejor_dia")
        if estrella or mejor:
            extra = tk.Frame(self._kpi_frame, bg=COLORS["surface"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
            extra.pack(side="left", expand=True, fill="both", ipady=4)
            tk.Frame(extra, bg=COLORS["text_dim"], height=3).pack(fill="x")
            if estrella:
                tk.Label(extra, text=estrella["nombre"][:22],
                         font=("Segoe UI", 10, "bold"),
                         bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(10, 0))
                tk.Label(extra, text="⭐ Producto estrella", font=FONT_SMALL,
                         bg=COLORS["surface"], fg=COLORS["text_muted"]).pack()
            if mejor:
                tk.Label(extra, text=mejor["dia"][5:],
                         font=("Segoe UI", 10, "bold"),
                         bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(6, 0))
                tk.Label(extra, text="📅 Mejor día", font=FONT_SMALL,
                         bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 8))

    # ── Pestaña Ventas ────────────────────────────────────────────────────────

    def _tab_ventas(self, ini, fin):
        from modules.reportes import reporte_ventas_por_periodo
        from modules.caja import formatear_pesos

        try:
            data = reporte_ventas_por_periodo(ini, fin)
        except Exception as e:
            tk.Label(self._tab_outer, text=f"Error: {e}",
                     font=FONT_LABEL, bg=COLORS["bg"], fg=COLORS["danger"]).pack()
            return

        row = tk.Frame(self._tab_outer, bg=COLORS["bg"])
        row.pack(fill="both", expand=True)

        # Izquierda: ventas por día
        left = tk.Frame(row, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tk.Label(left, text="Ventas por día", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))
        wl = tk.Frame(left, bg=COLORS["bg"])
        wl.pack(fill="both", expand=True)
        t1 = self._tabla(wl, ("Día", "Transacciones", "Total"), alto=12)
        t1.column("Día",           width=120)
        t1.column("Transacciones", width=110)
        t1.column("Total",         width=130)
        for d in data["por_dia"]:
            t1.insert("", "end", values=(
                d["dia"], d["num"], formatear_pesos(d["total"])))

        # Derecha: método y vendedor
        right = tk.Frame(row, bg=COLORS["bg"], width=290)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="Por método de pago", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))
        wm = tk.Frame(right, bg=COLORS["bg"])
        wm.pack(fill="x")
        t2 = self._tabla(wm, ("Método", "Transacc.", "Total"), alto=6)
        t2.column("Método",     width=100, anchor="w")
        t2.column("Transacc.",  width=70)
        t2.column("Total",      width=100)
        for m in data["por_metodo"]:
            t2.insert("", "end", values=(
                m["metodo_pago"], m["num"], formatear_pesos(m["total"])))

        tk.Label(right, text="Por vendedor", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(14, 6))
        wv = tk.Frame(right, bg=COLORS["bg"])
        wv.pack(fill="x")
        t3 = self._tabla(wv, ("Vendedor", "Ventas", "Total"), alto=6)
        t3.column("Vendedor", width=100, anchor="w")
        t3.column("Ventas",   width=70)
        t3.column("Total",    width=100)
        for v in data["por_vendedor"]:
            t3.insert("", "end", values=(
                v["usuario"], v["num_ventas"], formatear_pesos(v["total"])))

        # Desglose tienda / cocina
        por_tipo = {r["tipo"]: r["total"] for r in data["por_tipo"]}
        if por_tipo:
            resumen = tk.Frame(right, bg=COLORS["bg"])
            resumen.pack(fill="x", pady=(14, 0))
            tk.Label(resumen, text="Por tipo de negocio", font=FONT_BOLD,
                     bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))
            for tipo, color in [("tienda", COLORS["accent"]), ("cocina", COLORS["warning"])]:
                total = por_tipo.get(tipo, 0)
                f = tk.Frame(resumen, bg=COLORS["surface"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
                f.pack(fill="x", pady=(0, 4), ipady=4)
                tk.Label(f, text=tipo.capitalize(), font=FONT_SMALL,
                         bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=10)
                tk.Label(f, text=formatear_pesos(total), font=FONT_BOLD,
                         bg=COLORS["surface"], fg=color).pack(anchor="w", padx=10)

    # ── Pestaña Productos ─────────────────────────────────────────────────────

    def _tab_productos(self, ini, fin):
        from modules.reportes import productos_mas_vendidos, combos_mas_vendidos
        from modules.caja import formatear_pesos

        row = tk.Frame(self._tab_outer, bg=COLORS["bg"])
        row.pack(fill="both", expand=True)

        # Productos
        left = tk.Frame(row, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tk.Label(left, text="Productos más vendidos", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))
        wl = tk.Frame(left, bg=COLORS["bg"])
        wl.pack(fill="both", expand=True)
        t1 = self._tabla(wl, ("Producto", "Categoría", "Tipo", "Uds.", "Ingresos"), alto=14)
        t1.column("Producto",  width=190, anchor="w")
        t1.column("Categoría", width=130, anchor="w")
        t1.column("Tipo",      width=70)
        t1.column("Uds.",      width=60)
        t1.column("Ingresos",  width=110)
        try:
            for p in productos_mas_vendidos(ini, fin, limite=15):
                t1.insert("", "end", values=(
                    p["nombre"], p["categoria"], p["tipo_negocio"],
                    int(p["unidades_vendidas"]),
                    formatear_pesos(p["ingresos_totales"]),
                ))
        except Exception as e:
            t1.insert("", "end", values=(f"Error: {e}", "", "", "", ""))

        # Combos
        right = tk.Frame(row, bg=COLORS["bg"], width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="Combos más vendidos", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))
        wr = tk.Frame(right, bg=COLORS["bg"])
        wr.pack(fill="x")
        t2 = self._tabla(wr, ("Combo", "Veces", "Ingresos"), alto=10)
        t2.column("Combo",    width=130, anchor="w")
        t2.column("Veces",    width=60)
        t2.column("Ingresos", width=100)
        try:
            for c in combos_mas_vendidos(ini, fin, limite=10):
                t2.insert("", "end", values=(
                    c["nombre"], int(c["veces_vendido"]),
                    formatear_pesos(c["ingresos_totales"]),
                ))
        except Exception as e:
            t2.insert("", "end", values=(f"Error: {e}", "", ""))

    # ── Pestaña Inventario ────────────────────────────────────────────────────

    def _tab_inventario(self):
        from modules.reportes import reporte_inventario, reporte_insumos
        from modules.caja import formatear_pesos

        row = tk.Frame(self._tab_outer, bg=COLORS["bg"])
        row.pack(fill="both", expand=True)

        # Izquierda: productos
        left = tk.Frame(row, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        try:
            inv = reporte_inventario()
            tot = inv["totales"]

            # Cards resumen
            cards = tk.Frame(left, bg=COLORS["bg"])
            cards.pack(fill="x", pady=(0, 10))
            for titulo, valor, color in [
                ("Total productos",  str(tot.get("total_productos") or 0), COLORS["text"]),
                ("Valor en costo",   formatear_pesos(tot.get("valor_costo") or 0), COLORS["warning"]),
                ("Valor en venta",   formatear_pesos(tot.get("valor_venta") or 0), COLORS["success"]),
            ]:
                c = tk.Frame(cards, bg=COLORS["surface"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
                c.pack(side="left", expand=True, fill="both", padx=(0, 6), ipady=4)
                tk.Label(c, text=valor, font=("Segoe UI", 13, "bold"),
                         bg=COLORS["surface"], fg=color).pack(pady=(8, 2))
                tk.Label(c, text=titulo, font=FONT_SMALL,
                         bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 8))

            tk.Label(left, text="Productos bajo mínimo de stock", font=FONT_BOLD,
                     bg=COLORS["bg"], fg=COLORS["warning"]).pack(anchor="w", pady=(0, 6))
            wl = tk.Frame(left, bg=COLORS["bg"])
            wl.pack(fill="both", expand=True)
            t1 = self._tabla(wl,
                             ("Producto", "Categoría", "Stock actual", "Mínimo", "Faltante"),
                             alto=10)
            t1.column("Producto",     width=180, anchor="w")
            t1.column("Categoría",    width=130, anchor="w")
            t1.column("Stock actual", width=90)
            t1.column("Mínimo",       width=70)
            t1.column("Faltante",     width=70)
            for p in inv["bajo_minimo"]:
                t1.insert("", "end", values=(
                    p["nombre"], p["categoria"],
                    p["stock"], p["stock_minimo"], p["faltante"],
                ), tags=("alerta",))
            t1.tag_configure("alerta", foreground=COLORS["warning"])

            if not inv["bajo_minimo"]:
                tk.Label(left, text="✓  Todo el stock de productos en orden.",
                         font=FONT_SMALL, bg=COLORS["bg"],
                         fg=COLORS["success"]).pack(anchor="w", pady=8)

        except Exception as e:
            tk.Label(left, text=f"Error al cargar inventario: {e}",
                     font=FONT_LABEL, bg=COLORS["bg"], fg=COLORS["danger"]).pack(anchor="w")

        # Derecha: insumos
        right = tk.Frame(row, bg=COLORS["bg"], width=280)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        try:
            ins = reporte_insumos()

            tk.Label(right, text="Insumos de cocina", font=FONT_BOLD,
                     bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))

            if ins["bajo_minimo"]:
                tk.Label(right, text="⚠  Bajo mínimo:", font=FONT_SMALL,
                         bg=COLORS["bg"], fg=COLORS["warning"]).pack(anchor="w")
                wb = tk.Frame(right, bg=COLORS["bg"])
                wb.pack(fill="x", pady=(4, 10))
                tb = self._tabla(wb, ("Insumo", "Stock", "Unidad"), alto=5)
                tb.column("Insumo", width=120, anchor="w")
                tb.column("Stock",  width=60)
                tb.column("Unidad", width=70)
                for i in ins["bajo_minimo"]:
                    tb.insert("", "end",
                              values=(i["nombre"], i["stock"], i["unidad"]),
                              tags=("alerta",))
                tb.tag_configure("alerta", foreground=COLORS["warning"])
            else:
                tk.Label(right, text="✓  Insumos en orden.", font=FONT_SMALL,
                         bg=COLORS["bg"], fg=COLORS["success"]).pack(anchor="w", pady=(0, 8))

            tk.Label(right, text="Todos los insumos:", font=FONT_SMALL,
                     bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))
            wa = tk.Frame(right, bg=COLORS["bg"])
            wa.pack(fill="x")
            ta = self._tabla(wa, ("Insumo", "Stock", "Unidad"), alto=12)
            ta.column("Insumo", width=120, anchor="w")
            ta.column("Stock",  width=60)
            ta.column("Unidad", width=70)
            for i in ins["listado"]:
                ta.insert("", "end", values=(i["nombre"], i["stock"], i["unidad"]))

        except Exception as e:
            tk.Label(right, text=f"Error insumos: {e}",
                     font=FONT_LABEL, bg=COLORS["bg"], fg=COLORS["danger"]).pack(anchor="w")

    # ── Pestaña Caja ──────────────────────────────────────────────────────────

    def _tab_caja(self, ini, fin):
        from modules.reportes import reporte_caja_por_periodo
        from modules.caja import formatear_pesos

        try:
            data = reporte_caja_por_periodo(ini, fin)
        except Exception as e:
            tk.Label(self._tab_outer, text=f"Error: {e}",
                     font=FONT_LABEL, bg=COLORS["bg"], fg=COLORS["danger"]).pack()
            return

        tot = data["totales"]

        # Cards de resumen
        cards = tk.Frame(self._tab_outer, bg=COLORS["bg"])
        cards.pack(fill="x", pady=(0, 14))

        dif_total = tot.get("diferencia_total") or 0
        for titulo, valor, color in [
            ("Sesiones",       str(tot.get("num_sesiones") or 0),          COLORS["text"]),
            ("Total ventas",   formatear_pesos(tot.get("suma_ventas") or 0), COLORS["success"]),
            ("Total contado",  formatear_pesos(tot.get("suma_contado") or 0), COLORS["accent"]),
            ("Diferencia",     formatear_pesos(dif_total),
             COLORS["success"] if dif_total >= 0 else COLORS["danger"]),
        ]:
            c = tk.Frame(cards, bg=COLORS["surface"],
                         highlightbackground=COLORS["border"], highlightthickness=1)
            c.pack(side="left", expand=True, fill="both", padx=(0, 8), ipady=4)
            tk.Label(c, text=valor, font=("Segoe UI", 14, "bold"),
                     bg=COLORS["surface"], fg=color).pack(pady=(10, 2))
            tk.Label(c, text=titulo, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 10))

        # Tabla de sesiones
        tk.Label(self._tab_outer, text="Historial de sesiones de caja", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))
        wrap = tk.Frame(self._tab_outer, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True)

        cols = ("ID", "Apertura", "Cierre", "Cajero",
                "Base", "Ventas", "Contado", "Diferencia")
        t = self._tabla(wrap, cols, alto=12)
        t.column("ID",         width=40)
        t.column("Apertura",   width=130)
        t.column("Cierre",     width=130)
        t.column("Cajero",     width=110, anchor="w")
        t.column("Base",       width=100)
        t.column("Ventas",     width=100)
        t.column("Contado",    width=100)
        t.column("Diferencia", width=100)

        for s in data["sesiones"]:
            dif = s.get("diferencia") or 0
            tag = "pos" if dif >= 0 else "neg"
            t.insert("", "end", values=(
                s["id"],
                (s["apertura"] or "")[:16],
                (s["cierre"]   or "—")[:16],
                s["cajero"],
                formatear_pesos(s.get("monto_base")    or 0),
                formatear_pesos(s.get("total_ventas")  or 0),
                formatear_pesos(s.get("monto_cierre")  or 0),
                formatear_pesos(dif),
            ), tags=(tag,))
        t.tag_configure("pos", foreground=COLORS["success"])
        t.tag_configure("neg", foreground=COLORS["danger"])

    # ── Exportar ──────────────────────────────────────────────────────────────

    def _exportar(self):
        from tkinter.filedialog import asksaveasfilename
        from modules.reportes import exportar_ventas_excel

        ini = self.entry_ini.get().strip()
        fin = self.entry_fin.get().strip()
        ruta = asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"ventas_{ini}_{fin}.xlsx",
        )
        if not ruta:
            return
        try:
            exportar_ventas_excel(ini, fin, ruta)
            messagebox.showinfo("Exportado", f"✓ Archivo Excel guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error al exportar", str(e))
