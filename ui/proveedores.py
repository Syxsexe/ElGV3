"""
ui/proveedores.py — El G POS
Gestión de proveedores y pedidos de stock.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_KPI


class FrameProveedores(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Proveedores", "Gestión de proveedores y pedidos de stock")
        self._proveedor_sel = None
        self._pedido_sel    = None
        self._pedido_items  = []   # ítems del pedido en construcción
        self._modo_prov     = "nuevo"
        self._build()

    def _build(self):
        # Tabs: Proveedores | Pedidos
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

        # Contenedor principal
        self._main = tk.Frame(self, bg=COLORS["bg"])
        self._main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # Panel derecho scrolleable (primero para pack order)
        right_outer = tk.Frame(self._main, bg=COLORS["border"],
                               highlightbackground=COLORS["border"],
                               highlightthickness=1, width=302)
        right_outer.pack(side="right", fill="y")
        right_outer.pack_propagate(False)

        right_canvas = tk.Canvas(right_outer, bg=COLORS["surface"],
                                  highlightthickness=0, bd=0, width=300)
        right_scroll = tk.Scrollbar(right_outer, orient="vertical",
                                     command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_scroll.set)
        right_scroll.pack(side="right", fill="y")
        right_canvas.pack(side="left", fill="both", expand=True)

        self._panel = tk.Frame(right_canvas, bg=COLORS["surface"])
        self._panel_win = right_canvas.create_window(
            (0, 0), window=self._panel, anchor="nw"
        )
        right_canvas.bind("<Configure>",
            lambda e: right_canvas.itemconfig(self._panel_win, width=e.width))
        self._panel.bind("<Configure>",
            lambda e: right_canvas.configure(
                scrollregion=right_canvas.bbox("all")))
        self._right_canvas = right_canvas

        # Panel izquierdo: tabla
        left = tk.Frame(self._main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tabla_wrap = tk.Frame(left, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)

        cols = ("id", "nombre", "contacto", "telefono", "estado")
        self.tree = self._tabla(tabla_wrap, cols, alto=18)
        self.tree.heading("id",       text="#")
        self.tree.heading("nombre",   text="Nombre")
        self.tree.heading("contacto", text="Contacto")
        self.tree.heading("telefono", text="Telefono")
        self.tree.heading("estado",   text="Estado")
        self.tree.column("id",       width=40)
        self.tree.column("nombre",   width=200, anchor="w")
        self.tree.column("contacto", width=150, anchor="w")
        self.tree.column("telefono", width=120)
        self.tree.column("estado",   width=80)
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)

        self._cargar_proveedores()
        self._construir_panel_proveedor()

    # ── Navegación entre tabs ─────────────────────────────────────────────────
    def _cambiar_tab(self):
        self._limpiar_panel()
        self._proveedor_sel = None
        self._pedido_sel    = None
        if self._tab.get() == "proveedores":
            self._configurar_cols_proveedores()
            self._cargar_proveedores()
            self._construir_panel_proveedor()
        else:
            self._configurar_cols_pedidos()
            self._cargar_pedidos()
            self._construir_panel_pedido()

    def _limpiar_panel(self):
        for w in self._panel.winfo_children():
            w.destroy()
        self._right_canvas.yview_moveto(0)

    def _al_seleccionar(self, event=None):
        sel = self.tree.focus()
        if not sel:
            return
        if self._tab.get() == "proveedores":
            self._proveedor_sel = int(sel)
            self._modo_prov = "editar"
            self._cargar_proveedor_en_form(self._proveedor_sel)
        else:
            self._pedido_sel = int(sel)
            self._cargar_pedido_en_panel(self._pedido_sel)

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
        self.tree.column("nombre",   width=200, anchor="w")
        self.tree.column("contacto", width=150, anchor="w")
        self.tree.column("telefono", width=120)
        self.tree.column("estado",   width=80)

    def _cargar_proveedores(self):
        from modules.proveedores import listar_proveedores
        self.tree.delete(*self.tree.get_children())
        for p in listar_proveedores(solo_activos=False):
            estado = "Activo" if p["activo"] else "Inactivo"
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["nombre"],
                p["contacto"] or "—",
                p["telefono"] or "—",
                estado
            ))

    def _construir_panel_proveedor(self):
        self._limpiar_panel()
        self._modo_prov = "nuevo"

        self._lbl_modo_p = tk.Label(self._panel, text="Nuevo proveedor",
                                     font=FONT_BOLD, bg=COLORS["surface"],
                                     fg=COLORS["text"])
        self._lbl_modo_p.pack(anchor="w", padx=16, pady=(16, 12))

        campos = [
            ("Nombre *",   "_p_nombre"),
            ("Contacto",   "_p_contacto"),
            ("Telefono",   "_p_telefono"),
            ("Email",      "_p_email"),
        ]
        for label, attr in campos:
            tk.Label(self._panel, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
            e = self._input(self._panel)
            e.pack(fill="x", padx=16, pady=(2, 8), ipady=5)
            setattr(self, attr, e)

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=8)

        if auth.es_admin():
            self._btn_primary(self._panel, "Guardar proveedor",
                              self._guardar_proveedor).pack(fill="x", padx=16, ipady=8)
            self._btn_danger(self._panel, "Desactivar proveedor",
                             self._desactivar_proveedor).pack(
                                 fill="x", padx=16, pady=(6, 0), ipady=6)

        tk.Button(self._panel, text="+ Nuevo (limpiar)",
                  font=FONT_SMALL, bg=COLORS["surface"],
                  fg=COLORS["text_muted"], relief="flat", cursor="hand2",
                  command=self._nuevo_proveedor).pack(pady=(8, 16))

    def _cargar_proveedor_en_form(self, proveedor_id: int):
        from modules.proveedores import obtener_proveedor
        p = obtener_proveedor(proveedor_id)
        if not p:
            return
        self._lbl_modo_p.config(text=f"Editando: {p['nombre'][:22]}")
        for entry, valor in [
            (self._p_nombre,   p["nombre"]),
            (self._p_contacto, p["contacto"] or ""),
            (self._p_telefono, p["telefono"] or ""),
            (self._p_email,    p["email"]    or ""),
        ]:
            entry.delete(0, "end")
            entry.insert(0, valor)

    def _nuevo_proveedor(self):
        self._proveedor_sel = None
        self._modo_prov     = "nuevo"
        self.tree.selection_remove(*self.tree.selection())
        self._lbl_modo_p.config(text="Nuevo proveedor")
        for e in [self._p_nombre, self._p_contacto,
                  self._p_telefono, self._p_email]:
            e.delete(0, "end")

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
            self._nuevo_proveedor()
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
        self._nuevo_proveedor()

    # ══════════════════════════════════════════════════════════
    # TAB PEDIDOS
    # ══════════════════════════════════════════════════════════

    def _configurar_cols_pedidos(self):
        cols = ("pid", "fecha", "proveedor", "items", "total", "estado")
        self.tree["columns"] = cols
        textos = {"pid": "#", "fecha": "Fecha", "proveedor": "Proveedor",
                  "items": "Items", "total": "Total", "estado": "Estado"}
        anchos = {"pid": 40, "fecha": 140, "proveedor": 180,
                  "items": 60, "total": 110, "estado": 90}
        for col in cols:
            self.tree.heading(col, text=textos[col])
            anchor = "w" if col == "proveedor" else "center"
            self.tree.column(col, width=anchos[col], anchor=anchor)

    def _cargar_pedidos(self):
        from modules.proveedores import listar_pedidos
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for p in listar_pedidos():
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"],
                p["fecha"][:16],
                p["proveedor_nombre"],
                p["num_items"],
                formatear_pesos(p["total"] or 0),
                p["estado"].capitalize()
            ))

    def _construir_panel_pedido(self):
        self._limpiar_panel()
        self._pedido_items = []

        tk.Label(self._panel, text="Nuevo pedido", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(16, 10))

        # Proveedor
        from modules.proveedores import listar_proveedores
        provs = listar_proveedores()
        self._provs_map = {p["nombre"]: p["id"] for p in provs}
        tk.Label(self._panel, text="Proveedor", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._combo_prov = ttk.Combobox(
            self._panel, values=list(self._provs_map.keys()),
            font=FONT_LABEL, state="readonly"
        )
        if provs:
            self._combo_prov.set(provs[0]["nombre"])
        self._combo_prov.pack(fill="x", padx=16, pady=(2, 10))

        # Tipo de ítem
        tk.Label(self._panel, text="Tipo de item", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._tipo_item = tk.StringVar(value="producto")
        tipo_frame = tk.Frame(self._panel, bg=COLORS["surface"])
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
        tk.Label(self._panel, text="Buscar", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._entry_buscar_item = self._input(self._panel)
        self._entry_buscar_item.pack(fill="x", padx=16, pady=(2, 4), ipady=5)
        self._entry_buscar_item.bind("<KeyRelease>", self._actualizar_lista_items)

        lst_wrap = tk.Frame(self._panel, bg=COLORS["surface"])
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
        grid = tk.Frame(self._panel, bg=COLORS["surface"])
        grid.pack(fill="x", padx=16, pady=(0, 6))

        tk.Label(grid, text="Cantidad:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).grid(
                     row=0, column=0, sticky="w", pady=2)
        self._entry_cant_item = self._input(grid, width=8)
        self._entry_cant_item.insert(0, "1")
        self._entry_cant_item.grid(row=0, column=1, padx=(6, 0), ipady=4)
        aplicar_validacion(self._entry_cant_item, "decimal")

        tk.Label(grid, text="Precio unit ($):", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).grid(
                     row=1, column=0, sticky="w", pady=2)
        self._entry_precio_item = self._input(grid, width=8)
        self._entry_precio_item.insert(0, "0")
        self._entry_precio_item.grid(row=1, column=1, padx=(6, 0), ipady=4)
        aplicar_validacion(self._entry_precio_item, "monto")

        self._btn_primary(self._panel, "+ Agregar al pedido",
                          self._agregar_item_pedido).pack(fill="x", padx=16, ipady=6)

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        # Tabla de ítems del pedido
        tk.Label(self._panel, text="Contenido del pedido", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(0, 6))
        self._frame_tabla_pedido = tk.Frame(self._panel, bg=COLORS["surface"])
        self._frame_tabla_pedido.pack(fill="x", padx=16)

        self._lbl_total_pedido = tk.Label(
            self._panel, text="Total: $0", font=FONT_BOLD,
            bg=COLORS["surface"], fg=COLORS["accent"]
        )
        self._lbl_total_pedido.pack(anchor="w", padx=16, pady=(6, 0))

        # Notas
        tk.Label(self._panel, text="Notas (opcional)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(10, 0))
        self._txt_notas = tk.Text(self._panel, height=2, font=FONT_SMALL,
                                   bg=COLORS["surface2"], fg=COLORS["text"],
                                   insertbackground=COLORS["accent"],
                                   relief="flat", highlightthickness=1,
                                   highlightbackground=COLORS["border"])
        self._txt_notas.pack(fill="x", padx=16, pady=(2, 10))

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 10))

        if auth.es_admin():
            self._btn_primary(self._panel, "Crear pedido",
                              self._crear_pedido).pack(fill="x", padx=16, ipady=8)

        self._actualizar_lista_items()
        self._refrescar_tabla_pedido()

    def _actualizar_lista_items(self, event=None):
        """Actualiza el listbox según el tipo seleccionado (producto/insumo)."""
        from modules.inventario import listar_productos, listar_insumos
        texto = self._entry_buscar_item.get().strip().lower()
        self._lst_items_pedido.delete(0, "end")
        self._items_pedido_data = []

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

        # Si ya existe, actualiza
        clave = "producto_id" if "producto_id" in item_data else "insumo_id"
        for linea in self._pedido_items:
            if linea.get(clave) == item_data.get(clave):
                linea["cantidad"]   = cantidad
                linea["precio_unit"] = precio
                self._refrescar_tabla_pedido()
                return

        self._pedido_items.append({
            **item_data,
            "cantidad":    cantidad,
            "precio_unit": precio,
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
                if linea["precio_unit"] > 0:
                    tk.Label(fila,
                             text=formatear_pesos(linea["precio_unit"]),
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
            self._refrescar_tabla_pedido()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _cargar_pedido_en_panel(self, pedido_id: int):
        """Muestra el detalle de un pedido seleccionado con opciones de acción."""
        from modules.proveedores import obtener_pedido
        from modules.caja import formatear_pesos

        self._limpiar_panel()
        pedido = obtener_pedido(pedido_id)
        if not pedido:
            return

        # Encabezado
        estado_color = {
            "pendiente":  COLORS["warning"],
            "recibido":   COLORS["success"],
            "cancelado":  COLORS["danger"],
        }.get(pedido["estado"], COLORS["text_muted"])

        tk.Label(self._panel, text=f"Pedido #{pedido['id']}",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 2))
        tk.Label(self._panel,
                 text=f"Proveedor: {pedido['proveedor_nombre']}",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        tk.Label(self._panel,
                 text=f"Fecha: {pedido['fecha'][:16]}",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        tk.Label(self._panel,
                 text=f"Estado: {pedido['estado'].capitalize()}",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=estado_color).pack(anchor="w", padx=16, pady=(2, 0))

        if pedido.get("notas"):
            tk.Label(self._panel, text=f"Notas: {pedido['notas']}",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"],
                     wraplength=240, justify="left").pack(
                         anchor="w", padx=16, pady=(2, 0))

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        # Detalle de ítems
        tk.Label(self._panel, text="Items del pedido", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(0, 6))

        for item in pedido["detalle"]:
            fila = tk.Frame(self._panel, bg=COLORS["surface2"],
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

        # Total
        tk.Label(self._panel,
                 text=f"Total: {formatear_pesos(pedido['total'] or 0)}",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["accent"]).pack(anchor="e", padx=16, pady=(8, 0))

        # Acciones solo si es pendiente
        if pedido["estado"] == "pendiente" and auth.es_admin():
            tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
                fill="x", padx=16, pady=10)
            self._btn_primary(
                self._panel, "✓ Marcar como Recibido",
                lambda pid=pedido_id: self._recibir_pedido(pid)
            ).pack(fill="x", padx=16, ipady=10)
            self._btn_danger(
                self._panel, "✕ Cancelar pedido",
                lambda pid=pedido_id: self._cancelar_pedido(pid)
            ).pack(fill="x", padx=16, pady=(6, 16), ipady=6)

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
            messagebox.showinfo("Pedido recibido", msg)
            self._cargar_pedidos()
            self._limpiar_panel()
            tk.Label(self._panel,
                     text="Pedido recibido.\nSelecciona otro pedido.",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(padx=16, pady=24)
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
            self._limpiar_panel()
        except Exception as e:
            messagebox.showerror("Error", str(e))