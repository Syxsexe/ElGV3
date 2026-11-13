-- 0026_toppings_incluidos.sql — Toppings que van incluidos en el precio del plato.
--
-- Un plato puede traer N toppings sin costo (ej. el ramen: 2). Si el cliente
-- marca más de N, van incluidos los N más baratos y se cobran los demás. Lo
-- calcula la API al armar la foto: los incluidos quedan con precio 0, así lo
-- ya vendido no cambia aunque después se edite el plato.

ALTER TABLE productos
    ADD COLUMN toppings_incluidos smallint NOT NULL DEFAULT 0
        CONSTRAINT productos_toppings_incluidos_check CHECK (toppings_incluidos BETWEEN 0 AND 50);
COMMENT ON COLUMN productos.toppings_incluidos IS
    'Toppings sin costo al pedir el plato; de más, se cobran los más caros (van incluidos los más baratos).';

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
             WHERE pt.adicional_id = a.id AND pa.activo)) AS es_topping,
       p.toppings_incluidos
  FROM articulos a
  JOIN categorias c ON c.id = a.categoria_id
  JOIN impuestos i ON i.id = a.impuesto_id
  LEFT JOIN productos p ON p.articulo_id = a.id
  LEFT JOIN combos co ON co.articulo_id = a.id
  LEFT JOIN adicionales ad ON ad.articulo_id = a.id
  LEFT JOIN LATERAL margenes_combo(a.id) mc ON co.articulo_id IS NOT NULL;
COMMENT ON COLUMN v_articulos.toppings_incluidos IS 'Toppings sin costo al pedir el plato (null si no es producto).';
