"""
ui/usuarios.py — El G POS
Gestión de accesos. Alta de usuario en ventana emergente (ui.modal.ModalForm)
para caber en pantallas de baja resolución (1366x768); la tabla ocupa todo el
ancho y se desactiva con el botón de la barra superior.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI
from ui.modal import ModalForm


class FrameUsuarios(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Usuarios", "Gestión de accesos al sistema")
        self._modal = None
        self._build()

    def _build(self):
        # Barra de acciones
        acciones = tk.Frame(self, bg=COLORS["bg"])
        acciones.pack(fill="x", padx=32, pady=(0, 10))
        self._btn_primary(acciones, "+ Nuevo usuario", self._modal_usuario).pack(
            side="right", padx=(8, 0), ipady=4, ipadx=12)
        self._btn_danger(acciones, "Desactivar seleccionado", self._desactivar).pack(
            side="right", ipady=4, ipadx=10)

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        tabla_wrap = tk.Frame(main, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)
        self.tree = self._tabla(tabla_wrap,
                                ("ID", "Usuario", "Rol", "Activo", "Creado"),
                                alto=12)
        self.tree.column("ID",      width=40)
        self.tree.column("Usuario", width=200, anchor="w")
        self.tree.column("Rol",     width=110)
        self.tree.column("Activo",  width=80)
        self.tree.column("Creado",  width=160)
        self._cargar_usuarios()

    def _cargar_usuarios(self):
        from auth import listar_usuarios
        self.tree.delete(*self.tree.get_children())
        for u in listar_usuarios():
            self.tree.insert("", "end", iid=str(u["id"]), values=(
                u["id"], u["usuario"], u["rol"],
                "Sí" if u["activo"] else "No",
                u["creado_en"][:10]
            ))

    # ── Modal: nuevo usuario ────────────────────────────────────────────────

    def _modal_usuario(self):
        m = ModalForm(self, "Nuevo usuario", ancho=380)
        self._modal = m
        body = m.body

        for lbl, attr in [("Usuario", "entry_nuevo_user"), ("Contraseña", "entry_nuevo_pass")]:
            tk.Label(body, text=lbl, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16, pady=(8, 0))
            e = self._input(body, show="●" if lbl == "Contraseña" else None)
            e.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
            setattr(self, attr, e)

        tk.Label(body, text="Rol", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=16, pady=(8, 0))
        self.combo_rol = ttk.Combobox(body, values=["admin", "vendedor"],
                                       font=FONT_LABEL, state="readonly")
        self.combo_rol.set("vendedor")
        self.combo_rol.pack(fill="x", padx=16, pady=(2, 12))

        self._btn_primary(m.footer, "Crear usuario", self._crear).pack(
            side="right", ipady=6, ipadx=16)
        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(
            side="left", ipady=6, ipadx=14)

        m.mostrar()

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
            self._cargar_usuarios()
            if self._modal is not None:
                try:
                    self._modal.cerrar()
                except tk.TclError:
                    pass
                self._modal = None
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
