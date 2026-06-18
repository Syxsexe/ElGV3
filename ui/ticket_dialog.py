"""
ui/ticket_dialog.py — El G POS
Diálogo reutilizable para previsualizar e imprimir tickets.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ui.base import COLORS, FONT_BOLD, FONT_SMALL, FONT_LABEL


class DialogTicket(tk.Toplevel):
    """
    Muestra el ticket generado con opciones de:
    - Imprimir en térmica
    - Guardar como .txt
    - Cerrar sin hacer nada
    """

    def __init__(self, parent, texto: str, titulo: str = "Ticket"):
        super().__init__(parent)
        self.title(titulo)
        self.configure(bg=COLORS["surface"])
        self.resizable(True, True)
        self.grab_set()
        self.focus_force()
        self._texto = texto
        self._build()
        self._centrar(520, 600)

    def _centrar(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        from modules.ticket import listar_impresoras

        # Barra superior
        top = tk.Frame(self, bg=COLORS["surface2"], pady=8)
        top.pack(fill="x")
        tk.Label(top, text="Vista previa del ticket",
                 font=FONT_BOLD, bg=COLORS["surface2"],
                 fg=COLORS["text"]).pack(side="left", padx=16)

        # Vista previa del ticket
        preview_frame = tk.Frame(self, bg=COLORS["bg"])
        preview_frame.pack(fill="both", expand=True, padx=16, pady=12)

        self._txt = tk.Text(
            preview_frame,
            font=("Courier New", 9),
            bg=COLORS["bg"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            wrap="none",
            state="normal"
        )
        scroll_y = ttk.Scrollbar(preview_frame, orient="vertical",
                                  command=self._txt.yview)
        scroll_x = ttk.Scrollbar(preview_frame, orient="horizontal",
                                  command=self._txt.xview)
        self._txt.configure(yscrollcommand=scroll_y.set,
                             xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self._txt.pack(fill="both", expand=True)

        self._txt.insert("1.0", self._texto)
        self._txt.config(state="disabled")

        # Selector de impresora
        impresoras = listar_impresoras()
        imp_frame = tk.Frame(self, bg=COLORS["surface"], pady=6)
        imp_frame.pack(fill="x", padx=16)

        tk.Label(imp_frame, text="Impresora:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")

        self._imp_var = tk.StringVar()
        combo_state = "readonly" if impresoras else "disabled"
        self._combo_imp = ttk.Combobox(
            imp_frame, textvariable=self._imp_var,
            values=impresoras, font=FONT_LABEL,
            state=combo_state, width=30
        )
        if impresoras:
            self._combo_imp.set(impresoras[0])
        else:
            self._combo_imp.set("Sin impresoras detectadas")
        self._combo_imp.pack(side="left", padx=(8, 0))

        # Botones de acción
        btn_frame = tk.Frame(self, bg=COLORS["surface"], pady=12)
        btn_frame.pack(fill="x", padx=16)

        self._btn_imprimir = tk.Button(
            btn_frame, text="🖨  Imprimir",
            font=FONT_BOLD,
            bg=COLORS["accent"], fg=COLORS["text"],
            activebackground=COLORS["accent_hover"],
            relief="flat", cursor="hand2",
            command=self._imprimir
        )
        if not impresoras:
            self._btn_imprimir.config(state="disabled")
        self._btn_imprimir.pack(side="left", ipady=8, ipadx=16)

        tk.Button(
            btn_frame, text="💾  Guardar .txt",
            font=FONT_BOLD,
            bg=COLORS["surface2"], fg=COLORS["text"],
            activebackground=COLORS["border"],
            relief="flat", cursor="hand2",
            command=self._guardar
        ).pack(side="left", padx=(8, 0), ipady=8, ipadx=16)

        tk.Button(
            btn_frame, text="Cerrar",
            font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"],
            activebackground=COLORS["surface2"],
            relief="flat", cursor="hand2",
            command=self.destroy
        ).pack(side="right", ipady=6, ipadx=12)

    def _imprimir(self):
        from modules.ticket import imprimir_ticket
        impresora = self._imp_var.get()
        if not impresora or "Sin impresoras" in impresora:
            messagebox.showwarning(
                "Sin impresora",
                "No se detectaron impresoras en este sistema.\n"
                "La impresión directa está disponible solo en Windows con pywin32.",
                parent=self
            )
            return
        try:
            imprimir_ticket(self._texto, impresora)
            messagebox.showinfo("Impreso", "Ticket enviado a la impresora.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error al imprimir", str(e), parent=self)

    def _guardar(self):
        from modules.ticket import guardar_ticket
        ruta = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile="ticket.txt",
            parent=self
        )
        if ruta:
            guardar_ticket(self._texto, ruta)
            messagebox.showinfo("Guardado", f"Ticket guardado en:\n{ruta}", parent=self)


def mostrar_ticket_venta(parent, venta_id: int):
    from modules.ticket import generar_ticket_venta
    try:
        texto = generar_ticket_venta(venta_id)
        DialogTicket(parent, texto, f"Ticket — Venta #{venta_id}")
    except Exception as e:
        messagebox.showerror("Error", str(e), parent=parent)


def mostrar_ticket_cuenta(parent, cuenta_id: int, venta_id: int = None):
    from modules.ticket import generar_ticket_cuenta
    try:
        texto = generar_ticket_cuenta(cuenta_id, venta_id)
        DialogTicket(parent, texto, f"Ticket — Mesa / Cuenta #{cuenta_id}")
    except Exception as e:
        messagebox.showerror("Error", str(e), parent=parent)


def mostrar_ticket_pedido(parent, pedido_id: int):
    from modules.ticket import generar_ticket_pedido
    try:
        texto = generar_ticket_pedido(pedido_id)
        DialogTicket(parent, texto, f"Ticket — Pedido #{pedido_id}")
    except Exception as e:
        messagebox.showerror("Error", str(e), parent=parent)
