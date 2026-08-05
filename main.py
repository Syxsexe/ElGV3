"""
main.py — El G POS
Punto de entrada. Lanza el login y construye la interfaz principal.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from database import inicializar
import auth

from ui.base import (
    COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL,
    FONT_NAV, FONT_KPI, _add_hover, aplicar_tema, tema_actual,
)
from ui import (
    FrameInicio, FrameVentas, FrameInventario,
    FrameCaja, FrameReportes, FrameUsuarios, FrameCuentas,
    FrameClientes, FrameProveedores, FrameFiscal, FrameGastos,
    FrameAuditoria, FrameCreditos, FrameDocumentos,
    FrameConsultaPrecios, FrameLibros, FrameTorneos,
    FramePreparaciones,
)


# ════════════════════════════════════════════════════════════
# VENTANA DE LOGIN
# ════════════════════════════════════════════════════════════

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("El G — POS")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self._center(420, 540)
        from modules.validaciones import registrar_validaciones
        registrar_validaciones(self)
        self._build()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        outer = tk.Frame(self, bg=COLORS["bg"])
        outer.place(relx=0.5, rely=0.5, anchor="center")

        frame = tk.Frame(outer, bg=COLORS["surface"],
                         highlightbackground=COLORS["border"],
                         highlightthickness=1)
        frame.pack(ipadx=0, ipady=0)

        # Barra de acento superior
        tk.Frame(frame, bg=COLORS["accent"], height=3).pack(fill="x")

        inner = tk.Frame(frame, bg=COLORS["surface"])
        inner.pack(padx=44, pady=(32, 40))

        # Branding
        tk.Label(inner, text="El G", font=("Segoe UI", 42, "bold"),
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack()
        tk.Label(inner, text="TCG · Juegos · Comidas",
                 font=("Segoe UI", 10), bg=COLORS["surface"],
                 fg=COLORS["text_dim"]).pack(pady=(0, 4))

        # Separador decorativo
        sep_frame = tk.Frame(inner, bg=COLORS["surface"])
        sep_frame.pack(pady=(8, 28))
        tk.Frame(sep_frame, bg=COLORS["accent"], height=2, width=40).pack(side="left")
        tk.Frame(sep_frame, bg=COLORS["border"], height=2, width=60).pack(side="left")

        # Usuario
        tk.Label(inner, text="Usuario", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text_muted"],
                 anchor="w").pack(fill="x")
        self.entry_user = self._input(inner)
        self.entry_user.pack(fill="x", pady=(6, 18), ipady=9)

        # Contraseña + toggle
        tk.Label(inner, text="Contraseña", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text_muted"],
                 anchor="w").pack(fill="x")

        pass_wrap = tk.Frame(inner, bg=COLORS["surface2"],
                             highlightthickness=1,
                             highlightbackground=COLORS["border"])
        pass_wrap.pack(fill="x", pady=(6, 24))

        self.entry_pass = tk.Entry(
            pass_wrap, font=FONT_LABEL, show="●",
            bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat", bd=0, highlightthickness=0,
        )
        self.entry_pass.pack(side="left", fill="x", expand=True, padx=(10, 0), ipady=9)

        self._pass_visible = False
        self._btn_toggle = tk.Button(
            pass_wrap, text="Mostrar",
            font=("Segoe UI", 8), bg=COLORS["surface2"],
            fg=COLORS["text_dim"], relief="flat", cursor="hand2",
            bd=0, highlightthickness=0,
            command=self._toggle_pass,
            activebackground=COLORS["surface2"],
            activeforeground=COLORS["text_muted"],
        )
        self._btn_toggle.pack(side="right", padx=8)

        # Botón Ingresar
        btn_login = tk.Button(
            inner, text="Ingresar", font=("Segoe UI", 11, "bold"),
            bg=COLORS["accent"], fg=COLORS["on_accent"],
            activebackground=COLORS["accent_hover"],
            activeforeground=COLORS["text"],
            relief="flat", cursor="hand2",
            command=self._login,
        )
        btn_login.pack(fill="x", ipady=12)
        _add_hover(btn_login, COLORS["accent"], COLORS["accent_hover"])

        self.lbl_error = tk.Label(inner, text="", font=FONT_SMALL,
                                   bg=COLORS["surface"], fg=COLORS["danger"])
        self.lbl_error.pack(pady=(12, 0))

        self.bind("<Return>", lambda e: self._login())
        self.entry_user.focus()

    def _input(self, parent, **kwargs):
        return tk.Entry(
            parent, font=FONT_LABEL, **kwargs,
            bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )

    def _toggle_pass(self):
        self._pass_visible = not self._pass_visible
        self.entry_pass.config(show="" if self._pass_visible else "●")
        self._btn_toggle.config(text="Ocultar" if self._pass_visible else "Mostrar")

    def _login(self):
        usuario    = self.entry_user.get().strip()
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
        # Re-registrar validaciones en el nuevo intérprete Tcl
        from modules.validaciones import registrar_validaciones
        registrar_validaciones(self)
        sesion = auth.get_sesion()
        self.title(f"El G POS — {sesion['usuario']} ({sesion['rol']})")
        self.configure(bg=COLORS["bg"])
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except Exception:
                pass
        self._frame_actual = None
        self._nav_activo   = None
        self._nav_btns     = {}
        self._build()

    def _build(self):
        # ── Sidebar ───────────────────────────────────────────────────────────
        # Estructura en 3 zonas para que el menú funcione en cualquier resolución:
        #   • arriba : branding (fijo)
        #   • abajo  : pie con usuario, tema y cerrar sesión (fijo, nunca se pierde)
        #   • medio  : lista de navegación con scroll propio si no cabe entera
        self.sidebar = tk.Frame(self, bg=COLORS["surface"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Branding (arriba, fijo)
        brand = tk.Frame(self.sidebar, bg=COLORS["surface"])
        brand.pack(side="top", fill="x", pady=(22, 0))
        tk.Label(brand, text="El G", font=("Segoe UI", 22, "bold"),
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w", padx=24)
        tk.Label(brand, text="Punto de Venta",
                 font=("Segoe UI", 8), bg=COLORS["surface"],
                 fg=COLORS["text_dim"]).pack(anchor="w", padx=24, pady=(0, 4))

        tk.Frame(self.sidebar, bg=COLORS["border"], height=1).pack(
            side="top", fill="x", padx=20, pady=(12, 8))

        # ── Pie de sidebar (abajo, FIJO — se empaqueta antes que el medio para que
        #     quede anclado y nunca se salga de pantalla) ──────────────────────
        sesion = auth.get_sesion()

        btn_salir = tk.Button(
            self.sidebar, text="Cerrar sesión", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_dim"],
            relief="flat", cursor="hand2", command=self._cerrar_sesion,
            activebackground=COLORS["surface2"],
            activeforeground=COLORS["danger"],
        )
        btn_salir.pack(side="bottom", padx=20, pady=(4, 16), anchor="w")
        btn_salir.bind("<Enter>", lambda e: btn_salir.config(fg=COLORS["danger"]))
        btn_salir.bind("<Leave>", lambda e: btn_salir.config(fg=COLORS["text_dim"]))

        es_oscuro = tema_actual() == "oscuro"
        btn_tema = tk.Button(
            self.sidebar,
            text="☀  Tema claro" if es_oscuro else "🌙  Tema oscuro",
            font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text_muted"],
            relief="flat", cursor="hand2", command=self._cambiar_tema,
            activebackground=COLORS["surface2"], activeforeground=COLORS["accent"],
        )
        btn_tema.pack(side="bottom", padx=20, pady=(6, 0), anchor="w")
        btn_tema.bind("<Enter>", lambda e: btn_tema.config(fg=COLORS["accent"]))
        btn_tema.bind("<Leave>", lambda e: btn_tema.config(fg=COLORS["text_muted"]))

        pie = tk.Frame(self.sidebar, bg=COLORS["surface"])
        pie.pack(side="bottom", padx=20, pady=(0, 6), fill="x")
        tk.Label(pie, text=sesion["usuario"], font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w")
        tk.Label(pie, text=sesion["rol"].capitalize(), font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w")

        tk.Frame(self.sidebar, bg=COLORS["border"], height=1).pack(
            side="bottom", fill="x", padx=20, pady=(8, 10))

        # ── Navegación (medio, con scroll propio) ──────────────────────────────
        nav_wrap = tk.Frame(self.sidebar, bg=COLORS["surface"])
        nav_wrap.pack(side="top", fill="both", expand=True)

        self._nav_canvas = tk.Canvas(nav_wrap, bg=COLORS["surface"],
                                     highlightthickness=0, bd=0)
        self._nav_sb = ttk.Scrollbar(nav_wrap, orient="vertical",
                                     command=self._nav_canvas.yview)
        self._nav_canvas.configure(yscrollcommand=self._nav_sb.set)
        self._nav_canvas.pack(side="left", fill="both", expand=True)

        self._nav_inner = tk.Frame(self._nav_canvas, bg=COLORS["surface"])
        self._nav_win = self._nav_canvas.create_window(
            (0, 0), window=self._nav_inner, anchor="nw")
        self._nav_canvas.bind(
            "<Configure>",
            lambda e: self._nav_canvas.itemconfig(self._nav_win, width=e.width))
        self._nav_inner.bind("<Configure>", self._on_nav_resize)
        # La rueda controla el menú mientras el puntero está sobre el sidebar y
        # el contenido cuando entra al área de contenido. Se cambia solo al ENTRAR
        # a cada zona (nunca al salir) para no oscilar al pasar sobre los botones.
        self.sidebar.bind("<Enter>", self._activar_scroll_nav)

        nav_items = [
            ("Inicio",           self._mostrar_inicio),
            ("Nueva Venta",      self._mostrar_ventas),
            ("Consulta Precios", self._mostrar_consulta_precios),
            ("Clientes",         self._mostrar_clientes),
            ("Cuentas",          self._mostrar_cuentas),
            ("Inventario",       self._mostrar_inventario),
            ("Preparaciones",    self._mostrar_preparaciones),
            ("Proveedores",      self._mostrar_proveedores),
            ("Caja",             self._mostrar_caja),
            ("Créditos",         self._mostrar_creditos),
            ("Gastos",           self._mostrar_gastos),
            ("Torneos",          self._mostrar_torneos),
            ("Documentos",       self._mostrar_documentos),
            ("Doc. Fiscales",    self._mostrar_fiscal),
            ("Reportes",         self._mostrar_reportes),
            ("Libros",           self._mostrar_libros),
        ]
        if sesion["rol"] == "admin":
            nav_items += [
                ("Usuarios",   self._mostrar_usuarios),
                ("Auditoría",  self._mostrar_auditoria),
            ]
        for label, cmd in nav_items:
            self._nav_btn(label, cmd)

        # ── Área de contenido (scroll vertical y horizontal) ───────────────────
        self._content_outer = tk.Frame(self, bg=COLORS["bg"])
        self._content_outer.pack(side="right", expand=True, fill="both")

        self._canvas = tk.Canvas(self._content_outer, bg=COLORS["bg"],
                                  highlightthickness=0, bd=0)
        self._scrollbar = ttk.Scrollbar(self._content_outer, orient="vertical",
                                         command=self._canvas.yview)
        self._scrollbar_x = ttk.Scrollbar(self._content_outer, orient="horizontal",
                                           command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set,
                               xscrollcommand=self._scrollbar_x.set)
        self._scrollbar.pack(side="right", fill="y")
        self._scrollbar_x.pack(side="bottom", fill="x")
        self._canvas.pack(side="left", expand=True, fill="both")

        self.content = tk.Frame(self._canvas, bg=COLORS["bg"])
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self.content, anchor="nw")

        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self.content.bind("<Configure>",  self._on_content_resize)
        self._canvas.bind("<Enter>", self._activar_scroll_contenido)
        self._activar_scroll_contenido()

        self._mostrar_inicio()

    # ── Scroll del contenido ────────────────────────────────────────────────

    def _on_canvas_resize(self, event):
        # El contenido nunca es más angosto que el canvas (así llena el ancho),
        # pero si necesita más (tarjetas/tablas anchas) crece y aparece el scroll
        # horizontal en vez de recortarse.
        ancho = max(event.width, self.content.winfo_reqwidth())
        self._canvas.itemconfig(self._canvas_window, width=ancho)

    def _on_content_resize(self, event):
        ancho = max(self._canvas.winfo_width(), self.content.winfo_reqwidth())
        self._canvas.itemconfig(self._canvas_window, width=ancho)
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        if self.content.winfo_reqheight() > self._canvas.winfo_height():
            self._scrollbar.pack(side="right", fill="y")
        else:
            self._scrollbar.pack_forget()
        if self.content.winfo_reqwidth() > self._canvas.winfo_width():
            self._scrollbar_x.pack(side="bottom", fill="x")
        else:
            self._scrollbar_x.pack_forget()

    def _on_mousewheel(self, event):
        if self.content.winfo_reqheight() <= self._canvas.winfo_height():
            return
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _resetear_scroll(self):
        self._canvas.yview_moveto(0)
        self._canvas.xview_moveto(0)

    # ── Scroll del menú lateral ─────────────────────────────────────────────

    def _on_nav_resize(self, event):
        self._nav_canvas.configure(scrollregion=self._nav_canvas.bbox("all"))
        if self._nav_inner.winfo_reqheight() > self._nav_canvas.winfo_height():
            self._nav_sb.pack(side="right", fill="y")
        else:
            self._nav_sb.pack_forget()

    def _nav_mousewheel(self, event):
        if self._nav_inner.winfo_reqheight() <= self._nav_canvas.winfo_height():
            return
        if event.num == 4:
            self._nav_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._nav_canvas.yview_scroll(1, "units")
        else:
            self._nav_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _activar_scroll_nav(self, event=None):
        self._canvas.bind_all("<MouseWheel>", self._nav_mousewheel)
        self._canvas.bind_all("<Button-4>",   self._nav_mousewheel)
        self._canvas.bind_all("<Button-5>",   self._nav_mousewheel)

    def _activar_scroll_contenido(self, event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>",   self._on_mousewheel)
        self._canvas.bind_all("<Button-5>",   self._on_mousewheel)

    # ── Navegación ────────────────────────────────────────────────────────────

    def _nav_btn(self, label, cmd):
        wrap = tk.Frame(self._nav_inner, bg=COLORS["surface"], cursor="hand2")
        wrap.pack(fill="x", pady=1)

        # Indicador izquierdo (3px, visible solo en activo)
        bar = tk.Frame(wrap, width=3, bg=COLORS["surface"])
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)

        lbl = tk.Label(
            wrap, text=f"   {label}",
            font=FONT_NAV, bg=COLORS["surface"], fg=COLORS["text_muted"],
            anchor="w", cursor="hand2",
        )
        lbl.pack(side="left", fill="x", expand=True, ipady=9)

        def _activate():
            wrap.config(bg=COLORS["surface2"])
            lbl.config(bg=COLORS["surface2"], fg=COLORS["accent"])
            bar.config(bg=COLORS["accent"])

        def _deactivate():
            wrap.config(bg=COLORS["surface"])
            lbl.config(bg=COLORS["surface"], fg=COLORS["text_muted"])
            bar.config(bg=COLORS["surface"])

        def _on_enter(e):
            if self._nav_activo != label:
                wrap.config(bg=COLORS["surface2"])
                lbl.config(bg=COLORS["surface2"], fg=COLORS["text"])
                bar.config(bg=COLORS["surface2"])

        def _on_leave(e):
            if self._nav_activo != label:
                _deactivate()

        for w in (wrap, lbl, bar):
            w.bind("<Button-1>", lambda e, c=cmd: c())
            w.bind("<Enter>", _on_enter)
            w.bind("<Leave>", _on_leave)

        self._nav_btns[label] = {
            "activate":   _activate,
            "deactivate": _deactivate,
            "cmd":        cmd,
        }

    def _nav_click(self, label):
        if self._nav_activo and self._nav_activo in self._nav_btns:
            self._nav_btns[self._nav_activo]["deactivate"]()
        self._nav_activo = label
        self._nav_btns[label]["activate"]()

    def _cambiar_frame(self, nuevo_frame_cls, **kwargs):
        if self._frame_actual:
            self._frame_actual.destroy()
        self._frame_actual = nuevo_frame_cls(self.content, **kwargs)
        self._frame_actual.pack(expand=True, fill="both")
        self._resetear_scroll()

    # ── Pantallas ─────────────────────────────────────────────────────────────

    def _mostrar_inicio(self):
        self._nav_click("Inicio")
        self._cambiar_frame(FrameInicio)

    def _mostrar_ventas(self):
        self._nav_click("Nueva Venta")
        self._cambiar_frame(FrameVentas)

    def _mostrar_cuentas(self):
        self._nav_click("Cuentas")
        self._cambiar_frame(FrameCuentas)

    def _mostrar_clientes(self):
        self._nav_click("Clientes")
        self._cambiar_frame(FrameClientes)

    def _mostrar_inventario(self):
        self._nav_click("Inventario")
        self._cambiar_frame(FrameInventario)

    def _mostrar_preparaciones(self):
        self._nav_click("Preparaciones")
        self._cambiar_frame(FramePreparaciones)

    def _mostrar_proveedores(self):
        self._nav_click("Proveedores")
        self._cambiar_frame(FrameProveedores)

    def _mostrar_caja(self):
        self._nav_click("Caja")
        self._cambiar_frame(FrameCaja)

    def _mostrar_gastos(self):
        self._nav_click("Gastos")
        self._cambiar_frame(FrameGastos)

    def _mostrar_torneos(self):
        self._nav_click("Torneos")
        self._cambiar_frame(FrameTorneos)

    def _mostrar_consulta_precios(self):
        self._nav_click("Consulta Precios")
        self._cambiar_frame(FrameConsultaPrecios)

    def _mostrar_documentos(self):
        self._nav_click("Documentos")
        self._cambiar_frame(FrameDocumentos)

    def _mostrar_fiscal(self):
        self._nav_click("Doc. Fiscales")
        self._cambiar_frame(FrameFiscal)

    def _mostrar_creditos(self):
        self._nav_click("Créditos")
        self._cambiar_frame(FrameCreditos)

    def _mostrar_auditoria(self):
        self._nav_click("Auditoría")
        self._cambiar_frame(FrameAuditoria)

    def _mostrar_reportes(self):
        self._nav_click("Reportes")
        self._cambiar_frame(FrameReportes)

    def _mostrar_libros(self):
        self._nav_click("Libros")
        self._cambiar_frame(FrameLibros)

    def _mostrar_usuarios(self):
        self._nav_click("Usuarios")
        self._cambiar_frame(FrameUsuarios)

    def _cambiar_tema(self):
        """Alterna entre tema oscuro/claro y reconstruye la ventana en caliente."""
        aplicar_tema("claro" if tema_actual() == "oscuro" else "oscuro")
        vista = self._nav_activo
        for w in self.winfo_children():
            w.destroy()
        self.configure(bg=COLORS["bg"])
        self._frame_actual = None
        self._nav_activo   = None
        self._nav_btns     = {}
        self._build()
        # _build() ya muestra "Inicio"; solo restauramos si estaba en otra vista
        # (evita reconstruir el dashboard dos veces).
        if vista and vista != "Inicio" and vista in self._nav_btns:
            self._nav_btns[vista]["cmd"]()

    def _cerrar_sesion(self):
        if messagebox.askyesno("Cerrar sesión", "¿Deseas cerrar la sesión actual?"):
            auth.cerrar_sesion()
            self.destroy()
            login = LoginWindow()
            login.mainloop()


# ════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    # Modo respaldo (headless): ElGV3.exe --backup [carpeta_destino]
    # Lo usa la tarea programada de Windows; no abre la interfaz.
    if "--backup" in sys.argv:
        from modules.respaldo import respaldar
        i = sys.argv.index("--backup")
        destino = None
        if len(sys.argv) > i + 1 and not sys.argv[i + 1].startswith("-"):
            destino = sys.argv[i + 1]
        try:
            ruta = respaldar(destino)
            print(f"Respaldo creado: {ruta}")
            sys.exit(0)
        except Exception as e:
            print(f"ERROR en respaldo: {e}", file=sys.stderr)
            sys.exit(1)

    # Modo importación (headless): ElGV3.exe --import "archivo.xlsx"
    # Carga el inventario (hojas PRODUCTOS e INSUMOS) a la base local.
    if "--import" in sys.argv:
        from modules.importador import importar_inventario
        i = sys.argv.index("--import")
        if len(sys.argv) <= i + 1:
            print('ERROR: falta la ruta. Uso: ElGV3.exe --import "archivo.xlsx"',
                  file=sys.stderr)
            sys.exit(1)
        ruta = sys.argv[i + 1]
        inicializar()   # asegura que la BD y las categorías base existan
        try:
            res = importar_inventario(ruta)
            print(f"Productos: {res['productos_nuevos']} nuevos, "
                  f"{res['productos_actualizados']} actualizados")
            print(f"Insumos:   {res['insumos_nuevos']} nuevos, "
                  f"{res['insumos_actualizados']} actualizados")
            print(f"Categorías creadas: {res['categorias_creadas']}, "
                  f"ajustadas: {res['categorias_ajustadas']}")
            if res.get("recetas_lineas"):
                print(f"Recetas: {res['recetas_lineas']} líneas vinculadas")
            if res.get("preparaciones"):
                print(f"Preparaciones: {res['preparaciones']} "
                      f"({res['recetas_prep']} líneas de producción)")
            if res["omitidos"]:
                print(f"Omitidos ({len(res['omitidos'])}, sin precio_venta):")
                for o in res["omitidos"]:
                    print(f"   - {o}")
            sys.exit(0)
        except Exception as e:
            print(f"ERROR en importación: {e}", file=sys.stderr)
            sys.exit(1)

    if "--seed-cocina" in sys.argv:
        from modules.seed_cocina import poblar_cocina
        inicializar()   # asegura que la BD y las categorías base existan
        try:
            res = poblar_cocina()
            print(f"Categorías creadas: {res['categorias_creadas']}")
            print(f"Insumos: {res['insumos_nuevos']} nuevos, "
                  f"{res['insumos_existentes']} ya existían")
            print(f"Preparaciones: {res['preparaciones']} "
                  f"({res['recetas_prep']} líneas de receta de producción)")
            print(f"Platos: {res['platos_nuevos']} nuevos, "
                  f"{res['platos_actualizados']} actualizados")
            print(f"Líneas de receta: {res['recetas']}")
            if res["errores"]:
                print("Errores:")
                for e in res["errores"]:
                    print(f"   - {e}")
            sys.exit(0 if not res["errores"] else 1)
        except Exception as e:
            print(f"ERROR poblando cocina: {e}", file=sys.stderr)
            sys.exit(1)

    inicializar()
    app = LoginWindow()
    app.mainloop()
