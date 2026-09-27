import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import PagoModal from "../components/PagoModal";
import { useIsMobile } from "../useMediaQuery";

const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");
const TABS = [
  ["tienda", "Tienda"],
  ["cocina", "Cocina"],
  ["combos", "Combos"],
];

export default function Venta() {
  const isMobile = useIsMobile();
  const [tab, setTab] = useState("tienda");
  const [q, setQ] = useState("");
  const [productos, setProductos] = useState([]);
  const [cart, setCart] = useState([]); // {tipo,id,nombre,precio,cantidad}
  const [descuento, setDescuento] = useState(0);
  const [error, setError] = useState("");
  const [mostrarCobro, setMostrarCobro] = useState(false);
  const [mostrarCarritoMovil, setMostrarCarritoMovil] = useState(false);
  const [ventaOk, setVentaOk] = useState(null);

  const cargarProductos = async () => {
    try {
      if (tab === "combos") {
        const combos = await api.combos();
        setProductos(combos.map((c) => ({ id: c.id, nombre: c.nombre, precio_venta: c.precio, tipo: "combo" })));
      } else {
        const prods = await api.buscarProductos(q, tab);
        setProductos(prods.map((p) => ({ ...p, tipo: "producto" })));
      }
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    const t = setTimeout(cargarProductos, 200);
    return () => clearTimeout(t);
  }, [tab, q]);

  const total = useMemo(() => Math.max(0, cart.reduce((a, it) => a + it.precio * it.cantidad, 0) - Number(descuento || 0)), [cart, descuento]);

  const agregarAlCarrito = (p) => {
    setCart((c) => {
      const idx = c.findIndex((it) => it.tipo === p.tipo && it.id === p.id);
      if (idx >= 0) {
        const copia = [...c];
        copia[idx] = { ...copia[idx], cantidad: copia[idx].cantidad + 1 };
        return copia;
      }
      return [...c, { tipo: p.tipo, id: p.id, nombre: p.nombre, precio: p.precio_venta, cantidad: 1 }];
    });
  };

  const cambiarCantidad = (tipo, id, delta) => {
    setCart((c) => c
      .map((it) => (it.tipo === tipo && it.id === id ? { ...it, cantidad: it.cantidad + delta } : it))
      .filter((it) => it.cantidad > 0));
  };

  const limpiar = () => setCart([]);

  const cobrar = async (pagos) => {
    setError("");
    const r = await api.registrarVenta({
      items: cart.map((it) => ({ tipo: it.tipo, id: it.id, cantidad: it.cantidad })),
      descuento: Number(descuento || 0),
      pagos,
    });
    setMostrarCobro(false);
    setMostrarCarritoMovil(false);
    setCart([]);
    setDescuento(0);
    setVentaOk(r.venta_id);
    setTimeout(() => setVentaOk(null), 4000);
    cargarProductos();
  };

  const cantidadEnCarrito = (tipo, id) => cart.find((it) => it.tipo === tipo && it.id === id)?.cantidad || 0;

  const carritoPanel = (
    <>
      <div style={{ padding: "18px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-2)" }}>
        <h2 style={{ fontSize: 20 }}>Carrito</h2>
        <button type="button" className="btn btn-g" style={{ height: 34, fontSize: 13 }} onClick={limpiar}>Limpiar</button>
      </div>
      <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border-2)", fontSize: 14, color: "var(--text-label)" }}>
        Sin cliente — Consumidor final
      </div>
      <div style={{ flexGrow: 1, overflowY: "auto", padding: "6px 20px" }}>
        {cart.length === 0 ? (
          <div className="muted" style={{ margin: "auto", textAlign: "center", fontSize: 14, paddingTop: 40 }}>
            Carrito vacío.<br />Toca un producto para agregarlo.
          </div>
        ) : cart.map((it) => (
          <div key={`${it.tipo}-${it.id}`} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: "1px solid var(--border-2)" }}>
            <div style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: 14, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.nombre}</span>
              <span className="muted num" style={{ fontSize: 12 }}>{fmt(it.precio)} c/u</span>
            </div>
            <button type="button" className="step" onClick={() => cambiarCantidad(it.tipo, it.id, -1)}>−</button>
            <span className="num" style={{ width: 22, textAlign: "center", fontWeight: 700 }}>{it.cantidad}</span>
            <button type="button" className="step" onClick={() => cambiarCantidad(it.tipo, it.id, 1)}>+</button>
            <span className="num" style={{ width: 78, textAlign: "right", fontWeight: 700, fontSize: 14 }}>{fmt(it.precio * it.cantidad)}</span>
          </div>
        ))}
      </div>
      <div style={{ padding: "14px 20px", display: "flex", flexDirection: "column", gap: 12, borderTop: "1px solid var(--border-2)", background: "var(--surface-2)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <label className="lbl" htmlFor="desc">Descuento ($)</label>
          <input className="inp num" id="desc" type="number" value={descuento} style={{ width: 120, textAlign: "right" }}
            onChange={(e) => setDescuento(e.target.value)} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>Total</span>
          <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 32, fontWeight: 700 }}>{fmt(total)}</span>
        </div>
        <button type="button" className="btn btn-p" style={{ height: 52, fontSize: 16, width: "100%" }}
          disabled={cart.length === 0} onClick={() => setMostrarCobro(true)}>
          Cobrar {fmt(total)}
        </button>
      </div>
    </>
  );

  return (
    <>
      <header style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Nueva venta</h1>
        {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Registra una venta de tienda o cocina</div>}
      </header>

      {error && <div className="error-banner">{error}</div>}
      {ventaOk && <div className="chip ok" style={{ alignSelf: "flex-start" }}>Venta #{ventaOk} registrada</div>}

      <div style={{ display: "flex", gap: 20, flexGrow: 1, minHeight: 0 }}>
        <section style={{ flexGrow: 1, display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ position: "relative", flexGrow: 1, minWidth: 200 }}>
              <input className="inp" type="search" placeholder="Buscar producto, código…"
                value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <div className="seg" role="tablist" aria-label="Catálogo">
              {TABS.map(([k, label]) => (
                <button key={k} type="button" role="tab" className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>
              ))}
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "repeat(2, minmax(0,1fr))" : "repeat(3, minmax(0,1fr))", gap: 12, overflowY: "auto", alignContent: "start" }}>
            {productos.map((p) => {
              const cant = cantidadEnCarrito(p.tipo, p.id);
              const stockTxt = p.tipo === "combo" || p.stock == null ? "Por receta" : `Stock ${p.stock}`;
              const stockCls = p.tipo === "combo" || p.stock == null ? "neu" : p.stock <= 2 ? "warn" : "ok";
              return (
                <button key={`${p.tipo}-${p.id}`} type="button" className="prod" onClick={() => agregarAlCarrito(p)}>
                  {cant > 0 && <span className="qty num">{cant}</span>}
                  <span style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3, paddingRight: cant > 0 ? 24 : 0 }}>{p.nombre}</span>
                  <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "auto" }}>
                    <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 18, fontWeight: 700, color: "var(--accent-hover)" }}>{fmt(p.precio_venta)}</span>
                    <span className={`chip ${stockCls} num`}>{stockTxt}</span>
                  </span>
                </button>
              );
            })}
            {productos.length === 0 && <div className="muted">Sin resultados.</div>}
          </div>
        </section>

        {!isMobile && (
          <aside className="card" aria-label="Carrito" style={{ width: 400, flexShrink: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {carritoPanel}
          </aside>
        )}
      </div>

      {isMobile && (
        <div style={{ position: "fixed", left: 12, right: 12, bottom: 88 }}>
          <button type="button" onClick={() => setMostrarCarritoMovil(true)} style={{
            width: "100%", height: 60, border: 0, borderRadius: 16, background: "var(--accent)", color: "#fff",
            display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 18px",
            font: "600 15px Figtree, sans-serif", cursor: "pointer", boxShadow: "0 6px 18px rgba(30,110,100,.28)",
          }}>
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num" style={{ minWidth: 28, height: 28, borderRadius: 99, background: "#fff", color: "var(--accent-hover)", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {cart.reduce((a, it) => a + it.cantidad, 0)}
              </span>
              Ver carrito
            </span>
            <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 20, fontWeight: 700 }}>{fmt(total)}</span>
          </button>
        </div>
      )}

      {isMobile && mostrarCarritoMovil && (
        <div style={{ position: "fixed", inset: 0, zIndex: 40 }}>
          <div style={{ position: "absolute", inset: 0, background: "rgba(42,38,34,.4)" }} onClick={() => setMostrarCarritoMovil(false)} />
          <section aria-label="Carrito" className="card" style={{
            position: "absolute", left: 0, right: 0, bottom: 0, borderRadius: "24px 24px 0 0",
            padding: "10px 0 0", display: "flex", flexDirection: "column", maxHeight: "85vh",
          }}>
            <div style={{ width: 40, height: 5, borderRadius: 99, background: "#D9D1C4", alignSelf: "center", marginBottom: 8 }} />
            {carritoPanel}
          </section>
        </div>
      )}

      {mostrarCobro && (
        <PagoModal total={total} onCancel={() => setMostrarCobro(false)} onConfirm={cobrar} />
      )}
    </>
  );
}
