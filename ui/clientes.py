"""
ui/clientes.py — El G POS
Gestión de clientes para facturación y clientes frecuentes.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL


class FrameClientes(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Clientes", "Registro de clientes y datos fiscales")
        self._build()

    def _build(self):
        from modules.clientes import listar_clientes, crear_cliente

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # Tabla de clientes
        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tk.Label(left, text="Clientes registrados", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))

        tabla_wrap = tk.Frame(left, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)

        cols = ("ID", "Nombre", "Documento", "Tipo", "Teléfono", "Activo")
        self.tree = self._tabla(tabla_wrap, cols, alto=18)
        self.tree.column("ID", width=40)
        self.tree.column("Nombre", width=220, anchor="w")
        self.tree.column("Documento", width=130)
        self.tree.column("Tipo", width=100)
        self.tree.column("Teléfono", width=120)
        self.tree.column("Activo", width=70)

        self._cargar_clientes()

        # Panel de formulario
        panel = self._card(main, width=320)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)

        tk.Label(panel, text="Nuevo cliente", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 12))

        campos = [
            ("Nombre", "entry_nombre"),
            ("Tipo de documento", "combo_tipo"),
            ("Número de documento", "entry_documento"),
            ("Dirección", "entry_direccion"),
            ("Teléfono", "entry_telefono"),
            ("Email", "entry_email"),
        ]

        for lbl, attr in campos:
            tk.Label(panel, text=lbl, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
            if attr == "combo_tipo":
                combo = ttk.Combobox(panel,
                                     values=["CC", "NIT", "CE", "TI", "CONSUMIDOR_FINAL"],
                                     font=FONT_LABEL, state="readonly")
                combo.set("CC")
                combo.pack(fill="x", padx=16, pady=(2, 10), ipady=4)
                setattr(self, attr, combo)
            else:
                e = self._input(panel)
                e.pack(fill="x", padx=16, pady=(2, 10), ipady=5)
                setattr(self, attr, e)

        self._btn_primary(panel, "Crear cliente", self._crear_cliente).pack(
            fill="x", padx=16, ipady=10)

    def _cargar_clientes(self):
        from modules.clientes import listar_clientes

        self.tree.delete(*self.tree.get_children())
        for c in listar_clientes():
            self.tree.insert("", "end", iid=str(c["id"]), values=(
                c["id"], c["nombre"], c["documento"], c["tipo_documento"],
                c["telefono"] or "", "Sí" if c["activo"] else "No"
            ))

    def _crear_cliente(self):
        from modules.clientes import crear_cliente

        nombre = self.entry_nombre.get().strip()
        tipo_documento = self.combo_tipo.get()
        documento = self.entry_documento.get().strip()
        direccion = self.entry_direccion.get().strip()
        telefono = self.entry_telefono.get().strip()
        email = self.entry_email.get().strip()

        if not nombre or not documento:
            messagebox.showwarning("Campos vacíos", "Completa nombre y documento.")
            return

        try:
            crear_cliente(
                nombre=nombre,
                tipo_documento=tipo_documento,
                documento=documento,
                direccion=direccion,
                telefono=telefono,
                email=email,
            )
            messagebox.showinfo("Cliente creado", f"Cliente '{nombre}' creado con éxito.")
            self.entry_nombre.delete(0, "end")
            self.entry_documento.delete(0, "end")
            self.entry_direccion.delete(0, "end")
            self.entry_telefono.delete(0, "end")
            self.entry_email.delete(0, "end")
            self.combo_tipo.set("CC")
            self._cargar_clientes()
        except Exception as e:
            messagebox.showerror("Error", str(e))
