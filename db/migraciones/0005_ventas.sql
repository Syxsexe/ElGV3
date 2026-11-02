-- 0005_ventas.sql — Grupo 5: ventas, sus líneas y sus pagos.
--
-- Las ventas no se anulan ni se editan (solo inserción). El total, el método
-- ("mixto" incluido) y el tipo tienda/cocina se calculan en v_ventas. El
-- cuadre pagos + fiado = total vive en 0011_reglas (necesita cargos_credito).

CREATE TABLE ventas (
    id          uuid          PRIMARY KEY DEFAULT uuidv7(),
    numero      bigint        GENERATED ALWAYS AS IDENTITY UNIQUE,
    sesion_id   uuid          NOT NULL REFERENCES sesiones_caja,
    usuario_id  uuid          NOT NULL REFERENCES usuarios,
    cliente_id  uuid          REFERENCES clientes,
    creada_en   timestamptz   NOT NULL DEFAULT now(),
    descuento   numeric(14,2) NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    notas       text
);
COMMENT ON COLUMN ventas.notas IS 'Solo lo que escribe una persona; el origen (mesa, torneo) se ve por sus FK.';

CREATE TABLE detalle_venta (
    id           uuid          PRIMARY KEY DEFAULT uuidv7(),
    venta_id     uuid          NOT NULL REFERENCES ventas,
    articulo_id  uuid          NOT NULL REFERENCES articulos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    precio_unit  numeric(14,2) NOT NULL CHECK (precio_unit >= 0),
    costo_unit   numeric(14,2) NOT NULL DEFAULT 0 CHECK (costo_unit >= 0),
    impuesto_id  uuid          NOT NULL REFERENCES impuestos
);
COMMENT ON COLUMN detalle_venta.precio_unit IS 'Foto histórica del precio (impuestos incluidos) al vender.';
COMMENT ON COLUMN detalle_venta.costo_unit IS 'Foto histórica del costo al vender: el margen de una venta vieja no cambia.';
COMMENT ON COLUMN detalle_venta.impuesto_id IS 'Foto del impuesto (las filas de impuestos son inmutables).';

CREATE TABLE pagos_venta (
    id              uuid          PRIMARY KEY DEFAULT uuidv7(),
    venta_id        uuid          NOT NULL REFERENCES ventas,
    metodo_pago_id  uuid          NOT NULL REFERENCES metodos_pago,
    monto           numeric(14,2) NOT NULL CHECK (monto > 0)
);
COMMENT ON TABLE pagos_venta IS 'Solo plata real que entra a una caja. La parte fiada es un cargo en cargos_credito.';

CREATE INDEX detalle_venta_venta ON detalle_venta (venta_id);
CREATE INDEX pagos_venta_venta ON pagos_venta (venta_id);
CREATE INDEX ventas_sesion ON ventas (sesion_id);

CREATE TRIGGER ventas_turno_abierto
    BEFORE INSERT ON ventas
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto();

-- Líneas y pagos se agregan solo mientras el turno de su venta está abierto.
CREATE FUNCTION fn_trg_turno_abierto_de_venta() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_exigir_turno_abierto((SELECT sesion_id FROM ventas WHERE id = NEW.venta_id));
    RETURN NEW;
END $$;
CREATE TRIGGER detalle_venta_turno_abierto
    BEFORE INSERT ON detalle_venta
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto_de_venta();
CREATE TRIGGER pagos_venta_turno_abierto
    BEFORE INSERT ON pagos_venta
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto_de_venta();

CREATE FUNCTION fn_pago_venta_caja_en_turno() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_exigir_caja_de_metodo((SELECT sesion_id FROM ventas WHERE id = NEW.venta_id), NEW.metodo_pago_id);
    RETURN NEW;
END $$;
CREATE TRIGGER pagos_venta_caja_en_turno
    BEFORE INSERT ON pagos_venta
    FOR EACH ROW EXECUTE FUNCTION fn_pago_venta_caja_en_turno();

CREATE TRIGGER ventas_solo_insercion
    BEFORE UPDATE OR DELETE ON ventas
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
CREATE TRIGGER detalle_venta_solo_insercion
    BEFORE UPDATE OR DELETE ON detalle_venta
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
CREATE TRIGGER pagos_venta_solo_insercion
    BEFORE UPDATE OR DELETE ON pagos_venta
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
