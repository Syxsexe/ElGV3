"""
main.py — El G POS
Punto de entrada. Lanza el login y construye la interfaz principal.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from database import inicializar
import auth

# ── Paleta de colores ─────────────────────────────────────────────────────────
COLORS = {
    "bg":           "#0F1117",   # fondo principal
    "surface":      "#1A1D27",   # tarjetas y paneles
    "surface2":     "#22263A",   # hover, inputs
    "border":       "#2E3350",   # bordes sutiles
    "accent":       "#6C63FF",   # morado principal
    "accent_hover": "#8B84FF",   # morado hover
    "accent2":      "#FF6584",   # rosa/rojo acento
    "success":      "#43D9A2",   # verde éxito
    "warning":      "#FFB547",   # naranja advertencia
    "danger":       "#FF5757",   # rojo error
    "text":         "#E8E9F3",   # texto principal
    "text_muted":   "#7C8098",   # texto secundario
    "text_dim":     "#4A4E6A",   # texto muy tenue
}

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_SUB    = ("Segoe UI", 11)
FONT_LABEL  = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_SMALL  = ("Segoe UI", 9)
FONT_NAV    = ("Segoe UI", 10, "bold")
FONT_KPI    = ("Segoe UI", 26, "bold")


# ════════════════════════════════════════════════════════════
# VENTANA DE LOGIN
# ════════════════════════════════════════════════════════════

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("El G — POS")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self._center(400, 500)
        self._build()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        # Contenedor central
        frame = tk.Frame(self, bg=COLORS["surface"],
                         highlightbackground=COLORS["border"],
                         highlightthickness=1)
        frame.place(relx=0.5, rely=0.5, anchor="center", width=320, height=400)

        # Logo / nombre
        tk.Label(frame, text="El G", font=("Segoe UI", 36, "bold"),
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(pady=(40, 4))
        tk.Label(frame, text="Sistema de Punto de Venta",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack()

        # Separador
        sep = tk.Frame(frame, bg=COLORS["accent"], height=2, width=60)
        sep.pack(pady=20)

        # Campo usuario
        tk.Label(frame, text="Usuario", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"],
                 anchor="w").pack(padx=40, fill="x")
        self.entry_user = self._input(frame)
        self.entry_user.pack(padx=40, fill="x", pady=(4, 14))

        # Campo contraseña
        tk.Label(frame, text="Contraseña", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"],
                 anchor="w").pack(padx=40, fill="x")
        self.entry_pass = self._input(frame, show="●")
        self.entry_pass.pack(padx=40, fill="x", pady=(4, 24))

        # Botón ingresar
        self.btn_login = tk.Button(
            frame, text="Ingresar", font=FONT_BOLD,
            bg=COLORS["accent"], fg=COLORS["text"],
            activebackground=COLORS["accent_hover"],
            activeforeground=COLORS["text"],
            relief="flat", cursor="hand2",
            command=self._login
        )
        self.btn_login.pack(padx=40, fill="x", ipady=10)

        # Error label
        self.lbl_error = tk.Label(frame, text="", font=FONT_SMALL,
                                   bg=COLORS["surface"], fg=COLORS["danger"])
        self.lbl_error.pack(pady=(10, 0))

        # Bind Enter
        self.bind("<Return>", lambda e: self._login())
        self.entry_user.focus()

    def _input(self, parent, show=None):
        entry = tk.Entry(
            parent, font=FONT_LABEL, show=show,
            bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        return entry

    def _login(self):
        usuario   = self.entry_user.get().strip()
        contrasena = self.entry_pass.get()

        if not usuario or not contrasena:
            self.lbl_error.config(text="Completa todos los campos.")
            return

        sesion = auth.iniciar_sesion(usuario, contrasena)
        if not sesion:
            self.lbl_error.config(text="Usuario o contraseña incorrectos.")
            self.entry_pass.delete(0, "end")
            return

        self.destroy()
        app = MainWindow()
        app.mainloop()


# ════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ════════════════════════════════════════════════════════════

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        sesion = auth.get_sesion()
        self.title(f"El G POS — {sesion['usuario']} ({sesion['rol']})")
        self.configure(bg=COLORS["bg"])
        self.state("zoomed")   # maximizado al abrir
        self._frame_actual = None
        self._build()

    def _build(self):
        # ── Sidebar ──────────────────────────────────────────────────────────
        self.sidebar = tk.Frame(self, bg=COLORS["surface"], width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo sidebar
        tk.Label(self.sidebar, text="El G", font=("Segoe UI", 20, "bold"),
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(pady=(28, 2))
        tk.Label(self.sidebar, text="POS", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_dim"]).pack()

        sep = tk.Frame(self.sidebar, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=20, pady=16)

        # Ítem activo
        self._nav_activo = None
        self._nav_btns   = {}

        # Navegación según rol
        sesion = auth.get_sesion()
        nav_items = [
            ("🏠", "Inicio",       self._mostrar_inicio),
            ("🛒", "Nueva Venta",  self._mostrar_ventas),
            ("📦", "Inventario",   self._mostrar_inventario),
            ("💰", "Caja",         self._mostrar_caja),
        ]
        if sesion["rol"] == "admin":
            nav_items += [
                ("📊", "Reportes",     self._mostrar_reportes),
                ("👥", "Usuarios",     self._mostrar_usuarios),
            ]

        for icono, label, cmd in nav_items:
            self._nav_btn(icono, label, cmd)

        # Espaciador
        tk.Frame(self.sidebar, bg=COLORS["surface"]).pack(expand=True, fill="y")

        # Info usuario
        sep2 = tk.Frame(self.sidebar, bg=COLORS["border"], height=1)
        sep2.pack(fill="x", padx=20, pady=8)

        info_frame = tk.Frame(self.sidebar, bg=COLORS["surface"])
        info_frame.pack(padx=16, pady=(0, 8), fill="x")
        tk.Label(info_frame, text=sesion["usuario"],
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w")
        tk.Label(info_frame, text=sesion["rol"].capitalize(),
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["accent"]).pack(anchor="w")

        tk.Button(
            self.sidebar, text="Cerrar sesión",
            font=FONT_SMALL, bg=COLORS["surface"],
            fg=COLORS["text_muted"], relief="flat",
            cursor="hand2", command=self._cerrar_sesion,
            activebackground=COLORS["surface2"],
            activeforeground=COLORS["danger"],
        ).pack(padx=16, pady=(0, 20), anchor="w")

        # ── Área de contenido ─────────────────────────────────────────────────
        self.content = tk.Frame(self, bg=COLORS["bg"])
        self.content.pack(side="right", expand=True, fill="both")

        # Cargar inicio por defecto
        self._mostrar_inicio()

    def _nav_btn(self, icono, label, cmd):
        """Crea un botón de navegación en el sidebar."""
        btn = tk.Button(
            self.sidebar,
            text=f"  {icono}  {label}",
            font=FONT_NAV,
            bg=COLORS["surface"], fg=COLORS["text_muted"],
            relief="flat", anchor="w", cursor="hand2",
            activebackground=COLORS["surface2"],
            activeforeground=COLORS["text"],
            command=lambda c=cmd, l=label: self._nav_click(l, c),
        )
        btn.pack(fill="x", padx=8, pady=2, ipady=8)
        self._nav_btns[label] = btn

    def _nav_click(self, label, cmd):
        """Marca el botón activo y ejecuta la navegación."""
        # Resetear todos
        for lbl, btn in self._nav_btns.items():
            btn.config(bg=COLORS["surface"], fg=COLORS["text_muted"])

        # Marcar activo
        self._nav_btns[label].config(
            bg=COLORS["surface2"], fg=COLORS["accent"]
        )
        cmd()

    def _cambiar_frame(self, nuevo_frame_cls, **kwargs):
        """Destruye el frame actual y muestra el nuevo."""
        if self._frame_actual:
            self._frame_actual.destroy()
        self._frame_actual = nuevo_frame_cls(self.content, **kwargs)
        self._frame_actual.pack(expand=True, fill="both")

    # ── Navegación ────────────────────────────────────────────────────────────
    def _mostrar_inicio(self):
        self._nav_click("Inicio", lambda: None)
        self._cambiar_frame(FrameInicio)

    def _mostrar_ventas(self):
        self._nav_click("Nueva Venta", lambda: None)
        self._cambiar_frame(FrameVentas)

    def _mostrar_inventario(self):
        self._nav_click("Inventario", lambda: None)
        self._cambiar_frame(FrameInventario)

    def _mostrar_caja(self):
        self._nav_click("Caja", lambda: None)
        self._cambiar_frame(FrameCaja)

    def _mostrar_reportes(self):
        self._nav_click("Reportes", lambda: None)
        self._cambiar_frame(FrameReportes)

    def _mostrar_usuarios(self):
        self._nav_click("Usuarios", lambda: None)
        self._cambiar_frame(FrameUsuarios)

    def _cerrar_sesion(self):
        if messagebox.askyesno("Cerrar sesión", "¿Deseas cerrar la sesión actual?"):
            auth.cerrar_sesion()
            self.destroy()
            login = LoginWindow()
            login.mainloop()


# ════════════════════════════════════════════════════════════
# FRAME BASE (herencia para todos los frames)
# ════════════════════════════════════════════════════════════

class FrameBase(tk.Frame):
    def __init__(self, parent, titulo, subtitulo=""):
        super().__init__(parent, bg=COLORS["bg"])
        self._build_header(titulo, subtitulo)

    def _build_header(self, titulo, subtitulo):
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=32, pady=(28, 0))

        tk.Label(header, text=titulo, font=FONT_TITLE,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        if subtitulo:
            tk.Label(header, text=subtitulo, font=FONT_SUB,
                     bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(2, 0))

        sep = tk.Frame(self, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=32, pady=16)

    def _card(self, parent, **kwargs):
        """Crea un frame con estilo de tarjeta."""
        return tk.Frame(parent, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1, **kwargs)

    def _label_muted(self, parent, text, **kwargs):
        return tk.Label(parent, text=text, font=FONT_SMALL,
                        bg=COLORS["surface"], fg=COLORS["text_muted"], **kwargs)

    def _btn_primary(self, parent, text, cmd, **kwargs):
        return tk.Button(parent, text=text, font=FONT_BOLD,
                         bg=COLORS["accent"], fg=COLORS["text"],
                         activebackground=COLORS["accent_hover"],
                         activeforeground=COLORS["text"],
                         relief="flat", cursor="hand2",
                         command=cmd, **kwargs)

    def _btn_danger(self, parent, text, cmd, **kwargs):
        return tk.Button(parent, text=text, font=FONT_BOLD,
                         bg=COLORS["danger"], fg=COLORS["text"],
                         activebackground="#cc4444",
                         activeforeground=COLORS["text"],
                         relief="flat", cursor="hand2",
                         command=cmd, **kwargs)

    def _input(self, parent, **kwargs):
        return tk.Entry(parent, font=FONT_LABEL,
                        bg=COLORS["surface2"], fg=COLORS["text"],
                        insertbackground=COLORS["accent"],
                        relief="flat", bd=0,
                        highlightthickness=1,
                        highlightbackground=COLORS["border"],
                        highlightcolor=COLORS["accent"], **kwargs)

    def _tabla(self, parent, columnas, alto=10):
        """Crea un Treeview con estilo consistente."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("POS.Treeview",
                        background=COLORS["surface"],
                        foreground=COLORS["text"],
                        fieldbackground=COLORS["surface"],
                        rowheight=28,
                        font=FONT_LABEL,
                        borderwidth=0)
        style.configure("POS.Treeview.Heading",
                        background=COLORS["surface2"],
                        foreground=COLORS["text_muted"],
                        font=FONT_BOLD,
                        relief="flat")
        style.map("POS.Treeview",
                  background=[("selected", COLORS["accent"])],
                  foreground=[("selected", COLORS["text"])])

        tree = ttk.Treeview(parent, columns=columnas, show="headings",
                            height=alto, style="POS.Treeview")
        for col in columnas:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=120)

        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree


# ════════════════════════════════════════════════════════════
# FRAME INICIO — Dashboard con KPIs del día
# ════════════════════════════════════════════════════════════

class FrameInicio(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Inicio",
                         "Resumen del día — El G")
        self._build()

    def _build(self):
        from modules.ventas import resumen_del_dia
        from modules.inventario import productos_bajo_stock, insumos_bajo_stock
        from modules.caja import get_sesion_activa, formatear_pesos

        resumen = resumen_del_dia()
        sesion  = get_sesion_activa()

        # ── Fila de KPIs ─────────────────────────────────────────────────────
        kpi_row = tk.Frame(self, bg=COLORS["bg"])
        kpi_row.pack(fill="x", padx=32, pady=(0, 20))

        kpis = [
            ("Ventas hoy",     formatear_pesos(resumen["total"]),       COLORS["accent"]),
            ("Transacciones",  str(resumen["num_ventas"]),               COLORS["success"]),
            ("Tienda",         formatear_pesos(resumen["por_tipo"].get("tienda", 0)), COLORS["accent2"]),
            ("Cocina",         formatear_pesos(resumen["por_tipo"].get("cocina", 0)), COLORS["warning"]),
        ]

        for titulo, valor, color in kpis:
            card = tk.Frame(kpi_row, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            card.pack(side="left", expand=True, fill="both",
                      padx=(0, 12), ipady=16)
            tk.Label(card, text=valor, font=FONT_KPI,
                     bg=COLORS["surface"], fg=color).pack(pady=(16, 4))
            tk.Label(card, text=titulo, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 16))

        # ── Fila inferior ─────────────────────────────────────────────────────
        row2 = tk.Frame(self, bg=COLORS["bg"])
        row2.pack(fill="both", expand=True, padx=32, pady=(0, 28))

        # Estado de caja
        caja_card = self._card(row2)
        caja_card.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(caja_card, text="Estado de Caja", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 8))

        if sesion:
            tk.Label(caja_card, text="● Caja abierta", font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["success"]).pack(anchor="w", padx=20)
            tk.Label(caja_card, text=f"Cajero: {sesion['cajero']}",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=20, pady=2)
            tk.Label(caja_card, text=f"Desde: {sesion['apertura'][:16]}",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=20)
            tk.Label(caja_card,
                     text=f"Ventas acumuladas: {formatear_pesos(sesion['total_ventas'])}",
                     font=FONT_BOLD, bg=COLORS["surface"],
                     fg=COLORS["accent"]).pack(anchor="w", padx=20, pady=(8, 16))
        else:
            tk.Label(caja_card, text="● Caja cerrada", font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["danger"]).pack(anchor="w", padx=20, pady=(0, 16))

        # Alertas de stock
        alertas_card = self._card(row2)
        alertas_card.pack(side="left", fill="both", expand=True)
        tk.Label(alertas_card, text="Alertas de Stock", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 8))

        productos_bajos = productos_bajo_stock()
        insumos_bajos   = insumos_bajo_stock()
        alertas = [(p["nombre"], f"Stock: {p['stock']} / Mín: {p['stock_minimo']}")
                   for p in productos_bajos[:3]]
        alertas += [(i["nombre"], f"Stock: {i['stock']} {i['unidad']}")
                    for i in insumos_bajos[:3]]

        if alertas:
            for nombre, detalle in alertas:
                fila = tk.Frame(alertas_card, bg=COLORS["surface"])
                fila.pack(fill="x", padx=20, pady=3)
                tk.Label(fila, text="⚠", font=FONT_LABEL,
                         bg=COLORS["surface"], fg=COLORS["warning"]).pack(side="left")
                tk.Label(fila, text=f" {nombre}",
                         font=FONT_BOLD, bg=COLORS["surface"],
                         fg=COLORS["text"]).pack(side="left")
                tk.Label(fila, text=f"  {detalle}",
                         font=FONT_SMALL, bg=COLORS["surface"],
                         fg=COLORS["text_muted"]).pack(side="left")
        else:
            tk.Label(alertas_card, text="✓ Todo el stock en orden",
                     font=FONT_LABEL, bg=COLORS["surface"],
                     fg=COLORS["success"]).pack(anchor="w", padx=20, pady=(0, 16))


# ════════════════════════════════════════════════════════════
# FRAME VENTAS — Carrito de compra
# ════════════════════════════════════════════════════════════

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

        # Método de pago
        tk.Label(right, text="Método de pago", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self.combo_pago = ttk.Combobox(
            right, values=["efectivo", "transferencia", "tarjeta", "nequi", "daviplata"],
            font=FONT_LABEL, state="readonly"
        )
        self.combo_pago.set("efectivo")
        self.combo_pago.pack(fill="x", padx=16, pady=(4, 12))

        # Confirmar
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
        from modules.ventas import registrar_venta
        from modules.caja import formatear_pesos

        if self.carrito.esta_vacio():
            messagebox.showwarning("Carrito vacío", "Agrega productos antes de confirmar.")
            return

        metodo = self.combo_pago.get()
        total  = formatear_pesos(self.carrito.total())

        if not messagebox.askyesno("Confirmar venta",
                                    f"Total: {total}\nMétodo: {metodo}\n\n¿Confirmar venta?"):
            return
        try:
            venta_id = registrar_venta(self.carrito, metodo_pago=metodo,
                                        sesion_id=self.sesion_id)
            messagebox.showinfo("Venta registrada",
                                 f"✓ Venta #{venta_id} registrada por {total}")
            self._buscar()
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ════════════════════════════════════════════════════════════
# FRAME INVENTARIO — Listado y gestión básica
# ════════════════════════════════════════════════════════════

class FrameInventario(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Inventario", "Productos, insumos y stock")
        self._build()

    def _build(self):
        from modules.inventario import listar_productos, listar_insumos
        from modules.caja import formatear_pesos

        # IDs de columna sin tildes (Tkinter/Tcl los usa internamente)
        # y textos visibles separados
        self._cols_prods = {
            "nombre":       "Nombre",
            "categoria":    "Categoría",
            "precio_venta": "Precio Venta",
            "costo":        "Costo",
            "stock":        "Stock",
            "minimo":       "Mín",
            "margen":       "Margen %",
        }
        self._cols_insumos = {
            "nombre":    "Nombre",
            "stock":     "Stock",
            "unidad":    "Unidad",
            "stock_min": "Stock Mín",
        }

        # Tabs productos / insumos
        tab_frame = tk.Frame(self, bg=COLORS["bg"])
        tab_frame.pack(fill="x", padx=32, pady=(0, 12))
        self._tab = tk.StringVar(value="productos")
        for t, v in [("Productos", "productos"), ("Insumos de cocina", "insumos")]:
            tk.Radiobutton(
                tab_frame, text=t, variable=self._tab, value=v,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._cargar, padx=14, pady=6,
            ).pack(side="left", padx=(0, 4))

        # Tabla (se inicializa con columnas de productos)
        tabla_wrap = tk.Frame(self, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True, padx=32, pady=(0, 16))

        ids_prods = list(self._cols_prods.keys())
        self.tree = self._tabla(tabla_wrap, ids_prods, alto=18)
        # Ajustar anchos iniciales
        anchos = {"nombre": 200, "categoria": 140, "precio_venta": 110,
                  "costo": 110, "stock": 70, "minimo": 60, "margen": 80}
        for col_id, ancho in anchos.items():
            anchor = "w" if col_id in ("nombre", "categoria") else "center"
            self.tree.column(col_id, width=ancho, anchor=anchor)
            self.tree.heading(col_id, text=self._cols_prods[col_id])

        self._cargar()

    def _cargar(self):
        from modules.inventario import listar_productos, listar_insumos, calcular_margen
        from modules.caja import formatear_pesos

        self.tree.delete(*self.tree.get_children())
        tab = self._tab.get()

        if tab == "productos":
            ids = list(self._cols_prods.keys())
            self.tree["columns"] = ids
            anchos = {"nombre": 200, "categoria": 140, "precio_venta": 110,
                      "costo": 110, "stock": 70, "minimo": 60, "margen": 80}
            for col_id in ids:
                anchor = "w" if col_id in ("nombre", "categoria") else "center"
                self.tree.column(col_id, width=anchos.get(col_id, 100), anchor=anchor)
                self.tree.heading(col_id, text=self._cols_prods[col_id])

            for p in listar_productos():
                margen = calcular_margen(p["precio_venta"], p["precio_costo"])
                self.tree.insert("", "end", values=(
                    p["nombre"], p["categoria_nombre"],
                    formatear_pesos(p["precio_venta"]),
                    formatear_pesos(p["precio_costo"]),
                    p["stock"], p["stock_minimo"],
                    f"{margen}%"
                ))
        else:
            ids = list(self._cols_insumos.keys())
            self.tree["columns"] = ids
            anchos = {"nombre": 250, "stock": 100, "unidad": 120, "stock_min": 100}
            for col_id in ids:
                anchor = "w" if col_id == "nombre" else "center"
                self.tree.column(col_id, width=anchos.get(col_id, 120), anchor=anchor)
                self.tree.heading(col_id, text=self._cols_insumos[col_id])

            for i in listar_insumos():
                self.tree.insert("", "end", values=(
                    i["nombre"], i["stock"], i["unidad"], i["stock_minimo"]
                ))


# ════════════════════════════════════════════════════════════
# FRAME CAJA — Apertura y cierre
# ════════════════════════════════════════════════════════════

class FrameCaja(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Caja", "Apertura y cierre de turno")
        self._build()

    def _build(self):
        from modules.caja import get_sesion_activa, formatear_pesos, DENOMINACIONES_COP

        sesion = get_sesion_activa()
        main   = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        if not sesion:
            self._panel_apertura(main)
        else:
            self._panel_cierre(main, sesion)

    def _panel_apertura(self, parent):
        card = self._card(parent, width=360)
        card.pack(anchor="center", pady=40, ipadx=20, ipady=20)

        tk.Label(card, text="Abrir Caja", font=FONT_TITLE,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(20, 4))
        tk.Label(card, text="Ingresa el monto base en efectivo",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(pady=(0, 20))

        tk.Label(card, text="Monto base ($)", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=30)
        self.entry_base = self._input(card)
        self.entry_base.pack(padx=30, fill="x", pady=(4, 20), ipady=6)

        self._btn_primary(card, "Abrir caja", self._abrir).pack(
            padx=30, fill="x", ipady=10, pady=(0, 20))

    def _abrir(self):
        from modules.caja import abrir_caja
        try:
            monto = float(self.entry_base.get().replace(".", "").replace(",", "."))
            abrir_caja(monto)
            messagebox.showinfo("Caja abierta", "✓ Caja abierta correctamente.")
            self.destroy()
            FrameCaja(self.master).pack(expand=True, fill="both")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _panel_cierre(self, parent, sesion):
        from modules.caja import DENOMINACIONES_COP, formatear_pesos, calcular_desde_denominaciones

        tk.Label(parent, text=f"Caja abierta por: {sesion['cajero']}  ·  Desde: {sesion['apertura'][:16]}",
                 font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 16))

        cols = tk.Frame(parent, bg=COLORS["bg"])
        cols.pack(fill="both", expand=True)

        # Denominaciones
        denom_card = self._card(cols)
        denom_card.pack(side="left", fill="y", padx=(0, 12), ipadx=10, ipady=10)

        tk.Label(denom_card, text="Conteo de denominaciones",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 8))

        self._denom_entries = {}
        self._lbl_contado   = None

        for denom in reversed(DENOMINACIONES_COP):
            fila = tk.Frame(denom_card, bg=COLORS["surface"])
            fila.pack(fill="x", padx=16, pady=2)
            tk.Label(fila, text=formatear_pesos(denom), font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["text"],
                     width=12, anchor="w").pack(side="left")
            entry = self._input(fila, width=6)
            entry.insert(0, "0")
            entry.pack(side="left", padx=8, ipady=4)
            entry.bind("<KeyRelease>", lambda e: self._actualizar_contado())

            subtotal_lbl = tk.Label(fila, text="$0", font=FONT_SMALL,
                                     bg=COLORS["surface"], fg=COLORS["text_muted"],
                                     width=12, anchor="e")
            subtotal_lbl.pack(side="left")
            self._denom_entries[denom] = (entry, subtotal_lbl)

        # Resumen
        resumen_card = self._card(cols)
        resumen_card.pack(side="left", fill="both", expand=True, ipady=10)

        tk.Label(resumen_card, text="Resumen del turno",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 12))

        from modules.caja import formatear_pesos
        datos = [
            ("Monto base:",        formatear_pesos(sesion["monto_base"])),
            ("Ventas del turno:",  formatear_pesos(sesion["total_ventas"])),
            ("Total esperado:",    formatear_pesos(sesion["monto_base"] + sesion["total_ventas"])),
        ]
        for label, valor in datos:
            fila = tk.Frame(resumen_card, bg=COLORS["surface"])
            fila.pack(fill="x", padx=20, pady=4)
            tk.Label(fila, text=label, font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
            tk.Label(fila, text=valor, font=FONT_BOLD,
                     bg=COLORS["surface"], fg=COLORS["text"]).pack(side="right")

        sep = tk.Frame(resumen_card, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=20, pady=12)

        fila_contado = tk.Frame(resumen_card, bg=COLORS["surface"])
        fila_contado.pack(fill="x", padx=20)
        tk.Label(fila_contado, text="Monto contado:", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(side="left")
        self.lbl_contado = tk.Label(fila_contado, text="$0", font=FONT_KPI,
                                     bg=COLORS["surface"], fg=COLORS["accent"])
        self.lbl_contado.pack(side="right")

        self.lbl_diferencia = tk.Label(resumen_card, text="",
                                        font=FONT_BOLD, bg=COLORS["surface"])
        self.lbl_diferencia.pack(anchor="e", padx=20, pady=4)

        # Notas
        tk.Label(resumen_card, text="Notas (opcional)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=20, pady=(12, 4))
        self.txt_notas = tk.Text(resumen_card, height=3, font=FONT_SMALL,
                                  bg=COLORS["surface2"], fg=COLORS["text"],
                                  insertbackground=COLORS["accent"],
                                  relief="flat",
                                  highlightthickness=1,
                                  highlightbackground=COLORS["border"])
        self.txt_notas.pack(fill="x", padx=20)

        self._btn_danger(resumen_card, "Cerrar caja",
                         self._cerrar).pack(fill="x", padx=20, pady=20, ipady=10)

    def _actualizar_contado(self):
        from modules.caja import formatear_pesos, calcular_desde_denominaciones, DENOMINACIONES_COP
        denominaciones = {}
        for denom, (entry, lbl_sub) in self._denom_entries.items():
            try:
                cant = int(entry.get() or 0)
            except ValueError:
                cant = 0
            denominaciones[denom] = cant
            lbl_sub.config(text=formatear_pesos(denom * cant))

        total = calcular_desde_denominaciones(denominaciones)
        self.lbl_contado.config(text=formatear_pesos(total))

    def _cerrar(self):
        from modules.caja import cerrar_caja, get_sesion_activa, formatear_pesos
        denominaciones = {}
        for denom, (entry, _) in self._denom_entries.items():
            try:
                denominaciones[denom] = int(entry.get() or 0)
            except ValueError:
                denominaciones[denom] = 0

        notas = self.txt_notas.get("1.0", "end").strip()
        try:
            resumen = cerrar_caja(denominaciones, notas or None)
            dif     = resumen["diferencia"]
            color   = COLORS["success"] if dif >= 0 else COLORS["danger"]
            msg     = (
                f"Caja cerrada correctamente.\n\n"
                f"Esperado:  {formatear_pesos(resumen['monto_esperado'])}\n"
                f"Contado:   {formatear_pesos(resumen['monto_contado'])}\n"
                f"Diferencia: {formatear_pesos(dif)}"
            )
            messagebox.showinfo("Cierre de caja", msg)
            self.destroy()
            FrameCaja(self.master).pack(expand=True, fill="both")
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ════════════════════════════════════════════════════════════
# FRAME REPORTES — KPIs y tablas (solo admin)
# ════════════════════════════════════════════════════════════

class FrameReportes(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Reportes", "KPIs y análisis de ventas")
        self._build()

    def _build(self):
        from datetime import date, timedelta
        from modules.caja import formatear_pesos

        filtros = tk.Frame(self, bg=COLORS["bg"])
        filtros.pack(fill="x", padx=32, pady=(0, 16))

        tk.Label(filtros, text="Desde:", font=FONT_LABEL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_ini = self._input(filtros, width=12)
        hoy = date.today()
        self.entry_ini.insert(0, (hoy - timedelta(days=7)).isoformat())
        self.entry_ini.pack(side="left", padx=(4, 16), ipady=4)

        tk.Label(filtros, text="Hasta:", font=FONT_LABEL,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.entry_fin = self._input(filtros, width=12)
        self.entry_fin.insert(0, hoy.isoformat())
        self.entry_fin.pack(side="left", padx=(4, 16), ipady=4)

        self._btn_primary(filtros, "Consultar", self._consultar).pack(
            side="left", padx=(0, 8), ipady=4)
        tk.Button(filtros, text="Exportar CSV", font=FONT_BOLD,
                  bg=COLORS["surface"], fg=COLORS["text"],
                  activebackground=COLORS["surface2"],
                  relief="flat", cursor="hand2",
                  command=self._exportar).pack(side="left", ipady=4, padx=4)

        # KPIs rápidos
        self.kpi_frame = tk.Frame(self, bg=COLORS["bg"])
        self.kpi_frame.pack(fill="x", padx=32, pady=(0, 16))

        # Tabla productos más vendidos
        tk.Label(self, text="Productos más vendidos", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", padx=32)
        tabla_wrap = tk.Frame(self, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True, padx=32, pady=(8, 24))
        cols = ("Producto", "Categoría", "Tipo", "Unidades", "Ingresos")
        self.tree = self._tabla(tabla_wrap, cols, alto=12)
        self.tree.column("Producto",   width=200, anchor="w")
        self.tree.column("Categoría",  width=140, anchor="w")
        self.tree.column("Tipo",       width=80)
        self.tree.column("Unidades",   width=80)
        self.tree.column("Ingresos",   width=120)

        self._consultar()

    def _consultar(self):
        from modules.reportes import kpis_generales, productos_mas_vendidos
        from modules.caja import formatear_pesos

        ini = self.entry_ini.get().strip()
        fin = self.entry_fin.get().strip()

        # KPIs
        for w in self.kpi_frame.winfo_children():
            w.destroy()
        try:
            kpis = kpis_generales(ini, fin)
            datos_kpi = [
                ("Ingresos",        formatear_pesos(kpis["ingresos"]["actual"]),      COLORS["accent"]),
                ("Ventas",          str(kpis["num_ventas"]["actual"]),                COLORS["success"]),
                ("Ticket Prom.",    formatear_pesos(kpis["ticket_promedio"]["actual"]), COLORS["accent2"]),
                ("Tienda",          formatear_pesos(kpis["por_linea"]["tienda"]),     COLORS["text"]),
                ("Cocina",          formatear_pesos(kpis["por_linea"]["cocina"]),     COLORS["warning"]),
            ]
            for titulo, valor, color in datos_kpi:
                card = tk.Frame(self.kpi_frame, bg=COLORS["surface"],
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
                card.pack(side="left", expand=True, fill="both",
                          padx=(0, 8), ipady=8)
                tk.Label(card, text=valor, font=("Segoe UI", 18, "bold"),
                         bg=COLORS["surface"], fg=color).pack(pady=(10, 2))
                tk.Label(card, text=titulo, font=FONT_SMALL,
                         bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 10))
        except Exception:
            pass

        # Tabla
        self.tree.delete(*self.tree.get_children())
        try:
            for p in productos_mas_vendidos(ini, fin):
                self.tree.insert("", "end", values=(
                    p["nombre"], p["categoria"],
                    p["tipo_negocio"],
                    p["unidades_vendidas"],
                    formatear_pesos(p["ingresos_totales"])
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _exportar(self):
        from tkinter.filedialog import asksaveasfilename
        from modules.reportes import exportar_ventas_csv
        ini = self.entry_ini.get().strip()
        fin = self.entry_fin.get().strip()
        ruta = asksaveasfilename(defaultextension=".csv",
                                  filetypes=[("CSV", "*.csv")],
                                  initialfile=f"ventas_{ini}_{fin}.csv")
        if ruta:
            exportar_ventas_csv(ini, fin, ruta)
            messagebox.showinfo("Exportado", f"✓ Archivo guardado en:\n{ruta}")


# ════════════════════════════════════════════════════════════
# FRAME USUARIOS (solo admin)
# ════════════════════════════════════════════════════════════

class FrameUsuarios(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Usuarios", "Gestión de accesos al sistema")
        self._build()

    def _build(self):
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # Tabla
        tabla_wrap = tk.Frame(main, bg=COLORS["bg"])
        tabla_wrap.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self.tree = self._tabla(tabla_wrap,
                                ("ID", "Usuario", "Rol", "Activo", "Creado"),
                                alto=16)
        self.tree.column("ID",      width=40)
        self.tree.column("Usuario", width=160, anchor="w")
        self.tree.column("Rol",     width=90)
        self.tree.column("Activo",  width=70)
        self.tree.column("Creado",  width=150)
        self._cargar_usuarios()

        # Panel lateral
        panel = self._card(main, width=260)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)

        tk.Label(panel, text="Nuevo usuario", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 12))

        for lbl, attr in [("Usuario", "entry_nuevo_user"), ("Contraseña", "entry_nuevo_pass")]:
            tk.Label(panel, text=lbl, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
            e = self._input(panel, show="●" if lbl == "Contraseña" else None)
            e.pack(fill="x", padx=16, pady=(2, 10), ipady=5)
            setattr(self, attr, e)

        tk.Label(panel, text="Rol", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
        self.combo_rol = ttk.Combobox(panel, values=["admin", "vendedor"],
                                       font=FONT_LABEL, state="readonly")
        self.combo_rol.set("vendedor")
        self.combo_rol.pack(fill="x", padx=16, pady=(2, 16))

        self._btn_primary(panel, "Crear usuario", self._crear).pack(
            fill="x", padx=16, ipady=8)

        sep = tk.Frame(panel, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=16, pady=16)

        self._btn_danger(panel, "Desactivar seleccionado",
                         self._desactivar).pack(fill="x", padx=16, ipady=8)

    def _cargar_usuarios(self):
        from auth import listar_usuarios
        self.tree.delete(*self.tree.get_children())
        for u in listar_usuarios():
            self.tree.insert("", "end", iid=str(u["id"]), values=(
                u["id"], u["usuario"], u["rol"],
                "Sí" if u["activo"] else "No",
                u["creado_en"][:10]
            ))

    def _crear(self):
        from auth import crear_usuario
        usuario    = self.entry_nuevo_user.get().strip()
        contrasena = self.entry_nuevo_pass.get()
        rol        = self.combo_rol.get()

        if not usuario or not contrasena:
            messagebox.showwarning("Campos vacíos", "Completa usuario y contraseña.")
            return
        ok = crear_usuario(usuario, contrasena, rol)
        if ok:
            messagebox.showinfo("Creado", f"✓ Usuario '{usuario}' creado.")
            self.entry_nuevo_user.delete(0, "end")
            self.entry_nuevo_pass.delete(0, "end")
            self._cargar_usuarios()
        else:
            messagebox.showerror("Error", "El nombre de usuario ya existe.")

    def _desactivar(self):
        from auth import desactivar_usuario
        sel = self.tree.focus()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona un usuario.")
            return
        usuario_id = int(sel)
        if not messagebox.askyesno("Confirmar", "¿Desactivar este usuario?"):
            return
        desactivar_usuario(usuario_id)
        self._cargar_usuarios()


# ════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    inicializar()
    app = LoginWindow()
    app.mainloop()