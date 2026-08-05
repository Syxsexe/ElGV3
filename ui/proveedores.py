"""
ui/proveedores.py — El G POS
Gestión de proveedores y pedidos de stock.

Formularios en ventanas emergentes (ui.modal.ModalForm) para caber en pantallas
de baja resolución (1366x768): la tabla ocupa todo el ancho y se crea/edita con
"+ Nuevo" / "✎ Editar" / doble-clic.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_KPI
from ui.modal import ModalForm


class FrameProveedores(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Proveedores", "Gestión de proveedores y pedidos de stock")
        self._proveedor_sel = None
        self._pedido_sel    = None
        self._pedido_items  = []   # ítems del pedido en construcción
        self._modo_prov     = "nuevo"
        self._modal         = None
        self._build()

    def _build(self):
        # Tabs: Proveedores | Pedidos + acciones
        tab_frame = tk.Frame(self, bg=COLORS["bg"])
        tab_frame.pack(fill="x", padx=32, pady=(0, 12))
        self._tab = tk.StringVar(value="proveedores")
        for t, v in [("Proveedores", "proveedores"), ("Pedidos", "pedidos")]:
            tk.Radiobutton(
                tab_frame, text=t, variable=self._tab, value=v,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._cambiar_tab, padx=14, pady=6,
            ).pack(side="left", padx=(0, 4))

        self._btn_primary(tab_frame, "+ Nuevo", self._nuevo).pack(
            side="right", padx=(0, 8), ipady=4, ipadx=12)
        self._btn_secondary(tab_frame, "✎ Editar / Ver", self._editar).pack(
            side="right", padx=(0, 8), ipady=4, ipadx=12)

        # Contenedor principal (tabla a todo el ancho)
        self._main = tk.Frame(self, bg=COLORS["bg"])
        self._main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        buscar_row = tk.Frame(self._main, bg=COLORS["bg"])
        buscar_row.pack(fill="x", pady=(0, 6))
        tk.Label(buscar_row, text="Buscar:", font=FONT_SMALL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left", padx=(0, 6))
        self._entry_buscar = self._input(buscar_row)
        self._entry_buscar.pack(side="left", fill="x", expand=True, ipady=5)
        self._entry_buscar.bind("<KeyRelease>", lambda e: self._filtrar())
        tk.Button(buscar_row, text="✕", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=lambda: (self._entry_buscar.delete(0, "end"),
                                   self._filtrar())).pack(side="left", padx=(4, 0))

        tabla_wrap = tk.Frame(self._main, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)

        cols = ("id", "nombre", "contacto", "telefono", "estado")
        self.tree = self._tabla(tabla_wrap, cols, alto=12)
        self._configurar_cols_proveedores()
        self.tree.bind("<Double-1>", lambda e: self._editar())

        self._cargar_proveedores()

    # ── Navegación entre tabs ─────────────────────────────────────────────────
    def _filtrar(self):
        filtro = self._entry_buscar.get().strip().lower()
        if self._tab.get() == "proveedores":
            self._cargar_proveedores(filtro=filtro)
        else:
            self._cargar_pedidos(filtro=filtro)

    def _cambiar_tab(self):
        self._entry_buscar.delete(0, "end")
        self._proveedor_sel = None
        self._pedido_sel    = None
        if self._tab.get() == "proveedores":
            self._configurar_cols_proveedores()
            self._cargar_proveedores()
        else:
            self._configurar_cols_pedidos()
            self._cargar_pedidos()

    def _nuevo(self):
        if self._tab.get() == "proveedores":
            self._modal_proveedor()
        else:
            self._modal_pedido()

    def _editar(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showinfo("Selecciona una fila",
                                "Elige una fila de la tabla (o haz doble-clic).")
            return
        if self._tab.get() == "proveedores":
            self._modal_proveedor(int(sel))
        else:
            self._modal_pedido_detalle(int(sel))

    def _cerrar_modal(self):
        if self._modal is not None:
            try:
                self._modal.cerrar()
            except tk.TclError:
                pass
            self._modal = None

    # ══════════════════════════════════════════════════════════
    # TAB PROVEEDORES
    # ══════════════════════════════════════════════════════════

    def _configurar_cols_proveedores(self):
        cols = ("id", "nombre", "contacto", "telefono", "estado")
        self.tree["columns"] = cols
        self.tree.heading("id",       text="#")
        self.tree.heading("nombre",   text="Nombre")
        self.tree.heading("contacto", text="Contacto")
        self.tree.heading("telefono", text="Telefono")
        self.tree.heading("estado",   text="Estado")
        self.tree.column("id",       width=40)
        self.tree.column("nombre",   width=220, anchor="w")
        self.tree.column("contacto", width=180, anchor="w")
        self.tree.column("telefono", width=140)
        self.tree.column("estado",   width=90)

    def _cargar_proveedores(self, filtro=""):
        from modules.proveedores import listar_proveedores
        self.tree.delete(*self.tree.get_children())
        for p in listar_proveedores(solo_activos=False):
            if filtro and filtro not in f"{p['nombre']} {p.get('contacto','')} {p.get('telefono','')} {p.get('email','')}".lower():
                continue
            estado = "Activo" if p["activo"] else "Inactivo"
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["nombre"],
                p["contacto"] or "—",
                p["telefono"] or "—",
                estado
            ))

    def _modal_proveedor(self, proveedor_id=None):
        editar = proveedor_id is not None
        self._proveedor_sel = proveedor_id
        self._modo_prov = "editar" if editar else "nuevo"

        m = ModalForm(self, "Editar proveedor" if editar else "Nuevo proveedor",
                      ancho=420)
        self._modal = m
        body = m.body

        campos = [
            ("Nombre *",   "_p_nombre"),
            ("Contacto",   "_p_contacto"),
            ("Telefono",   "_p_telefono"),
            ("Email",      "_p_email"),
        ]
        for label, attr in campos:
            tk.Label(body, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16, pady=(8, 0))
            e = self._input(body)
            e.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
            setattr(self, attr, e)

        self._btn_primary(m.footer, "Guardar",
                          self._guardar_proveedor).pack(
                              side="right", ipady=6, ipadx=16)
        if editar:
            self._btn_danger(m.footer, "Activar / Desactivar",
                             self._desactivar_proveedor).pack(
                                 side="right", padx=(0, 8), ipady=6, ipadx=10)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        if editar:
            self._cargar_proveedor_en_form(proveedor_id)
        m.mostrar()

    def _cargar_proveedor_en_form(self, proveedor_id: int):
        from modules.proveedores import obtener_proveedor
        p = obtener_proveedor(proveedor_id)
        if not p:
            return
        for entry, valor in [
            (self._p_nombre,   p["nombre"]),
            (self._p_contacto, p["contacto"] or ""),
            (self._p_telefono, p["telefono"] or ""),
            (self._p_email,    p["email"]    or ""),
        ]:
            entry.delete(0, "end")
            entry.insert(0, valor)

    def _guardar_proveedor(self):
        from modules.proveedores import crear_proveedor, editar_proveedor
        from modules.validaciones import leer_texto
        nombre   = leer_texto(self._p_nombre)
        contacto = leer_texto(self._p_contacto) or None
        telefono = leer_texto(self._p_telefono) or None
        email    = leer_texto(self._p_email)    or None

        if not nombre:
            messagebox.showwarning("Campo vacio", "El nombre es obligatorio.")
            return
        try:
            if self._modo_prov == "nuevo":
                pid = crear_proveedor(nombre, contacto, telefono, email)
                messagebox.showinfo("Creado", f"Proveedor creado (ID {pid}).")
            else:
                editar_proveedor(self._proveedor_sel,
                                  nombre=nombre, contacto=contacto,
                                  telefono=telefono, email=email)
                messagebox.showinfo("Guardado", "Proveedor actualizado.")
            self._cargar_proveedores()
            self._cerrar_modal()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _desactivar_proveedor(self):
        if not self._proveedor_sel:
            messagebox.showwarning("Sin seleccion", "Selecciona un proveedor.")
            return
        from modules.proveedores import obtener_proveedor, editar_proveedor
        p = obtener_proveedor(self._proveedor_sel)
        if not p:
            return
        nuevo = 0 if p["activo"] else 1
        accion = "desactivar" if nuevo == 0 else "activar"
        if not messagebox.askyesno("Confirmar", f"Deseas {accion} a '{p['nombre']}'?"):
            return
        editar_proveedor(self._proveedor_sel, activo=nuevo)
        self._cargar_proveedores()
        self._cerrar_modal()

    # ══════════════════════════════════════════════════════════
    # TAB PEDIDOS
    # ══════════════════════════════════════════════════════════

    def _configurar_cols_pedidos(self):
        cols = ("pid", "fecha", "proveedor", "items", "total", "estado")
        self.tree["columns"] = cols
        textos = {"pid": "#", "fecha": "Fecha", "proveedor": "Proveedor",
                  "items": "Items", "total": "Total", "estado": "Estado"}
        anchos = {"pid": 40, "fecha": 150, "proveedor": 220,
                  "items": 70, "total": 130, "estado": 100}
        for col in cols:
            self.tree.heading(col, text=textos[col])
            anchor = "w" if col == "proveedor" else "center"
            self.tree.column(col, width=anchos[col], anchor=anchor)

    def _cargar_pedidos(self, filtro=""):
        from modules.proveedores import listar_pedidos
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for p in listar_pedidos():
            if filtro and filtro not in f"{p['proveedor_nombre']} {p['estado']}".lower():
                continue
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"],
                p["fecha"][:16],
                p["proveedor_nombre"],
                p["num_items"],
                formatear_pesos(p["total"] or 0),
                p["estado"].capitalize()
            ))

    def _modal_pedido(self):
        self._pedido_items = []
        m = ModalForm(self, "Nuevo pedido", ancho=460)
        self._modal = m
        body = m.body

        # Proveedor
        from modules.proveedores import listar_proveedores
        provs = listar_proveedores()
        self._provs_map = {p["nombre"]: p["id"] for p in provs}
        tk.Label(body, text="Proveedor", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(8, 0))
        self._combo_prov = ttk.Combobox(
            body, values=list(self._provs_map.keys()),
            font=FONT_LABEL, state="readonly"
        )
        if provs:
            self._combo_prov.set(provs[0]["nombre"])
        self._combo_prov.pack(fill="x", padx=16, pady=(2, 10))

        # Tipo de ítem
        tk.Label(body, text="Tipo de item", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._tipo_item = tk.StringVar(value="producto")
        tipo_frame = tk.Frame(body, bg=COLORS["surface"])
        tipo_frame.pack(fill="x", padx=16, pady=(2, 6))
        for t, v in [("Producto", "producto"), ("Insumo", "insumo")]:
            tk.Radiobutton(
                tipo_frame, text=t, variable=self._tipo_item, value=v,
                font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["surface"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._actualizar_lista_items,
                padx=10, pady=4,
            ).pack(side="left", padx=(0, 4))

        # Buscar ítem
        tk.Label(body, text="Buscar", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._entry_buscar_item = self._input(body)
        self._entry_buscar_item.pack(fill="x", padx=16, pady=(2, 4), ipady=5)
        self._entry_buscar_item.bind("<KeyRelease>", self._actualizar_lista_items)

        lst_wrap = tk.Frame(body, bg=COLORS["surface"])
        lst_wrap.pack(fill="x", padx=16, pady=(0, 6))
        self._lst_items_pedido = tk.Listbox(
            lst_wrap, font=FONT_SMALL, height=4,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self._lst_items_pedido.pack(fill="x")

        # Cantidad y precio
        from modules.validaciones import aplicar_validacion
        grid = tk.Frame(body, bg=COLORS["surface"])
        grid.pack(fill="x", padx=16, pady=(0, 6))

        tk.Label(grid, text="Cantidad:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).grid(
                     row=0, column=0, sticky="w", pady=2)
        self._entry_cant_item = self._input(grid, width=8)
        self._entry_cant_item.insert(0, "1")
        self._entry_cant_item.grid(row=0, column=1, padx=(6, 0), ipady=4)
        aplicar_validacion(self._entry_cant_item, "decimal")

        self._lbl_precio_item = tk.Label(grid, text="Precio unit ($):", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"])
        self._lbl_precio_item.grid(row=1, column=0, sticky="w", pady=2)
        self._entry_precio_item = self._input(grid, width=8)
        self._entry_precio_item.insert(0, "0")
        self._entry_precio_item.grid(row=1, column=1, padx=(6, 0), ipady=4)
        aplicar_validacion(self._entry_precio_item, "monto")

        # Pista: para insumos se ingresa el total pagado por la presentación.
        self._lbl_hint_precio = tk.Label(
            body, text="", font=("Segoe UI", 8), bg=COLORS["surface"],
            fg=COLORS["text_dim"], anchor="w", wraplength=380, justify="left")
        self._lbl_hint_precio.pack(anchor="w", padx=16, pady=(0, 4))

        self._btn_primary(body, "+ Agregar al pedido",
                          self._agregar_item_pedido).pack(fill="x", padx=16, ipady=6)

        tk.Frame(body, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        # Tabla de ítems del pedido
        tk.Label(body, text="Contenido del pedido", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(0, 6))
        self._frame_tabla_pedido = tk.Frame(body, bg=COLORS["surface"])
        self._frame_tabla_pedido.pack(fill="x", padx=16)

        self._lbl_total_pedido = tk.Label(
            body, text="Total: $0", font=FONT_BOLD,
            bg=COLORS["surface"], fg=COLORS["accent"]
        )
        self._lbl_total_pedido.pack(anchor="w", padx=16, pady=(6, 0))

        # Notas
        tk.Label(body, text="Notas (opcional)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(10, 0))
        self._txt_notas = tk.Text(body, height=2, font=FONT_SMALL,
                                   bg=COLORS["surface2"], fg=COLORS["text"],
                                   insertbackground=COLORS["accent"],
                                   relief="flat", highlightthickness=1,
                                   highlightbackground=COLORS["border"])
        self._txt_notas.pack(fill="x", padx=16, pady=(2, 12))

        self._btn_primary(m.footer, "Crear pedido",
                          self._crear_pedido).pack(
                              side="right", ipady=6, ipadx=16)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        self._actualizar_lista_items()
        self._refrescar_tabla_pedido()
        m.mostrar()

    def _actualizar_lista_items(self, event=None):
        """Actualiza el listbox según el tipo seleccionado (producto/insumo)."""
        from modules.inventario import listar_productos, listar_insumos
        texto = self._entry_buscar_item.get().strip().lower()
        self._lst_items_pedido.delete(0, "end")
        self._items_pedido_data = []

        # Etiqueta del precio según el tipo (por presentación para insumos).
        if hasattr(self, "_lbl_precio_item"):
            if self._tipo_item.get() == "insumo":
                self._lbl_precio_item.config(text="Total pagado ($):")
                self._lbl_hint_precio.config(
                    text="Insumo de cocina: ingresa cuánto compraste (cantidad) y el "
                         "total pagado. El costo por unidad se calcula solo y define "
                         "el costo de los platos.")
            else:
                self._lbl_precio_item.config(text="Precio unit ($):")
                self._lbl_hint_precio.config(text="")

        if self._tipo_item.get() == "producto":
            items = listar_productos(tipo="tienda")
            for p in items:
                if not texto or texto in p["nombre"].lower():
                    self._lst_items_pedido.insert(
                        "end", f"{p['nombre']}  [{p['categoria_nombre']}]")
                    self._items_pedido_data.append(
                        {"producto_id": p["id"], "nombre": p["nombre"]})
        else:
            items = listar_insumos()
            for i in items:
                if not texto or texto in i["nombre"].lower():
                    self._lst_items_pedido.insert(
                        "end", f"{i['nombre']}  ({i['unidad']})")
                    self._items_pedido_data.append(
                        {"insumo_id": i["id"], "nombre": i["nombre"],
                         "unidad": i["unidad"]})

    def _agregar_item_pedido(self):
        from modules.validaciones import leer_decimal, leer_entero
        sel = self._lst_items_pedido.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona un item de la lista.")
            return
        item_data = self._items_pedido_data[sel[0]]
        cantidad  = leer_decimal(self._entry_cant_item, default=1.0)
        precio    = leer_entero(self._entry_precio_item, default=0)
        if cantidad <= 0:
            messagebox.showwarning("Cantidad invalida", "La cantidad debe ser mayor a 0.")
            return

        # Para insumos el precio ingresado es el TOTAL pagado por la presentación:
        # el costo por unidad = total ÷ cantidad. Para productos es precio unitario.
        es_insumo = "insumo_id" in item_data
        if es_insumo:
            precio_unit = round(precio / cantidad, 4) if cantidad else 0
        else:
            precio_unit = precio

        # Si ya existe, actualiza
        clave = "producto_id" if "producto_id" in item_data else "insumo_id"
        for linea in self._pedido_items:
            if linea.get(clave) == item_data.get(clave):
                linea["cantidad"]   = cantidad
                linea["precio_unit"] = precio_unit
                self._refrescar_tabla_pedido()
                return

        self._pedido_items.append({
            **item_data,
            "cantidad":    cantidad,
            "precio_unit": precio_unit,
        })
        self._entry_cant_item.delete(0, "end")
        self._entry_cant_item.insert(0, "1")
        self._refrescar_tabla_pedido()

    def _quitar_item_pedido(self, idx: int):
        if 0 <= idx < len(self._pedido_items):
            self._pedido_items.pop(idx)
        self._refrescar_tabla_pedido()

    def _refrescar_tabla_pedido(self):
        from modules.caja import formatear_pesos
        for w in self._frame_tabla_pedido.winfo_children():
            w.destroy()

        if not self._pedido_items:
            tk.Label(self._frame_tabla_pedido, text="Sin items aun",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_dim"]).pack(anchor="w")
        else:
            for idx, linea in enumerate(self._pedido_items):
                fila = tk.Frame(self._frame_tabla_pedido, bg=COLORS["surface2"],
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
                fila.pack(fill="x", pady=2, ipady=3)
                unidad = linea.get("unidad", "")
                tk.Label(fila, text=linea["nombre"], font=FONT_SMALL,
                         bg=COLORS["surface2"], fg=COLORS["text"],
                         anchor="w").pack(side="left", padx=(8, 0),
                                          fill="x", expand=True)
                tk.Label(fila,
                         text=f"x{linea['cantidad']}{' '+unidad if unidad else ''}",
                         font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["accent"]).pack(side="left", padx=4)
                subtotal_linea = linea["cantidad"] * linea["precio_unit"]
                if subtotal_linea > 0:
                    tk.Label(fila,
                             text=formatear_pesos(subtotal_linea),
                             font=FONT_SMALL, bg=COLORS["surface2"],
                             fg=COLORS["text_muted"]).pack(side="left", padx=4)
                tk.Button(
                    fila, text="x", font=FONT_SMALL,
                    bg=COLORS["surface2"], fg=COLORS["danger"],
                    activebackground=COLORS["surface2"],
                    relief="flat", cursor="hand2", bd=0,
                    command=lambda i=idx: self._quitar_item_pedido(i)
                ).pack(side="right", padx=(0, 6))

        total = sum(l["cantidad"] * l["precio_unit"] for l in self._pedido_items)
        self._lbl_total_pedido.config(
            text=f"Total estimado: {formatear_pesos(total)}"
        )

    def _crear_pedido(self):
        from modules.proveedores import crear_pedido
        if not self._pedido_items:
            messagebox.showwarning("Sin items", "Agrega al menos un item al pedido.")
            return
        proveedor_nombre = self._combo_prov.get()
        proveedor_id     = self._provs_map.get(proveedor_nombre)
        if not proveedor_id:
            messagebox.showwarning("Sin proveedor", "Selecciona un proveedor.")
            return
        notas = self._txt_notas.get("1.0", "end").strip() or None
        items = [{"producto_id": l.get("producto_id"),
                  "insumo_id":   l.get("insumo_id"),
                  "cantidad":    l["cantidad"],
                  "precio_unit": l["precio_unit"]}
                 for l in self._pedido_items]
        try:
            pid = crear_pedido(proveedor_id, items, notas)
            messagebox.showinfo("Pedido creado",
                                f"Pedido #{pid} creado en estado Pendiente.")
            self._pedido_items = []
            self._cargar_pedidos()
            self._cerrar_modal()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _modal_pedido_detalle(self, pedido_id: int):
        """Modal de detalle de un pedido con opciones de acción."""
        from modules.proveedores import obtener_pedido
        from modules.caja import formatear_pesos

        pedido = obtener_pedido(pedido_id)
        if not pedido:
            return

        m = ModalForm(self, f"Pedido #{pedido['id']}", ancho=460)
        self._modal = m
        body = m.body

        estado_color = {
            "pendiente":  COLORS["warning"],
            "recibido":   COLORS["success"],
            "cancelado":  COLORS["danger"],
        }.get(pedido["estado"], COLORS["text_muted"])

        tk.Label(body, text=f"Proveedor: {pedido['proveedor_nombre']}",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(10, 0))
        tk.Label(body, text=f"Fecha: {pedido['fecha'][:16]}",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        tk.Label(body, text=f"Estado: {pedido['estado'].capitalize()}",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=estado_color).pack(anchor="w", padx=16, pady=(2, 0))

        if pedido.get("notas"):
            tk.Label(body, text=f"Notas: {pedido['notas']}",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"],
                     wraplength=400, justify="left").pack(
                         anchor="w", padx=16, pady=(2, 0))

        tk.Frame(body, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        tk.Label(body, text="Items del pedido", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(0, 6))

        for item in pedido["detalle"]:
            fila = tk.Frame(body, bg=COLORS["surface2"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            fila.pack(fill="x", padx=16, pady=2, ipady=3)
            tipo_icono = "📦" if item["item_tipo"] == "producto" else "🧂"
            tk.Label(fila, text=f"{tipo_icono} {item['item_nombre']}",
                     font=FONT_SMALL, bg=COLORS["surface2"],
                     fg=COLORS["text"], anchor="w").pack(
                         side="left", padx=(8, 0), fill="x", expand=True)
            tk.Label(fila, text=f"x{item['cantidad']}",
                     font=FONT_SMALL, bg=COLORS["surface2"],
                     fg=COLORS["accent"]).pack(side="left", padx=6)
            if item["precio_unit"] > 0:
                tk.Label(fila, text=formatear_pesos(item["precio_unit"]),
                         font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["text_muted"]).pack(side="right", padx=8)

        tk.Label(body, text=f"Total: {formatear_pesos(pedido['total'] or 0)}",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["accent"]).pack(anchor="e", padx=16, pady=(8, 12))

        # Acciones (footer) solo si es pendiente
        if pedido["estado"] == "pendiente":
            self._btn_primary(
                m.footer, "✓ Recibir",
                lambda pid=pedido_id: (self._cerrar_modal(), self._recibir_pedido(pid))
            ).pack(side="right", ipady=6, ipadx=14)
            self._btn_danger(
                m.footer, "✕ Cancelar pedido",
                lambda pid=pedido_id: (self._cerrar_modal(), self._cancelar_pedido(pid))
            ).pack(side="right", padx=(0, 8), ipady=6, ipadx=10)
        self._btn_secondary(m.footer, "Cerrar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        m.mostrar()

    def _recibir_pedido(self, pedido_id: int):
        """Abre el dialogo de pago y procesa la recepcion del pedido."""
        from modules.proveedores import obtener_pedido
        from modules.ui_pago import abrir_dialogo_pago

        pedido = obtener_pedido(pedido_id)
        if not pedido:
            return

        total = pedido.get("total") or 0

        if total > 0:
            abrir_dialogo_pago(
                self, total,
                lambda pagos, pid=pedido_id: self._procesar_recepcion(pid, pagos),
                titulo=f"Pagar pedido #{pedido_id}"
            )
        else:
            if messagebox.askyesno(
                "Confirmar recepcion",
                "El pedido no tiene total registrado.\n"
                "Se actualizara el stock sin descontar de caja.\n\n"
                "Deseas continuar?"
            ):
                self._procesar_recepcion(pedido_id, pagos=None)

    def _procesar_recepcion(self, pedido_id: int, pagos):
        from modules.proveedores import recibir_pedido
        from modules.caja import get_sesion_activa, formatear_pesos
        sesion    = get_sesion_activa()
        sesion_id = sesion["id"] if sesion else None
        try:
            resultado = recibir_pedido(pedido_id, pagos=pagos,
                                        sesion_id=sesion_id)
            items   = resultado["items_actualizados"]
            resumen = "\n".join(
                f"  + {i['cantidad']} de {i['nombre']}" for i in items
            )
            total_pagado = sum(p["monto"] for p in pagos) if pagos else 0
            msg = f"Stock actualizado:\n{resumen}"
            if total_pagado > 0:
                metodos = " + ".join(p["metodo"] for p in pagos)
                msg += f"\n\nEgreso: {formatear_pesos(total_pagado)}\nMetodo: {metodos}"
                if not sesion:
                    msg += "\n\nAviso: no hay caja abierta. El egreso quedo registrado sin sesion."
            if messagebox.askyesno("Pedido recibido",
                                     msg + "\n\n¿Imprimir ticket del pedido?"):
                from ui.ticket_dialog import mostrar_ticket_pedido
                mostrar_ticket_pedido(self, pedido_id)
            # Ingreso de compra (soporte contable / factura electrónica proveedor)
            if messagebox.askyesno(
                    "Ingreso de compra",
                    "¿Registrar la factura del proveedor para el libro de compras?"):
                from modules.proveedores import obtener_pedido
                ped = obtener_pedido(pedido_id)
                DialogFacturaProveedor(
                    self, ped["proveedor_id"], pedido_id=pedido_id,
                    total_sugerido=ped.get("total") or total_pagado)
            self._cargar_pedidos()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _cancelar_pedido(self, pedido_id: int):
        from modules.proveedores import cancelar_pedido
        if not messagebox.askyesno("Confirmar", "Deseas cancelar este pedido?"):
            return
        try:
            cancelar_pedido(pedido_id)
            messagebox.showinfo("Cancelado", "Pedido cancelado.")
            self._cargar_pedidos()
        except Exception as e:
            messagebox.showerror("Error", str(e))


class DialogFacturaProveedor(tk.Toplevel):
    """Registra la factura de compra de un proveedor (ingreso de compras)."""

    def __init__(self, parent, proveedor_id, pedido_id=None, total_sugerido=0):
        super().__init__(parent)
        self.proveedor_id = proveedor_id
        self.pedido_id = pedido_id
        self.title("Ingreso de compra — Factura de proveedor")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()

        from modules.compras import TIPOS_DOCUMENTO, METODOS_PAGO
        self._TIPOS = TIPOS_DOCUMENTO

        card = tk.Frame(self, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(padx=20, pady=20, ipadx=16, ipady=16)

        tk.Label(card, text="Factura de proveedor", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(0, 4))
        if pedido_id:
            tk.Label(card, text=f"Enlazada al pedido #{pedido_id}", font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 10))

        def _campo(lbl):
            tk.Label(card, text=lbl, font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
            e = tk.Entry(card, font=FONT_LABEL, bg=COLORS["surface2"], fg=COLORS["text"],
                         insertbackground=COLORS["accent"], relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=COLORS["border"],
                         highlightcolor=COLORS["accent"], width=38)
            e.pack(fill="x", ipady=5)
            return e

        # Tipo de documento
        tk.Label(card, text="Tipo de documento", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 0))
        self._tipo_var = tk.StringVar(value="factura")
        tipo_row = tk.Frame(card, bg=COLORS["surface"])
        tipo_row.pack(fill="x", pady=(2, 0))
        for key, label in TIPOS_DOCUMENTO.items():
            tk.Radiobutton(
                tipo_row, text=label, variable=self._tipo_var, value=key,
                font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["surface"],
                cursor="hand2", command=self._toggle_cufe).pack(anchor="w")

        self.e_numero = _campo("Número de factura")
        self.e_cufe = _campo("CUFE (obligatorio si es factura electrónica)")
        self.e_base = _campo("Base gravable ($)")
        self.e_iva = _campo("IVA ($)")
        self.e_iva.insert(0, "0")
        if total_sugerido:
            self.e_base.insert(0, str(int(total_sugerido)))

        # Método de pago
        tk.Label(card, text="Método de pago", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        self._metodo_var = tk.StringVar(value="efectivo")
        met_menu = tk.OptionMenu(card, self._metodo_var, *METODOS_PAGO)
        met_menu.config(bg=COLORS["surface2"], fg=COLORS["text"], relief="flat",
                        font=FONT_LABEL, anchor="w", highlightthickness=1,
                        highlightbackground=COLORS["border"])
        met_menu.pack(fill="x", pady=(2, 0))

        self.e_notas = _campo("Notas (opcional)")

        btns = tk.Frame(card, bg=COLORS["surface"])
        btns.pack(fill="x", pady=(14, 0))
        tk.Button(btns, text="Cancelar", font=FONT_BOLD, bg=COLORS["surface2"],
                  fg=COLORS["text_muted"], relief="flat", cursor="hand2",
                  command=self.destroy).pack(side="left", ipadx=14, ipady=6, padx=(0, 8))
        tk.Button(btns, text="Registrar compra", font=FONT_BOLD, bg=COLORS["accent"],
                  fg=COLORS["on_accent"], relief="flat", cursor="hand2",
                  command=self._guardar).pack(side="right", ipadx=14, ipady=6)

        self._toggle_cufe()
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth()-w)//2}+{(self.winfo_screenheight()-h)//2}")

    def _toggle_cufe(self):
        estado = "normal" if self._tipo_var.get() == "factura_electronica" else "disabled"
        self.e_cufe.config(state=estado)

    def _guardar(self):
        from modules.compras import registrar_ingreso_compra
        numero = self.e_numero.get().strip()
        try:
            base = float(self.e_base.get().replace(",", "").replace("$", "") or 0)
            iva = float(self.e_iva.get().replace(",", "").replace("$", "") or 0)
        except ValueError:
            messagebox.showerror("Error", "Base e IVA deben ser numéricos.", parent=self)
            return
        cufe = self.e_cufe.get().strip() if self._tipo_var.get() == "factura_electronica" else None
        try:
            registrar_ingreso_compra(
                self.proveedor_id, numero, base, iva=iva,
                tipo_documento=self._tipo_var.get(), cufe=cufe,
                pedido_id=self.pedido_id, metodo_pago=self._metodo_var.get(),
                notas=self.e_notas.get().strip() or None,
            )
            messagebox.showinfo("Compra registrada",
                                "Factura de compra registrada en el libro de compras.",
                                parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
