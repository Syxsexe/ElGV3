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
        self._combo_sel    = None   # ID del combo seleccionado
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
        for t, v in [("Productos", "productos"),
                     ("Insumos", "insumos"),
                     ("Recetas", "recetas"),
                     ("Combos", "combos")]:
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
            # Mostrar stock sin decimales si es entero exacto
            stock  = int(i["stock"])  if i["stock"]  == int(i["stock"])  else round(i["stock"], 2)
            minimo = int(i["stock_minimo"]) if i["stock_minimo"] == int(i["stock_minimo"]) else round(i["stock_minimo"], 2)
            self.tree.insert("", "end", iid=f"i{i['id']}", values=(
                i["id"], i["nombre"],
                f"{stock} {i['unidad']}",
                i["unidad"],
                f"{minimo} {i['unidad']}"
            ))

    def _configurar_columnas_prods_cocina(self):
        """Columnas para la tabla de recetas — muestra solo productos de cocina."""
        self.tree["columns"] = list(self._cols_prods.keys())
        anchos = {"pid": 35, "nombre": 220, "categoria": 140, "precio_venta": 100,
                  "costo": 90, "stock": 60, "minimo": 50, "margen": 70, "activo": 70}
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id == "nombre" else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=self._cols_prods[col_id])

    def _cargar_productos_cocina(self):
        """Carga solo productos de tipo cocina en la tabla."""
        from modules.inventario import listar_productos, calcular_margen
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for p in listar_productos(tipo="cocina", solo_activos=False):
            margen = calcular_margen(p["precio_venta"], p["precio_costo"])
            estado = "Activo" if p["activo"] else "Inactivo"
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["nombre"], p["categoria_nombre"],
                formatear_pesos(p["precio_venta"]),
                formatear_pesos(p["precio_costo"]),
                p["stock"], p["stock_minimo"],
                f"{margen}%", estado
            ))

    def _construir_panel_receta(self):
        """Panel derecho para la pestaña Recetas — instrucción inicial."""
        self._receta_lineas = []
        self._producto_receta_id = None
        tk.Label(self._panel, text="Recetas", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(16, 4))
        tk.Label(self._panel,
                 text="Selecciona un producto\nde cocina de la tabla\npara editar su receta.",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"], justify="left").pack(
                     anchor="w", padx=16, pady=(0, 16))

    def _cargar_receta_en_panel(self, producto_id: int):
        """Carga la receta de un producto de cocina en el panel."""
        from modules.inventario import obtener_producto, obtener_receta, listar_insumos
        from modules.validaciones import aplicar_validacion

        self._limpiar_panel()
        self._producto_receta_id = producto_id
        producto = obtener_producto(producto_id)
        if not producto:
            return

        # Título
        tk.Label(self._panel,
                 text=f"Receta: {producto['nombre'][:24]}",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(self._panel,
                 text=f"Categoria: {producto['categoria_nombre']}",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(0, 8))

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 10))

        # ── Buscador de insumo ────────────────────────────────────────────────
        tk.Label(self._panel, text="Agregar insumo", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(0, 6))

        insumos = listar_insumos()
        self._insumos_lista_r = insumos
        self._insumos_map_r   = {i["nombre"]: i for i in insumos}

        tk.Label(self._panel, text="Buscar insumo", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._entry_buscar_insumo_r = self._input(self._panel)
        self._entry_buscar_insumo_r.pack(fill="x", padx=16, pady=(2, 4), ipady=5)
        self._entry_buscar_insumo_r.bind("<KeyRelease>", self._filtrar_insumos_r)

        lst_wrap = tk.Frame(self._panel, bg=COLORS["surface"])
        lst_wrap.pack(fill="x", padx=16, pady=(0, 8))
        self._lst_insumos_r = tk.Listbox(
            lst_wrap, font=FONT_SMALL, height=5,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self._lst_insumos_r.pack(fill="x")

        # Cantidad
        cant_frame = tk.Frame(self._panel, bg=COLORS["surface"])
        cant_frame.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(cant_frame, text="Cantidad:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._entry_cant_r = self._input(cant_frame, width=6)
        self._entry_cant_r.insert(0, "1")
        self._entry_cant_r.pack(side="left", padx=(6, 0), ipady=4)
        aplicar_validacion(self._entry_cant_r, "decimal")

        self._btn_primary(self._panel, "+ Agregar insumo",
                          self._agregar_insumo_r).pack(fill="x", padx=16, ipady=6)

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        # ── Tabla de receta ───────────────────────────────────────────────────
        tk.Label(self._panel, text="Receta actual", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(0, 6))

        self._frame_tabla_r = tk.Frame(self._panel, bg=COLORS["surface"])
        self._frame_tabla_r.pack(fill="x", padx=16)

        self._lbl_resumen_r = tk.Label(
            self._panel, text="", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["success"]
        )
        self._lbl_resumen_r.pack(anchor="w", padx=16, pady=(6, 0))

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        if auth.es_admin():
            self._btn_primary(self._panel, "Guardar receta",
                              self._guardar_receta_panel).pack(
                                  fill="x", padx=16, ipady=8, pady=(0, 16))

        # Cargar receta existente
        receta = obtener_receta(producto_id)
        self._receta_lineas = [
            {"insumo_id": r["insumo_id"], "nombre": r["insumo_nombre"],
             "cantidad": int(r["cantidad"]), "unidad": r["unidad"]}
            for r in receta
        ]
        self._filtrar_insumos_r()   # poblar listbox
        self._refrescar_tabla_r()

    def _filtrar_insumos_r(self, event=None):
        """Filtra el listbox de insumos según el texto buscado."""
        texto = self._entry_buscar_insumo_r.get().strip().lower()
        self._lst_insumos_r.delete(0, "end")
        for i in self._insumos_lista_r:
            if not texto or texto in i["nombre"].lower():
                self._lst_insumos_r.insert("end", f"{i['nombre']}  ({i['unidad']})")

    def _agregar_insumo_r(self):
        """Agrega el insumo seleccionado al listado de receta."""
        from modules.validaciones import leer_decimal
        sel = self._lst_insumos_r.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona un insumo de la lista.")
            return
        nombre = self._lst_insumos_r.get(sel[0]).split("  (")[0].strip()
        insumo = self._insumos_map_r.get(nombre)
        if not insumo:
            return
        cantidad = leer_decimal(self._entry_cant_r, default=1.0)
        if cantidad <= 0:
            cantidad = 1.0
        # Si ya existe, actualiza cantidad
        for linea in self._receta_lineas:
            if linea["insumo_id"] == insumo["id"]:
                linea["cantidad"] = cantidad
                self._refrescar_tabla_r()
                return
        self._receta_lineas.append({
            "insumo_id": insumo["id"],
            "nombre":    insumo["nombre"],
            "cantidad":  cantidad,
            "unidad":    insumo["unidad"],
        })
        self._entry_cant_r.delete(0, "end")
        self._entry_cant_r.insert(0, "1")
        self._refrescar_tabla_r()

    def _quitar_insumo_r(self, insumo_id: int):
        """Quita un insumo del listado de receta."""
        self._receta_lineas = [l for l in self._receta_lineas
                                if l["insumo_id"] != insumo_id]
        self._refrescar_tabla_r()

    def _refrescar_tabla_r(self):
        """Redibuja la tabla de insumos de la receta."""
        for w in self._frame_tabla_r.winfo_children():
            w.destroy()
        if not self._receta_lineas:
            tk.Label(self._frame_tabla_r, text="Sin insumos aun",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_dim"]).pack(anchor="w")
        else:
            for linea in self._receta_lineas:
                fila = tk.Frame(self._frame_tabla_r, bg=COLORS["surface2"],
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
                fila.pack(fill="x", pady=2, ipady=3)
                tk.Label(fila, text=linea["nombre"], font=FONT_SMALL,
                         bg=COLORS["surface2"], fg=COLORS["text"],
                         anchor="w").pack(side="left", padx=(8, 0),
                                          fill="x", expand=True)
                tk.Label(fila, text=f"x{linea['cantidad']} {linea['unidad']}",
                         font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["accent"]).pack(side="left", padx=6)
                tk.Button(
                    fila, text="x", font=FONT_SMALL,
                    bg=COLORS["surface2"], fg=COLORS["danger"],
                    activebackground=COLORS["surface2"],
                    relief="flat", cursor="hand2", bd=0,
                    command=lambda iid=linea["insumo_id"]: self._quitar_insumo_r(iid)
                ).pack(side="right", padx=(0, 6))
        total = sum(l["cantidad"] for l in self._receta_lineas)
        self._lbl_resumen_r.config(
            text=f"{len(self._receta_lineas)} insumos  -  {total} unidades totales"
        )

    def _guardar_receta_panel(self):
        """Guarda la receta del producto seleccionado."""
        from modules.inventario import guardar_receta
        if not self._producto_receta_id:
            return
        receta = [{"insumo_id": l["insumo_id"], "cantidad": float(l["cantidad"])}
                  for l in self._receta_lineas]
        try:
            guardar_receta(self._producto_receta_id, receta)
            messagebox.showinfo("Guardado", "Receta guardada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _limpiar_panel(self):
        """Elimina todos los widgets del panel sin destruirlo."""
        for w in self._panel.winfo_children():
            w.destroy()
        self._panel_canvas.yview_moveto(0)
        self._limpiar_seleccion()

    def _cambiar_tab(self):
        self._limpiar_panel()
        tab = self._tab.get()
        if tab == "productos":
            self._configurar_columnas_prods()
            self._cargar_productos()
            self._construir_panel_producto()
        elif tab == "insumos":
            self._configurar_columnas_insumos()
            self._cargar_insumos()
            self._construir_panel_insumo()
        elif tab == "recetas":
            self._configurar_columnas_prods_cocina()
            self._cargar_productos_cocina()
            self._construir_panel_receta()
        else:  # combos
            self._configurar_columnas_combos()
            self._cargar_combos()
            self._construir_panel_combo()

    # ── Selección en tabla ────────────────────────────────────────────────────
    def _al_seleccionar(self, event=None):
        sel = self.tree.focus()
        if not sel:
            return
        tab = self._tab.get()
        if tab == "productos":
            self._producto_sel = int(sel)
            self._modo = "editar"
            self._cargar_producto_en_form(self._producto_sel)
        elif tab == "insumos":
            self._insumo_sel = int(sel.replace("i", ""))
            self._modo = "editar"
            self._cargar_insumo_en_form(self._insumo_sel)
        elif tab == "recetas":
            self._producto_sel = int(sel)
            self._cargar_receta_en_panel(self._producto_sel)
        else:  # combos
            self._combo_sel = int(sel.replace("c", ""))
            self._modo = "editar"
            self._cargar_combo_en_panel(self._combo_sel)

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


        sep = tk.Frame(self._panel, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=16, pady=8)

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

    def _filtrar_insumos(self, event=None):
        """Filtra la lista de insumos según el texto buscado."""
        texto = self._entry_insumo.get().strip().lower()
        self._lst_insumos.delete(0, "end")
        for i in self._insumos_lista:
            if not texto or texto in i["nombre"].lower():
                self._lst_insumos.insert("end", f"{i['nombre']}  ({i['unidad']})")

    def _agregar_insumo_receta(self):
        """Agrega el insumo seleccionado a la receta."""
        from modules.validaciones import leer_entero
        sel = self._lst_insumos.curselection()
        if not sel:
            return

        nombre_completo = self._lst_insumos.get(sel[0]).split("  (")[0].strip()
        insumo = self._insumos_map.get(nombre_completo)
        if not insumo:
            return

        cantidad = leer_entero(self._entry_cant_insumo, default=1)
        if cantidad <= 0:
            quantity = 1

        # Si ya está en la receta, actualizar cantidad
        for linea in self._receta_lineas:
            if linea["insumo_id"] == insumo["id"]:
                linea["cantidad"] = cantidad
                self._refrescar_tabla_receta()
                return

        self._receta_lineas.append({
            "insumo_id":   insumo["id"],
            "nombre":      insumo["nombre"],
            "cantidad":    cantidad,
            "unidad":      insumo["unidad"],
            "costo_unit":  0,  # insumos no tienen costo unitario registrado
        })
        self._entry_cant_insumo.delete(0, "end")
        self._entry_cant_insumo.insert(0, "1")
        self._refrescar_tabla_receta()

    def _quitar_insumo_receta(self, insumo_id: int):
        """Quita un insumo de la receta."""
        self._receta_lineas = [l for l in self._receta_lineas
                                if l["insumo_id"] != insumo_id]
        self._refrescar_tabla_receta()

    def _refrescar_tabla_receta(self):
        """Redibuja la tabla de insumos de la receta y actualiza el costo."""
        from modules.caja import formatear_pesos

        for w in self._frame_tabla_receta.winfo_children():
            w.destroy()

        if not self._receta_lineas:
            tk.Label(self._frame_tabla_receta, text="Sin insumos agregados",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_dim"]).pack(anchor="w")
        else:
            for linea in self._receta_lineas:
                fila = tk.Frame(self._frame_tabla_receta,
                                bg=COLORS["surface2"],
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
                fila.pack(fill="x", pady=2, ipady=3)

                tk.Label(fila,
                         text=f"{linea['nombre']}",
                         font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["text"], anchor="w").pack(
                             side="left", padx=(8, 0), fill="x", expand=True)

                tk.Label(fila,
                         text=f"x{linea['cantidad']} {linea['unidad']}",
                         font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["accent"]).pack(side="left", padx=6)

                tk.Button(
                    fila, text="✕", font=FONT_SMALL,
                    bg=COLORS["surface2"], fg=COLORS["danger"],
                    activebackground=COLORS["surface2"],
                    relief="flat", cursor="hand2", bd=0,
                    command=lambda iid=linea["insumo_id"]: self._quitar_insumo_receta(iid)
                ).pack(side="right", padx=(0, 6))

        # Actualizar label de costo (placeholder — sin costo unitario por insumo)
        total_items = sum(l["cantidad"] for l in self._receta_lineas)
        self._lbl_costo_receta.config(
            text=f"Insumos en receta: {len(self._receta_lineas)}  ·  "
                 f"Unidades totales: {total_items}"
        )



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
            (self._p_stock,  str(int(p["stock"]) if p["stock"] == int(p["stock"]) else round(p["stock"], 2))),
            (self._p_minimo, str(int(p["stock_minimo"]) if p["stock_minimo"] == int(p["stock_minimo"]) else round(p["stock_minimo"], 2))),
        ]:
            entry.delete(0, "end")
            entry.insert(0, valor)

        # Categoría
        cat_nombre = p["categoria_nombre"]
        if cat_nombre in self._cats_map:
            self._combo_cat.set(cat_nombre)

        # Receta — cargar insumos en la nueva tabla
        receta = obtener_receta(producto_id)
        self._receta_lineas = [
            {
                "insumo_id": r["insumo_id"],
                "nombre":    r["insumo_nombre"],
                "cantidad":  int(r["cantidad"]),
                "unidad":    r["unidad"],
                "costo_unit": 0,
            }
            for r in receta
        ]
        if hasattr(self, "_frame_tabla_receta"):
            self._refrescar_tabla_receta()

    def _nuevo_producto(self):
        self._limpiar_seleccion()
        self.tree.selection_remove(*self.tree.selection())
        self._lbl_modo.config(text="Nuevo producto")
        for entry in [self._p_nombre, self._p_codigo,
                      self._p_pventa, self._p_pcosto,
                      self._p_stock, self._p_minimo]:
            entry.delete(0, "end")
        self._receta_lineas = []
        if hasattr(self, "_frame_tabla_receta"):
            self._refrescar_tabla_receta()

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

        # Receta — leer de la nueva tabla
        receta = [
            {"insumo_id": l["insumo_id"], "cantidad": l["cantidad"]}
            for l in self._receta_lineas
            if l["cantidad"] > 0
        ]

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
        self._lbl_modo_i.pack(anchor="w", padx=16, pady=(16, 6))

        # Unidad base primero — define qué tipo de campo usar para stock
        tk.Label(self._panel, text="Unidad base", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)

        UNIDADES = [
            ("g",      "Gramos (g)"),
            ("kg",     "Kilogramos (kg)"),
            ("ml",     "Mililitros (ml)"),
            ("l",      "Litros (l)"),
            ("unidad", "Unidad"),
            ("porcion","Porcion"),
        ]
        self._i_unidad_var = tk.StringVar(value="g")
        self._combo_unidad = ttk.Combobox(
            self._panel, textvariable=self._i_unidad_var,
            values=[u[1] for u in UNIDADES],
            font=FONT_LABEL, state="readonly"
        )
        self._combo_unidad.pack(fill="x", padx=16, pady=(2, 8))
        self._unidades_map = {u[1]: u[0] for u in UNIDADES}
        self._unidades_map_inv = {u[0]: u[1] for u in UNIDADES}
        self._combo_unidad.bind("<<ComboboxSelected>>", self._on_unidad_change)

        # Nota de ayuda
        self._lbl_ayuda_unidad = tk.Label(
            self._panel,
            text="El stock siempre se ingresa en la unidad base.\nEj: compras 3kg → ingresas 3000 en gramos",
            font=("Segoe UI", 8), bg=COLORS["surface"],
            fg=COLORS["text_dim"], justify="left"
        )
        self._lbl_ayuda_unidad.pack(anchor="w", padx=16, pady=(0, 8))

        tk.Label(self._panel, text="Nombre del insumo", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._i_nombre = self._input(self._panel)
        self._i_nombre.pack(fill="x", padx=16, pady=(2, 8), ipady=5)

        # Stock — usa decimal para g, ml; entero para unidad, porcion
        self._lbl_stock_i = tk.Label(self._panel, text="Stock actual (g)",
                                      font=FONT_SMALL, bg=COLORS["surface"],
                                      fg=COLORS["text_muted"])
        self._lbl_stock_i.pack(anchor="w", padx=16)
        self._i_stock = self._input(self._panel)
        self._i_stock.pack(fill="x", padx=16, pady=(2, 8), ipady=5)
        aplicar_validacion(self._i_stock, "decimal")

        self._lbl_minimo_i = tk.Label(self._panel, text="Stock minimo (g)",
                                       font=FONT_SMALL, bg=COLORS["surface"],
                                       fg=COLORS["text_muted"])
        self._lbl_minimo_i.pack(anchor="w", padx=16)
        self._i_minimo = self._input(self._panel)
        self._i_minimo.pack(fill="x", padx=16, pady=(2, 12), ipady=5)
        aplicar_validacion(self._i_minimo, "decimal")

        sep = tk.Frame(self._panel, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=16, pady=8)

        if auth.es_admin():
            self._btn_primary(self._panel, "Guardar insumo",
                              self._guardar_insumo).pack(fill="x", padx=16, ipady=8)

        tk.Button(self._panel, text="+ Nuevo (limpiar)",
                  font=FONT_SMALL, bg=COLORS["surface"],
                  fg=COLORS["text_muted"], relief="flat", cursor="hand2",
                  command=self._nuevo_insumo).pack(pady=(8, 16))

        self._actualizar_labels_stock()

    def _on_unidad_change(self, event=None):
        """Actualiza los labels de stock según la unidad seleccionada."""
        self._actualizar_labels_stock()

    def _actualizar_labels_stock(self):
        """Actualiza los labels de stock con la unidad base seleccionada."""
        display = self._i_unidad_var.get()
        codigo  = self._unidades_map.get(display, "g")
        self._lbl_stock_i.config(text=f"Stock actual ({codigo})")
        self._lbl_minimo_i.config(text=f"Stock minimo ({codigo})")

        # Unidades que usan decimal vs entero
        usa_decimal = codigo in ("g", "kg", "ml", "l")
        if usa_decimal:
            self._lbl_ayuda_unidad.config(
                text=f"Ingresa el valor en {codigo}.\nEj: 3kg de carne = 3000g"
                if codigo == "g" else f"Ingresa el valor en {codigo}."
            )
        else:
            self._lbl_ayuda_unidad.config(text=f"Ingresa la cantidad en {codigo}.")

    def _cargar_insumo_en_form(self, insumo_id: int):
        from modules.inventario import obtener_insumo
        i = obtener_insumo(insumo_id)
        if not i:
            return
        self._lbl_modo_i.config(text=f"Editando: {i['nombre'][:22]}")

        # Unidad
        display = self._unidades_map_inv.get(i["unidad"], i["unidad"])
        self._combo_unidad.set(display)
        self._actualizar_labels_stock()

        # Nombre
        self._i_nombre.delete(0, "end")
        self._i_nombre.insert(0, i["nombre"])

        # Stock — mostrar con decimales si aplica
        for entry, valor in [
            (self._i_stock,  i["stock"]),
            (self._i_minimo, i["stock_minimo"]),
        ]:
            entry.delete(0, "end")
            # Si es entero exacto, mostrar sin decimales
            v = int(valor) if valor == int(valor) else valor
            entry.insert(0, str(v))

    def _nuevo_insumo(self):
        self._limpiar_seleccion()
        self.tree.selection_remove(*self.tree.selection())
        self._lbl_modo_i.config(text="Nuevo insumo")
        for e in [self._i_nombre, self._i_stock, self._i_minimo]:
            e.delete(0, "end")
        self._combo_unidad.set("Gramos (g)")
        self._actualizar_labels_stock()

    def _guardar_insumo(self):
        from modules.inventario import crear_insumo, editar_insumo
        from modules.validaciones import leer_decimal, leer_texto

        nombre = leer_texto(self._i_nombre)
        stock  = leer_decimal(self._i_stock)
        minimo = leer_decimal(self._i_minimo)
        display = self._i_unidad_var.get()
        unidad  = self._unidades_map.get(display, "g")

        if not nombre:
            messagebox.showwarning("Campo vacio", "El nombre del insumo es obligatorio.")
            return

        try:
            if self._modo == "nuevo":
                iid = crear_insumo(nombre, stock, unidad, minimo)
                messagebox.showinfo("Creado", f"Insumo creado (ID {iid}).\nStock: {stock} {unidad}")
            else:
                editar_insumo(
                    self._insumo_sel,
                    nombre=nombre, stock=stock,
                    unidad=unidad, stock_minimo=minimo
                )
                messagebox.showinfo("Guardado", "Insumo actualizado.")
            self._cargar_insumos()
            self._nuevo_insumo()
        except Exception as e:
            messagebox.showerror("Error", str(e))


    # ══════════════════════════════════════════════════════════
    # PANEL COMBOS
    # ══════════════════════════════════════════════════════════

    def _configurar_columnas_combos(self):
        cols = {"cid": "#", "nombre": "Nombre", "precio": "Precio",
                "productos": "Productos", "estado": "Estado"}
        self.tree["columns"] = list(cols.keys())
        anchos = {"cid": 40, "nombre": 260, "precio": 110,
                  "productos": 90, "estado": 80}
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id == "nombre" else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=cols[col_id])

    def _cargar_combos(self):
        from modules.ventas import listar_combos
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for c in listar_combos(solo_activos=False):
            estado = "Activo" if c["activo"] else "Inactivo"
            self.tree.insert("", "end", iid=f"c{c['id']}", values=(
                c["id"], c["nombre"],
                formatear_pesos(c["precio"]),
                len(c["productos"]),
                estado
            ))

    def _construir_panel_combo(self):
        self._limpiar_panel()
        self._combo_lineas = []
        self._combo_sel    = None
        self._modo         = "nuevo"

        from modules.validaciones import aplicar_validacion

        self._lbl_modo_c = tk.Label(self._panel, text="Nuevo combo",
                                     font=FONT_BOLD, bg=COLORS["surface"],
                                     fg=COLORS["text"])
        self._lbl_modo_c.pack(anchor="w", padx=16, pady=(16, 12))

        # Nombre
        tk.Label(self._panel, text="Nombre del combo", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._c_nombre = self._input(self._panel)
        self._c_nombre.pack(fill="x", padx=16, pady=(2, 8), ipady=5)

        # Precio
        tk.Label(self._panel, text="Precio ($)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._c_precio = self._input(self._panel)
        self._c_precio.pack(fill="x", padx=16, pady=(2, 8), ipady=5)
        aplicar_validacion(self._c_precio, "monto")

        # Descripcion
        tk.Label(self._panel, text="Descripcion (opcional)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._c_desc = self._input(self._panel)
        self._c_desc.pack(fill="x", padx=16, pady=(2, 12), ipady=5)

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 10))

        # ── Agregar productos al combo ────────────────────────────────────────
        tk.Label(self._panel, text="Productos del combo", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))

        from modules.inventario import listar_productos
        prods = listar_productos()
        self._prods_combo_map = {p["nombre"]: p["id"] for p in prods}

        tk.Label(self._panel, text="Buscar producto", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._c_buscar = self._input(self._panel)
        self._c_buscar.pack(fill="x", padx=16, pady=(2, 4), ipady=5)
        self._c_buscar.bind("<KeyRelease>", self._filtrar_prods_combo)

        lst_wrap = tk.Frame(self._panel, bg=COLORS["surface"])
        lst_wrap.pack(fill="x", padx=16, pady=(0, 6))
        self._lst_prods_combo = tk.Listbox(
            lst_wrap, font=FONT_SMALL, height=4,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self._lst_prods_combo.pack(fill="x")
        self._prods_combo_lista = prods

        cant_frame = tk.Frame(self._panel, bg=COLORS["surface"])
        cant_frame.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(cant_frame, text="Cantidad:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._c_cant = self._input(cant_frame, width=5)
        self._c_cant.insert(0, "1")
        self._c_cant.pack(side="left", padx=(6, 0), ipady=4)
        aplicar_validacion(self._c_cant, "entero")

        self._btn_primary(self._panel, "+ Agregar producto",
                          self._agregar_prod_combo).pack(fill="x", padx=16, ipady=6)

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        # ── Tabla de productos del combo ──────────────────────────────────────
        tk.Label(self._panel, text="Contenido del combo", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))

        self._frame_tabla_combo = tk.Frame(self._panel, bg=COLORS["surface"])
        self._frame_tabla_combo.pack(fill="x", padx=16)

        self._lbl_resumen_combo = tk.Label(
            self._panel, text="Sin productos aun", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"]
        )
        self._lbl_resumen_combo.pack(anchor="w", padx=16, pady=(6, 0))

        tk.Frame(self._panel, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        if auth.es_admin():
            self._btn_primary(self._panel, "Guardar combo",
                              self._guardar_combo).pack(fill="x", padx=16, ipady=8)
            self._btn_danger(self._panel, "Desactivar combo",
                             self._desactivar_combo).pack(
                                 fill="x", padx=16, pady=(6, 0), ipady=6)

        tk.Button(self._panel, text="+ Nuevo (limpiar)",
                  font=FONT_SMALL, bg=COLORS["surface"],
                  fg=COLORS["text_muted"], relief="flat", cursor="hand2",
                  command=self._nuevo_combo).pack(pady=(8, 16))

        self._filtrar_prods_combo()
        self._refrescar_tabla_combo()

    def _filtrar_prods_combo(self, event=None):
        texto = self._c_buscar.get().strip().lower()
        self._lst_prods_combo.delete(0, "end")
        for p in self._prods_combo_lista:
            if not texto or texto in p["nombre"].lower():
                self._lst_prods_combo.insert("end",
                    f"{p['nombre']}  [{p['categoria_nombre']}]")

    def _agregar_prod_combo(self):
        from modules.validaciones import leer_entero
        sel = self._lst_prods_combo.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona un producto.")
            return
        nombre = self._lst_prods_combo.get(sel[0]).split("  [")[0].strip()
        prod_id = self._prods_combo_map.get(nombre)
        if not prod_id:
            return
        cantidad = leer_entero(self._c_cant, default=1)
        if cantidad <= 0:
            cantidad = 1
        # Si ya existe actualiza cantidad
        for linea in self._combo_lineas:
            if linea["producto_id"] == prod_id:
                linea["cantidad"] = cantidad
                self._refrescar_tabla_combo()
                return
        self._combo_lineas.append({
            "producto_id": prod_id,
            "nombre":      nombre,
            "cantidad":    cantidad,
        })
        self._c_cant.delete(0, "end")
        self._c_cant.insert(0, "1")
        self._refrescar_tabla_combo()

    def _quitar_prod_combo(self, producto_id: int):
        self._combo_lineas = [l for l in self._combo_lineas
                               if l["producto_id"] != producto_id]
        self._refrescar_tabla_combo()

    def _refrescar_tabla_combo(self):
        from modules.caja import formatear_pesos
        for w in self._frame_tabla_combo.winfo_children():
            w.destroy()
        if not self._combo_lineas:
            tk.Label(self._frame_tabla_combo, text="Sin productos aun",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_dim"]).pack(anchor="w")
        else:
            for linea in self._combo_lineas:
                fila = tk.Frame(self._frame_tabla_combo, bg=COLORS["surface2"],
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
                fila.pack(fill="x", pady=2, ipady=3)
                tk.Label(fila, text=linea["nombre"], font=FONT_SMALL,
                         bg=COLORS["surface2"], fg=COLORS["text"],
                         anchor="w").pack(side="left", padx=(8, 0),
                                          fill="x", expand=True)
                tk.Label(fila, text=f"x{linea['cantidad']}",
                         font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["accent"]).pack(side="left", padx=6)
                tk.Button(
                    fila, text="x", font=FONT_SMALL,
                    bg=COLORS["surface2"], fg=COLORS["danger"],
                    activebackground=COLORS["surface2"],
                    relief="flat", cursor="hand2", bd=0,
                    command=lambda pid=linea["producto_id"]: self._quitar_prod_combo(pid)
                ).pack(side="right", padx=(0, 6))

        n = len(self._combo_lineas)
        self._lbl_resumen_combo.config(
            text=f"{n} producto{'s' if n != 1 else ''} en el combo"
        )

    def _cargar_combo_en_panel(self, combo_id: int):
        from database import get_connection
        from modules.caja import formatear_pesos
        conn = get_connection()
        combo = conn.execute(
            "SELECT * FROM combos WHERE id = ?", (combo_id,)
        ).fetchone()
        prods = conn.execute("""
            SELECT cp.producto_id, cp.cantidad, p.nombre
            FROM combo_productos cp
            JOIN productos p ON cp.producto_id = p.id
            WHERE cp.combo_id = ?
        """, (combo_id,)).fetchall()
        conn.close()
        if not combo:
            return
        self._lbl_modo_c.config(text=f"Editando: {combo['nombre'][:22]}")
        self._c_nombre.delete(0, "end")
        self._c_nombre.insert(0, combo["nombre"])
        self._c_precio.delete(0, "end")
        self._c_precio.insert(0, str(int(combo["precio"])))
        self._c_desc.delete(0, "end")
        if combo["descripcion"]:
            self._c_desc.insert(0, combo["descripcion"])
        self._combo_lineas = [
            {"producto_id": p["producto_id"],
             "nombre":      p["nombre"],
             "cantidad":    p["cantidad"]}
            for p in prods
        ]
        self._refrescar_tabla_combo()

    def _nuevo_combo(self):
        self._limpiar_seleccion()
        self._combo_sel = None
        self._modo      = "nuevo"
        self.tree.selection_remove(*self.tree.selection())
        self._lbl_modo_c.config(text="Nuevo combo")
        for e in [self._c_nombre, self._c_precio, self._c_desc]:
            e.delete(0, "end")
        self._combo_lineas = []
        self._refrescar_tabla_combo()

    def _guardar_combo(self):
        from modules.validaciones import leer_entero, leer_texto
        from modules.ventas import crear_combo, editar_combo
        from database import get_connection

        nombre = leer_texto(self._c_nombre)
        precio = leer_entero(self._c_precio)
        desc   = leer_texto(self._c_desc) or None

        if not nombre:
            messagebox.showwarning("Campo vacio", "El nombre del combo es obligatorio.")
            return
        if precio <= 0:
            messagebox.showwarning("Precio invalido", "El precio debe ser mayor a 0.")
            return
        if not self._combo_lineas:
            messagebox.showwarning("Sin productos", "Agrega al menos un producto al combo.")
            return

        productos = [{"producto_id": l["producto_id"], "cantidad": l["cantidad"]}
                     for l in self._combo_lineas]
        try:
            if self._modo == "nuevo":
                cid = crear_combo(nombre, precio, productos, desc)
                messagebox.showinfo("Creado", f"Combo creado (ID {cid}).")
            else:
                editar_combo(self._combo_sel, nombre=nombre,
                             precio=precio, descripcion=desc)
                # Actualizar productos del combo
                conn = get_connection()
                conn.execute("DELETE FROM combo_productos WHERE combo_id = ?",
                             (self._combo_sel,))
                conn.executemany(
                    "INSERT INTO combo_productos (combo_id, producto_id, cantidad) VALUES (?,?,?)",
                    [(self._combo_sel, p["producto_id"], p["cantidad"]) for p in productos]
                )
                conn.commit()
                conn.close()
                messagebox.showinfo("Guardado", "Combo actualizado.")
            self._cargar_combos()
            self._nuevo_combo()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _desactivar_combo(self):
        if not self._combo_sel:
            messagebox.showwarning("Sin seleccion", "Selecciona un combo para desactivar.")
            return
        from modules.ventas import editar_combo
        from database import get_connection
        conn = get_connection()
        combo = conn.execute("SELECT nombre, activo FROM combos WHERE id = ?",
                             (self._combo_sel,)).fetchone()
        conn.close()
        if not combo:
            return
        nuevo_estado = 0 if combo["activo"] else 1
        accion = "desactivar" if nuevo_estado == 0 else "activar"
        if not messagebox.askyesno("Confirmar", f"Deseas {accion} el combo '{combo['nombre']}'?"):
            return
        editar_combo(self._combo_sel, activo=nuevo_estado)
        self._cargar_combos()
        self._nuevo_combo()
        texto_btn = "Desactivar combo" if nuevo_estado == 1 else "Activar combo"
        messagebox.showinfo("Listo", f"Combo {accion}do correctamente.")