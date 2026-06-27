"""
ui/gastos.py — El G POS
Módulo de gastos generales: nómina, arriendo, aseo, envíos, etc.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import (
    FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_KPI, FONT_TITLE
)
from modules.gastos import CATEGORIAS_GASTO, METODOS_PAGO


class FrameGastos(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Gastos", "Registro de gastos generales del negocio")
        self._tab_activa = tk.StringVar(value="registrar")
        self._build()

    # ── Construcción principal ────────────────────────────────────────────────

    def _build(self):
        tab_frame = tk.Frame(self, bg=COLORS["bg"])
        tab_frame.pack(fill="x", padx=32, pady=(0, 12))
        for label, val in [("Registrar", "registrar"), ("Historial", "historial")]:
            tk.Radiobutton(
                tab_frame, text=label, variable=self._tab_activa, value=val,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._cambiar_tab, padx=14, pady=6,
            ).pack(side="left", padx=(0, 4))

        self._main = tk.Frame(self, bg=COLORS["bg"])
        self._main.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self._cambiar_tab()

    def _cambiar_tab(self):
        for w in self._main.winfo_children():
            w.destroy()
        if self._tab_activa.get() == "registrar":
            self._panel_registrar()
        else:
            self._panel_historial()

    # ── Tab Registrar ─────────────────────────────────────────────────────────

    def _panel_registrar(self):
        from modules.caja import get_sesion_activa, formatear_pesos

        wrapper = tk.Frame(self._main, bg=COLORS["bg"])
        wrapper.pack(anchor="center", expand=True, fill="both")

        card = self._card(wrapper)
        card.pack(anchor="n", pady=20, ipadx=20, ipady=10)
        card.config(width=480)

        tk.Label(card, text="Nuevo gasto", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=24, pady=(20, 0))

        sesion = get_sesion_activa()
        if sesion:
            tk.Label(
                card,
                text=f"Sesión de caja abierta — el gasto se descontará del turno",
                font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text_muted"]
            ).pack(anchor="w", padx=24, pady=(2, 12))
        else:
            tk.Label(
                card,
                text="Sin sesión de caja activa — el gasto se registra sin turno",
                font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["warning"]
            ).pack(anchor="w", padx=24, pady=(2, 12))

        def campo(label_txt, widget_fn):
            tk.Label(card, text=label_txt, font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=24)
            w = widget_fn(card)
            w.pack(fill="x", padx=24, pady=(4, 14), ipady=6)
            return w

        # Concepto
        self.entry_concepto = campo("Concepto *", self._input)

        # Categoría
        tk.Label(card, text="Categoría *", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=24)
        self.combo_cat = ttk.Combobox(
            card, values=CATEGORIAS_GASTO, state="readonly", font=FONT_LABEL
        )
        self.combo_cat.set(CATEGORIAS_GASTO[-1])
        self.combo_cat.pack(fill="x", padx=24, pady=(4, 14), ipady=4)

        # Monto
        tk.Label(card, text="Monto ($) *", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=24)
        self.entry_monto = self._input(card)
        self.entry_monto.pack(fill="x", padx=24, pady=(4, 14), ipady=6)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_monto, "monto")

        # Método de pago
        tk.Label(card, text="Método de pago *", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=24)
        self.combo_metodo = ttk.Combobox(
            card, values=METODOS_PAGO, state="readonly", font=FONT_LABEL
        )
        self.combo_metodo.set("efectivo")
        self.combo_metodo.pack(fill="x", padx=24, pady=(4, 14), ipady=4)

        # Notas
        tk.Label(card, text="Notas (opcional)", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=24)
        self.txt_notas = tk.Text(
            card, height=3, font=FONT_SMALL,
            bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat", highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        self.txt_notas.pack(fill="x", padx=24, pady=(4, 20))

        self._btn_primary(card, "Registrar gasto", self._guardar_gasto).pack(
            fill="x", padx=24, pady=(0, 20), ipady=10
        )

    def _guardar_gasto(self):
        from modules.gastos import registrar_gasto
        from modules.validaciones import leer_entero
        from modules.caja import formatear_pesos

        concepto  = self.entry_concepto.get().strip()
        categoria = self.combo_cat.get()
        metodo    = self.combo_metodo.get()
        notas     = self.txt_notas.get("1.0", "end").strip() or None

        try:
            total = leer_entero(self.entry_monto, default=0)
            if total <= 0:
                raise ValueError("El monto debe ser mayor a cero.")
            egreso_id = registrar_gasto(concepto, total, categoria, metodo, notas)
            messagebox.showinfo(
                "Gasto registrado",
                f"Gasto registrado correctamente.\n\n"
                f"Concepto:  {concepto}\n"
                f"Categoría: {categoria}\n"
                f"Monto:     {formatear_pesos(total)}\n"
                f"Método:    {metodo}"
            )
            # Limpiar formulario
            self.entry_concepto.delete(0, "end")
            self.entry_monto.delete(0, "end")
            self.txt_notas.delete("1.0", "end")
            self.combo_cat.set(CATEGORIAS_GASTO[-1])
            self.combo_metodo.set("efectivo")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Tab Historial ─────────────────────────────────────────────────────────

    def _panel_historial(self):
        # Barra de filtros
        filtros = self._card(self._main)
        filtros.pack(fill="x", pady=(0, 12), ipadx=10, ipady=6)

        fila = tk.Frame(filtros, bg=COLORS["surface"])
        fila.pack(fill="x", padx=16, pady=8)

        tk.Label(fila, text="Desde:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_desde = self._input(fila, width=12)
        self.entry_desde.pack(side="left", padx=(4, 16), ipady=3)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_desde, "fecha")

        tk.Label(fila, text="Hasta:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_hasta = self._input(fila, width=12)
        self.entry_hasta.pack(side="left", padx=(4, 16), ipady=3)
        aplicar_validacion(self.entry_hasta, "fecha")

        tk.Label(fila, text="Categoría:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self.combo_filtro_cat = ttk.Combobox(
            fila, values=["Todas"] + CATEGORIAS_GASTO,
            state="readonly", font=FONT_SMALL, width=18
        )
        self.combo_filtro_cat.set("Todas")
        self.combo_filtro_cat.pack(side="left", padx=(4, 16))

        self._btn_primary(fila, "Filtrar", self._cargar_historial).pack(
            side="left", padx=(0, 8), ipady=3
        )
        self._btn_secondary(fila, "Limpiar", self._limpiar_filtros).pack(
            side="left", ipady=3
        )

        # KPIs
        self._frame_kpis = tk.Frame(self._main, bg=COLORS["bg"])
        self._frame_kpis.pack(fill="x", pady=(0, 12))

        # Tabla
        cols = ("Fecha", "Concepto", "Categoría", "Monto", "Método", "Cajero")
        self._tree = self._tabla(self._main, cols, alto=14)
        self._tree.pack(fill="both", expand=True)

        self._tree.column("Fecha",     width=130, anchor="w")
        self._tree.column("Concepto",  width=200, anchor="w")
        self._tree.column("Categoría", width=140, anchor="w")
        self._tree.column("Monto",     width=100, anchor="e")
        self._tree.column("Método",    width=110, anchor="w")
        self._tree.column("Cajero",    width=100, anchor="w")

        # Botón eliminar (solo admin)
        if auth.get_sesion()["rol"] == "admin":
            self._btn_danger(self._main, "Eliminar seleccionado",
                             self._eliminar_gasto).pack(
                                 anchor="e", pady=(8, 0), padx=0, ipady=5, ipadx=10
                             )

        self._cargar_historial()

    def _cargar_historial(self):
        from modules.gastos import listar_gastos
        from modules.caja import formatear_pesos

        desde   = self.entry_desde.get().strip() or None
        hasta   = self.entry_hasta.get().strip() or None
        cat_sel = self.combo_filtro_cat.get()
        cat     = None if cat_sel == "Todas" else cat_sel

        try:
            gastos = listar_gastos(
                fecha_inicio=desde, fecha_fin=hasta, categoria=cat
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # KPIs
        for w in self._frame_kpis.winfo_children():
            w.destroy()
        total_sum = sum(g["total"] for g in gastos)
        self._kpi(self._frame_kpis, "Total gastos", formatear_pesos(total_sum))
        self._kpi(self._frame_kpis, "Registros", str(len(gastos)))

        # Llenar tabla
        for row in self._tree.get_children():
            self._tree.delete(row)

        for g in gastos:
            self._tree.insert("", "end", iid=str(g["id"]), values=(
                g["fecha"][:16],
                g["concepto"],
                g["categoria"] or "Otros",
                formatear_pesos(g["total"]),
                g["metodo_pago"],
                g["cajero"],
            ))

    def _limpiar_filtros(self):
        self.entry_desde.delete(0, "end")
        self.entry_hasta.delete(0, "end")
        self.combo_filtro_cat.set("Todas")
        self._cargar_historial()

    def _eliminar_gasto(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona un gasto para eliminar.")
            return
        egreso_id = int(sel[0])
        vals      = self._tree.item(egreso_id)["values"]
        if not messagebox.askyesno(
            "Eliminar gasto",
            f"¿Eliminar el gasto?\n\n"
            f"  Concepto: {vals[1]}\n"
            f"  Monto:    {vals[3]}\n\n"
            "Esta acción no se puede deshacer."
        ):
            return
        try:
            from modules.gastos import eliminar_gasto
            eliminar_gasto(egreso_id)
            self._cargar_historial()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _kpi(self, parent, label, valor):
        card = self._card(parent)
        card.pack(side="left", ipadx=16, ipady=8, padx=(0, 12))
        tk.Label(card, text=label, font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=12, pady=(10, 0))
        tk.Label(card, text=valor, font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=12, pady=(0, 10))
