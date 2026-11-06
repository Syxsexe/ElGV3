-- 0016_administracion.sql — Reglas de la configuración editable (paso 1).
--
-- v_sesion_cajas reparte cada pago en la caja de su método leyendo la caja
-- ACTUAL del método. Si un método ya usado cambiara de caja, el esperado de
-- turnos viejos (ya cerrados y cuadrados) cambiaría. Por eso, un método con
-- pagos registrados conserva su caja: para mover un medio de pago a otra caja
-- se crea un método nuevo y se desactiva el viejo.

CREATE FUNCTION fn_metodo_pago_caja_fija() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.caja_id IS DISTINCT FROM OLD.caja_id AND (
           EXISTS (SELECT 1 FROM pagos_venta    WHERE metodo_pago_id = OLD.id)
        OR EXISTS (SELECT 1 FROM pagos_egreso   WHERE metodo_pago_id = OLD.id)
        OR EXISTS (SELECT 1 FROM abonos_credito WHERE metodo_pago_id = OLD.id))
    THEN
        RAISE EXCEPTION 'El método % ya tiene pagos registrados: no puede cambiar de caja (crea otro método y desactiva este)',
                        OLD.nombre
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER metodos_pago_caja_fija
    BEFORE UPDATE OF caja_id ON metodos_pago
    FOR EACH ROW EXECUTE FUNCTION fn_metodo_pago_caja_fija();

-- El pago lee la caja de su método con FOR SHARE: así un cambio de caja
-- simultáneo (que toma la fila para UPDATE) espera a que el pago confirme y
-- entonces lo ve en el trigger de arriba, o el pago espera al cambio y valida
-- contra la caja nueva. Sin esto, el bloqueo de la FK (FOR KEY SHARE) no
-- choca con el UPDATE y los dos podían confirmar.
CREATE OR REPLACE FUNCTION fn_exigir_caja_de_metodo(p_sesion uuid, p_metodo uuid) RETURNS void
LANGUAGE sql AS $$
    SELECT fn_exigir_caja_en_turno(p_sesion, (SELECT caja_id FROM metodos_pago WHERE id = p_metodo FOR SHARE))
$$;

-- ── Sesiones ────────────────────────────────────────────────────────────────

ALTER TABLE usuarios
    ADD COLUMN sesiones_desde timestamptz NOT NULL DEFAULT date_trunc('second', now());
COMMENT ON COLUMN usuarios.sesiones_desde IS
    'Los tokens emitidos antes de este momento ya no valen: se mueve al cambiar o restablecer la contraseña '
    '(un token robado deja de servir). Al segundo, porque el iat del JWT va en segundos.';
