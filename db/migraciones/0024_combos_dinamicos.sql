-- 0024_combos_dinamicos.sql — Combos con grupos de elección.
--
-- Un combo tiene sus productos fijos (combo_productos) y, además, grupos de
-- los que el cliente elige una opción al pedirlo: "Bebida" entre la Coca-Cola,
-- la Pepsi o una cerveza (+$2.000). Así no hace falta un combo por bebida.
--
-- Lo elegido queda como foto pegada a la línea (de venta o de cuenta): el
-- grupo por su nombre, el producto, cuántas unidades lleva cada combo y el
-- recargo cobrado. Editar el combo después no cambia lo ya vendido.
--
-- En una venta, lo elegido se guarda ANTES que su línea (los id de las líneas
-- los pone la API) y la FK espera al confirmar: así el trigger de stock de
-- detalle_venta, que es por sentencia, mueve en un solo paso los productos
-- fijos y los elegidos, con el bloqueo ordenado de siempre (0015).

-- ── 1. Catálogo ─────────────────────────────────────────────────────────────

CREATE TABLE combo_grupos (
    id        uuid          PRIMARY KEY DEFAULT uuidv7(),
    combo_id  uuid          NOT NULL REFERENCES combos ON DELETE CASCADE,
    nombre    text          NOT NULL CHECK (btrim(nombre) <> ''),
    cantidad  numeric(12,3) NOT NULL DEFAULT 1 CHECK (cantidad > 0),
    orden     integer       NOT NULL DEFAULT 0,
    UNIQUE (combo_id, nombre)
);
COMMENT ON TABLE combo_grupos IS
    'Grupo de un combo del que se elige una opción al venderlo (ej. "Bebida"). cantidad = unidades de la opción por combo.';

CREATE TABLE combo_opciones (
    grupo_id     uuid          NOT NULL REFERENCES combo_grupos ON DELETE CASCADE,
    producto_id  uuid          NOT NULL REFERENCES productos,
    recargo      numeric(14,2) NOT NULL DEFAULT 0 CHECK (recargo >= 0),
    PRIMARY KEY (grupo_id, producto_id)
);
COMMENT ON TABLE combo_opciones IS 'Productos que se pueden elegir en un grupo. Las desactivadas no se ofrecen al vender.';
COMMENT ON COLUMN combo_opciones.recargo IS 'Lo que se suma al precio del combo (por combo) si se elige esta opción.';
CREATE INDEX combo_opciones_producto ON combo_opciones (producto_id);

-- ── 2. Lo elegido en cada línea ─────────────────────────────────────────────

CREATE TABLE detalle_venta_elecciones (
    detalle_id   uuid          NOT NULL REFERENCES detalle_venta DEFERRABLE INITIALLY DEFERRED,
    grupo        text          NOT NULL CHECK (btrim(grupo) <> ''),
    producto_id  uuid          NOT NULL REFERENCES productos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    recargo      numeric(14,2) NOT NULL DEFAULT 0 CHECK (recargo >= 0),
    PRIMARY KEY (detalle_id, grupo)
);
COMMENT ON TABLE detalle_venta_elecciones IS
    'Foto de lo elegido en un combo vendido. Se inserta antes que su línea (FK diferida): el stock lo mueve el trigger de detalle_venta.';
COMMENT ON COLUMN detalle_venta_elecciones.cantidad IS 'Unidades del producto por cada combo de la línea.';
CREATE INDEX detalle_venta_elecciones_producto ON detalle_venta_elecciones (producto_id);

CREATE TABLE cuenta_item_elecciones (
    item_id      uuid          NOT NULL REFERENCES cuenta_items ON DELETE CASCADE,
    grupo        text          NOT NULL CHECK (btrim(grupo) <> ''),
    producto_id  uuid          NOT NULL REFERENCES productos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    recargo      numeric(14,2) NOT NULL DEFAULT 0 CHECK (recargo >= 0),
    PRIMARY KEY (item_id, grupo)
);
COMMENT ON TABLE cuenta_item_elecciones IS 'Foto de lo elegido en un combo de una cuenta abierta; al cobrar pasa a detalle_venta_elecciones.';

ALTER TABLE comanda_items ADD COLUMN elecciones text CHECK (btrim(elecciones) <> '');
COMMENT ON COLUMN comanda_items.elecciones IS 'Lo elegido en el combo, como se imprimió (ej. "Coca-Cola, Papas grandes").';

-- Lo elegido de una venta llega antes que su línea: si la línea ya existe, el
-- stock de lo elegido no se movería. Y como toda foto, no se edita.
CREATE FUNCTION fn_elecciones_venta_antes_de_la_linea() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM detalle_venta WHERE id = NEW.detalle_id) THEN
        RAISE EXCEPTION 'Lo elegido en un combo se guarda junto con su línea de venta, no después'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER detalle_venta_elecciones_antes
    BEFORE INSERT ON detalle_venta_elecciones
    FOR EACH ROW EXECUTE FUNCTION fn_elecciones_venta_antes_de_la_linea();
CREATE TRIGGER detalle_venta_elecciones_inmutables
    BEFORE UPDATE OR DELETE ON detalle_venta_elecciones
    FOR EACH ROW EXECUTE FUNCTION fn_registro_inmutable();

-- Solo un combo lleva elecciones (se revisa al confirmar: en una venta la
-- línea llega después).
CREATE FUNCTION fn_elecciones_de_un_combo() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_tipo text;
BEGIN
    IF TG_TABLE_NAME = 'detalle_venta_elecciones' THEN
        SELECT a.tipo INTO v_tipo FROM detalle_venta d JOIN articulos a ON a.id = d.articulo_id WHERE d.id = NEW.detalle_id;
    ELSE
        SELECT a.tipo INTO v_tipo FROM cuenta_items ci JOIN articulos a ON a.id = ci.articulo_id WHERE ci.id = NEW.item_id;
    END IF;
    IF v_tipo IS DISTINCT FROM 'combo' THEN
        RAISE EXCEPTION 'Solo un combo lleva opciones elegidas' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER detalle_venta_elecciones_de_combo
    AFTER INSERT ON detalle_venta_elecciones DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_elecciones_de_un_combo();
CREATE CONSTRAINT TRIGGER cuenta_item_elecciones_de_combo
    AFTER INSERT ON cuenta_item_elecciones DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_elecciones_de_un_combo();

-- Lo elegido en una cuenta cambia solo mientras está abierta (como sus ítems).
CREATE FUNCTION fn_cuenta_item_elecciones_cuenta_abierta() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM cuenta_items ci JOIN cuentas cu ON cu.id = ci.cuenta_id
                WHERE ci.id = NEW.item_id AND (cu.venta_id IS NOT NULL OR cu.cancelada_en IS NOT NULL)) THEN
        RAISE EXCEPTION 'La cuenta ya está cerrada: sus ítems no cambian' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER cuenta_item_elecciones_cuenta_abierta
    BEFORE INSERT ON cuenta_item_elecciones
    FOR EACH ROW EXECUTE FUNCTION fn_cuenta_item_elecciones_cuenta_abierta();
CREATE TRIGGER cuenta_item_elecciones_inmutables
    BEFORE UPDATE ON cuenta_item_elecciones
    FOR EACH ROW EXECUTE FUNCTION fn_registro_inmutable();

-- "Coca-Cola, 2 × Papas" para mostrar junto al nombre del combo.
CREATE FUNCTION texto_elecciones(p_venta_detalle uuid, p_cuenta_item uuid) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT string_agg(CASE WHEN e.cantidad <> 1 THEN trim_scale(e.cantidad) || ' × ' ELSE '' END || a.nombre,
                      ', ' ORDER BY e.grupo)
      FROM (SELECT grupo, producto_id, cantidad FROM detalle_venta_elecciones WHERE detalle_id = p_venta_detalle
            UNION ALL
            SELECT grupo, producto_id, cantidad FROM cuenta_item_elecciones WHERE item_id = p_cuenta_item) e
      JOIN articulos a ON a.id = e.producto_id
$$;
COMMENT ON FUNCTION texto_elecciones(uuid, uuid) IS
    'Lo elegido en una línea de venta (primer argumento) o de cuenta (segundo), en una frase; NULL si no lleva.';

-- ── 3. Stock: lo elegido sale como los productos fijos ──────────────────────

-- Lo elegido es una línea directa más: se exige su stock y, si es un plato,
-- abre su receta (0022).
CREATE OR REPLACE FUNCTION fn_trg_stock_venta() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_mover_stock(array_agg(m.articulo_id), array_agg(m.delta), true, true)
       FROM (SELECT n.articulo_id, -n.cantidad AS delta FROM nuevas n
             UNION ALL
             SELECT e.producto_id, -(e.cantidad * n.cantidad)
               FROM nuevas n JOIN detalle_venta_elecciones e ON e.detalle_id = n.id) m;
    RETURN NULL;
END $$;

-- ── 4. Costo, cuántos alcanzan y bloqueos ───────────────────────────────────

-- Costo de los productos fijos del combo (lo que siempre lleva).
CREATE FUNCTION costo_combo_fijo(p_combo uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT round(COALESCE(sum(cp.cantidad * p.precio_costo), 0), 2)
      FROM combo_productos cp JOIN productos p ON p.articulo_id = cp.producto_id
     WHERE cp.combo_id = p_combo
$$;

-- Costo del combo con la opción activa más barata (o la más cara) de cada grupo.
CREATE FUNCTION costo_combo(p_combo uuid, p_maximo boolean DEFAULT false) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT costo_combo_fijo(p_combo) + COALESCE(round(sum(g.cantidad * g.costo), 2), 0)
      FROM (SELECT gr.cantidad,
                   (SELECT CASE WHEN p_maximo THEN max(p.precio_costo) ELSE min(p.precio_costo) END
                      FROM combo_opciones o
                      JOIN productos p ON p.articulo_id = o.producto_id
                      JOIN articulos a ON a.id = o.producto_id
                     WHERE o.grupo_id = gr.id AND a.activo) AS costo
              FROM combo_grupos gr WHERE gr.combo_id = p_combo) g
$$;

-- El costo de un combo es ahora el "desde": fijos + la opción más barata.
CREATE OR REPLACE FUNCTION costo_articulo(p_articulo uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT CASE a.tipo
               WHEN 'producto' THEN (SELECT p.precio_costo FROM productos p WHERE p.articulo_id = a.id)
               WHEN 'combo' THEN costo_combo(a.id)
               WHEN 'adicional' THEN (SELECT round(ad.cantidad * costo_insumo(ad.insumo_id), 2)
                                        FROM adicionales ad WHERE ad.articulo_id = a.id)
               ELSE 0
           END
      FROM articulos a WHERE a.id = p_articulo
$$;

-- Margen del combo en % sobre lo cobrado (precio + recargos), el menor y el
-- mayor entre todas las combinaciones de opciones activas: con una cerveza
-- de recargo puede quedar más plata pero menos porcentaje. Los combos tienen
-- pocos grupos y opciones, así que se recorren todas. NULL si algún grupo no
-- tiene opciones activas o el combo no cobra nada.
CREATE FUNCTION margenes_combo(p_combo uuid) RETURNS TABLE (minimo numeric, maximo numeric)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE
    grupos AS (SELECT id, cantidad, row_number() OVER (ORDER BY orden, nombre) AS n
                 FROM combo_grupos WHERE combo_id = p_combo),
    combinaciones (n, recargo, costo) AS (
        SELECT 0::bigint, 0::numeric, 0::numeric
        UNION ALL
        SELECT g.n, c.recargo + op.recargo, c.costo + g.cantidad * p.precio_costo
          FROM combinaciones c
          JOIN grupos g ON g.n = c.n + 1
          JOIN combo_opciones op ON op.grupo_id = g.id
          JOIN productos p ON p.articulo_id = op.producto_id
          JOIN articulos pa ON pa.id = op.producto_id
         WHERE pa.activo),
    margenes AS (
        SELECT 100 * (a.precio_venta + c.recargo - costo_combo_fijo(a.id) - c.costo) / (a.precio_venta + c.recargo) AS m
          FROM combinaciones c JOIN articulos a ON a.id = p_combo
         WHERE c.n = (SELECT count(*) FROM grupos) AND a.precio_venta + c.recargo > 0)
    SELECT round(min(m)), round(max(m)) FROM margenes
$$;

-- Unidades de un producto que hay para vender: el stock en la tienda, los
-- platos que alcanzan en la cocina; NULL = sin límite (plato sin receta).
CREATE FUNCTION unidades_disponibles(p_producto uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT CASE c.tipo WHEN 'tienda' THEN greatest(p.stock, 0) ELSE platos_disponibles(a.id) END
      FROM articulos a
      JOIN productos p ON p.articulo_id = a.id
      JOIN categorias c ON c.id = a.categoria_id
     WHERE a.id = p_producto
$$;

-- Combos enteros que alcanzan: los limita el producto fijo que menos alcance
-- y, en cada grupo, lo que suman sus opciones activas. NULL = sin límite.
CREATE FUNCTION combos_disponibles(p_combo uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT min(x.n)
      FROM (SELECT floor(unidades_disponibles(cp.producto_id) / cp.cantidad) AS n
              FROM combo_productos cp WHERE cp.combo_id = p_combo
            UNION ALL
            SELECT CASE WHEN count(o.producto_id) = 0 THEN 0
                        WHEN bool_or(o.disponibles IS NULL) THEN NULL
                        ELSE sum(floor(o.disponibles / g.cantidad)) END
              FROM combo_grupos g
              LEFT JOIN LATERAL (
                  SELECT op.producto_id, unidades_disponibles(op.producto_id) AS disponibles
                    FROM combo_opciones op JOIN articulos a ON a.id = op.producto_id
                   WHERE op.grupo_id = g.id AND a.activo) o ON true
             WHERE g.combo_id = p_combo
             GROUP BY g.id) x
$$;

-- Por qué un combo no se puede vender: un producto fijo desactivado o un
-- grupo sin opciones activas. NULL = se puede vender.
CREATE FUNCTION combo_bloqueo(p_combo uuid) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT string_agg(x.motivo, '; ' ORDER BY x.orden, x.motivo)
      FROM (SELECT 1 AS orden, a.nombre || ' está desactivado' AS motivo
              FROM combo_productos cp JOIN articulos a ON a.id = cp.producto_id
             WHERE cp.combo_id = p_combo AND NOT a.activo
            UNION ALL
            SELECT 2, 'el grupo ' || g.nombre || ' no tiene opciones activas'
              FROM combo_grupos g
             WHERE g.combo_id = p_combo
               AND NOT EXISTS (SELECT 1 FROM combo_opciones o JOIN articulos a ON a.id = o.producto_id
                                WHERE o.grupo_id = g.id AND a.activo)) x
$$;

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
       mc.minimo AS margen_min, mc.maximo AS margen_max
  FROM articulos a
  JOIN categorias c ON c.id = a.categoria_id
  JOIN impuestos i ON i.id = a.impuesto_id
  LEFT JOIN productos p ON p.articulo_id = a.id
  LEFT JOIN combos co ON co.articulo_id = a.id
  LEFT JOIN adicionales ad ON ad.articulo_id = a.id
  LEFT JOIN LATERAL margenes_combo(a.id) mc ON co.articulo_id IS NOT NULL;
COMMENT ON COLUMN v_articulos.alcanza IS
    'Platos de cocina y combos: cuántos alcanzan con el stock de lo que llevan (NULL = sin límite o sin receta).';
COMMENT ON COLUMN v_articulos.costo IS 'Combos con grupos: el costo con la opción más barata de cada grupo (el "desde").';
COMMENT ON COLUMN v_articulos.costo_max IS 'Combos: el costo con la opción más cara de cada grupo (igual a costo si no tiene grupos).';
COMMENT ON COLUMN v_articulos.margen_min IS
    'Combos: el menor margen (en % sobre precio + recargos) entre las combinaciones de opciones activas; margen_max, el mayor.';
COMMENT ON COLUMN v_articulos.bloqueo IS 'Combos: por qué no se puede vender (producto fijo desactivado o grupo sin opciones activas).';
