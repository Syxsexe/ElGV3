"""
ui/auditoria.py — El G POS
Panel de auditoría: registro de actividad por usuario. Solo admin.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import (
    FrameBase, COLORS,
    FONT_BOLD, FONT_SMALL, FONT_LABEL, FONT_KPI,
)
from modules.auditoria import ACCIONES


# Colores por categoría de acción
_COLORES_ACCION = {
    "login":      "#4f8ef7",
    "caja":       "#22c55e",
    "venta":      "#f59e0b",
    "cuenta":     "#a78bfa",
    "gasto":      "#ef4444",
    "inventario": "#06b6d4",
    "sistema":    "#6b7280",
}


class FrameAuditoria(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Auditoría", "Registro de actividad por usuario")
        self._build()

    def _build(self):
        import auth
        if not auth.es_admin():
            tk.Label(
                self, text="Solo administradores pueden ver la auditoría.",
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["danger"]
            ).pack(expand=True)
            return

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Filtros ───────────────────────────────────────────────────────────
        filtros = tk.Frame(main, bg=COLORS["bg"])
        filtros.pack(fill="x", pady=(0, 12))

        def _lbl(parent, texto):
            tk.Label(parent, text=texto, font=FONT_SMALL,
                     bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w")

        col1 = tk.Frame(filtros, bg=COLORS["bg"])
        col1.pack(side="left", padx=(0, 16))
        _lbl(col1, "Desde")
        self.entry_desde = self._input(col1, width=12)
        self.entry_desde.pack(ipady=4)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_desde, "fecha")

        col2 = tk.Frame(filtros, bg=COLORS["bg"])
        col2.pack(side="left", padx=(0, 16))
        _lbl(col2, "Hasta")
        self.entry_hasta = self._input(col2, width=12)
        self.entry_hasta.pack(ipady=4)
        aplicar_validacion(self.entry_hasta, "fecha")

        col3 = tk.Frame(filtros, bg=COLORS["bg"])
        col3.pack(side="left", padx=(0, 16))
        _lbl(col3, "Usuario")
        self.combo_usuario = ttk.Combobox(
            col3, width=14, state="readonly", font=FONT_SMALL,
        )
        self.combo_usuario.pack(ipady=3)
        self._cargar_usuarios_combo()

        col4 = tk.Frame(filtros, bg=COLORS["bg"])
        col4.pack(side="left", padx=(0, 16))
        _lbl(col4, "Tipo")
        opciones_tipo = ["Todos"] + list(ACCIONES.values())
        self.combo_tipo = ttk.Combobox(
            col4, values=opciones_tipo, width=14, state="readonly", font=FONT_SMALL
        )
        self.combo_tipo.current(0)
        self.combo_tipo.pack(ipady=3)

        col5 = tk.Frame(filtros, bg=COLORS["bg"])
        col5.pack(side="left", padx=(0, 16))
        _lbl(col5, "Buscar")
        self.entry_texto = self._input(col5, width=18)
        self.entry_texto.pack(ipady=4)
        self.entry_texto.bind("<KeyRelease>", lambda e: self._cargar())

        col6 = tk.Frame(filtros, bg=COLORS["bg"])
        col6.pack(side="left", pady=(14, 0))
        self._btn_primary(col6, "Filtrar", self._cargar).pack(ipady=5, padx=4)

        # ── KPIs ─────────────────────────────────────────────────────────────
        self._kpi_frame = tk.Frame(main, bg=COLORS["bg"])
        self._kpi_frame.pack(fill="x", pady=(0, 10))

        # ── Tabla ─────────────────────────────────────────────────────────────
        self.tree = self._tabla(
            main,
            ("fecha", "usuario", "tipo", "detalle", "ref"),
            alto=20,
        )
        self.tree.heading("fecha",   text="Fecha y hora")
        self.tree.heading("usuario", text="Usuario")
        self.tree.heading("tipo",    text="Tipo")
        self.tree.heading("detalle", text="Detalle")
        self.tree.heading("ref",     text="Ref.")
        self.tree.column("fecha",   width=145, anchor="w")
        self.tree.column("usuario", width=100, anchor="w")
        self.tree.column("tipo",    width=90,  anchor="center")
        self.tree.column("detalle", width=500, anchor="w")
        self.tree.column("ref",     width=55,  anchor="center")

        # Tags de color por tipo de acción
        for accion, color in _COLORES_ACCION.items():
            self.tree.tag_configure(accion, foreground=color)

        self._cargar()

    # ── Carga de datos ────────────────────────────────────────────────────────

    def _cargar_usuarios_combo(self):
        from modules.auditoria import listar_usuarios_con_actividad
        usuarios = listar_usuarios_con_actividad()
        self._usuarios_map = {u["usuario"]: u["usuario_id"] for u in usuarios}
        self.combo_usuario["values"] = ["Todos"] + [u["usuario"] for u in usuarios]
        self.combo_usuario.current(0)

    def _cargar(self):
        from modules.auditoria import listar, ACCIONES
        from modules.validaciones import leer_texto

        desde  = self.entry_desde.get().strip() or None
        hasta  = self.entry_hasta.get().strip() or None
        texto  = self.entry_texto.get().strip() or None

        usel = self.combo_usuario.get()
        uid  = self._usuarios_map.get(usel) if usel != "Todos" else None

        tsel = self.combo_tipo.get()
        accion_key = None
        if tsel and tsel != "Todos":
            accion_key = next((k for k, v in ACCIONES.items() if v == tsel), None)

        eventos = listar(
            fecha_inicio=desde,
            fecha_fin=hasta,
            usuario_id=uid,
            accion=accion_key,
            texto=texto,
        )

        self.tree.delete(*self.tree.get_children())
        for ev in eventos:
            accion = ev.get("accion", "sistema")
            label  = ACCIONES.get(accion, accion)
            ref    = ev.get("referencia_id") or ""
            self.tree.insert("", "end", values=(
                ev["fecha"],
                ev.get("usuario", "—"),
                label,
                ev.get("detalle", ""),
                ref,
            ), tags=(accion,))

        self._actualizar_kpis(eventos)
        self._cargar_usuarios_combo()

    def _actualizar_kpis(self, eventos: list):
        for w in self._kpi_frame.winfo_children():
            w.destroy()

        total = len(eventos)
        logins = sum(1 for e in eventos if e.get("accion") == "login"
                     and "Inicio" in (e.get("detalle") or ""))
        ventas = sum(1 for e in eventos if e.get("accion") == "venta")
        usuarios_uniq = len({e.get("usuario") for e in eventos if e.get("usuario") and e.get("usuario") != "—"})

        for etiqueta, valor in [
            ("Total eventos", str(total)),
            ("Inicios de sesión", str(logins)),
            ("Ventas registradas", str(ventas)),
            ("Usuarios activos", str(usuarios_uniq)),
        ]:
            card = tk.Frame(self._kpi_frame, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            card.pack(side="left", padx=(0, 12), ipadx=14, ipady=8)
            tk.Label(card, text=valor, font=FONT_KPI,
                     bg=COLORS["surface"], fg=COLORS["accent"]).pack()
            tk.Label(card, text=etiqueta, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack()
