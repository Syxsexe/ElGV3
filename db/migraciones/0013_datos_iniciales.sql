-- 0013_datos_iniciales.sql — Catálogos fijos con los que arranca el sistema.
-- Categorías, productos, clientes y usuarios reales llegan con la migración de
-- datos desde SQLite; los datos del negocio (tabla empresa) en su configuración.

-- ── Usuarios: roles y permisos ──────────────────────────────────────────────

INSERT INTO roles (nombre, descripcion) VALUES
    ('admin',    'Administrador: todos los permisos'),
    ('vendedor', 'Cajero o vendedor: opera ventas, cuentas y caja');

INSERT INTO permisos (codigo, descripcion) VALUES
    ('inventario.editar',    'Crear y editar productos, insumos y categorías'),
    ('combos.editar',        'Crear y editar combos'),
    ('preparaciones.editar', 'Editar recetas de preparaciones'),
    ('caja.historial',       'Ver el historial de turnos de caja'),
    ('gastos.anular',        'Anular egresos'),
    ('usuarios.gestionar',   'Crear, editar y desactivar usuarios'),
    ('auditoria.ver',        'Ver la bitácora de auditoría'),
    ('creditos.condonar',    'Condonar deuda de fiado');

INSERT INTO rol_permisos (rol_id, permiso_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permisos p WHERE r.nombre = 'admin';

-- ── Terceros ────────────────────────────────────────────────────────────────

INSERT INTO tipos_identificacion (codigo, nombre) VALUES
    ('11', 'Registro civil'),
    ('12', 'Tarjeta de identidad'),
    ('13', 'Cédula de ciudadanía'),
    ('21', 'Tarjeta de extranjería'),
    ('22', 'Cédula de extranjería'),
    ('31', 'NIT'),
    ('41', 'Pasaporte'),
    ('42', 'Documento de identificación extranjero'),
    ('47', 'PEP (Permiso Especial de Permanencia)'),
    ('48', 'PPT (Permiso por Protección Temporal)'),
    ('50', 'NIT de otro país'),
    ('91', 'NUIP');

INSERT INTO responsabilidades_fiscales (codigo, descripcion) VALUES
    ('O-13',    'Gran contribuyente'),
    ('O-15',    'Autorretenedor'),
    ('O-23',    'Agente de retención IVA'),
    ('O-47',    'Régimen simple de tributación'),
    ('R-99-PN', 'No aplica – Otros');

-- Adquiriente genérico de la DIAN para ventas sin cliente identificado.
INSERT INTO terceros (tipo_persona, nombre, tipo_identificacion_id, numero_identificacion)
SELECT 'natural', 'CONSUMIDOR FINAL', id, '222222222222'
  FROM tipos_identificacion WHERE codigo = '13';

-- ── Catálogo ────────────────────────────────────────────────────────────────

INSERT INTO unidades_medida (simbolo, nombre) VALUES
    ('g',   'Gramos'),
    ('ml',  'Mililitros'),
    ('und', 'Unidades');

-- El negocio es no responsable de IVA: estos impuestos clasifican cada
-- artículo para cuando se discriminen (empresa / factura electrónica).
INSERT INTO impuestos (codigo, nombre, tributo, tarifa) VALUES
    ('IVA19',       'IVA 19%',                       'IVA', 19),
    ('INC8',        'Impuesto al consumo 8%',        'INC',  8),
    ('IVA0-EXENTO', 'IVA exento (servicio exento)',  'IVA',  0);

INSERT INTO categorias (nombre, tipo) VALUES ('Torneos', 'tienda');

WITH articulo AS (
    INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta)
    SELECT 'servicio', 'Inscripción a torneo', c.id, i.id, 15000
      FROM categorias c, impuestos i
     WHERE c.nombre = 'Torneos' AND i.codigo = 'IVA0-EXENTO'
    RETURNING id
)
INSERT INTO servicios (articulo_id) SELECT id FROM articulo;

-- ── Caja ────────────────────────────────────────────────────────────────────

INSERT INTO cajas (nombre, usa_denominaciones) VALUES
    ('Efectivo', true),
    ('Digital',  false);

INSERT INTO metodos_pago (codigo, nombre, caja_id)
SELECT m.codigo, m.nombre, c.id
  FROM (VALUES ('efectivo',      'Efectivo',      'Efectivo'),
               ('nequi',         'Nequi',         'Digital'),
               ('daviplata',     'Daviplata',     'Digital'),
               ('transferencia', 'Transferencia', 'Digital'),
               ('tarjeta',       'Tarjeta',       'Digital')) AS m (codigo, nombre, caja)
  JOIN cajas c ON c.nombre = m.caja;

INSERT INTO denominaciones (valor, tipo) VALUES
    (50, 'moneda'), (100, 'moneda'), (200, 'moneda'), (500, 'moneda'), (1000, 'moneda'),
    (2000, 'billete'), (5000, 'billete'), (10000, 'billete'),
    (20000, 'billete'), (50000, 'billete'), (100000, 'billete');

-- ── Mesas, gastos y torneos ─────────────────────────────────────────────────

INSERT INTO mesas (nombre) SELECT n::text FROM generate_series(1, 16) AS n;

INSERT INTO categorias_gasto (nombre) VALUES
    ('Nómina'), ('Arriendo'), ('Servicios públicos'), ('Aseo y utensilios'),
    ('Envíos y domicilios'), ('Mantenimiento'), ('Publicidad'), ('Otros');

INSERT INTO juegos (nombre) VALUES
    ('MTG'), ('Yu-Gi-Oh!'), ('Riftbound'), ('Torneo genérico');
