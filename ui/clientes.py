"""
ui/clientes.py — El G POS
Gestión de clientes para facturación y clientes frecuentes.

Alta/edición en ventana emergente (ui.modal.ModalForm) para caber en pantallas
de baja resolución (1366x768): la tabla ocupa todo el ancho, se crea/edita con
"+ Nuevo" / "✎ Editar" y se ve el detalle (compras y crédito) con doble-clic.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_TITLE, FONT_KPI
from ui.modal import ModalForm

from modules.clientes import TIPOS_DOCUMENTO

REGIMENES = [
    "Régimen Común",
    "Régimen Simplificado",
    "Gran Contribuyente",
    "No Responsable",
    "Consumidor Final",
]
RESPONSABILIDADES = [
    "R-99-PN (No responsable)",
    "O-13 (Gran contribuyente)",
    "O-15 (Autorretenedor)",
    "O-23 (Agente retención IVA)",
    "ZZ (No aplica)",
]


# ── Helper: OptionMenu con estilo oscuro ──────────────────────────────────────

def _make_optmenu(parent, variable, options):
    """tk.OptionMenu con colores del tema oscuro."""
    m = tk.OptionMenu(parent, variable, *options)
    m.config(
        bg=COLORS["surface2"], fg=COLORS["text"],
        activebackground=COLORS["accent"], activeforeground=COLORS["text"],
        highlightthickness=1, highlightbackground=COLORS["border"],
        relief="flat", font=FONT_LABEL, anchor="w",
    )
    m["menu"].config(
        bg=COLORS["surface2"], fg=COLORS["text"],
        activebackground=COLORS["accent"], activeforeground=COLORS["text"],
        font=FONT_LABEL,
    )
    return m


class FrameClientes(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Clientes", "Registro de clientes y datos fiscales")
        self._cliente_sel_id = None
        self._modal = None
        self._build()

    def _build(self):
        # Barra de acciones
        acciones = tk.Frame(self, bg=COLORS["bg"])
        acciones.pack(fill="x", padx=32, pady=(0, 8))
        self._btn_primary(acciones, "+ Nuevo", self._modal_cliente).pack(
            side="right", padx=(8, 0), ipady=4, ipadx=12)
        self._btn_secondary(acciones, "✎ Editar", self._editar).pack(
            side="right", ipady=4, ipadx=12)

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(fill="both", expand=True)

        tk.Label(left, text="Doble clic para ver detalles, compras y crédito del cliente.",
                 font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 6))

        buscar_row = tk.Frame(left, bg=COLORS["bg"])
        buscar_row.pack(fill="x", pady=(0, 6))
        tk.Label(buscar_row, text="Buscar:", font=FONT_SMALL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left", padx=(0, 6))
        self._entry_buscar = self._input(buscar_row)
        self._entry_buscar.pack(side="left", fill="x", expand=True, ipady=5)
        self._entry_buscar.bind("<KeyRelease>", lambda e: self._filtrar_clientes())
        tk.Button(buscar_row, text="✕", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=lambda: (self._entry_buscar.delete(0, "end"),
                                   self._filtrar_clientes())).pack(side="left", padx=(4, 0))

        tabla_wrap = tk.Frame(left, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)

        cols = ("ID", "Nombre", "Documento", "Tipo", "Régimen", "Activo")
        self.tree = self._tabla(tabla_wrap, cols, alto=12)
        self.tree.column("ID",        width=40)
        self.tree.column("Nombre",    width=220, anchor="w")
        self.tree.column("Documento", width=130)
        self.tree.column("Tipo",      width=100)
        self.tree.column("Régimen",   width=150)
        self.tree.column("Activo",    width=60)
        self.tree.bind("<Double-1>", self._abrir_detalle)

        self._cargar_clientes()

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _filtrar_clientes(self):
        filtro = self._entry_buscar.get().strip().lower()
        self._cargar_clientes(filtro=filtro)

    def _cargar_clientes(self, filtro=""):
        from modules.clientes import listar_clientes
        self.tree.delete(*self.tree.get_children())
        for c in listar_clientes():
            if filtro and filtro not in f"{c['nombre']} {c['documento']} {c.get('telefono','')} {c.get('email','')}".lower():
                continue
            self.tree.insert("", "end", iid=str(c["id"]), values=(
                c["id"], c["nombre"], c["documento"], c["tipo_documento"],
                c.get("regimen") or "—",
                "Sí" if c["activo"] else "No",
            ))

    def _editar(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showinfo("Selecciona una fila",
                                "Elige un cliente de la tabla para editarlo.")
            return
        self._modal_cliente(int(sel))

    def _abrir_detalle(self, event=None):
        sel = self.tree.focus()
        if not sel:
            return
        DialogCliente(self, int(sel))

    # ── Modal alta/edición ──────────────────────────────────────────────────

    def _modal_cliente(self, cliente_id=None):
        editar = cliente_id is not None
        self._cliente_sel_id = cliente_id

        m = ModalForm(self, "Editar cliente" if editar else "Nuevo cliente",
                      ancho=420)
        self._modal = m
        body = m.body

        def field_label(texto):
            tk.Label(body, text=texto, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16, pady=(8, 0))

        def entry_field(attr):
            e = self._input(body)
            e.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
            setattr(self, attr, e)

        def select_field(attr, var, options):
            mm = _make_optmenu(body, var, options)
            mm.pack(fill="x", padx=16, pady=(2, 0), ipady=2)
            setattr(self, attr, var)

        field_label("Nombre *")
        entry_field("entry_nombre")

        self._var_tipo = tk.StringVar(value=TIPOS_DOCUMENTO[0])
        field_label("Tipo de documento *")
        select_field("combo_tipo", self._var_tipo, TIPOS_DOCUMENTO)

        field_label("Número de documento *")
        entry_field("entry_documento")

        field_label("Dirección")
        entry_field("entry_direccion")

        field_label("Teléfono")
        entry_field("entry_telefono")

        field_label("Email")
        entry_field("entry_email")

        self._var_regimen = tk.StringVar(value=REGIMENES[0])
        field_label("Régimen fiscal")
        select_field("combo_regimen", self._var_regimen, REGIMENES)

        self._var_resp = tk.StringVar(value=RESPONSABILIDADES[0])
        field_label("Responsabilidad fiscal")
        select_field("combo_responsabilidad", self._var_resp, RESPONSABILIDADES)

        field_label("Municipio")
        entry_field("entry_municipio")
        # separación al final del cuerpo
        tk.Frame(body, bg=COLORS["surface"], height=8).pack()

        self._btn_primary(
            m.footer, "Guardar" if editar else "Crear cliente",
            self._editar_cliente if editar else self._crear_cliente
        ).pack(side="right", ipady=6, ipadx=16)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        if editar:
            self._cargar_cliente_en_form(cliente_id)
        m.mostrar()

    def _cargar_cliente_en_form(self, cliente_id: int):
        from modules.clientes import obtener_cliente
        c = obtener_cliente(cliente_id)
        if not c:
            return
        self.entry_nombre.delete(0, "end")
        self.entry_nombre.insert(0, c["nombre"])
        self.combo_tipo.set(c.get("tipo_documento") or TIPOS_DOCUMENTO[0])
        self.entry_documento.delete(0, "end")
        self.entry_documento.insert(0, c.get("documento") or "")
        self.entry_direccion.delete(0, "end")
        self.entry_direccion.insert(0, c.get("direccion") or "")
        self.entry_telefono.delete(0, "end")
        self.entry_telefono.insert(0, c.get("telefono") or "")
        self.entry_email.delete(0, "end")
        self.entry_email.insert(0, c.get("email") or "")
        self.combo_regimen.set(c.get("regimen") or REGIMENES[0])
        self.combo_responsabilidad.set(
            c.get("responsabilidad_fiscal") or RESPONSABILIDADES[0])
        self.entry_municipio.delete(0, "end")
        self.entry_municipio.insert(0, c.get("municipio") or "")

    def _cerrar_modal(self):
        if self._modal is not None:
            try:
                self._modal.cerrar()
            except tk.TclError:
                pass
            self._modal = None

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _crear_cliente(self):
        from modules.clientes import crear_cliente
        nombre    = self.entry_nombre.get().strip()
        tipo_doc  = self.combo_tipo.get()
        documento = self.entry_documento.get().strip()

        if not nombre or not documento:
            messagebox.showwarning("Campos vacíos", "Completa nombre y número de documento.")
            return

        try:
            crear_cliente(
                nombre=nombre,
                tipo_documento=tipo_doc,
                documento=documento,
                direccion=self.entry_direccion.get().strip() or None,
                telefono=self.entry_telefono.get().strip() or None,
                email=self.entry_email.get().strip() or None,
                regimen=self.combo_regimen.get() or None,
                responsabilidad_fiscal=self.combo_responsabilidad.get() or None,
                municipio=self.entry_municipio.get().strip() or None,
            )
            messagebox.showinfo("Éxito", f"Cliente '{nombre}' creado correctamente.")
            self._cargar_clientes()
            self._cerrar_modal()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _editar_cliente(self):
        from modules.clientes import editar_cliente
        if not self._cliente_sel_id:
            return
        nombre    = self.entry_nombre.get().strip()
        tipo_doc  = self.combo_tipo.get()
        documento = self.entry_documento.get().strip()

        if not nombre or not documento:
            messagebox.showwarning("Campos vacíos", "Completa nombre y número de documento.")
            return

        try:
            editar_cliente(
                self._cliente_sel_id,
                nombre=nombre,
                tipo_documento=tipo_doc,
                documento=documento,
                direccion=self.entry_direccion.get().strip() or None,
                telefono=self.entry_telefono.get().strip() or None,
                email=self.entry_email.get().strip() or None,
                regimen=self.combo_regimen.get() or None,
                responsabilidad_fiscal=self.combo_responsabilidad.get() or None,
                municipio=self.entry_municipio.get().strip() or None,
            )
            messagebox.showinfo("Éxito", "Cliente actualizado correctamente.")
            self._cargar_clientes()
            self._cerrar_modal()
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO DE DETALLE DE CLIENTE
# ══════════════════════════════════════════════════════════════════════════════

class DialogCliente(tk.Toplevel):
    """
    Ventana de detalle de cliente: compras, crédito y abonos.
    Se abre con doble clic en la lista de clientes.
    """

    def __init__(self, parent, cliente_id: int):
        super().__init__(parent)
        self._cliente_id   = cliente_id
        self._cargo_sel_id = None   # ID de movimiento de crédito seleccionado
        self._cargo_sel_monto = 0.0

        from modules.clientes import obtener_cliente
        self._cliente = obtener_cliente(cliente_id)
        if not self._cliente:
            self.destroy()
            return

        self.title(f"Cliente — {self._cliente['nombre']}")
        self.configure(bg=COLORS["bg"])
        self.resizable(True, True)

        self._build()
        self._centrar()
        self.update_idletasks()
        self.grab_set()
        self.focus_force()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        c = self._cliente

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=COLORS["surface"],
                       highlightbackground=COLORS["border"], highlightthickness=1)
        hdr.pack(fill="x", padx=0, pady=0)
        tk.Frame(hdr, bg=COLORS["accent"], height=3).pack(fill="x")

        hdr_inner = tk.Frame(hdr, bg=COLORS["surface"])
        hdr_inner.pack(fill="x", padx=20, pady=12)

        tk.Label(hdr_inner, text=c["nombre"], font=("Segoe UI", 14, "bold"),
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w")

        info_parts = []
        if c.get("tipo_documento") and c.get("documento"):
            info_parts.append(f"{c['tipo_documento']} {c['documento']}")
        if c.get("telefono"):
            info_parts.append(f"Tel: {c['telefono']}")
        if c.get("email"):
            info_parts.append(c["email"])
        if c.get("municipio"):
            info_parts.append(c["municipio"])

        tk.Label(hdr_inner, text="  ·  ".join(info_parts) or "Sin datos de contacto",
                 font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")

        # ── Tab bar ───────────────────────────────────────────────────────────
        tab_bar = tk.Frame(self, bg=COLORS["bg"])
        tab_bar.pack(fill="x", padx=20, pady=(12, 0))

        self._tab_btns = {}
        for key, lbl in [("compras", "Compras"), ("credito", "Crédito")]:
            b = tk.Button(
                tab_bar, text=lbl, font=FONT_BOLD,
                bg=COLORS["surface"], fg=COLORS["text_muted"],
                activebackground=COLORS["surface2"], relief="flat", cursor="hand2",
                padx=18, pady=8,
                command=lambda k=key: self._cambiar_tab(k),
            )
            b.pack(side="left", padx=(0, 4))
            self._tab_btns[key] = b

        self._body = tk.Frame(self, bg=COLORS["bg"])
        self._body.pack(fill="both", expand=True, padx=20, pady=10)

        self._cambiar_tab("compras")

    def _cambiar_tab(self, key: str):
        for k, b in self._tab_btns.items():
            b.config(
                bg=COLORS["accent"] if k == key else COLORS["surface"],
                fg=COLORS["text"]   if k == key else COLORS["text_muted"],
            )
        for w in self._body.winfo_children():
            w.destroy()
        if key == "compras":
            self._tab_compras()
        else:
            self._tab_credito()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB COMPRAS
    # ══════════════════════════════════════════════════════════════════════════

    def _tab_compras(self):
        frame = tk.Frame(self._body, bg=COLORS["bg"])
        frame.pack(fill="both", expand=True)

        # KPIs rápidos de compras
        from modules.ventas import listar_ventas
        from modules.caja import formatear_pesos
        ventas = listar_ventas(cliente_id=self._cliente_id, limite=200)

        kpi_row = tk.Frame(frame, bg=COLORS["bg"])
        kpi_row.pack(fill="x", pady=(0, 10))
        total_gastado = sum(v["total"] for v in ventas)
        for label, valor in [
            ("Compras totales", str(len(ventas))),
            ("Total gastado",   formatear_pesos(total_gastado)),
        ]:
            card = tk.Frame(kpi_row, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 12), ipadx=14, ipady=8)
            tk.Label(card, text=valor, font=FONT_KPI,
                     bg=COLORS["surface"], fg=COLORS["accent"]).pack()
            tk.Label(card, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack()

        # Tabla de ventas
        cols_v = ("id", "fecha", "total", "descuento", "metodo", "vendedor")
        self.tree_ventas = self._make_tree(frame, cols_v, alto=10)
        self.tree_ventas.heading("id",        text="#")
        self.tree_ventas.heading("fecha",     text="Fecha")
        self.tree_ventas.heading("total",     text="Total")
        self.tree_ventas.heading("descuento", text="Descuento")
        self.tree_ventas.heading("metodo",    text="Método")
        self.tree_ventas.heading("vendedor",  text="Vendedor")
        self.tree_ventas.column("id",        width=45,  anchor="center")
        self.tree_ventas.column("fecha",     width=145, anchor="w")
        self.tree_ventas.column("total",     width=100, anchor="e")
        self.tree_ventas.column("descuento", width=90,  anchor="e")
        self.tree_ventas.column("metodo",    width=100, anchor="center")
        self.tree_ventas.column("vendedor",  width=100, anchor="w")
        self.tree_ventas.tag_configure("credito", foreground=COLORS["warning"])
        self.tree_ventas.bind("<<TreeviewSelect>>", self._al_sel_venta)

        for v in ventas:
            tag = ("credito",) if v.get("metodo_pago") == "credito" else ()
            desc = formatear_pesos(v["descuento"]) if v.get("descuento") else "—"
            self.tree_ventas.insert("", "end", iid=str(v["id"]), values=(
                v["id"], v["fecha"],
                formatear_pesos(v["total"]),
                desc,
                v.get("metodo_pago", "—"),
                v.get("vendedor", "—"),
            ), tags=tag)

        # Detalle de la venta seleccionada
        tk.Label(frame, text="Detalle de la venta seleccionada",
                 font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text"]).pack(
                     anchor="w", pady=(10, 4))

        cols_d = ("item", "cant", "precio", "subtotal")
        self.tree_detalle = self._make_tree(frame, cols_d, alto=6)
        self.tree_detalle.heading("item",     text="Producto / Combo")
        self.tree_detalle.heading("cant",     text="Cant.")
        self.tree_detalle.heading("precio",   text="Precio unit.")
        self.tree_detalle.heading("subtotal", text="Subtotal")
        self.tree_detalle.column("item",     width=280, anchor="w")
        self.tree_detalle.column("cant",     width=60,  anchor="center")
        self.tree_detalle.column("precio",   width=110, anchor="e")
        self.tree_detalle.column("subtotal", width=110, anchor="e")

    def _al_sel_venta(self, event=None):
        from modules.ventas import obtener_venta
        from modules.caja import formatear_pesos
        sel = self.tree_ventas.focus()
        if not sel:
            return
        venta = obtener_venta(int(sel))
        if not venta:
            return
        self.tree_detalle.delete(*self.tree_detalle.get_children())
        for d in venta.get("detalle", []):
            self.tree_detalle.insert("", "end", values=(
                d.get("nombre_item", "—"),
                d["cantidad"],
                formatear_pesos(d["precio_unit"]),
                formatear_pesos(d["subtotal"]),
            ))

    # ══════════════════════════════════════════════════════════════════════════
    # TAB CRÉDITO
    # ══════════════════════════════════════════════════════════════════════════

    def _tab_credito(self):
        from modules.creditos import get_info_credito, migrar
        from modules.caja import formatear_pesos
        from modules.validaciones import aplicar_validacion
        migrar()
        info = get_info_credito(self._cliente_id)

        frame = tk.Frame(self._body, bg=COLORS["bg"])
        frame.pack(fill="both", expand=True)

        # ── KPIs ──────────────────────────────────────────────────────────────
        kpi_row = tk.Frame(frame, bg=COLORS["bg"])
        kpi_row.pack(fill="x", pady=(0, 8))
        for label, valor, color in [
            ("Límite",        formatear_pesos(info["limite"]),     COLORS["text"]),
            ("Deuda total",   formatear_pesos(info["saldo"]),      COLORS["danger"]  if info["saldo"] > 0 else COLORS["text_muted"]),
            ("Disponible",    formatear_pesos(info["disponible"]), COLORS["success"] if info["disponible"] > 0 else COLORS["text_muted"]),
            ("Días/compra",   f"{info['dias_credito']} días",      COLORS["text_muted"]),
        ]:
            card = tk.Frame(kpi_row, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 12), ipadx=14, ipady=8)
            tk.Label(card, text=valor, font=FONT_KPI,
                     bg=COLORS["surface"], fg=color).pack()
            tk.Label(card, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack()

        # ── Configuración inline ───────────────────────────────────────────────
        conf_row = tk.Frame(frame, bg=COLORS["bg"])
        conf_row.pack(fill="x", pady=(0, 10))

        tk.Label(conf_row, text="Límite ($)", font=FONT_SMALL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_limite = self._make_input(conf_row, width=10)
        self.entry_limite.insert(0, str(int(info["limite"])))
        self.entry_limite.pack(side="left", padx=(4, 12), ipady=4)
        aplicar_validacion(self.entry_limite, "monto")

        tk.Label(conf_row, text="Días por compra", font=FONT_SMALL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_dias = self._make_input(conf_row, width=5)
        self.entry_dias.insert(0, str(info["dias_credito"]))
        self.entry_dias.pack(side="left", padx=(4, 12), ipady=4)
        aplicar_validacion(self.entry_dias, "entero")

        tk.Button(
            conf_row, text="Guardar configuración", font=FONT_SMALL,
            bg=COLORS["accent"], fg=COLORS["on_accent"],
            activebackground=COLORS["accent"], relief="flat", cursor="hand2",
            command=self._guardar_limite, pady=5, padx=10,
        ).pack(side="left")

        # ── Cuerpo: izq (tablas) + der (panel pago) ───────────────────────────
        body = tk.Frame(frame, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        # — Compras pendientes —
        hdr_pend = tk.Frame(left, bg=COLORS["bg"])
        hdr_pend.pack(fill="x", pady=(0, 4))
        tk.Label(hdr_pend, text="Compras a crédito pendientes", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(side="left")
        tk.Label(hdr_pend, text="  · clic para abonar a esa compra",
                 font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")

        cols_c = ("id", "fecha", "venta", "total", "pagado", "pendiente", "vence", "estado")
        self.tree_cargos = self._make_tree(left, cols_c, alto=9, expand=True)
        self.tree_cargos.heading("id",        text="#")
        self.tree_cargos.heading("fecha",     text="Fecha compra")
        self.tree_cargos.heading("venta",     text="Origen")
        self.tree_cargos.heading("total",     text="Total")
        self.tree_cargos.heading("pagado",    text="Pagado")
        self.tree_cargos.heading("pendiente", text="Pendiente")
        self.tree_cargos.heading("vence",     text="Vence")
        self.tree_cargos.heading("estado",    text="Estado")
        self.tree_cargos.column("id",        width=35,  anchor="center")
        self.tree_cargos.column("fecha",     width=128, anchor="w")
        self.tree_cargos.column("venta",     width=95,  anchor="center")
        self.tree_cargos.column("total",     width=92,  anchor="e")
        self.tree_cargos.column("pagado",    width=88,  anchor="e")
        self.tree_cargos.column("pendiente", width=92,  anchor="e")
        self.tree_cargos.column("vence",     width=88,  anchor="center")
        self.tree_cargos.column("estado",    width=72,  anchor="center")
        self.tree_cargos.tag_configure("vencido", foreground=COLORS["danger"])
        self.tree_cargos.tag_configure("al_dia",  foreground=COLORS["success"])
        self.tree_cargos.bind("<<TreeviewSelect>>", self._al_sel_cargo)

        # — Historial de pagos —
        tk.Frame(left, bg=COLORS["border"], height=1).pack(fill="x", pady=(8, 4))
        tk.Label(left, text="Historial de pagos registrados", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 4))

        cols_a = ("fecha", "monto", "metodo", "compra_ref", "notas")
        self.tree_abonos = self._make_tree(left, cols_a, alto=5, expand=False)
        self.tree_abonos.heading("fecha",      text="Fecha")
        self.tree_abonos.heading("monto",      text="Monto")
        self.tree_abonos.heading("metodo",     text="Método")
        self.tree_abonos.heading("compra_ref", text="Compra #")
        self.tree_abonos.heading("notas",      text="Notas")
        self.tree_abonos.column("fecha",      width=128, anchor="w")
        self.tree_abonos.column("monto",      width=92,  anchor="e")
        self.tree_abonos.column("metodo",     width=90,  anchor="center")
        self.tree_abonos.column("compra_ref", width=72,  anchor="center")
        self.tree_abonos.column("notas",      width=230, anchor="w")
        self.tree_abonos.tag_configure("abono", foreground=COLORS["success"])

        # ── Panel derecho: formulario de pago ─────────────────────────────────
        right = tk.Frame(body, bg=COLORS["surface"],
                         highlightbackground=COLORS["border"], highlightthickness=1,
                         width=268)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        rf = tk.Frame(right, bg=COLORS["surface"])
        rf.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(rf, text="Registrar pago", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))

        self.lbl_cargo_sel = tk.Label(
            rf,
            text="Sin compra seleccionada\n(abono general a la deuda total)",
            font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text_muted"],
            wraplength=232, justify="left",
        )
        self.lbl_cargo_sel.pack(anchor="w", pady=(0, 10))

        tk.Label(rf, text="Monto ($)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self.entry_abono = self._make_input(rf)
        self.entry_abono.pack(fill="x", pady=(2, 10), ipady=6)
        aplicar_validacion(self.entry_abono, "monto")

        tk.Label(rf, text="Método de pago", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self._var_metodo = tk.StringVar(value="efectivo")
        ttk.Combobox(
            rf, values=["efectivo", "transferencia", "nequi", "daviplata", "tarjeta"],
            textvariable=self._var_metodo, state="readonly", font=FONT_SMALL,
        ).pack(fill="x", pady=(2, 10), ipady=3)

        tk.Label(rf, text="Notas", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self.entry_notas = self._make_input(rf)
        self.entry_notas.pack(fill="x", pady=(2, 12), ipady=6)

        tk.Button(
            rf, text="✓ Registrar pago", font=FONT_BOLD,
            bg=COLORS["accent"], fg=COLORS["on_accent"],
            activebackground=COLORS["accent"], relief="flat", cursor="hand2",
            command=self._registrar_abono, pady=10,
        ).pack(fill="x")

        tk.Frame(rf, bg=COLORS["border"], height=1).pack(fill="x", pady=10)

        tk.Button(
            rf, text="Pagar toda la deuda", font=FONT_SMALL,
            bg=COLORS["surface2"], fg=COLORS["warning"],
            activebackground=COLORS["border"], relief="flat", cursor="hand2",
            command=self._pagar_todo, pady=8,
        ).pack(fill="x")

        tk.Frame(rf, bg=COLORS["border"], height=1).pack(fill="x", pady=10)

        tk.Button(
            rf, text="Quitar selección", font=FONT_SMALL,
            bg=COLORS["surface2"], fg=COLORS["text_muted"],
            activebackground=COLORS["border"], relief="flat", cursor="hand2",
            command=self._limpiar_sel_cargo, pady=6,
        ).pack(fill="x")

        self._cargo_sel_id    = None
        self._cargo_sel_monto = 0.0
        self._cargar_cargos()
        self._cargar_abonos()

    def _cargar_cargos(self):
        """Recarga la tabla de compras pendientes."""
        from modules.creditos import get_cargos_pendientes
        from modules.caja import formatear_pesos
        self.tree_cargos.delete(*self.tree_cargos.get_children())
        for c in get_cargos_pendientes(self._cliente_id):
            venc   = c["fecha_vencimiento"][:10] if c.get("fecha_vencimiento") else "—"
            estado = "VENCIDA" if c["vencido"] else "Al día"
            tag    = "vencido" if c["vencido"] else "al_dia"
            # Distinguir el origen: torneo (por sus notas) vs venta normal.
            if "torneo" in (c.get("notas") or "").lower():
                origen = "🏆 Torneo"
            elif c.get("venta_id"):
                origen = f"Venta #{c['venta_id']}"
            else:
                origen = "—"
            self.tree_cargos.insert("", "end", iid=str(c["id"]), values=(
                c["id"],
                c["fecha"][:16],
                origen,
                formatear_pesos(c["monto"]),
                formatear_pesos(c["pagado"]),
                formatear_pesos(c["pendiente"]),
                venc,
                estado,
            ), tags=(tag,))

    def _cargar_abonos(self):
        """Recarga la tabla de historial de pagos."""
        from modules.creditos import historial_abonos
        from modules.caja import formatear_pesos
        self.tree_abonos.delete(*self.tree_abonos.get_children())
        for a in historial_abonos(self._cliente_id):
            self.tree_abonos.insert("", "end", values=(
                a["fecha"][:16],
                formatear_pesos(a["monto"]),
                a.get("metodo_pago") or "—",
                f"#{a['cargo_id']}" if a.get("cargo_id") else "General",
                a.get("notas") or "",
            ), tags=("abono",))

    def _al_sel_cargo(self, event=None):
        """Seleccionar una compra pendiente rellena el formulario de pago."""
        from modules.creditos import get_saldo_cargo
        from modules.caja import formatear_pesos
        sel = self.tree_cargos.focus()
        if not sel:
            return
        cargo_id  = int(sel)
        pendiente = get_saldo_cargo(cargo_id)
        vence = self.tree_cargos.item(sel, "values")[6]
        self._cargo_sel_id    = cargo_id
        self._cargo_sel_monto = pendiente
        self.lbl_cargo_sel.config(
            text=f"Compra #{cargo_id}  ·  Vence: {vence}\nPendiente: {formatear_pesos(pendiente)}",
            fg=COLORS["warning"],
        )
        self.entry_abono.delete(0, "end")
        self.entry_abono.insert(0, str(int(pendiente)))
        self.entry_notas.delete(0, "end")
        self.entry_notas.insert(0, f"Pago compra #{cargo_id}")

    def _limpiar_sel_cargo(self):
        self._cargo_sel_id    = None
        self._cargo_sel_monto = 0.0
        if hasattr(self, "lbl_cargo_sel"):
            self.lbl_cargo_sel.config(
                text="Sin compra seleccionada\n(abono general a la deuda total)",
                fg=COLORS["text_muted"],
            )
        if hasattr(self, "entry_abono"):
            self.entry_abono.delete(0, "end")
        if hasattr(self, "entry_notas"):
            self.entry_notas.delete(0, "end")
        if hasattr(self, "tree_cargos"):
            for item in self.tree_cargos.selection():
                self.tree_cargos.selection_remove(item)

    def _guardar_limite(self):
        from modules.creditos import set_limite_credito
        from modules.validaciones import leer_entero
        try:
            limite = leer_entero(self.entry_limite)
            dias   = leer_entero(self.entry_dias, default=30)
            set_limite_credito(self._cliente_id, limite, dias)
            messagebox.showinfo("Guardado", "Configuración de crédito actualizada.", parent=self)
            self._cambiar_tab("credito")
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _registrar_abono(self):
        from modules.creditos import registrar_abono
        from modules.caja import get_sesion_activa
        from modules.validaciones import leer_entero
        monto = leer_entero(self.entry_abono)
        if monto <= 0:
            messagebox.showwarning("Monto inválido", "Ingresa un monto mayor a cero.", parent=self)
            return
        metodo = self._var_metodo.get()
        notas  = self.entry_notas.get().strip() or None
        sesion = get_sesion_activa()
        try:
            registrar_abono(
                self._cliente_id, monto,
                cargo_id=self._cargo_sel_id,
                metodo_pago=metodo,
                sesion_id=sesion["id"] if sesion else None,
                notas=notas,
            )
            tipo_str = f"a la compra #{self._cargo_sel_id}" if self._cargo_sel_id else "general"
            messagebox.showinfo(
                "Pago registrado",
                f"Pago {tipo_str} de ${monto:,.0f} registrado.",
                parent=self,
            )
            self._limpiar_sel_cargo()
            self._cambiar_tab("credito")
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _pagar_todo(self):
        from modules.creditos import get_saldo, registrar_abono_masivo
        from modules.caja import get_sesion_activa, formatear_pesos
        saldo = get_saldo(self._cliente_id)
        if saldo <= 0:
            messagebox.showinfo("Sin deuda", "Este cliente no tiene saldo pendiente.", parent=self)
            return
        if not messagebox.askyesno(
            "Confirmar pago total",
            f"¿Registrar el pago de {formatear_pesos(saldo)} para saldar "
            f"toda la deuda del cliente?",
            parent=self,
        ):
            return
        metodo = self._var_metodo.get()
        sesion = get_sesion_activa()
        try:
            registrar_abono_masivo(
                self._cliente_id, saldo,
                metodo_pago=metodo,
                sesion_id=sesion["id"] if sesion else None,
            )
            messagebox.showinfo(
                "Pagado", f"Deuda total de {formatear_pesos(saldo)} saldada.", parent=self
            )
            self._cambiar_tab("credito")
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=self)

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _make_tree(self, parent, cols, alto=10, expand=True):
        """Treeview con estilo consistente para el diálogo."""
        wrap = tk.Frame(parent, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=expand)
        style = ttk.Style()
        style.configure("Dlg.Treeview",
            background=COLORS["surface"], fieldbackground=COLORS["surface"],
            foreground=COLORS["text"], rowheight=26,
            borderwidth=0, font=FONT_SMALL,
        )
        style.configure("Dlg.Treeview.Heading",
            background=COLORS["surface2"], foreground=COLORS["text_muted"],
            font=FONT_SMALL, relief="flat",
        )
        style.map("Dlg.Treeview",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", COLORS["text"])],
        )
        tree = ttk.Treeview(wrap, columns=cols, show="headings",
                             height=alto, style="Dlg.Treeview")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        return tree

    def _make_input(self, parent, width=None):
        kw = {"width": width} if width else {}
        return tk.Entry(
            parent, font=FONT_LABEL,
            bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            **kw,
        )

    def _centrar(self):
        self.update_idletasks()
        # Ajustar a la pantalla (baja resolución): no exceder el alto disponible.
        w = min(980, self.winfo_screenwidth() - 40)
        h = min(700, self.winfo_screenheight() - 60)
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{max(y, 0)}")
