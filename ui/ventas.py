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
                  bg=COLORS["accent"], fg=COLORS["text"],
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
        self.carrito   = Carrito()
        self.sesion_id = get_sesion_activa()
        self.sesion_id = self.sesion_id["id"] if self.sesion_id else None
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
        for texto, valor in [("Tienda", "tienda"), ("Cocina", "cocina"), ("Combos", "combos")]:
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

        # ── Panel derecho: carrito ────────────────────────────────────────────
        right = tk.Frame(main, bg=COLORS["surface"],
                         highlightbackground=COLORS["border"],
                         highlightthickness=1, width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="Carrito", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 8))

        # Lista carrito
        cart_wrap = tk.Frame(right, bg=COLORS["surface"])
        cart_wrap.pack(fill="both", expand=True, padx=8)
        self.tree_carrito = self._tabla(cart_wrap, ("Ítem", "Cant", "Subtotal"), alto=10)
        self.tree_carrito.column("Ítem",     width=120, anchor="w")
        self.tree_carrito.column("Cant",     width=40)
        self.tree_carrito.column("Subtotal", width=90)

        # Quitar ítem
        self._btn_danger(right, "✕ Quitar seleccionado",
                         self._quitar_item).pack(fill="x", padx=16, pady=(8, 0))

        sep = tk.Frame(right, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=16, pady=12)

        # Total
        self.lbl_total = tk.Label(right, text="Total: $0",
                                   font=("Segoe UI", 16, "bold"),
                                   bg=COLORS["surface"], fg=COLORS["accent"])
        self.lbl_total.pack(pady=(0, 8))

        # Confirmar
        self._btn_primary(right, "✓ Confirmar Venta",
                          self._confirmar_venta).pack(fill="x", padx=16, ipady=10)

        # Cliente y factura
        cliente_frame = tk.Frame(right, bg=COLORS["surface"])
        cliente_frame.pack(fill="x", padx=16, pady=(16, 0))

        tk.Label(cliente_frame, text="Cliente", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self.combo_cliente = ttk.Combobox(
            cliente_frame, font=FONT_SMALL, state="readonly"
        )
        self.combo_cliente.pack(fill="x", pady=(4, 8), ipady=4)
        self.combo_cliente.bind("<<ComboboxSelected>>", lambda e: None)

        self._emitir_factura = tk.BooleanVar(value=True)
        tk.Checkbutton(
            cliente_frame,
            text="Emitir factura electrónica",
            variable=self._emitir_factura,
            font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text"],
            selectcolor=COLORS["surface2"], activebackground=COLORS["surface"],
            activeforeground=COLORS["text"], cursor="hand2"
        ).pack(anchor="w")

        self._btn_primary(right, "Actualizar clientes", self._cargar_clientes).pack(
            fill="x", padx=16, pady=(8, 0), ipady=8)

        self._cargar_clientes()

        tk.Button(right, text="Limpiar carrito", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self._limpiar_carrito).pack(pady=(8, 16))

        # ── Estado DIAN ───────────────────────────────────────────────────────
        dian_frame = tk.Frame(right, bg=COLORS["surface"])
        dian_frame.pack(fill="x", padx=16, pady=(0, 16))
        self.lbl_dian_status = tk.Label(
            dian_frame, text="", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"]
        )
        self.lbl_dian_status.pack()
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
            else:
                prod_id = int(sel.split("_")[1])
                self.carrito.agregar_producto(prod_id)
            self._actualizar_carrito()
        except ValueError as e:
            messagebox.showwarning("Stock insuficiente", str(e))

    def _actualizar_carrito(self):
        from modules.caja import formatear_pesos
        self.tree_carrito.delete(*self.tree_carrito.get_children())
        for item in self.carrito.get_items():
            self.tree_carrito.insert("", "end", values=(
                item["nombre"],
                item["cantidad"],
                formatear_pesos(item["subtotal"])
            ))
        self.lbl_total.config(text=f"Total: {formatear_pesos(self.carrito.total())}")

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

        abrir_dialogo_pago(self, self.carrito.total(), self._procesar_pago)

    def _procesar_pago(self, pagos: list):
        from modules.ventas import registrar_venta
        from modules.caja import formatear_pesos
        from modules.fiscal_documents import preparar_venta_para_dian
        from modules.sync import get_sync_manager
        from modules.dian_client import is_configured

        cliente_id = self._get_cliente_id()
        emitir_factura = self._emitir_factura.get()

        try:
            venta_id = registrar_venta(
                self.carrito,
                pagos=pagos,
                sesion_id=self.sesion_id,
                cliente_id=cliente_id,
                emitir_factura=emitir_factura
            )
            total_str = formatear_pesos(sum(p["monto"] for p in pagos))
            metodos   = " + ".join(p["metodo"] for p in pagos)
            self._actualizar_carrito()
            self._buscar()
            self._ultimo_venta_id = venta_id

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
                    venta_data["pagos"] = pagos

                    # Get customer info
                    cliente = None
                    if cliente_id:
                        from modules.clientes import obtener_cliente
                        cliente = obtener_cliente(cliente_id)

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

            # ── Show DIAN status dialog if applicable ────────────────────
            if emitir_factura and dian_result.get("status") != "no_configurado":
                DialogDianStatus(self, dian_result)

            # ── Ticket ────────────────────────────────────────────────────
            if dian_result.get("status") in ("aceptada", "contingencia", "no_configurado"):
                if messagebox.askyesno(
                    "Venta registrada",
                    f"Venta #{venta_id}\nTotal: {total_str}\nMétodo: {metodos}\n\n¿Imprimir ticket?"
                ):
                    from ui.ticket_dialog import mostrar_ticket_venta
                    mostrar_ticket_venta(self, venta_id)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _cargar_clientes(self):
        from modules.clientes import listar_clientes

        clientes = listar_clientes(solo_activos=False)
        opciones = ["-- Consumidor Final --"]
        self._cliente_ids = {"-- Consumidor Final --": None}
        for c in clientes:
            texto = f"{c['id']} - {c['nombre']} ({c['tipo_documento']})"
            opciones.append(texto)
            self._cliente_ids[texto] = c["id"]
        self.combo_cliente["values"] = opciones
        self.combo_cliente.set(opciones[0])

    def _get_cliente_id(self):
        seleccionado = self.combo_cliente.get()
        return self._cliente_ids.get(seleccionado)
