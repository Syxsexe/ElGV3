-- 0017_catalogo.sql — Apoyo del catálogo para la API (paso 2): búsqueda sin
-- tildes, costo de cualquier artículo y vistas de artículos e insumos.

-- Minúsculas sin tildes ni diéresis ("Crêpe", "Häagen", "PIÑA" → "crepe",
-- "haagen", "pina"), para buscar sin importar cómo se escribió. Se aplica a
-- la columna Y al texto buscado, así ambos lados se normalizan igual.
-- unaccent es una extensión confiable (trusted): la crea el dueño de la base.
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE FUNCTION normalizar(p_texto text) RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT lower(unaccent(p_texto))
$$;

-- Costo actual de un artículo: el del producto (en platos con receta es el
-- calculado), la suma de los productos de un combo, la porción de insumo de un
-- adicional. Los servicios no tienen costo. Es lo que se fotografía en
-- detalle_venta.costo_unit al vender.
CREATE FUNCTION costo_articulo(p_articulo uuid) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT CASE a.tipo
               WHEN 'producto' THEN (SELECT p.precio_costo FROM productos p WHERE p.articulo_id = a.id)
               WHEN 'combo' THEN (SELECT round(COALESCE(sum(cp.cantidad * p.precio_costo), 0), 2)
                                    FROM combo_productos cp
                                    JOIN productos p ON p.articulo_id = cp.producto_id
                                   WHERE cp.combo_id = a.id)
               WHEN 'adicional' THEN (SELECT round(ad.cantidad * costo_insumo(ad.insumo_id), 2)
                                        FROM adicionales ad WHERE ad.articulo_id = a.id)
               ELSE 0
           END
      FROM articulos a WHERE a.id = p_articulo
$$;

-- Todo artículo con su subtipo, categoría, impuesto y costo, en una fila.
CREATE VIEW v_articulos AS
SELECT a.id, a.tipo, a.nombre, a.activo, a.precio_venta,
       a.categoria_id, c.nombre AS categoria, c.tipo AS categoria_tipo,
       a.impuesto_id, i.codigo AS impuesto, i.tributo, i.tarifa,
       p.codigo, p.precio_costo, p.stock, p.stock_minimo,
       (p.articulo_id IS NOT NULL
        AND EXISTS (SELECT 1 FROM receta_insumos r WHERE r.producto_id = a.id)) AS tiene_receta,
       co.descripcion,
       ad.insumo_id AS adicional_insumo_id, ad.cantidad AS adicional_cantidad,
       costo_articulo(a.id) AS costo
  FROM articulos a
  JOIN categorias c ON c.id = a.categoria_id
  JOIN impuestos i ON i.id = a.impuesto_id
  LEFT JOIN productos p ON p.articulo_id = a.id
  LEFT JOIN combos co ON co.articulo_id = a.id
  LEFT JOIN adicionales ad ON ad.articulo_id = a.id;
COMMENT ON VIEW v_articulos IS 'Catálogo completo. costo = costo_articulo(); el margen lo calcula quien lo muestra.';

-- Insumos con su costo efectivo: el comprado, o el calculado si es preparación.
CREATE VIEW v_insumos AS
SELECT ins.id, ins.nombre, ins.activo, ins.unidad_medida_id, u.simbolo AS unidad,
       ins.costo_unitario,
       (pr.insumo_id IS NOT NULL) AS es_preparacion, pr.rendimiento,
       costo_insumo(ins.id) AS costo
  FROM insumos ins
  JOIN unidades_medida u ON u.id = ins.unidad_medida_id
  LEFT JOIN preparaciones pr ON pr.insumo_id = ins.id;
COMMENT ON VIEW v_insumos IS 'costo = costo_unitario en insumos comprados; en preparaciones, el calculado por su receta y rendimiento.';
