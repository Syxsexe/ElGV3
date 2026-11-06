-- 0015_fase3.sql — Ajustes para que la API corra sobre este esquema.
--
-- 1. Sin vía de escape: no hay migración de datos (el negocio se repuebla
--    desde cero), así que nada puede escribir en un turno ya cerrado.
-- 2. Stock por trigger: ventas, compras y premios de torneo mueven el stock
--    de los productos de tienda en la misma transacción.
-- 3. Permisos de los módulos nuevos.

-- ── 1. Turnos cerrados sin excepciones ──────────────────────────────────────

-- Lanza error si el turno ya está cerrado. El bloqueo FOR SHARE hace que un
-- cierre simultáneo espere a que esta transacción termine (y al revés): así
-- nada entra a un turno mientras se cierra.
CREATE OR REPLACE FUNCTION fn_exigir_turno_abierto(p_sesion uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_cerrada timestamptz;
BEGIN
    IF p_sesion IS NULL THEN
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

-- Un turno solo pasa de abierto a cerrado; cerrado no cambia y nunca se borra.
-- Al cerrar: toda caja del turno tiene contado, y en cajas con denominaciones
-- el contado es igual a lo contado en billetes y monedas.
CREATE OR REPLACE FUNCTION fn_sesion_caja_transicion() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    r record;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Los turnos de caja no se borran' USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.cerrada_en IS NOT NULL THEN
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

-- ── 2. Stock de productos de tienda ─────────────────────────────────────────

-- Suma a cada artículo su delta: a un producto directamente, a un combo en
-- cada uno de sus productos (× su cantidad en el combo). Solo productos de
-- categoría tienda: la cocina trabaja por costo. El stock puede quedar
-- negativo: se vende aunque el conteo registrado no alcance, y la diferencia
-- se corrige con un ajuste.
--
-- Bloquea las filas de productos en un orden fijo (por id) antes de tocarlas:
-- así dos ventas que llevan los mismos productos en distinto orden (o un combo
-- y sus productos sueltos) se esperan en vez de bloquearse mutuamente. Por eso
-- los triggers son por sentencia: la API inserta todas las líneas de una venta
-- o compra en un solo INSERT y el bloqueo ordenado cubre la venta completa.
CREATE FUNCTION fn_mover_stock(p_articulos uuid[], p_deltas numeric[]) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_productos uuid[];
    v_deltas    numeric[];
BEGIN
    SELECT array_agg(t.producto_id ORDER BY t.producto_id), array_agg(t.delta ORDER BY t.producto_id)
      INTO v_productos, v_deltas
      FROM (SELECT e.producto_id, sum(e.delta) AS delta
              FROM (SELECT x.articulo AS producto_id, x.delta
                      FROM unnest(p_articulos, p_deltas) AS x(articulo, delta)
                    UNION ALL
                    SELECT cp.producto_id, cp.cantidad * x.delta
                      FROM unnest(p_articulos, p_deltas) AS x(articulo, delta)
                      JOIN combo_productos cp ON cp.combo_id = x.articulo) e
              JOIN articulos a ON a.id = e.producto_id
              JOIN categorias c ON c.id = a.categoria_id
             WHERE a.tipo = 'producto' AND c.tipo = 'tienda'
             GROUP BY e.producto_id) t;
    IF v_productos IS NULL THEN
        RETURN;
    END IF;
    PERFORM 1 FROM productos WHERE articulo_id = ANY (v_productos) ORDER BY articulo_id FOR UPDATE;
    UPDATE productos p
       SET stock = p.stock + m.delta
      FROM unnest(v_productos, v_deltas) AS m(producto_id, delta)
     WHERE p.articulo_id = m.producto_id;
END $$;

-- detalle_venta es de solo inserción: vender solo descuenta.
CREATE FUNCTION fn_trg_stock_venta() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_mover_stock(array_agg(articulo_id), array_agg(-cantidad)) FROM nuevas;
    RETURN NULL;
END $$;
CREATE TRIGGER detalle_venta_stock
    AFTER INSERT ON detalle_venta REFERENCING NEW TABLE AS nuevas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_venta();

-- Tablas con producto_id y cantidad. TG_ARGV[0] es el sentido: 1 entra
-- (compras), -1 sale (premios). Editar o borrar líneas revierte lo anterior.
-- Postgres no admite tablas de transición en un trigger de varios eventos:
-- va un trigger por evento, todos con esta función.
CREATE FUNCTION fn_trg_stock_producto() RETURNS trigger
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
    PERFORM fn_mover_stock(v_articulos, v_deltas);
    RETURN NULL;
END $$;
CREATE TRIGGER compra_lineas_stock_insert
    AFTER INSERT ON compra_lineas REFERENCING NEW TABLE AS nuevas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_producto('1');
CREATE TRIGGER compra_lineas_stock_update
    AFTER UPDATE ON compra_lineas REFERENCING OLD TABLE AS viejas NEW TABLE AS nuevas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_producto('1');
CREATE TRIGGER compra_lineas_stock_delete
    AFTER DELETE ON compra_lineas REFERENCING OLD TABLE AS viejas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_producto('1');
CREATE TRIGGER torneo_premios_stock_insert
    AFTER INSERT ON torneo_premios REFERENCING NEW TABLE AS nuevas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_producto('-1');
CREATE TRIGGER torneo_premios_stock_update
    AFTER UPDATE ON torneo_premios REFERENCING OLD TABLE AS viejas NEW TABLE AS nuevas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_producto('-1');
CREATE TRIGGER torneo_premios_stock_delete
    AFTER DELETE ON torneo_premios REFERENCING OLD TABLE AS viejas
    FOR EACH STATEMENT EXECUTE FUNCTION fn_trg_stock_producto('-1');

COMMENT ON COLUMN productos.stock IS
    'Solo en productos de tienda: lo mueven ventas, compras y premios por trigger; '
    'los ajustes manuales quedan en auditoría.';

-- ── 3. Permisos de los módulos nuevos ───────────────────────────────────────

INSERT INTO permisos (codigo, descripcion) VALUES
    ('configuracion.editar', 'Editar empresa, cajas, métodos de pago, mesas, categorías de gasto y juegos'),
    ('compras.registrar',    'Registrar compras a proveedores'),
    ('reportes.ver',         'Ver reportes del negocio'),
    ('clientes.editar',      'Cambiar cupo y días de crédito de los clientes');

INSERT INTO rol_permisos (rol_id, permiso_id)
SELECT r.id, p.id
  FROM roles r CROSS JOIN permisos p
 WHERE r.nombre = 'admin'
   AND p.codigo IN ('configuracion.editar', 'compras.registrar', 'reportes.ver', 'clientes.editar');
