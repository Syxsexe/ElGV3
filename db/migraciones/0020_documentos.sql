-- 0020_documentos.sql — Un documento descartado no cierra a su origen (paso 9).
--
-- Antes, cualquier documento hijo dejaba al origen como aceptado/entregado.
-- Si el hijo se anula (fue un error) o se rechaza, el origen debe volver a
-- quedar abierto para editarlo, convertirlo de nuevo o venderlo. Mismas
-- columnas que en 0012: solo cambia qué hijos cuentan.

CREATE OR REPLACE VIEW v_documentos_comerciales AS
SELECT d.*,
       COALESCE(i.subtotal, 0)               AS subtotal,
       COALESCE(i.subtotal, 0) - d.descuento AS total,
       CASE
           WHEN d.motivo_descarte = 'rechazado' THEN 'rechazada'
           WHEN d.motivo_descarte = 'anulado'   THEN 'anulada'
           WHEN d.venta_id IS NOT NULL          THEN 'facturada'
           WHEN EXISTS (SELECT 1 FROM documentos_comerciales h
                         WHERE h.doc_origen_id = d.id AND h.descartado_en IS NULL)
                THEN CASE d.tipo WHEN 'cotizacion' THEN 'aceptada' ELSE 'entregada' END
           WHEN d.vigente_hasta < current_date  THEN 'vencida'
           ELSE 'vigente'
       END                                   AS estado
  FROM documentos_comerciales d
  CROSS JOIN LATERAL (
        SELECT round(sum(cantidad * precio_unit), 2) AS subtotal
          FROM documento_items WHERE documento_id = d.id) i;

CREATE INDEX documentos_comerciales_origen ON documentos_comerciales (doc_origen_id);
