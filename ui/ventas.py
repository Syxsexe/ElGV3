"""
ui/ventas.py — El G POS
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI


QR_DEFAULT_SIZE = "90x90"


class DialogDianStatus(tk.Toplevel):
    """Shows DIAN electronic invoice status after a sale."""

    def __init__(self, parent, result: dict):
        super().__init__(parent)
        self.title("Facturación Electrónica DIAN")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)

        status = result.get("status", "error")
        numero = result.get("numero", "")
        cufe = result.get("cufe", "")
        qr_b64 = result.get("qr", "")
        mensaje = result.get("mensaje_dian") or result.get("mensaje") or ""

        card = tk.Frame(self, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1)
        card.pack(padx=20, pady=20, ipadx=16, ipady=16)

        if status == "aceptada":
            color = COLORS["success"]
            icon_text = "✓"
            title_text = "Factura Electrónica Aceptada por DIAN"
        elif status == "contingencia":
            color = COLORS["warning"]
            icon_text = "⚠"
            title_text = "Factura en Contingencia"
        else:
            color = COLORS["danger"]
            icon_text = "✗"
            title_text = "Error en Factura Electrónica"

        tk.Label(card, text=icon_text, font=("Segoe UI", 36),
                 bg=COLORS["surface"], fg=color).pack(pady=(10, 4))
        tk.Label(card, text=title_text, font=FONT_BOLD,
                 bg=COLORS["surface"], fg=color).pack()

        if numero:
            tk.Label(card, text=f"N° {numero}", font=FONT_SUB,
                     bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(8, 0))

        if cufe:
            cufe_frame = tk.Frame(card, bg=COLORS["surface2"],
                                  highlightbackground=COLORS["border"],
                                  highlightthickness=1)
            cufe_frame.pack(fill="x", padx=10, pady=8, ipadx=6, ipady=6)
            tk.Label(cufe_frame, text="CUFE", font=FONT_SMALL,
                     bg=COLORS["surface2"], fg=COLORS["text_muted"]).pack(anchor="w")
            lbl_cufe = tk.Label(cufe_frame, text=cufe, font=("Courier", 8),
                                bg=COLORS["surface2"], fg=COLORS["text"],
                                wraplength=320, justify="left")
            lbl_cufe.pack(fill="x")
            from modules.validaciones import copiar_al_portapapeles
            tk.Button(cufe_frame, text="Copiar CUFE", font=FONT_SMALL,
                      bg=COLORS["surface2"], fg=COLORS["accent"],
                      relief="flat", cursor="hand2",
                      command=lambda: copiar_al_portapapeles(cufe)).pack(pady=(4, 0))

        if qr_b64:
            try:
                import base64, io, tkinter as tk
                from PIL import Image, ImageTk
                img_data = base64.b64decode(qr_b64)
                img = Image.open(io.BytesIO(img_data))
                img = img.resize((90, 90), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                lbl_qr = tk.Label(card, image=photo, bg=COLORS["surface"])
                lbl_qr.image = photo
                lbl_qr.pack(pady=8)
            except Exception:
                pass

        if mensaje:
            tk.Label(card, text=mensaje, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"],
                     wraplength=320).pack(pady=(0, 8))

        tk.Button(card, text="Cerrar", font=FONT_BOLD,
                  bg=COLORS["accent"], fg=COLORS["on_accent"],
                  relief="flat", cursor="hand2",
                  command=self.destroy).pack(pady=(8, 4), ipadx=20, ipady=6)

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()


class FrameVentas(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Nueva Venta", "Registra una venta de tienda o cocina")
        from modules.ventas import Carrito
        from modules.caja import get_sesion_activa
        self.carrito           = Carrito()
        self.sesion_id         = get_sesion_activa()
        self.sesion_id         = self.sesion_id["id"] if self.sesion_id else None
        self._cliente_id       = None   # cliente vinculado (None = Consumidor Final)
        self._clientes_drop_db = []     # resultados de búsqueda de cliente
        self._build()

    def _build(self):
        from modules.inventario import listar_productos, listar_categorias
        from modules.ventas import listar_combos
        from modules.caja import formatear_pesos

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Panel izquierdo: búsqueda y catálogo ─────────────────────────────
        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        # Búsqueda
        search_frame = tk.Frame(left, bg=COLORS["bg"])
        search_frame.pack(fill="x", pady=(0, 10))
        self.entry_buscar = self._input(search_frame)
        self.entry_buscar.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry_buscar.insert(0, "Buscar producto...")
        self.entry_buscar.bind("<FocusIn>",  lambda e: self._clear_placeholder())
        self.entry_buscar.bind("<KeyRelease>", lambda e: self._buscar())

        # Tabs tienda / cocina / combos
        tab_frame = tk.Frame(left, bg=COLORS["bg"])
        tab_frame.pack(fill="x", pady=(0, 8))
        self._tab_actual = tk.StringVar(value="tienda")
        for texto, valor in [("Tienda", "tienda"), ("Cocina", "cocina"),
                             ("Combos", "combos"), ("Adicionales", "adicionales")]:
            tk.Radiobutton(
                tab_frame, text=texto, variable=self._tab_actual, value=valor,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._buscar, padx=14, pady=6,
            ).pack(side="left", padx=(0, 4))

        # Lista de productos
        lista_wrap = tk.Frame(left, bg=COLORS["bg"])
        lista_wrap.pack(fill="both", expand=True)
        cols = ("Nombre", "Precio", "Stock")
        self.tree_productos = self._tabla(lista_wrap, cols, alto=14)
        self.tree_productos.column("Nombre", width=220, anchor="w")
        self.tree_productos.column("Precio", width=100)
        self.tree_productos.column("Stock",  width=80)
        self.tree_productos.bind("<Double-1>", lambda e: self._agregar_al_carrito())

        self._buscar()

        # ── Panel derecho: carrito (scrollable) ──────────────────────────────
        right_outer = tk.Frame(main, bg=COLORS["border"],
                               highlightbackground=COLORS["border"],
                               highlightthickness=1, width=334)
        right_outer.pack(side="right", fill="y")
        right_outer.pack_propagate(False)

        right_cv = tk.Canvas(right_outer, bg=COLORS["surface"],
                              highlightthickness=0, bd=0, width=332)
        right_sb = tk.Scrollbar(right_outer, orient="vertical", command=right_cv.yview)
        right_cv.configure(yscrollcommand=right_sb.set)
        right_sb.pack(side="right", fill="y")
        right_cv.pack(side="left", fill="both", expand=True)

        right = tk.Frame(right_cv, bg=COLORS["surface"])
        _win = right_cv.create_window((0, 0), window=right, anchor="nw")
        right_cv.bind("<Configure>", lambda e: right_cv.itemconfig(_win, width=e.width))
        right.bind("<Configure>", lambda e: right_cv.configure(
            scrollregion=right_cv.bbox("all")))

        # La rueda controla el carrito solo mientras el puntero esté sobre él
        # (sin bind_all permanente que rompa el scroll global de main.py).
        from ui.scroll import rueda_al_entrar
        rueda_al_entrar(right_cv, right_outer, right_cv, right)

        # ── Título ────────────────────────────────────────────────────────────
        tk.Label(right, text="Carrito", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(16, 8))

        # ── Lista carrito (altura fija — no expande) ──────────────────────────
        cart_wrap = tk.Frame(right, bg=COLORS["surface"])
        cart_wrap.pack(fill="x", padx=8)
        self.tree_carrito = self._tabla(cart_wrap, ("Ítem", "Cant", "Subtotal"), alto=9)
        self.tree_carrito.column("Ítem",     width=145, anchor="w")
        self.tree_carrito.column("Cant",     width=45,  anchor="center")
        self.tree_carrito.column("Subtotal", width=100, anchor="e")
        self.tree_carrito.bind("<<TreeviewSelect>>", lambda e: self._actualizar_qty_label())

        # ── Controles de cantidad ─────────────────────────────────────────────
        qty_row = tk.Frame(right, bg=COLORS["surface"])
        qty_row.pack(fill="x", padx=16, pady=(8, 0))

        tk.Button(
            qty_row, text="−", font=("Segoe UI", 14, "bold"),
            bg=COLORS["surface2"], fg=COLORS["text"],
            activebackground=COLORS["border"], activeforeground=COLORS["text"],
            relief="flat", cursor="hand2", width=3,
            command=self._decrementar_qty,
        ).pack(side="left")

        self.lbl_qty = tk.Label(
            qty_row, text="—", font=FONT_BOLD,
            bg=COLORS["surface"], fg=COLORS["text"], width=8,
        )
        self.lbl_qty.pack(side="left", expand=True)

        tk.Button(
            qty_row, text="+", font=("Segoe UI", 14, "bold"),
            bg=COLORS["surface2"], fg=COLORS["text"],
            activebackground=COLORS["border"], activeforeground=COLORS["text"],
            relief="flat", cursor="hand2", width=3,
            command=self._incrementar_qty,
        ).pack(side="right")

        # ── Quitar ítem ───────────────────────────────────────────────────────
        self._btn_danger(right, "✕ Quitar seleccionado",
                         self._quitar_item).pack(fill="x", padx=16, pady=(6, 0))

        tk.Frame(right, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=12)

        # ── Total ─────────────────────────────────────────────────────────────
        self.lbl_subtotal = tk.Label(right, text="",
                                      font=FONT_SMALL,
                                      bg=COLORS["surface"], fg=COLORS["text_muted"])
        self.lbl_subtotal.pack(pady=(0, 2))

        self.lbl_total = tk.Label(right, text="Total: $0",
                                   font=("Segoe UI", 18, "bold"),
                                   bg=COLORS["surface"], fg=COLORS["accent"])
        self.lbl_total.pack(pady=(0, 6))

        # ── Descuento ─────────────────────────────────────────────────────────
        fila_desc = tk.Frame(right, bg=COLORS["surface"])
        fila_desc.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(fila_desc, text="Descuento ($):", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_descuento = self._input(fila_desc, width=12)
        self.entry_descuento.insert(0, "0")
        self.entry_descuento.pack(side="right", ipady=4)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_descuento, "monto")
        self.entry_descuento.bind("<KeyRelease>", lambda e: self._actualizar_carrito())

        # ── Confirmar ─────────────────────────────────────────────────────────
        self._btn_primary(right, "✓ Confirmar Venta",
                          self._confirmar_venta).pack(fill="x", padx=16, ipady=10)

        tk.Frame(right, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=12)

        # ── Selector de cliente ───────────────────────────────────────────────
        tk.Label(right, text="Cliente (opcional)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)

        self.entry_buscar_cliente = self._input(right)
        self.entry_buscar_cliente.pack(fill="x", padx=16, pady=(4, 0), ipady=5)
        self.entry_buscar_cliente.bind("<KeyRelease>", self._buscar_clientes_venta)
        self.entry_buscar_cliente.bind(
            "<FocusOut>", lambda e: self.after(150, self._ocultar_drop_cli))

        drop_wrap = tk.Frame(right, bg=COLORS["surface"])
        drop_wrap.pack(fill="x", padx=16)
        self.lst_clientes_venta = tk.Listbox(
            drop_wrap, font=FONT_SMALL, height=4,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self.lst_clientes_venta.bind("<<ListboxSelect>>", self._seleccionar_cliente_venta)
        # Oculto hasta que el usuario escriba

        self.lbl_cliente_venta = tk.Label(
            right, text="Sin cliente — Consumidor Final",
            font=("Segoe UI", 8), bg=COLORS["surface"],
            fg=COLORS["text_dim"], anchor="w",
        )
        self.lbl_cliente_venta.pack(fill="x", padx=16, pady=(4, 0))

        self._emitir_factura = tk.BooleanVar(value=False)
        tk.Checkbutton(
            right, text="Emitir a DIAN (si no, queda solo local)",
            variable=self._emitir_factura,
            font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text"],
            selectcolor=COLORS["surface2"],
            activebackground=COLORS["surface"],
            activeforeground=COLORS["text"], cursor="hand2",
        ).pack(anchor="w", padx=16, pady=(6, 0))

        tk.Frame(right, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=12)

        # ── Limpiar ───────────────────────────────────────────────────────────
        tk.Button(right, text="Limpiar carrito", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self._limpiar_carrito).pack(pady=(0, 6))

        # ── Estado DIAN ───────────────────────────────────────────────────────
        self.lbl_dian_status = tk.Label(
            right, text="", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"],
        )
        self.lbl_dian_status.pack(pady=(0, 16))
        self._update_dian_status()

    def _update_dian_status(self):
        from modules.dian_client import is_configured
        if is_configured():
            self.lbl_dian_status.config(
                text="✓ DIAN configurado", fg=COLORS["success"])
        else:
            self.lbl_dian_status.config(
                text="⚠ DIAN no configurado. Ir a Documentos Fiscales",
                fg=COLORS["warning"])

    def _clear_placeholder(self):
        if self.entry_buscar.get() == "Buscar producto...":
            self.entry_buscar.delete(0, "end")

    def _buscar(self):
        from modules.inventario import listar_productos, buscar_productos
        from modules.ventas import listar_combos
        from modules.caja import formatear_pesos

        texto = self.entry_buscar.get().strip()
        if texto == "Buscar producto...":
            texto = ""

        tab = self._tab_actual.get()
        self.tree_productos.delete(*self.tree_productos.get_children())

        if tab == "combos":
            combos = listar_combos()
            for c in combos:
                if texto.lower() in c["nombre"].lower() or not texto:
                    self.tree_productos.insert("", "end", iid=f"combo_{c['id']}",
                                               values=(c["nombre"],
                                                       formatear_pesos(c["precio"]),
                                                       "—"))
        elif tab == "adicionales":
            from modules.inventario import listar_adicionales
            for a in listar_adicionales():
                if texto.lower() in a["nombre"].lower() or not texto:
                    self.tree_productos.insert("", "end", iid=f"adic_{a['id']}",
                                               values=(f"{a['nombre']} (adicional)",
                                                       formatear_pesos(a["precio_adicional"]),
                                                       "—"))
        else:
            prods = buscar_productos(texto, tipo=tab) if texto else listar_productos(tipo=tab)
            for p in prods:
                self.tree_productos.insert("", "end", iid=f"prod_{p['id']}",
                                           values=(p["nombre"],
                                                   formatear_pesos(p["precio_venta"]),
                                                   p["stock"]))

    def _agregar_al_carrito(self):
        from modules.caja import formatear_pesos
        sel = self.tree_productos.focus()
        if not sel:
            return
        try:
            if sel.startswith("combo_"):
                combo_id = int(sel.split("_")[1])
                self.carrito.agregar_combo(combo_id)
            elif sel.startswith("adic_"):
                insumo_id = int(sel.split("_")[1])
                self.carrito.agregar_adicional(insumo_id)
            else:
                prod_id = int(sel.split("_")[1])
                self.carrito.agregar_producto(prod_id)
            self._actualizar_carrito()
        except ValueError as e:
            messagebox.showwarning("Stock insuficiente", str(e))

    def _get_descuento(self) -> float:
        from modules.validaciones import leer_entero
        try:
            d = leer_entero(self.entry_descuento, default=0)
            return max(0, min(d, self.carrito.total()))
        except Exception:
            return 0

    def _actualizar_carrito(self):
        from modules.caja import formatear_pesos
        self.tree_carrito.delete(*self.tree_carrito.get_children())
        for item in self.carrito.get_items():
            self.tree_carrito.insert("", "end", values=(
                item["nombre"],
                item["cantidad"],
                formatear_pesos(item["subtotal"])
            ))
        subtotal   = self.carrito.total()
        descuento  = self._get_descuento()
        total_final = subtotal - descuento

        if descuento > 0:
            self.lbl_subtotal.config(
                text=f"Subtotal: {formatear_pesos(subtotal)}  |  Desc: -{formatear_pesos(descuento)}"
            )
        else:
            self.lbl_subtotal.config(text="")

        self.lbl_total.config(text=f"Total: {formatear_pesos(total_final)}")
        if not self.carrito.get_items():
            self.lbl_qty.config(text="—")

    def _quitar_item(self):
        sel = self.tree_carrito.selection()
        if not sel:
            return
        idx = self.tree_carrito.index(sel[0])
        self.carrito.quitar_item(idx)
        self._actualizar_carrito()

    def _limpiar_carrito(self):
        self.carrito.limpiar()
        self._actualizar_carrito()

    def _confirmar_venta(self):
        from modules.ui_pago import abrir_dialogo_pago
        from modules.caja import formatear_pesos

        if self.carrito.esta_vacio():
            messagebox.showwarning("Carrito vacío", "Agrega productos antes de confirmar.")
            return

        descuento   = self._get_descuento()
        total_final = self.carrito.total() - descuento
        abrir_dialogo_pago(
            self, total_final, self._procesar_pago,
            cliente_id=self._get_cliente_id(),
        )

    def _procesar_pago(self, pagos: list):
        from modules.ventas import registrar_venta
        from modules.caja import formatear_pesos
        from modules.fiscal_documents import preparar_venta_para_dian
        from modules.sync import get_sync_manager
        from modules.dian_client import is_configured

        cliente_id = self._get_cliente_id()
        emitir_dian = self._emitir_factura.get()

        try:
            venta_id = registrar_venta(
                self.carrito,
                pagos=pagos,
                descuento=self._get_descuento(),
                sesion_id=self.sesion_id,
                cliente_id=cliente_id,
                emitir_factura=emitir_dian
            )
            total_str = formatear_pesos(sum(p["monto"] for p in pagos))
            metodos   = " + ".join(p["metodo"] for p in pagos)
            self._actualizar_carrito()
            self._buscar()
            self._ultimo_venta_id = venta_id

            # ── Sync backend ──────────────────────────────────────────────
            # Sincronizamos siempre que el backend esté configurado: las que no
            # se emiten a DIAN quedan como factura local (LOC) en el backend.
            dian_result = {"status": "no_configurado"}
            if is_configured():
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
                    venta_data["pagos"] = pagos

                    # Get customer info
                    cliente = None
                    if cliente_id:
                        from modules.clientes import obtener_cliente
                        cliente = obtener_cliente(cliente_id)

                    dian_payload = preparar_venta_para_dian(
                        venta_data, cliente, emitir_dian=emitir_dian
                    )

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

            # ── Show DIAN status dialog if applicable ────────────────────
            # Solo mostramos el diálogo DIAN cuando se pidió emitir.
            if emitir_dian and dian_result.get("status") != "no_configurado":
                DialogDianStatus(self, dian_result)

            # ── Ticket ────────────────────────────────────────────────────
            if dian_result.get("status") in (
                "aceptada", "contingencia", "no_configurado",
                "local", "en_proceso", "pendiente",
            ):
                if messagebox.askyesno(
                    "Venta registrada",
                    f"Venta #{venta_id}\nTotal: {total_str}\nMétodo: {metodos}\n\n¿Imprimir ticket?"
                ):
                    from ui.ticket_dialog import mostrar_ticket_venta
                    mostrar_ticket_venta(self, venta_id)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Búsqueda de cliente ───────────────────────────────────────────────────

    def _buscar_clientes_venta(self, event=None):
        from modules.clientes import buscar_clientes
        texto = self.entry_buscar_cliente.get().strip()
        self._cliente_id = None
        self.lbl_cliente_venta.config(
            text="Sin cliente — Consumidor Final", fg=COLORS["text_dim"])

        self.lst_clientes_venta.delete(0, "end")
        self._clientes_drop_db = []

        if not texto:
            self._ocultar_drop_cli()
            return

        resultados = buscar_clientes(texto)[:6]
        if not resultados:
            self._ocultar_drop_cli()
            return

        self._clientes_drop_db = resultados
        for c in resultados:
            doc = f"{c['tipo_documento']} {c['documento']}" if c.get("documento") else ""
            self.lst_clientes_venta.insert("end", f"  {c['nombre']}  —  {doc}")
        self.lst_clientes_venta.pack(fill="x")

    def _seleccionar_cliente_venta(self, event=None):
        idx = self.lst_clientes_venta.curselection()
        if not idx or idx[0] >= len(self._clientes_drop_db):
            return
        c = self._clientes_drop_db[idx[0]]
        self._cliente_id = c["id"]
        self.entry_buscar_cliente.delete(0, "end")
        self.entry_buscar_cliente.insert(0, c["nombre"])
        doc = f"{c['tipo_documento']} {c['documento']}" if c.get("documento") else ""
        self.lbl_cliente_venta.config(
            text=f"✓  Vinculado — {doc}" if doc else "✓  Cliente vinculado",
            fg=COLORS["success"],
        )
        self._ocultar_drop_cli()

    def _ocultar_drop_cli(self):
        self.lst_clientes_venta.pack_forget()

    def _get_cliente_id(self):
        return self._cliente_id

    # ── Controles +/- carrito ─────────────────────────────────────────────────

    def _actualizar_qty_label(self):
        sel = self.tree_carrito.selection()
        if not sel:
            self.lbl_qty.config(text="—")
            return
        idx   = self.tree_carrito.index(sel[0])
        items = self.carrito.get_items()
        if 0 <= idx < len(items):
            cant = items[idx]["cantidad"]
            # Mostrar entero si no tiene decimales
            texto = str(int(cant)) if cant == int(cant) else str(cant)
            self.lbl_qty.config(text=f"×{texto}")
        else:
            self.lbl_qty.config(text="—")

    def _incrementar_qty(self):
        sel = self.tree_carrito.selection()
        if not sel:
            return
        idx   = self.tree_carrito.index(sel[0])
        items = self.carrito.get_items()
        if 0 <= idx < len(items):
            nueva = items[idx]["cantidad"] + 1
            try:
                self.carrito.cambiar_cantidad(idx, nueva)
            except ValueError as e:
                messagebox.showwarning("Stock insuficiente", str(e))
                return
            self._actualizar_carrito()
            # Re-seleccionar la misma fila
            children = self.tree_carrito.get_children()
            if idx < len(children):
                self.tree_carrito.selection_set(children[idx])
                self.tree_carrito.focus(children[idx])
            self._actualizar_qty_label()

    def _decrementar_qty(self):
        sel = self.tree_carrito.selection()
        if not sel:
            return
        idx   = self.tree_carrito.index(sel[0])
        items = self.carrito.get_items()
        if 0 <= idx < len(items):
            nueva = items[idx]["cantidad"] - 1
            self.carrito.cambiar_cantidad(idx, nueva)  # quita el item si nueva <= 0
            self._actualizar_carrito()
            # Re-seleccionar si aún existe la fila
            children = self.tree_carrito.get_children()
            if children and idx < len(children):
                self.tree_carrito.selection_set(children[idx])
                self.tree_carrito.focus(children[idx])
                self._actualizar_qty_label()
            else:
                self.lbl_qty.config(text="—")
