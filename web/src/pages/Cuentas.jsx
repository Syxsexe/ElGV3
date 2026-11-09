import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import BuscarTercero from "../components/BuscarTercero";
import Catalogo from "../components/Catalogo";
import Modal, { Campo, ErrorBanner, Seccion } from "../components/Modal";
import PagoModal from "../components/PagoModal";
import { fmt, fmtCant } from "../format";
import { useIsMobile } from "../useMediaQuery";
import { useTurno } from "../useTurno";

const GRANDE = { fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontWeight: 700 };
const REFRESCO_MS = 20000; // otras pantallas (el celular del mesero) también cambian las cuentas

const hora = (iso) => new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });

// "Mesa 3" arriba y el nombre abajo; sin mesa, el nombre arriba. Si el nombre
// es el de la mesa (se abrió sin escribir otro), no se repite.
function titulos(c) {
  if (!c.mesa) return [c.nombre, ""];
  return [`Mesa ${c.mesa}`, c.nombre !== c.mesa ? c.nombre : ""];
}

// Abrir una cuenta o cambiarle la mesa o el nombre.
function ModalDatosCuenta({ cuenta, abiertas, onClose, onGuardada }) {
  const [mesas, setMesas] = useState(null);
  const [mesaId, setMesaId] = useState(cuenta?.mesa_id || "");
  const [porCliente, setPorCliente] = useState(!!cuenta?.cliente_id);
  const [cliente, setCliente] = useState(cuenta?.cliente_id ? { id: cuenta.cliente_id, nombre: cuenta.cliente } : null);
  const [alias, setAlias] = useState(cuenta?.alias && cuenta.alias !== cuenta.mesa ? cuenta.alias : "");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    // Con las inactivas: la mesa actual de la cuenta puede haberse desactivado.
    api.catalogo("mesas", true).then(setMesas).catch((err) => setError(err.message));
  }, []);

  const ocupadas = new Set(abiertas.filter((c) => c.id !== cuenta?.id && c.mesa_id).map((c) => c.mesa_id));
  const libres = (mesas || []).filter((m) => m.id === cuenta?.mesa_id || (m.activo && !ocupadas.has(m.id)));
  const mesa = mesas?.find((m) => m.id === mesaId);

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    // Sin nombre, una cuenta de mesa se llama como la mesa.
    const nombre = alias.trim() || (mesa ? mesa.nombre : "");
    if (porCliente && !cliente) return setError("Elige el cliente.");
    if (!porCliente && !nombre) return setError("Escribe un nombre o elige una mesa.");
    const body = porCliente ? { cliente_id: cliente.id } : { alias: nombre };
    if (!cuenta || (mesaId || null) !== (cuenta.mesa_id || null)) body.mesa_id = mesaId || null;
    setEnviando(true);
    try {
      onGuardada(cuenta ? await api.editarCuenta(cuenta.id, body) : await api.abrirCuenta(body));
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo={cuenta ? `Cuenta #${cuenta.numero}` : "Abrir cuenta"} onClose={onClose}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Campo etiqueta="Mesa">
          <select className="inp" value={mesaId} onChange={(e) => setMesaId(e.target.value)} disabled={!mesas}>
            <option value="">Sin mesa (para llevar, barra…)</option>
            {libres.map((m) => <option key={m.id} value={m.id}>Mesa {m.nombre}{m.activo ? "" : " (desactivada)"}</option>)}
          </select>
        </Campo>
        <div className="seg" role="tablist" aria-label="A nombre de" style={{ alignSelf: "flex-start" }}>
          <button type="button" role="tab" aria-selected={!porCliente} className={!porCliente ? "on" : ""} onClick={() => setPorCliente(false)}>Nombre</button>
          <button type="button" role="tab" aria-selected={porCliente} className={porCliente ? "on" : ""} onClick={() => setPorCliente(true)}>Cliente registrado</button>
        </div>
        {porCliente ? (
          <Seccion etiqueta="Cliente">
            {cliente ? (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <strong>{cliente.nombre}</strong>
                <button type="button" className="btn btn-g" onClick={() => setCliente(null)}>Cambiar</button>
              </div>
            ) : (
              <BuscarTercero rol="cliente" placeholder="Buscar cliente" onElegir={(t) => setCliente({ id: t.id, nombre: t.nombre })} />
            )}
          </Seccion>
        ) : (
          <Campo etiqueta="Nombre" ayuda={mesa ? `Si lo dejas vacío, la cuenta se llama "Mesa ${mesa.nombre}".` : "Ej.: Juan, Los del torneo."}>
            <input className="inp" value={alias} maxLength={80} onChange={(e) => setAlias(e.target.value)} autoFocus />
          </Campo>
        )}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={enviando}>{cuenta ? "Guardar" : "Abrir cuenta"}</button>
        </div>
      </form>
    </Modal>
  );
}

function ModalCancelar({ cuenta, onClose, onCancelada }) {
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const conConsumos = cuenta.items.length > 0;

  const cancelar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    try {
      onCancelada(await api.cancelarCuenta(cuenta.id, motivo.trim() || null));
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo={`Cancelar la cuenta #${cuenta.numero}`} onClose={onClose}>
      <form onSubmit={cancelar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <span>
          {conConsumos
            ? <>Tiene consumos por <strong className="num">{fmt(cuenta.total)}</strong> que no se van a cobrar. Queda registrado en auditoría.</>
            : "La cuenta no tiene consumos."}
        </span>
        <Campo etiqueta={conConsumos ? "Motivo" : "Motivo (opcional)"}>
          <input className="inp" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus
            placeholder={conConsumos ? "Ej.: se fueron sin pagar, pedido de prueba" : ""} />
        </Campo>
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-d" disabled={enviando || (conConsumos && !motivo.trim())}>Cancelar cuenta</button>
        </div>
      </form>
    </Modal>
  );
}

function DetalleCuenta({ cuenta, turno, isMobile, onCambio, onCerrada, onVolver, onFallo, abiertas }) {
  const [modal, setModal] = useState(null); // "agregar" | "editar" | "cancelar" | "cobrar"
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [titulo, subtitulo] = titulos(cuenta);

  // Cada cambio devuelve la cuenta completa; si falla (otra pantalla la cobró
  // o la canceló), se recarga para mostrar el estado real.
  const accion = async (promesa) => {
    setError("");
    setOcupado(true);
    try {
      onCambio(await promesa);
    } catch (err) {
      setError(err.message);
      onFallo();
    } finally {
      setOcupado(false);
    }
  };

  const cantidades = {};
  cuenta.items.forEach((it) => { cantidades[it.articulo_id] = (cantidades[it.articulo_id] || 0) + Number(it.cantidad); });

  const cobrar = async (cobro, { cambio }) => {
    try {
      const venta = await api.cobrarCuenta(cuenta.id, { ...cobro, sesion_id: turno.id, descuento: 0 });
      setModal(null);
      onCerrada(`Cuenta #${cuenta.numero} cobrada: venta #${venta.numero} por ${fmt(venta.total)}`, cambio);
    } catch (err) {
      onFallo();
      throw err;
    }
  };

  return (
    <section className="card" aria-label={`Cuenta ${titulo}`} style={{ flexGrow: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
      <div style={{ padding: 18, display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid var(--border-2)", gap: 12 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start", minWidth: 0 }}>
          {isMobile && (
            <button type="button" onClick={onVolver} aria-label="Volver a las cuentas" className="btn btn-g" style={{ width: 40, height: 40, padding: 0, flexShrink: 0 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 5l-7 7 7 7" /></svg>
            </button>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
            <h2 style={{ fontSize: isMobile ? 20 : 24, overflowWrap: "anywhere" }}>{titulo}</h2>
            {subtitulo && <span style={{ fontWeight: 600, overflowWrap: "anywhere" }}>{subtitulo}</span>}
            <span className="muted" style={{ fontSize: 13 }}>Cuenta #{cuenta.numero} · desde las {hora(cuenta.abierta_en)} · {cuenta.abierta_por}</span>
          </div>
        </div>
        <button type="button" className="btn btn-g" style={{ flexShrink: 0 }} onClick={() => setModal("editar")}>Editar</button>
      </div>

      <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--border-2)", background: "var(--surface-2)" }}>
        <button type="button" className="btn btn-p" style={{ width: "100%" }} onClick={() => setModal("agregar")}>Agregar consumos</button>
      </div>
      {error && <div style={{ margin: "12px 18px 0" }}><ErrorBanner mensaje={error} /></div>}

      <div style={{ flexGrow: 1, overflowY: "auto", minHeight: 100 }}>
        {cuenta.items.length === 0 ? (
          <div className="muted" style={{ padding: 24, textAlign: "center" }}>Sin consumos todavía.</div>
        ) : cuenta.items.map((it) => (
          <div key={it.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 18px", borderBottom: "1px solid var(--border-2)" }}>
            <div style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: 14, fontWeight: 600, overflowWrap: "anywhere" }}>{it.nombre}</span>
              <span className="muted num" style={{ fontSize: 12 }}>{fmt(it.precio_unit)} c/u · {hora(it.agregado_en)}</span>
            </div>
            <button type="button" className="step" disabled={ocupado} aria-label={`Quitar uno de ${it.nombre}`}
              onClick={() => accion(Number(it.cantidad) > 1
                ? api.cantidadEnCuenta(cuenta.id, it.id, Number(it.cantidad) - 1)
                : api.quitarDeCuenta(cuenta.id, it.id))}>−</button>
            <span className="num" style={{ minWidth: 24, textAlign: "center", fontWeight: 700 }}>{fmtCant(it.cantidad)}</span>
            <button type="button" className="step" disabled={ocupado} aria-label={`Agregar uno de ${it.nombre}`}
              onClick={() => accion(api.cantidadEnCuenta(cuenta.id, it.id, Number(it.cantidad) + 1))}>+</button>
            <span className="num" style={{ width: 84, textAlign: "right", fontWeight: 600, whiteSpace: "nowrap" }}>{fmt(it.subtotal)}</span>
          </div>
        ))}
      </div>

      <div style={{ padding: "14px 18px", display: "flex", flexDirection: "column", gap: 12, borderTop: "1px solid var(--border-2)", background: "var(--surface-2)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>Total</span>
            <span className="num" style={{ ...GRANDE, fontSize: 30 }}>{fmt(cuenta.total)}</span>
          </div>
          <button type="button" className="btn btn-p" style={{ height: 52, padding: "0 28px", fontSize: 16 }}
            disabled={cuenta.items.length === 0 || !turno} onClick={() => setModal("cobrar")}>
            Cobrar cuenta
          </button>
        </div>
        {turno === null && (
          <span className="muted" style={{ fontSize: 13 }}>
            Para cobrar abre el turno en <Link to="/caja">Caja</Link>.
          </span>
        )}
        <button type="button" className="btn btn-d" style={{ alignSelf: isMobile ? "stretch" : "flex-start" }}
          onClick={() => setModal("cancelar")}>
          Cancelar cuenta
        </button>
      </div>

      {modal === "agregar" && (
        <Modal titulo={`Agregar a ${titulo}`} onClose={() => setModal(null)} ancho={860}>
          <ErrorBanner mensaje={error} />
          <Catalogo autoFocus cantidades={cantidades}
            onElegir={(a) => accion(api.agregarACuenta(cuenta.id, a.id))} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, position: "sticky", bottom: -24, background: "#fff", padding: "12px 0", borderTop: "1px solid var(--border-2)" }}>
            <span className="num" style={{ fontWeight: 700 }}>Total {fmt(cuenta.total)}</span>
            <button type="button" className="btn btn-p" onClick={() => setModal(null)}>Listo</button>
          </div>
        </Modal>
      )}
      {modal === "editar" && (
        <ModalDatosCuenta cuenta={cuenta} abiertas={abiertas} onClose={() => setModal(null)}
          onGuardada={(c) => { setModal(null); onCambio(c); }} />
      )}
      {modal === "cancelar" && (
        <ModalCancelar cuenta={cuenta} onClose={() => setModal(null)}
          onCancelada={() => { setModal(null); onCerrada(`Cuenta #${cuenta.numero} cancelada.`); }} />
      )}
      {modal === "cobrar" && (
        <PagoModal total={Number(cuenta.total)} cliente={cuenta.cliente_id ? { id: cuenta.cliente_id, nombre: cuenta.cliente } : null}
          cajas={turno.cajas} onCobrar={cobrar} onClose={() => setModal(null)} />
      )}
    </section>
  );
}

export default function Cuentas() {
  const isMobile = useIsMobile();
  const { turno, error: errorTurno, recargar: recargarTurno } = useTurno();
  const [abiertas, setAbiertas] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [abriendo, setAbriendo] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState(null); // {texto, cambio}

  const cargar = useCallback(() => api.cuentas()
    .then((r) => { setError(""); setAbiertas(r); })
    .catch((err) => setError(err.message)), []);

  useEffect(() => {
    cargar();
    const t = setInterval(() => document.visibilityState === "visible" && cargar(), REFRESCO_MS);
    return () => clearInterval(t);
  }, [cargar]);

  const elegir = (id) => {
    setAviso(null);
    api.cuenta(id).then(setDetalle).catch((err) => setError(err.message));
  };

  // La cuenta en pantalla: si otra pantalla la cerró, se suelta.
  const refrescarDetalle = () => {
    cargar();
    recargarTurno();
    if (detalle) {
      api.cuenta(detalle.id)
        .then((c) => setDetalle(c.estado === "abierta" ? c : null))
        .catch(() => setDetalle(null));
    }
  };

  const actualizar = (c) => {
    setDetalle(c);
    setAbiertas((as) => as && as.map((a) => (a.id === c.id ? { ...a, ...c } : a)));
  };

  const cerrada = (texto, cambio = 0) => {
    setDetalle(null);
    setAviso({ texto, cambio });
    cargar();
  };

  const mostrarLista = !isMobile || !detalle;

  return (
    <>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Cuentas</h1>
          {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Consumos por mesa o por nombre, para cobrar después</div>}
        </div>
        {mostrarLista && (
          <button type="button" className="btn btn-p" onClick={() => setAbriendo(true)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
            Abrir cuenta
          </button>
        )}
      </header>

      {error && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>{error}</span>
          <button type="button" className="btn btn-s" onClick={cargar}>Reintentar</button>
        </div>
      )}
      {errorTurno && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>No se pudo revisar el turno de caja (para cobrar): {errorTurno}</span>
          <button type="button" className="btn btn-s" onClick={recargarTurno}>Reintentar</button>
        </div>
      )}
      {aviso && (
        <div role="status" className="card" style={{ padding: "12px 16px", display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap", borderColor: "var(--accent)" }}>
          <strong>{aviso.texto}</strong>
          {aviso.cambio > 0 && <span className="num" style={{ ...GRANDE, fontSize: 20, color: "var(--accent-hover)" }}>Cambio {fmt(aviso.cambio)}</span>}
        </div>
      )}

      <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
        {mostrarLista && (
          <section aria-label="Cuentas abiertas" style={{ width: isMobile ? "100%" : 400, flexShrink: 0, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: 18 }}>Abiertas</h2>
              {abiertas && <span className="chip neu num">{abiertas.length}</span>}
            </div>
            {!abiertas && !error && <div className="muted">Cargando…</div>}
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, minmax(0, 1fr))", gap: 10 }}>
              {(abiertas || []).map((c) => {
                const [titulo, subtitulo] = titulos(c);
                return (
                  <button key={c.id} type="button" className={`mesa${c.id === detalle?.id ? " on" : ""}`} onClick={() => elegir(c.id)}>
                    <span style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, width: "100%" }}>
                      <span style={{ ...GRANDE, fontSize: 18, overflowWrap: "anywhere" }}>{titulo}</span>
                      <span className="muted num" style={{ fontSize: 12, flexShrink: 0 }}>{hora(c.abierta_en)}</span>
                    </span>
                    <span style={{ fontSize: 14, color: "var(--text-label)", minHeight: 18, overflowWrap: "anywhere" }}>{subtitulo}</span>
                    <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", gap: 8 }}>
                      <span className="chip neu num">{c.lineas} {Number(c.lineas) === 1 ? "ítem" : "ítems"}</span>
                      <span className="num" style={{ fontWeight: 700, fontSize: 16, whiteSpace: "nowrap" }}>{fmt(c.total)}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            {abiertas?.length === 0 && <div className="muted">No hay cuentas abiertas.</div>}
          </section>
        )}

        {detalle && (
          <DetalleCuenta key={detalle.id} cuenta={detalle} turno={turno} isMobile={isMobile} abiertas={abiertas || []}
            onCambio={actualizar} onCerrada={cerrada} onVolver={() => { setDetalle(null); cargar(); }}
            onFallo={refrescarDetalle} />
        )}
        {!detalle && !isMobile && abiertas?.length > 0 && (
          <div className="muted" style={{ alignSelf: "center", flexGrow: 1, textAlign: "center" }}>Elige una cuenta para ver sus consumos.</div>
        )}
      </div>

      {abriendo && (
        <ModalDatosCuenta abiertas={abiertas || []} onClose={() => setAbriendo(false)}
          onGuardada={(c) => { setAbriendo(false); cargar(); setDetalle(c); }} />
      )}
    </>
  );
}
