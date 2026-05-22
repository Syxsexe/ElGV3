"""
database.py — El G POS
Gestión de la base de datos SQLite local.
Crea todas las tablas si no existen y provee la conexión centralizada.
"""

import sqlite3
import hashlib
import os
from pathlib import Path

# ── Ruta de la base de datos ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "elg_pos.db"


# ── Conexión ──────────────────────────────────────────────────────────────────
def get_connection() -> sqlite3.Connection:
    """Retorna una conexión con soporte a claves foráneas activado."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # acceso por nombre de columna
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Creación de tablas ────────────────────────────────────────────────────────
def crear_tablas():
    conn = get_connection()
    cur  = conn.cursor()

    # ── Usuarios ──────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario          TEXT    NOT NULL UNIQUE,
            contrasena_hash  TEXT    NOT NULL,
            rol              TEXT    NOT NULL CHECK(rol IN ('admin', 'vendedor')),
            activo           INTEGER NOT NULL DEFAULT 1,
            creado_en        TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Categorías ────────────────────────────────────────────────────────────
    # tipo: 'tienda' (TCG, juegos, accesorios) | 'cocina' (comidas rápidas)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre  TEXT    NOT NULL UNIQUE,
            tipo    TEXT    NOT NULL CHECK(tipo IN ('tienda', 'cocina'))
        )
    """)

    # ── Productos de tienda ───────────────────────────────────────────────────
    # Cubre: sobres TCG, mazos, accesorios, juegos de mesa,
    #        paquetes de cartas sueltas (5 cartas x $3000)
    #        y productos terminados de cocina (hamburguesa, perro, etc.)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT    NOT NULL,
            codigo        TEXT    UNIQUE,
            precio_venta  REAL    NOT NULL CHECK(precio_venta >= 0),
            precio_costo  REAL             DEFAULT 0,
            stock         REAL    NOT NULL DEFAULT 0,
            stock_minimo  REAL             DEFAULT 0,
            categoria_id  INTEGER NOT NULL REFERENCES categorias(id),
            activo        INTEGER NOT NULL DEFAULT 1,
            creado_en     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Insumos de cocina ─────────────────────────────────────────────────────
    # Son ingredientes (no se venden directos): carne, pan, papas, gaseosa, etc.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS insumos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT    NOT NULL UNIQUE,
            stock         REAL    NOT NULL DEFAULT 0,
            unidad        TEXT    NOT NULL DEFAULT 'unidad',  -- unidad, gramos, ml, etc.
            stock_minimo  REAL             DEFAULT 0,
            activo        INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Receta de insumos por producto de cocina ──────────────────────────────
    # Vincula un producto terminado (hamburguesa) con los insumos que consume.
    # Al registrar la venta se descuenta stock de cada insumo.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receta_insumos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id  INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
            insumo_id    INTEGER NOT NULL REFERENCES insumos(id)   ON DELETE CASCADE,
            cantidad     REAL    NOT NULL CHECK(cantidad > 0),
            UNIQUE(producto_id, insumo_id)
        )
    """)

    # ── Combos ────────────────────────────────────────────────────────────────
    # Un combo agrupa varios productos con precio especial.
    # Puede mezclar tienda + cocina (ej. juego de mesa + bebida).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS combos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre       TEXT    NOT NULL UNIQUE,
            precio       REAL    NOT NULL CHECK(precio >= 0),
            descripcion  TEXT,
            activo       INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Productos que componen cada combo ─────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS combo_productos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            combo_id    INTEGER NOT NULL REFERENCES combos(id)    ON DELETE CASCADE,
            producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
            cantidad    REAL    NOT NULL DEFAULT 1,
            UNIQUE(combo_id, producto_id)
        )
    """)

    # ── Proveedores ───────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS proveedores (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT    NOT NULL UNIQUE,
            contacto  TEXT,
            telefono  TEXT,
            email     TEXT,
            activo    INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Pedidos a proveedores ─────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_id  INTEGER NOT NULL REFERENCES proveedores(id),
            fecha         TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            estado        TEXT    NOT NULL DEFAULT 'pendiente'
                              CHECK(estado IN ('pendiente','recibido','cancelado')),
            total         REAL             DEFAULT 0,
            notas         TEXT
        )
    """)

    # ── Detalle de pedidos ────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detalle_pedido (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id   INTEGER NOT NULL REFERENCES pedidos(id)   ON DELETE CASCADE,
            producto_id INTEGER          REFERENCES productos(id),
            insumo_id   INTEGER          REFERENCES insumos(id),
            cantidad    REAL    NOT NULL CHECK(cantidad > 0),
            precio_unit REAL    NOT NULL DEFAULT 0
        )
    """)

    # ── Sesiones de caja ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_caja (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id       INTEGER NOT NULL REFERENCES usuarios(id),
            apertura         TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            cierre           TEXT,
            monto_base         REAL    NOT NULL DEFAULT 0,
            monto_base_digital REAL             DEFAULT 0,
            total_ventas       REAL             DEFAULT 0,
            total_efectivo     REAL             DEFAULT 0,
            total_digital      REAL             DEFAULT 0,
            monto_cierre       REAL,
            monto_cierre_digital REAL,
            diferencia         REAL,
            diferencia_digital REAL,
            notas              TEXT
        )
    """)

    # ── Denominaciones de caja (billetes y monedas al cerrar) ─────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS denominaciones_caja (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_id   INTEGER NOT NULL REFERENCES sesiones_caja(id) ON DELETE CASCADE,
            denominacion INTEGER NOT NULL,   -- 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000
            cantidad    INTEGER NOT NULL DEFAULT 0,
            subtotal    REAL    NOT NULL DEFAULT 0
        )
    """)

    # ── Ventas ────────────────────────────────────────────────────────────────
    # metodo_pago: 'mixto' cuando se usan dos métodos a la vez
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            total        REAL    NOT NULL CHECK(total >= 0),
            descuento    REAL             DEFAULT 0,
            metodo_pago  TEXT    NOT NULL DEFAULT 'efectivo'
                             CHECK(metodo_pago IN ('efectivo','transferencia','tarjeta','nequi','daviplata','mixto')),
            tipo         TEXT    NOT NULL DEFAULT 'tienda'
                             CHECK(tipo IN ('tienda','cocina')),
            usuario_id   INTEGER NOT NULL REFERENCES usuarios(id),
            sesion_id    INTEGER          REFERENCES sesiones_caja(id),
            notas        TEXT
        )
    """)

    # ── Pagos de venta (detalle cuando hay pago mixto) ────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pagos_venta (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id    INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
            metodo      TEXT    NOT NULL
                            CHECK(metodo IN ('efectivo','transferencia','tarjeta','nequi','daviplata')),
            monto       REAL    NOT NULL CHECK(monto > 0)
        )
    """)

    # ── Detalle de ventas ─────────────────────────────────────────────────────
    # Un ítem puede ser producto suelto O un combo completo.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detalle_venta (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id     INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
            producto_id  INTEGER          REFERENCES productos(id),
            combo_id     INTEGER          REFERENCES combos(id),
            cantidad     REAL    NOT NULL CHECK(cantidad > 0),
            precio_unit  REAL    NOT NULL,
            subtotal     REAL    NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ── Datos iniciales ───────────────────────────────────────────────────────────
def insertar_datos_iniciales():
    """
    Inserta datos de ejemplo solo si las tablas están vacías.
    Incluye: usuario admin, categorías base y denominaciones COP.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # Admin por defecto (contraseña: admin123)
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if cur.fetchone()[0] == 0:
        hash_pw = hashlib.sha256("admin123".encode()).hexdigest()
        cur.execute("""
            INSERT INTO usuarios (usuario, contrasena_hash, rol)
            VALUES (?, ?, 'admin')
        """, ("admin", hash_pw))
        print("✓ Usuario admin creado (contraseña: admin123)")

    # Categorías base
    cur.execute("SELECT COUNT(*) FROM categorias")
    if cur.fetchone()[0] == 0:
        categorias_base = [
            # tienda
            ("TCG - Sobres",           "tienda"),
            ("TCG - Mazos",            "tienda"),
            ("TCG - Paquetes cartas",  "tienda"),
            ("Accesorios TCG",         "tienda"),
            ("Juegos de mesa",         "tienda"),
            # cocina
            ("Comidas rápidas",        "cocina"),
            ("Bebidas",                "cocina"),
            ("Combos cocina",          "cocina"),
        ]
        cur.executemany(
            "INSERT INTO categorias (nombre, tipo) VALUES (?, ?)",
            categorias_base
        )
        print(f"✓ {len(categorias_base)} categorías creadas")

    conn.commit()
    conn.close()


# ── Utilidades ────────────────────────────────────────────────────────────────
def hash_contrasena(contrasena: str) -> str:
    return hashlib.sha256(contrasena.encode()).hexdigest()


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    return hash_contrasena(contrasena) == hash_guardado


def obtener_version_db() -> str:
    """Retorna la versión de SQLite instalada."""
    conn = get_connection()
    version = conn.execute("SELECT sqlite_version()").fetchone()[0]
    conn.close()
    return version


# ── Inicialización ────────────────────────────────────────────────────────────
def inicializar():
    """Punto de entrada: crea tablas e inserta datos iniciales."""
    crear_tablas()
    insertar_datos_iniciales()
    print(f"✓ Base de datos lista en: {DB_PATH}")
    print(f"✓ SQLite versión: {obtener_version_db()}")


# ── Ejecución directa ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    inicializar()