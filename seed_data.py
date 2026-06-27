"""
seed_data.py — El G POS
Carga datos de prueba realistas para probar el sistema completo.
Ejecutar UNA sola vez después de inicializar la base de datos vacía:
    python seed_data.py

Cubre: inventario, insumos, recetas, combos, proveedores,
       usuarios, clientes, créditos (con escenarios variados).
"""

from database import inicializar, get_connection
from auth import iniciar_sesion
from modules.inventario import (
    listar_categorias, crear_producto, crear_insumo, guardar_receta
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def crear_o_obtener_producto(nombre, categoria_id, precio_venta,
                              precio_costo=0, stock=0, stock_minimo=0, codigo=None):
    conn = get_connection()
    if codigo:
        fila = conn.execute("SELECT id FROM productos WHERE codigo = ?", (codigo,)).fetchone()
    else:
        fila = conn.execute("SELECT id FROM productos WHERE nombre = ?", (nombre,)).fetchone()
    conn.close()
    if fila:
        return fila["id"]
    return crear_producto(nombre, categoria_id, precio_venta,
                          precio_costo, stock, stock_minimo, codigo)

def crear_o_obtener_insumo(nombre, stock=0, unidad="unidad", stock_minimo=0):
    conn = get_connection()
    fila = conn.execute("SELECT id FROM insumos WHERE nombre = ?", (nombre,)).fetchone()
    conn.close()
    if fila:
        return fila["id"]
    return crear_insumo(nombre, stock, unidad, stock_minimo)

def obtener_o_crear_cliente(nombre, tipo_doc, documento, telefono=None, email=None):
    conn = get_connection()
    fila = conn.execute("SELECT id FROM clientes WHERE documento = ?", (documento,)).fetchone()
    conn.close()
    if fila:
        return fila["id"]
    from modules.clientes import crear_cliente
    return crear_cliente(nombre, tipo_doc, documento,
                         telefono=telefono, email=email)

from modules.ventas import crear_combo
from modules.cuentas import migrar as migrar_cuentas

# ── Inicializar ───────────────────────────────────────────────────────────────
inicializar()
migrar_cuentas()
iniciar_sesion("admin", "admin123")

cats = {c["nombre"]: c["id"] for c in listar_categorias()}

# ══════════════════════════════════════════════════════════════════════════════
# USUARIOS ADICIONALES
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Creando usuarios ──")
from auth import crear_usuario

for usuario, clave, rol in [
    ("vendedor1", "vend123",  "vendedor"),
    ("vendedor2", "vend456",  "vendedor"),
    ("cajero1",   "caja123",  "vendedor"),
]:
    ok = crear_usuario(usuario, clave, rol)
    print(f"  {'✓' if ok else '~'} {usuario} ({rol})")

# ══════════════════════════════════════════════════════════════════════════════
# INVENTARIO — TIENDA
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Creando productos de tienda ──")

sobres = [
    ("Sobre Pokemon Scarlet & Violet",       "PKM-SV-001", 15000,  9000, 40, 10),
    ("Sobre Pokemon Temporal Forces",        "PKM-TF-001", 15000,  9000, 30,  8),
    ("Sobre Magic The Gathering — Murders",  "MTG-MKM-01", 18000, 11000, 25,  8),
    ("Sobre Magic The Gathering — Thunder",  "MTG-OTJ-01", 18000, 11000, 20,  5),
    ("Sobre Yu-Gi-Oh! Rage of the Abyss",   "YGO-RA02-1", 14000,  8500, 30,  8),
    ("Sobre One Piece Card Game OP-07",      "OPC-OP07-1", 16000, 10000, 20,  5),
]
for nombre, codigo, pv, pc, stock, minimo in sobres:
    pid = crear_o_obtener_producto(nombre, cats["TCG - Sobres"], pv, pc, stock, minimo, codigo)
    print(f"  ✓ {nombre} (ID {pid})")

mazos = [
    ("Mazo Pokemon Ex Starter — Meowscarada", "PKM-EX-001", 65000, 42000, 6, 2),
    ("Mazo Pokemon Ex Starter — Skeledirge",  "PKM-EX-002", 65000, 42000, 6, 2),
    ("Mazo Commander Magic — Chaos Incarnate","MTG-CMD-01", 85000, 55000, 4, 1),
    ("Mazo Structure Yu-Gi-Oh! Fire King",    "YGO-STR-01", 35000, 20000, 8, 2),
]
for nombre, codigo, pv, pc, stock, minimo in mazos:
    pid = crear_o_obtener_producto(nombre, cats["TCG - Mazos"], pv, pc, stock, minimo, codigo)
    print(f"  ✓ {nombre} (ID {pid})")

paquetes = [
    ("Paquete 5 cartas Pokemon comunes",   "PKM-PKT-C", 3000,  1500, 50, 10),
    ("Paquete 5 cartas Pokemon poco com.", "PKM-PKT-U", 5000,  2500, 40, 10),
    ("Paquete 5 cartas Magic comunes",     "MTG-PKT-C", 4000,  2000, 40,  8),
    ("Paquete 5 cartas Yu-Gi-Oh comunes",  "YGO-PKT-C", 3000,  1500, 50, 10),
]
for nombre, codigo, pv, pc, stock, minimo in paquetes:
    pid = crear_o_obtener_producto(nombre, cats["TCG - Paquetes cartas"], pv, pc, stock, minimo, codigo)
    print(f"  ✓ {nombre} (ID {pid})")

accesorios = [
    ("Sleeves Dragon Shield Matte (100 uds)", "ACC-DS-100", 28000, 18000, 15, 3),
    ("Sleeves Ultra Pro (50 uds)",            "ACC-UP-050", 12000,  7000, 20, 5),
    ("Playmat El G Logo",                     "ACC-PM-ELG", 45000, 28000,  5, 1),
    ("Deckbox Top Loader",                    "ACC-DB-TL1",  8000,  4500, 20, 5),
    ("Dados de vida — juego x7",              "ACC-DIC-7D",  9000,  5000, 15, 3),
    ("Contador de vida Pokemon",              "ACC-CTR-PK", 15000,  9000, 10, 2),
    ("Carpeta porta cartas (9 bolsillos)",    "ACC-BIN-9P", 22000, 13000, 12, 3),
    ("Token Pack Magic x30",                  "ACC-TOK-30",  7000,  4000, 25, 5),
]
for nombre, codigo, pv, pc, stock, minimo in accesorios:
    pid = crear_o_obtener_producto(nombre, cats["Accesorios TCG"], pv, pc, stock, minimo, codigo)
    print(f"  ✓ {nombre} (ID {pid})")

juegos = [
    ("Catan — Edición Base",           "JM-CAT-001", 120000, 75000, 3, 1),
    ("Catan — Expansión Ciudades",     "JM-CAT-EXP",  75000, 48000, 2, 1),
    ("Ticket to Ride Europa",          "JM-TTR-EU1",  95000, 60000, 2, 1),
    ("Dixit — Edición Base",           "JM-DIX-001",  80000, 50000, 3, 1),
    ("Codenames",                      "JM-CDN-001",  55000, 34000, 4, 1),
    ("Exploding Kittens",              "JM-EXK-001",  45000, 28000, 5, 2),
    ("Uno Attack",                     "JM-UNO-ATK",  35000, 20000, 8, 2),
    ("Jenga Clásico",                  "JM-JEN-001",  28000, 16000, 6, 2),
]
for nombre, codigo, pv, pc, stock, minimo in juegos:
    pid = crear_o_obtener_producto(nombre, cats["Juegos de mesa"], pv, pc, stock, minimo, codigo)
    print(f"  ✓ {nombre} (ID {pid})")

# ══════════════════════════════════════════════════════════════════════════════
# INSUMOS Y COCINA
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Creando insumos de cocina ──")
insumos_data = [
    ("Carne de res (presa 100g)",  30, "porción",  8),
    ("Pan de hamburguesa",         30, "unidad",    8),
    ("Pan de perro caliente",      30, "unidad",    8),
    ("Salchicha",                  40, "unidad",   10),
    ("Queso tajada",               60, "tajada",   15),
    ("Tomate",                     20, "rodaja",    5),
    ("Lechuga",                    20, "porción",   5),
    ("Papas a la francesa (200g)", 25, "porción",   6),
    ("Salsa de tomate",            50, "porción",  10),
    ("Mayonesa",                   50, "porción",  10),
    ("Mostaza",                    50, "porción",  10),
    ("Gaseosa lata",               48, "unidad",   12),
    ("Agua botella 600ml",         24, "unidad",    6),
    ("Jugo Hit",                   24, "unidad",    6),
    ("Vaso desechable 16oz",      100, "unidad",   20),
    ("Caja para hamburguesa",      50, "unidad",   10),
    ("Papel de aluminio",         100, "porción",  20),
]
insumos_ids = {}
for nombre, stock, unidad, minimo in insumos_data:
    iid = crear_o_obtener_insumo(nombre, stock, unidad, minimo)
    insumos_ids[nombre] = iid
    print(f"  ✓ {nombre} (ID {iid})")

print("\n── Creando productos de cocina ──")

def prod_cocina(nombre, codigo, pv, pc):
    return crear_o_obtener_producto(nombre, cats["Comidas rápidas"], pv, pc, 0, 0, codigo)

id_hamburguesa  = prod_cocina("Hamburguesa clásica",     "COM-HAM-CL", 12000, 5500)
id_ham_especial = prod_cocina("Hamburguesa especial",    "COM-HAM-ES", 15000, 7000)
id_perro        = prod_cocina("Perro caliente clásico",  "COM-PER-CL",  8000, 3500)
id_perro_esp    = prod_cocina("Perro caliente especial", "COM-PER-ES", 10000, 4500)
id_papas        = prod_cocina("Papas a la francesa",     "COM-PAP-FR",  5000, 1800)
id_papas_qso    = prod_cocina("Papas con queso",         "COM-PAP-QS",  7000, 2800)

for nombre in ["Hamburguesa clásica", "Hamburguesa especial", "Perro caliente clásico",
               "Perro caliente especial", "Papas a la francesa", "Papas con queso"]:
    print(f"  ✓ {nombre}")

id_gaseosa = crear_o_obtener_producto("Gaseosa lata",  cats["Bebidas"], 4000, 2000, 48, 12, "BEB-GAS-LT")
id_agua    = crear_o_obtener_producto("Agua 600ml",     cats["Bebidas"], 2500, 1200, 24,  6, "BEB-AGU-60")
id_jugo    = crear_o_obtener_producto("Jugo Hit",       cats["Bebidas"], 3500, 1800, 24,  6, "BEB-JUI-HT")
print("  ✓ Bebidas creadas")

print("\n── Asignando recetas ──")

guardar_receta(id_hamburguesa, [
    {"insumo_id": insumos_ids["Carne de res (presa 100g)"], "cantidad": 1},
    {"insumo_id": insumos_ids["Pan de hamburguesa"],        "cantidad": 1},
    {"insumo_id": insumos_ids["Queso tajada"],              "cantidad": 1},
    {"insumo_id": insumos_ids["Salsa de tomate"],           "cantidad": 1},
    {"insumo_id": insumos_ids["Mayonesa"],                  "cantidad": 1},
    {"insumo_id": insumos_ids["Caja para hamburguesa"],     "cantidad": 1},
])
print("  ✓ Hamburguesa clásica")

guardar_receta(id_ham_especial, [
    {"insumo_id": insumos_ids["Carne de res (presa 100g)"], "cantidad": 2},
    {"insumo_id": insumos_ids["Pan de hamburguesa"],        "cantidad": 1},
    {"insumo_id": insumos_ids["Queso tajada"],              "cantidad": 2},
    {"insumo_id": insumos_ids["Tomate"],                    "cantidad": 1},
    {"insumo_id": insumos_ids["Lechuga"],                   "cantidad": 1},
    {"insumo_id": insumos_ids["Salsa de tomate"],           "cantidad": 1},
    {"insumo_id": insumos_ids["Mayonesa"],                  "cantidad": 1},
    {"insumo_id": insumos_ids["Caja para hamburguesa"],     "cantidad": 1},
])
print("  ✓ Hamburguesa especial")

guardar_receta(id_perro, [
    {"insumo_id": insumos_ids["Salchicha"],            "cantidad": 1},
    {"insumo_id": insumos_ids["Pan de perro caliente"],"cantidad": 1},
    {"insumo_id": insumos_ids["Salsa de tomate"],      "cantidad": 1},
    {"insumo_id": insumos_ids["Mostaza"],              "cantidad": 1},
    {"insumo_id": insumos_ids["Papel de aluminio"],    "cantidad": 1},
])
print("  ✓ Perro clásico")

guardar_receta(id_perro_esp, [
    {"insumo_id": insumos_ids["Salchicha"],             "cantidad": 1},
    {"insumo_id": insumos_ids["Pan de perro caliente"], "cantidad": 1},
    {"insumo_id": insumos_ids["Queso tajada"],          "cantidad": 1},
    {"insumo_id": insumos_ids["Salsa de tomate"],       "cantidad": 1},
    {"insumo_id": insumos_ids["Mayonesa"],              "cantidad": 1},
    {"insumo_id": insumos_ids["Mostaza"],               "cantidad": 1},
    {"insumo_id": insumos_ids["Papel de aluminio"],     "cantidad": 1},
])
print("  ✓ Perro especial")

guardar_receta(id_papas, [
    {"insumo_id": insumos_ids["Papas a la francesa (200g)"], "cantidad": 1},
    {"insumo_id": insumos_ids["Salsa de tomate"],            "cantidad": 1},
    {"insumo_id": insumos_ids["Vaso desechable 16oz"],       "cantidad": 1},
])
print("  ✓ Papas clásicas")

guardar_receta(id_papas_qso, [
    {"insumo_id": insumos_ids["Papas a la francesa (200g)"], "cantidad": 1},
    {"insumo_id": insumos_ids["Queso tajada"],               "cantidad": 2},
    {"insumo_id": insumos_ids["Vaso desechable 16oz"],       "cantidad": 1},
])
print("  ✓ Papas con queso")

print("\n── Creando combos ──")

combos_data = [
    ("Combo 1 — Hamburguesa + Gaseosa",    13500, [
        {"producto_id": id_hamburguesa, "cantidad": 1},
        {"producto_id": id_gaseosa,     "cantidad": 1},
    ]),
    ("Combo 2 — Hamburguesa Esp + Gaseosa",17500, [
        {"producto_id": id_ham_especial,"cantidad": 1},
        {"producto_id": id_gaseosa,     "cantidad": 1},
    ]),
    ("Combo 3 — Perro + Papas + Gaseosa", 15000, [
        {"producto_id": id_perro,       "cantidad": 1},
        {"producto_id": id_papas,       "cantidad": 1},
        {"producto_id": id_gaseosa,     "cantidad": 1},
    ]),
    ("Combo 4 — Perro Esp + Papas Qso",   16500, [
        {"producto_id": id_perro_esp,   "cantidad": 1},
        {"producto_id": id_papas_qso,   "cantidad": 1},
        {"producto_id": id_gaseosa,     "cantidad": 1},
    ]),
    ("Combo Gamer — 2 Sobres + Gaseosa",  32000, [
        {"producto_id": id_gaseosa,     "cantidad": 1},
    ]),
]

from database import get_connection as _gc
for nombre, precio, productos in combos_data:
    _conn = _gc()
    _fila = _conn.execute("SELECT id FROM combos WHERE nombre = ?", (nombre,)).fetchone()
    _conn.close()
    if _fila:
        print(f"  ~ {nombre} ya existe (ID {_fila['id']})")
    else:
        cid = crear_combo(nombre, precio, productos)
        print(f"  ✓ {nombre} (ID {cid})")

# ══════════════════════════════════════════════════════════════════════════════
# PROVEEDORES
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Creando proveedores ──")
conn = get_connection()
conn.execute("""
    INSERT OR IGNORE INTO proveedores (nombre, contacto, telefono, email)
    VALUES (?, ?, ?, ?)
""", ("Distribuidora TCG Colombia", "Carlos Ruiz", "3001234567", "ventas@tcgcol.com"))
conn.execute("""
    INSERT OR IGNORE INTO proveedores (nombre, contacto, telefono, email)
    VALUES (?, ?, ?, ?)
""", ("Mayorista Juegos Ltda", "Ana Torres", "3109876543", "pedidos@mayoristajuegos.co"))
conn.commit()
conn.close()
print("  ✓ 2 proveedores creados")

# ══════════════════════════════════════════════════════════════════════════════
# CLIENTES
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Creando clientes ──")

clientes_data = [
    # (nombre, tipo_doc, documento, teléfono, email)
    ("Andrés Gamer",           "CC",  "1020334455", "3201112233", "andres@gamer.co"),
    ("Club de Cartas Bogotá",  "NIT", "900789012",  "3105556677", "clubcartas@bogota.co"),
    ("Laura Coleccionista",    "CC",  "1022334455", "3154445566", "laura@correo.com"),
    ("Torneos El G",           "NIT", "901234567",  "3001234567", None),
    ("Miguel Jugador",         "CC",  "1015998877", "3178889900", None),
]

clids = {}
for nombre, tipo_doc, documento, telefono, email in clientes_data:
    clid = obtener_o_crear_cliente(nombre, tipo_doc, documento, telefono, email)
    clids[nombre] = clid
    print(f"  ✓ {nombre} (ID {clid})")

# ══════════════════════════════════════════════════════════════════════════════
# CRÉDITOS
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Configurando créditos ──")
from modules.creditos import (
    migrar as migrar_creditos,
    set_limite_credito,
    registrar_abono,
    registrar_abono_masivo,
    get_saldo,
    get_cargos_pendientes,
)
from datetime import datetime, timedelta

migrar_creditos()

# Configurar límites de crédito
creditos_config = [
    ("Andrés Gamer",          300_000, 30),   # límite 300k, 30 días por compra
    ("Club de Cartas Bogotá", 600_000, 45),   # límite 600k, 45 días por compra
    ("Laura Coleccionista",   200_000, 30),   # límite 200k, 30 días por compra
    ("Torneos El G",          500_000, 60),   # límite 500k, 60 días por compra
]
for nombre, limite, dias in creditos_config:
    set_limite_credito(clids[nombre], limite, dias)
    print(f"  ✓ {nombre}: límite ${limite:,.0f} / {dias} días por compra")

# ── Insertar cargos con fechas controladas ────────────────────────────────────
print("\n── Registrando compras a crédito ──")
hoy = datetime.now()

conn = get_connection()

def _cargo(cliente_id, monto, dias_venc, descripcion, venta_id=None):
    """Inserta un cargo directamente con fecha de vencimiento controlada."""
    venc = (hoy + timedelta(days=dias_venc)).strftime("%Y-%m-%d")
    fecha = (hoy - timedelta(days=abs(min(dias_venc, 0)) + 2)).strftime("%Y-%m-%d %H:%M:%S") \
            if dias_venc < 0 else hoy.strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("""
        INSERT INTO creditos (cliente_id, tipo, monto, fecha, fecha_vencimiento, venta_id, notas)
        VALUES (?, 'cargo', ?, ?, ?, ?, ?)
    """, (cliente_id, monto, fecha, venc, venta_id, descripcion))
    return cur.lastrowid

# — Andrés Gamer —
# Compra 1: VENCIDA hace 10 días, pagada parcialmente ($30k de $80k)
c_andres_1 = _cargo(clids["Andrés Gamer"], 80_000, -10,
                    "Sobre Pokemon x5 + Sleeves Dragon Shield (100 uds)")
# Compra 2: vence en 20 días, sin pagos
c_andres_2 = _cargo(clids["Andrés Gamer"], 45_000, 20,
                    "Mazo Structure Yu-Gi-Oh Fire King")
# Compra 3: vence en 8 días, pagada completamente
c_andres_3 = _cargo(clids["Andrés Gamer"], 28_000, 8,
                    "Paquete cartas Pokemon x3 + dados")

# — Club de Cartas Bogotá —
# Compra 1: vence en 38 días, sin pagos (compra grande)
c_club_1 = _cargo(clids["Club de Cartas Bogotá"], 220_000, 38,
                  "Lote: 12 sobres Magic + 3 mazos Commander")
# Compra 2: VENCIDA hace 5 días (deuda vieja)
c_club_2 = _cargo(clids["Club de Cartas Bogotá"], 95_000, -5,
                  "6 sobres One Piece + playmat")

# — Laura Coleccionista —
# Una sola compra, la paga completa
c_laura_1 = _cargo(clids["Laura Coleccionista"], 120_000, 15,
                   "Catan edición base + Ticket to Ride")

# — Torneos El G —
# Compra reciente, sin pagos aún
c_torneos_1 = _cargo(clids["Torneos El G"], 180_000, 55,
                     "Premio torneo: 10 mazos Commander + accesorios")

conn.commit()
conn.close()

print(f"  ✓ Andrés Gamer: 3 compras (1 vencida, 1 al día, 1 reciente)")
print(f"  ✓ Club de Cartas Bogotá: 2 compras (1 vencida, 1 al día)")
print(f"  ✓ Laura Coleccionista: 1 compra")
print(f"  ✓ Torneos El G: 1 compra")

# ── Registrar abonos ──────────────────────────────────────────────────────────
print("\n── Registrando abonos ──")

# Andrés: pago parcial a la compra vencida ($30k de $80k)
registrar_abono(clids["Andrés Gamer"], 30_000,
                cargo_id=c_andres_1,
                metodo_pago="efectivo",
                notas="Pago parcial — queda pendiente $50k")
print(f"  ✓ Andrés: abono $30k a compra vencida #{c_andres_1} → quedan $50k")

# Andrés: pago completo de la compra 3 ($28k)
registrar_abono(clids["Andrés Gamer"], 28_000,
                cargo_id=c_andres_3,
                metodo_pago="nequi",
                notas="Pago completo")
print(f"  ✓ Andrés: pago completo $28k a compra #{c_andres_3} → SALDADA")

# Club: pago parcial a la compra vencida ($40k de $95k)
registrar_abono(clids["Club de Cartas Bogotá"], 40_000,
                cargo_id=c_club_2,
                metodo_pago="transferencia",
                notas="Abono parcial — transferencia bancaria")
print(f"  ✓ Club: abono $40k a compra vencida #{c_club_2} → quedan $55k")

# Laura: pago masivo que saldo TODO de una vez
ids_abonos = registrar_abono_masivo(clids["Laura Coleccionista"],
                                     120_000,
                                     metodo_pago="daviplata",
                                     notas="Pago total con Daviplata")
print(f"  ✓ Laura: pago masivo $120k → deuda saldada ({len(ids_abonos)} abono(s))")

# ── Verificación de saldos ────────────────────────────────────────────────────
print("\n── Verificando saldos finales ──")
verificaciones = [
    ("Andrés Gamer",          95_000),   # 50k (vencida) + 45k (al día)
    ("Club de Cartas Bogotá", 275_000),  # 220k (al día) + 55k (vencida parcial)
    ("Laura Coleccionista",   0),        # pagado todo
    ("Torneos El G",          180_000),  # sin pagos
]
ok_todos = True
for nombre, esperado in verificaciones:
    real = get_saldo(clids[nombre])
    estado = "✓" if abs(real - esperado) < 1 else "✗"
    print(f"  {estado} {nombre}: ${real:,.0f}  (esperado ${esperado:,.0f})")
    if abs(real - esperado) >= 1:
        ok_todos = False

pendientes_andres = get_cargos_pendientes(clids["Andrés Gamer"])
assert len(pendientes_andres) == 2, f"Andrés debe tener 2 compras pendientes, tiene {len(pendientes_andres)}"
vencidas_andres = [p for p in pendientes_andres if p["vencido"]]
assert len(vencidas_andres) == 1, "Andrés debe tener 1 compra vencida"
print(f"  ✓ Andrés: {len(pendientes_andres)} compras pendientes, {len(vencidas_andres)} vencida")

pendientes_club = get_cargos_pendientes(clids["Club de Cartas Bogotá"])
vencidas_club = [p for p in pendientes_club if p["vencido"]]
print(f"  ✓ Club: {len(pendientes_club)} compras pendientes, {len(vencidas_club)} vencida(s)")

assert get_cargos_pendientes(clids["Laura Coleccionista"]) == [], "Laura no debe tener pendientes"
print("  ✓ Laura: sin compras pendientes (todo pagado)")

# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN FINAL
# ══════════════════════════════════════════════════════════════════════════════
conn = get_connection()
n_prods    = conn.execute("SELECT COUNT(*) FROM productos  WHERE activo=1").fetchone()[0]
n_insumos  = conn.execute("SELECT COUNT(*) FROM insumos    WHERE activo=1").fetchone()[0]
n_combos   = conn.execute("SELECT COUNT(*) FROM combos     WHERE activo=1").fetchone()[0]
n_provs    = conn.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0]
n_usuarios = conn.execute("SELECT COUNT(*) FROM usuarios   WHERE activo=1").fetchone()[0]
n_clientes = conn.execute("SELECT COUNT(*) FROM clientes   WHERE activo=1").fetchone()[0]
n_cargos   = conn.execute("SELECT COUNT(*) FROM creditos   WHERE tipo='cargo'").fetchone()[0]
n_abonos   = conn.execute("SELECT COUNT(*) FROM creditos   WHERE tipo='abono'").fetchone()[0]
conn.close()

print(f"""
══════════════════════════════════════════
  Datos de prueba cargados exitosamente
══════════════════════════════════════════
  Productos:    {n_prods}
  Insumos:      {n_insumos}
  Combos:       {n_combos}
  Proveedores:  {n_provs}
  Usuarios:     {n_usuarios}
  Clientes:     {n_clientes}
  Cargos cred.: {n_cargos}
  Abonos:       {n_abonos}

  Cuentas de acceso:
    admin     / admin123
    vendedor1 / vend123
    vendedor2 / vend456
    cajero1   / caja123

  Escenarios de crédito cargados:
    Andrés Gamer        — $95.000 pendiente (1 compra VENCIDA)
    Club de Cartas Bog. — $275.000 pendiente (1 compra VENCIDA)
    Laura Coleccionista — $0 (deuda saldada, historial visible)
    Torneos El G        — $180.000 pendiente (al día)
══════════════════════════════════════════
{'  ✓ Todas las verificaciones pasaron' if ok_todos else '  ✗ Hay verificaciones fallidas'}
══════════════════════════════════════════
""")
