"""
ui/inventario.py — El G POS
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI

class FrameInventario(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Inventario", "Productos, insumos y stock")
        self._producto_sel = None   # ID del producto seleccionado
        self._insumo_sel   = None   # ID del insumo seleccionado
        self._modo         = "nuevo"  # "nuevo" | "editar"
        self._build()

    # ── Layout principal ──────────────────────────────────────────────────────
    def _build(self):
        self._cols_prods = {
            "pid":          "#",
            "nombre":       "Nombre",
            "categoria":    "Categoría",
            "precio_venta": "Precio Venta",
            "costo":        "Costo",
            "stock":        "Stock",
            "minimo":       "Mín",
            "margen":       "Margen %",
            "activo":       "Estado",
        }
        self._cols_insumos = {
            "iid":       "#",
            "nombre":    "Nombre",
            "stock":     "Stock",
            "unidad":    "Unidad",
            "stock_min": "Stock Mín",
        }

        self._main_frame = tk.Frame(self, bg=COLORS["bg"])
        self._main_frame.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        main = self._main_frame

        # ── Panel derecho PRIMERO (pack order importa en Tkinter) ────────────
        self._panel_outer = tk.Frame(
            self._main_frame, bg=COLORS["border"],
            highlightbackground=COLORS["border"], highlightthickness=1,
            width=302
        )
        self._panel_outer.pack(side="right", fill="y")
        self._panel_outer.pack_propagate(False)

        self._panel_canvas = tk.Canvas(
            self._panel_outer, bg=COLORS["surface"],
            highlightthickness=0, bd=0, width=300
        )
        self._panel_scroll = tk.Scrollbar(
            self._panel_outer, orient="vertical",
            command=self._panel_canvas.yview
        )
        self._panel_canvas.configure(yscrollcommand=self._panel_scroll.set)
        self._panel_scroll.pack(side="right", fill="y")
        self._panel_canvas.pack(side="left", fill="both", expand=True)

        self._panel = tk.Frame(self._panel_canvas, bg=COLORS["surface"])
        self._panel_win = self._panel_canvas.create_window(
            (0, 0), window=self._panel, anchor="nw"
        )
        self._panel_canvas.bind("<Configure>",
            lambda e: self._panel_canvas.itemconfig(self._panel_win, width=e.width))
        self._panel.bind("<Configure>",
            lambda e: self._panel_canvas.configure(
                scrollregion=self._panel_canvas.bbox("all")))
        self._panel_canvas.bind_all("<MouseWheel>", self._on_panel_wheel)

        # ── Panel izquierdo DESPUÉS (así el derecho siempre tiene espacio) ────
        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        # Tabs
        tab_frame = tk.Frame(left, bg=COLORS["bg"])
        tab_frame.pack(fill="x", pady=(0, 10))
        self._tab = tk.StringVar(value="productos")
        for t, v in [("Productos", "productos"), ("Insumos de cocina", "insumos")]:
            tk.Radiobutton(
                tab_frame, text=t, variable=self._tab, value=v,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._cambiar_tab, padx=14, pady=6,
            ).pack(side="left", padx=(0, 4))

        # Tabla
        tabla_wrap = tk.Frame(left, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)
        ids_prods = list(self._cols_prods.keys())
        self.tree = self._tabla(tabla_wrap, ids_prods, alto=16)
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)
        self._configurar_columnas_prods()
        self._cargar_productos()

        self._construir_panel_producto()

    def _on_panel_wheel(self, event):
        """Scroll con rueda del mouse solo sobre el panel derecho."""
        widget = event.widget
        # Solo scrollear si el mouse está sobre el panel
        try:
            px = self._panel_outer.winfo_rootx()
            pw = self._panel_outer.winfo_width()
            mx = event.x_root
            if not (px <= mx <= px + pw):
                return
        except Exception:
            return
        if event.num == 4:
            self._panel_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._panel_canvas.yview_scroll(1, "units")
        else:
            self._panel_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Configuración de columnas ─────────────────────────────────────────────
    def _configurar_columnas_prods(self):
        self.tree["columns"] = list(self._cols_prods.keys())
        anchos = {"pid": 35, "nombre": 180, "categoria": 120, "precio_venta": 100,
                  "costo": 90, "stock": 60, "minimo": 50, "margen": 70, "activo": 70}
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id == "nombre" else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=self._cols_prods[col_id])

    def _configurar_columnas_insumos(self):
        self.tree["columns"] = list(self._cols_insumos.keys())
        anchos = {"iid": 35, "nombre": 220, "stock": 80, "unidad": 100, "stock_min": 80}
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id == "nombre" else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=self._cols_insumos[col_id])

    # ── Carga de datos ────────────────────────────────────────────────────────
    def _cargar_productos(self):
        from modules.inventario import listar_productos, calcular_margen
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for p in listar_productos(solo_activos=False):
            margen = calcular_margen(p["precio_venta"], p["precio_costo"])
            estado = "Activo" if p["activo"] else "Inactivo"
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["nombre"], p["categoria_nombre"],
                formatear_pesos(p["precio_venta"]),
                formatear_pesos(p["precio_costo"]),
                p["stock"], p["stock_minimo"],
                f"{margen}%", estado
            ))

    def _cargar_insumos(self):
        from modules.inventario import listar_insumos
        self.tree.delete(*self.tree.get_children())
        for i in listar_insumos(solo_activos=False):
            self.tree.insert("", "end", iid=f"i{i['id']}", values=(
                i["id"], i["nombre"], i["stock"], i["unidad"], i["stock_minimo"]
            ))

    def _limpiar_panel(self):
        """Elimina todos los widgets del panel sin destruirlo."""
        for w in self._panel.winfo_children():
            w.destroy()
        self._panel_canvas.yview_moveto(0)
        self._limpiar_seleccion()

    def _cambiar_tab(self):
        self._limpiar_panel()
        if self._tab.get() == "productos":
            self._configurar_columnas_prods()
            self._cargar_productos()
            self._construir_panel_producto()
        else:
            self._configurar_columnas_insumos()
            self._cargar_insumos()
            self._construir_panel_insumo()

    # ── Selección en tabla ────────────────────────────────────────────────────
    def _al_seleccionar(self, event=None):
        sel = self.tree.focus()
        if not sel:
            return
        if self._tab.get() == "productos":
            self._producto_sel = int(sel)
            self._modo = "editar"
            self._cargar_producto_en_form(self._producto_sel)
        else:
            self._insumo_sel = int(sel.replace("i", ""))
            self._modo = "editar"
            self._cargar_insumo_en_form(self._insumo_sel)

    def _limpiar_seleccion(self):
        self._producto_sel = None
        self._insumo_sel   = None
        self._modo         = "nuevo"

    # ══════════════════════════════════════════════════════════
    # PANEL PRODUCTO
    # ══════════════════════════════════════════════════════════
    def _construir_panel_producto(self):
        self._limpiar_panel()
        from modules.validaciones import aplicar_validacion
        from modules.inventario import listar_categorias

        self._lbl_modo = tk.Label(self._panel, text="Nuevo producto",
                                   font=FONT_BOLD, bg=COLORS["surface"],
                                   fg=COLORS["text"])
        self._lbl_modo.pack(anchor="w", padx=16, pady=(16, 12))

        def campo(label, attr, tipo_val=None):
            tk.Label(self._panel, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16)
            e = self._input(self._panel)
            e.pack(fill="x", padx=16, pady=(2, 8), ipady=5)
            if tipo_val:
                aplicar_validacion(e, tipo_val)
            setattr(self, attr, e)

        campo("Nombre",        "_p_nombre")
        campo("Código (SKU)",  "_p_codigo", "codigo")
        campo("Precio venta ($)", "_p_pventa", "monto")
        campo("Precio costo ($)", "_p_pcosto", "monto")
        campo("Stock inicial",    "_p_stock",  "entero")
        campo("Stock mínimo",     "_p_minimo", "entero")

        # Categoría
        tk.Label(self._panel, text="Categoría", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        cats = listar_categorias()
        self._cats_map = {c["nombre"]: c["id"] for c in cats}
        self._p_cat_var = tk.StringVar()
        self._combo_cat = ttk.Combobox(
            self._panel, textvariable=self._p_cat_var,
            values=list(self._cats_map.keys()),
            font=FONT_LABEL, state="readonly"
        )
        if cats:
            self._combo_cat.set(cats[0]["nombre"])
        self._combo_cat.pack(fill="x", padx=16, pady=(2, 8))
        self._combo_cat.bind("<<ComboboxSelected>>", self._on_cat_change)

        # Sección receta (visible solo para cocina)
        self._frame_receta = tk.Frame(self._panel, bg=COLORS["surface"])
        self._frame_receta.pack(fill="x", padx=16, pady=(0, 8))
        self._receta_items = []   # [(insumo_id, nombre, entry_cant)]
        self._construir_receta_ui()

        self._sep_receta = tk.Frame(self._panel, bg=COLORS["border"], height=1)
        self._sep_receta.pack(fill="x", padx=16, pady=8)

        # Botones
        if auth.es_admin():
            self._btn_primary(self._panel, "Guardar producto",
                              self._guardar_producto).pack(fill="x", padx=16, ipady=8)
            self._btn_danger(self._panel, "Desactivar producto",
                             self._desactivar_producto).pack(
                                 fill="x", padx=16, pady=(6, 0), ipady=6)

        tk.Button(self._panel, text="+ Nuevo (limpiar)",
                  font=FONT_SMALL, bg=COLORS["surface"],
                  fg=COLORS["text_muted"], relief="flat", cursor="hand2",
                  command=self._nuevo_producto).pack(pady=(8, 16))

        self._actualizar_visibilidad_receta()

    def _construir_receta_ui(self):
        """Construye la sección de receta dentro del panel."""
        for w in self._frame_receta.winfo_children():
            w.destroy()
        self._receta_items = []

        from modules.inventario import listar_insumos
        insumos = listar_insumos()
        if not insumos:
            return

        tk.Label(self._frame_receta, text="Receta (insumos)",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", pady=(4, 6))

        self._insumos_map = {i["nombre"]: i["id"] for i in insumos}

        for i in insumos[:10]:   # máximo 10 insumos visibles
            fila = tk.Frame(self._frame_receta, bg=COLORS["surface"])
            fila.pack(fill="x", pady=2)

            var_check = tk.BooleanVar(value=False)
            chk = tk.Checkbutton(
                fila, variable=var_check,
                bg=COLORS["surface"], activebackground=COLORS["surface"],
                selectcolor=COLORS["surface2"],
            )
            chk.pack(side="left")

            tk.Label(fila, text=i["nombre"], font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text"],
                     width=14, anchor="w").pack(side="left")

            from modules.validaciones import aplicar_validacion
            entry_cant = self._input(fila, width=5)
            entry_cant.insert(0, "0")
            entry_cant.pack(side="left", padx=(4, 0), ipady=3)
            aplicar_validacion(entry_cant, "entero")

            tk.Label(fila, text=i["unidad"], font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left", padx=(4, 0))

            self._receta_items.append((i["id"], var_check, entry_cant))

    def _on_cat_change(self, event=None):
        self._actualizar_visibilidad_receta()

    def _actualizar_visibilidad_receta(self):
        """Muestra u oculta la sección de receta según la categoría seleccionada."""
        cat_nombre = self._p_cat_var.get()
        cat_id     = self._cats_map.get(cat_nombre)
        # Ocultar por defecto
        self._frame_receta.pack_forget()
        if not cat_id:
            return
        from modules.inventario import listar_categorias
        cats = {c["id"]: c["tipo"] for c in listar_categorias()}
        tipo = cats.get(cat_id, "tienda")
        if tipo == "cocina":
            # Insertar receta antes del separador (antes del sep Frame)
            self._frame_receta.pack(fill="x", padx=16, pady=(0, 8),
                                     before=self._sep_receta)

    def _cargar_producto_en_form(self, producto_id: int):
        """Rellena el formulario con los datos del producto seleccionado."""
        from modules.inventario import obtener_producto, obtener_receta

        p = obtener_producto(producto_id)
        if not p:
            return

        self._lbl_modo.config(text=f"Editando: {p['nombre'][:22]}")

        for entry, valor in [
            (self._p_nombre, p["nombre"]),
            (self._p_codigo, p["codigo"] or ""),
            (self._p_pventa, str(int(p["precio_venta"]))),
            (self._p_pcosto, str(int(p["precio_costo"]))),
            (self._p_stock,  str(int(p["stock"]))),
            (self._p_minimo, str(int(p["stock_minimo"]))),
        ]:
            entry.delete(0, "end")
            entry.insert(0, valor)

        # Categoría
        cat_nombre = p["categoria_nombre"]
        if cat_nombre in self._cats_map:
            self._combo_cat.set(cat_nombre)
        self._actualizar_visibilidad_receta()

        # Receta
        receta = {r["insumo_id"]: r["cantidad"] for r in obtener_receta(producto_id)}
        for insumo_id, var_check, entry_cant in self._receta_items:
            if insumo_id in receta:
                var_check.set(True)
                entry_cant.delete(0, "end")
                entry_cant.insert(0, str(int(receta[insumo_id])))
            else:
                var_check.set(False)
                entry_cant.delete(0, "end")
                entry_cant.insert(0, "0")

    def _nuevo_producto(self):
        self._limpiar_seleccion()
        self.tree.selection_remove(*self.tree.selection())
        self._lbl_modo.config(text="Nuevo producto")
        for entry in [self._p_nombre, self._p_codigo,
                      self._p_pventa, self._p_pcosto,
                      self._p_stock, self._p_minimo]:
            entry.delete(0, "end")
        for _, var_check, entry_cant in self._receta_items:
            var_check.set(False)
            entry_cant.delete(0, "end")
            entry_cant.insert(0, "0")

    def _guardar_producto(self):
        from modules.inventario import crear_producto, editar_producto, guardar_receta
        from modules.validaciones import leer_entero, leer_texto

        nombre  = leer_texto(self._p_nombre)
        codigo  = leer_texto(self._p_codigo) or None
        pventa  = leer_entero(self._p_pventa)
        pcosto  = leer_entero(self._p_pcosto)
        stock   = leer_entero(self._p_stock)
        minimo  = leer_entero(self._p_minimo)
        cat_id  = self._cats_map.get(self._p_cat_var.get())

        if not nombre:
            messagebox.showwarning("Campo vacío", "El nombre del producto es obligatorio.")
            return
        if not cat_id:
            messagebox.showwarning("Categoría", "Selecciona una categoría.")
            return
        if pventa <= 0:
            messagebox.showwarning("Precio inválido", "El precio de venta debe ser mayor a 0.")
            return

        # Receta
        receta = []
        for insumo_id, var_check, entry_cant in self._receta_items:
            if var_check.get():
                cant = leer_entero(entry_cant, default=1)
                if cant > 0:
                    receta.append({"insumo_id": insumo_id, "cantidad": cant})

        try:
            if self._modo == "nuevo":
                pid = crear_producto(nombre, cat_id, pventa, pcosto, stock, minimo, codigo)
                if receta:
                    guardar_receta(pid, receta)
                messagebox.showinfo("Creado", f"✓ Producto '{nombre}' creado (ID {pid}).")
            else:
                editar_producto(
                    self._producto_sel,
                    nombre=nombre, codigo=codigo,
                    precio_venta=pventa, precio_costo=pcosto,
                    stock=stock, stock_minimo=minimo,
                    categoria_id=cat_id
                )
                guardar_receta(self._producto_sel, receta)
                messagebox.showinfo("Guardado", f"✓ Producto actualizado.")

            self._cargar_productos()
            self._nuevo_producto()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _desactivar_producto(self):
        if not self._producto_sel:
            messagebox.showwarning("Sin selección", "Selecciona un producto para desactivar.")
            return
        from modules.inventario import obtener_producto, desactivar_producto
        p = obtener_producto(self._producto_sel)
        nombre_prod = p["nombre"]
        if not messagebox.askyesno("Confirmar",
                                    f"¿Desactivar '{nombre_prod}'?\n"
                                    "No aparecerá en ventas pero se conserva el historial."):
            return
        desactivar_producto(self._producto_sel)
        messagebox.showinfo("Desactivado", "✓ Producto desactivado.")
        self._cargar_productos()
        self._nuevo_producto()

    # ══════════════════════════════════════════════════════════
    # PANEL INSUMO
    # ══════════════════════════════════════════════════════════
    def _construir_panel_insumo(self):
        self._limpiar_panel()
        from modules.validaciones import aplicar_validacion

        self._lbl_modo_i = tk.Label(self._panel, text="Nuevo insumo",
                                     font=FONT_BOLD, bg=COLORS["surface"],
                                     fg=COLORS["text"])
        self._lbl_modo_i.pack(anchor="w", padx=16, pady=(16, 12))

        campos = [
            ("Nombre del insumo", "_i_nombre", None),
            ("Stock actual",      "_i_stock",  "entero"),
            ("Stock mínimo",      "_i_minimo", "entero"),
        ]
        for label, attr, val in campos:
            tk.Label(self._panel, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
            e = self._input(self._panel)
            e.pack(fill="x", padx=16, pady=(2, 8), ipady=5)
            if val:
                aplicar_validacion(e, val)
            setattr(self, attr, e)

        # Unidad
        tk.Label(self._panel, text="Unidad de medida", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._i_unidad_var = tk.StringVar(value="unidad")
        self._combo_unidad = ttk.Combobox(
            self._panel, textvariable=self._i_unidad_var,
            values=["unidad", "porción", "gramos", "ml", "litro", "taza"],
            font=FONT_LABEL
        )
        self._combo_unidad.pack(fill="x", padx=16, pady=(2, 12))

        sep = tk.Frame(self._panel, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=16, pady=8)

        if auth.es_admin():
            self._btn_primary(self._panel, "Guardar insumo",
                              self._guardar_insumo).pack(fill="x", padx=16, ipady=8)

        tk.Button(self._panel, text="+ Nuevo (limpiar)",
                  font=FONT_SMALL, bg=COLORS["surface"],
                  fg=COLORS["text_muted"], relief="flat", cursor="hand2",
                  command=self._nuevo_insumo).pack(pady=(8, 16))

    def _cargar_insumo_en_form(self, insumo_id: int):
        from modules.inventario import obtener_insumo
        i = obtener_insumo(insumo_id)
        if not i:
            return
        self._lbl_modo_i.config(text=f"Editando: {i['nombre'][:22]}")
        for entry, valor in [
            (self._i_nombre, i["nombre"]),
            (self._i_stock,  str(int(i["stock"]))),
            (self._i_minimo, str(int(i["stock_minimo"]))),
        ]:
            entry.delete(0, "end")
            entry.insert(0, valor)
        self._combo_unidad.set(i["unidad"])

    def _nuevo_insumo(self):
        self._limpiar_seleccion()
        self.tree.selection_remove(*self.tree.selection())
        self._lbl_modo_i.config(text="Nuevo insumo")
        for e in [self._i_nombre, self._i_stock, self._i_minimo]:
            e.delete(0, "end")
        self._combo_unidad.set("unidad")

    def _guardar_insumo(self):
        from modules.inventario import crear_insumo, editar_insumo
        from modules.validaciones import leer_entero, leer_texto

        nombre = leer_texto(self._i_nombre)
        stock  = leer_entero(self._i_stock)
        minimo = leer_entero(self._i_minimo)
        unidad = self._i_unidad_var.get().strip() or "unidad"

        if not nombre:
            messagebox.showwarning("Campo vacío", "El nombre del insumo es obligatorio.")
            return

        try:
            if self._modo == "nuevo":
                iid = crear_insumo(nombre, stock, unidad, minimo)
                messagebox.showinfo("Creado", f"✓ Insumo '{nombre}' creado (ID {iid}).")
            else:
                editar_insumo(
                    self._insumo_sel,
                    nombre=nombre, stock=stock,
                    unidad=unidad, stock_minimo=minimo
                )
                messagebox.showinfo("Guardado", "✓ Insumo actualizado.")
            self._cargar_insumos()
            self._nuevo_insumo()
        except Exception as e:
            messagebox.showerror("Error", str(e))