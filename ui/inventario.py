"""
ui/inventario.py — El G POS
Gestión de inventario: Tienda · Insumos · Recetas · Combos.

Diseño pensado para pantallas de BAJA RESOLUCIÓN (1366x768): la tabla ocupa TODO
el ancho y los formularios de alta/edición se abren en ventanas emergentes
(ui.modal.ModalForm), con alto tope y botones de acción siempre visibles.
Se entra a crear con "+ Nuevo" y a editar con "✎ Editar" o doble-clic en la fila.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import auth
from ui.base import (
    FrameBase, COLORS,
    FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI,
)
from ui.modal import ModalForm


class FrameInventario(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Inventario", "Tienda, insumos, recetas y combos")
        self._producto_sel       = None
        self._insumo_sel         = None
        self._combo_sel          = None
        self._producto_receta_id = None
        self._receta_lineas      = []
        self._combo_lineas       = []
        self._modo               = "nuevo"
        self._modal              = None
        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

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
            "iid":    "#",
            "nombre": "Nombre",
            "unidad": "Unidad",
            "costo":  "Costo/unidad",
        }

        cont = tk.Frame(self, bg=COLORS["bg"])
        cont.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Barra de pestañas + acciones ───────────────────────────────────
        tab_frame = tk.Frame(cont, bg=COLORS["bg"])
        tab_frame.pack(fill="x", pady=(0, 10))
        self._tab = tk.StringVar(value="tienda")
        for texto, valor in [
            ("Tienda",   "tienda"),
            ("Insumos",  "insumos"),
            ("Recetas",  "recetas"),
            ("Combos",   "combos"),
        ]:
            tk.Radiobutton(
                tab_frame, text=texto, variable=self._tab, value=valor,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._cambiar_tab, padx=14, pady=6,
            ).pack(side="left", padx=(0, 4))

        # Acciones a la derecha (Importar solo admin; Nuevo solo admin).
        if auth.es_admin():
            self._btn_secondary(
                tab_frame, "⭱  Importar Excel", self._importar_excel
            ).pack(side="right", ipady=4, ipadx=6)
            self._btn_primary(
                tab_frame, "+ Nuevo", self._nuevo
            ).pack(side="right", padx=(0, 8), ipady=4, ipadx=12)
        self._btn_secondary(
            tab_frame, "✎ Editar", self._editar
        ).pack(side="right", padx=(0, 8), ipady=4, ipadx=12)

        # ── Barra de búsqueda ───────────────────────────────────────────────
        buscar_row = tk.Frame(cont, bg=COLORS["bg"])
        buscar_row.pack(fill="x", pady=(0, 6))
        tk.Label(buscar_row, text="Buscar:", font=FONT_SMALL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left", padx=(0, 6))
        self._entry_buscar = self._input(buscar_row)
        self._entry_buscar.pack(side="left", fill="x", expand=True, ipady=5)
        self._entry_buscar.bind("<KeyRelease>", lambda e: self._filtrar())
        tk.Button(buscar_row, text="✕", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self._limpiar_busqueda).pack(side="left", padx=(4, 0))

        # ── Tabla a todo el ancho ───────────────────────────────────────────
        tabla_wrap = tk.Frame(cont, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)
        self.tree = self._tabla(tabla_wrap, list(self._cols_prods.keys()), alto=10)
        self.tree.bind("<Double-1>", lambda e: self._editar())
        self._configurar_columnas_prods()
        self._cargar_tienda()

    # ── Cambio de pestaña / búsqueda ────────────────────────────────────────

    def _filtrar(self):
        texto = self._entry_buscar.get().strip().lower()
        tab = self._tab.get()
        if tab == "tienda":
            self._cargar_tienda(filtro=texto)
        elif tab == "insumos":
            self._cargar_insumos(filtro=texto)
        elif tab == "recetas":
            self._cargar_cocina(filtro=texto)
        else:
            self._cargar_combos(filtro=texto)

    def _limpiar_busqueda(self):
        if hasattr(self, "_entry_buscar"):
            self._entry_buscar.delete(0, "end")
        self._filtrar()

    def _cambiar_tab(self):
        self._limpiar_busqueda()
        tab = self._tab.get()
        if tab == "tienda":
            self._configurar_columnas_prods()
            self._cargar_tienda()
        elif tab == "insumos":
            self._configurar_columnas_insumos()
            self._cargar_insumos()
        elif tab == "recetas":
            self._configurar_columnas_prods_cocina()
            self._cargar_cocina()
        else:
            self._configurar_columnas_combos()
            self._cargar_combos()

    # ── Acciones Nuevo / Editar ─────────────────────────────────────────────

    def _nuevo(self):
        tab = self._tab.get()
        if tab == "tienda":
            self._modal_producto()
        elif tab == "insumos":
            self._modal_insumo()
        elif tab == "recetas":
            self._modal_plato()
        else:
            self._modal_combo()

    def _editar(self):
        iid = self.tree.focus()
        if not iid:
            messagebox.showinfo(
                "Selecciona una fila",
                "Elige una fila de la tabla para editarla (o haz doble-clic).")
            return
        tab = self._tab.get()
        if tab == "tienda":
            self._modal_producto(int(iid))
        elif tab == "insumos":
            self._modal_insumo(int(iid.replace("i", "")))
        elif tab == "recetas":
            self._modal_plato(int(iid))
        else:
            self._modal_combo(int(iid.replace("c", "")))

    # ── Importar desde Excel ──────────────────────────────────────────────────

    def _importar_excel(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona el Excel de inventario",
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
        )
        if not ruta:
            return
        if not messagebox.askyesno(
            "Importar inventario",
            "Se importarán los productos e insumos del archivo.\n\n"
            "Los que ya existan (por código o nombre) se actualizarán; "
            "no se duplican.\n\n¿Continuar?",
        ):
            return
        try:
            from modules.importador import importar_inventario
            res = importar_inventario(ruta)
        except Exception as e:
            messagebox.showerror("Error al importar", str(e))
            return

        resumen = (
            f"Productos: {res['productos_nuevos']} nuevos, "
            f"{res['productos_actualizados']} actualizados\n"
            f"Insumos: {res['insumos_nuevos']} nuevos, "
            f"{res['insumos_actualizados']} actualizados\n"
            f"Categorías creadas: {res['categorias_creadas']}"
        )
        if res.get("categorias_ajustadas"):
            resumen += f", ajustadas: {res['categorias_ajustadas']}"
        if res.get("recetas_lineas"):
            resumen += f"\nRecetas: {res['recetas_lineas']} líneas vinculadas"
        if res["omitidos"]:
            n = len(res["omitidos"])
            muestra = "\n".join(f"  • {o}" for o in res["omitidos"][:8])
            extra = f"\n  … y {n - 8} más" if n > 8 else ""
            resumen += (
                f"\n\nOmitidos ({n}, sin precio de venta):\n{muestra}{extra}"
            )
        messagebox.showinfo("Importación completada", resumen)

        # Refrescar la vista actual (recarga tabla + categorías nuevas)
        self._cambiar_tab()

    # ── Configuración de columnas ─────────────────────────────────────────────

    def _configurar_columnas_prods(self):
        self.tree["columns"] = list(self._cols_prods.keys())
        anchos = {
            "pid": 35, "nombre": 180, "categoria": 120,
            "precio_venta": 100, "costo": 90, "stock": 60,
            "minimo": 50, "margen": 70, "activo": 70,
        }
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id == "nombre" else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=self._cols_prods[col_id])

    def _configurar_columnas_insumos(self):
        self.tree["columns"] = list(self._cols_insumos.keys())
        anchos = {"iid": 35, "nombre": 260, "unidad": 120, "costo": 130}
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id == "nombre" else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=self._cols_insumos[col_id])

    def _configurar_columnas_prods_cocina(self):
        self.tree["columns"] = list(self._cols_prods.keys())
        anchos = {
            "pid": 35, "nombre": 220, "categoria": 140,
            "precio_venta": 100, "costo": 90, "stock": 60,
            "minimo": 50, "margen": 70, "activo": 70,
        }
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id == "nombre" else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=self._cols_prods[col_id])

    def _configurar_columnas_combos(self):
        cols = {"cid": "#", "nombre": "Nombre", "precio": "Precio",
                "productos": "Productos", "estado": "Estado"}
        self.tree["columns"] = list(cols.keys())
        anchos = {"cid": 40, "nombre": 260, "precio": 110, "productos": 90, "estado": 80}
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id == "nombre" else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=cols[col_id])

    # ── Carga de datos ────────────────────────────────────────────────────────

    def _cargar_tienda(self, filtro=""):
        from modules.inventario import listar_productos, calcular_margen
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for p in listar_productos(tipo="tienda", solo_activos=False):
            if filtro and filtro not in f"{p['nombre']} {p['categoria_nombre']} {p.get('codigo','')}".lower():
                continue
            margen = calcular_margen(p["precio_venta"], p["precio_costo"])
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["nombre"], p["categoria_nombre"],
                formatear_pesos(p["precio_venta"]),
                formatear_pesos(p["precio_costo"]),
                p["stock"], p["stock_minimo"],
                f"{margen}%",
                "Activo" if p["activo"] else "Inactivo",
            ))

    def _cargar_cocina(self, filtro=""):
        from modules.inventario import listar_productos, calcular_margen
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for p in listar_productos(tipo="cocina", solo_activos=False):
            if filtro and filtro not in f"{p['nombre']} {p['categoria_nombre']} {p.get('codigo','')}".lower():
                continue
            margen = calcular_margen(p["precio_venta"], p["precio_costo"])
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["nombre"], p["categoria_nombre"],
                formatear_pesos(p["precio_venta"]),
                formatear_pesos(p["precio_costo"]),
                p["stock"], p["stock_minimo"],
                f"{margen}%",
                "Activo" if p["activo"] else "Inactivo",
            ))

    def _cargar_insumos(self, filtro=""):
        from modules.inventario import listar_insumos
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for i in listar_insumos(solo_activos=False):
            if filtro and filtro not in f"{i['nombre']} {i['unidad']}".lower():
                continue
            costo = i.get("costo_unitario", 0) or 0
            costo_txt = f"{formatear_pesos(costo)} /{i['unidad']}" if costo else "—"
            self.tree.insert("", "end", iid=f"i{i['id']}", values=(
                i["id"], i["nombre"],
                i["unidad"],
                costo_txt,
            ))

    def _cargar_combos(self, filtro=""):
        from modules.ventas import listar_combos
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for c in listar_combos(solo_activos=False):
            if filtro and filtro not in c["nombre"].lower():
                continue
            self.tree.insert("", "end", iid=f"c{c['id']}", values=(
                c["id"], c["nombre"],
                formatear_pesos(c["precio"]),
                len(c["productos"]),
                "Activo" if c["activo"] else "Inactivo",
            ))

    # ══════════════════════════════════════════════════════════
    # MODAL — TIENDA (productos tipo tienda)
    # ══════════════════════════════════════════════════════════

    def _modal_producto(self, producto_id=None):
        from modules.validaciones import aplicar_validacion
        from modules.inventario import listar_categorias

        editar = producto_id is not None
        self._producto_sel = producto_id
        self._modo = "editar" if editar else "nuevo"

        m = ModalForm(self, "Editar producto" if editar else "Nuevo producto",
                      ancho=440)
        self._modal = m
        body = m.body

        def campo(label, attr, tipo_val=None):
            tk.Label(body, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16, pady=(8, 0))
            e = self._input(body)
            e.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
            if tipo_val:
                aplicar_validacion(e, tipo_val)
            setattr(self, attr, e)

        campo("Nombre *",           "_p_nombre")
        campo("Código (SKU)",       "_p_codigo",  "codigo")
        campo("Precio venta ($) *", "_p_pventa",  "monto")
        campo("Precio costo ($)",   "_p_pcosto",  "monto")
        campo("Stock inicial",      "_p_stock",   "entero")
        campo("Stock mínimo",       "_p_minimo",  "entero")

        cats = listar_categorias(tipo="tienda")
        self._cats_map = {c["nombre"]: c["id"] for c in cats}
        self._p_cat_var = tk.StringVar()
        tk.Label(body, text="Categoría", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(8, 0))
        self._combo_cat = ttk.Combobox(
            body, textvariable=self._p_cat_var,
            values=list(self._cats_map.keys()),
            font=FONT_LABEL, state="readonly",
        )
        if cats:
            self._combo_cat.set(cats[0]["nombre"])
        self._combo_cat.pack(fill="x", padx=16, pady=(2, 16))

        if auth.es_admin():
            self._btn_primary(m.footer, "Guardar",
                              self._guardar_producto).pack(
                                  side="right", ipady=6, ipadx=16)
            if editar:
                self._btn_danger(m.footer, "Desactivar",
                                 self._desactivar_producto).pack(
                                     side="right", padx=(0, 8), ipady=6, ipadx=10)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        if editar:
            self._cargar_producto_en_form(producto_id)
        m.mostrar()

    def _cargar_producto_en_form(self, producto_id: int):
        from modules.inventario import obtener_producto
        p = obtener_producto(producto_id)
        if not p:
            return
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
        if p["categoria_nombre"] in self._cats_map:
            self._combo_cat.set(p["categoria_nombre"])

    def _guardar_producto(self):
        from modules.inventario import crear_producto, editar_producto
        from modules.validaciones import leer_entero, leer_texto

        nombre = leer_texto(self._p_nombre)
        codigo = leer_texto(self._p_codigo) or None
        pventa = leer_entero(self._p_pventa)
        pcosto = leer_entero(self._p_pcosto)
        stock  = leer_entero(self._p_stock)
        minimo = leer_entero(self._p_minimo)
        cat_id = self._cats_map.get(self._p_cat_var.get())

        if not nombre:
            messagebox.showwarning("Campo vacío", "El nombre del producto es obligatorio.")
            return
        if not cat_id:
            messagebox.showwarning("Categoría", "Selecciona una categoría.")
            return
        if pventa <= 0:
            messagebox.showwarning("Precio inválido", "El precio de venta debe ser mayor a 0.")
            return
        try:
            if self._modo == "nuevo":
                pid = crear_producto(nombre, cat_id, pventa, pcosto, stock, minimo, codigo)
                messagebox.showinfo("Creado", f"✓ Producto '{nombre}' creado (ID {pid}).")
            else:
                editar_producto(
                    self._producto_sel,
                    nombre=nombre, codigo=codigo,
                    precio_venta=pventa, precio_costo=pcosto,
                    stock=stock, stock_minimo=minimo,
                    categoria_id=cat_id,
                )
                messagebox.showinfo("Guardado", "✓ Producto actualizado.")
            self._cargar_tienda()
            self._cerrar_modal()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _desactivar_producto(self):
        if not self._producto_sel:
            messagebox.showwarning("Sin selección", "Selecciona un producto para desactivar.")
            return
        from modules.inventario import obtener_producto, desactivar_producto
        p = obtener_producto(self._producto_sel)
        if not messagebox.askyesno("Confirmar",
                                    f"¿Desactivar '{p['nombre']}'?\n"
                                    "No aparecerá en ventas pero se conserva el historial."):
            return
        desactivar_producto(self._producto_sel)
        messagebox.showinfo("Desactivado", "✓ Producto desactivado.")
        self._cargar_tienda()
        self._cerrar_modal()

    # ══════════════════════════════════════════════════════════
    # MODAL — INSUMOS
    # ══════════════════════════════════════════════════════════

    def _modal_insumo(self, insumo_id=None):
        from modules.validaciones import aplicar_validacion

        editar = insumo_id is not None
        self._insumo_sel = insumo_id
        self._modo = "editar" if editar else "nuevo"

        m = ModalForm(self, "Editar insumo" if editar else "Nuevo insumo",
                      ancho=440)
        self._modal = m
        body = m.body

        UNIDADES = [
            ("g",       "Gramos (g)"),
            ("kg",      "Kilogramos (kg)"),
            ("ml",      "Mililitros (ml)"),
            ("l",       "Litros (l)"),
            ("unidad",  "Unidad"),
            ("porcion", "Porción"),
        ]
        self._unidades_map     = {u[1]: u[0] for u in UNIDADES}
        self._unidades_map_inv = {u[0]: u[1] for u in UNIDADES}

        tk.Label(body, text="Unidad base", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(8, 0))
        self._i_unidad_var = tk.StringVar(value="Gramos (g)")
        self._combo_unidad = ttk.Combobox(
            body, textvariable=self._i_unidad_var,
            values=[u[1] for u in UNIDADES],
            font=FONT_LABEL, state="readonly",
        )
        self._combo_unidad.pack(fill="x", padx=16, pady=(2, 4))
        self._combo_unidad.bind("<<ComboboxSelected>>", self._on_unidad_change)

        self._lbl_ayuda_unidad = tk.Label(
            body,
            text="Unidad base del insumo (en la que se mide la receta).",
            font=("Segoe UI", 8), bg=COLORS["surface"],
            fg=COLORS["text_dim"], justify="left",
        )
        self._lbl_ayuda_unidad.pack(anchor="w", padx=16, pady=(0, 8))

        tk.Label(body, text="Nombre del insumo *", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._i_nombre = self._input(body)
        self._i_nombre.pack(fill="x", padx=16, pady=(2, 8), ipady=5)

        self._lbl_costo_i = tk.Label(body, text="Costo por unidad ($/g)",
                                     font=FONT_SMALL, bg=COLORS["surface"],
                                     fg=COLORS["text_muted"])
        self._lbl_costo_i.pack(anchor="w", padx=16)
        self._i_costo = self._input(body)
        self._i_costo.pack(fill="x", padx=16, pady=(2, 4), ipady=5)
        aplicar_validacion(self._i_costo, "decimal")

        tk.Label(body,
                 text="Este costo define el costo de los platos. Normalmente se "
                      "actualiza solo al recibir compras del proveedor; aquí puedes "
                      "ajustarlo a mano si hace falta.",
                 font=("Segoe UI", 8), bg=COLORS["surface"], fg=COLORS["text_dim"],
                 justify="left", wraplength=390).pack(anchor="w", padx=16, pady=(0, 12))

        if auth.es_admin():
            self._btn_primary(m.footer, "Guardar",
                              self._guardar_insumo).pack(
                                  side="right", ipady=6, ipadx=16)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        if editar:
            self._cargar_insumo_en_form(insumo_id)
        else:
            self._actualizar_labels_stock()
        m.mostrar()

    def _on_unidad_change(self, event=None):
        self._actualizar_labels_stock()

    def _actualizar_labels_stock(self):
        display = self._i_unidad_var.get()
        codigo  = self._unidades_map.get(display, "g")
        self._lbl_costo_i.config(text=f"Costo por unidad ($/{codigo})")

    def _cargar_insumo_en_form(self, insumo_id: int):
        from modules.inventario import obtener_insumo
        i = obtener_insumo(insumo_id)
        if not i:
            return
        display = self._unidades_map_inv.get(i["unidad"], i["unidad"])
        self._combo_unidad.set(display)
        self._actualizar_labels_stock()
        self._i_nombre.delete(0, "end")
        self._i_nombre.insert(0, i["nombre"])
        costo = i.get("costo_unitario", 0) or 0
        self._i_costo.delete(0, "end")
        v = int(costo) if costo == int(costo) else costo
        self._i_costo.insert(0, str(v))

    def _guardar_insumo(self):
        from modules.inventario import crear_insumo, editar_insumo
        from modules.validaciones import leer_decimal, leer_texto

        nombre  = leer_texto(self._i_nombre)
        costo   = leer_decimal(self._i_costo)
        display = self._i_unidad_var.get()
        unidad  = self._unidades_map.get(display, "g")

        if not nombre:
            messagebox.showwarning("Campo vacío", "El nombre del insumo es obligatorio.")
            return
        try:
            if self._modo == "nuevo":
                iid = crear_insumo(nombre, unidad=unidad, costo_unitario=costo)
                messagebox.showinfo("Creado", f"Insumo creado (ID {iid}).")
            else:
                editar_insumo(
                    self._insumo_sel,
                    nombre=nombre, unidad=unidad, costo_unitario=costo,
                )
                messagebox.showinfo("Guardado", "Insumo actualizado.")
            self._cargar_insumos()
            self._cerrar_modal()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ══════════════════════════════════════════════════════════
    # MODAL — RECETAS (platos de cocina + sus ingredientes)
    # ══════════════════════════════════════════════════════════

    def _modal_plato(self, producto_id=None):
        """Modal: crear/editar plato de cocina + gestionar su receta."""
        from modules.validaciones import aplicar_validacion
        from modules.inventario import listar_categorias, listar_insumos

        editar = producto_id is not None
        self._producto_receta_id = producto_id
        self._modo = "editar" if editar else "nuevo"
        self._receta_lineas = []

        m = ModalForm(self, "Editar plato" if editar else "Nuevo plato",
                      ancho=460)
        self._modal = m
        body = m.body

        # ── Datos del plato ───────────────────────────────────────────────────
        def campo(label, attr, tipo_val=None):
            tk.Label(body, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16, pady=(8, 0))
            e = self._input(body)
            e.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
            if tipo_val:
                aplicar_validacion(e, tipo_val)
            setattr(self, attr, e)

        campo("Nombre del plato *",    "_r_nombre")
        campo("Precio de venta ($) *", "_r_pventa", "monto")
        campo("Stock mínimo",          "_r_minimo", "entero")
        self._r_minimo.insert(0, "0")

        cats = listar_categorias(tipo="cocina")
        self._cats_cocina_map = {c["nombre"]: c["id"] for c in cats}
        self._r_cat_var = tk.StringVar()
        tk.Label(body, text="Categoría", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(8, 0))
        self._combo_cat_r = ttk.Combobox(
            body, textvariable=self._r_cat_var,
            values=list(self._cats_cocina_map.keys()),
            font=FONT_LABEL, state="readonly",
        )
        if cats:
            self._combo_cat_r.set(cats[0]["nombre"])
        self._combo_cat_r.pack(fill="x", padx=16, pady=(2, 12))

        tk.Frame(body, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 10))

        # ── Sección ingredientes ──────────────────────────────────────────────
        tk.Label(body, text="Ingredientes (insumos)", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))

        insumos = listar_insumos()
        self._insumos_lista_r = insumos
        self._insumos_map_r   = {i["nombre"]: i for i in insumos}

        tk.Label(body, text="Buscar insumo", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._entry_buscar_insumo_r = self._input(body)
        self._entry_buscar_insumo_r.pack(fill="x", padx=16, pady=(2, 4), ipady=5)
        self._entry_buscar_insumo_r.bind("<KeyRelease>", self._filtrar_insumos_r)

        lst_wrap = tk.Frame(body, bg=COLORS["surface"])
        lst_wrap.pack(fill="x", padx=16, pady=(0, 6))
        self._lst_insumos_r = tk.Listbox(
            lst_wrap, font=FONT_SMALL, height=5,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self._lst_insumos_r.pack(fill="x")

        cant_frame = tk.Frame(body, bg=COLORS["surface"])
        cant_frame.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(cant_frame, text="Cantidad:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._entry_cant_r = self._input(cant_frame, width=6)
        self._entry_cant_r.insert(0, "1")
        self._entry_cant_r.pack(side="left", padx=(6, 0), ipady=4)
        aplicar_validacion(self._entry_cant_r, "decimal")

        self._btn_primary(body, "+ Agregar ingrediente",
                          self._agregar_insumo_r).pack(fill="x", padx=16, ipady=6)

        tk.Frame(body, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        # ── Lista de ingredientes de la receta ────────────────────────────────
        tk.Label(body, text="Receta actual", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))

        self._frame_tabla_r = tk.Frame(body, bg=COLORS["surface"])
        self._frame_tabla_r.pack(fill="x", padx=16)

        self._lbl_resumen_r = tk.Label(
            body, text="", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["success"],
        )
        self._lbl_resumen_r.pack(anchor="w", padx=16, pady=(6, 12))

        if auth.es_admin():
            self._btn_primary(m.footer, "Guardar",
                              self._guardar_plato).pack(
                                  side="right", ipady=6, ipadx=16)
            if editar:
                self._btn_danger(m.footer, "Desactivar",
                                 self._desactivar_plato).pack(
                                     side="right", padx=(0, 8), ipady=6, ipadx=10)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        if editar:
            self._cargar_plato_en_panel(producto_id)
        self._filtrar_insumos_r()
        self._refrescar_tabla_r()
        m.mostrar()

    def _cargar_plato_en_panel(self, producto_id: int):
        from modules.inventario import obtener_producto, obtener_receta

        producto = obtener_producto(producto_id)
        if not producto:
            return

        self._producto_receta_id = producto_id
        for entry, valor in [
            (self._r_nombre, producto["nombre"]),
            (self._r_pventa, str(int(producto["precio_venta"]))),
            (self._r_minimo, str(int(producto["stock_minimo"])
                                 if producto["stock_minimo"] == int(producto["stock_minimo"])
                                 else round(producto["stock_minimo"], 2))),
        ]:
            entry.delete(0, "end")
            entry.insert(0, valor)

        if producto["categoria_nombre"] in self._cats_cocina_map:
            self._combo_cat_r.set(producto["categoria_nombre"])

        receta = obtener_receta(producto_id)
        self._receta_lineas = [
            {"insumo_id": r["insumo_id"], "nombre": r["insumo_nombre"],
             "cantidad": r["cantidad"], "unidad": r["unidad"]}
            for r in receta
        ]

    def _guardar_plato(self):
        from modules.inventario import crear_producto, editar_producto, guardar_receta
        from modules.validaciones import leer_entero, leer_texto

        nombre = leer_texto(self._r_nombre)
        pventa = leer_entero(self._r_pventa)
        minimo = leer_entero(self._r_minimo)
        cat_id = self._cats_cocina_map.get(self._r_cat_var.get())

        if not nombre:
            messagebox.showwarning("Campo vacío", "El nombre del plato es obligatorio.")
            return
        if pventa <= 0:
            messagebox.showwarning("Precio inválido", "El precio de venta debe ser mayor a 0.")
            return
        if not cat_id:
            messagebox.showwarning("Categoría", "Selecciona una categoría de cocina.")
            return

        receta = [
            {"insumo_id": l["insumo_id"], "cantidad": float(l["cantidad"])}
            for l in self._receta_lineas
            if l["cantidad"] > 0
        ]

        try:
            if self._modo == "nuevo" or not self._producto_receta_id:
                pid = crear_producto(nombre, cat_id, pventa, 0, 0, minimo)
                if receta:
                    guardar_receta(pid, receta)
                messagebox.showinfo("Creado", f"✓ Plato '{nombre}' creado.")
            else:
                editar_producto(
                    self._producto_receta_id,
                    nombre=nombre,
                    precio_venta=pventa,
                    stock_minimo=minimo,
                    categoria_id=cat_id,
                )
                guardar_receta(self._producto_receta_id, receta)
                messagebox.showinfo("Guardado", "✓ Plato y receta actualizados.")
            self._cargar_cocina()
            self._cerrar_modal()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _desactivar_plato(self):
        if not self._producto_receta_id:
            messagebox.showwarning("Sin selección", "Selecciona un plato de la tabla.")
            return
        from modules.inventario import obtener_producto, desactivar_producto
        p = obtener_producto(self._producto_receta_id)
        if not p:
            return
        if not messagebox.askyesno("Confirmar",
                                    f"¿Desactivar '{p['nombre']}'?\n"
                                    "No aparecerá en ventas pero se conserva el historial."):
            return
        desactivar_producto(self._producto_receta_id)
        messagebox.showinfo("Desactivado", "✓ Plato desactivado.")
        self._cargar_cocina()
        self._cerrar_modal()

    # ── Helpers: ingredientes ─────────────────────────────────────────────────

    def _filtrar_insumos_r(self, event=None):
        texto = self._entry_buscar_insumo_r.get().strip().lower()
        self._lst_insumos_r.delete(0, "end")
        for i in self._insumos_lista_r:
            if not texto or texto in i["nombre"].lower():
                self._lst_insumos_r.insert("end", f"{i['nombre']}  ({i['unidad']})")

    def _agregar_insumo_r(self):
        from modules.validaciones import leer_decimal
        sel = self._lst_insumos_r.curselection()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona un insumo de la lista.")
            return
        nombre = self._lst_insumos_r.get(sel[0]).split("  (")[0].strip()
        insumo = self._insumos_map_r.get(nombre)
        if not insumo:
            return
        cantidad = leer_decimal(self._entry_cant_r, default=1.0)
        if cantidad <= 0:
            cantidad = 1.0
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
        self._receta_lineas = [l for l in self._receta_lineas
                                if l["insumo_id"] != insumo_id]
        self._refrescar_tabla_r()

    def _refrescar_tabla_r(self):
        for w in self._frame_tabla_r.winfo_children():
            w.destroy()
        if not self._receta_lineas:
            tk.Label(self._frame_tabla_r, text="Sin ingredientes aún",
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
                         anchor="w").pack(side="left", padx=(8, 0), fill="x", expand=True)
                tk.Label(fila, text=f"×{linea['cantidad']} {linea['unidad']}",
                         font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["accent"]).pack(side="left", padx=6)
                tk.Button(
                    fila, text="✕", font=FONT_SMALL,
                    bg=COLORS["surface2"], fg=COLORS["danger"],
                    activebackground=COLORS["surface2"],
                    relief="flat", cursor="hand2", bd=0,
                    command=lambda iid=linea["insumo_id"]: self._quitar_insumo_r(iid),
                ).pack(side="right", padx=(0, 6))
        n = len(self._receta_lineas)
        self._lbl_resumen_r.config(
            text=f"{n} ingrediente{'s' if n != 1 else ''}" if n else "")

    # ══════════════════════════════════════════════════════════
    # MODAL — COMBOS
    # ══════════════════════════════════════════════════════════

    def _modal_combo(self, combo_id=None):
        from modules.validaciones import aplicar_validacion

        editar = combo_id is not None
        self._combo_sel = combo_id
        self._modo = "editar" if editar else "nuevo"
        self._combo_lineas = []

        m = ModalForm(self, "Editar combo" if editar else "Nuevo combo",
                      ancho=460)
        self._modal = m
        body = m.body

        def campo(label, attr, tipo_val=None):
            tk.Label(body, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16, pady=(8, 0))
            e = self._input(body)
            e.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
            if tipo_val:
                aplicar_validacion(e, tipo_val)
            setattr(self, attr, e)

        campo("Nombre del combo *",     "_c_nombre")
        campo("Precio ($) *",           "_c_precio",  "monto")
        campo("Descripción (opcional)", "_c_desc")

        tk.Frame(body, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(10, 10))

        # Buscador de productos (tienda + cocina)
        tk.Label(body, text="Agregar productos al combo", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))

        from modules.inventario import listar_productos
        prods = listar_productos()
        self._prods_combo_lista = prods
        self._prods_combo_map   = {p["nombre"]: p["id"] for p in prods}

        tk.Label(body, text="Buscar producto", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self._c_buscar = self._input(body)
        self._c_buscar.pack(fill="x", padx=16, pady=(2, 4), ipady=5)
        self._c_buscar.bind("<KeyRelease>", self._filtrar_prods_combo)

        lst_wrap = tk.Frame(body, bg=COLORS["surface"])
        lst_wrap.pack(fill="x", padx=16, pady=(0, 6))
        self._lst_prods_combo = tk.Listbox(
            lst_wrap, font=FONT_SMALL, height=4,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self._lst_prods_combo.pack(fill="x")

        cant_frame = tk.Frame(body, bg=COLORS["surface"])
        cant_frame.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(cant_frame, text="Cantidad:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._c_cant = self._input(cant_frame, width=5)
        self._c_cant.insert(0, "1")
        self._c_cant.pack(side="left", padx=(6, 0), ipady=4)
        aplicar_validacion(self._c_cant, "entero")

        self._btn_primary(body, "+ Agregar producto",
                          self._agregar_prod_combo).pack(fill="x", padx=16, ipady=6)

        tk.Frame(body, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=10)

        tk.Label(body, text="Contenido del combo", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))

        self._frame_tabla_combo = tk.Frame(body, bg=COLORS["surface"])
        self._frame_tabla_combo.pack(fill="x", padx=16)

        self._lbl_resumen_combo = tk.Label(
            body, text="Sin productos aún", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"],
        )
        self._lbl_resumen_combo.pack(anchor="w", padx=16, pady=(6, 12))

        if auth.es_admin():
            self._btn_primary(m.footer, "Guardar",
                              self._guardar_combo).pack(
                                  side="right", ipady=6, ipadx=16)
            if editar:
                self._btn_danger(m.footer, "Activar / Desactivar",
                                 self._desactivar_combo).pack(
                                     side="right", padx=(0, 8), ipady=6, ipadx=10)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        if editar:
            self._cargar_combo_en_panel(combo_id)
        self._filtrar_prods_combo()
        self._refrescar_tabla_combo()
        m.mostrar()

    def _filtrar_prods_combo(self, event=None):
        texto = self._c_buscar.get().strip().lower()
        self._lst_prods_combo.delete(0, "end")
        for p in self._prods_combo_lista:
            if not texto or texto in p["nombre"].lower():
                tipo = "🏪" if p["categoria_tipo"] == "tienda" else "🍽"
                self._lst_prods_combo.insert(
                    "end", f"{tipo} {p['nombre']}  [{p['categoria_nombre']}]")

    def _agregar_prod_combo(self):
        from modules.validaciones import leer_entero
        sel = self._lst_prods_combo.curselection()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona un producto.")
            return
        etiqueta = self._lst_prods_combo.get(sel[0])
        # Strip leading emoji and spaces before looking up name
        nombre = etiqueta.split("  [")[0].strip().lstrip("🏪🍽 ")
        prod_id = self._prods_combo_map.get(nombre)
        if not prod_id:
            return
        cantidad = leer_entero(self._c_cant, default=1)
        if cantidad <= 0:
            cantidad = 1
        for linea in self._combo_lineas:
            if linea["producto_id"] == prod_id:
                linea["cantidad"] = cantidad
                self._refrescar_tabla_combo()
                return
        self._combo_lineas.append({"producto_id": prod_id, "nombre": nombre, "cantidad": cantidad})
        self._c_cant.delete(0, "end")
        self._c_cant.insert(0, "1")
        self._refrescar_tabla_combo()

    def _quitar_prod_combo(self, producto_id: int):
        self._combo_lineas = [l for l in self._combo_lineas
                               if l["producto_id"] != producto_id]
        self._refrescar_tabla_combo()

    def _refrescar_tabla_combo(self):
        for w in self._frame_tabla_combo.winfo_children():
            w.destroy()
        if not self._combo_lineas:
            tk.Label(self._frame_tabla_combo, text="Sin productos aún",
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
                         anchor="w").pack(side="left", padx=(8, 0), fill="x", expand=True)
                tk.Label(fila, text=f"×{linea['cantidad']}",
                         font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["accent"]).pack(side="left", padx=6)
                tk.Button(
                    fila, text="✕", font=FONT_SMALL,
                    bg=COLORS["surface2"], fg=COLORS["danger"],
                    activebackground=COLORS["surface2"],
                    relief="flat", cursor="hand2", bd=0,
                    command=lambda pid=linea["producto_id"]: self._quitar_prod_combo(pid),
                ).pack(side="right", padx=(0, 6))
        n = len(self._combo_lineas)
        self._lbl_resumen_combo.config(
            text=f"{n} producto{'s' if n != 1 else ''} en el combo")

    def _cargar_combo_en_panel(self, combo_id: int):
        from database import get_connection
        conn = get_connection()
        combo = conn.execute("SELECT * FROM combos WHERE id = ?", (combo_id,)).fetchone()
        prods = conn.execute("""
            SELECT cp.producto_id, cp.cantidad, p.nombre
            FROM combo_productos cp
            JOIN productos p ON cp.producto_id = p.id
            WHERE cp.combo_id = ?
        """, (combo_id,)).fetchall()
        conn.close()
        if not combo:
            return
        self._c_nombre.delete(0, "end")
        self._c_nombre.insert(0, combo["nombre"])
        self._c_precio.delete(0, "end")
        self._c_precio.insert(0, str(int(combo["precio"])))
        self._c_desc.delete(0, "end")
        if combo["descripcion"]:
            self._c_desc.insert(0, combo["descripcion"])
        self._combo_lineas = [
            {"producto_id": p["producto_id"], "nombre": p["nombre"], "cantidad": p["cantidad"]}
            for p in prods
        ]

    def _guardar_combo(self):
        from modules.validaciones import leer_entero, leer_texto
        from modules.ventas import crear_combo, editar_combo
        from database import get_connection

        nombre = leer_texto(self._c_nombre)
        precio = leer_entero(self._c_precio)
        desc   = leer_texto(self._c_desc) or None

        if not nombre:
            messagebox.showwarning("Campo vacío", "El nombre del combo es obligatorio.")
            return
        if precio <= 0:
            messagebox.showwarning("Precio inválido", "El precio debe ser mayor a 0.")
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
                editar_combo(self._combo_sel, nombre=nombre, precio=precio, descripcion=desc)
                conn = get_connection()
                conn.execute("DELETE FROM combo_productos WHERE combo_id = ?", (self._combo_sel,))
                conn.executemany(
                    "INSERT INTO combo_productos (combo_id, producto_id, cantidad) VALUES (?,?,?)",
                    [(self._combo_sel, p["producto_id"], p["cantidad"]) for p in productos],
                )
                conn.commit()
                conn.close()
                messagebox.showinfo("Guardado", "Combo actualizado.")
            self._cargar_combos()
            self._cerrar_modal()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _desactivar_combo(self):
        if not self._combo_sel:
            messagebox.showwarning("Sin selección", "Selecciona un combo para desactivar.")
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
        if not messagebox.askyesno("Confirmar",
                                    f"¿Deseas {accion} el combo '{combo['nombre']}'?"):
            return
        editar_combo(self._combo_sel, activo=nuevo_estado)
        self._cargar_combos()
        self._cerrar_modal()
        messagebox.showinfo("Listo", f"Combo {accion}do correctamente.")

    # ── Utilidad ──────────────────────────────────────────────────────────────

    def _cerrar_modal(self):
        if self._modal is not None:
            try:
                self._modal.cerrar()
            except tk.TclError:
                pass
            self._modal = None
