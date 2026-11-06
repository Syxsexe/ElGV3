-- 0018_terceros.sql — CONSUMIDOR FINAL marcado explícitamente (paso 3).
--
-- El adquiriente genérico de la DIAN no se edita ni se lista como cliente, y
-- las ventas sin cliente lo usarán al facturar. Se marca con una columna en
-- vez de reconocerlo por su número, para que la regla no dependa de copiar
-- el dato sembrado en 0013.

ALTER TABLE terceros ADD COLUMN es_consumidor_final boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN terceros.es_consumidor_final IS
    'El adquiriente genérico de la DIAN (CONSUMIDOR FINAL): uno solo, no se edita ni es cliente.';

UPDATE terceros SET es_consumidor_final = true
 WHERE numero_identificacion = '222222222222'
   AND tipo_identificacion_id = (SELECT id FROM tipos_identificacion WHERE codigo = '13');

CREATE UNIQUE INDEX terceros_un_consumidor_final ON terceros ((true)) WHERE es_consumidor_final;
