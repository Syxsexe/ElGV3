-- 0010_torneos.sql — Grupo 10: torneos de TCG, sus jugadores y premios.
--
-- La plata de las inscripciones es una venta (una línea del artículo servicio
-- "Inscripción a torneo"); cada jugador apunta a su pago o a su cargo fiado,
-- o a ninguno si entró gratis. Recaudado, costo de premios, ganancia y número
-- de jugadores se calculan en v_torneos.

CREATE TABLE juegos (
    id      uuid    PRIMARY KEY DEFAULT uuidv7(),
    nombre  text    NOT NULL UNIQUE,
    activo  boolean NOT NULL DEFAULT true
);

CREATE TABLE torneos (
    id            uuid        PRIMARY KEY DEFAULT uuidv7(),
    nombre        text        NOT NULL CHECK (btrim(nombre) <> ''),
    juego_id      uuid        NOT NULL REFERENCES juegos,
    realizado_en  timestamptz NOT NULL DEFAULT now(),
    usuario_id    uuid        NOT NULL REFERENCES usuarios,
    venta_id      uuid        UNIQUE REFERENCES ventas,
    notas         text
);
COMMENT ON COLUMN torneos.venta_id IS 'Venta de las inscripciones; NULL si nadie pagó (todos gratis).';

CREATE TABLE torneo_participantes (
    id             uuid PRIMARY KEY DEFAULT uuidv7(),
    torneo_id      uuid NOT NULL REFERENCES torneos,
    cliente_id     uuid REFERENCES clientes,
    alias          text CHECK (btrim(alias) <> ''),
    pago_venta_id  uuid UNIQUE REFERENCES pagos_venta,
    cargo_id       uuid UNIQUE REFERENCES cargos_credito,
    CONSTRAINT torneo_participantes_cliente_o_alias CHECK ((cliente_id IS NULL) <> (alias IS NULL)),
    CONSTRAINT torneo_participantes_pago_o_fiado CHECK (pago_venta_id IS NULL OR cargo_id IS NULL),
    CONSTRAINT torneo_participantes_fiado_con_cliente CHECK (cargo_id IS NULL OR cliente_id IS NOT NULL),
    CONSTRAINT torneo_participantes_una_inscripcion UNIQUE (torneo_id, cliente_id)
);
COMMENT ON TABLE torneo_participantes IS
    'Sin pago_venta_id ni cargo_id = inscripción gratis. El monto y el método salen del pago o del cargo.';

CREATE TABLE torneo_premios (
    torneo_id    uuid          NOT NULL REFERENCES torneos,
    producto_id  uuid          NOT NULL REFERENCES productos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    costo_unit   numeric(14,2) NOT NULL CHECK (costo_unit >= 0),
    PRIMARY KEY (torneo_id, producto_id)
);
COMMENT ON TABLE torneo_premios IS 'Productos entregados como premio (se reparten entre todos, no se ligan a jugadores).';
COMMENT ON COLUMN torneo_premios.costo_unit IS 'Foto del costo del producto al entregarlo.';

-- El pago o el cargo de un jugador pertenecen a la venta de su torneo, y el
-- cargo es del mismo cliente.
CREATE FUNCTION fn_torneo_participante_coherente() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_venta uuid := (SELECT venta_id FROM torneos WHERE id = NEW.torneo_id);
BEGIN
    IF NEW.pago_venta_id IS NOT NULL
       AND (SELECT venta_id FROM pagos_venta WHERE id = NEW.pago_venta_id) IS DISTINCT FROM v_venta THEN
        RAISE EXCEPTION 'El pago del jugador no pertenece a la venta del torneo' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.cargo_id IS NOT NULL THEN
        IF (SELECT venta_id FROM cargos_credito WHERE id = NEW.cargo_id) IS DISTINCT FROM v_venta THEN
            RAISE EXCEPTION 'El cargo fiado del jugador no pertenece a la venta del torneo' USING ERRCODE = 'check_violation';
        END IF;
        IF (SELECT cliente_id FROM cargos_credito WHERE id = NEW.cargo_id) <> NEW.cliente_id THEN
            RAISE EXCEPTION 'El cargo fiado es de otro cliente' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER torneo_participantes_coherente
    BEFORE INSERT OR UPDATE ON torneo_participantes
    FOR EACH ROW EXECUTE FUNCTION fn_torneo_participante_coherente();
