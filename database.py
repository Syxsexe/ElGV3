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
from paths import ruta_datos
DB_PATH = ruta_datos("elg_pos.db")


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

    # ── Clientes para facturación ────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT    NOT NULL,
            tipo_documento  TEXT    NOT NULL CHECK(tipo_documento IN ('CC','NIT','CE','TI','CONSUMIDOR_FINAL')),
            documento       TEXT    NOT NULL,
            direccion       TEXT,
            telefono        TEXT,
            email           TEXT,
            activo          INTEGER NOT NULL DEFAULT 1,
            creado_en       TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
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
    # metodo_pago: 'mixto' cuando se usan dos métodos, 'credito' para venta a crédito
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            total        REAL    NOT NULL CHECK(total >= 0),
            descuento    REAL             DEFAULT 0,
            metodo_pago  TEXT    NOT NULL DEFAULT 'efectivo'
                             CHECK(metodo_pago IN ('efectivo','transferencia','tarjeta','nequi','daviplata','mixto','credito')),
            tipo         TEXT    NOT NULL DEFAULT 'tienda'
                             CHECK(tipo IN ('tienda','cocina')),
            usuario_id   INTEGER NOT NULL REFERENCES usuarios(id),
            sesion_id    INTEGER          REFERENCES sesiones_caja(id),
            cliente_id   INTEGER          REFERENCES clientes(id),
            notas        TEXT
        )
    """)

    # ── Facturas y documentos fiscales ─────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id        INTEGER NOT NULL UNIQUE REFERENCES ventas(id) ON DELETE CASCADE,
            cliente_id      INTEGER REFERENCES clientes(id),
            numero          TEXT    NOT NULL UNIQUE,
            tipo_documento  TEXT    NOT NULL CHECK(tipo_documento IN ('CC','NIT','CE','TI','CONSUMIDOR_FINAL')),
            documento       TEXT    NOT NULL,
            direccion       TEXT,
            telefono        TEXT,
            email           TEXT,
            fecha           TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            total_base      REAL    NOT NULL DEFAULT 0,
            iva_porcentaje  REAL    NOT NULL DEFAULT 0,
            iva             REAL    NOT NULL DEFAULT 0,
            total           REAL    NOT NULL DEFAULT 0,
            notas           TEXT
        )
    """)

    # ── Pagos de venta (detalle cuando hay pago mixto) ────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pagos_venta (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id    INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
            metodo      TEXT    NOT NULL
                            CHECK(metodo IN ('efectivo','transferencia','tarjeta','nequi','daviplata','credito')),
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

    # ── Documentos comerciales ────────────────────────────────────────────────
    # Cotizaciones, órdenes de pedido y remisiones (documentos previos/paralelos
    # a la venta). Comparten estructura cabecera + ítems.
    #   tipo:   'cotizacion' | 'orden_pedido' | 'remision'
    #   estado: vigente | aceptada | rechazada | facturada | entregada | anulada
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos_comerciales (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo           TEXT    NOT NULL CHECK(tipo IN ('cotizacion','orden_pedido','remision')),
            numero         TEXT    NOT NULL UNIQUE,
            cliente_id     INTEGER REFERENCES clientes(id),
            fecha          TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            vigencia       TEXT,
            estado         TEXT    NOT NULL DEFAULT 'vigente'
                               CHECK(estado IN ('vigente','aceptada','rechazada',
                                                'facturada','entregada','anulada')),
            subtotal       REAL    NOT NULL DEFAULT 0,
            descuento      REAL             DEFAULT 0,
            iva_porcentaje REAL             DEFAULT 0,
            iva            REAL             DEFAULT 0,
            total          REAL    NOT NULL DEFAULT 0,
            usuario_id     INTEGER NOT NULL REFERENCES usuarios(id),
            venta_id       INTEGER REFERENCES ventas(id),
            doc_origen_id  INTEGER REFERENCES documentos_comerciales(id),
            notas          TEXT
        )
    """)

    # ── Ítems de documentos comerciales ───────────────────────────────────────
    # producto_id/combo_id pueden ser NULL para ítems de texto libre.
    # descripcion guarda el nombre "snapshot" al momento de crear el documento.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documento_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_id INTEGER NOT NULL REFERENCES documentos_comerciales(id) ON DELETE CASCADE,
            producto_id  INTEGER          REFERENCES productos(id),
            combo_id     INTEGER          REFERENCES combos(id),
            descripcion  TEXT    NOT NULL,
            cantidad     REAL    NOT NULL CHECK(cantidad > 0),
            precio_unit  REAL    NOT NULL,
            subtotal     REAL    NOT NULL
        )
    """)

    # ── Torneos ───────────────────────────────────────────────────────────────
    # Registra un torneo de TCG: el dinero recaudado entre los jugadores (ingreso)
    # y los sobres/productos entregados como premio (salen del inventario). Así el
    # stock queda correcto y la ganancia = recaudado − costo de los premios.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS torneos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT    NOT NULL,
            juego         TEXT,
            fecha         TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            num_jugadores INTEGER          DEFAULT 0,
            recaudado     REAL    NOT NULL DEFAULT 0,
            costo_premios REAL    NOT NULL DEFAULT 0,
            ganancia      REAL    NOT NULL DEFAULT 0,
            usuario_id    INTEGER          REFERENCES usuarios(id),
            sesion_id     INTEGER          REFERENCES sesiones_caja(id),
            venta_id      INTEGER          REFERENCES ventas(id),
            notas         TEXT
        )
    """)

    # ── Participantes / inscripciones de cada torneo ──────────────────────────
    # Cada jugador es una inscripción con su monto y método de pago. Si el método
    # es 'credito' queda ligado a un cliente (cargo en la tabla creditos) para
    # poder cobrarlo después, igual que se hacía con el "item de torneo" por jugador.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS torneo_participantes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            torneo_id   INTEGER NOT NULL REFERENCES torneos(id) ON DELETE CASCADE,
            cliente_id  INTEGER          REFERENCES clientes(id),
            nombre      TEXT    NOT NULL,
            monto       REAL    NOT NULL DEFAULT 0,
            metodo_pago TEXT    NOT NULL DEFAULT 'efectivo',
            cargo_id    INTEGER
        )
    """)

    # ── Premios entregados en cada torneo (salidas de inventario) ─────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS torneo_premios (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            torneo_id      INTEGER NOT NULL REFERENCES torneos(id) ON DELETE CASCADE,
            producto_id    INTEGER NOT NULL REFERENCES productos(id),
            nombre         TEXT    NOT NULL,
            cantidad       REAL    NOT NULL CHECK(cantidad > 0),
            costo_unit     REAL    NOT NULL DEFAULT 0,
            subtotal_costo REAL    NOT NULL DEFAULT 0
        )
    """)

    # ── Preparaciones (producción de cocina) ──────────────────────────────────
    # Una preparación es un insumo que se FABRICA a partir de otros insumos
    # (crudos y/o otras preparaciones): rellenos, salsas, masa, adobo, etc.
    # 'rendimiento' es cuánto produce un lote (en la unidad del insumo).
    # Marca qué insumos son preparaciones y guarda el rendimiento por lote.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS preparaciones (
            insumo_id    INTEGER PRIMARY KEY REFERENCES insumos(id) ON DELETE CASCADE,
            rendimiento  REAL    NOT NULL DEFAULT 0
        )
    """)

    # ── Receta de cada preparación (qué consume un lote) ──────────────────────
    # preparacion_id → insumo que se produce; insumo_id → componente que consume.
    # Al "preparar un lote" se descuenta cada componente y sube el stock de la
    # preparación en 'rendimiento'. Permite anidar (una preparación como adobo
    # puede ser componente de otra como el filete apanado).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receta_preparacion (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            preparacion_id INTEGER NOT NULL REFERENCES insumos(id) ON DELETE CASCADE,
            insumo_id      INTEGER NOT NULL REFERENCES insumos(id) ON DELETE CASCADE,
            cantidad       REAL    NOT NULL CHECK(cantidad > 0),
            UNIQUE(preparacion_id, insumo_id)
        )
    """)

    # ── Historial de producción (lotes preparados) ────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS producciones (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            preparacion_id    INTEGER NOT NULL REFERENCES insumos(id),
            num_lotes         REAL    NOT NULL CHECK(num_lotes > 0),
            rendimiento_total REAL    NOT NULL DEFAULT 0,
            usuario_id        INTEGER          REFERENCES usuarios(id),
            fecha             TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            notas             TEXT
        )
    """)

    # Asegura columna cliente_id en ventas para versiones previas de la base de datos.
    columnas_ventas = [row[1] for row in conn.execute("PRAGMA table_info(ventas)").fetchall()]
    if "cliente_id" not in columnas_ventas:
        conn.execute("ALTER TABLE ventas ADD COLUMN cliente_id INTEGER REFERENCES clientes(id)")

    # Columnas fiscales para clientes (backward compatibility)
    columnas_clientes = [row[1] for row in conn.execute("PRAGMA table_info(clientes)").fetchall()]
    fiscal_cols = {
        "regimen": "TEXT",
        "responsabilidad_fiscal": "TEXT",
        "municipio": "TEXT",
    }
    for col, tipo in fiscal_cols.items():
        if col not in columnas_clientes:
            conn.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")

    # Columnas DIAN para facturas (backward compatibility)
    columnas_facturas = [row[1] for row in conn.execute("PRAGMA table_info(facturas)").fetchall()]
    factura_cols = {
        "dian_status": "TEXT DEFAULT 'pendiente'",
        "dian_cufe": "TEXT",
        "dian_qr": "TEXT",
        "dian_uuid": "TEXT",
        "dian_mensaje": "TEXT",
        "dian_fecha_transmision": "TEXT",
    }
    for col, tipo in factura_cols.items():
        col_name = col.split()[0]  # extract column name before any DEFAULT
        if col_name not in columnas_facturas:
            conn.execute(f"ALTER TABLE facturas ADD COLUMN {col} {tipo}")

    conn.commit()
    conn.close()

    # Migración en conexión separada (evita conflictos de transacción implícita)
    _migrar_metodo_credito()


def _migrar_metodo_credito():
    """
    Recrea ventas y pagos_venta para incluir 'credito' en sus CHECK constraints.
    Usa conexión propia con isolation_level=None (autocommit) para control
    total del ciclo de vida de la transacción DDL.
    """
    import sqlite3 as _sq3
    conn = _sq3.connect(str(DB_PATH), isolation_level=None)
    conn.row_factory = _sq3.Row
    try:
        schema_v = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='ventas'"
        ).fetchone()
        if not schema_v or "'credito'" in schema_v[0]:
            return  # Ya migrado o tabla no existe todavía

        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        # ── ventas ────────────────────────────────────────────────────────────
        conn.execute("ALTER TABLE ventas RENAME TO _ventas_bk")
        conn.execute("""
            CREATE TABLE ventas (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                total        REAL    NOT NULL CHECK(total >= 0),
                descuento    REAL             DEFAULT 0,
                metodo_pago  TEXT    NOT NULL DEFAULT 'efectivo'
                                 CHECK(metodo_pago IN ('efectivo','transferencia','tarjeta','nequi','daviplata','mixto','credito')),
                tipo         TEXT    NOT NULL DEFAULT 'tienda'
                                 CHECK(tipo IN ('tienda','cocina')),
                usuario_id   INTEGER NOT NULL REFERENCES usuarios(id),
                sesion_id    INTEGER          REFERENCES sesiones_caja(id),
                cliente_id   INTEGER          REFERENCES clientes(id),
                notas        TEXT
            )
        """)
        conn.execute("INSERT INTO ventas SELECT * FROM _ventas_bk")
        conn.execute("DROP TABLE _ventas_bk")

        # ── pagos_venta ───────────────────────────────────────────────────────
        conn.execute("ALTER TABLE pagos_venta RENAME TO _pagos_venta_bk")
        conn.execute("""
            CREATE TABLE pagos_venta (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id    INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
                metodo      TEXT    NOT NULL
                                CHECK(metodo IN ('efectivo','transferencia','tarjeta','nequi','daviplata','credito')),
                monto       REAL    NOT NULL CHECK(monto > 0)
            )
        """)
        conn.execute("INSERT INTO pagos_venta SELECT * FROM _pagos_venta_bk")
        conn.execute("DROP TABLE _pagos_venta_bk")

        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
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