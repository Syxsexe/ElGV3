-- 0003_catalogo.sql — Grupo 2: lo que se vende (artículos y sus subtipos) y
-- lo que se cocina (insumos, recetas y preparaciones).

CREATE TABLE categorias (
    id      uuid PRIMARY KEY DEFAULT uuidv7(),
    nombre  text NOT NULL UNIQUE,
    tipo    text NOT NULL CHECK (tipo IN ('tienda', 'cocina'))
);
COMMENT ON COLUMN categorias.tipo IS 'Propone el impuesto del artículo (tienda → IVA 19, cocina → INC 8) y separa reportes.';

CREATE TABLE unidades_medida (
    id       uuid PRIMARY KEY DEFAULT uuidv7(),
    simbolo  text NOT NULL UNIQUE,
    nombre   text NOT NULL
);

CREATE TABLE impuestos (
    id       uuid         PRIMARY KEY DEFAULT uuidv7(),
    codigo   text         NOT NULL UNIQUE,
    nombre   text         NOT NULL,
    tributo  text         NOT NULL CHECK (tributo IN ('IVA', 'INC')),
    tarifa   numeric(5,2) NOT NULL CHECK (tarifa >= 0 AND tarifa < 100)
);
COMMENT ON TABLE impuestos IS
    'Filas inmutables (codigo, tributo y tarifa no se editan): si la ley cambia una tarifa se crea '
    'una fila nueva, así impuesto_id en las líneas funciona como foto histórica.';
COMMENT ON COLUMN impuestos.tarifa IS 'Porcentaje (19.00 = 19%). Los precios ya incluyen el impuesto.';

CREATE FUNCTION fn_impuesto_inmutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.codigo <> OLD.codigo OR NEW.tributo <> OLD.tributo OR NEW.tarifa <> OLD.tarifa THEN
        RAISE EXCEPTION 'El impuesto % no se edita: crea una fila nueva con la tarifa nueva', OLD.codigo
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER impuestos_inmutables
    BEFORE UPDATE ON impuestos
    FOR EACH ROW EXECUTE FUNCTION fn_impuesto_inmutable();

-- ── Supertipo artículo y sus subtipos 1:1 ───────────────────────────────────
-- Cada subtipo lleva una columna tipo fija y una FK compuesta a articulos(id, tipo):
-- así un combo no puede colgar de un artículo tipo producto, y el tipo de un
-- artículo no puede cambiar mientras tenga su fila de subtipo.

CREATE TABLE articulos (
    id            uuid          PRIMARY KEY DEFAULT uuidv7(),
    tipo          text          NOT NULL CHECK (tipo IN ('producto', 'combo', 'adicional', 'servicio')),
    nombre        text          NOT NULL CHECK (btrim(nombre) <> ''),
    categoria_id  uuid          NOT NULL REFERENCES categorias,
    impuesto_id   uuid          NOT NULL REFERENCES impuestos,
    precio_venta  numeric(14,2) NOT NULL CHECK (precio_venta >= 0),
    activo        boolean       NOT NULL DEFAULT true,
    UNIQUE (id, tipo)
);
COMMENT ON TABLE articulos IS
    'Todo lo que se vende. Las líneas de venta, cuenta y documento apuntan aquí con un solo articulo_id.';

CREATE TABLE productos (
    articulo_id   uuid          PRIMARY KEY,
    tipo          text          NOT NULL DEFAULT 'producto' CHECK (tipo = 'producto'),
    codigo        text          UNIQUE,
    precio_costo  numeric(14,2) NOT NULL DEFAULT 0 CHECK (precio_costo >= 0),
    stock         numeric(12,3) NOT NULL DEFAULT 0,
    stock_minimo  numeric(12,3) NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
    creado_en     timestamptz   NOT NULL DEFAULT now(),
    FOREIGN KEY (articulo_id, tipo) REFERENCES articulos (id, tipo)
);
COMMENT ON COLUMN productos.precio_costo IS
    'En platos con receta es caché (redundancia controlada): un trigger lo recalcula desde la receta.';
COMMENT ON COLUMN productos.stock IS 'Solo tiene sentido en productos de tienda; la cocina trabaja por costo.';

CREATE TABLE combos (
    articulo_id  uuid PRIMARY KEY,
    tipo         text NOT NULL DEFAULT 'combo' CHECK (tipo = 'combo'),
    descripcion  text,
    FOREIGN KEY (articulo_id, tipo) REFERENCES articulos (id, tipo)
);

CREATE TABLE combo_productos (
    combo_id     uuid          NOT NULL REFERENCES combos ON DELETE CASCADE,
    producto_id  uuid          NOT NULL REFERENCES productos,
    cantidad     numeric(12,3) NOT NULL DEFAULT 1 CHECK (cantidad > 0),
    PRIMARY KEY (combo_id, producto_id)
);

CREATE TABLE insumos (
    id                uuid          PRIMARY KEY DEFAULT uuidv7(),
    nombre            text          NOT NULL UNIQUE,
    unidad_medida_id  uuid          NOT NULL REFERENCES unidades_medida,
    costo_unitario    numeric(14,4) NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
    activo            boolean       NOT NULL DEFAULT true
);
COMMENT ON TABLE insumos IS 'Ingredientes de cocina. Sin stock: el modelo de cocina es de costo, no de inventario.';
COMMENT ON COLUMN insumos.costo_unitario IS 'Costo por unidad de medida (ej. $/g); 4 decimales porque suele ser fracción de peso.';

CREATE TABLE adicionales (
    articulo_id  uuid          PRIMARY KEY,
    tipo         text          NOT NULL DEFAULT 'adicional' CHECK (tipo = 'adicional'),
    insumo_id    uuid          NOT NULL REFERENCES insumos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    FOREIGN KEY (articulo_id, tipo) REFERENCES articulos (id, tipo)
);
COMMENT ON TABLE adicionales IS 'Extras que se venden (queso extra, tocineta extra): cuánto insumo lleva la porción.';

CREATE TABLE servicios (
    articulo_id  uuid PRIMARY KEY,
    tipo         text NOT NULL DEFAULT 'servicio' CHECK (tipo = 'servicio'),
    FOREIGN KEY (articulo_id, tipo) REFERENCES articulos (id, tipo)
);
COMMENT ON TABLE servicios IS 'Servicios que se venden (inscripción a torneo). Sin atributos propios por ahora.';

CREATE TABLE receta_insumos (
    producto_id  uuid          NOT NULL REFERENCES productos ON DELETE CASCADE,
    insumo_id    uuid          NOT NULL REFERENCES insumos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (producto_id, insumo_id)
);

CREATE TABLE preparaciones (
    insumo_id    uuid          PRIMARY KEY REFERENCES insumos,
    rendimiento  numeric(12,3) NOT NULL CHECK (rendimiento > 0)
);
COMMENT ON TABLE preparaciones IS 'Insumos que se fabrican con otros (salsas, adobo, rellenos). rendimiento = cuánto produce un lote.';

CREATE TABLE receta_preparacion (
    preparacion_id  uuid          NOT NULL REFERENCES preparaciones,
    insumo_id       uuid          NOT NULL REFERENCES insumos,
    cantidad        numeric(12,3) NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (preparacion_id, insumo_id),
    CONSTRAINT receta_preparacion_no_se_contiene CHECK (preparacion_id <> insumo_id)
);

-- ── Coherencia del supertipo ────────────────────────────────────────────────

-- Todo artículo tiene la fila de su subtipo. Se revisa al confirmar la
-- transacción (se insertan en dos pasos) al crear el artículo, al cambiarle el
-- tipo y al borrar o mover una fila de subtipo.
CREATE FUNCTION fn_verificar_subtipo(p_articulo uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_nombre text;
    v_tipo   text;
    v_existe boolean;
BEGIN
    SELECT nombre, tipo INTO v_nombre, v_tipo FROM articulos WHERE id = p_articulo;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I WHERE articulo_id = $1)',
                   CASE v_tipo WHEN 'producto' THEN 'productos'
                               WHEN 'combo' THEN 'combos'
                               WHEN 'adicional' THEN 'adicionales'
                               ELSE 'servicios' END)
        INTO v_existe USING p_articulo;
    IF NOT v_existe THEN
        RAISE EXCEPTION 'El artículo "%" (tipo %) no tiene su fila de subtipo', v_nombre, v_tipo
            USING ERRCODE = 'check_violation';
    END IF;
END $$;

CREATE FUNCTION fn_trg_verificar_subtipo() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- IF y no CASE: plpgsql resuelve OLD.articulo_id aunque la rama no aplique.
    IF TG_TABLE_NAME = 'articulos' THEN
        PERFORM fn_verificar_subtipo(NEW.id);
    ELSE
        PERFORM fn_verificar_subtipo(OLD.articulo_id);
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER articulos_tienen_subtipo
    AFTER INSERT OR UPDATE OF tipo ON articulos
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_verificar_subtipo();
CREATE CONSTRAINT TRIGGER productos_subtipo_obligatorio
    AFTER UPDATE OR DELETE ON productos DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_verificar_subtipo();
CREATE CONSTRAINT TRIGGER combos_subtipo_obligatorio
    AFTER UPDATE OR DELETE ON combos DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_verificar_subtipo();
CREATE CONSTRAINT TRIGGER adicionales_subtipo_obligatorio
    AFTER UPDATE OR DELETE ON adicionales DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_verificar_subtipo();
CREATE CONSTRAINT TRIGGER servicios_subtipo_obligatorio
    AFTER UPDATE OR DELETE ON servicios DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_trg_verificar_subtipo();

-- Todo combo va con INC (decisión del contador: el combo es servicio de restaurante).
CREATE FUNCTION fn_combo_con_inc() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.tipo = 'combo'
       AND (SELECT tributo FROM impuestos WHERE id = NEW.impuesto_id) <> 'INC' THEN
        RAISE EXCEPTION 'El combo "%" debe llevar un impuesto INC', NEW.nombre
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER articulos_combo_con_inc
    BEFORE INSERT OR UPDATE OF tipo, impuesto_id ON articulos
    FOR EACH ROW EXECUTE FUNCTION fn_combo_con_inc();
