-- 0006_mesas.sql — Grupo 6: mesas y cuentas abiertas.
--
-- Estado calculado (v_cuentas): abierta, cobrada (tiene venta) o cancelada
-- (tiene cancelada_en). Al cobrar, las líneas se MUEVEN a detalle_venta: una
-- cuenta cobrada no conserva ítems; una cancelada conserva lo que se canceló.

CREATE TABLE mesas (
    id      uuid    PRIMARY KEY DEFAULT uuidv7(),
    nombre  text    NOT NULL UNIQUE,
    activa  boolean NOT NULL DEFAULT true
);

CREATE TABLE cuentas (
    id            uuid        PRIMARY KEY DEFAULT uuidv7(),
    numero        bigint      GENERATED ALWAYS AS IDENTITY UNIQUE,
    mesa_id       uuid        REFERENCES mesas,
    cliente_id    uuid        REFERENCES clientes,
    alias         text        CHECK (btrim(alias) <> ''),
    abierta_por   uuid        NOT NULL REFERENCES usuarios,
    abierta_en    timestamptz NOT NULL DEFAULT now(),
    venta_id      uuid        UNIQUE REFERENCES ventas,
    cancelada_en  timestamptz,
    notas         text,
    CONSTRAINT cuentas_cliente_o_alias CHECK ((cliente_id IS NULL) <> (alias IS NULL)),
    CONSTRAINT cuentas_cobrada_o_cancelada CHECK (venta_id IS NULL OR cancelada_en IS NULL)
);
COMMENT ON COLUMN cuentas.mesa_id IS 'Opcional: grupos que no están en una mesa.';
COMMENT ON COLUMN cuentas.alias IS 'Nombre de referencia solo cuando no hay cliente registrado.';

CREATE UNIQUE INDEX cuentas_una_abierta_por_mesa
    ON cuentas (mesa_id)
    WHERE mesa_id IS NOT NULL AND venta_id IS NULL AND cancelada_en IS NULL;

CREATE TABLE cuenta_items (
    id           uuid          PRIMARY KEY DEFAULT uuidv7(),
    cuenta_id    uuid          NOT NULL REFERENCES cuentas,
    articulo_id  uuid          NOT NULL REFERENCES articulos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    precio_unit  numeric(14,2) NOT NULL CHECK (precio_unit >= 0),
    agregado_en  timestamptz   NOT NULL DEFAULT now()
);
COMMENT ON COLUMN cuenta_items.precio_unit IS 'Foto del precio cuando se agregó.';
CREATE INDEX cuenta_items_cuenta ON cuenta_items (cuenta_id);

-- Los ítems solo cambian mientras la cuenta está abierta.
CREATE FUNCTION fn_cuenta_items_cuenta_abierta() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_cuenta uuid := CASE WHEN TG_OP = 'DELETE' THEN OLD.cuenta_id ELSE NEW.cuenta_id END;
BEGIN
    IF EXISTS (SELECT 1 FROM cuentas
                WHERE id = v_cuenta AND (venta_id IS NOT NULL OR cancelada_en IS NOT NULL)) THEN
        RAISE EXCEPTION 'La cuenta ya está cerrada: sus ítems no cambian'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.cuenta_id <> OLD.cuenta_id THEN
        RAISE EXCEPTION 'Un ítem no se pasa de una cuenta a otra' USING ERRCODE = 'check_violation';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER cuenta_items_cuenta_abierta
    BEFORE INSERT OR UPDATE OR DELETE ON cuenta_items
    FOR EACH ROW EXECUTE FUNCTION fn_cuenta_items_cuenta_abierta();

-- Una cuenta cerrada no se reabre ni se edita. Al cobrarla ya no puede tener
-- ítems: deben haberse movido a detalle_venta.
CREATE FUNCTION fn_cuentas_transicion() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Las cuentas no se borran: se cancelan' USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.venta_id IS NOT NULL OR OLD.cancelada_en IS NOT NULL THEN
        RAISE EXCEPTION 'La cuenta #% ya está cerrada: no admite cambios', OLD.numero
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.venta_id IS NOT NULL AND EXISTS (SELECT 1 FROM cuenta_items WHERE cuenta_id = NEW.id) THEN
        RAISE EXCEPTION 'Para cobrar la cuenta #% sus ítems deben pasar a la venta', NEW.numero
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER cuentas_transicion
    BEFORE UPDATE OR DELETE ON cuentas
    FOR EACH ROW EXECUTE FUNCTION fn_cuentas_transicion();
