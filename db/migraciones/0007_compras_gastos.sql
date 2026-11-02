-- 0007_compras_gastos.sql — Grupo 8: compras a proveedores, gastos y toda
-- salida de plata (egresos). Va antes que crédito porque un abono puede
-- pagarse con un egreso (cruce de cuentas).

CREATE TABLE categorias_gasto (
    id      uuid    PRIMARY KEY DEFAULT uuidv7(),
    nombre  text    NOT NULL UNIQUE,
    activa  boolean NOT NULL DEFAULT true
);

CREATE TABLE compras (
    id              uuid        PRIMARY KEY DEFAULT uuidv7(),
    numero          bigint      GENERATED ALWAYS AS IDENTITY UNIQUE,
    proveedor_id    uuid        NOT NULL REFERENCES proveedores,
    usuario_id      uuid        NOT NULL REFERENCES usuarios,
    registrada_en   timestamptz NOT NULL DEFAULT now(),
    tipo_soporte    text        NOT NULL DEFAULT 'otro'
                                CHECK (tipo_soporte IN ('factura_electronica', 'factura', 'pos', 'otro')),
    numero_soporte  text        CHECK (btrim(numero_soporte) <> ''),
    cufe            text,
    fecha_soporte   date,
    notas           text,
    CONSTRAINT compras_soporte_unico UNIQUE (proveedor_id, numero_soporte),
    CONSTRAINT compras_fe_con_cufe CHECK (tipo_soporte <> 'factura_electronica' OR cufe IS NOT NULL)
);
COMMENT ON TABLE compras IS
    'Una compra a un proveedor con su soporte (une los antiguos pedidos y compras_proveedor). '
    'Total y cuenta por pagar se calculan en v_compras.';
COMMENT ON COLUMN compras.numero_soporte IS 'Número de la factura del proveedor; opcional para no inventarlo.';

CREATE TABLE compra_lineas (
    id           uuid          PRIMARY KEY DEFAULT uuidv7(),
    compra_id    uuid          NOT NULL REFERENCES compras ON DELETE CASCADE,
    producto_id  uuid          REFERENCES productos,
    insumo_id    uuid          REFERENCES insumos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    costo_unit   numeric(14,4) NOT NULL CHECK (costo_unit > 0),
    impuesto_id  uuid          REFERENCES impuestos,
    CONSTRAINT compra_lineas_producto_o_insumo CHECK ((producto_id IS NULL) <> (insumo_id IS NULL))
);
COMMENT ON TABLE compra_lineas IS
    'Producto o insumo, exactamente uno (los insumos no son artículos de venta, no hay supertipo común).';
COMMENT ON COLUMN compra_lineas.costo_unit IS 'Costo pagado por unidad, impuestos incluidos.';
COMMENT ON COLUMN compra_lineas.impuesto_id IS 'NULL si el soporte no discrimina impuesto (proveedor que no factura).';
CREATE INDEX compra_lineas_compra ON compra_lineas (compra_id);

CREATE TABLE egresos (
    id                  uuid        PRIMARY KEY DEFAULT uuidv7(),
    sesion_id           uuid        NOT NULL REFERENCES sesiones_caja,
    usuario_id          uuid        NOT NULL REFERENCES usuarios,
    compra_id           uuid        REFERENCES compras,
    categoria_gasto_id  uuid        REFERENCES categorias_gasto,
    tercero_id          uuid        REFERENCES terceros,
    concepto            text        NOT NULL CHECK (btrim(concepto) <> ''),
    creado_en           timestamptz NOT NULL DEFAULT now(),
    notas               text,
    CONSTRAINT egresos_compra_o_gasto CHECK ((compra_id IS NULL) <> (categoria_gasto_id IS NULL)),
    CONSTRAINT egresos_beneficiario_solo_en_gastos CHECK (compra_id IS NULL OR tercero_id IS NULL)
);
COMMENT ON TABLE egresos IS
    'Toda salida de plata: pago de una compra o gasto general. El monto es Σ pagos_egreso + Σ abonos '
    'cruzados (v_egresos); no se guarda.';
COMMENT ON COLUMN egresos.tercero_id IS 'A quién se le pagó (empleado, aliado). En pagos de compra es el proveedor de la compra.';
CREATE INDEX egresos_sesion ON egresos (sesion_id);
CREATE INDEX egresos_compra ON egresos (compra_id);

CREATE TABLE pagos_egreso (
    id              uuid          PRIMARY KEY DEFAULT uuidv7(),
    egreso_id       uuid          NOT NULL REFERENCES egresos,
    metodo_pago_id  uuid          NOT NULL REFERENCES metodos_pago,
    monto           numeric(14,2) NOT NULL CHECK (monto > 0)
);
COMMENT ON TABLE pagos_egreso IS 'Siempre se usa, también en gastos de un solo método.';
CREATE INDEX pagos_egreso_egreso ON pagos_egreso (egreso_id);

CREATE TABLE anulaciones_egreso (
    egreso_id   uuid        PRIMARY KEY REFERENCES egresos,
    sesion_id   uuid        NOT NULL REFERENCES sesiones_caja,
    usuario_id  uuid        NOT NULL REFERENCES usuarios,
    motivo      text        NOT NULL CHECK (btrim(motivo) <> ''),
    creado_en   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE anulaciones_egreso IS
    'Anular un egreso: la plata vuelve a las cajas en el turno de la anulación (sesion_id) y sus '
    'cruces dejan de contar. El turno original no se toca.';

CREATE TRIGGER egresos_turno_abierto
    BEFORE INSERT ON egresos
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto();
CREATE TRIGGER anulaciones_egreso_turno_abierto
    BEFORE INSERT ON anulaciones_egreso
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto();

CREATE FUNCTION fn_trg_turno_abierto_de_egreso() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_exigir_turno_abierto((SELECT sesion_id FROM egresos WHERE id = NEW.egreso_id));
    RETURN NEW;
END $$;
CREATE TRIGGER pagos_egreso_turno_abierto
    BEFORE INSERT ON pagos_egreso
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto_de_egreso();

CREATE FUNCTION fn_pago_egreso_caja_en_turno() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_exigir_caja_de_metodo((SELECT sesion_id FROM egresos WHERE id = NEW.egreso_id), NEW.metodo_pago_id);
    RETURN NEW;
END $$;
CREATE TRIGGER pagos_egreso_caja_en_turno
    BEFORE INSERT ON pagos_egreso
    FOR EACH ROW EXECUTE FUNCTION fn_pago_egreso_caja_en_turno();

-- La plata de un egreso anulado vuelve a sus cajas en el turno de la anulación.
CREATE FUNCTION fn_anulacion_cajas_en_turno() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_exigir_caja_de_metodo(NEW.sesion_id, metodo_pago_id)
       FROM pagos_egreso WHERE egreso_id = NEW.egreso_id;
    RETURN NEW;
END $$;
CREATE TRIGGER anulaciones_egreso_cajas_en_turno
    BEFORE INSERT ON anulaciones_egreso
    FOR EACH ROW EXECUTE FUNCTION fn_anulacion_cajas_en_turno();

CREATE TRIGGER egresos_solo_insercion
    BEFORE UPDATE OR DELETE ON egresos
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
CREATE TRIGGER pagos_egreso_solo_insercion
    BEFORE UPDATE OR DELETE ON pagos_egreso
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
CREATE TRIGGER anulaciones_egreso_solo_insercion
    BEFORE UPDATE OR DELETE ON anulaciones_egreso
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
