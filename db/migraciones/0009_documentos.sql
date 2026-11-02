-- 0009_documentos.sql — Grupo 9: documentos fiscales (factura electrónica,
-- documento equivalente POS, nota crédito) y documentos comerciales
-- (cotización → orden de pedido → remisión).
--
-- La facturación electrónica aún no se usa (decisión del contador) pero queda
-- lista: un documento es opcional por venta y resoluciones arranca vacía.

CREATE TABLE resoluciones (
    id                  uuid    PRIMARY KEY DEFAULT uuidv7(),
    tipo_documento      text    NOT NULL CHECK (tipo_documento IN ('FEV', 'POS', 'NC')),
    prefijo             text    NOT NULL CHECK (prefijo ~ '^[A-Z0-9]{1,4}$'),
    numero_resolucion   text,
    rango_inicio        bigint  NOT NULL CHECK (rango_inicio > 0),
    rango_fin           bigint  NOT NULL,
    consecutivo_actual  bigint  NOT NULL,
    fecha_autorizacion  date    NOT NULL,
    fecha_vencimiento   date    NOT NULL,
    clave_tecnica       text,
    activa              boolean NOT NULL DEFAULT true,
    CONSTRAINT resoluciones_rango CHECK (rango_fin >= rango_inicio),
    CONSTRAINT resoluciones_consecutivo_en_rango
        CHECK (consecutivo_actual BETWEEN rango_inicio - 1 AND rango_fin),
    CONSTRAINT resoluciones_vigencia CHECK (fecha_vencimiento >= fecha_autorizacion),
    UNIQUE (prefijo, rango_inicio)
);
COMMENT ON COLUMN resoluciones.consecutivo_actual IS
    'Último número usado (arranca en rango_inicio - 1). Se bloquea por fila (FOR UPDATE) al emitir.';

CREATE TABLE documentos_fiscales (
    id                         uuid        PRIMARY KEY DEFAULT uuidv7(),
    tipo                       text        NOT NULL CHECK (tipo IN ('FEV', 'POS', 'NC')),
    resolucion_id              uuid        REFERENCES resoluciones,
    prefijo                    text        NOT NULL,
    consecutivo                bigint      NOT NULL CHECK (consecutivo > 0),
    venta_id                   uuid        REFERENCES ventas,
    documento_referencia_id    uuid        REFERENCES documentos_fiscales,
    adquiriente_id             uuid        NOT NULL REFERENCES terceros,
    adq_nombre                 text        NOT NULL,
    adq_tipo_identificacion    text,
    adq_numero_identificacion  text,
    adq_direccion              text,
    adq_email                  text,
    motivo                     text,
    emitido_en                 timestamptz NOT NULL DEFAULT now(),
    estado                     text        NOT NULL DEFAULT 'pendiente'
                                           CHECK (estado IN ('local', 'pendiente', 'en_proceso', 'aceptado',
                                                             'rechazado', 'contingencia', 'error')),
    cufe                       text        UNIQUE,
    proveedor                  text,
    track_id                   text,
    pdf_url                    text,
    xml_url                    text,
    mensaje                    text,
    CONSTRAINT documentos_fiscales_numero_unico UNIQUE (prefijo, consecutivo),
    CONSTRAINT documentos_fiscales_segun_tipo CHECK (
           (tipo IN ('FEV', 'POS') AND venta_id IS NOT NULL AND documento_referencia_id IS NULL)
        OR (tipo = 'NC' AND venta_id IS NULL AND documento_referencia_id IS NOT NULL AND motivo IS NOT NULL)),
    CONSTRAINT documentos_fiscales_local_sin_resolucion CHECK (resolucion_id IS NOT NULL OR estado = 'local')
);
COMMENT ON TABLE documentos_fiscales IS
    'Une las facturas del POS y del backend DIAN. Ítems y totales salen de la venta. "Anulado" = '
    'tiene una nota crédito aceptada (v_documentos_fiscales). Por ahora solo nota crédito total.';
COMMENT ON COLUMN documentos_fiscales.adq_nombre IS
    'Foto legal del adquiriente tal como se envió (adq_*): no cambia si después se edita el tercero.';
COMMENT ON COLUMN documentos_fiscales.resolucion_id IS 'NULL = documento solo local (estado local), sin transmitir a la DIAN.';
CREATE INDEX documentos_fiscales_venta ON documentos_fiscales (venta_id);
CREATE INDEX documentos_fiscales_referencia ON documentos_fiscales (documento_referencia_id);

CREATE TABLE eventos_documento (
    id                 uuid        PRIMARY KEY DEFAULT uuidv7(),
    documento_id       uuid        NOT NULL REFERENCES documentos_fiscales ON DELETE CASCADE,
    estado             text        NOT NULL,
    recibido_en        timestamptz NOT NULL DEFAULT now(),
    evento_externo_id  text        UNIQUE,
    payload            jsonb
);
COMMENT ON TABLE eventos_documento IS
    'Historial de estados del proveedor tecnológico (webhook o consulta). evento_externo_id único: '
    'un webhook repetido no se procesa dos veces.';

-- Una NC corrige una FEV o POS (no otra NC). Una venta tiene a lo sumo una
-- factura vigente: solo se emite otra si las anteriores tienen NC aceptada o
-- nunca fueron válidas (rechazadas por la DIAN o con error de envío).
CREATE FUNCTION fn_documentos_fiscales_coherencia() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.tipo = 'NC' THEN
        IF (SELECT tipo FROM documentos_fiscales WHERE id = NEW.documento_referencia_id) = 'NC' THEN
            RAISE EXCEPTION 'Una nota crédito corrige una factura o documento POS, no otra nota crédito'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        PERFORM 1 FROM ventas WHERE id = NEW.venta_id FOR UPDATE;  -- serializa emisiones de la misma venta
        IF EXISTS (
            SELECT 1 FROM documentos_fiscales d
             WHERE d.venta_id = NEW.venta_id AND d.id <> NEW.id
               AND d.estado NOT IN ('rechazado', 'error')
               AND NOT EXISTS (SELECT 1 FROM documentos_fiscales nc
                                WHERE nc.documento_referencia_id = d.id
                                  AND nc.tipo = 'NC' AND nc.estado = 'aceptado'))
        THEN
            RAISE EXCEPTION 'La venta ya tiene un documento fiscal vigente: anúlalo con una nota crédito antes de emitir otro'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER documentos_fiscales_coherencia
    BEFORE INSERT ON documentos_fiscales
    FOR EACH ROW EXECUTE FUNCTION fn_documentos_fiscales_coherencia();

-- ── Documentos comerciales ──────────────────────────────────────────────────

CREATE SEQUENCE documentos_comerciales_cotizacion_seq;
CREATE SEQUENCE documentos_comerciales_orden_pedido_seq;
CREATE SEQUENCE documentos_comerciales_remision_seq;

CREATE TABLE documentos_comerciales (
    id               uuid          PRIMARY KEY DEFAULT uuidv7(),
    tipo             text          NOT NULL CHECK (tipo IN ('cotizacion', 'orden_pedido', 'remision')),
    numero           bigint        NOT NULL,
    cliente_id       uuid          REFERENCES clientes,
    usuario_id       uuid          NOT NULL REFERENCES usuarios,
    creado_en        timestamptz   NOT NULL DEFAULT now(),
    descuento        numeric(14,2) NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    vigente_hasta    date,
    doc_origen_id    uuid          REFERENCES documentos_comerciales,
    venta_id         uuid          REFERENCES ventas,
    descartado_en    timestamptz,
    motivo_descarte  text          CHECK (motivo_descarte IN ('rechazado', 'anulado')),
    notas            text,
    CONSTRAINT documentos_comerciales_numero_por_tipo UNIQUE (tipo, numero),
    CONSTRAINT documentos_comerciales_vigencia_solo_cotizacion CHECK (vigente_hasta IS NULL OR tipo = 'cotizacion'),
    CONSTRAINT documentos_comerciales_descarte_completo CHECK ((descartado_en IS NULL) = (motivo_descarte IS NULL))
);
COMMENT ON TABLE documentos_comerciales IS
    'Cotización → orden de pedido → remisión → venta. El estado (vigente, vencida, aceptada, entregada, '
    'facturada, rechazada, anulada) y los totales se calculan en v_documentos_comerciales.';
COMMENT ON COLUMN documentos_comerciales.numero IS 'Consecutivo propio de cada tipo, asignado por trigger.';

CREATE TABLE documento_items (
    id            uuid          PRIMARY KEY DEFAULT uuidv7(),
    documento_id  uuid          NOT NULL REFERENCES documentos_comerciales ON DELETE CASCADE,
    articulo_id   uuid          REFERENCES articulos,
    descripcion   text          NOT NULL CHECK (btrim(descripcion) <> ''),
    cantidad      numeric(12,3) NOT NULL CHECK (cantidad > 0),
    precio_unit   numeric(14,2) NOT NULL CHECK (precio_unit >= 0),
    impuesto_id   uuid          REFERENCES impuestos
);
COMMENT ON COLUMN documento_items.descripcion IS 'Lo que vio el cliente en el papel. Sin articulo_id es una línea de texto libre.';
CREATE INDEX documento_items_documento ON documento_items (documento_id);

CREATE FUNCTION fn_documentos_comerciales_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_origen text;
BEGIN
    IF NEW.numero IS NULL THEN
        NEW.numero := nextval(format('documentos_comerciales_%s_seq', NEW.tipo)::regclass);
    END IF;
    IF NEW.doc_origen_id IS NOT NULL THEN
        SELECT tipo INTO v_origen FROM documentos_comerciales WHERE id = NEW.doc_origen_id;
        IF NOT ((v_origen = 'cotizacion' AND NEW.tipo = 'orden_pedido')
             OR (v_origen = 'orden_pedido' AND NEW.tipo = 'remision')) THEN
            RAISE EXCEPTION 'Un(a) % no puede salir de un(a) %: la cadena es cotización → orden de pedido → remisión',
                            NEW.tipo, v_origen
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER documentos_comerciales_insert
    BEFORE INSERT ON documentos_comerciales
    FOR EACH ROW EXECUTE FUNCTION fn_documentos_comerciales_insert();
