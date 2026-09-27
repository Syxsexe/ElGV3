import { useEffect, useState } from "react";
import { api } from "../api";
import PagoModal from "../components/PagoModal";
import { useIsMobile } from "../useMediaQuery";

const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");

function AbrirCuentaModal({ onClose, onCreated }) {
  const [cliente, setCliente] = useState("Consumidor final");
  const [mesa, setMesa] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.siguienteMesa().then((r) => setMesa(r.mesa)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setEnviando(true);
    try {
      const r = await api.abrirCuenta(cliente || "Consumidor final", mesa);
      onCreated(r.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(42,38,34,.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }}>
      <form className="card" onSubmit={submit} style={{ width: 380, maxWidth: "100%", padding: 24, display: "flex", flexDirection: "column", gap: 14 }}>
        <h2 style={{ fontSize: 22 }}>Abrir cuenta nueva</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label className="lbl" htmlFor="cli">Cliente</label>
          <input className="inp" id="cli" value={cliente} onChange={(e) => setCliente(e.target.value)} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label className="lbl" htmlFor="mesa">Mesa / puesto</label>
          <input className="inp" id="mesa" value={mesa} onChange={(e) => setMesa(e.target.value)} required />
        </div>
        {error && <div className="error-banner">{error}</div>}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Cancelar</button>
          <button type="submit" className="btn btn-p" disabled={enviando}>{enviando ? "Abriendo…" : "Abrir cuenta"}</button>
        </div>
      </form>
    </div>
  );
}

function BuscadorProducto({ onAgregar }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);
  const [cantidad, setCantidad] = useState(1);
  const [buscando, setBuscando] = useState(false);

  useEffect(() => {
    if (!q.trim()) { setResultados([]); return; }
    const t = setTimeout(async () => {
      setBuscando(true);
      try {
        const r = await api.buscarProductos(q);
        setResultados(r);
      } finally {
        setBuscando(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div style={{ position: "relative" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 90px auto", gap: 10, alignItems: "end" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label className="lbl" htmlFor="bp">Agregar consumo</label>
          <input className="inp" id="bp" type="search" placeholder="Buscar producto"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label className="lbl" htmlFor="cn">Cantidad</label>
          <input className="inp num" id="cn" type="number" min="1" value={cantidad}
            onChange={(e) => setCantidad(Number(e.target.value) || 1)} />
        </div>
      </div>
      {buscando && <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>Buscando…</div>}
      {resultados.length > 0 && (
        <div className="card" style={{ position: "absolute", top: "100%", left: 0, right: 0, marginTop: 6, zIndex: 5, maxHeight: 240, overflowY: "auto" }}>
          {resultados.map((p) => (
            <button key={p.id} type="button" onClick={() => { onAgregar(p.id, cantidad); setQ(""); setResultados([]); }}
              style={{ display: "flex", justifyContent: "space-between", width: "100%", padding: "10px 14px", border: 0, borderBottom: "1px solid var(--border-2)", background: "#fff", cursor: "pointer", font: "inherit", textAlign: "left" }}>
              <span>{p.nombre}</span>
              <span className="num muted">{fmt(p.precio_venta)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function DetalleCuenta({ cuenta, onVolver, onRefrescar, isMobile }) {
  const [error, setError] = useState("");
  const [mostrarCobro, setMostrarCobro] = useState(false);

  const agregar = async (productoId, cantidad) => {
    setError("");
    try {
      await api.agregarItemCuenta(cuenta.id, { producto_id: productoId, cantidad });
      onRefrescar();
    } catch (err) {
      setError(err.message);
    }
  };

  const cambiarCantidad = async (itemId, delta, actual) => {
    const nueva = actual + delta;
    setError("");
    try {
      if (nueva <= 0) await api.quitarItem(itemId);
      else await api.cambiarCantidadItem(itemId, nueva);
      onRefrescar();
    } catch (err) {
      setError(err.message);
    }
  };

  const cancelar = async () => {
    if (!window.confirm(`¿Cancelar la cuenta de ${cuenta.cliente}?`)) return;
    setError("");
    try {
      await api.cancelarCuenta(cuenta.id);
      onVolver();
    } catch (err) {
      setError(err.message);
    }
  };

  const cobrar = async (pagos) => {
    await api.cobrarCuenta(cuenta.id, { pagos });
    setMostrarCobro(false);
    onVolver();
  };

  return (
    <section className="card" style={{ flexGrow: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
      <div style={{ padding: 20, display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid var(--border-2)", gap: 12 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          {isMobile && (
            <button type="button" onClick={onVolver} aria-label="Volver a mesas" className="btn btn-g" style={{ width: 40, height: 40, padding: 0, flexShrink: 0 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 5l-7 7 7 7" /></svg>
            </button>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <h2 style={{ fontSize: isMobile ? 19 : 24 }}>{cuenta.mesa} — {cuenta.cliente}</h2>
            <div className="muted" style={{ fontSize: 14 }}>Abierta desde {cuenta.abierta_en?.slice(11, 16)}</div>
          </div>
        </div>
        {!isMobile && <button type="button" className="btn btn-d" onClick={cancelar}>Cancelar cuenta</button>}
      </div>

      <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border-2)", background: "var(--surface-2)" }}>
        <BuscadorProducto onAgregar={agregar} />
      </div>

      {error && <div className="error-banner" style={{ margin: "12px 20px 0" }}>{error}</div>}

      <div style={{ flexGrow: 1, overflowY: "auto" }}>
        {cuenta.items.length === 0 ? (
          <div className="muted" style={{ padding: 24, textAlign: "center" }}>Sin ítems todavía.</div>
        ) : (
          cuenta.items.map((it) => (
            <div key={it.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 20px", borderBottom: "1px solid var(--border-2)", fontSize: 14 }}>
              <span style={{ flexGrow: 1, fontWeight: 600 }}>{it.nombre}</span>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button type="button" className="step" onClick={() => cambiarCantidad(it.id, -1, it.cantidad)}>−</button>
                <span className="num" style={{ width: 24, textAlign: "center", fontWeight: 700 }}>{it.cantidad}</span>
                <button type="button" className="step" onClick={() => cambiarCantidad(it.id, 1, it.cantidad)}>+</button>
              </div>
              <span className="num" style={{ width: 90, textAlign: "right", fontWeight: 600 }}>{fmt(it.subtotal)}</span>
            </div>
          ))
        )}
      </div>

      <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 12, borderTop: "1px solid var(--border-2)", background: "var(--surface-2)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>Total a cobrar</span>
            <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 32, fontWeight: 700 }}>{fmt(cuenta.total)}</span>
          </div>
          <button type="button" className="btn btn-p" style={{ height: 52, padding: "0 28px", fontSize: 16 }}
            disabled={cuenta.items.length === 0} onClick={() => setMostrarCobro(true)}>
            Cobrar cuenta
          </button>
        </div>
        {isMobile && <button type="button" className="btn btn-d" onClick={cancelar}>Cancelar cuenta</button>}
      </div>

      {mostrarCobro && (
        <PagoModal total={cuenta.total} onCancel={() => setMostrarCobro(false)} onConfirm={cobrar} />
      )}
    </section>
  );
}

export default function Cuentas() {
  const isMobile = useIsMobile();
  const [mesas, setMesas] = useState([]);
  const [seleccionId, setSeleccionId] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [mostrarAbrir, setMostrarAbrir] = useState(false);
  const [error, setError] = useState("");

  const cargarMesas = async () => {
    try {
      setMesas(await api.cuentasAbiertas());
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => { cargarMesas(); }, []);

  useEffect(() => {
    if (seleccionId == null) { setDetalle(null); return; }
    api.obtenerCuenta(seleccionId).then(setDetalle).catch((err) => setError(err.message));
  }, [seleccionId]);

  const refrescarDetalle = async () => {
    if (seleccionId == null) return;
    setDetalle(await api.obtenerCuenta(seleccionId));
    cargarMesas();
  };

  const volver = () => {
    setSeleccionId(null);
    cargarMesas();
  };

  const mostrarLista = !isMobile || seleccionId == null;
  const mostrarDetalle = !isMobile || seleccionId != null;

  return (
    <>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Cuentas</h1>
          {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Mesas abiertas y consumo por cliente</div>}
        </div>
        <button type="button" className="btn btn-p" onClick={() => setMostrarAbrir(true)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
          Abrir cuenta
        </button>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div style={{ display: "flex", gap: 20, flexGrow: 1, minHeight: 0 }}>
        {mostrarLista && (
          <section aria-label="Mesas abiertas" style={{ width: isMobile ? "100%" : 420, flexShrink: 0, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: 18 }}>Mesas abiertas</h2>
              <span className="chip neu">{mesas.length} abiertas</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, minmax(0,1fr))", gap: 12 }}>
              {mesas.map((m) => (
                <button key={m.id} type="button" className={`mesa${m.id === seleccionId ? " on" : ""}`} onClick={() => setSeleccionId(m.id)}>
                  <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                    <span style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 20, fontWeight: 700 }}>{m.mesa}</span>
                    <span className="muted num" style={{ fontSize: 12 }}>{m.abierta_en?.slice(11, 16)}</span>
                  </span>
                  <span style={{ fontSize: 14, color: "var(--text-label)" }}>{m.cliente}</span>
                  <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                    <span className="chip neu num">{m.num_items} ítems</span>
                    <span className="num" style={{ fontWeight: 700, fontSize: 16 }}>{fmt(m.total)}</span>
                  </span>
                </button>
              ))}
              {mesas.length === 0 && <div className="muted">No hay mesas abiertas.</div>}
            </div>
          </section>
        )}

        {mostrarDetalle && detalle && (
          <DetalleCuenta cuenta={detalle} onVolver={volver} onRefrescar={refrescarDetalle} isMobile={isMobile} />
        )}
      </div>

      {mostrarAbrir && (
        <AbrirCuentaModal onClose={() => setMostrarAbrir(false)}
          onCreated={(id) => { setMostrarAbrir(false); cargarMesas(); setSeleccionId(id); }} />
      )}
    </>
  );
}
