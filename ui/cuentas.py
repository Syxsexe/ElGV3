"""
ui/cuentas.py — El G POS
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI

class FrameCuentas(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Cuentas", "Mesas abiertas y consumo por cliente")
        from modules.cuentas import migrar
        migrar()
        self._cuenta_sel  = None   # ID de cuenta seleccionada
        self._cliente_id  = None   # ID del cliente registrado (puede ser None)
        self._clientes_db = []     # caché de resultados de búsqueda
        self._build()

    def _build(self):
        from modules.caja import formatear_pesos

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self._main = main

        # ── Panel derecho PRIMERO (orden de pack importa) ─────────────────────
        right_outer = tk.Frame(main, bg=COLORS["border"],
                               highlightbackground=COLORS["border"],
                               highlightthickness=1, width=292)
        right_outer.pack(side="right", fill="y")
        right_outer.pack_propagate(False)

        right_canvas = tk.Canvas(right_outer, bg=COLORS["surface"],
                                  highlightthickness=0, bd=0, width=290)
        right_scroll = tk.Scrollbar(right_outer, orient="vertical",
                                     command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_scroll.set)
        right_scroll.pack(side="right", fill="y")
        right_canvas.pack(side="left", fill="both", expand=True)

        right = tk.Frame(right_canvas, bg=COLORS["surface"])
        right_win = right_canvas.create_window((0, 0), window=right, anchor="nw")

        right_canvas.bind("<Configure>",
            lambda e: right_canvas.itemconfig(right_win, width=e.width))
        right.bind("<Configure>",
            lambda e: right_canvas.configure(scrollregion=right_canvas.bbox("all")))

        def _on_right_wheel(event):
            try:
                rx = right_outer.winfo_rootx()
                rw = right_outer.winfo_width()
                if not (rx <= event.x_root <= rx + rw):
                    return
            except Exception:
                return
            if event.num == 4:
                right_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                right_canvas.yview_scroll(1, "units")
            else:
                right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        right_canvas.bind_all("<MouseWheel>", _on_right_wheel)
        right_canvas.bind_all("<Button-4>",   _on_right_wheel)
        right_canvas.bind_all("<Button-5>",   _on_right_wheel)

        # ── Panel izquierdo DESPUÉS ───────────────────────────────────────────
        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tk.Label(left, text="Mesas abiertas", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))

        lista_wrap = tk.Frame(left, bg=COLORS["bg"])
        lista_wrap.pack(fill="both", expand=True)

        self.tree_mesas = self._tabla(
            lista_wrap,
            ("id_cuenta", "mesa", "cliente", "items", "total", "desde"),
            alto=8
        )
        self.tree_mesas.heading("id_cuenta", text="#")
        self.tree_mesas.heading("mesa",      text="Mesa")
        self.tree_mesas.heading("cliente",   text="Cliente")
        self.tree_mesas.heading("items",     text="Items")
        self.tree_mesas.heading("total",     text="Total")
        self.tree_mesas.heading("desde",     text="Desde")
        self.tree_mesas.column("id_cuenta", width=40)
        self.tree_mesas.column("mesa",      width=80)
        self.tree_mesas.column("cliente",   width=140, anchor="w")
        self.tree_mesas.column("items",     width=50)
        self.tree_mesas.column("total",     width=100)
        self.tree_mesas.column("desde",     width=130)
        self.tree_mesas.bind("<<TreeviewSelect>>", self._al_seleccionar)

        # Botón refrescar
        btn_row = tk.Frame(left, bg=COLORS["bg"])
        btn_row.pack(fill="x", pady=(8, 0))
        tk.Button(btn_row, text="↻ Refrescar", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self._cargar_mesas).pack(side="left")

        # ── Detalle de cuenta seleccionada ────────────────────────────────────
        tk.Label(left, text="Ítems de la cuenta", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(16, 6))

        detalle_wrap = tk.Frame(left, bg=COLORS["bg"])
        detalle_wrap.pack(fill="both", expand=True)

        self.tree_items = self._tabla(
            detalle_wrap,
            ("item_id", "nombre", "cantidad", "precio", "subtotal"),
            alto=7
        )
        self.tree_items.heading("item_id",  text="#")
        self.tree_items.heading("nombre",   text="Producto / Combo")
        self.tree_items.heading("cantidad", text="Cant")
        self.tree_items.heading("precio",   text="Precio")
        self.tree_items.heading("subtotal", text="Subtotal")
        self.tree_items.column("item_id",  width=40)
        self.tree_items.column("nombre",   width=180, anchor="w")
        self.tree_items.column("cantidad", width=50)
        self.tree_items.column("precio",   width=90)
        self.tree_items.column("subtotal", width=90)
        self.tree_items.bind("<<TreeviewSelect>>", self._al_seleccionar_item)

        # ── Controles de cantidad ─────────────────────────────────────────────
        qty_row = tk.Frame(left, bg=COLORS["bg"])
        qty_row.pack(anchor="w", pady=(6, 0))

        tk.Button(
            qty_row, text="−", font=("Segoe UI", 13, "bold"),
            bg=COLORS["surface2"], fg=COLORS["text"],
            activebackground=COLORS["border"], activeforeground=COLORS["text"],
            relief="flat", cursor="hand2", width=3,
            command=self._decrementar_item,
        ).pack(side="left")

        self.lbl_qty_cuenta = tk.Label(
            qty_row, text="—", font=FONT_BOLD,
            bg=COLORS["bg"], fg=COLORS["text"], width=7,
        )
        self.lbl_qty_cuenta.pack(side="left")

        tk.Button(
            qty_row, text="+", font=("Segoe UI", 13, "bold"),
            bg=COLORS["surface2"], fg=COLORS["text"],
            activebackground=COLORS["border"], activeforeground=COLORS["text"],
            relief="flat", cursor="hand2", width=3,
            command=self._incrementar_item,
        ).pack(side="left")

        # Quitar ítem
        self._btn_danger(left, "✕ Quitar ítem seleccionado",
                         self._quitar_item).pack(anchor="w", pady=(6, 0))

        # — Abrir cuenta nueva —
        tk.Label(right, text="Abrir cuenta", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(16, 4))

        # ── Selector de cliente ────────────────────────────────────────────────
        tk.Label(right, text="Cliente", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16)

        self.entry_cliente = self._input(right)
        self.entry_cliente.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
        self.entry_cliente.bind("<KeyRelease>", self._buscar_clientes)
        self.entry_cliente.bind("<FocusOut>",
                                lambda e: self.after(150, self._ocultar_dropdown))

        # Dropdown de resultados
        drop_wrap = tk.Frame(right, bg=COLORS["surface"])
        drop_wrap.pack(fill="x", padx=16)
        self.lst_clientes = tk.Listbox(
            drop_wrap, font=FONT_SMALL, height=4,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.lst_clientes.bind("<<ListboxSelect>>", self._seleccionar_cliente)
        # No empaquetado aún — se muestra solo cuando hay resultados

        # Indicador de cliente vinculado
        self.lbl_cliente_sel = tk.Label(
            right, text="", font=("Segoe UI", 8),
            bg=COLORS["surface"], fg=COLORS["success"],
            anchor="w", wraplength=220, justify="left",
        )
        self.lbl_cliente_sel.pack(fill="x", padx=16, pady=(2, 4))

        # Mesa
        tk.Label(right, text="Mesa / Puesto", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16)
        self.entry_mesa = self._input(right)
        self.entry_mesa.pack(fill="x", padx=16, pady=(2, 8), ipady=5)

        self._btn_primary(right, "Abrir cuenta",
                          self._abrir_cuenta).pack(fill="x", padx=16, ipady=8)

        sep = tk.Frame(right, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=16, pady=14)

        # — Agregar ítem a cuenta seleccionada —
        tk.Label(right, text="Agregar a cuenta seleccionada",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 8))

        tk.Label(right, text="Buscar producto", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self.entry_buscar = self._input(right)
        self.entry_buscar.pack(fill="x", padx=16, pady=(2, 6), ipady=5)
        self.entry_buscar.bind("<KeyRelease>", lambda e: self._buscar_productos())

        buscar_wrap = tk.Frame(right, bg=COLORS["surface"])
        buscar_wrap.pack(fill="x", padx=16)
        self.lst_buscar = tk.Listbox(
            buscar_wrap, font=FONT_SMALL, height=5,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.lst_buscar.pack(fill="x")
        self._resultados_busqueda = []

        tk.Label(right, text="Cantidad", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(6, 0))
        self.entry_cant = self._input(right, width=6)
        self.entry_cant.insert(0, "1")
        self.entry_cant.pack(anchor="w", padx=16, pady=(2, 8), ipady=4)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_cant, "cantidad")

        self._btn_primary(right, "+ Agregar ítem",
                          self._agregar_item).pack(fill="x", padx=16, ipady=8)

        sep2 = tk.Frame(right, bg=COLORS["border"], height=1)
        sep2.pack(fill="x", padx=16, pady=14)

        # — Cobrar —
        tk.Label(right, text="Cobrar cuenta", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16)

        self.lbl_subtotal_cuenta = tk.Label(
            right, text="",
            font=("Segoe UI", 10),
            bg=COLORS["surface"], fg=COLORS["text_muted"]
        )
        self.lbl_subtotal_cuenta.pack(pady=(6, 0))

        self.lbl_total_cuenta = tk.Label(
            right, text="Total: $0",
            font=("Segoe UI", 15, "bold"),
            bg=COLORS["surface"], fg=COLORS["accent"]
        )
        self.lbl_total_cuenta.pack(pady=(0, 4))

        tk.Label(right, text="Descuento ($)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self.entry_descuento_cuenta = self._input(right)
        self.entry_descuento_cuenta.pack(fill="x", padx=16, pady=(2, 8), ipady=4)
        from modules.validaciones import aplicar_validacion as _av
        _av(self.entry_descuento_cuenta, "monto")
        self.entry_descuento_cuenta.bind(
            "<KeyRelease>", lambda e: self._actualizar_total_con_descuento()
        )

        self._emitir_factura = tk.BooleanVar(value=False)
        tk.Checkbutton(
            right, text="Emitir factura DIAN",
            variable=self._emitir_factura,
            font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text"],
            selectcolor=COLORS["surface2"],
            activebackground=COLORS["surface"],
            activeforeground=COLORS["text"], cursor="hand2",
        ).pack(anchor="w", padx=16, pady=(0, 6))

        self._btn_primary(right, "✓ Cobrar y cerrar",
                          self._cobrar).pack(fill="x", padx=16, ipady=10)
        self._btn_danger(right, "✕ Cancelar cuenta",
                         self._cancelar).pack(fill="x", padx=16, pady=(6, 8), ipady=6)

        self.lbl_dian_status = tk.Label(
            right, text="", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"],
        )
        self.lbl_dian_status.pack(pady=(0, 16))
        self._update_dian_status()

        # Cargar datos iniciales
        self._cargar_mesas()
        self._buscar_productos()

    # ── Búsqueda y selección de cliente ──────────────────────────────────────

    def _buscar_clientes(self, event=None):
        from modules.clientes import buscar_clientes, listar_clientes

        texto = self.entry_cliente.get().strip()

        # Si el usuario modifica el campo después de haber seleccionado, limpiar vínculo
        self._cliente_id = None
        self.lbl_cliente_sel.config(text="")

        self.lst_clientes.delete(0, "end")
        self._clientes_db = []

        if not texto:
            self._ocultar_dropdown()
            return

        resultados = buscar_clientes(texto)[:8]
        if not resultados:
            self._ocultar_dropdown()
            return

        self._clientes_db = resultados
        for c in resultados:
            doc = f"{c['tipo_documento']} {c['documento']}" if c.get("documento") else ""
            self.lst_clientes.insert("end", f"  {c['nombre']}  —  {doc}")

        self.lst_clientes.pack(fill="x")

    def _seleccionar_cliente(self, event=None):
        idx = self.lst_clientes.curselection()
        if not idx or idx[0] >= len(self._clientes_db):
            return
        c = self._clientes_db[idx[0]]
        self._cliente_id = c["id"]
        self.entry_cliente.delete(0, "end")
        self.entry_cliente.insert(0, c["nombre"])
        doc = f"{c['tipo_documento']} {c['documento']}" if c.get("documento") else ""
        self.lbl_cliente_sel.config(
            text=f"✓  Vinculado — {doc}" if doc else "✓  Cliente vinculado"
        )
        self._ocultar_dropdown()

    def _ocultar_dropdown(self):
        self.lst_clientes.pack_forget()

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _cargar_mesas(self):
        from modules.cuentas import listar_cuentas_abiertas
        from modules.caja import formatear_pesos

        self.tree_mesas.delete(*self.tree_mesas.get_children())
        for c in listar_cuentas_abiertas():
            self.tree_mesas.insert("", "end", iid=str(c["id"]), values=(
                c["id"], c["mesa"], c["cliente"],
                c["num_items"],
                formatear_pesos(c["total"]),
                c["abierta_en"][11:16]   # solo HH:MM
            ))

    def _al_seleccionar(self, event=None):
        from modules.cuentas import obtener_cuenta
        from modules.caja import formatear_pesos

        sel = self.tree_mesas.focus()
        if not sel:
            return
        self._cuenta_sel = int(sel)
        cuenta = obtener_cuenta(self._cuenta_sel)
        if not cuenta:
            return

        self.tree_items.delete(*self.tree_items.get_children())
        for item in cuenta["items"]:
            self.tree_items.insert("", "end", iid=str(item["id"]), values=(
                item["id"], item["nombre"],
                item["cantidad"],
                formatear_pesos(item["precio_unit"]),
                formatear_pesos(item["subtotal"])
            ))
        self.entry_descuento_cuenta.delete(0, "end")
        self.lbl_subtotal_cuenta.config(text="")
        self.lbl_total_cuenta.config(
            text=f"Total: {formatear_pesos(cuenta['total'])}"
        )

    def _buscar_productos(self):
        from modules.inventario import buscar_productos, listar_productos
        from modules.ventas import listar_combos

        texto = self.entry_buscar.get().strip()
        self.lst_buscar.delete(0, "end")
        self._resultados_busqueda = []

        # Todos los productos activos — tienda y cocina sin distinción
        prods  = buscar_productos(texto) if texto else listar_productos()
        combos = [c for c in listar_combos()
                  if not texto or texto.lower() in c["nombre"].lower()]

        # Agrupar productos por tipo para que sea más fácil encontrarlos
        tienda = [p for p in prods if p["categoria_tipo"] == "tienda"]
        cocina = [p for p in prods if p["categoria_tipo"] == "cocina"]

        if tienda:
            self.lst_buscar.insert("end", "── Tienda ──")
            self._resultados_busqueda.append(None)   # separador, no seleccionable
            for p in tienda[:12]:
                self.lst_buscar.insert("end", f"  {p['nombre']}")
                self._resultados_busqueda.append(("producto", p["id"]))

        if cocina:
            self.lst_buscar.insert("end", "── Cocina ──")
            self._resultados_busqueda.append(None)
            for p in cocina[:8]:
                self.lst_buscar.insert("end", f"  {p['nombre']}")
                self._resultados_busqueda.append(("producto", p["id"]))

        if combos:
            self.lst_buscar.insert("end", "── Combos ──")
            self._resultados_busqueda.append(None)
            for c in combos[:6]:
                self.lst_buscar.insert("end", f"  {c['nombre']}")
                self._resultados_busqueda.append(("combo", c["id"]))

    def _abrir_cuenta(self):
        from modules.cuentas import abrir_cuenta
        cliente = self.entry_cliente.get().strip()
        mesa    = self.entry_mesa.get().strip()
        if not cliente or not mesa:
            messagebox.showwarning("Campos vacíos", "Completa cliente y mesa.")
            return
        try:
            abrir_cuenta(cliente, mesa, cliente_id=self._cliente_id)
            self.entry_cliente.delete(0, "end")
            self.entry_mesa.delete(0, "end")
            self._cliente_id = None
            self.lbl_cliente_sel.config(text="")
            self._ocultar_dropdown()
            self._cargar_mesas()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _agregar_item(self):
        from modules.cuentas import agregar_item
        from modules.caja import formatear_pesos

        if not self._cuenta_sel:
            messagebox.showwarning("Sin selección", "Selecciona una mesa primero.")
            return

        sel_idx = self.lst_buscar.curselection()
        if not sel_idx:
            messagebox.showwarning("Sin selección", "Selecciona un producto de la lista.")
            return

        # Ignorar clic en separadores de categoría
        resultado = self._resultados_busqueda[sel_idx[0]]
        if resultado is None:
            return

        try:
            cantidad = float(self.entry_cant.get() or 1)
        except ValueError:
            messagebox.showwarning("Cantidad inválida", "Ingresa un número válido.")
            return

        tipo, item_id = resultado
        try:
            if tipo == "producto":
                agregar_item(self._cuenta_sel, producto_id=item_id, cantidad=cantidad)
            else:
                agregar_item(self._cuenta_sel, combo_id=item_id, cantidad=cantidad)
            self._al_seleccionar()
            self._cargar_mesas()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _quitar_item(self):
        from modules.cuentas import quitar_item
        sel = self.tree_items.focus()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona un ítem para quitar.")
            return
        if not messagebox.askyesno("Confirmar", "¿Quitar este ítem de la cuenta?"):
            return
        try:
            quitar_item(int(sel))
            self._al_seleccionar()
            self._cargar_mesas()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _get_descuento_cuenta(self) -> float:
        from modules.cuentas import obtener_cuenta
        from modules.validaciones import leer_entero
        if not self._cuenta_sel:
            return 0.0
        cuenta = obtener_cuenta(self._cuenta_sel)
        if not cuenta:
            return 0.0
        bruto = cuenta["total"]
        return max(0, min(leer_entero(self.entry_descuento_cuenta), bruto))

    def _actualizar_total_con_descuento(self):
        from modules.cuentas import obtener_cuenta
        from modules.caja import formatear_pesos
        if not self._cuenta_sel:
            return
        cuenta = obtener_cuenta(self._cuenta_sel)
        if not cuenta:
            return
        bruto     = cuenta["total"]
        descuento = self._get_descuento_cuenta()
        if descuento > 0:
            self.lbl_subtotal_cuenta.config(
                text=f"Subtotal: {formatear_pesos(bruto)}  —  Desc: {formatear_pesos(descuento)}"
            )
            self.lbl_total_cuenta.config(
                text=f"Total: {formatear_pesos(bruto - descuento)}"
            )
        else:
            self.lbl_subtotal_cuenta.config(text="")
            self.lbl_total_cuenta.config(text=f"Total: {formatear_pesos(bruto)}")

    def _cobrar(self):
        from modules.cuentas import obtener_cuenta
        from modules.ui_pago import abrir_dialogo_pago

        if not self._cuenta_sel:
            messagebox.showwarning("Sin selección", "Selecciona una mesa para cobrar.")
            return

        cuenta = obtener_cuenta(self._cuenta_sel)
        if not cuenta or not cuenta["items"]:
            messagebox.showwarning("Cuenta vacía", "La cuenta no tiene ítems.")
            return

        descuento   = self._get_descuento_cuenta()
        total_final = max(0, cuenta["total"] - descuento)
        abrir_dialogo_pago(
            self, total_final,
            self._procesar_cobro,
            titulo=f"Cobrar — {cuenta['cliente']} / {cuenta['mesa']}",
            cliente_id=cuenta.get("cliente_id"),
        )

    def _update_dian_status(self):
        from modules.dian_client import is_configured
        if is_configured():
            self.lbl_dian_status.config(text="✓ DIAN configurado", fg=COLORS["success"])
        else:
            self.lbl_dian_status.config(
                text="⚠ DIAN no configurado", fg=COLORS["warning"])

    def _procesar_cobro(self, pagos: list):
        from modules.cuentas import cobrar_cuenta, obtener_cuenta
        from modules.caja import get_sesion_activa, formatear_pesos
        from modules.fiscal_documents import preparar_venta_para_dian
        from modules.sync import get_sync_manager
        from modules.dian_client import is_configured

        cuenta        = obtener_cuenta(self._cuenta_sel)
        sesion        = get_sesion_activa()
        emitir_factura = self._emitir_factura.get()

        descuento = self._get_descuento_cuenta()
        try:
            venta_id = cobrar_cuenta(
                self._cuenta_sel,
                pagos=pagos,
                sesion_id=sesion["id"] if sesion else None,
                descuento=descuento,
            )
            total_str = formatear_pesos(max(0, cuenta["total"] - descuento))
            metodos   = " + ".join(p["metodo"] for p in pagos)
            cuenta_id_cobrada = self._cuenta_sel
            self._cuenta_sel = None
            self.tree_items.delete(*self.tree_items.get_children())
            self.entry_descuento_cuenta.delete(0, "end")
            self.lbl_subtotal_cuenta.config(text="")
            self.lbl_total_cuenta.config(text="Total: $0")
            self._cargar_mesas()

            # ── DIAN Sync ─────────────────────────────────────────────────
            dian_result = {"status": "no_configurado"}
            if is_configured() and emitir_factura:
                try:
                    from database import get_connection
                    conn = get_connection()
                    venta_data = dict(conn.execute(
                        "SELECT * FROM ventas WHERE id = ?", (venta_id,)
                    ).fetchone())
                    detalle = conn.execute(
                        "SELECT * FROM detalle_venta WHERE venta_id = ?", (venta_id,)
                    ).fetchall()
                    conn.close()
                    venta_data["detalle"] = [dict(d) for d in detalle]
                    venta_data["pagos"]   = pagos

                    cliente = None
                    if cuenta.get("cliente_id"):
                        from modules.clientes import obtener_cliente
                        cliente = obtener_cliente(cuenta["cliente_id"])

                    dian_payload = preparar_venta_para_dian(venta_data, cliente)

                    import asyncio
                    sync_mgr = get_sync_manager()
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    if loop.is_running():
                        dian_result = {"status": "pendiente", "mensaje": "Sincronización en cola"}
                    else:
                        dian_result = loop.run_until_complete(
                            sync_mgr.process_venta(dian_payload)
                        )
                except Exception as e:
                    dian_result = {"status": "error", "error": str(e)}

            # ── Diálogo estado DIAN ───────────────────────────────────────
            if emitir_factura and dian_result.get("status") != "no_configurado":
                from ui.ventas import DialogDianStatus
                DialogDianStatus(self, dian_result)

            if messagebox.askyesno(
                "Cobro exitoso",
                f"Cuenta cobrada — Venta #{venta_id}\n"
                f"Total: {total_str}\nMétodo: {metodos}\n\n¿Imprimir ticket?"
            ):
                from ui.ticket_dialog import mostrar_ticket_cuenta
                mostrar_ticket_cuenta(self, cuenta_id_cobrada, venta_id)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _cancelar(self):
        from modules.cuentas import cancelar_cuenta, obtener_cuenta

        if not self._cuenta_sel:
            messagebox.showwarning("Sin selección", "Selecciona una mesa para cancelar.")
            return

        cuenta = obtener_cuenta(self._cuenta_sel)
        if not messagebox.askyesno(
            "Cancelar cuenta",
            f"¿Cancelar la cuenta de {cuenta['cliente']} en {cuenta['mesa']}?\n"
            "No se generará ninguna venta."
        ):
            return

        try:
            cancelar_cuenta(self._cuenta_sel)
            self._cuenta_sel = None
            self.tree_items.delete(*self.tree_items.get_children())
            self.lbl_total_cuenta.config(text="Total: $0")
            self._cargar_mesas()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    # ── Controles +/- ítems de cuenta ────────────────────────────────────────

    def _al_seleccionar_item(self, event=None):
        sel = self.tree_items.selection()
        if not sel:
            self.lbl_qty_cuenta.config(text="—")
            return
        vals = self.tree_items.item(sel[0], "values")
        # vals: (item_id, nombre, cantidad, precio, subtotal)
        if vals:
            cant = vals[2]
            try:
                c = float(cant)
                texto = str(int(c)) if c == int(c) else str(c)
            except (ValueError, TypeError):
                texto = str(cant)
            self.lbl_qty_cuenta.config(text=f"×{texto}")

    def _incrementar_item(self):
        sel = self.tree_items.selection()
        if not sel:
            return
        item_id = int(self.tree_items.item(sel[0], "values")[0])
        vals    = self.tree_items.item(sel[0], "values")
        try:
            nueva = float(vals[2]) + 1
        except (ValueError, TypeError):
            return
        from modules.cuentas import cambiar_cantidad_item
        try:
            cambiar_cantidad_item(item_id, nueva)
            self._al_seleccionar()
            # Re-seleccionar el mismo ítem si sigue existiendo
            iid = str(item_id)
            if self.tree_items.exists(iid):
                self.tree_items.selection_set(iid)
                self.tree_items.focus(iid)
                self._al_seleccionar_item()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _decrementar_item(self):
        sel = self.tree_items.selection()
        if not sel:
            return
        item_id = int(self.tree_items.item(sel[0], "values")[0])
        vals    = self.tree_items.item(sel[0], "values")
        try:
            nueva = float(vals[2]) - 1
        except (ValueError, TypeError):
            return
        from modules.cuentas import cambiar_cantidad_item
        try:
            cambiar_cantidad_item(item_id, nueva)  # quita si nueva <= 0
            self._al_seleccionar()
            iid = str(item_id)
            if self.tree_items.exists(iid):
                self.tree_items.selection_set(iid)
                self.tree_items.focus(iid)
                self._al_seleccionar_item()
            else:
                self.lbl_qty_cuenta.config(text="—")
        except ValueError as e:
            messagebox.showerror("Error", str(e))