"""
ui/documentos.py — El G POS
Documentos comerciales: cotizaciones, órdenes de pedido y remisiones.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from ui.base import (FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL,
                     FONT_BOLD, FONT_SMALL)

# Etiquetas de estado → color
_ESTADO_COLOR = {
    "vigente":   "text",
    "aceptada":  "success",
    "rechazada": "danger",
    "facturada": "accent",
    "entregada": "success",
    "anulada":   "text_dim",
}


class DialogNuevoDocumento(tk.Toplevel):
    """Crea una cotización, orden de pedido o remisión."""

    def __init__(self, parent, tipo: str, on_creado=None):
        super().__init__(parent)
        from modules.documentos import TIPOS
        self._tipo = tipo
        self._on_creado = on_creado
        self._items: list[dict] = []       # {tipo,id,descripcion,cantidad,precio_unit,subtotal}
        self._cliente_id = None
        self._clientes_drop = []

        self.title(f"Nueva {TIPOS[tipo]['label']}")
        self.configure(bg=COLORS["bg"])
        self.grab_set()
        self.focus_force()
        self._build()
        self._centrar(940, 660)
        self.bind("<Escape>", lambda e: self.destroy())

    def _centrar(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── Widgets base (replican estilo de FrameBase) ───────────────────────────
    def _input(self, parent, **kwargs):
        return tk.Entry(parent, font=FONT_LABEL, bg=COLORS["surface2"],
                        fg=COLORS["text"], insertbackground=COLORS["accent"],
                        relief="flat", bd=0, highlightthickness=1,
                        highlightbackground=COLORS["border"],
                        highlightcolor=COLORS["accent"], **kwargs)

    def _tabla(self, parent, columnas, alto=10):
        tree = ttk.Treeview(parent, columns=columnas, show="headings",
                            height=alto, style="POS.Treeview")
        for col in columnas:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=110)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def _btn(self, parent, text, cmd, kind="primary", **kw):
        colores = {
            "primary": (COLORS["accent"], COLORS["on_accent"]),
            "danger":  (COLORS["danger"], COLORS["on_accent"]),
            "sec":     (COLORS["surface2"], COLORS["text_muted"]),
        }[kind]
        kw.setdefault("font", FONT_BOLD)
        b = tk.Button(parent, text=text, bg=colores[0],
                      fg=colores[1], relief="flat", cursor="hand2", command=cmd, **kw)
        return b

    def _build(self):
        outer = tk.Frame(self, bg=COLORS["bg"])
        outer.pack(fill="both", expand=True, padx=16, pady=16)

        # ── Izquierda: catálogo ───────────────────────────────────────────────
        left = tk.Frame(outer, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        search_row = tk.Frame(left, bg=COLORS["bg"])
        search_row.pack(fill="x", pady=(0, 8))
        self.entry_buscar = self._input(search_row)
        self.entry_buscar.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry_buscar.bind("<KeyRelease>", lambda e: self._buscar())

        tab_row = tk.Frame(left, bg=COLORS["bg"])
        tab_row.pack(fill="x", pady=(0, 8))
        self._tab = tk.StringVar(value="tienda")
        for txt, val in [("Tienda", "tienda"), ("Cocina", "cocina"), ("Combos", "combos")]:
            tk.Radiobutton(
                tab_row, text=txt, variable=self._tab, value=val,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._buscar, padx=12, pady=5,
            ).pack(side="left", padx=(0, 4))

        catalogo_wrap = tk.Frame(left, bg=COLORS["bg"])
        catalogo_wrap.pack(fill="both", expand=True)
        self.tree_cat = self._tabla(catalogo_wrap, ("Nombre", "Precio", "Stock"), alto=16)
        self.tree_cat.column("Nombre", width=220, anchor="w")
        self.tree_cat.column("Precio", width=100)
        self.tree_cat.column("Stock", width=70)
        self.tree_cat.bind("<Double-1>", lambda e: self._agregar_item())

        # Ítem de texto libre
        libre_row = tk.Frame(left, bg=COLORS["bg"])
        libre_row.pack(fill="x", pady=(8, 0))
        self._btn(libre_row, "+ Ítem libre (texto)", self._agregar_libre,
                  kind="sec").pack(side="left", ipady=4, ipadx=8)

        # ── Derecha: documento ────────────────────────────────────────────────
        right = tk.Frame(outer, bg=COLORS["surface"],
                         highlightbackground=COLORS["border"], highlightthickness=1,
                         width=380)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="Ítems del documento", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=14, pady=(14, 8))

        items_wrap = tk.Frame(right, bg=COLORS["surface"])
        items_wrap.pack(fill="x", padx=8)
        self.tree_items = self._tabla(items_wrap, ("Ítem", "Cant", "Subtotal"), alto=8)
        self.tree_items.column("Ítem", width=180, anchor="w")
        self.tree_items.column("Cant", width=50)
        self.tree_items.column("Subtotal", width=100, anchor="e")

        qty_row = tk.Frame(right, bg=COLORS["surface"])
        qty_row.pack(fill="x", padx=14, pady=(6, 0))
        self._btn(qty_row, "−", lambda: self._cambiar_qty(-1), kind="sec",
                  width=3, font=("Segoe UI", 13, "bold")).pack(side="left")
        self._btn(qty_row, "✕ Quitar", self._quitar_item, kind="danger").pack(
            side="left", padx=6, ipadx=6)
        self._btn(qty_row, "+", lambda: self._cambiar_qty(1), kind="sec",
                  width=3, font=("Segoe UI", 13, "bold")).pack(side="right")

        tk.Frame(right, bg=COLORS["border"], height=1).pack(fill="x", padx=14, pady=10)

        # Descuento + IVA
        desc_row = tk.Frame(right, bg=COLORS["surface"])
        desc_row.pack(fill="x", padx=14)
        tk.Label(desc_row, text="Descuento ($):", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_desc = self._input(desc_row, width=12)
        self.entry_desc.insert(0, "0")
        self.entry_desc.pack(side="right", ipady=4)
        self.entry_desc.bind("<KeyRelease>", lambda e: self._actualizar_totales())

        self._iva_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            right, text="Discriminar IVA (19%)", variable=self._iva_var,
            font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text"],
            selectcolor=COLORS["surface2"], activebackground=COLORS["surface"],
            activeforeground=COLORS["text"], cursor="hand2",
            command=self._actualizar_totales,
        ).pack(anchor="w", padx=12, pady=(6, 0))

        self.lbl_total = tk.Label(right, text="Total: $0",
                                  font=("Segoe UI", 16, "bold"),
                                  bg=COLORS["surface"], fg=COLORS["accent"])
        self.lbl_total.pack(pady=(8, 6))

        tk.Frame(right, bg=COLORS["border"], height=1).pack(fill="x", padx=14, pady=(4, 8))

        # Cliente
        tk.Label(right, text="Cliente (opcional)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=14)
        self.entry_cli = self._input(right)
        self.entry_cli.pack(fill="x", padx=14, pady=(3, 0), ipady=5)
        self.entry_cli.bind("<KeyRelease>", self._buscar_clientes)
        self.entry_cli.bind("<FocusOut>", lambda e: self.after(150, self._ocultar_drop))
        self.lst_cli = tk.Listbox(
            right, font=FONT_SMALL, height=3, bg=COLORS["surface2"],
            fg=COLORS["text"], selectbackground=COLORS["accent"], relief="flat",
            activestyle="none", highlightthickness=1, highlightbackground=COLORS["border"])
        self.lst_cli.bind("<<ListboxSelect>>", self._seleccionar_cliente)
        self.lbl_cli = tk.Label(right, text="Sin cliente — Consumidor Final",
                                font=("Segoe UI", 8), bg=COLORS["surface"],
                                fg=COLORS["text_dim"], anchor="w")
        self.lbl_cli.pack(fill="x", padx=14, pady=(3, 0))

        # Vigencia (solo cotización)
        if self._tipo == "cotizacion":
            vig_row = tk.Frame(right, bg=COLORS["surface"])
            vig_row.pack(fill="x", padx=14, pady=(6, 0))
            tk.Label(vig_row, text="Válida hasta (YYYY-MM-DD):", font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
            self.entry_vig = self._input(vig_row, width=12)
            self.entry_vig.pack(side="right", ipady=4)
        else:
            self.entry_vig = None

        # Notas
        tk.Label(right, text="Notas", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=14, pady=(6, 0))
        self.entry_notas = self._input(right)
        self.entry_notas.pack(fill="x", padx=14, pady=(3, 8), ipady=4)

        self._btn(right, "✓ Crear documento", self._crear).pack(
            fill="x", padx=14, pady=(4, 12), ipady=8)

        self._buscar()
        self._actualizar_totales()

    # ── Catálogo ──────────────────────────────────────────────────────────────
    def _buscar(self):
        from modules.inventario import listar_productos, buscar_productos
        from modules.ventas import listar_combos
        from modules.caja import formatear_pesos

        texto = self.entry_buscar.get().strip()
        tab = self._tab.get()
        self.tree_cat.delete(*self.tree_cat.get_children())

        if tab == "combos":
            for c in listar_combos():
                if not texto or texto.lower() in c["nombre"].lower():
                    self.tree_cat.insert("", "end", iid=f"combo_{c['id']}",
                                         values=(c["nombre"], formatear_pesos(c["precio"]), "—"))
        else:
            prods = buscar_productos(texto, tipo=tab) if texto else listar_productos(tipo=tab)
            for p in prods:
                self.tree_cat.insert("", "end", iid=f"prod_{p['id']}",
                                     values=(p["nombre"], formatear_pesos(p["precio_venta"]),
                                             p["stock"]))

    def _agregar_item(self):
        from modules.inventario import obtener_producto
        from database import get_connection
        sel = self.tree_cat.focus()
        if not sel:
            return
        clase, _id = sel.split("_")
        _id = int(_id)
        if clase == "prod":
            p = obtener_producto(_id)
            self._push_item({"tipo": "producto", "id": _id, "descripcion": p["nombre"],
                             "precio_unit": p["precio_venta"]})
        else:
            conn = get_connection()
            c = conn.execute("SELECT * FROM combos WHERE id = ?", (_id,)).fetchone()
            conn.close()
            self._push_item({"tipo": "combo", "id": _id, "descripcion": c["nombre"],
                             "precio_unit": c["precio"]})

    def _agregar_libre(self):
        DialogItemLibre(self, self._push_item)

    def _push_item(self, base: dict):
        """Agrega o incrementa un ítem en el documento."""
        for it in self._items:
            if it["tipo"] == base["tipo"] and it.get("id") == base.get("id") \
               and base["tipo"] != "libre":
                it["cantidad"] += base.get("cantidad", 1)
                it["subtotal"] = round(it["cantidad"] * it["precio_unit"], 2)
                self._refrescar_items()
                return
        cantidad = base.get("cantidad", 1)
        self._items.append({
            "tipo": base["tipo"],
            "id": base.get("id"),
            "descripcion": base["descripcion"],
            "cantidad": cantidad,
            "precio_unit": base["precio_unit"],
            "subtotal": round(cantidad * base["precio_unit"], 2),
        })
        self._refrescar_items()

    def _refrescar_items(self):
        from modules.caja import formatear_pesos
        self.tree_items.delete(*self.tree_items.get_children())
        for it in self._items:
            cant = int(it["cantidad"]) if it["cantidad"] == int(it["cantidad"]) else it["cantidad"]
            self.tree_items.insert("", "end", values=(
                it["descripcion"], cant, formatear_pesos(it["subtotal"])))
        self._actualizar_totales()

    def _cambiar_qty(self, delta: int):
        sel = self.tree_items.selection()
        if not sel:
            return
        idx = self.tree_items.index(sel[0])
        it = self._items[idx]
        nueva = it["cantidad"] + delta
        if nueva <= 0:
            self._items.pop(idx)
        else:
            it["cantidad"] = nueva
            it["subtotal"] = round(nueva * it["precio_unit"], 2)
        self._refrescar_items()
        hijos = self.tree_items.get_children()
        if idx < len(hijos):
            self.tree_items.selection_set(hijos[idx])

    def _quitar_item(self):
        sel = self.tree_items.selection()
        if not sel:
            return
        self._items.pop(self.tree_items.index(sel[0]))
        self._refrescar_items()

    def _get_descuento(self) -> float:
        try:
            return max(0, float(self.entry_desc.get().replace(",", "") or 0))
        except ValueError:
            return 0

    def _subtotal(self) -> float:
        return round(sum(it["subtotal"] for it in self._items), 2)

    def _actualizar_totales(self):
        from modules.caja import formatear_pesos
        base = max(0, self._subtotal() - self._get_descuento())
        iva = round(base * 0.19, 2) if self._iva_var.get() else 0
        total = base + iva
        extra = f"  (IVA {formatear_pesos(iva)})" if iva else ""
        self.lbl_total.config(text=f"Total: {formatear_pesos(total)}{extra}")

    # ── Cliente ───────────────────────────────────────────────────────────────
    def _buscar_clientes(self, event=None):
        from modules.clientes import buscar_clientes
        texto = self.entry_cli.get().strip()
        self._cliente_id = None
        self.lbl_cli.config(text="Sin cliente — Consumidor Final", fg=COLORS["text_dim"])
        self.lst_cli.delete(0, "end")
        self._clientes_drop = []
        if not texto:
            self._ocultar_drop()
            return
        res = buscar_clientes(texto)[:6]
        if not res:
            self._ocultar_drop()
            return
        self._clientes_drop = res
        for c in res:
            doc = f"{c['tipo_documento']} {c['documento']}" if c.get("documento") else ""
            self.lst_cli.insert("end", f"  {c['nombre']}  —  {doc}")
        self.lst_cli.pack(fill="x", padx=14)

    def _seleccionar_cliente(self, event=None):
        idx = self.lst_cli.curselection()
        if not idx or idx[0] >= len(self._clientes_drop):
            return
        c = self._clientes_drop[idx[0]]
        self._cliente_id = c["id"]
        self.entry_cli.delete(0, "end")
        self.entry_cli.insert(0, c["nombre"])
        self.lbl_cli.config(text=f"✓ Vinculado — {c['nombre']}", fg=COLORS["success"])
        self._ocultar_drop()

    def _ocultar_drop(self):
        self.lst_cli.pack_forget()

    # ── Crear ─────────────────────────────────────────────────────────────────
    def _crear(self):
        from modules.documentos import crear_documento
        if not self._items:
            messagebox.showwarning("Sin ítems", "Agrega al menos un ítem.", parent=self)
            return
        vigencia = self.entry_vig.get().strip() if self.entry_vig else None
        notas = self.entry_notas.get().strip() or None
        try:
            doc_id = crear_documento(
                self._tipo,
                self._items,
                cliente_id=self._cliente_id,
                descuento=self._get_descuento(),
                iva_porcentaje=0.19 if self._iva_var.get() else 0,
                vigencia=vigencia,
                notas=notas,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
            return
        if self._on_creado:
            self._on_creado(doc_id)
        self.destroy()
        if messagebox.askyesno("Documento creado",
                               f"Documento creado (#{doc_id}).\n¿Imprimir ahora?"):
            from ui.ticket_dialog import mostrar_ticket_documento
            mostrar_ticket_documento(self.master, doc_id)


class DialogItemLibre(tk.Toplevel):
    """Captura un ítem de texto libre (descripción + precio + cantidad)."""

    def __init__(self, parent, on_add):
        super().__init__(parent)
        self._on_add = on_add
        self.title("Ítem libre")
        self.configure(bg=COLORS["bg"])
        self.grab_set()

        card = tk.Frame(self, bg=COLORS["surface"], highlightbackground=COLORS["border"],
                        highlightthickness=1)
        card.pack(padx=18, pady=18, ipadx=12, ipady=12)

        def _entry(lbl):
            tk.Label(card, text=lbl, font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
            e = tk.Entry(card, font=FONT_LABEL, bg=COLORS["surface2"], fg=COLORS["text"],
                         insertbackground=COLORS["accent"], relief="flat",
                         highlightthickness=1, highlightbackground=COLORS["border"])
            e.pack(fill="x", ipady=4)
            return e

        self.e_desc = _entry("Descripción")
        self.e_precio = _entry("Precio unitario ($)")
        self.e_cant = _entry("Cantidad")
        self.e_cant.insert(0, "1")

        tk.Button(card, text="Agregar", font=FONT_BOLD, bg=COLORS["accent"],
                  fg=COLORS["on_accent"], relief="flat", cursor="hand2",
                  command=self._add).pack(fill="x", pady=(12, 0), ipady=6)
        self.e_desc.focus_set()
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{(self.winfo_screenwidth()-w)//2}+{(self.winfo_screenheight()-h)//2}")

    def _add(self):
        desc = self.e_desc.get().strip()
        try:
            precio = float(self.e_precio.get().replace(",", ""))
            cant = float(self.e_cant.get().replace(",", ""))
        except ValueError:
            messagebox.showerror("Error", "Precio y cantidad deben ser números.", parent=self)
            return
        if not desc or precio < 0 or cant <= 0:
            messagebox.showerror("Error", "Completa los campos correctamente.", parent=self)
            return
        self._on_add({"tipo": "libre", "id": None, "descripcion": desc,
                      "precio_unit": precio, "cantidad": cant})
        self.destroy()


class FrameDocumentos(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Documentos Comerciales",
                         "Cotizaciones, órdenes de pedido y remisiones")
        self._filtro_tipo = None
        self._build()

    def _build(self):
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Barra de acciones ─────────────────────────────────────────────────
        toolbar = tk.Frame(main, bg=COLORS["bg"])
        toolbar.pack(fill="x", pady=(0, 12))

        self._btn_primary(toolbar, "+ Cotización",
                          lambda: self._nuevo("cotizacion")).pack(side="left", ipadx=6, ipady=4)
        self._btn_primary(toolbar, "+ Orden de Pedido",
                          lambda: self._nuevo("orden_pedido")).pack(side="left", padx=(8, 0), ipadx=6, ipady=4)
        self._btn_primary(toolbar, "+ Remisión",
                          lambda: self._nuevo("remision")).pack(side="left", padx=(8, 0), ipadx=6, ipady=4)

        # Filtro por tipo
        filtro = tk.Frame(toolbar, bg=COLORS["bg"])
        filtro.pack(side="right")
        self._tipo_var = tk.StringVar(value="todos")
        opciones = [("Todos", "todos"), ("Cotizaciones", "cotizacion"),
                    ("Órdenes", "orden_pedido"), ("Remisiones", "remision")]
        for txt, val in opciones:
            tk.Radiobutton(
                filtro, text=txt, variable=self._tipo_var, value=val,
                font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._recargar, padx=10, pady=4,
            ).pack(side="left", padx=(4, 0))

        # ── Tabla ─────────────────────────────────────────────────────────────
        tabla_wrap = tk.Frame(main, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)
        cols = ("Número", "Tipo", "Fecha", "Cliente", "Total", "Estado")
        self.tree = self._tabla(tabla_wrap, cols, alto=16)
        self.tree.column("Número", width=150, anchor="w")
        self.tree.column("Tipo", width=120)
        self.tree.column("Fecha", width=140)
        self.tree.column("Cliente", width=200, anchor="w")
        self.tree.column("Total", width=110, anchor="e")
        self.tree.column("Estado", width=100)
        self.tree.bind("<Double-1>", lambda e: self._ver_imprimir())
        self.tree.bind("<Button-3>", self._menu_contextual)

        # ── Botones de acción ─────────────────────────────────────────────────
        acciones = tk.Frame(main, bg=COLORS["bg"])
        acciones.pack(fill="x", pady=(12, 0))
        self._btn_primary(acciones, "🖶 Ver / Imprimir", self._ver_imprimir).pack(
            side="left", ipadx=6, ipady=4)
        self._btn_secondary(acciones, "→ Convertir (siguiente)", self._convertir).pack(
            side="left", padx=(8, 0), ipadx=6, ipady=4)
        self._btn_secondary(acciones, "$ Facturar", self._facturar).pack(
            side="left", padx=(8, 0), ipadx=6, ipady=4)
        self._btn_danger(acciones, "✕ Anular", self._anular).pack(
            side="left", padx=(8, 0), ipadx=6, ipady=4)

        # Al facturar un documento: emitir a DIAN o dejarlo solo local.
        self._emitir_factura = tk.BooleanVar(value=False)
        tk.Checkbutton(
            acciones, text="Emitir a DIAN (si no, queda solo local)",
            variable=self._emitir_factura, font=FONT_SMALL,
            bg=COLORS["bg"], fg=COLORS["text"],
            selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
            activeforeground=COLORS["text"], cursor="hand2",
        ).pack(side="right", padx=(0, 4))

        self._recargar()

    # ── Datos ─────────────────────────────────────────────────────────────────
    def _recargar(self):
        from modules.documentos import listar_documentos, TIPOS
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        tipo = self._tipo_var.get()
        docs = listar_documentos(tipo=None if tipo == "todos" else tipo)
        for d in docs:
            self.tree.insert("", "end", iid=str(d["id"]), values=(
                d["numero"],
                TIPOS.get(d["tipo"], {}).get("label", d["tipo"]),
                d["fecha"][:16],
                d.get("cliente_nombre") or "Consumidor Final",
                formatear_pesos(d["total"]),
                d["estado"].capitalize(),
            ))

    def _sel_id(self):
        sel = self.tree.focus()
        return int(sel) if sel else None

    def _nuevo(self, tipo):
        DialogNuevoDocumento(self, tipo, on_creado=lambda _id: self._recargar())

    def _ver_imprimir(self):
        doc_id = self._sel_id()
        if not doc_id:
            messagebox.showinfo("Documentos", "Selecciona un documento.", parent=self)
            return
        from ui.ticket_dialog import mostrar_ticket_documento
        mostrar_ticket_documento(self, doc_id)

    def _convertir(self):
        from modules.documentos import obtener_documento, convertir_documento, TIPOS, _SIGUIENTE
        doc_id = self._sel_id()
        if not doc_id:
            messagebox.showinfo("Documentos", "Selecciona un documento.", parent=self)
            return
        doc = obtener_documento(doc_id)
        siguiente = _SIGUIENTE.get(doc["tipo"])
        if not siguiente:
            messagebox.showinfo("Sin conversión",
                                "Una remisión no se convierte en otro documento.\n"
                                "Usa 'Facturar' para generar la venta.", parent=self)
            return
        if doc["estado"] == "anulada":
            messagebox.showwarning("Anulada", "El documento está anulado.", parent=self)
            return
        if not messagebox.askyesno(
                "Convertir",
                f"Generar {TIPOS[siguiente]['label']} a partir de "
                f"{TIPOS[doc['tipo']]['label']} {doc['numero']}?", parent=self):
            return
        try:
            nuevo = convertir_documento(doc_id)
            self._recargar()
            messagebox.showinfo("Convertido",
                                f"{TIPOS[siguiente]['label']} generada (#{nuevo}).", parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _facturar(self):
        from modules.documentos import obtener_documento, cargar_en_carrito, marcar_facturado
        from modules.caja import get_sesion_activa
        from modules.ui_pago import abrir_dialogo_pago

        doc_id = self._sel_id()
        if not doc_id:
            messagebox.showinfo("Documentos", "Selecciona un documento.", parent=self)
            return
        doc = obtener_documento(doc_id)
        if doc["estado"] == "facturada":
            messagebox.showinfo("Ya facturada",
                                f"Ese documento ya fue facturado (venta #{doc['venta_id']}).",
                                parent=self)
            return
        if doc["estado"] == "anulada":
            messagebox.showwarning("Anulada", "El documento está anulado.", parent=self)
            return
        try:
            carrito, omitidos = cargar_en_carrito(doc_id)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
            return
        if carrito.esta_vacio():
            messagebox.showwarning(
                "Sin ítems facturables",
                "Ningún ítem del documento se puede facturar "
                "(ítems de texto libre o sin stock).", parent=self)
            return
        if omitidos:
            if not messagebox.askyesno(
                    "Ítems omitidos",
                    "Los siguientes ítems no se facturarán:\n\n" +
                    "\n".join(f"• {o}" for o in omitidos) +
                    "\n\n¿Continuar con el resto?", parent=self):
                return

        sesion = get_sesion_activa()
        sesion_id = sesion["id"] if sesion else None

        emitir_dian = self._emitir_factura.get()

        def _on_pago(pagos):
            from modules.ventas import registrar_venta
            try:
                venta_id = registrar_venta(
                    carrito, pagos=pagos, sesion_id=sesion_id,
                    cliente_id=doc["cliente_id"],
                    emitir_factura=emitir_dian or bool(doc["cliente_id"]),
                )
                marcar_facturado(doc_id, venta_id)
                self._recargar()

                # Emitir a DIAN / registrar en backend (local si emitir_dian=False).
                self._sync_dian(venta_id, pagos, doc["cliente_id"], emitir_dian)

                if messagebox.askyesno("Facturado",
                                       f"Venta #{venta_id} registrada.\n¿Imprimir ticket?",
                                       parent=self):
                    from ui.ticket_dialog import mostrar_ticket_venta
                    mostrar_ticket_venta(self, venta_id)
            except Exception as e:
                messagebox.showerror("Error al facturar", str(e), parent=self)

        abrir_dialogo_pago(self, carrito.total(), _on_pago,
                           cliente_id=doc["cliente_id"])

    def _sync_dian(self, venta_id, pagos, cliente_id, emitir_dian):
        """Sincroniza la venta al backend: emite a DIAN o la deja solo local.

        Igual que en Ventas/Cuentas: sincroniza siempre que el backend esté
        configurado; el flag `emitir_dian` decide si se transmite a DIAN o
        queda como factura local (numeración LOC).
        """
        from modules.dian_client import is_configured
        if not is_configured():
            return

        try:
            from database import get_connection
            from modules.fiscal_documents import preparar_venta_para_dian
            from modules.sync import get_sync_manager

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

            cliente = None
            if cliente_id:
                from modules.clientes import obtener_cliente
                cliente = obtener_cliente(cliente_id)

            dian_payload = preparar_venta_para_dian(
                venta_data, cliente, emitir_dian=emitir_dian
            )

            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                dian_result = {"status": "pendiente", "mensaje": "Sincronización en cola"}
            else:
                dian_result = loop.run_until_complete(
                    get_sync_manager().process_venta(dian_payload)
                )
        except Exception as e:
            dian_result = {"status": "error", "error": str(e)}

        # Solo mostramos el diálogo DIAN cuando se pidió emitir.
        if emitir_dian and dian_result.get("status") != "no_configurado":
            from ui.ventas import DialogDianStatus
            DialogDianStatus(self, dian_result)

    def _anular(self):
        from modules.documentos import anular_documento
        doc_id = self._sel_id()
        if not doc_id:
            messagebox.showinfo("Documentos", "Selecciona un documento.", parent=self)
            return
        if not messagebox.askyesno("Anular", "¿Anular este documento?", parent=self):
            return
        anular_documento(doc_id)
        self._recargar()

    def _menu_contextual(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.focus(row)
        self.tree.selection_set(row)
        menu = tk.Menu(self, tearoff=0, bg=COLORS["surface"], fg=COLORS["text"],
                       activebackground=COLORS["accent"], activeforeground=COLORS["on_accent"])
        menu.add_command(label="Ver / Imprimir", command=self._ver_imprimir)
        menu.add_command(label="Convertir al siguiente", command=self._convertir)
        menu.add_command(label="Facturar", command=self._facturar)
        menu.add_separator()
        menu.add_command(label="Anular", command=self._anular)
        menu.post(event.x_root, event.y_root)
