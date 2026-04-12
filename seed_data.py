"""
seed_data.py — El G POS
Carga datos de prueba realistas para probar el sistema.
Ejecutar UNA sola vez después de inicializar la base de datos vacía:
    python seed_data.py
"""

from database import inicializar, get_connection
from auth import iniciar_sesion
from modules.inventario import (
    listar_categorias, crear_producto, crear_insumo, guardar_receta
)

def crear_o_obtener_producto(nombre, categoria_id, precio_venta,
                              precio_costo=0, stock=0, stock_minimo=0, codigo=None):
    """Crea el producto si no existe (por código o nombre), si ya existe retorna su ID."""
    from database import get_connection
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
    """Crea el insumo si no existe, si ya existe retorna su ID."""
    from database import get_connection
    conn = get_connection()
    fila = conn.execute("SELECT id FROM insumos WHERE nombre = ?", (nombre,)).fetchone()
    conn.close()
    if fila:
        return fila["id"]
    return crear_insumo(nombre, stock, unidad, stock_minimo)
from modules.ventas import crear_combo
from modules.cuentas import migrar as migrar_cuentas

# ── Inicializar ───────────────────────────────────────────────────────────────
inicializar()
migrar_cuentas()
iniciar_sesion("admin", "admin123")

cats = {c["nombre"]: c["id"] for c in listar_categorias()}
print("\n── Creando productos de tienda ──")

# ── TCG — Sobres ──────────────────────────────────────────────────────────────
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

# ── TCG — Mazos ───────────────────────────────────────────────────────────────
mazos = [
    ("Mazo Pokemon Ex Starter — Meowscarada", "PKM-EX-001", 65000, 42000, 6, 2),
    ("Mazo Pokemon Ex Starter — Skeledirge",  "PKM-EX-002", 65000, 42000, 6, 2),
    ("Mazo Commander Magic — Chaos Incarnate","MTG-CMD-01", 85000, 55000, 4, 1),
    ("Mazo Structure Yu-Gi-Oh! Fire King",    "YGO-STR-01", 35000, 20000, 8, 2),
]
for nombre, codigo, pv, pc, stock, minimo in mazos:
    pid = crear_o_obtener_producto(nombre, cats["TCG - Mazos"], pv, pc, stock, minimo, codigo)
    print(f"  ✓ {nombre} (ID {pid})")

# ── TCG — Paquetes de cartas sueltas ─────────────────────────────────────────
paquetes = [
    ("Paquete 5 cartas Pokemon comunes",   "PKM-PKT-C", 3000,  1500, 50, 10),
    ("Paquete 5 cartas Pokemon poco com.", "PKM-PKT-U", 5000,  2500, 40, 10),
    ("Paquete 5 cartas Magic comunes",     "MTG-PKT-C", 4000,  2000, 40,  8),
    ("Paquete 5 cartas Yu-Gi-Oh comunes",  "YGO-PKT-C", 3000,  1500, 50, 10),
]
for nombre, codigo, pv, pc, stock, minimo in paquetes:
    pid = crear_o_obtener_producto(nombre, cats["TCG - Paquetes cartas"], pv, pc, stock, minimo, codigo)
    print(f"  ✓ {nombre} (ID {pid})")

# ── Accesorios TCG ────────────────────────────────────────────────────────────
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

# ── Juegos de mesa ────────────────────────────────────────────────────────────
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

# ── Insumos de cocina ─────────────────────────────────────────────────────────
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
    ("Salsa de tomate",            50, "porción",   10),
    ("Mayonesa",                   50, "porción",   10),
    ("Mostaza",                    50, "porción",   10),
    ("Gaseosa lata",               48, "unidad",   12),
    ("Agua botella 600ml",         24, "unidad",    6),
    ("Jugo Hit",                   24, "unidad",    6),
    ("Vaso desechable 16oz",      100, "unidad",   20),
    ("Caja para hamburguesa",      50, "unidad",   10),
    ("Papel de aluminio",         100, "porción",   20),
]
insumos_ids = {}
for nombre, stock, unidad, minimo in insumos_data:
    iid = crear_o_obtener_insumo(nombre, stock, unidad, minimo)
    insumos_ids[nombre] = iid
    print(f"  ✓ {nombre} (ID {iid})")

# ── Productos de cocina (terminados) ──────────────────────────────────────────
print("\n── Creando productos de cocina ──")

def prod_cocina(nombre, codigo, pv, pc):
    return crear_o_obtener_producto(nombre, cats["Comidas rápidas"], pv, pc, 0, 0, codigo)

id_hamburguesa  = prod_cocina("Hamburguesa clásica",         "COM-HAM-CL", 12000, 5500)
id_ham_especial = prod_cocina("Hamburguesa especial",        "COM-HAM-ES", 15000, 7000)
id_perro        = prod_cocina("Perro caliente clásico",      "COM-PER-CL",  8000, 3500)
id_perro_esp    = prod_cocina("Perro caliente especial",     "COM-PER-ES", 10000, 4500)
id_papas        = prod_cocina("Papas a la francesa",         "COM-PAP-FR",  5000, 1800)
id_papas_qso    = prod_cocina("Papas con queso",             "COM-PAP-QS",  7000, 2800)

for nombre in ["Hamburguesa clásica", "Hamburguesa especial", "Perro caliente clásico",
               "Perro caliente especial", "Papas a la francesa", "Papas con queso"]:
    print(f"  ✓ {nombre}")

# ── Bebidas (como productos con stock propio) ─────────────────────────────────
id_gaseosa = crear_o_obtener_producto("Gaseosa lata",      cats["Bebidas"], 4000, 2000, 48, 12, "BEB-GAS-LT")
id_agua    = crear_o_obtener_producto("Agua 600ml",         cats["Bebidas"], 2500, 1200, 24,  6, "BEB-AGU-60")
id_jugo    = crear_o_obtener_producto("Jugo Hit",           cats["Bebidas"], 3500, 1800, 24,  6, "BEB-JUI-HT")
print(f"  ✓ Bebidas creadas")

# ── Recetas ───────────────────────────────────────────────────────────────────
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
    {"insumo_id": insumos_ids["Salchicha"],           "cantidad": 1},
    {"insumo_id": insumos_ids["Pan de perro caliente"],"cantidad": 1},
    {"insumo_id": insumos_ids["Salsa de tomate"],     "cantidad": 1},
    {"insumo_id": insumos_ids["Mostaza"],             "cantidad": 1},
    {"insumo_id": insumos_ids["Papel de aluminio"],   "cantidad": 1},
])
print("  ✓ Perro clásico")

guardar_receta(id_perro_esp, [
    {"insumo_id": insumos_ids["Salchicha"],            "cantidad": 1},
    {"insumo_id": insumos_ids["Pan de perro caliente"],"cantidad": 1},
    {"insumo_id": insumos_ids["Queso tajada"],         "cantidad": 1},
    {"insumo_id": insumos_ids["Salsa de tomate"],      "cantidad": 1},
    {"insumo_id": insumos_ids["Mayonesa"],             "cantidad": 1},
    {"insumo_id": insumos_ids["Mostaza"],              "cantidad": 1},
    {"insumo_id": insumos_ids["Papel de aluminio"],    "cantidad": 1},
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

# ── Combos ────────────────────────────────────────────────────────────────────
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
        cid = _fila["id"]
        print(f"  ~ {nombre} ya existe (ID {cid})")
    else:
        cid = crear_combo(nombre, precio, productos)
        print(f"  ✓ {nombre} (ID {cid})")

# ── Proveedor de ejemplo ──────────────────────────────────────────────────────
print("\n── Creando proveedor de ejemplo ──")
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

# ── Resumen final ─────────────────────────────────────────────────────────────
conn = get_connection()
n_prods    = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1").fetchone()[0]
n_insumos  = conn.execute("SELECT COUNT(*) FROM insumos  WHERE activo=1").fetchone()[0]
n_combos   = conn.execute("SELECT COUNT(*) FROM combos   WHERE activo=1").fetchone()[0]
n_provs    = conn.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0]
conn.close()

print(f"""
══════════════════════════════════════════
  Datos de prueba cargados exitosamente
══════════════════════════════════════════
  Productos:    {n_prods}
  Insumos:      {n_insumos}
  Combos:       {n_combos}
  Proveedores:  {n_provs}

  Usuario: admin
  Clave:   admin123
══════════════════════════════════════════
""")
