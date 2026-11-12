# El G — POS web

Punto de venta de **El G** (tienda de TCG, juegos de mesa y comidas rápidas) en
versión web, para usarlo desde celulares y PCs en la red local del negocio.

La app de escritorio (Tkinter) quedó fuera de esta rama; sigue en el historial
de git hasta el commit anterior a la limpieza.

## Estructura

| Carpeta / archivo | Qué es |
|---|---|
| `web/` | Frontend React + Vite |
| `pos_api/` | API FastAPI que usa el frontend (puerto 8100), sobre la base Postgres de `db/` |
| `db/` | Esquema Postgres 18 (migraciones SQL numeradas) y sus pruebas |
| `backend/` | Servicio de facturación electrónica DIAN (FastAPI + Postgres, adaptador Matias) |
| `tests/` | Pruebas del backend DIAN (CUFE, QR, XML UBL 2.1, servidor mock) |

## Desarrollo

API (desde la raíz del repo). La base va primero: ver "Base de datos Postgres".

```bash
python -m venv .venv
.venv/bin/pip install -r pos_api/requirements.txt
export ELG_DATABASE_URL=postgresql://elg:elg@localhost:5433/elg
DATABASE_URL=$ELG_DATABASE_URL .venv/bin/python db/migrar.py   # migraciones pendientes
.venv/bin/python -m pos_api.configurar                           # solo la primera vez
.venv/bin/uvicorn pos_api.main:app --reload --port 8100
```

`pos_api.configurar` pide los datos del negocio (NIT, nombre, municipio,
régimen) y crea el primer usuario administrador; se niega si la base ya tiene
usuarios. La API no arranca si faltan migraciones.

Variables de entorno: `ELG_DATABASE_URL`, `ELG_JWT_SECRET`, `ELG_JWT_EXP_HORAS`,
`ELG_CORS_ORIGINS` y `ELG_ZONA_HORARIA` (por defecto `America/Bogota`). El panel admin del backend DIAN inicia sesión con los
usuarios de esta base (permiso `usuarios.gestionar`) si tiene `ELG_DATABASE_URL`
en su `.env`.

Frontend:

```bash
cd web
npm install
VITE_API_BASE=http://localhost:8100 npm run dev
```

Pruebas del backend DIAN:

```bash
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest tests
```

## Base de datos Postgres (`db/`)

El modelo relacional (63 tablas, Postgres 18) vive en `db/migraciones/` como
archivos SQL numerados. No hay migración de datos desde la versión SQLite: el
negocio se carga desde cero en la app.

```bash
db/pg_local.sh                                   # Postgres 18 en podman, puerto 5433
.venv/bin/pip install -r db/requirements.txt
export DATABASE_URL=postgresql://elg:elg@localhost:5433/elg
.venv/bin/python db/migrar.py                    # aplica las migraciones pendientes
```

Pruebas del esquema y de la API (crean y borran bases desechables):

```bash
PRUEBAS_DATABASE_URL=postgresql://elg:elg@localhost:5433/elg .venv/bin/python -m pytest db/pruebas pos_api/pruebas
```

Sin `PRUEBAS_DATABASE_URL` esas pruebas se omiten. `db/migraciones/0014_divipola.sql`
se genera con `db/datos/generar_divipola.py` desde el CSV oficial del DANE.

## Estado

La fase 3 (la API y la web sobre Postgres) está completa. Módulos:

- **Operación:** Inicio (turno, ventas del día, cuentas abiertas, abonos
  del día, créditos vencidos, stock bajo), Nueva venta (catálogo táctil, lector de
  códigos, cobro en uno o varios métodos con cambio, crédito dentro del cupo;
  no vende por encima del stock; ticket de venta en tirilla de 80 mm con los
  datos del negocio, impuestos incluidos y un mensaje editable en
  Configuración, reimprimible desde Reportes), Cuentas por mesa o nombre (con comandas
  de cocina impresas en tirilla de 80 mm, solo lo nuevo y con comentarios),
  Caja (apertura y cierre contando billetes y monedas, retiros, ingresos y
  traslados, aviso de cuentas abiertas al cerrar, historial) y Consulta de
  precios.
- **Clientes:** datos con documento, DV y municipio; Créditos (saldos,
  abonos aplicados a cargos, cargos manuales, condonaciones).
- **Inventario:** productos de tienda con stock; platos de cocina con receta
  de insumos, preparaciones y productos de la tienda (costo calculado, precio a
  mano, sin stock propio: vender descuenta sus ingredientes y se ve para
  cuántos alcanza); insumos con stock y ajuste por conteo; preparaciones que se
  producen por lotes; combos, adicionales y servicios; Proveedores con compras
  (actualizan stock y último costo) y cuentas por pagar.
- **Negocio:** Gastos (por categoría, nómina, cruce de cuentas, anulación),
  Torneos (inscripciones, fiado por jugador, premios), Documentos
  (cotización → orden de pedido → remisión → venta) y Reportes (ventas,
  costo, utilidad, gastos y resultado por rango, con gráficas y la lista de
  ventas con su detalle).
- **Administración:** usuarios, roles y permisos, datos del negocio, cajas y
  métodos de pago, mesas, categorías de gasto, juegos y auditoría.

Pendiente: documentos fiscales (integrar `backend/` con `documentos_fiscales`
cuando se facture electrónico), Libros (por definir), impresión de tickets de
venta y el despliegue en el servidor del local.
