-- 0022_inventario_cocina.sql — Inventario de cocina: platos, insumos y preparaciones.
--
-- Un plato (producto de categoría cocina) no lleva stock propio: lo que hay
-- de él depende de su receta. La receta lleva insumos (o preparaciones) y,
-- ahora, productos de la tienda por unidades (el pan empacado, la gaseosa de un
-- combo de cocina). Su costo es Σ cantidad × costo de cada ingrediente; el
-- precio de venta lo pone el negocio.
--
-- Los insumos llevan stock: entran por compras, salen al vender platos y
-- adicionales. Las preparaciones se producen por lotes: producir descuenta sus
-- ingredientes y suma el rendimiento a su stock; al vender, el plato descuenta
-- la preparación. La cocina vende y avisa: un insumo puede quedar en negativo
-- (los pesos nunca cuadran exacto) y se marca como stock bajo para ajustarlo.
-- Los productos de tienda dentro de un plato tampoco frenan la venta; los que
-- se venden directo (o en un combo) sí se exigen, como en 0021.

-- ── 1. Stock de insumos ─────────────────────────────────────────────────────

ALTER TABLE insumos
    ADD COLUMN stock        numeric(12,3) NOT NULL DEFAULT 0,
    ADD COLUMN stock_minimo numeric(12,3) NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0);
COMMENT ON TABLE insumos IS
    'Ingredientes de cocina con stock: entran por compras (las preparaciones, al producirlas) y salen al vender platos y adicionales.';
COMMENT ON COLUMN insumos.stock IS 'Puede quedar negativo: la cocina vende y avisa; se corrige con un ajuste.';

-- ── 2. Productos de tienda en la receta de un plato ─────────────────────────

CREATE TABLE receta_productos (
    plato_id     uuid          NOT NULL REFERENCES productos ON DELETE CASCADE,
    producto_id  uuid          NOT NULL REFERENCES productos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (plato_id, producto_id),
    CONSTRAINT receta_productos_no_se_contiene CHECK (plato_id <> producto_id)
);
COMMENT ON TABLE receta_productos IS 'Productos de tienda que lleva un plato, por unidades (salen del stock de la tienda al venderlo).';

-- Solo un plato (categoría cocina) lleva productos, y solo de tienda: así un
-- producto con receta nunca va dentro de otra receta (sin cadenas ni ciclos).
CREATE FUNCTION fn_receta_productos_de_tienda() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM articulos a JOIN categorias c ON c.id = a.categoria_id
                    WHERE a.id = NEW.producto_id AND c.tipo = 'tienda') THEN
        RAISE EXCEPTION 'En la receta de un plato solo van productos de la tienda (o insumos)'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM articulos a JOIN categorias c ON c.id = a.categoria_id
                    WHERE a.id = NEW.plato_id AND c.tipo = 'cocina') THEN
        RAISE EXCEPTION 'Solo los platos de cocina llevan productos de la tienda en su receta'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER receta_productos_de_tienda
    BEFORE INSERT OR UPDATE ON receta_productos
    FOR EACH ROW EXECUTE FUNCTION fn_receta_productos_de_tienda();

-- Cambiar de categoría no rompe esa regla: un ingrediente sigue siendo de
-- tienda y un plato con productos sigue siendo de cocina.
CREATE FUNCTION fn_articulos_categoria_y_recetas() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_tipo text := (SELECT tipo FROM categorias WHERE id = NEW.categoria_id);
BEGIN
    IF v_tipo <> 'tienda' AND EXISTS (SELECT 1 FROM receta_productos WHERE producto_id = NEW.id) THEN
        RAISE EXCEPTION '% va en la receta de algún plato: debe seguir en una categoría de tienda', NEW.nombre
            USING ERRCODE = 'check_violation';
    END IF;
    IF v_tipo <> 'cocina' AND EXISTS (SELECT 1 FROM receta_productos WHERE plato_id = NEW.id) THEN
        RAISE EXCEPTION '% lleva productos de la tienda en su receta: debe seguir en una categoría de cocina', NEW.nombre
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER articulos_categoria_y_recetas
    BEFORE UPDATE OF categoria_id ON articulos
    FOR EACH ROW WHEN (OLD.categoria_id IS DISTINCT FROM NEW.categoria_id)
    EXECUTE FUNCTION fn_articulos_categoria_y_recetas();

-- ── 3. Costo de los platos ──────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION costo_plato(p_producto uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT round(
        COALESCE((SELECT sum(cantidad * costo_insumo(insumo_id)) FROM receta_insumos WHERE producto_id = p_producto), 0)
      + COALESCE((SELECT sum(r.cantidad * p.precio_costo)
                    FROM receta_productos r JOIN productos p ON p.articulo_id = r.producto_id
                   WHERE r.plato_id = p_producto), 0), 2)
$$;

CREATE OR REPLACE FUNCTION recalcular_costos_cocina() RETURNS void
LANGUAGE sql AS $$
    UPDATE productos p
       SET precio_costo = x.costo
      FROM (SELECT producto_id, costo_plato(producto_id) AS costo
              FROM (SELECT producto_id FROM receta_insumos
                    UNION SELECT plato_id FROM receta_productos) platos) x
     WHERE p.articulo_id = x.producto_id
       AND p.precio_costo IS DISTINCT FROM x.costo
$$;

CREATE TRIGGER receta_productos_recalcular_costos
    AFTER INSERT OR UPDATE OR DELETE ON receta_productos
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_recalcular_costos();

-- Si cambia el costo de un producto de tienda que va en alguna receta (una
-- compra lo actualiza), los platos que lo llevan se recalculan: una vez por
-- sentencia, aunque cambien varios. No se encadena: los platos (los que se
-- recalculan) nunca son ingredientes de otra receta.
CREATE FUNCTION fn_trg_costo_producto_en_recetas() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM nuevas n JOIN viejas v USING (articulo_id)
                 JOIN receta_productos r ON r.producto_id = n.articulo_id
                WHERE n.precio_costo IS DISTINCT FROM v.precio_costo) THEN
        PERFORM recalcular_costos_cocina();
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER productos_costo_en_recetas
    AFTER UPDATE ON productos REFERENCING OLD TABLE AS viejas NEW TABLE AS nuevas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_costo_producto_en_recetas();

-- ── 4. Movimientos de stock ─────────────────────────────────────────────────

-- Suma a cada insumo su delta. Bloquea en orden fijo (por id), después de los
-- productos: así todas las operaciones toman los bloqueos en el mismo orden.
CREATE FUNCTION fn_mover_insumos(p_insumos uuid[], p_deltas numeric[]) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_insumos uuid[];
    v_deltas  numeric[];
BEGIN
    SELECT array_agg(t.insumo_id ORDER BY t.insumo_id), array_agg(t.delta ORDER BY t.insumo_id)
      INTO v_insumos, v_deltas
      FROM (SELECT x.insumo_id, sum(x.delta) AS delta
              FROM unnest(p_insumos, p_deltas) AS x(insumo_id, delta)
             WHERE x.insumo_id IS NOT NULL
             GROUP BY x.insumo_id) t;
    IF v_insumos IS NULL THEN
        RETURN;
    END IF;
    PERFORM 1 FROM insumos WHERE id = ANY (v_insumos) ORDER BY id FOR UPDATE;
    UPDATE insumos i
       SET stock = i.stock + m.delta
      FROM unnest(v_insumos, v_deltas) AS m(insumo_id, delta)
     WHERE i.id = m.insumo_id;
END $$;

-- Mueve los productos de tienda (los combos, en sus productos) y, con
-- p_recetas (al vender), también lo que lleva cada plato: los productos de
-- tienda de su receta, los insumos de su receta y los de los adicionales.
-- Las compras y los premios no abren recetas: lo que entró fue el artículo.
-- p_exigir solo cuenta lo que sale directo o en un combo: lo que se va dentro
-- de un plato nunca frena la venta.
DROP FUNCTION fn_mover_stock(uuid[], numeric[], boolean);
CREATE FUNCTION fn_mover_stock(p_articulos uuid[], p_deltas numeric[], p_exigir boolean DEFAULT false,
                               p_recetas boolean DEFAULT false) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_productos uuid[];
    v_deltas    numeric[];
    v_directos  numeric[];
    v_insumos   uuid[];
    v_ideltas   numeric[];
    v_falta     text;
BEGIN
    WITH x AS (SELECT articulo, delta FROM unnest(p_articulos, p_deltas) AS x(articulo, delta)),
         lineas AS (SELECT x.articulo AS producto_id, x.delta FROM x
                    UNION ALL
                    SELECT cp.producto_id, cp.cantidad * x.delta FROM x JOIN combo_productos cp ON cp.combo_id = x.articulo),
         mov AS (SELECT l.producto_id, l.delta, true AS directo FROM lineas l
                 UNION ALL
                 SELECT rp.producto_id, rp.cantidad * l.delta, false
                   FROM lineas l JOIN receta_productos rp ON rp.plato_id = l.producto_id
                  WHERE p_recetas)
    SELECT array_agg(t.producto_id ORDER BY t.producto_id), array_agg(t.delta ORDER BY t.producto_id),
           array_agg(t.directo ORDER BY t.producto_id)
      INTO v_productos, v_deltas, v_directos
      FROM (SELECT m.producto_id, sum(m.delta) AS delta, COALESCE(sum(m.delta) FILTER (WHERE m.directo), 0) AS directo
              FROM mov m
              JOIN articulos a ON a.id = m.producto_id
              JOIN categorias c ON c.id = a.categoria_id
             WHERE a.tipo = 'producto' AND c.tipo = 'tienda'
             GROUP BY m.producto_id) t;

    IF v_productos IS NOT NULL THEN
        PERFORM 1 FROM productos WHERE articulo_id = ANY (v_productos) ORDER BY articulo_id FOR UPDATE;
        UPDATE productos p
           SET stock = p.stock + m.delta
          FROM unnest(v_productos, v_deltas) AS m(producto_id, delta)
         WHERE p.articulo_id = m.producto_id;
        -- Con lo de antes (stock − delta) debe alcanzar lo que sale directo.
        SELECT string_agg(format('%s (hay %s, se necesitan %s)', a.nombre,
                                 trim_scale(greatest(p.stock - m.delta, 0)), trim_scale(-m.directo)), ', ' ORDER BY a.nombre)
          INTO v_falta
          FROM unnest(v_productos, v_deltas, v_directos) AS m(producto_id, delta, directo)
          JOIN productos p ON p.articulo_id = m.producto_id
          JOIN articulos a ON a.id = m.producto_id
         WHERE p_exigir AND m.directo < 0 AND p.stock - m.delta + m.directo < 0;
        IF v_falta IS NOT NULL THEN
            RAISE EXCEPTION 'No hay stock suficiente de %', v_falta USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NOT p_recetas THEN
        RETURN;
    END IF;
    WITH x AS (SELECT articulo, delta FROM unnest(p_articulos, p_deltas) AS x(articulo, delta)),
         lineas AS (SELECT x.articulo AS producto_id, x.delta FROM x
                    UNION ALL
                    SELECT cp.producto_id, cp.cantidad * x.delta FROM x JOIN combo_productos cp ON cp.combo_id = x.articulo),
         mov AS (SELECT ri.insumo_id, ri.cantidad * l.delta AS delta
                   FROM lineas l JOIN receta_insumos ri ON ri.producto_id = l.producto_id
                 UNION ALL
                 SELECT ad.insumo_id, ad.cantidad * x.delta FROM x JOIN adicionales ad ON ad.articulo_id = x.articulo)
    SELECT array_agg(insumo_id), array_agg(delta) INTO v_insumos, v_ideltas FROM mov;
    PERFORM fn_mover_insumos(v_insumos, v_ideltas);
END $$;

CREATE OR REPLACE FUNCTION fn_trg_stock_venta() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_mover_stock(array_agg(articulo_id), array_agg(-cantidad), true, true) FROM nuevas;
    RETURN NULL;
END $$;

-- Compras (sentido 1) y premios (-1): solo el producto; se exige lo que sale.
CREATE OR REPLACE FUNCTION fn_trg_stock_producto() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_sentido   numeric  := TG_ARGV[0]::numeric;
    v_articulos uuid[]   := '{}';
    v_deltas    numeric[] := '{}';
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT v_articulos || array_agg(producto_id), v_deltas || array_agg(-v_sentido * cantidad)
          INTO v_articulos, v_deltas
          FROM viejas WHERE producto_id IS NOT NULL;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT v_articulos || array_agg(producto_id), v_deltas || array_agg(v_sentido * cantidad)
          INTO v_articulos, v_deltas
          FROM nuevas WHERE producto_id IS NOT NULL;
    END IF;
    PERFORM fn_mover_stock(v_articulos, v_deltas, v_sentido < 0, false);
    RETURN NULL;
END $$;

-- Las compras de insumos suman a su stock (editar o borrar la línea revierte).
CREATE FUNCTION fn_trg_stock_insumo_compra() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_insumos uuid[]    := '{}';
    v_deltas  numeric[] := '{}';
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT v_insumos || array_agg(insumo_id), v_deltas || array_agg(-cantidad)
          INTO v_insumos, v_deltas
          FROM viejas WHERE insumo_id IS NOT NULL;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT v_insumos || array_agg(insumo_id), v_deltas || array_agg(cantidad)
          INTO v_insumos, v_deltas
          FROM nuevas WHERE insumo_id IS NOT NULL;
    END IF;
    PERFORM fn_mover_insumos(v_insumos, v_deltas);
    RETURN NULL;
END $$;
-- Postgres dispara los triggers en orden alfabético: el "z_" los deja después
-- de los de productos (compra_lineas_stock_insert/update/delete), así se
-- bloquean productos primero e insumos después, como en fn_mover_stock.
CREATE TRIGGER compra_lineas_stock_z_insumos_insert
    AFTER INSERT ON compra_lineas REFERENCING NEW TABLE AS nuevas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_insumo_compra();
CREATE TRIGGER compra_lineas_stock_z_insumos_update
    AFTER UPDATE ON compra_lineas REFERENCING OLD TABLE AS viejas NEW TABLE AS nuevas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_insumo_compra();
CREATE TRIGGER compra_lineas_stock_z_insumos_delete
    AFTER DELETE ON compra_lineas REFERENCING OLD TABLE AS viejas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_insumo_compra();

-- ── 5. Producción de preparaciones ──────────────────────────────────────────

CREATE TABLE producciones (
    id              uuid          PRIMARY KEY DEFAULT uuidv7(),
    preparacion_id  uuid          NOT NULL REFERENCES insumos,
    lotes           numeric(12,3) NOT NULL CHECK (lotes > 0),
    cantidad        numeric(12,3) NOT NULL CHECK (cantidad > 0),
    usuario_id      uuid          NOT NULL REFERENCES usuarios,
    creada_en       timestamptz   NOT NULL DEFAULT now(),
    notas           text          CHECK (btrim(notas) <> '')
);
COMMENT ON COLUMN producciones.preparacion_id IS
    'El insumo producido. Apunta a insumos (no a preparaciones) para que quitarle la receta no choque con su historial.';
COMMENT ON TABLE producciones IS
    'Lotes producidos de una preparación: descuentan sus ingredientes (receta × lotes) y suman cantidad (lotes × rendimiento de ese momento) a su stock.';
CREATE INDEX producciones_preparacion ON producciones (preparacion_id, creada_en DESC);

CREATE FUNCTION fn_trg_producir() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_insumos uuid[];
    v_deltas  numeric[];
BEGIN
    SELECT array_agg(insumo_id) || NEW.preparacion_id, array_agg(-cantidad * NEW.lotes) || NEW.cantidad
      INTO v_insumos, v_deltas
      FROM receta_preparacion WHERE preparacion_id = NEW.preparacion_id;
    PERFORM fn_mover_insumos(v_insumos, v_deltas);
    RETURN NULL;
END $$;
CREATE TRIGGER producciones_mover_stock
    AFTER INSERT ON producciones
    FOR EACH ROW EXECUTE FUNCTION fn_trg_producir();

CREATE FUNCTION fn_registro_inmutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Este registro no se edita ni se borra' USING ERRCODE = 'restrict_violation';
END $$;
CREATE TRIGGER producciones_inmutables
    BEFORE UPDATE OR DELETE ON producciones
    FOR EACH ROW EXECUTE FUNCTION fn_registro_inmutable();

-- ── 6. Cuántos platos alcanzan y vistas ─────────────────────────────────────

-- Platos enteros que alcanzan con el stock de su receta; NULL si no tiene receta.
CREATE FUNCTION platos_disponibles(p_plato uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT min(floor(greatest(x.stock, 0) / x.cantidad))
      FROM (SELECT i.stock, r.cantidad FROM receta_insumos r JOIN insumos i ON i.id = r.insumo_id
             WHERE r.producto_id = p_plato
            UNION ALL
            SELECT p.stock, r.cantidad FROM receta_productos r JOIN productos p ON p.articulo_id = r.producto_id
             WHERE r.plato_id = p_plato) x
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
       CASE WHEN p.articulo_id IS NOT NULL AND c.tipo = 'cocina' THEN platos_disponibles(a.id) END AS alcanza
  FROM articulos a
  JOIN categorias c ON c.id = a.categoria_id
  JOIN impuestos i ON i.id = a.impuesto_id
  LEFT JOIN productos p ON p.articulo_id = a.id
  LEFT JOIN combos co ON co.articulo_id = a.id
  LEFT JOIN adicionales ad ON ad.articulo_id = a.id;
COMMENT ON COLUMN v_articulos.alcanza IS 'Platos de cocina: cuántos alcanzan con el stock de su receta (NULL sin receta).';

CREATE OR REPLACE VIEW v_insumos AS
SELECT ins.id, ins.nombre, ins.activo, ins.unidad_medida_id, u.simbolo AS unidad,
       ins.costo_unitario,
       (pr.insumo_id IS NOT NULL) AS es_preparacion, pr.rendimiento,
       costo_insumo(ins.id) AS costo,
       ins.stock, ins.stock_minimo
  FROM insumos ins
  JOIN unidades_medida u ON u.id = ins.unidad_medida_id
  LEFT JOIN preparaciones pr ON pr.insumo_id = ins.id;
