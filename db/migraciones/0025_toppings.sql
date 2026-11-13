-- 0025_toppings.sql — Toppings de los platos.
--
-- Un plato de cocina puede aceptar toppings: adicionales (insumo + porción +
-- precio) que el cliente agrega o no al pedirlo, varios a la vez, una vez cada
-- uno (ej. ramen + huevo duro + queso). El precio es el del adicional, el
-- mismo en cualquier plato.
--
-- Como lo elegido en un combo (0024), los toppings quedan como foto pegada a
-- la línea (de venta o de cuenta) con el precio cobrado: editar el plato o el
-- adicional después no cambia lo ya vendido. En una venta se guardan ANTES que
-- su línea (FK diferida) para que el trigger de stock, que es por sentencia,
-- descuente en un solo paso el plato y sus toppings (sus insumos pueden quedar
-- en negativo, como los de los platos: la cocina vende y avisa).

-- ── 1. Qué toppings acepta cada plato ───────────────────────────────────────

CREATE TABLE plato_toppings (
    plato_id     uuid    NOT NULL REFERENCES productos ON DELETE CASCADE,
    adicional_id uuid    NOT NULL REFERENCES adicionales,
    orden        integer NOT NULL DEFAULT 0,
    PRIMARY KEY (plato_id, adicional_id)
);
COMMENT ON TABLE plato_toppings IS
    'Toppings que acepta un plato de cocina: adicionales que se agregan (o no) al pedirlo, con el precio del adicional.';
CREATE INDEX plato_toppings_adicional ON plato_toppings (adicional_id);

CREATE FUNCTION fn_toppings_de_un_plato_de_cocina() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM articulos a JOIN categorias c ON c.id = a.categoria_id
                    WHERE a.id = NEW.plato_id AND c.tipo = 'cocina') THEN
        RAISE EXCEPTION 'Solo los platos de cocina llevan toppings' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER plato_toppings_de_cocina
    BEFORE INSERT OR UPDATE ON plato_toppings
    FOR EACH ROW EXECUTE FUNCTION fn_toppings_de_un_plato_de_cocina();

-- Un plato con toppings sigue siendo de cocina (como uno con productos en su receta).
CREATE FUNCTION fn_articulos_categoria_y_toppings() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT tipo FROM categorias WHERE id = NEW.categoria_id) <> 'cocina'
       AND EXISTS (SELECT 1 FROM plato_toppings WHERE plato_id = NEW.id) THEN
        RAISE EXCEPTION '% acepta toppings: debe seguir en una categoría de cocina', NEW.nombre
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER articulos_categoria_y_toppings
    BEFORE UPDATE OF categoria_id ON articulos
    FOR EACH ROW WHEN (OLD.categoria_id IS DISTINCT FROM NEW.categoria_id)
    EXECUTE FUNCTION fn_articulos_categoria_y_toppings();

-- ── 2. Los toppings de cada línea (foto) ────────────────────────────────────

CREATE TABLE detalle_venta_toppings (
    detalle_id   uuid          NOT NULL REFERENCES detalle_venta DEFERRABLE INITIALLY DEFERRED,
    adicional_id uuid          NOT NULL REFERENCES adicionales,
    precio       numeric(14,2) NOT NULL CHECK (precio >= 0),
    PRIMARY KEY (detalle_id, adicional_id)
);
COMMENT ON TABLE detalle_venta_toppings IS
    'Foto de los toppings de un plato vendido (precio cobrado por plato). Se inserta antes que su línea (FK diferida).';
CREATE INDEX detalle_venta_toppings_adicional ON detalle_venta_toppings (adicional_id);

CREATE TABLE cuenta_item_toppings (
    item_id      uuid          NOT NULL REFERENCES cuenta_items ON DELETE CASCADE,
    adicional_id uuid          NOT NULL REFERENCES adicionales,
    precio       numeric(14,2) NOT NULL CHECK (precio >= 0),
    PRIMARY KEY (item_id, adicional_id)
);
COMMENT ON TABLE cuenta_item_toppings IS 'Foto de los toppings de un plato en una cuenta abierta; al cobrar pasa a detalle_venta_toppings.';

-- Las mismas reglas que lo elegido en un combo (0024): en una venta se guarda
-- antes que la línea y no se edita; en una cuenta, solo mientras está abierta.
CREATE TRIGGER detalle_venta_toppings_antes
    BEFORE INSERT ON detalle_venta_toppings
    FOR EACH ROW EXECUTE FUNCTION fn_elecciones_venta_antes_de_la_linea();
CREATE TRIGGER detalle_venta_toppings_inmutables
    BEFORE UPDATE OR DELETE ON detalle_venta_toppings
    FOR EACH ROW EXECUTE FUNCTION fn_registro_inmutable();
CREATE TRIGGER cuenta_item_toppings_cuenta_abierta
    BEFORE INSERT ON cuenta_item_toppings
    FOR EACH ROW EXECUTE FUNCTION fn_cuenta_item_elecciones_cuenta_abierta();
CREATE TRIGGER cuenta_item_toppings_inmutables
    BEFORE UPDATE ON cuenta_item_toppings
    FOR EACH ROW EXECUTE FUNCTION fn_registro_inmutable();

-- Solo un plato de cocina lleva toppings (se revisa al confirmar: en una venta
-- la línea llega después). En la venta basta con que sea un producto: si vino
-- de una cuenta, ya se revisó al agregarlo, y el plato pudo cambiar de
-- categoría mientras la cuenta seguía abierta (no debe impedir cobrarla).
CREATE FUNCTION fn_toppings_de_un_plato() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_cocina boolean;
BEGIN
    IF TG_TABLE_NAME = 'detalle_venta_toppings' THEN
        SELECT a.tipo = 'producto' INTO v_cocina
          FROM detalle_venta d JOIN articulos a ON a.id = d.articulo_id
         WHERE d.id = NEW.detalle_id;
    ELSE
        SELECT a.tipo = 'producto' AND c.tipo = 'cocina' INTO v_cocina
          FROM cuenta_items ci JOIN articulos a ON a.id = ci.articulo_id JOIN categorias c ON c.id = a.categoria_id
         WHERE ci.id = NEW.item_id;
    END IF;
    IF v_cocina IS NOT TRUE THEN
        RAISE EXCEPTION 'Solo un plato lleva toppings' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER detalle_venta_toppings_de_plato
    AFTER INSERT ON detalle_venta_toppings DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_toppings_de_un_plato();
CREATE CONSTRAINT TRIGGER cuenta_item_toppings_de_plato
    AFTER INSERT ON cuenta_item_toppings DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_toppings_de_un_plato();

-- ── 3. El texto junto al nombre ─────────────────────────────────────────────
-- Lo elegido en un combo y los toppings de un plato, en una frase: "Coca-Cola"
-- o "con Huevo duro, Queso". Es lo que se ve en la cuenta, la comanda, el
-- ticket y el detalle de la venta.
CREATE OR REPLACE FUNCTION texto_elecciones(p_venta_detalle uuid, p_cuenta_item uuid) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(concat_ws(' · ',
        (SELECT string_agg(CASE WHEN e.cantidad <> 1 THEN trim_scale(e.cantidad) || ' × ' ELSE '' END || a.nombre,
                           ', ' ORDER BY e.grupo)
           FROM (SELECT grupo, producto_id, cantidad FROM detalle_venta_elecciones WHERE detalle_id = p_venta_detalle
                 UNION ALL
                 SELECT grupo, producto_id, cantidad FROM cuenta_item_elecciones WHERE item_id = p_cuenta_item) e
           JOIN articulos a ON a.id = e.producto_id),
        (SELECT 'con ' || string_agg(a.nombre, ', ' ORDER BY a.nombre)
           FROM (SELECT adicional_id FROM detalle_venta_toppings WHERE detalle_id = p_venta_detalle
                 UNION ALL
                 SELECT adicional_id FROM cuenta_item_toppings WHERE item_id = p_cuenta_item) t
           JOIN articulos a ON a.id = t.adicional_id)), '')
$$;
COMMENT ON FUNCTION texto_elecciones(uuid, uuid) IS
    'Lo elegido en un combo y los toppings de un plato, en una frase (línea de venta o de cuenta); NULL si no lleva.';

-- ── 4. Stock: los toppings salen con su plato ───────────────────────────────
-- Cada topping es un adicional: fn_mover_stock (con recetas) descuenta su
-- porción de insumo; como lo de un plato, nunca frena la venta.
CREATE OR REPLACE FUNCTION fn_trg_stock_venta() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_mover_stock(array_agg(m.articulo_id), array_agg(m.delta), true, true)
       FROM (SELECT n.articulo_id, -n.cantidad AS delta FROM nuevas n
             UNION ALL
             SELECT e.producto_id, -(e.cantidad * n.cantidad)
               FROM nuevas n JOIN detalle_venta_elecciones e ON e.detalle_id = n.id
             UNION ALL
             SELECT t.adicional_id, -n.cantidad
               FROM nuevas n JOIN detalle_venta_toppings t ON t.detalle_id = n.id) m;
    RETURN NULL;
END $$;

-- ── 5. Catálogo: si un plato acepta toppings ────────────────────────────────
-- Columna nueva al final (CREATE OR REPLACE VIEW solo deja agregar al final).
CREATE OR REPLACE VIEW v_articulos AS
SELECT a.id, a.tipo, a.nombre, a.activo, a.precio_venta,
       a.categoria_id, c.nombre AS categoria, c.tipo AS categoria_tipo,
       a.impuesto_id, i.codigo AS impuesto, i.tributo, i.tarifa,
       p.codigo, p.precio_costo, p.stock, p.stock_minimo,
       (p.articulo_id IS NOT NULL
        AND (EXISTS (SELECT 1 FROM receta_insumos r WHERE r.producto_id = a.id)
             OR EXISTS (SELECT 1 FROM receta_productos r WHERE r.plato_id = a.id))) AS tiene_receta,
       co.descripcion,
       ad.insumo_id AS adicional_insumo_id, ad.cantidad AS adicional_cantidad,
       costo_articulo(a.id) AS costo,
       CASE WHEN p.articulo_id IS NOT NULL AND c.tipo = 'cocina' THEN platos_disponibles(a.id)
            WHEN co.articulo_id IS NOT NULL THEN combos_disponibles(a.id) END AS alcanza,
       CASE WHEN co.articulo_id IS NOT NULL THEN costo_combo(a.id, true) END AS costo_max,
       (co.articulo_id IS NOT NULL AND EXISTS (SELECT 1 FROM combo_grupos g WHERE g.combo_id = a.id)) AS tiene_grupos,
       CASE WHEN co.articulo_id IS NOT NULL THEN combo_bloqueo(a.id) END AS bloqueo,
       mc.minimo AS margen_min, mc.maximo AS margen_max,
       (p.articulo_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM plato_toppings pt JOIN articulos ta ON ta.id = pt.adicional_id
             WHERE pt.plato_id = a.id AND ta.activo)) AS tiene_toppings,
       (ad.articulo_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM plato_toppings pt JOIN articulos pa ON pa.id = pt.plato_id
             WHERE pt.adicional_id = a.id AND pa.activo)) AS es_topping
  FROM articulos a
  JOIN categorias c ON c.id = a.categoria_id
  JOIN impuestos i ON i.id = a.impuesto_id
  LEFT JOIN productos p ON p.articulo_id = a.id
  LEFT JOIN combos co ON co.articulo_id = a.id
  LEFT JOIN adicionales ad ON ad.articulo_id = a.id
  LEFT JOIN LATERAL margenes_combo(a.id) mc ON co.articulo_id IS NOT NULL;
COMMENT ON COLUMN v_articulos.tiene_toppings IS 'Plato que acepta al menos un topping activo (al venderlo se ofrecen).';
COMMENT ON COLUMN v_articulos.es_topping IS
    'Adicional que es topping de algún plato activo: se vende solo dentro del plato, no suelto.';
