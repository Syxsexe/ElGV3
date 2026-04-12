"""
ui/usuarios.py — El G POS
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI

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

