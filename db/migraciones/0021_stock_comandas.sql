-- 0021_stock_comandas.sql — Ventas sin stock bloqueadas y comandas de cocina.
--
-- 1. Vender (o entregar un premio) ya no deja el stock en negativo: si un
--    producto de tienda no alcanza, la operación falla con el faltante. Las
--    compras siguen moviendo el stock libremente (borrar una compra puede
--    dejarlo en negativo; se corrige con un ajuste).
-- 2. Comandas: lo que se manda a cocina desde una cuenta abierta. Cada ítem
--    de la cuenta recuerda cuánto ya se envió (enviado), para que la siguiente
--    comanda lleve solo lo nuevo. La comanda guarda su copia de lo enviado
--    (con comentarios) para reimprimirla aunque la cuenta ya se haya cobrado.

-- ── 1. Stock ────────────────────────────────────────────────────────────────

DROP FUNCTION fn_mover_stock(uuid[], numeric[]);

-- p_exigir: los productos que bajan no pueden quedar en negativo.
CREATE FUNCTION fn_mover_stock(p_articulos uuid[], p_deltas numeric[], p_exigir boolean DEFAULT false) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_productos uuid[];
    v_deltas    numeric[];
    v_falta     text;
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
    IF p_exigir THEN
        SELECT string_agg(format('%s (hay %s, se necesitan %s)', a.nombre,
                                 trim_scale(greatest(p.stock - m.delta, 0)), trim_scale(-m.delta)), ', ' ORDER BY a.nombre)
          INTO v_falta
          FROM unnest(v_productos, v_deltas) AS m(producto_id, delta)
          JOIN productos p ON p.articulo_id = m.producto_id
          JOIN articulos a ON a.id = m.producto_id
         WHERE m.delta < 0 AND p.stock < 0;
        IF v_falta IS NOT NULL THEN
            RAISE EXCEPTION 'No hay stock suficiente de %', v_falta USING ERRCODE = 'check_violation';
        END IF;
    END IF;
END $$;
COMMENT ON FUNCTION fn_mover_stock(uuid[], numeric[], boolean) IS
    'Mueve el stock de productos de tienda (los combos, en sus productos). Con p_exigir, lo que baja no queda en negativo.';

CREATE OR REPLACE FUNCTION fn_trg_stock_venta() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_mover_stock(array_agg(articulo_id), array_agg(-cantidad), true) FROM nuevas;
    RETURN NULL;
END $$;

-- Lo que sale (premios, sentido -1) se exige; lo que entra (compras) no.
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
    PERFORM fn_mover_stock(v_articulos, v_deltas, v_sentido < 0);
    RETURN NULL;
END $$;

-- ── 2. Comandas ─────────────────────────────────────────────────────────────

ALTER TABLE cuenta_items
    ADD COLUMN enviado numeric(12,3) NOT NULL DEFAULT 0 CHECK (enviado >= 0);
COMMENT ON COLUMN cuenta_items.enviado IS
    'Cantidad ya mandada a cocina en comandas. Lo pendiente es cantidad − enviado (si es positivo).';

CREATE TABLE comandas (
    id          uuid        PRIMARY KEY DEFAULT uuidv7(),
    numero      bigint      GENERATED ALWAYS AS IDENTITY UNIQUE,
    cuenta_id   uuid        NOT NULL REFERENCES cuentas,
    usuario_id  uuid        NOT NULL REFERENCES usuarios,
    creada_en   timestamptz NOT NULL DEFAULT now(),
    notas       text        CHECK (btrim(notas) <> '')
);
COMMENT ON TABLE comandas IS 'Pedido impreso para cocina desde una cuenta abierta.';
CREATE INDEX comandas_cuenta ON comandas (cuenta_id);

CREATE TABLE comanda_items (
    id           uuid          PRIMARY KEY DEFAULT uuidv7(),
    comanda_id   uuid          NOT NULL REFERENCES comandas,
    articulo_id  uuid          NOT NULL REFERENCES articulos,
    cantidad     numeric(12,3) NOT NULL CHECK (cantidad > 0),
    comentario   text          CHECK (btrim(comentario) <> '')
);
COMMENT ON TABLE comanda_items IS 'Copia de lo enviado en cada comanda (no apunta a cuenta_items: al cobrar, esos se mueven a la venta).';
CREATE INDEX comanda_items_comanda ON comanda_items (comanda_id);

-- Las comandas son un registro: no se editan ni se borran.
CREATE FUNCTION fn_comandas_inmutables() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Las comandas no se editan ni se borran' USING ERRCODE = 'restrict_violation';
END $$;
CREATE TRIGGER comandas_inmutables
    BEFORE UPDATE OR DELETE ON comandas
    FOR EACH ROW EXECUTE FUNCTION fn_comandas_inmutables();
CREATE TRIGGER comanda_items_inmutables
    BEFORE UPDATE OR DELETE ON comanda_items
    FOR EACH ROW EXECUTE FUNCTION fn_comandas_inmutables();

-- ── 3. Textos ───────────────────────────────────────────────────────────────

UPDATE permisos SET descripcion = 'Condonar deuda de crédito' WHERE codigo = 'creditos.condonar';
