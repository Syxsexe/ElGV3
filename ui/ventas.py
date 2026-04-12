"""
ui/ventas.py — El G POS
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI

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

        # Confirmar — el método de pago se elige en el diálogo
        self._btn_primary(right, "✓ Confirmar Venta",
                          self._confirmar_venta).pack(fill="x", padx=16, ipady=10)
        tk.Button(right, text="Limpiar carrito", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self._limpiar_carrito).pack(pady=(8, 16))

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

        try:
            venta_id = registrar_venta(
                self.carrito,
                pagos=pagos,
                sesion_id=self.sesion_id
            )
            total_str = formatear_pesos(sum(p["monto"] for p in pagos))
            metodos   = " + ".join(p["metodo"] for p in pagos)
            messagebox.showinfo("Venta registrada",
                                f"✓ Venta #{venta_id} registrada\nTotal: {total_str}\nMétodo: {metodos}")
            self._actualizar_carrito()   # limpia el carrito en pantalla
            self._buscar()               # refresca stock en el catálogo
        except Exception as e:
            messagebox.showerror("Error", str(e))

