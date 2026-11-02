-- 0004_caja.sql — Grupo 4: cajas, turnos, conteos y movimientos de caja.
--
-- Regla del modelo: un turno cerrado no cambia. Nada guarda totales; el
-- esperado y la diferencia de cada caja se calculan (vista v_sesion_cajas).

CREATE TABLE cajas (
    id                  uuid    PRIMARY KEY DEFAULT uuidv7(),
    nombre              text    NOT NULL UNIQUE,
    usa_denominaciones  boolean NOT NULL DEFAULT false,
    activo              boolean NOT NULL DEFAULT true
);
COMMENT ON TABLE cajas IS 'Dónde está la plata (Efectivo, Digital…). Cada método de pago cae en una caja.';

-- conteo_denominaciones no distingue caja: solo el cajón físico se cuenta en billetes y monedas.
CREATE UNIQUE INDEX cajas_una_con_denominaciones ON cajas ((true)) WHERE usa_denominaciones;

CREATE TABLE metodos_pago (
    id       uuid    PRIMARY KEY DEFAULT uuidv7(),
    codigo   text    NOT NULL UNIQUE,
    nombre   text    NOT NULL,
    caja_id  uuid    NOT NULL REFERENCES cajas,
    activo   boolean NOT NULL DEFAULT true
);
COMMENT ON TABLE metodos_pago IS
    'Catálogo único de métodos de pago. Solo plata real: "mixto" se deduce y el fiado vive en cargos_credito.';

CREATE TABLE sesiones_caja (
    id           uuid        PRIMARY KEY DEFAULT uuidv7(),
    numero       bigint      GENERATED ALWAYS AS IDENTITY UNIQUE,
    abierta_por  uuid        NOT NULL REFERENCES usuarios,
    abierta_en   timestamptz NOT NULL DEFAULT now(),
    cerrada_por  uuid        REFERENCES usuarios,
    cerrada_en   timestamptz,
    notas        text,
    CONSTRAINT sesiones_caja_cierre_completo CHECK ((cerrada_por IS NULL) = (cerrada_en IS NULL)),
    CONSTRAINT sesiones_caja_cierre_posterior CHECK (cerrada_en IS NULL OR cerrada_en >= abierta_en)
);
COMMENT ON TABLE sesiones_caja IS 'Turno de caja. Cerrado (cerrada_en con valor) ya no cambia.';
COMMENT ON COLUMN sesiones_caja.numero IS 'Consecutivo legible ("Sesión #N").';

CREATE UNIQUE INDEX sesiones_caja_un_turno_abierto
    ON sesiones_caja ((true)) WHERE cerrada_en IS NULL;

CREATE TABLE sesion_cajas (
    sesion_id  uuid          NOT NULL REFERENCES sesiones_caja,
    caja_id    uuid          NOT NULL REFERENCES cajas,
    base       numeric(14,2) NOT NULL CHECK (base >= 0),
    contado    numeric(14,2) CHECK (contado >= 0),
    PRIMARY KEY (sesion_id, caja_id)
);
COMMENT ON TABLE sesion_cajas IS 'Base declarada al abrir y conteo al cerrar, por caja y turno.';
COMMENT ON COLUMN sesion_cajas.contado IS
    'NULL mientras el turno está abierto. En cajas con denominaciones es redundancia controlada: '
    'al cerrar debe ser igual a la suma de conteo_denominaciones.';

CREATE TABLE denominaciones (
    id      uuid    PRIMARY KEY DEFAULT uuidv7(),
    valor   integer NOT NULL UNIQUE CHECK (valor > 0),
    tipo    text    NOT NULL CHECK (tipo IN ('billete', 'moneda')),
    activa  boolean NOT NULL DEFAULT true
);

CREATE TABLE conteo_denominaciones (
    sesion_id        uuid    NOT NULL REFERENCES sesiones_caja,
    denominacion_id  uuid    NOT NULL REFERENCES denominaciones,
    cantidad         integer NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (sesion_id, denominacion_id)
);
COMMENT ON TABLE conteo_denominaciones IS 'Billetes y monedas contados al cerrar. Solo se guardan las que tienen cantidad.';

CREATE TABLE movimientos_caja (
    id               uuid          PRIMARY KEY DEFAULT uuidv7(),
    sesion_id        uuid          NOT NULL REFERENCES sesiones_caja,
    tipo             text          NOT NULL CHECK (tipo IN ('retiro', 'ingreso', 'traslado')),
    caja_origen_id   uuid          REFERENCES cajas,
    caja_destino_id  uuid          REFERENCES cajas,
    monto            numeric(14,2) NOT NULL CHECK (monto > 0),
    motivo           text          NOT NULL CHECK (btrim(motivo) <> ''),
    usuario_id       uuid          NOT NULL REFERENCES usuarios,
    creado_en        timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT movimientos_caja_cajas_segun_tipo CHECK (
           (tipo = 'retiro'   AND caja_origen_id IS NOT NULL AND caja_destino_id IS NULL)
        OR (tipo = 'ingreso'  AND caja_origen_id IS NULL     AND caja_destino_id IS NOT NULL)
        OR (tipo = 'traslado' AND caja_origen_id IS NOT NULL AND caja_destino_id IS NOT NULL
                              AND caja_origen_id <> caja_destino_id))
);
COMMENT ON TABLE movimientos_caja IS
    'Retiros, ingresos y traslados (consignar efectivo al banco = traslado Efectivo → Digital). '
    'Un error se corrige con el movimiento contrario.';

-- ── Turnos abiertos y cerrados ──────────────────────────────────────────────

-- Lanza error si el turno no existe o ya está cerrado. El bloqueo FOR SHARE
-- hace que un cierre simultáneo espere a que esta transacción termine (y al
-- revés): así nada entra a un turno mientras se cierra. La migración de datos
-- históricos (que inserta en turnos ya cerrados) puede saltarse esta revisión
-- con SET LOCAL elg.migracion = 'on'.
CREATE FUNCTION fn_exigir_turno_abierto(p_sesion uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_cerrada timestamptz;
BEGIN
    IF p_sesion IS NULL OR current_setting('elg.migracion', true) = 'on' THEN
        RETURN;
    END IF;
    SELECT cerrada_en INTO v_cerrada FROM sesiones_caja WHERE id = p_sesion FOR SHARE;
    IF NOT FOUND THEN
        RETURN;  -- la FK reporta el error
    END IF;
    IF v_cerrada IS NOT NULL THEN
        RAISE EXCEPTION 'El turno de caja ya está cerrado: no admite cambios'
            USING ERRCODE = 'check_violation';
    END IF;
END $$;

-- La plata solo entra o sale de cajas registradas en el turno (con su base):
-- si no, quedaría fuera del esperado de v_sesion_cajas y nadie la cuadraría.
CREATE FUNCTION fn_exigir_caja_en_turno(p_sesion uuid, p_caja uuid) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF p_sesion IS NULL OR p_caja IS NULL THEN
        RETURN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM sesion_cajas WHERE sesion_id = p_sesion AND caja_id = p_caja) THEN
        RAISE EXCEPTION 'La caja % no está registrada en el turno: ábrela con su base antes de moverle plata',
                        (SELECT nombre FROM cajas WHERE id = p_caja)
            USING ERRCODE = 'check_violation';
    END IF;
END $$;

CREATE FUNCTION fn_exigir_caja_de_metodo(p_sesion uuid, p_metodo uuid) RETURNS void
LANGUAGE sql AS $$
    SELECT fn_exigir_caja_en_turno(p_sesion, (SELECT caja_id FROM metodos_pago WHERE id = p_metodo))
$$;

-- Trigger genérico para tablas con columna sesion_id.
CREATE FUNCTION fn_trg_turno_abierto() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM fn_exigir_turno_abierto(OLD.sesion_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM fn_exigir_turno_abierto(NEW.sesion_id);
        RETURN NEW;
    END IF;
    RETURN OLD;
END $$;

CREATE TRIGGER sesion_cajas_turno_abierto
    BEFORE INSERT OR UPDATE OR DELETE ON sesion_cajas
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto();
CREATE TRIGGER conteo_denominaciones_turno_abierto
    BEFORE INSERT OR UPDATE OR DELETE ON conteo_denominaciones
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto();
CREATE TRIGGER movimientos_caja_turno_abierto
    BEFORE INSERT ON movimientos_caja
    FOR EACH ROW EXECUTE FUNCTION fn_trg_turno_abierto();
CREATE FUNCTION fn_movimiento_cajas_en_turno() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_exigir_caja_en_turno(NEW.sesion_id, NEW.caja_origen_id);
    PERFORM fn_exigir_caja_en_turno(NEW.sesion_id, NEW.caja_destino_id);
    RETURN NEW;
END $$;
CREATE TRIGGER movimientos_caja_cajas_en_turno
    BEFORE INSERT ON movimientos_caja
    FOR EACH ROW EXECUTE FUNCTION fn_movimiento_cajas_en_turno();
CREATE TRIGGER movimientos_caja_solo_insercion
    BEFORE UPDATE OR DELETE ON movimientos_caja
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();

-- Un turno solo pasa de abierto a cerrado; cerrado no cambia y nunca se borra.
-- Al cerrar: toda caja del turno tiene contado, y en cajas con denominaciones
-- el contado es igual a lo contado en billetes y monedas.
CREATE FUNCTION fn_sesion_caja_transicion() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    r record;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Los turnos de caja no se borran' USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.cerrada_en IS NOT NULL AND current_setting('elg.migracion', true) IS DISTINCT FROM 'on' THEN
            RAISE EXCEPTION 'Un turno se abre abierto: se cierra después con su conteo'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.cerrada_en IS NOT NULL THEN
        RAISE EXCEPTION 'El turno #% ya está cerrado: no admite cambios', OLD.numero
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.abierta_por <> OLD.abierta_por OR NEW.abierta_en <> OLD.abierta_en THEN
        RAISE EXCEPTION 'La apertura de un turno no se edita' USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.cerrada_en IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM sesion_cajas WHERE sesion_id = NEW.id) THEN
            RAISE EXCEPTION 'El turno #% no tiene cajas registradas', NEW.numero
                USING ERRCODE = 'check_violation';
        END IF;
        FOR r IN
            SELECT c.nombre, c.usa_denominaciones, sc.contado,
                   (SELECT COALESCE(sum(d.valor::numeric * cd.cantidad), 0)
                      FROM conteo_denominaciones cd
                      JOIN denominaciones d ON d.id = cd.denominacion_id
                     WHERE cd.sesion_id = NEW.id) AS suma_denominaciones
              FROM sesion_cajas sc
              JOIN cajas c ON c.id = sc.caja_id
             WHERE sc.sesion_id = NEW.id
        LOOP
            IF r.contado IS NULL THEN
                RAISE EXCEPTION 'Falta el conteo de la caja % para cerrar el turno', r.nombre
                    USING ERRCODE = 'check_violation';
            END IF;
            IF r.usa_denominaciones AND r.contado <> r.suma_denominaciones THEN
                RAISE EXCEPTION 'El contado de % (%) no coincide con las denominaciones (%)',
                                r.nombre, r.contado, r.suma_denominaciones
                    USING ERRCODE = 'check_violation';
            END IF;
        END LOOP;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER sesiones_caja_transicion
    BEFORE INSERT OR UPDATE OR DELETE ON sesiones_caja
    FOR EACH ROW EXECUTE FUNCTION fn_sesion_caja_transicion();
