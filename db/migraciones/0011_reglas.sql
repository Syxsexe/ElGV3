-- 0011_reglas.sql — Reglas que cruzan grupos: cuadres de plata (triggers
-- diferidos que se revisan al confirmar la transacción, porque una venta o un
-- abono se arman en varios INSERT) y el caché del costo de los platos.
--
-- Todas lanzan check_violation con un mensaje para mostrar al usuario.

-- Un abono aplicado vale mientras no venga de un cruce cuyo egreso se anuló.
CREATE FUNCTION abono_vigente(p_abono uuid) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT NOT EXISTS (
        SELECT 1 FROM abonos_credito a
          JOIN anulaciones_egreso ae ON ae.egreso_id = a.egreso_id
         WHERE a.id = p_abono)
$$;

-- ── Venta: pagos + fiado = líneas − descuento ───────────────────────────────

CREATE FUNCTION fn_cuadre_venta(p_venta uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_numero     bigint;
    v_descuento  numeric;
    v_lineas     integer;
    v_subtotal   numeric;
    v_pagos      numeric;
    v_fiado      numeric;
BEGIN
    SELECT numero, descuento INTO v_numero, v_descuento FROM ventas WHERE id = p_venta;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    SELECT count(*), COALESCE(round(sum(cantidad * precio_unit), 2), 0)
      INTO v_lineas, v_subtotal
      FROM detalle_venta WHERE venta_id = p_venta;
    IF v_lineas = 0 THEN
        RAISE EXCEPTION 'La venta #% no tiene líneas', v_numero USING ERRCODE = 'check_violation';
    END IF;
    IF v_descuento > v_subtotal THEN
        RAISE EXCEPTION 'El descuento de la venta #% (%) supera su subtotal (%)', v_numero, v_descuento, v_subtotal
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT COALESCE(sum(monto), 0) INTO v_pagos FROM pagos_venta WHERE venta_id = p_venta;
    SELECT COALESCE(sum(monto), 0) INTO v_fiado FROM cargos_credito WHERE venta_id = p_venta;
    IF v_pagos + v_fiado <> v_subtotal - v_descuento THEN
        RAISE EXCEPTION 'La venta #% no cuadra: pagos % + fiado % ≠ total %',
                        v_numero, v_pagos, v_fiado, v_subtotal - v_descuento
            USING ERRCODE = 'check_violation';
    END IF;
END $$;

CREATE FUNCTION fn_trg_cuadre_venta() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- IF y no CASE: plpgsql resuelve NEW.venta_id aunque la rama no aplique.
    IF TG_TABLE_NAME = 'ventas' THEN
        PERFORM fn_cuadre_venta(NEW.id);
    ELSE
        PERFORM fn_cuadre_venta(NEW.venta_id);
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER ventas_cuadre
    AFTER INSERT ON ventas DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_cuadre_venta();
CREATE CONSTRAINT TRIGGER detalle_venta_cuadre
    AFTER INSERT ON detalle_venta DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_cuadre_venta();
CREATE CONSTRAINT TRIGGER pagos_venta_cuadre
    AFTER INSERT ON pagos_venta DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_cuadre_venta();
CREATE CONSTRAINT TRIGGER cargos_credito_cuadre_venta
    AFTER INSERT ON cargos_credito DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW WHEN (NEW.venta_id IS NOT NULL)
    EXECUTE FUNCTION fn_trg_cuadre_venta();

-- ── Abono: Σ aplicaciones = monto, todas a cargos del mismo cliente ─────────

CREATE FUNCTION fn_cuadre_abono(p_abono uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_monto      numeric;
    v_cliente    uuid;
    v_aplicado   numeric;
BEGIN
    SELECT monto, cliente_id INTO v_monto, v_cliente FROM abonos_credito WHERE id = p_abono;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM abono_aplicaciones aa
                 JOIN cargos_credito c ON c.id = aa.cargo_id
                WHERE aa.abono_id = p_abono AND c.cliente_id <> v_cliente) THEN
        RAISE EXCEPTION 'Un abono solo se aplica a cargos de su mismo cliente' USING ERRCODE = 'check_violation';
    END IF;
    SELECT COALESCE(sum(monto), 0) INTO v_aplicado FROM abono_aplicaciones WHERE abono_id = p_abono;
    IF v_aplicado <> v_monto THEN
        RAISE EXCEPTION 'El abono de % está aplicado por %: todo abono se aplica completo a cargos',
                        v_monto, v_aplicado
            USING ERRCODE = 'check_violation';
    END IF;
END $$;

CREATE FUNCTION fn_trg_cuadre_abono() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- IF y no CASE: plpgsql resuelve NEW.abono_id aunque la rama no aplique.
    IF TG_TABLE_NAME = 'abonos_credito' THEN
        PERFORM fn_cuadre_abono(NEW.id);
    ELSE
        PERFORM fn_cuadre_abono(NEW.abono_id);
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER abonos_credito_cuadre
    AFTER INSERT ON abonos_credito DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_cuadre_abono();
CREATE CONSTRAINT TRIGGER abono_aplicaciones_cuadre
    AFTER INSERT ON abono_aplicaciones DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_cuadre_abono();

-- ── Cargo: lo abonado (vigente) + lo condonado no supera el monto ───────────

CREATE FUNCTION fn_limite_cargo(p_cargo uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_monto      numeric;
    v_abonado    numeric;
    v_condonado  numeric;
BEGIN
    -- El bloqueo serializa dos abonos simultáneos al mismo cargo: el segundo
    -- espera al primero y luego ve lo que este aplicó.
    SELECT monto INTO v_monto FROM cargos_credito WHERE id = p_cargo FOR UPDATE;
    SELECT COALESCE(sum(monto), 0) INTO v_abonado
      FROM abono_aplicaciones WHERE cargo_id = p_cargo AND abono_vigente(abono_id);
    SELECT COALESCE(sum(monto), 0) INTO v_condonado
      FROM condonaciones_credito WHERE cargo_id = p_cargo;
    IF v_abonado + v_condonado > v_monto THEN
        RAISE EXCEPTION 'El cargo de % quedaría pagado de más (abonado %, condonado %)',
                        v_monto, v_abonado, v_condonado
            USING ERRCODE = 'check_violation';
    END IF;
END $$;

CREATE FUNCTION fn_trg_limite_cargo() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_limite_cargo(NEW.cargo_id);
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER abono_aplicaciones_limite_cargo
    AFTER INSERT ON abono_aplicaciones DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_limite_cargo();
CREATE CONSTRAINT TRIGGER condonaciones_credito_limite_cargo
    AFTER INSERT ON condonaciones_credito DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_limite_cargo();

-- ── Cruce de cuentas: el abono es del mismo tercero al que se le paga ───────

CREATE FUNCTION fn_cruce_mismo_tercero() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_beneficiario uuid;
BEGIN
    IF EXISTS (SELECT 1 FROM anulaciones_egreso WHERE egreso_id = NEW.egreso_id) THEN
        RAISE EXCEPTION 'No se cruza contra un egreso anulado' USING ERRCODE = 'check_violation';
    END IF;
    SELECT COALESCE(e.tercero_id, co.proveedor_id) INTO v_beneficiario
      FROM egresos e LEFT JOIN compras co ON co.id = e.compra_id
     WHERE e.id = NEW.egreso_id;
    IF v_beneficiario IS DISTINCT FROM NEW.cliente_id THEN
        RAISE EXCEPTION 'Cruce de cuentas inválido: el egreso no se le paga al mismo tercero del abono'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER abonos_credito_cruce_mismo_tercero
    BEFORE INSERT ON abonos_credito
    FOR EACH ROW WHEN (NEW.egreso_id IS NOT NULL)
    EXECUTE FUNCTION fn_cruce_mismo_tercero();

-- ── Egreso: tiene al menos un pago o un cruce; a una compra no se le paga de más ──

CREATE FUNCTION egreso_monto(p_egreso uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT sum(monto) FROM pagos_egreso WHERE egreso_id = p_egreso), 0)
         + COALESCE((SELECT sum(monto) FROM abonos_credito WHERE egreso_id = p_egreso), 0)
$$;

-- Lo pagado (egresos no anulados) a una compra no supera su total. Se revisa
-- al pagarla y también al cambiar sus líneas después de pagada.
CREATE FUNCTION fn_limite_compra(p_compra uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_total   numeric;
    v_pagado  numeric;
BEGIN
    PERFORM 1 FROM compras WHERE id = p_compra FOR UPDATE;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    SELECT COALESCE(round(sum(cantidad * costo_unit), 2), 0) INTO v_total
      FROM compra_lineas WHERE compra_id = p_compra;
    SELECT COALESCE(sum(egreso_monto(e.id)), 0) INTO v_pagado
      FROM egresos e
     WHERE e.compra_id = p_compra
       AND NOT EXISTS (SELECT 1 FROM anulaciones_egreso ae WHERE ae.egreso_id = e.id);
    IF v_pagado > v_total THEN
        RAISE EXCEPTION 'A la compra se le pagaría % de un total de %', v_pagado, v_total
            USING ERRCODE = 'check_violation';
    END IF;
END $$;

CREATE FUNCTION fn_cuadre_egreso(p_egreso uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_compra  uuid;
BEGIN
    SELECT compra_id INTO v_compra FROM egresos WHERE id = p_egreso;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    IF egreso_monto(p_egreso) = 0 THEN
        RAISE EXCEPTION 'El egreso no tiene pagos ni cruces' USING ERRCODE = 'check_violation';
    END IF;
    IF v_compra IS NOT NULL THEN
        PERFORM fn_limite_compra(v_compra);
    END IF;
END $$;

CREATE FUNCTION fn_trg_cuadre_egreso() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- IF y no CASE: plpgsql resuelve NEW.egreso_id aunque la rama no aplique.
    IF TG_TABLE_NAME = 'egresos' THEN
        PERFORM fn_cuadre_egreso(NEW.id);
    ELSE
        PERFORM fn_cuadre_egreso(NEW.egreso_id);
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER egresos_cuadre
    AFTER INSERT ON egresos DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_cuadre_egreso();
CREATE CONSTRAINT TRIGGER pagos_egreso_cuadre
    AFTER INSERT ON pagos_egreso DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_cuadre_egreso();
CREATE CONSTRAINT TRIGGER abonos_credito_cuadre_egreso
    AFTER INSERT ON abonos_credito DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW WHEN (NEW.egreso_id IS NOT NULL)
    EXECUTE FUNCTION fn_trg_cuadre_egreso();

CREATE FUNCTION fn_trg_limite_compra_lineas() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM fn_limite_compra(OLD.compra_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM fn_limite_compra(NEW.compra_id);
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER compra_lineas_limite_compra
    AFTER INSERT OR UPDATE OR DELETE ON compra_lineas DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_limite_compra_lineas();

-- ── Caché del costo de los platos ───────────────────────────────────────────
-- productos.precio_costo de un plato con receta = Σ cantidad × costo del insumo.
-- El costo de una preparación es Σ (cantidad × costo de sus componentes) ÷
-- rendimiento, y una preparación puede usar otra (adobo dentro del filete).

CREATE FUNCTION costo_insumo(p_insumo uuid, p_visitados uuid[] DEFAULT '{}') RETURNS numeric
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_rendimiento  numeric;
    v_total        numeric := 0;
    r              record;
BEGIN
    IF p_insumo = ANY (p_visitados) THEN
        RAISE EXCEPTION 'Las recetas de preparación forman un ciclo (una preparación termina usándose a sí misma)'
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT rendimiento INTO v_rendimiento FROM preparaciones WHERE insumo_id = p_insumo;
    IF NOT FOUND THEN
        RETURN (SELECT costo_unitario FROM insumos WHERE id = p_insumo);
    END IF;
    FOR r IN SELECT insumo_id, cantidad FROM receta_preparacion WHERE preparacion_id = p_insumo LOOP
        v_total := v_total + r.cantidad * costo_insumo(r.insumo_id, p_visitados || p_insumo);
    END LOOP;
    RETURN v_total / v_rendimiento;
END $$;

CREATE FUNCTION costo_plato(p_producto uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT round(COALESCE(sum(cantidad * costo_insumo(insumo_id)), 0), 2)
      FROM receta_insumos WHERE producto_id = p_producto
$$;

-- Recalcula todos los platos con receta (el menú es pequeño). Un plato al que
-- se le quita toda la receta conserva su último costo y pasa a costo manual.
CREATE FUNCTION recalcular_costos_cocina() RETURNS void
LANGUAGE sql AS $$
    UPDATE productos p
       SET precio_costo = x.costo
      FROM (SELECT producto_id, costo_plato(producto_id) AS costo
              FROM (SELECT DISTINCT producto_id FROM receta_insumos) platos) x
     WHERE p.articulo_id = x.producto_id
       AND p.precio_costo IS DISTINCT FROM x.costo
$$;

CREATE FUNCTION fn_trg_recalcular_costos() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM recalcular_costos_cocina();
    RETURN NULL;
END $$;

CREATE FUNCTION fn_receta_preparacion_sin_ciclos() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM costo_insumo(NEW.preparacion_id);  -- recorre la receta y falla si hay ciclo
    RETURN NULL;
END $$;
CREATE TRIGGER receta_preparacion_sin_ciclos
    AFTER INSERT OR UPDATE ON receta_preparacion
    FOR EACH ROW EXECUTE FUNCTION fn_receta_preparacion_sin_ciclos();

CREATE TRIGGER insumos_recalcular_costos
    AFTER UPDATE OF costo_unitario ON insumos
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_recalcular_costos();
CREATE TRIGGER receta_insumos_recalcular_costos
    AFTER INSERT OR UPDATE OR DELETE ON receta_insumos
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_recalcular_costos();
CREATE TRIGGER receta_preparacion_recalcular_costos
    AFTER INSERT OR UPDATE OR DELETE ON receta_preparacion
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_recalcular_costos();
CREATE TRIGGER preparaciones_recalcular_costos
    AFTER INSERT OR UPDATE OR DELETE ON preparaciones
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_recalcular_costos();
