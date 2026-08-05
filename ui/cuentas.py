"""
ui/cuentas.py — El G POS

Pantalla de Cuentas (mesas abiertas) rediseñada a un flujo con BOTONES + modales:
  • "+ Abrir cuenta nueva"  → modal (cliente + mesa)
  • "+ Agregar consumo"     → modal (buscar producto/combo + cantidad, agrega en cadena)
  • "✓ Cobrar"              → modal (descuento + DIAN) → diálogo de pago
  • "✕ Cancelar cuenta"     → confirma y descarta

A la izquierda las mesas abiertas; a la derecha el detalle de la cuenta
seleccionada con sus acciones. Los formularios ya no viven en un panel lateral
siempre visible, sino que se abren bajo demanda.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import auth
from ui.base import (FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL,
                     FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI)
from ui.modal import ModalForm


def _fmt_cant(n) -> str:
    """Muestra una cantidad sin decimales si es entera."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    return f"{int(n)}" if n == int(n) else f"{n:g}"


class FrameCuentas(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Cuentas", "Mesas abiertas y consumo por cliente")
        from modules.cuentas import migrar
        migrar()
        self._cuenta_sel        = None   # ID de cuenta seleccionada
        self._descuento_actual  = 0      # se fija al abrir el modal de cobro
        self._emitir_dian       = False  # se fija al abrir el modal de cobro
        self._build()

    # ══════════════════════════════════════════════════════════════════════
    # LAYOUT PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════

    def _build(self):
        # ── Barra de acciones ──────────────────────────────────────────────
        acciones = tk.Frame(self, bg=COLORS["bg"])
        acciones.pack(fill="x", padx=32, pady=(0, 12))
        self._btn_primary(acciones, "+ Abrir cuenta nueva",
                          self._modal_abrir_cuenta).pack(
                              side="left", ipady=7, ipadx=16)
        self._btn_secondary(acciones, "↻ Actualizar", self._cargar_mesas).pack(
            side="left", padx=(10, 0), ipady=7, ipadx=12)

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Panel derecho: detalle de la cuenta seleccionada ───────────────
        right = self._card(main, width=352)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self._build_detalle(right)

        # ── Panel izquierdo: mesas abiertas ────────────────────────────────
        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))

        tk.Label(left, text="Mesas abiertas", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))
        tk.Label(left, text="Selecciona una mesa para ver y gestionar su cuenta.",
                 font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(
                     anchor="w", pady=(0, 6))

        lista_wrap = tk.Frame(left, bg=COLORS["bg"])
        lista_wrap.pack(fill="both", expand=True)

        self.tree_mesas = self._tabla(
            lista_wrap,
            ("id_cuenta", "mesa", "cliente", "items", "total", "desde"),
            alto=16,
        )
        self.tree_mesas.heading("id_cuenta", text="#")
        self.tree_mesas.heading("mesa",      text="Mesa")
        self.tree_mesas.heading("cliente",   text="Cliente")
        self.tree_mesas.heading("items",     text="Ítems")
        self.tree_mesas.heading("total",     text="Total")
        self.tree_mesas.heading("desde",     text="Desde")
        self.tree_mesas.column("id_cuenta", width=40)
        self.tree_mesas.column("mesa",      width=90)
        self.tree_mesas.column("cliente",   width=160, anchor="w")
        self.tree_mesas.column("items",     width=55)
        self.tree_mesas.column("total",     width=110)
        self.tree_mesas.column("desde",     width=80)
        self.tree_mesas.bind("<<TreeviewSelect>>", self._al_seleccionar)

        self._cargar_mesas()

    def _build_detalle(self, right):
        """Panel derecho: cabecera de la cuenta, ítems y botones de acción."""
        pad = 16

        self.lbl_cuenta_titulo = tk.Label(
            right, text="Ninguna mesa seleccionada", font=FONT_BOLD,
            bg=COLORS["surface"], fg=COLORS["text"], anchor="w",
            wraplength=320, justify="left")
        self.lbl_cuenta_titulo.pack(fill="x", padx=pad, pady=(pad, 2))

        self.lbl_cuenta_sub = tk.Label(
            right, text="Abre o selecciona una cuenta para empezar.",
            font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text_muted"],
            anchor="w", wraplength=320, justify="left")
        self.lbl_cuenta_sub.pack(fill="x", padx=pad, pady=(0, 10))

        # ── Ítems de la cuenta ─────────────────────────────────────────────
        items_wrap = tk.Frame(right, bg=COLORS["surface"])
        items_wrap.pack(fill="both", expand=True, padx=pad)

        self.tree_items = self._tabla(
            items_wrap,
            ("item_id", "nombre", "cantidad", "subtotal"),
            alto=9,
        )
        self.tree_items.heading("item_id",  text="#")
        self.tree_items.heading("nombre",   text="Producto / Combo")
        self.tree_items.heading("cantidad", text="Cant")
        self.tree_items.heading("subtotal", text="Subtotal")
        self.tree_items.column("item_id",  width=0, stretch=False)  # oculto
        self.tree_items.column("nombre",   width=150, anchor="w")
        self.tree_items.column("cantidad", width=45)
        self.tree_items.column("subtotal", width=90)
        self.tree_items.bind("<<TreeviewSelect>>", self._al_seleccionar_item)

        # ── Controles de cantidad del ítem seleccionado ────────────────────
        qty_row = tk.Frame(right, bg=COLORS["surface"])
        qty_row.pack(anchor="w", padx=pad, pady=(8, 0))

        tk.Button(qty_row, text="−", font=("Segoe UI", 13, "bold"),
                  bg=COLORS["surface2"], fg=COLORS["text"],
                  activebackground=COLORS["border"], activeforeground=COLORS["text"],
                  relief="flat", cursor="hand2", width=3,
                  command=self._decrementar_item).pack(side="left")
        self.lbl_qty_cuenta = tk.Label(
            qty_row, text="—", font=FONT_BOLD,
            bg=COLORS["surface"], fg=COLORS["text"], width=7)
        self.lbl_qty_cuenta.pack(side="left")
        tk.Button(qty_row, text="+", font=("Segoe UI", 13, "bold"),
                  bg=COLORS["surface2"], fg=COLORS["text"],
                  activebackground=COLORS["border"], activeforeground=COLORS["text"],
                  relief="flat", cursor="hand2", width=3,
                  command=self._incrementar_item).pack(side="left")
        self._btn_secondary(qty_row, "✕ Quitar", self._quitar_item).pack(
            side="left", padx=(10, 0), ipady=2, ipadx=6)

        # ── Total ──────────────────────────────────────────────────────────
        tk.Frame(right, bg=COLORS["border"], height=1).pack(
            fill="x", padx=pad, pady=12)
        self.lbl_total_cuenta = tk.Label(
            right, text="Total: $0", font=("Segoe UI", 17, "bold"),
            bg=COLORS["surface"], fg=COLORS["accent"], anchor="e")
        self.lbl_total_cuenta.pack(fill="x", padx=pad)

        # ── Acciones de la cuenta ──────────────────────────────────────────
        self._btn_primary(right, "+ Agregar consumo", self._modal_agregar).pack(
            fill="x", padx=pad, pady=(12, 6), ipady=9)

        btn_cobrar = tk.Button(
            right, text="✓ Cobrar cuenta", font=FONT_BOLD,
            bg=COLORS["success"], fg=COLORS["on_accent"],
            activebackground=COLORS["success"], activeforeground=COLORS["on_accent"],
            relief="flat", cursor="hand2", command=self._modal_cobrar)
        btn_cobrar.pack(fill="x", padx=pad, ipady=10)

        self._btn_danger(right, "✕ Cancelar cuenta", self._cancelar).pack(
            fill="x", padx=pad, pady=(6, 16), ipady=6)

    # ══════════════════════════════════════════════════════════════════════
    # CARGA / SELECCIÓN
    # ══════════════════════════════════════════════════════════════════════

    def _cargar_mesas(self):
        from modules.cuentas import listar_cuentas_abiertas
        from modules.caja import formatear_pesos

        self.tree_mesas.delete(*self.tree_mesas.get_children())
        for c in listar_cuentas_abiertas():
            self.tree_mesas.insert("", "end", iid=str(c["id"]), values=(
                c["id"], c["mesa"], c["cliente"],
                c["num_items"],
                formatear_pesos(c["total"]),
                c["abierta_en"][11:16],   # solo HH:MM
            ))

    def _refrescar_cuenta_sel(self):
        """Recarga mesas + ítems manteniendo la cuenta seleccionada."""
        cid = self._cuenta_sel
        self._cargar_mesas()
        if cid is not None and self.tree_mesas.exists(str(cid)):
            self.tree_mesas.selection_set(str(cid))
            self.tree_mesas.focus(str(cid))
            self._al_seleccionar()
        else:
            self._limpiar_detalle()

    def _limpiar_detalle(self):
        self._cuenta_sel = None
        self.tree_items.delete(*self.tree_items.get_children())
        self.lbl_cuenta_titulo.config(text="Ninguna mesa seleccionada")
        self.lbl_cuenta_sub.config(text="Abre o selecciona una cuenta para empezar.")
        self.lbl_total_cuenta.config(text="Total: $0")
        self.lbl_qty_cuenta.config(text="—")

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

        self.lbl_cuenta_titulo.config(text=f"{cuenta['mesa']} — {cuenta['cliente']}")
        n = len(cuenta["items"])
        self.lbl_cuenta_sub.config(
            text=f"{n} ítem{'s' if n != 1 else ''} · abierta {cuenta['abierta_en'][11:16]}")

        self.tree_items.delete(*self.tree_items.get_children())
        for item in cuenta["items"]:
            self.tree_items.insert("", "end", iid=str(item["id"]), values=(
                item["id"], item["nombre"],
                _fmt_cant(item["cantidad"]),
                formatear_pesos(item["subtotal"]),
            ))
        self.lbl_total_cuenta.config(text=f"Total: {formatear_pesos(cuenta['total'])}")
        self.lbl_qty_cuenta.config(text="—")

    # ══════════════════════════════════════════════════════════════════════
    # MODAL — ABRIR CUENTA NUEVA
    # ══════════════════════════════════════════════════════════════════════

    def _modal_abrir_cuenta(self):
        from modules.clientes import buscar_clientes

        m = ModalForm(self, "Abrir cuenta nueva", ancho=420)
        b = m.body
        estado = {"cliente_id": None, "resultados": []}

        tk.Label(b, text="Cliente", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(12, 0))
        entry_cliente = self._input(b)
        entry_cliente.pack(fill="x", padx=16, pady=(2, 0), ipady=5)

        drop = tk.Frame(b, bg=COLORS["surface"])
        drop.pack(fill="x", padx=16)
        lst = tk.Listbox(drop, font=FONT_SMALL, height=4,
                         bg=COLORS["surface2"], fg=COLORS["text"],
                         selectbackground=COLORS["accent"], relief="flat",
                         activestyle="none", highlightthickness=1,
                         highlightbackground=COLORS["border"])
        lbl_sel = tk.Label(b, text="Sin cliente registrado (opcional).",
                           font=("Segoe UI", 8), bg=COLORS["surface"],
                           fg=COLORS["text_muted"], anchor="w",
                           wraplength=360, justify="left")
        lbl_sel.pack(fill="x", padx=16, pady=(2, 6))

        def buscar(event=None):
            estado["cliente_id"] = None
            lbl_sel.config(text="Sin cliente registrado (opcional).",
                           fg=COLORS["text_muted"])
            texto = entry_cliente.get().strip()
            lst.delete(0, "end")
            estado["resultados"] = []
            if not texto:
                lst.pack_forget()
                return
            resultados = buscar_clientes(texto)[:8]
            if not resultados:
                lst.pack_forget()
                return
            estado["resultados"] = resultados
            for c in resultados:
                doc = f"{c['tipo_documento']} {c['documento']}" if c.get("documento") else ""
                lst.insert("end", f"  {c['nombre']}  —  {doc}")
            lst.pack(fill="x", pady=(2, 0))

        def seleccionar(event=None):
            idx = lst.curselection()
            if not idx or idx[0] >= len(estado["resultados"]):
                return
            c = estado["resultados"][idx[0]]
            estado["cliente_id"] = c["id"]
            entry_cliente.delete(0, "end")
            entry_cliente.insert(0, c["nombre"])
            doc = f"{c['tipo_documento']} {c['documento']}" if c.get("documento") else ""
            lbl_sel.config(text=f"✓ Cliente vinculado — {doc}" if doc else "✓ Cliente vinculado",
                           fg=COLORS["success"])
            lst.pack_forget()

        entry_cliente.bind("<KeyRelease>", buscar)
        lst.bind("<<ListboxSelect>>", seleccionar)

        tk.Label(b, text="Mesa / Puesto", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        entry_mesa = self._input(b)
        entry_mesa.pack(fill="x", padx=16, pady=(2, 12), ipady=5)

        def guardar():
            from modules.cuentas import abrir_cuenta
            cliente = entry_cliente.get().strip()
            mesa    = entry_mesa.get().strip()
            if not cliente or not mesa:
                messagebox.showwarning("Campos vacíos",
                                       "Completa cliente y mesa.", parent=m)
                return
            try:
                nueva_id = abrir_cuenta(cliente, mesa, cliente_id=estado["cliente_id"])
                m.cerrar()
                self._cuenta_sel = nueva_id
                self._refrescar_cuenta_sel()
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=m)

        self._btn_primary(m.footer, "Abrir cuenta", guardar).pack(
            side="right", ipady=6, ipadx=12)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="right", padx=(0, 8), ipady=6, ipadx=10)
        entry_cliente.focus_set()
        m.mostrar()

    # ══════════════════════════════════════════════════════════════════════
    # MODAL — AGREGAR CONSUMO
    # ══════════════════════════════════════════════════════════════════════

    def _modal_agregar(self):
        from modules.cuentas import obtener_cuenta, agregar_item
        from modules.inventario import buscar_productos, listar_productos
        from modules.ventas import listar_combos
        from modules.validaciones import aplicar_validacion

        if not self._cuenta_sel:
            messagebox.showwarning("Sin selección", "Selecciona una mesa primero.")
            return
        cuenta = obtener_cuenta(self._cuenta_sel)
        if not cuenta:
            return

        m = ModalForm(self, f"Agregar consumo — {cuenta['mesa']}", ancho=440)
        b = m.body
        resultados = []   # paralelo a lst

        tk.Label(b, text="Buscar producto o combo", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(12, 0))
        entry = self._input(b)
        entry.pack(fill="x", padx=16, pady=(2, 6), ipady=5)

        lst_wrap = tk.Frame(b, bg=COLORS["surface"])
        lst_wrap.pack(fill="x", padx=16)
        lst = tk.Listbox(lst_wrap, font=FONT_SMALL, height=9,
                         bg=COLORS["surface2"], fg=COLORS["text"],
                         selectbackground=COLORS["accent"], relief="flat",
                         activestyle="none", highlightthickness=1,
                         highlightbackground=COLORS["border"])
        lst.pack(fill="x")

        cant_row = tk.Frame(b, bg=COLORS["surface"])
        cant_row.pack(anchor="w", padx=16, pady=(8, 0))
        tk.Label(cant_row, text="Cantidad", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(side="left", padx=(0, 8))
        entry_cant = self._input(cant_row, width=6)
        entry_cant.insert(0, "1")
        entry_cant.pack(side="left", ipady=3)
        aplicar_validacion(entry_cant, "cantidad")

        lbl_feedback = tk.Label(b, text="", font=FONT_SMALL, bg=COLORS["surface"],
                                fg=COLORS["success"], anchor="w",
                                wraplength=400, justify="left")
        lbl_feedback.pack(fill="x", padx=16, pady=(10, 12))

        def buscar():
            texto = entry.get().strip()
            lst.delete(0, "end")
            resultados.clear()
            prods  = buscar_productos(texto) if texto else listar_productos()
            combos = [c for c in listar_combos()
                      if not texto or texto.lower() in c["nombre"].lower()]
            tienda = [p for p in prods if p["categoria_tipo"] == "tienda"]
            cocina = [p for p in prods if p["categoria_tipo"] == "cocina"]

            def add_grupo(titulo, filas, tipo, limite):
                if not filas:
                    return
                lst.insert("end", f"── {titulo} ──")
                resultados.append(None)
                for x in filas[:limite]:
                    lst.insert("end", f"  {x['nombre']}")
                    resultados.append((tipo, x["id"]))

            add_grupo("Tienda", tienda, "producto", 14)
            add_grupo("Cocina", cocina, "producto", 12)
            add_grupo("Combos", combos, "combo", 8)

        def agregar():
            idx = lst.curselection()
            if not idx:
                messagebox.showwarning("Sin selección",
                                       "Selecciona un producto de la lista.", parent=m)
                return
            r = resultados[idx[0]]
            if r is None:   # separador de grupo
                return
            try:
                cantidad = float(entry_cant.get() or 1)
            except ValueError:
                messagebox.showwarning("Cantidad inválida",
                                       "Ingresa un número válido.", parent=m)
                return
            if cantidad <= 0:
                messagebox.showwarning("Cantidad inválida",
                                       "La cantidad debe ser mayor que cero.", parent=m)
                return
            tipo, item_id = r
            try:
                if tipo == "producto":
                    it = agregar_item(self._cuenta_sel, producto_id=item_id, cantidad=cantidad)
                else:
                    it = agregar_item(self._cuenta_sel, combo_id=item_id, cantidad=cantidad)
                lbl_feedback.config(
                    text=f"✓ Agregado: {_fmt_cant(cantidad)} × {it['nombre']}")
                self._refrescar_cuenta_sel()
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=m)

        entry.bind("<KeyRelease>", lambda e: buscar())
        lst.bind("<Double-Button-1>", lambda e: agregar())
        buscar()

        self._btn_primary(m.footer, "+ Agregar", agregar).pack(
            side="right", ipady=6, ipadx=12)
        self._btn_secondary(m.footer, "Listo", m.cerrar).pack(
            side="right", padx=(0, 8), ipady=6, ipadx=10)
        entry.focus_set()
        m.mostrar()

    # ══════════════════════════════════════════════════════════════════════
    # CONTROLES +/- Y QUITAR ÍTEM
    # ══════════════════════════════════════════════════════════════════════

    def _al_seleccionar_item(self, event=None):
        sel = self.tree_items.selection()
        if not sel:
            self.lbl_qty_cuenta.config(text="—")
            return
        vals = self.tree_items.item(sel[0], "values")
        if vals:
            self.lbl_qty_cuenta.config(text=f"×{vals[2]}")

    def _cambiar_cantidad(self, delta):
        sel = self.tree_items.selection()
        if not sel:
            return
        vals    = self.tree_items.item(sel[0], "values")
        item_id = int(vals[0])
        try:
            nueva = float(vals[2]) + delta
        except (ValueError, TypeError):
            return
        from modules.cuentas import cambiar_cantidad_item
        try:
            cambiar_cantidad_item(item_id, nueva)   # quita si nueva <= 0
            self._refrescar_cuenta_sel()
            iid = str(item_id)
            if self.tree_items.exists(iid):
                self.tree_items.selection_set(iid)
                self.tree_items.focus(iid)
                self._al_seleccionar_item()
            else:
                self.lbl_qty_cuenta.config(text="—")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _incrementar_item(self):
        self._cambiar_cantidad(+1)

    def _decrementar_item(self):
        self._cambiar_cantidad(-1)

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
            self._refrescar_cuenta_sel()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    # ══════════════════════════════════════════════════════════════════════
    # MODAL — COBRAR
    # ══════════════════════════════════════════════════════════════════════

    def _modal_cobrar(self):
        from modules.cuentas import obtener_cuenta
        from modules.caja import formatear_pesos
        from modules.validaciones import aplicar_validacion, leer_entero
        from modules.dian_client import is_configured

        if not self._cuenta_sel:
            messagebox.showwarning("Sin selección", "Selecciona una mesa para cobrar.")
            return
        cuenta = obtener_cuenta(self._cuenta_sel)
        if not cuenta or not cuenta["items"]:
            messagebox.showwarning("Cuenta vacía", "La cuenta no tiene ítems.")
            return

        bruto = cuenta["total"]
        m = ModalForm(self, f"Cobrar — {cuenta['mesa']}", ancho=400)
        b = m.body

        tk.Label(b, text=f"Cliente: {cuenta['cliente']}", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(14, 2))

        lbl_total = tk.Label(b, text=f"Total a cobrar: {formatear_pesos(bruto)}",
                             font=("Segoe UI", 16, "bold"), bg=COLORS["surface"],
                             fg=COLORS["accent"], anchor="w")
        lbl_total.pack(anchor="w", padx=16, pady=(0, 10))

        tk.Label(b, text="Descuento ($)", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        entry_desc = self._input(b)
        entry_desc.pack(fill="x", padx=16, pady=(2, 6), ipady=4)
        aplicar_validacion(entry_desc, "monto")

        def clamp_desc():
            return max(0, min(leer_entero(entry_desc), bruto))

        def recalc(event=None):
            neto = bruto - clamp_desc()
            lbl_total.config(text=f"Total a cobrar: {formatear_pesos(neto)}")

        entry_desc.bind("<KeyRelease>", recalc)

        var_dian = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(
            b, text="Emitir a DIAN (si no, queda solo local)",
            variable=var_dian, font=FONT_SMALL, bg=COLORS["surface"],
            fg=COLORS["text"], selectcolor=COLORS["surface2"],
            activebackground=COLORS["surface"], activeforeground=COLORS["text"],
            cursor="hand2")
        chk.pack(anchor="w", padx=16, pady=(8, 4))
        if not is_configured():
            var_dian.set(False)
            chk.config(state="disabled")
            tk.Label(b, text="⚠ DIAN no configurado — se cobrará local.",
                     font=("Segoe UI", 8), bg=COLORS["surface"],
                     fg=COLORS["warning"], anchor="w").pack(
                         anchor="w", padx=16, pady=(0, 8))
        else:
            tk.Label(b, text="✓ DIAN configurado", font=("Segoe UI", 8),
                     bg=COLORS["surface"], fg=COLORS["success"], anchor="w").pack(
                         anchor="w", padx=16, pady=(0, 8))

        def continuar():
            from modules.ui_pago import abrir_dialogo_pago
            self._descuento_actual = clamp_desc()
            self._emitir_dian      = var_dian.get()
            total_final = max(0, bruto - self._descuento_actual)
            m.cerrar()
            abrir_dialogo_pago(
                self, total_final, self._procesar_cobro,
                titulo=f"Cobrar — {cuenta['cliente']} / {cuenta['mesa']}",
                cliente_id=cuenta.get("cliente_id"),
            )

        self._btn_primary(m.footer, "Continuar al pago →", continuar).pack(
            side="right", ipady=6, ipadx=12)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="right", padx=(0, 8), ipady=6, ipadx=10)
        m.mostrar()

    def _procesar_cobro(self, pagos: list):
        from modules.cuentas import cobrar_cuenta, obtener_cuenta
        from modules.caja import get_sesion_activa, formatear_pesos
        from modules.fiscal_documents import preparar_venta_para_dian
        from modules.sync import get_sync_manager
        from modules.dian_client import is_configured

        cuenta      = obtener_cuenta(self._cuenta_sel)
        sesion      = get_sesion_activa()
        emitir_dian = self._emitir_dian
        descuento   = self._descuento_actual

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
            self._limpiar_detalle()
            self._descuento_actual = 0
            self._emitir_dian      = False
            self._cargar_mesas()

            # ── Sync backend ──────────────────────────────────────────────
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
                    venta_data["pagos"]   = pagos

                    cliente = None
                    if cuenta.get("cliente_id"):
                        from modules.clientes import obtener_cliente
                        cliente = obtener_cliente(cuenta["cliente_id"])

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

            if emitir_dian and dian_result.get("status") != "no_configurado":
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

    # ══════════════════════════════════════════════════════════════════════
    # CANCELAR CUENTA
    # ══════════════════════════════════════════════════════════════════════

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
            self._limpiar_detalle()
            self._cargar_mesas()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
