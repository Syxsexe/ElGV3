"""
ui/inicio.py — El G POS
Dashboard principal: KPIs, gráficos canvas, estado de caja y alertas.
"""

import tkinter as tk
from datetime import date, timedelta

import auth
from ui.base import (
    FrameBase, COLORS,
    FONT_BOLD, FONT_SMALL, FONT_KPI, FONT_LABEL,
)

# ── Paleta interna para gráficos ──────────────────────────────────────────────

_G = [
    COLORS["accent"],   # violeta
    COLORS["success"],  # verde
    COLORS["accent2"],  # rosa
    COLORS["warning"],  # amarillo
    "#00C9B1",          # teal
    "#A78BFA",          # lavanda
]


# ══════════════════════════════════════════════════════════════════════════════
# Funciones de dibujo canvas (puras — sin estado)
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_k(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.0f}k"
    return str(int(v))


def _barras(canvas, datos, w, h):
    """Gráfico de barras verticales. datos: [(etiqueta, valor)]"""
    canvas.delete("all")
    CT = COLORS["text_muted"]
    CB = COLORS["accent"]
    CR = COLORS["border"]

    if not datos or all(v == 0 for _, v in datos):
        canvas.create_text(w // 2, h // 2, text="Sin datos hoy",
                           font=("Segoe UI", 9), fill=CT)
        return

    L, R, T, B = 38, 6, 10, 22
    aw, ah = w - L - R, h - T - B
    mx = max(v for _, v in datos) or 1
    n  = len(datos)
    bw = aw / n

    # Grid
    for k in range(1, 4):
        y = T + ah - ah * k / 3
        canvas.create_line(L, y, w - R, y, fill=CR, dash=(2, 4))
        canvas.create_text(L - 3, y, text=_fmt_k(mx * k / 3),
                           font=("Segoe UI", 7), fill=CT, anchor="e")

    for i, (lbl, val) in enumerate(datos):
        x0 = L + i * bw + bw * 0.12
        x1 = L + (i + 1) * bw - bw * 0.12
        bh = (val / mx) * ah
        y0 = T + ah - bh
        y1 = T + ah
        canvas.create_rectangle(x0, y0, x1, y1, fill=CB, outline="")
        cx = (x0 + x1) / 2
        if bh > 16:
            canvas.create_text(cx, y0 + 8, text=_fmt_k(val),
                               font=("Segoe UI", 7, "bold"), fill=COLORS["bg"])
        canvas.create_text(cx, h - B + 9, text=lbl,
                           font=("Segoe UI", 7), fill=CT, anchor="n")

    canvas.create_line(L, T, L, T + ah, fill=CR)


def _linea(canvas, datos, w, h):
    """Gráfico de línea con área sombreada. datos: [(etiqueta, valor)]"""
    canvas.delete("all")
    CT = COLORS["text_muted"]
    CL = COLORS["success"]
    CR = COLORS["border"]

    if not datos:
        canvas.create_text(w // 2, h // 2, text="Sin datos",
                           font=("Segoe UI", 9), fill=CT)
        return

    L, R, T, B = 40, 10, 12, 24
    aw, ah = w - L - R, h - T - B
    mx = max(v for _, v in datos) or 1
    n  = len(datos)

    for k in range(1, 4):
        y = T + ah - ah * k / 3
        canvas.create_line(L, y, w - R, y, fill=CR, dash=(2, 4))
        canvas.create_text(L - 3, y, text=_fmt_k(mx * k / 3),
                           font=("Segoe UI", 7), fill=CT, anchor="e")

    def pos(i, v):
        x = L + (i * aw / max(n - 1, 1)) if n > 1 else L + aw / 2
        y = T + ah - (v / mx) * ah
        return x, y

    # Área
    pts = []
    for i, (_, v) in enumerate(datos):
        pts.extend(pos(i, v))
    pts += [pos(n - 1, 0)[0], T + ah, pos(0, 0)[0], T + ah]
    canvas.create_polygon(pts, fill=CL, outline="", stipple="gray25")

    # Línea
    if n >= 2:
        for i in range(n - 1):
            x0, y0 = pos(i,     datos[i][1])
            x1, y1 = pos(i + 1, datos[i + 1][1])
            canvas.create_line(x0, y0, x1, y1, fill=CL, width=2)

    # Puntos + etiquetas eje X
    for i, (lbl, val) in enumerate(datos):
        x, y = pos(i, val)
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4,
                           fill=CL, outline=COLORS["surface"], width=2)
        short = lbl[5:] if len(lbl) >= 10 else lbl
        canvas.create_text(x, h - B + 10, text=short,
                           font=("Segoe UI", 7), fill=CT, anchor="n")

    canvas.create_line(L, T, L, T + ah, fill=CR)


def _donut(canvas, datos, w, h):
    """Gráfico de dona. datos: [(etiqueta, valor)]"""
    canvas.delete("all")
    CT = COLORS["text_muted"]

    total = sum(v for _, v in datos) if datos else 0
    if not total:
        canvas.create_text(w // 2, h // 2, text="Sin datos",
                           font=("Segoe UI", 9), fill=CT)
        return

    ro = min(h // 2 - 10, 58)
    ri = int(ro * 0.54)
    cx, cy = ro + 14, h // 2

    ang = -90.0
    for i, (_, val) in enumerate(datos):
        ext = (val / total) * 360
        canvas.create_arc(cx - ro, cy - ro, cx + ro, cy + ro,
                          start=ang, extent=ext,
                          fill=_G[i % len(_G)],
                          outline=COLORS["surface"], width=2, style="pie")
        ang += ext

    # Agujero central
    canvas.create_oval(cx - ri, cy - ri, cx + ri, cy + ri,
                       fill=COLORS["surface"], outline="")
    canvas.create_text(cx, cy - 8, text=_fmt_k(total),
                       font=("Segoe UI", 11, "bold"), fill=COLORS["text"])
    canvas.create_text(cx, cy + 8, text="COP",
                       font=("Segoe UI", 7), fill=CT)

    # Leyenda
    lx = cx + ro + 14
    ly0 = cy - len(datos) * 10
    for i, (lbl, val) in enumerate(datos):
        ly = ly0 + i * 20
        canvas.create_rectangle(lx, ly, lx + 10, ly + 10,
                                fill=_G[i % len(_G)], outline="")
        pct = round(val / total * 100)
        canvas.create_text(lx + 14, ly + 5,
                           text=f"{lbl}  {pct}%",
                           font=("Segoe UI", 8), fill=COLORS["text"], anchor="w")


# ══════════════════════════════════════════════════════════════════════════════
# FrameInicio
# ══════════════════════════════════════════════════════════════════════════════

class FrameInicio(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Dashboard", "Resumen operativo — El G")
        self._content: tk.Frame | None = None
        self._build()

    # ── Setup inicial ─────────────────────────────────────────────────────────

    def _build(self):
        bar = tk.Frame(self, bg=COLORS["bg"])
        bar.pack(fill="x", padx=32, pady=(0, 10))

        tk.Label(bar,
                 text=date.today().strftime("%A %d de %B de %Y").capitalize(),
                 font=FONT_SMALL, bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(side="left")

        tk.Button(bar, text="⟳  Actualizar", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["accent"],
                  activebackground=COLORS["surface2"],
                  activeforeground=COLORS["accent"],
                  relief="flat", cursor="hand2", bd=0,
                  command=self._actualizar).pack(
                      side="right", ipady=4, ipadx=14)

        self._actualizar()

    # ── Carga de datos desde DB ───────────────────────────────────────────────

    def _cargar_datos(self) -> dict:
        from database import get_connection
        from modules.ventas import resumen_del_dia
        from modules.inventario import productos_bajo_stock, insumos_bajo_stock
        from modules.caja import get_sesion_activa, formatear_pesos

        hoy   = date.today().isoformat()
        ayer  = (date.today() - timedelta(days=1)).isoformat()
        hace7 = (date.today() - timedelta(days=6)).isoformat()

        conn = get_connection()

        # Comparativa ayer
        ayer_row = conn.execute("""
            SELECT COALESCE(SUM(total), 0) AS total, COUNT(*) AS num
            FROM ventas WHERE date(fecha) = ?
        """, (ayer,)).fetchone()

        # Ticket promedio hoy
        tick_row = conn.execute("""
            SELECT COALESCE(AVG(total), 0) AS avg
            FROM ventas WHERE date(fecha) = ?
        """, (hoy,)).fetchone()

        # Ventas por hora hoy
        horas_raw = conn.execute("""
            SELECT strftime('%H', fecha) AS hora,
                   COUNT(*) AS n, SUM(total) AS total
            FROM ventas WHERE date(fecha) = ?
            GROUP BY hora ORDER BY hora
        """, (hoy,)).fetchall()

        # Tendencia 7 días
        tend_raw = conn.execute("""
            SELECT date(fecha) AS dia, SUM(total) AS total
            FROM ventas
            WHERE date(fecha) BETWEEN ? AND ?
            GROUP BY dia ORDER BY dia
        """, (hace7, hoy)).fetchall()

        # Top 5 productos hoy
        top5 = conn.execute("""
            SELECT p.nombre,
                   SUM(dv.cantidad)  AS unidades,
                   SUM(dv.subtotal)  AS ingresos
            FROM detalle_venta dv
            JOIN ventas    v ON dv.venta_id    = v.id
            JOIN productos p ON dv.producto_id = p.id
            WHERE date(v.fecha) = ? AND dv.producto_id IS NOT NULL
            GROUP BY dv.producto_id
            ORDER BY unidades DESC LIMIT 5
        """, (hoy,)).fetchall()

        # Métodos de pago hoy
        metodos_raw = conn.execute("""
            SELECT pv.metodo, SUM(pv.monto) AS total
            FROM pagos_venta pv
            JOIN ventas v ON pv.venta_id = v.id
            WHERE date(v.fecha) = ?
            GROUP BY pv.metodo ORDER BY total DESC
        """, (hoy,)).fetchall()

        # Egresos del turno (puede no existir la tabla aún)
        sesion = get_sesion_activa()
        eg_ef = eg_dig = 0
        if sesion:
            try:
                from modules.caja import migrar_dos_cajas
                from modules.proveedores import migrar_egresos
                migrar_dos_cajas()
                migrar_egresos()
                row_eg = conn.execute("""
                    SELECT
                        COALESCE(SUM(CASE WHEN metodo_pago='efectivo'
                                         THEN total ELSE 0 END), 0) AS eg_ef,
                        COALESCE(SUM(CASE WHEN metodo_pago!='efectivo'
                                         THEN total ELSE 0 END), 0) AS eg_dig
                    FROM egresos WHERE sesion_id = ?
                """, (sesion["id"],)).fetchone()
                eg_ef  = row_eg["eg_ef"]  if row_eg else 0
                eg_dig = row_eg["eg_dig"] if row_eg else 0
            except Exception:
                pass

        conn.close()

        return {
            "fp":           formatear_pesos,
            "hoy":          hoy,
            "resumen":      resumen_del_dia(),
            "ayer_total":   ayer_row["total"] if ayer_row else 0,
            "ayer_num":     ayer_row["num"]   if ayer_row else 0,
            "ticket":       tick_row["avg"]   if tick_row else 0,
            "horas":        [(f"{r['hora']}h", r["total"]) for r in horas_raw],
            "tendencia":    [(r["dia"], r["total"])         for r in tend_raw],
            "top5":         [dict(r) for r in top5],
            "metodos":      [(r["metodo"].capitalize(), r["total"]) for r in metodos_raw],
            "sesion":       sesion,
            "eg_ef":        eg_ef,
            "eg_dig":       eg_dig,
            "prods_bajos":  productos_bajo_stock(),
            "insumos_bajos":insumos_bajo_stock(),
        }

    # ── Actualizar (destruye y reconstruye el contenido) ──────────────────────

    def _actualizar(self):
        if self._content:
            self._content.destroy()
        self._content = tk.Frame(self, bg=COLORS["bg"])
        self._content.pack(fill="both", expand=True)

        try:
            d = self._cargar_datos()
        except Exception as e:
            tk.Label(self._content, text=f"Error cargando datos: {e}",
                     font=FONT_LABEL, bg=COLORS["bg"],
                     fg=COLORS["danger"]).pack(pady=40)
            return

        self._render_kpis(d)
        self._render_charts(d)
        self._render_bottom(d)
        self._render_alertas(d)

    # ── Sección 1: KPI strip ──────────────────────────────────────────────────

    def _render_kpis(self, d):
        fp      = d["fp"]
        resumen = d["resumen"]

        def var(actual, anterior):
            if not anterior:
                return "", COLORS["text_muted"]
            pct = (actual - anterior) / anterior * 100
            sym = "▲" if pct >= 0 else "▼"
            col = COLORS["success"] if pct >= 0 else COLORS["danger"]
            return f"{sym} {abs(pct):.1f}%", col

        tienda = resumen["por_tipo"].get("tienda", 0)
        cocina = resumen["por_tipo"].get("cocina", 0)

        kpis = [
            ("Ventas hoy",    fp(resumen["total"]),        COLORS["accent"],
             *var(resumen["total"], d["ayer_total"])),
            ("Transacciones", str(resumen["num_ventas"]),  COLORS["success"],
             *var(resumen["num_ventas"], d["ayer_num"])),
            ("Ticket prom.",  fp(d["ticket"]),             COLORS["accent2"],
             "", COLORS["text_muted"]),
            ("Tienda",        fp(tienda),                  COLORS["accent"],
             "", COLORS["text_muted"]),
            ("Cocina",        fp(cocina),                  COLORS["warning"],
             "", COLORS["text_muted"]),
        ]

        row = tk.Frame(self._content, bg=COLORS["bg"])
        row.pack(fill="x", padx=32, pady=(0, 14))

        for i, (titulo, valor, color_val, var_txt, var_col) in enumerate(kpis):
            card = tk.Frame(row, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            card.pack(side="left", expand=True, fill="both",
                      padx=(0, 10 if i < 4 else 0), ipady=8)

            # Barra de color superior
            tk.Frame(card, bg=color_val, height=3).pack(fill="x")

            tk.Label(card, text=valor, font=FONT_KPI,
                     bg=COLORS["surface"], fg=color_val).pack(pady=(12, 2))
            tk.Label(card, text=titulo, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack()

            if var_txt:
                tk.Label(card, text=var_txt, font=("Segoe UI", 8, "bold"),
                         bg=COLORS["surface"], fg=var_col).pack(pady=(3, 10))
            else:
                tk.Frame(card, bg=COLORS["surface"], height=16).pack()

    # ── Sección 2: Gráficos ───────────────────────────────────────────────────

    def _bind_redibujo(self, cv, datos, fn, h):
        """Dibuja un gráfico en `cv` al mostrarlo y al redimensionar, de forma
        segura: tolera ser llamado sin evento (p. ej. durante la reconstrucción
        por cambio de tema) y si el canvas ya fue destruido."""
        def _redibujar(e=None):
            try:
                if not cv.winfo_exists():
                    return
                w = e.width if e is not None else max(cv.winfo_width(), 200)
                fn(cv, datos, w, h)
            except tk.TclError:
                pass
        cv.bind("<Configure>", _redibujar)
        cv.after(50, _redibujar)

    def _render_charts(self, d):
        row = tk.Frame(self._content, bg=COLORS["bg"])
        row.pack(fill="x", padx=32, pady=(0, 14))

        for titulo, datos, fn in [
            ("Ventas por hora — hoy",      d["horas"],     _barras),
            ("Tendencia — últimos 7 días", d["tendencia"], _linea),
        ]:
            card = tk.Frame(row, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=(0, 10))

            tk.Label(card, text=titulo, font=FONT_BOLD,
                     bg=COLORS["surface"], fg=COLORS["text"]).pack(
                         anchor="w", padx=16, pady=(12, 4))

            cv = tk.Canvas(card, bg=COLORS["surface"],
                           highlightthickness=0, height=170)
            cv.pack(fill="x", padx=8, pady=(0, 10))

            # Dibuja al mostrar y al redimensionar
            self._bind_redibujo(cv, datos, fn, 170)

        # Quitar el padx extra del último card
        row.winfo_children()[-1].pack_configure(padx=0)

    # ── Sección 3: Caja + Top productos + Métodos de pago ────────────────────

    def _render_bottom(self, d):
        fp     = d["fp"]
        sesion = d["sesion"]

        row = tk.Frame(self._content, bg=COLORS["bg"])
        row.pack(fill="both", expand=True, padx=32, pady=(0, 14))

        # ── Estado de caja ────────────────────────────────────────────────────
        caja_wrap = tk.Frame(row, bg=COLORS["bg"])
        caja_wrap.pack(side="left", fill="both", expand=True, padx=(0, 10))

        if sesion:
            base_ef  = sesion.get("monto_base", 0) or 0
            base_dig = sesion.get("monto_base_digital", 0) or 0
            tot_ef   = sesion.get("total_efectivo", 0) or 0
            tot_dig  = sesion.get("total_digital", 0) or 0
            saldo_ef  = base_ef  + tot_ef  - d["eg_ef"]
            saldo_dig = base_dig + tot_dig - d["eg_dig"]

            tk.Label(caja_wrap,
                     text=f"● Caja abierta  ·  {sesion['cajero']}  ·  desde {sesion['apertura'][11:16]}",
                     font=FONT_SMALL, bg=COLORS["bg"],
                     fg=COLORS["success"]).pack(anchor="w", pady=(0, 6))

            cards = tk.Frame(caja_wrap, bg=COLORS["bg"])
            cards.pack(fill="both", expand=True)

            def _mini(parent, titulo, bg, accent, filas, saldo, lbl_s):
                c = tk.Frame(parent, bg=bg,
                             highlightbackground=accent, highlightthickness=2)
                c.pack(side="left", fill="both", expand=True,
                       padx=(0, 5), ipady=4)
                # Tarjetas de fondo oscuro fijo: texto claro en ambos temas.
                tk.Label(c, text=titulo, font=FONT_BOLD,
                         bg=bg, fg=COLORS["on_accent"]).pack(pady=(8, 6))
                for lbl, val, ico in filas:
                    f = tk.Frame(c, bg=bg)
                    f.pack(fill="x", padx=12, pady=1)
                    tk.Label(f, text=f"{ico} {lbl}", font=FONT_SMALL,
                             bg=bg, fg="#AEB4C7").pack(side="left")
                    tk.Label(f, text=fp(val), font=FONT_SMALL,
                             bg=bg, fg=COLORS["on_accent"]).pack(side="right")
                sf = tk.Frame(c, bg=accent)
                sf.pack(fill="x", pady=(6, 0))
                tk.Label(sf, text=lbl_s, font=FONT_SMALL,
                         bg=accent, fg=COLORS["on_accent"]).pack(pady=(4, 0))
                tk.Label(sf, text=fp(saldo),
                         font=("Segoe UI", 15, "bold"),
                         bg=accent, fg=COLORS["on_accent"]).pack(pady=(0, 6))

            _mini(cards, "EFECTIVO", "#1A3A2A", "#2E8B57",
                  [("Inicial:", base_ef, "💵"),
                   ("Ventas:",  tot_ef,  "🛒"),
                   ("Gastos:",  d["eg_ef"], "📦")],
                  saldo_ef, "SALDO EFECTIVO")

            _mini(cards, "DIGITAL", "#1A1A3A", "#4B4BCC",
                  [("Inicial:", base_dig, "📱"),
                   ("Ventas:",  tot_dig,  "🛒"),
                   ("Gastos:",  d["eg_dig"], "📦")],
                  saldo_dig, "SALDO DIGITAL")
        else:
            card = tk.Frame(caja_wrap, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            card.pack(fill="both", expand=True)
            tk.Label(card, text="Estado de Caja", font=FONT_BOLD,
                     bg=COLORS["surface"], fg=COLORS["text"]).pack(
                         anchor="w", padx=16, pady=(16, 6))
            tk.Label(card, text="● Caja cerrada", font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["danger"]).pack(
                         anchor="w", padx=16, pady=(0, 16))

        # ── Top 5 productos ───────────────────────────────────────────────────
        top_card = tk.Frame(row, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1, width=230)
        top_card.pack(side="left", fill="both", padx=(0, 10))
        top_card.pack_propagate(False)

        tk.Label(top_card, text="Top 5 productos — hoy",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(12, 6))

        if d["top5"]:
            for i, p in enumerate(d["top5"], 1):
                bg = COLORS["surface2"] if i % 2 == 0 else COLORS["surface"]
                fila = tk.Frame(top_card, bg=bg)
                fila.pack(fill="x", padx=6, pady=1, ipady=4)

                tk.Label(fila, text=f"{i}.", font=FONT_SMALL,
                         bg=bg, fg=COLORS["text_muted"],
                         width=2, anchor="e").pack(side="left", padx=(6, 4))
                tk.Label(fila, text=p["nombre"][:24], font=FONT_SMALL,
                         bg=bg, fg=COLORS["text"],
                         anchor="w").pack(side="left", fill="x", expand=True)
                tk.Label(fila, text=f"×{int(p['unidades'])}",
                         font=("Segoe UI", 9, "bold"),
                         bg=bg, fg=COLORS["accent"]).pack(side="right", padx=(0, 8))
                tk.Label(fila, text=fp(p["ingresos"]),
                         font=FONT_SMALL, bg=bg,
                         fg=COLORS["text_muted"]).pack(side="right", padx=(0, 4))
        else:
            tk.Label(top_card, text="Sin ventas registradas hoy",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(padx=16, pady=24)

        # ── Métodos de pago (donut) ───────────────────────────────────────────
        pago_card = tk.Frame(row, bg=COLORS["surface"],
                             highlightbackground=COLORS["border"],
                             highlightthickness=1, width=250)
        pago_card.pack(side="right", fill="both")
        pago_card.pack_propagate(False)

        tk.Label(pago_card, text="Métodos de pago — hoy",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(12, 4))

        cv_d = tk.Canvas(pago_card, bg=COLORS["surface"],
                         highlightthickness=0, height=155)
        cv_d.pack(fill="x", padx=6, pady=(0, 10))
        self._bind_redibujo(cv_d, d["metodos"], _donut, 155)

    # ── Sección 4: Alertas de stock ───────────────────────────────────────────

    def _render_alertas(self, d):
        pb = d["prods_bajos"]
        ib = d["insumos_bajos"]

        if not pb and not ib:
            # Mensaje positivo compacto
            ok = tk.Frame(self._content, bg=COLORS["bg"])
            ok.pack(fill="x", padx=32, pady=(0, 20))
            tk.Label(ok, text="✓  Todo el stock en orden",
                     font=FONT_SMALL, bg=COLORS["bg"],
                     fg=COLORS["success"]).pack(anchor="w")
            return

        card = tk.Frame(self._content, bg=COLORS["surface"],
                        highlightbackground=COLORS["warning"],
                        highlightthickness=1)
        card.pack(fill="x", padx=32, pady=(0, 24), ipady=6)

        hdr = tk.Frame(card, bg=COLORS["surface"])
        hdr.pack(fill="x", padx=16, pady=(10, 6))
        tk.Label(hdr, text="⚠  Alertas de stock bajo",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["warning"]).pack(side="left")
        total_alertas = len(pb) + len(ib)
        tk.Label(hdr, text=f"{total_alertas} ítem{'s' if total_alertas != 1 else ''}",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(side="right")

        grid = tk.Frame(card, bg=COLORS["surface"])
        grid.pack(fill="x", padx=16, pady=(0, 8))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        alertas = [
            (p["nombre"], f"Stock: {p['stock']} / Mín: {p['stock_minimo']}", "Prod.")
            for p in pb[:4]
        ] + [
            (i["nombre"], f"Stock: {i['stock']} {i['unidad']}", "Ins.")
            for i in ib[:4]
        ]

        for idx, (nombre, detalle, tipo) in enumerate(alertas):
            col = idx % 2
            row_n = idx // 2

            fila = tk.Frame(grid, bg=COLORS["surface2"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
            fila.grid(row=row_n, column=col, sticky="ew",
                      padx=(0, 8 if col == 0 else 0), pady=3, ipady=5)

            tk.Label(fila, text="⚠", font=FONT_SMALL,
                     bg=COLORS["surface2"], fg=COLORS["warning"]).pack(side="left", padx=(8, 4))

            inner = tk.Frame(fila, bg=COLORS["surface2"])
            inner.pack(side="left", fill="x", expand=True)
            tk.Label(inner, text=nombre[:30], font=FONT_BOLD,
                     bg=COLORS["surface2"], fg=COLORS["text"],
                     anchor="w").pack(anchor="w")
            tk.Label(inner, text=detalle, font=FONT_SMALL,
                     bg=COLORS["surface2"], fg=COLORS["text_muted"],
                     anchor="w").pack(anchor="w")

            tk.Label(fila, text=tipo, font=("Segoe UI", 7),
                     bg=COLORS["surface2"], fg=COLORS["text_dim"]).pack(
                         side="right", padx=(0, 8))
