-- 0012_vistas.sql — Lo que el modelo calcula en vez de guardar: totales,
-- estados, saldos y cuadres de caja. Las apps leen estas vistas.

-- ── Ventas ──────────────────────────────────────────────────────────────────

CREATE VIEW v_ventas AS
SELECT v.*,
       l.subtotal,
       l.subtotal - v.descuento                AS total,
       COALESCE(p.pagado, 0)                    AS pagado,
       COALESCE(f.fiado, 0)                     AS fiado,
       CASE
           WHEN p.pagado IS NULL AND f.fiado IS NULL THEN NULL
           WHEN p.pagado IS NULL                     THEN 'credito'
           WHEN f.fiado IS NULL AND p.metodos = 1    THEN p.metodo_unico
           ELSE 'mixto'
       END                                      AS metodo,
       CASE WHEN l.tipos = 1 THEN l.tipo_unico ELSE 'mixta' END AS tipo
  FROM ventas v
  CROSS JOIN LATERAL (
        SELECT COALESCE(round(sum(d.cantidad * d.precio_unit), 2), 0) AS subtotal,
               count(DISTINCT ca.tipo)                                 AS tipos,
               min(ca.tipo)                                            AS tipo_unico
          FROM detalle_venta d
          JOIN articulos a  ON a.id = d.articulo_id
          JOIN categorias ca ON ca.id = a.categoria_id
         WHERE d.venta_id = v.id) l
  CROSS JOIN LATERAL (
        SELECT sum(pv.monto)               AS pagado,
               count(DISTINCT mp.codigo)   AS metodos,
               min(mp.codigo)              AS metodo_unico
          FROM pagos_venta pv
          JOIN metodos_pago mp ON mp.id = pv.metodo_pago_id
         WHERE pv.venta_id = v.id) p
  CROSS JOIN LATERAL (
        SELECT sum(monto) AS fiado FROM cargos_credito WHERE venta_id = v.id) f;
COMMENT ON VIEW v_ventas IS 'total = subtotal − descuento; metodo = código, "credito" o "mixto"; tipo = tienda, cocina o mixta.';

-- ── Crédito ─────────────────────────────────────────────────────────────────

CREATE VIEW v_cargos_credito AS
SELECT c.*,
       COALESCE(ap.abonado, 0)                                          AS abonado,
       COALESCE(cd.condonado, 0)                                        AS condonado,
       c.monto - COALESCE(ap.abonado, 0) - COALESCE(cd.condonado, 0)    AS pendiente,
       c.vence_en < current_date
           AND c.monto - COALESCE(ap.abonado, 0) - COALESCE(cd.condonado, 0) > 0 AS vencido
  FROM cargos_credito c
  CROSS JOIN LATERAL (
        SELECT sum(aa.monto) AS abonado FROM abono_aplicaciones aa
         WHERE aa.cargo_id = c.id AND abono_vigente(aa.abono_id)) ap
  CROSS JOIN LATERAL (
        SELECT sum(monto) AS condonado FROM condonaciones_credito WHERE cargo_id = c.id) cd;

CREATE VIEW v_saldos_clientes AS
SELECT cl.tercero_id                                                          AS cliente_id,
       t.nombre,
       cl.limite_credito,
       cl.dias_credito,
       COALESCE(sum(vc.pendiente), 0)                                         AS saldo,
       greatest(cl.limite_credito - COALESCE(sum(vc.pendiente), 0), 0)        AS disponible,
       count(*) FILTER (WHERE vc.vencido)                                     AS cargos_vencidos,
       min(vc.vence_en) FILTER (WHERE vc.pendiente > 0)                       AS proximo_vencimiento
  FROM clientes cl
  JOIN terceros t ON t.id = cl.tercero_id
  LEFT JOIN v_cargos_credito vc ON vc.cliente_id = cl.tercero_id
 GROUP BY cl.tercero_id, t.nombre, cl.limite_credito, cl.dias_credito;

-- ── Gastos y compras ────────────────────────────────────────────────────────

CREATE VIEW v_egresos AS
SELECT e.*,
       COALESCE(p.pagado, 0)                              AS pagado,
       COALESCE(x.cruzado, 0)                             AS cruzado,
       COALESCE(p.pagado, 0) + COALESCE(x.cruzado, 0)     AS monto,
       an.egreso_id IS NOT NULL                           AS anulado
  FROM egresos e
  CROSS JOIN LATERAL (SELECT sum(monto) AS pagado  FROM pagos_egreso   WHERE egreso_id = e.id) p
  CROSS JOIN LATERAL (SELECT sum(monto) AS cruzado FROM abonos_credito WHERE egreso_id = e.id) x
  LEFT JOIN anulaciones_egreso an ON an.egreso_id = e.id;

CREATE VIEW v_compras AS
SELECT co.*,
       l.total,
       l.base,
       l.total - l.base                       AS impuestos,
       COALESCE(pg.pagado, 0)                 AS pagado,
       l.total - COALESCE(pg.pagado, 0)       AS pendiente
  FROM compras co
  CROSS JOIN LATERAL (
        SELECT COALESCE(round(sum(cl.cantidad * cl.costo_unit), 2), 0) AS total,
               COALESCE(round(sum(cl.cantidad * cl.costo_unit / (1 + COALESCE(i.tarifa, 0) / 100)), 2), 0) AS base
          FROM compra_lineas cl
          LEFT JOIN impuestos i ON i.id = cl.impuesto_id
         WHERE cl.compra_id = co.id) l
  CROSS JOIN LATERAL (
        SELECT sum(ve.monto) AS pagado FROM v_egresos ve
         WHERE ve.compra_id = co.id AND NOT ve.anulado) pg;
COMMENT ON VIEW v_compras IS 'costo_unit incluye impuestos: la base se saca hacia atrás. pendiente = cuenta por pagar.';

-- ── Caja ────────────────────────────────────────────────────────────────────
-- Esperado por caja = base + todo lo que entró − todo lo que salió en el turno.
-- Un egreso anulado devuelve su plata en el turno de la anulación.

CREATE VIEW v_sesion_cajas AS
WITH flujos (sesion_id, caja_id, monto) AS (
    SELECT v.sesion_id, mp.caja_id, pv.monto
      FROM pagos_venta pv
      JOIN ventas v        ON v.id = pv.venta_id
      JOIN metodos_pago mp ON mp.id = pv.metodo_pago_id
    UNION ALL
    SELECT a.sesion_id, mp.caja_id, a.monto
      FROM abonos_credito a
      JOIN metodos_pago mp ON mp.id = a.metodo_pago_id
    UNION ALL
    SELECT sesion_id, caja_destino_id, monto  FROM movimientos_caja WHERE caja_destino_id IS NOT NULL
    UNION ALL
    SELECT sesion_id, caja_origen_id, -monto  FROM movimientos_caja WHERE caja_origen_id IS NOT NULL
    UNION ALL
    SELECT e.sesion_id, mp.caja_id, -pe.monto
      FROM pagos_egreso pe
      JOIN egresos e       ON e.id = pe.egreso_id
      JOIN metodos_pago mp ON mp.id = pe.metodo_pago_id
    UNION ALL
    SELECT an.sesion_id, mp.caja_id, pe.monto
      FROM anulaciones_egreso an
      JOIN pagos_egreso pe ON pe.egreso_id = an.egreso_id
      JOIN metodos_pago mp ON mp.id = pe.metodo_pago_id
)
SELECT sc.sesion_id,
       s.numero,
       sc.caja_id,
       c.nombre                                           AS caja,
       sc.base,
       sc.contado,
       sc.base + COALESCE(f.neto, 0)                      AS esperado,
       sc.contado - (sc.base + COALESCE(f.neto, 0))       AS diferencia,
       sc.base - ant.contado                              AS diferencia_apertura
  FROM sesion_cajas sc
  JOIN sesiones_caja s ON s.id = sc.sesion_id
  JOIN cajas c         ON c.id = sc.caja_id
  LEFT JOIN (SELECT sesion_id, caja_id, sum(monto) AS neto FROM flujos GROUP BY 1, 2) f
         ON f.sesion_id = sc.sesion_id AND f.caja_id = sc.caja_id
  LEFT JOIN LATERAL (
        SELECT sc2.contado
          FROM sesion_cajas sc2
          JOIN sesiones_caja s2 ON s2.id = sc2.sesion_id
         WHERE sc2.caja_id = sc.caja_id AND s2.numero < s.numero
         ORDER BY s2.numero DESC
         LIMIT 1) ant ON true;
COMMENT ON VIEW v_sesion_cajas IS
    'diferencia = contado − esperado (NULL con el turno abierto). diferencia_apertura = base − contado del '
    'turno anterior: plata que entró o salió entre turnos sin registrarse.';

-- ── Mesas ───────────────────────────────────────────────────────────────────

CREATE VIEW v_cuentas AS
SELECT cu.*,
       CASE WHEN cu.venta_id IS NOT NULL     THEN 'cobrada'
            WHEN cu.cancelada_en IS NOT NULL THEN 'cancelada'
            ELSE 'abierta' END                                      AS estado,
       COALESCE(i.total_items, 0)                                   AS total_items
  FROM cuentas cu
  CROSS JOIN LATERAL (
        SELECT round(sum(cantidad * precio_unit), 2) AS total_items
          FROM cuenta_items WHERE cuenta_id = cu.id) i;
COMMENT ON COLUMN v_cuentas.total_items IS 'Lo pendiente en una cuenta abierta (o lo cancelado). Una cobrada lo tiene en su venta.';

-- ── Documentos ──────────────────────────────────────────────────────────────

CREATE VIEW v_documentos_comerciales AS
SELECT d.*,
       COALESCE(i.subtotal, 0)               AS subtotal,
       COALESCE(i.subtotal, 0) - d.descuento AS total,
       CASE
           WHEN d.motivo_descarte = 'rechazado' THEN 'rechazada'
           WHEN d.motivo_descarte = 'anulado'   THEN 'anulada'
           WHEN d.venta_id IS NOT NULL          THEN 'facturada'
           WHEN EXISTS (SELECT 1 FROM documentos_comerciales h WHERE h.doc_origen_id = d.id)
                THEN CASE d.tipo WHEN 'cotizacion' THEN 'aceptada' ELSE 'entregada' END
           WHEN d.vigente_hasta < current_date  THEN 'vencida'
           ELSE 'vigente'
       END                                   AS estado
  FROM documentos_comerciales d
  CROSS JOIN LATERAL (
        SELECT round(sum(cantidad * precio_unit), 2) AS subtotal
          FROM documento_items WHERE documento_id = d.id) i;

CREATE VIEW v_documentos_fiscales AS
SELECT d.*,
       EXISTS (SELECT 1 FROM documentos_fiscales nc
                WHERE nc.documento_referencia_id = d.id
                  AND nc.tipo = 'NC' AND nc.estado = 'aceptado') AS anulado,
       vv.total
  FROM documentos_fiscales d
  LEFT JOIN documentos_fiscales ref ON ref.id = d.documento_referencia_id
  LEFT JOIN v_ventas vv ON vv.id = COALESCE(d.venta_id, ref.venta_id);
COMMENT ON VIEW v_documentos_fiscales IS 'total sale de la venta (en una NC, de la venta del documento que corrige: NC total).';

-- ── Torneos ─────────────────────────────────────────────────────────────────

CREATE VIEW v_torneos AS
SELECT t.*,
       j.nombre                                           AS juego,
       COALESCE(vv.total, 0)                              AS recaudado,
       COALESCE(pr.costo_premios, 0)                      AS costo_premios,
       COALESCE(vv.total, 0) - COALESCE(pr.costo_premios, 0) AS ganancia,
       pa.jugadores,
       pa.jugadores_gratis
  FROM torneos t
  JOIN juegos j ON j.id = t.juego_id
  LEFT JOIN v_ventas vv ON vv.id = t.venta_id
  CROSS JOIN LATERAL (
        SELECT round(sum(cantidad * costo_unit), 2) AS costo_premios
          FROM torneo_premios WHERE torneo_id = t.id) pr
  CROSS JOIN LATERAL (
        SELECT count(*)                                                        AS jugadores,
               count(*) FILTER (WHERE pago_venta_id IS NULL AND cargo_id IS NULL) AS jugadores_gratis
          FROM torneo_participantes WHERE torneo_id = t.id) pa;
