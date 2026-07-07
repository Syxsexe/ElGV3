"""
ui/consulta_precios.py — El G POS
Consulta de precios con lector de código de barras / QR.

El campo de entrada mantiene el foco: un lector de código de barras funciona
como un teclado que "escribe" el código y envía Enter, disparando la búsqueda
por código exacto. También permite búsqueda manual por nombre o código.
"""
import tkinter as tk
from tkinter import ttk

from ui.base import (FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL,
                     FONT_BOLD, FONT_SMALL)


class FrameConsultaPrecios(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Consulta de Precios",
                         "Escanea un código de barras/QR o busca por nombre")
        self._build()

    def _build(self):
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Campo de escaneo/búsqueda ─────────────────────────────────────────
        scan_card = self._card(main)
        scan_card.pack(fill="x", pady=(0, 20))
        inner = tk.Frame(scan_card, bg=COLORS["surface"])
        inner.pack(fill="x", padx=20, pady=18)

        tk.Label(inner, text="🔎  Código de barras / QR o nombre",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 8))

        self.entry = tk.Entry(
            inner, font=("Segoe UI", 20), bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"], relief="flat", bd=0,
            highlightthickness=2, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"])
        self.entry.pack(fill="x", ipady=10)
        self.entry.bind("<Return>", lambda e: self._buscar_exacto())
        self.entry.bind("<KeyRelease>", self._on_type)
        self.entry.focus_set()

        # ── Ficha del producto ────────────────────────────────────────────────
        self.ficha = self._card(main)
        self.ficha.pack(fill="x", pady=(0, 16))
        self._render_vacio()

        # ── Sugerencias (búsqueda parcial por nombre) ─────────────────────────
        sug_label = tk.Label(main, text="Coincidencias", font=FONT_BOLD,
                             bg=COLORS["bg"], fg=COLORS["text_muted"])
        sug_label.pack(anchor="w", pady=(4, 6))

        tabla_wrap = tk.Frame(main, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)
        self.tree = self._tabla(tabla_wrap, ("Código", "Nombre", "Precio", "Stock"), alto=8)
        self.tree.column("Código", width=140, anchor="w")
        self.tree.column("Nombre", width=280, anchor="w")
        self.tree.column("Precio", width=120, anchor="e")
        self.tree.column("Stock", width=80)
        self.tree.bind("<Double-1>", lambda e: self._seleccionar_fila())
        self.tree.bind("<Return>", lambda e: self._seleccionar_fila())

    # ── Render de la ficha ────────────────────────────────────────────────────
    def _limpiar_ficha(self):
        for w in self.ficha.winfo_children():
            w.destroy()

    def _render_vacio(self):
        self._limpiar_ficha()
        inner = tk.Frame(self.ficha, bg=COLORS["surface"])
        inner.pack(fill="x", padx=24, pady=30)
        tk.Label(inner, text="Escanea o escribe un producto para ver su precio",
                 font=FONT_SUB, bg=COLORS["surface"],
                 fg=COLORS["text_dim"]).pack()

    def _render_no_encontrado(self, texto):
        self._limpiar_ficha()
        inner = tk.Frame(self.ficha, bg=COLORS["surface"])
        inner.pack(fill="x", padx=24, pady=24)
        tk.Label(inner, text="✗  Sin resultados", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["danger"]).pack(anchor="w")
        tk.Label(inner, text=f'No se encontró el código "{texto}".',
                 font=FONT_LABEL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", pady=(4, 0))

    def _render_producto(self, p):
        from modules.caja import formatear_pesos
        self._limpiar_ficha()
        inner = tk.Frame(self.ficha, bg=COLORS["surface"])
        inner.pack(fill="x", padx=24, pady=20)

        # Nombre
        tk.Label(inner, text=p["nombre"], font=("Segoe UI", 20, "bold"),
                 bg=COLORS["surface"], fg=COLORS["text"],
                 wraplength=640, justify="left").pack(anchor="w")

        meta = []
        if p.get("codigo"):
            meta.append(f"Código: {p['codigo']}")
        if p.get("categoria_nombre"):
            meta.append(p["categoria_nombre"])
        if meta:
            tk.Label(inner, text="   ·   ".join(meta), font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", pady=(2, 12))

        # Precio grande
        tk.Label(inner, text=formatear_pesos(p["precio_venta"]),
                 font=("Segoe UI", 42, "bold"), bg=COLORS["surface"],
                 fg=COLORS["accent"]).pack(anchor="w")

        # Stock
        stock = p.get("stock", 0)
        es_tienda = p.get("categoria_tipo") == "tienda"
        if es_tienda:
            if stock <= 0:
                color, txt = COLORS["danger"], "Agotado"
            elif stock <= (p.get("stock_minimo") or 0):
                color, txt = COLORS["warning"], f"Stock bajo: {stock:g}"
            else:
                color, txt = COLORS["success"], f"Disponible: {stock:g}"
        else:
            color, txt = COLORS["text_muted"], "Producto de cocina (según insumos)"
        tk.Label(inner, text=txt, font=FONT_BOLD, bg=COLORS["surface"],
                 fg=color).pack(anchor="w", pady=(10, 0))

    # ── Búsqueda ──────────────────────────────────────────────────────────────
    def _reset_scan(self):
        self.entry.delete(0, "end")
        self.entry.focus_set()

    def _buscar_exacto(self):
        """Enter / escaneo: intenta código exacto; si no, cae a búsqueda parcial."""
        from modules.inventario import obtener_producto_por_codigo
        texto = self.entry.get().strip()
        if not texto:
            return
        p = obtener_producto_por_codigo(texto)
        if p:
            self._render_producto(p)
            self._llenar_tabla([])
            self._reset_scan()
            return
        # No hay match exacto por código: mostrar coincidencias parciales
        resultados = self._buscar_parcial(texto)
        if len(resultados) == 1:
            self._render_producto(resultados[0])
            self._llenar_tabla([])
            self._reset_scan()
        elif resultados:
            self._render_vacio()
            self._llenar_tabla(resultados)
        else:
            self._render_no_encontrado(texto)
            self._llenar_tabla([])

    def _on_type(self, event=None):
        # Ignorar Enter (lo maneja _buscar_exacto)
        if event and event.keysym == "Return":
            return
        texto = self.entry.get().strip()
        if len(texto) < 2:
            self._llenar_tabla([])
            return
        self._llenar_tabla(self._buscar_parcial(texto))

    def _buscar_parcial(self, texto):
        from modules.inventario import buscar_productos
        return buscar_productos(texto)

    def _llenar_tabla(self, productos):
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for p in productos:
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p.get("codigo") or "—",
                p["nombre"],
                formatear_pesos(p["precio_venta"]),
                f"{p.get('stock', 0):g}",
            ))

    def _seleccionar_fila(self):
        from modules.inventario import obtener_producto
        sel = self.tree.focus()
        if not sel:
            return
        p = obtener_producto(int(sel))
        if p:
            self._render_producto(p)
            self._reset_scan()
