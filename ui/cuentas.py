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
        self._cuenta_sel = None   # ID de cuenta seleccionada
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

        # Quitar ítem
        self._btn_danger(left, "✕ Quitar ítem seleccionado",
                         self._quitar_item).pack(anchor="w", pady=(6, 0))

        # — Abrir cuenta nueva —
        tk.Label(right, text="Abrir cuenta", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(16, 8))

        for lbl, attr in [("Cliente", "entry_cliente"), ("Mesa / Puesto", "entry_mesa")]:
            tk.Label(right, text=lbl, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16)
            e = self._input(right)
            e.pack(fill="x", padx=16, pady=(2, 8), ipady=5)
            setattr(self, attr, e)

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

        self.lbl_total_cuenta = tk.Label(
            right, text="Total: $0",
            font=("Segoe UI", 15, "bold"),
            bg=COLORS["surface"], fg=COLORS["accent"]
        )
        self.lbl_total_cuenta.pack(pady=6)

        self._btn_primary(right, "✓ Cobrar y cerrar",
                          self._cobrar).pack(fill="x", padx=16, ipady=10)
        self._btn_danger(right, "✕ Cancelar cuenta",
                         self._cancelar).pack(fill="x", padx=16, pady=(6, 16), ipady=6)

        # Cargar datos iniciales
        self._cargar_mesas()
        self._buscar_productos()

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
            abrir_cuenta(cliente, mesa)
            self.entry_cliente.delete(0, "end")
            self.entry_mesa.delete(0, "end")
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

        abrir_dialogo_pago(
            self, cuenta["total"],
            self._procesar_cobro,
            titulo=f"Cobrar — {cuenta['cliente']} / {cuenta['mesa']}"
        )

    def _procesar_cobro(self, pagos: list):
        from modules.cuentas import cobrar_cuenta, obtener_cuenta
        from modules.caja import get_sesion_activa, formatear_pesos

        cuenta  = obtener_cuenta(self._cuenta_sel)
        sesion  = get_sesion_activa()
        try:
            venta_id = cobrar_cuenta(
                self._cuenta_sel,
                pagos=pagos,
                sesion_id=sesion["id"] if sesion else None
            )
            total_str = formatear_pesos(cuenta["total"])
            metodos   = " + ".join(p["metodo"] for p in pagos)
            messagebox.showinfo(
                "Cobro exitoso",
                f"✓ Cuenta cobrada — Venta #{venta_id}\n"
                f"Total: {total_str}\nMétodo: {metodos}"
            )
            self._cuenta_sel = None
            self.tree_items.delete(*self.tree_items.get_children())
            self.lbl_total_cuenta.config(text="Total: $0")
            self._cargar_mesas()
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