-- Migración: añade el valor 'error' a los enums de estado DIAN.
--
-- Motivo: cuando el Proveedor Tecnológico rechaza técnicamente un documento
-- (p.ej. HTTP 422 de validación), el adaptador devuelve estado 'error'. Sin este
-- valor en el enum, el INSERT falla con 500 y el documento fallido no se persiste
-- (el cajero no ve el error). Con 'error' presente, la factura/nota queda guardada
-- en estado 'error' con el detalle en mensaje_dian.
--
-- create_all NO altera enums existentes: en una BD ya creada hay que correr esto.
-- En una BD nueva, los modelos ya incluyen 'error' y no hace falta.
--
--   psql "$DATABASE_URL" -f backend/scripts/migracion_estado_error.sql
--
-- ADD VALUE es idempotente con IF NOT EXISTS (PostgreSQL 12+).

ALTER TYPE factura_estado_enum ADD VALUE IF NOT EXISTS 'error';
ALTER TYPE nc_estado_enum      ADD VALUE IF NOT EXISTS 'error';
ALTER TYPE nd_estado_enum      ADD VALUE IF NOT EXISTS 'error';
