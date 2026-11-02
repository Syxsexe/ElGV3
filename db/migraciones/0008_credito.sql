-- 0008_credito.sql — Grupo 7: fiado. Lo que se fía (cargos), lo que se paga
-- (abonos, aplicados a cargos concretos) y lo que se perdona (condonaciones).
-- Saldo, pendiente, vencido y cupo disponible se calculan (v_cargos_credito,
-- v_saldos_clientes).

CREATE TABLE cargos_credito (
    id          uuid          PRIMARY KEY DEFAULT uuidv7(),
    cliente_id  uuid          NOT NULL REFERENCES clientes,
    venta_id    uuid          REFERENCES ventas,
    monto       numeric(14,2) NOT NULL CHECK (monto > 0),
    creado_en   timestamptz   NOT NULL DEFAULT now(),
    vence_en    date          NOT NULL,
    notas       text,
    CONSTRAINT cargos_credito_con_origen CHECK (venta_id IS NOT NULL OR notas IS NOT NULL)
);
COMMENT ON COLUMN cargos_credito.venta_id IS
    'No es único: la venta de un torneo genera un cargo por cada jugador inscrito a crédito.';
COMMENT ON COLUMN cargos_credito.vence_en IS 'Foto de los dias_credito del cliente al momento del cargo.';
CREATE INDEX cargos_credito_cliente ON cargos_credito (cliente_id);
CREATE INDEX cargos_credito_venta ON cargos_credito (venta_id);

CREATE TABLE abonos_credito (
    id              uuid          PRIMARY KEY DEFAULT uuidv7(),
    cliente_id      uuid          NOT NULL REFERENCES clientes,
    sesion_id       uuid          REFERENCES sesiones_caja,
    metodo_pago_id  uuid          REFERENCES metodos_pago,
    egreso_id       uuid          REFERENCES egresos,
    usuario_id      uuid          NOT NULL REFERENCES usuarios,
    monto           numeric(14,2) NOT NULL CHECK (monto > 0),
    creado_en       timestamptz   NOT NULL DEFAULT now(),
    notas           text,
    CONSTRAINT abonos_credito_plata_o_cruce CHECK (
           (sesion_id IS NOT NULL AND metodo_pago_id IS NOT NULL AND egreso_id IS NULL)
        OR (sesion_id IS NULL     AND metodo_pago_id IS NULL     AND egreso_id IS NOT NULL))
);
COMMENT ON TABLE abonos_credito IS
    'Un pago real del cliente, una sola fila aunque cubra varios cargos. Con plata (turno + método) '
    'o con cruce de cuentas (egreso_id: se le descuenta la deuda de lo que el negocio le paga).';
COMMENT ON COLUMN abonos_credito.cliente_id IS
    'Redundancia controlada: coincide con el cliente de los cargos a los que se aplica (trigger).';
CREATE INDEX abonos_credito_cliente ON abonos_credito (cliente_id);
CREATE INDEX abonos_credito_egreso ON abonos_credito (egreso_id);

CREATE TABLE abono_aplicaciones (
    abono_id  uuid          NOT NULL REFERENCES abonos_credito,
    cargo_id  uuid          NOT NULL REFERENCES cargos_credito,
    monto     numeric(14,2) NOT NULL CHECK (monto > 0),
    PRIMARY KEY (abono_id, cargo_id)
);
COMMENT ON TABLE abono_aplicaciones IS 'A qué cargos se aplica cada abono. No hay abono general: todo peso queda aplicado.';
CREATE INDEX abono_aplicaciones_cargo ON abono_aplicaciones (cargo_id);

CREATE TABLE condonaciones_credito (
    id              uuid          PRIMARY KEY DEFAULT uuidv7(),
    cargo_id        uuid          NOT NULL REFERENCES cargos_credito,
    monto           numeric(14,2) NOT NULL CHECK (monto > 0),
    motivo          text          NOT NULL CHECK (btrim(motivo) <> ''),
    autorizada_por  uuid          NOT NULL REFERENCES usuarios,
    creado_en       timestamptz   NOT NULL DEFAULT now()
);
COMMENT ON TABLE condonaciones_credito IS
    'Perdonar deuda o corregir un cargo mal hecho, sin pasar por caja. Requiere el permiso creditos.condonar (lo valida la app).';
CREATE INDEX condonaciones_credito_cargo ON condonaciones_credito (cargo_id);

CREATE TRIGGER abonos_credito_turno_abierto
    BEFORE INSERT ON abonos_credito
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto();

CREATE FUNCTION fn_abono_caja_en_turno() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_exigir_caja_de_metodo(NEW.sesion_id, NEW.metodo_pago_id);
    RETURN NEW;
END $$;
CREATE TRIGGER abonos_credito_caja_en_turno
    BEFORE INSERT ON abonos_credito
    FOR EACH ROW EXECUTE FUNCTION fn_abono_caja_en_turno();

CREATE TRIGGER cargos_credito_solo_insercion
    BEFORE UPDATE OR DELETE ON cargos_credito
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
CREATE TRIGGER abonos_credito_solo_insercion
    BEFORE UPDATE OR DELETE ON abonos_credito
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
CREATE TRIGGER abono_aplicaciones_solo_insercion
    BEFORE UPDATE OR DELETE ON abono_aplicaciones
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
CREATE TRIGGER condonaciones_credito_solo_insercion
    BEFORE UPDATE OR DELETE ON condonaciones_credito
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
