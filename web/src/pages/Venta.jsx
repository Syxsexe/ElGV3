import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import BuscarTercero from "../components/BuscarTercero";
import Catalogo from "../components/Catalogo";
import ElegirCombo from "../components/ElegirCombo";
import { ErrorBanner } from "../components/Modal";
import PagoModal from "../components/PagoModal";
import { fmt, fmtCant } from "../format";
import { imprimirTicketVenta } from "../imprimir";
import { useIsMobile } from "../useMediaQuery";
import { useTurno } from "../useTurno";

const GRANDE = { fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontWeight: 700 };

// Aviso cuando no hay turno abierto (o no se pudo saber): sin turno no se cobra.
export function SinTurno({ turno, error, recargar, que = "vender" }) {
  if (error) {
    return (
      <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
        <span>{error}</span>
        <button type="button" className="btn btn-s" onClick={recargar}>Reintentar</button>
      </div>
    );
  }
  if (turno === undefined) return <div className="muted">Cargando…</div>;
  return (
    <div className="card" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start", maxWidth: 520 }}>
      <h2 style={{ fontSize: 20 }}>No hay turno de caja abierto</h2>
      <span className="muted">Para {que} primero se abre el turno con la base de cada caja.</span>
      <Link to="/caja" className="btn btn-p">Ir a Caja</Link>
    </div>
  );
}

// Solo la línea que se acaba de agregar se anima (no las que ya estaban cada
// vez que se abre el carrito del celular).
const recienAgregada = (it) => Date.now() - (it.agregada || 0) < 600;

function Carrito({ cart, setCantidad, cliente, setCliente, descuento, setDescuento, total, subtotal, onCobrar, onLimpiar }) {
  const [buscando, setBuscando] = useState(false);
  const descuentoInvalido = Number(descuento) > subtotal;
  return (
    <>
      <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-2)" }}>
        <h2 style={{ fontSize: 20 }}>Venta</h2>
        <button type="button" className="btn btn-g" style={{ height: 34, fontSize: 13 }} onClick={onLimpiar} disabled={cart.length === 0 && !cliente}>
          Limpiar
        </button>
      </div>
      <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--border-2)", display: "flex", flexDirection: "column", gap: 8 }}>
        {cliente ? (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
              <span className="muted">Cliente: </span><strong>{cliente.nombre}</strong>
            </span>
            <button type="button" className="btn btn-g" style={{ height: 30, fontSize: 13, flexShrink: 0 }} onClick={() => setCliente(null)}>
              Consumidor final
            </button>
          </div>
        ) : buscando ? (
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <div style={{ flexGrow: 1, minWidth: 0 }}>
              <BuscarTercero rol="cliente" placeholder="Buscar cliente" onElegir={(t) => { setCliente({ id: t.id, nombre: t.nombre }); setBuscando(false); }} />
            </div>
            <button type="button" className="btn btn-g" style={{ height: 40, fontSize: 13, flexShrink: 0 }} onClick={() => setBuscando(false)}>Cancelar</button>
          </div>
        ) : (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <span className="muted" style={{ fontSize: 14 }}>Sin cliente — consumidor final</span>
            <button type="button" className="btn btn-g" style={{ height: 30, fontSize: 13 }} onClick={() => setBuscando(true)}>Elegir cliente</button>
          </div>
        )}
      </div>
      <div style={{ flexGrow: 1, overflowY: "auto", padding: "4px 20px", minHeight: 80 }}>
        {cart.length === 0 ? (
          <div className="muted" style={{ textAlign: "center", fontSize: 14, padding: "32px 0" }}>
            Toca un artículo para agregarlo.
          </div>
        ) : cart.map((it) => (
          <div key={it.key} className={recienAgregada(it) ? "linea-entrar" : undefined} style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 0", borderBottom: "1px solid var(--border-2)" }}>
            <div style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3, overflowWrap: "anywhere" }}>{it.nombre}</span>
              {it.detalle && <span style={{ fontSize: 13, overflowWrap: "anywhere" }}>{it.detalle}</span>}
              <span className="muted num" style={{ fontSize: 12 }}>{fmt(it.precio)} c/u</span>
            </div>
            <button type="button" className="step" aria-label={`Quitar uno de ${it.nombre}`} onClick={() => setCantidad(it.key, it.cantidad - 1)}>−</button>
            <span className="num" style={{ minWidth: 24, textAlign: "center", fontWeight: 700 }}>{fmtCant(it.cantidad)}</span>
            <button type="button" className="step" aria-label={`Agregar uno de ${it.nombre}`} onClick={() => setCantidad(it.key, it.cantidad + 1)}>+</button>
            <span className="num" style={{ width: 84, textAlign: "right", fontWeight: 700, fontSize: 14, whiteSpace: "nowrap" }}>{fmt(it.precio * it.cantidad)}</span>
          </div>
        ))}
      </div>
      <div style={{ padding: "14px 20px", display: "flex", flexDirection: "column", gap: 12, borderTop: "1px solid var(--border-2)", background: "var(--surface-2)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <label className="lbl" htmlFor="venta-descuento">Descuento</label>
          <input className="inp num" id="venta-descuento" type="number" min="0" step="any" inputMode="decimal" value={descuento}
            placeholder="0" style={{ width: 130, textAlign: "right" }} onChange={(e) => setDescuento(e.target.value)} />
        </div>
        {descuentoInvalido && <span className="muted" role="status" style={{ fontSize: 13 }}>El descuento supera el subtotal.</span>}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>Total</span>
          <span className="num" style={{ ...GRANDE, fontSize: 30 }}>{fmt(total)}</span>
        </div>
        <button type="button" className="btn btn-p" style={{ height: 52, fontSize: 16, width: "100%" }}
          disabled={cart.length === 0 || descuentoInvalido} onClick={onCobrar}>
          Cobrar {fmt(total)}
        </button>
      </div>
    </>
  );
}

export default function Venta() {
  const isMobile = useIsMobile();
  const { turno, error: errorTurno, recargar } = useTurno();
  // [{key, articulo_id, nombre, base, recargo, precio, cantidad, stock, elecciones}]: stock solo en productos
  // de tienda; elecciones y recargo en combos con grupos (key = artículo + lo elegido).
  const [cart, setCart] = useState([]);
  const [eligiendo, setEligiendo] = useState(null); // combo con grupos esperando que elijan
  const [aviso, setAviso] = useState("");
  const [cliente, setCliente] = useState(null);
  const [descuento, setDescuento] = useState("");
  const [cobrando, setCobrando] = useState(false);
  const [carritoMovil, setCarritoMovil] = useState(false);
  const [hecha, setHecha] = useState(null); // {venta, cambio}
  const [version, setVersion] = useState(0);

  if (!turno) {
    return (
      <>
        <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Nueva venta</h1>
        <SinTurno turno={turno} error={errorTurno} recargar={recargar} />
      </>
    );
  }

  const subtotal = cart.reduce((a, it) => a + it.precio * it.cantidad, 0);
  const total = Math.max(0, subtotal - Number(descuento || 0));
  const unidades = cart.reduce((a, it) => a + it.cantidad, 0);
  const cantidades = cart.reduce((m, it) => ({ ...m, [it.articulo_id]: (m[it.articulo_id] || 0) + it.cantidad }), {});

  // Los productos de tienda no se venden por encima de su stock (el servidor
  // lo vuelve a exigir al cobrar; los combos solo los valida el servidor).
  const stockDe = (a) => (a.tipo === "producto" && a.categoria_tipo === "tienda" ? Number(a.stock) : null);
  const tope = (it, cantidad) => {
    if (it.stock == null || cantidad <= it.stock) return true;
    setAviso(it.stock > 0 ? `De ${it.nombre} solo hay ${fmtCant(it.stock)} en stock.` : `${it.nombre} está agotado.`);
    return false;
  };
  // eleccion (combo con grupos): {elecciones, recargo, texto, firma} de ElegirCombo.
  const agregarLinea = (a, eleccion = null) => {
    setHecha(null);
    setAviso("");
    const key = eleccion ? `${a.id}|${eleccion.firma}` : a.id;
    const base = Number(a.precio_venta);
    const recargo = eleccion?.recargo || 0;
    const stock = stockDe(a);
    const actual = cart.find((it) => it.key === key);
    if (!tope({ nombre: a.nombre, stock }, (actual?.cantidad || 0) + 1)) return;
    setCart((c) => (c.some((it) => it.key === key)
      ? c.map((it) => (it.key === key ? { ...it, base, precio: base + it.recargo, stock, cantidad: it.cantidad + 1 } : it))
      : [...c, {
        key, articulo_id: a.id, nombre: a.nombre, detalle: eleccion?.texto || "",
        base, recargo, precio: base + recargo, stock, cantidad: 1, elecciones: eleccion?.elecciones || [], agregada: Date.now(),
      }]));
  };
  const agregar = (a) => {
    if (a.tipo === "combo" && a.tiene_grupos) {
      setAviso("");
      setEligiendo(a);
    } else {
      agregarLinea(a);
    }
  };
  // El servidor cobra el precio actual (más los recargos de lo elegido): si
  // cambió, la línea se pone al día cada vez que el catálogo trae ese artículo.
  // Lo mismo con el stock, para que el tope del carrito siga al día.
  const preciosAlDia = (articulos) => setCart((c) => {
    const porId = new Map(articulos.map((a) => [a.id, { base: Number(a.precio_venta), stock: stockDe(a) }]));
    const nuevo = (it) => porId.get(it.articulo_id);
    return c.some((it) => nuevo(it) && (nuevo(it).base !== it.base || nuevo(it).stock !== it.stock))
      ? c.map((it) => (nuevo(it) ? { ...it, ...nuevo(it), precio: nuevo(it).base + it.recargo } : it))
      : c;
  });
  const setCantidad = (key, cantidad) => {
    setAviso("");
    const it = cart.find((x) => x.key === key);
    if (it && cantidad > it.cantidad && !tope(it, cantidad)) return;
    setCart((c) => c.map((x) => (x.key === key ? { ...x, cantidad } : x)).filter((x) => x.cantidad > 0));
  };
  const limpiar = () => {
    setCart([]);
    setCliente(null);
    setDescuento("");
  };

  // Si falla, el error se ve en el modal (lo lanza onCobrar).
  const cobrar = async (cobro, { cambio }) => {
    const venta = await api.vender(
      cart.map((it) => ({ articulo_id: it.articulo_id, cantidad: it.cantidad, elecciones: it.elecciones })),
      { ...cobro, sesion_id: turno.id, descuento: Number(descuento || 0) },
    );
    setCobrando(false);
    setCarritoMovil(false);
    limpiar();
    setHecha({ venta, cambio });
    setVersion((v) => v + 1);
  };

  const panel = (
    <Carrito cart={cart} setCantidad={setCantidad} cliente={cliente} setCliente={setCliente}
      descuento={descuento} setDescuento={setDescuento} total={total} subtotal={subtotal}
      onCobrar={() => setCobrando(true)} onLimpiar={limpiar} />
  );

  return (
    <>
      <header style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Nueva venta</h1>
        {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Turno #{turno.numero}</div>}
      </header>
      <ErrorBanner mensaje={errorTurno} />
      <ErrorBanner mensaje={aviso} />
      {hecha && (
        <div key={hecha.venta.id} role="status" className="card aviso-entrar" style={{ padding: "12px 16px", display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap", borderColor: "var(--accent)" }}>
          <strong>Venta #{hecha.venta.numero} registrada · {fmt(hecha.venta.total)}</strong>
          {hecha.cambio > 0 && <span className="num" style={{ ...GRANDE, fontSize: 20, color: "var(--accent-hover)" }}>Cambio {fmt(hecha.cambio)}</span>}
          <button type="button" className="btn btn-s" style={{ marginLeft: "auto" }}
            onClick={() => imprimirTicketVenta(hecha.venta, { cambio: hecha.cambio }).catch((err) => setAviso(err.message))}>
            Imprimir ticket
          </button>
        </div>
      )}

      <div style={{ display: "flex", gap: 20, alignItems: "flex-start", paddingBottom: isMobile && cart.length ? 72 : 0 }}>
        <section aria-label="Catálogo" style={{ flexGrow: 1, minWidth: 0 }}>
          <Catalogo onElegir={agregar} onCargados={preciosAlDia} cantidades={cantidades} version={version} autoFocus />
        </section>
        {!isMobile && (
          <aside className="card" aria-label="Venta actual" style={{
            width: 380, flexShrink: 0, display: "flex", flexDirection: "column", overflow: "hidden",
            position: "sticky", top: 28, maxHeight: "calc(100vh - 56px)",
          }}>
            {panel}
          </aside>
        )}
      </div>

      {isMobile && cart.length > 0 && !carritoMovil && (
        <div style={{ position: "fixed", left: 12, right: 12, bottom: 84, zIndex: 30 }}>
          <button type="button" onClick={() => setCarritoMovil(true)} style={{
            width: "100%", height: 58, border: 0, borderRadius: 16, background: "var(--accent)", color: "#fff",
            display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 18px",
            font: "600 15px Figtree, sans-serif", cursor: "pointer", boxShadow: "0 6px 18px rgba(194,65,12,.3)",
          }}>
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="num" style={{ minWidth: 28, height: 28, borderRadius: 99, background: "#fff", color: "var(--accent-hover)", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 6px" }}>
                {fmtCant(unidades)}
              </span>
              Ver venta
            </span>
            <span className="num" style={{ ...GRANDE, fontSize: 20 }}>{fmt(total)}</span>
          </button>
        </div>
      )}

      {isMobile && carritoMovil && (
        <div style={{ position: "fixed", inset: 0, zIndex: 40 }}>
          <div className="velo" onClick={() => setCarritoMovil(false)} />
          <section aria-label="Venta actual" className="card hoja" style={{
            position: "absolute", left: 0, right: 0, bottom: 0, borderRadius: "24px 24px 0 0",
            padding: "10px 0 0", display: "flex", flexDirection: "column", maxHeight: "88vh",
          }}>
            <button type="button" aria-label="Cerrar" onClick={() => setCarritoMovil(false)}
              style={{ width: 48, height: 18, border: 0, background: "none", alignSelf: "center", cursor: "pointer", padding: 0 }}>
              <span style={{ display: "block", width: 40, height: 5, borderRadius: 99, background: "var(--border-control)", margin: "0 auto" }} />
            </button>
            {panel}
          </section>
        </div>
      )}

      {eligiendo && (
        <ElegirCombo combo={eligiendo} onClose={() => setEligiendo(null)}
          onElegir={(eleccion) => { agregarLinea(eligiendo, eleccion); setEligiendo(null); }} />
      )}

      {cobrando && (
        <PagoModal total={total} cliente={cliente} cajas={turno.cajas} onCobrar={cobrar}
          onClose={() => {
            // Por si el turno se cerró o un precio cambió mientras se cobraba.
            setCobrando(false);
            recargar();
            setVersion((v) => v + 1);
          }} />
      )}
    </>
  );
}
