-- Seed de la resolución de facturación para pruebas en SANDBOX.
-- Refleja la resolución real que Matias tiene registrada en la cuenta de sandbox:
--   factura electrónica (type_document_id 7) → prefijo FEV, número 18760000001,
--   rango de numeración 1–1000.
--
-- Se ejecuta UNA vez contra la BD Postgres del backend (elg_pos):
--   psql "$DATABASE_URL" -f backend/scripts/seed_resolucion_sandbox.sql
--
-- consecutivo_actual = 4 porque las pruebas directas ya quemaron FEV1–FEV4 en el
-- sandbox; así el backend emite desde FEV5 y no colisiona. Ajusta si reinician
-- el consecutivo del sandbox.
--
-- ⚠️ NO usar en producción: en prod va la resolución REAL habilitada por la DIAN
--    (otro número, rango y clave técnica).

INSERT INTO resoluciones (
    id, numero_resolucion, prefijo, tipo_documento,
    rango_inicio, rango_fin, consecutivo_actual,
    fecha_autorizacion, fecha_vencimiento, clave_tecnica, activa, creado_en
) VALUES (
    gen_random_uuid(),
    '18760000001',            -- numero_resolucion (resolution_number del PT)
    'FEV',                    -- prefijo
    'FEV',                    -- tipo_documento (enum tipo_documento_enum)
    1,                        -- rango_inicio
    1000,                     -- rango_fin (sandbox: 1–1000)
    4,                        -- consecutivo_actual (siguiente emisión = FEV5)
    CURRENT_DATE,             -- fecha_autorizacion
    CURRENT_DATE + INTERVAL '1 year',   -- fecha_vencimiento
    'clave-tecnica-sandbox-no-usada-por-el-PT',  -- clave_tecnica (Matias firma; no la usa)
    TRUE,                     -- activa
    NOW()
);
