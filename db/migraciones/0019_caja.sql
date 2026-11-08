-- 0019_caja.sql — Desglose del esperado de caja (paso 4).
--
-- La pantalla de caja muestra de dónde sale el esperado (ventas, abonos,
-- gastos, retiros…). Para que ese desglose sume siempre lo mismo que el
-- esperado, los dos salen de la misma vista: v_flujos_caja lista cada entrada
-- y salida de plata con su concepto, y v_sesion_cajas suma sobre ella.

CREATE VIEW v_flujos_caja (sesion_id, caja_id, concepto, monto) AS
SELECT v.sesion_id, mp.caja_id, 'venta', pv.monto
  FROM pagos_venta pv
  JOIN ventas v        ON v.id = pv.venta_id
  JOIN metodos_pago mp ON mp.id = pv.metodo_pago_id
UNION ALL
SELECT a.sesion_id, mp.caja_id, 'abono', a.monto
  FROM abonos_credito a
  JOIN metodos_pago mp ON mp.id = a.metodo_pago_id
UNION ALL
SELECT sesion_id, caja_destino_id, CASE tipo WHEN 'ingreso' THEN 'ingreso' ELSE 'traslado_entrada' END, monto
  FROM movimientos_caja WHERE caja_destino_id IS NOT NULL
UNION ALL
SELECT sesion_id, caja_origen_id, CASE tipo WHEN 'retiro' THEN 'retiro' ELSE 'traslado_salida' END, -monto
  FROM movimientos_caja WHERE caja_origen_id IS NOT NULL
UNION ALL
SELECT e.sesion_id, mp.caja_id, 'egreso', -pe.monto
  FROM pagos_egreso pe
  JOIN egresos e       ON e.id = pe.egreso_id
  JOIN metodos_pago mp ON mp.id = pe.metodo_pago_id
UNION ALL
SELECT an.sesion_id, mp.caja_id, 'anulacion_egreso', pe.monto
  FROM anulaciones_egreso an
  JOIN pagos_egreso pe ON pe.egreso_id = an.egreso_id
  JOIN metodos_pago mp ON mp.id = pe.metodo_pago_id;
COMMENT ON VIEW v_flujos_caja IS
    'Cada entrada (+) y salida (−) de plata por turno y caja. Un egreso anulado devuelve su plata en el turno '
    'de la anulación. concepto: venta, abono, ingreso, retiro, traslado_entrada, traslado_salida, egreso, '
    'anulacion_egreso.';

-- Mismas columnas que en 0012: solo cambia de dónde salen los flujos.
CREATE OR REPLACE VIEW v_sesion_cajas AS
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
  LEFT JOIN (SELECT sesion_id, caja_id, sum(monto) AS neto FROM v_flujos_caja GROUP BY 1, 2) f
         ON f.sesion_id = sc.sesion_id AND f.caja_id = sc.caja_id
  LEFT JOIN LATERAL (
        SELECT sc2.contado
          FROM sesion_cajas sc2
          JOIN sesiones_caja s2 ON s2.id = sc2.sesion_id
         WHERE sc2.caja_id = sc.caja_id AND s2.numero < s.numero
         ORDER BY s2.numero DESC
         LIMIT 1) ant ON true;

-- La vista filtra por turno en cada tabla de flujos; ventas y egresos ya
-- tenían índice por sesion_id, estas no (el historial la consulta por turno).
CREATE INDEX movimientos_caja_sesion ON movimientos_caja (sesion_id);
CREATE INDEX abonos_credito_sesion ON abonos_credito (sesion_id);
CREATE INDEX anulaciones_egreso_sesion ON anulaciones_egreso (sesion_id);
