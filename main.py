"""
main.py — El G POS
Punto de entrada. Lanza el login y construye la interfaz principal.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from database import inicializar
import auth

from ui.base import COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI
from ui import (
    FrameInicio, FrameVentas, FrameInventario,
    FrameCaja, FrameReportes, FrameUsuarios, FrameCuentas,
    FrameClientes, FrameProveedores,
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
        self._center(400, 500)
        from modules.validaciones import registrar_validaciones
        registrar_validaciones(self)
        self._build()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        frame = tk.Frame(self, bg=COLORS["surface"],
                         highlightbackground=COLORS["border"],
                         highlightthickness=1)
        frame.place(relx=0.5, rely=0.5, anchor="center", width=320, height=400)

        tk.Label(frame, text="El G", font=("Segoe UI", 36, "bold"),
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(pady=(40, 4))
        tk.Label(frame, text="Sistema de Punto de Venta",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack()

        sep = tk.Frame(frame, bg=COLORS["accent"], height=2, width=60)
        sep.pack(pady=20)

        tk.Label(frame, text="Usuario", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"],
                 anchor="w").pack(padx=40, fill="x")
        self.entry_user = self._input(frame)
        self.entry_user.pack(padx=40, fill="x", pady=(4, 14))

        tk.Label(frame, text="Contrasena", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"],
                 anchor="w").pack(padx=40, fill="x")
        self.entry_pass = self._input(frame, show="*")
        self.entry_pass.pack(padx=40, fill="x", pady=(4, 24))

        tk.Button(
            frame, text="Ingresar", font=FONT_BOLD,
            bg=COLORS["accent"], fg=COLORS["text"],
            activebackground=COLORS["accent_hover"],
            activeforeground=COLORS["text"],
            relief="flat", cursor="hand2",
            command=self._login
        ).pack(padx=40, fill="x", ipady=10)

        self.lbl_error = tk.Label(frame, text="", font=FONT_SMALL,
                                   bg=COLORS["surface"], fg=COLORS["danger"])
        self.lbl_error.pack(pady=(10, 0))

        self.bind("<Return>", lambda e: self._login())
        self.entry_user.focus()

    def _input(self, parent, show=None):
        return tk.Entry(
            parent, font=FONT_LABEL, show=show,
            bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )

    def _login(self):
        usuario    = self.entry_user.get().strip()
        contrasena = self.entry_pass.get()
        if not usuario or not contrasena:
            self.lbl_error.config(text="Completa todos los campos.")
            return
        sesion = auth.iniciar_sesion(usuario, contrasena)
        if not sesion:
            self.lbl_error.config(text="Usuario o contrasena incorrectos.")
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
        # Intentar maximizar la ventana; algunos WMs no soportan 'zoomed'
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                # alternativa en algunos sistemas X11
                self.attributes("-zoomed", True)
            except Exception:
                # último recurso: dejar ventana en estado normal
                pass
        self._frame_actual = None
        self._build()

    def _build(self):
        self.sidebar = tk.Frame(self, bg=COLORS["surface"], width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="El G", font=("Segoe UI", 20, "bold"),
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(pady=(28, 2))
        tk.Label(self.sidebar, text="POS", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_dim"]).pack()
        tk.Frame(self.sidebar, bg=COLORS["border"], height=1).pack(fill="x", padx=20, pady=16)

        self._nav_activo = None
        self._nav_btns   = {}

        sesion    = auth.get_sesion()
        nav_items = [
            ("Inicio",      self._mostrar_inicio),
            ("Nueva Venta", self._mostrar_ventas),
            ("Clientes",    self._mostrar_clientes),
            ("Cuentas",     self._mostrar_cuentas),
            ("Inventario",  self._mostrar_inventario),
            ("Proveedores", self._mostrar_proveedores),
            ("Caja",        self._mostrar_caja),
        ]
        if sesion["rol"] == "admin":
            nav_items += [
                ("Reportes", self._mostrar_reportes),
                ("Usuarios", self._mostrar_usuarios),
            ]
        for label, cmd in nav_items:
            self._nav_btn(label, cmd)

        tk.Frame(self.sidebar, bg=COLORS["surface"]).pack(expand=True, fill="y")
        tk.Frame(self.sidebar, bg=COLORS["border"], height=1).pack(fill="x", padx=20, pady=8)

        info = tk.Frame(self.sidebar, bg=COLORS["surface"])
        info.pack(padx=16, pady=(0, 8), fill="x")
        tk.Label(info, text=sesion["usuario"], font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w")
        tk.Label(info, text=sesion["rol"].capitalize(), font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w")

        tk.Button(
            self.sidebar, text="Cerrar sesion", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"],
            relief="flat", cursor="hand2", command=self._cerrar_sesion,
            activebackground=COLORS["surface2"],
            activeforeground=COLORS["danger"],
        ).pack(padx=16, pady=(0, 20), anchor="w")

        self._content_outer = tk.Frame(self, bg=COLORS["bg"])
        self._content_outer.pack(side="right", expand=True, fill="both")

        self._canvas = tk.Canvas(self._content_outer, bg=COLORS["bg"],
                                  highlightthickness=0, bd=0)
        self._scrollbar = ttk.Scrollbar(self._content_outer, orient="vertical",
                                         command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", expand=True, fill="both")

        self.content = tk.Frame(self._canvas, bg=COLORS["bg"])
        self._canvas_window = self._canvas.create_window((0, 0), window=self.content, anchor="nw")

        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self.content.bind("<Configure>",  self._on_content_resize)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>",   self._on_mousewheel)
        self._canvas.bind_all("<Button-5>",   self._on_mousewheel)

        self._mostrar_inicio()

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_content_resize(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        if self.content.winfo_reqheight() > self._canvas.winfo_height():
            self._scrollbar.pack(side="right", fill="y")
        else:
            self._scrollbar.pack_forget()

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

    def _nav_btn(self, label, cmd):
        btn = tk.Button(
            self.sidebar, text=f"  {label}",
            font=FONT_NAV, bg=COLORS["surface"], fg=COLORS["text_muted"],
            relief="flat", anchor="w", cursor="hand2",
            activebackground=COLORS["surface2"],
            activeforeground=COLORS["text"],
            command=lambda c=cmd, l=label: self._nav_click(l, c),
        )
        btn.pack(fill="x", padx=8, pady=2, ipady=8)
        self._nav_btns[label] = btn

    def _nav_click(self, label, cmd):
        for btn in self._nav_btns.values():
            btn.config(bg=COLORS["surface"], fg=COLORS["text_muted"])
        self._nav_btns[label].config(bg=COLORS["surface2"], fg=COLORS["accent"])
        cmd()

    def _cambiar_frame(self, nuevo_frame_cls, **kwargs):
        if self._frame_actual:
            self._frame_actual.destroy()
        self._frame_actual = nuevo_frame_cls(self.content, **kwargs)
        self._frame_actual.pack(expand=True, fill="both")
        self._resetear_scroll()

    def _mostrar_inicio(self):
        self._nav_click("Inicio", lambda: None)
        self._cambiar_frame(FrameInicio)

    def _mostrar_ventas(self):
        self._nav_click("Nueva Venta", lambda: None)
        self._cambiar_frame(FrameVentas)

    def _mostrar_cuentas(self):
        self._nav_click("Cuentas", lambda: None)
        self._cambiar_frame(FrameCuentas)

    def _mostrar_clientes(self):
        self._nav_click("Clientes", lambda: None)
        self._cambiar_frame(FrameClientes)

    def _mostrar_inventario(self):
        self._nav_click("Inventario", lambda: None)
        self._cambiar_frame(FrameInventario)

    def _mostrar_proveedores(self):
        self._nav_click("Proveedores", lambda: None)
        self._cambiar_frame(FrameProveedores)

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
        if messagebox.askyesno("Cerrar sesion", "Deseas cerrar la sesion actual?"):
            auth.cerrar_sesion()
            self.destroy()
            login = LoginWindow()
            login.mainloop()


# ════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    inicializar()
    app = LoginWindow()
    app.mainloop()