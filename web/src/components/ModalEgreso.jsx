import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { centavos, fmt } from "../format";
import BuscarTercero from "./BuscarTercero";
import Modal, { Campo, ErrorBanner, Seccion } from "./Modal";
import { IconoQuitar } from "./Iconos";

const num = (v) => centavos(Number(v) || 0);

// Registrar una salida de plata: un gasto (con categoría; nómina = categoría
// Nómina + la persona) o, con `compra`, el pago de esa compra. Se paga con
// plata de las cajas del turno y, si el beneficiario debe fiado, con un cruce
// de cuentas (se le descuenta de lo que se le paga).
// compra: {id, numero, pendiente, proveedor_id, proveedor, proveedor_es_cliente}.
export default function ModalEgreso({ turno, compra, onClose, onHecho }) {
  const { puede } = useAuth();
  const puedeCruzar = puede("creditos.condonar"); // baja una deuda sin que entre plata
  const [metodos, setMetodos] = useState(null);
  const [categorias, setCategorias] = useState([]);
  const [categoriaId, setCategoriaId] = useState("");
  const [concepto, setConcepto] = useState(compra ? `Pago compra #${compra.numero}` : "");
  const [tercero, setTercero] = useState(compra
    ? { id: compra.proveedor_id, nombre: compra.proveedor, es_cliente: compra.proveedor_es_cliente } : null);
  const [filas, setFilas] = useState([]); // [{metodo, monto}]
  const [cruce, setCruce] = useState("");
  const [deuda, setDeuda] = useState(null); // {cliente_id, saldo} del beneficiario, si es cliente
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  // Lo que se carga una sola vez al abrir (en una ref: el padre puede pasar
  // objetos nuevos en cada render).
  const inicial = useRef({ cajas: turno.cajas, compra });

  useEffect(() => {
    const { cajas, compra: deCompra } = inicial.current;
    api.metodosPago()
      .then((ms) => {
        const disponibles = ms.filter((m) => cajas.includes(m.caja_id));
        setMetodos(disponibles);
        setFilas([{ metodo: disponibles[0]?.id ?? "", monto: deCompra ? String(Number(deCompra.pendiente)) : "" }]);
      })
      .catch((err) => setError(err.message));
    if (!deCompra) {
      api.catalogo("categorias-gasto").then((cs) => {
        setCategorias(cs);
        setCategoriaId(cs.find((c) => c.nombre === "Otros")?.id ?? cs[0]?.id ?? "");
      }).catch((err) => setError(err.message));
    }
  }, []);

  // Si al beneficiario se le fía (es cliente), se puede cruzar contra su deuda.
  const idTercero = puedeCruzar && tercero?.es_cliente ? tercero.id : null;
  useEffect(() => {
    if (!idTercero) return undefined;
    let vigente = true;
    api.cupoCliente(idTercero)
      .then((c) => vigente && setDeuda(c))
      .catch((err) => vigente && setError(err.message));
    return () => { vigente = false; };
  }, [idTercero]);

  const saldo = idTercero && deuda?.cliente_id === idTercero ? Number(deuda.saldo) : 0;
  const pagos = filas.filter((f) => f.metodo && num(f.monto) > 0).map((f) => ({ metodo_pago_id: f.metodo, monto: num(f.monto) }));
  const valorCruce = saldo > 0 ? num(cruce) : 0;
  const total = centavos(pagos.reduce((a, p) => a + p.monto, 0) + valorCruce);
  const nombreCategoria = categorias.find((c) => c.id === categoriaId)?.nombre;

  let bloqueo = "";
  if (!concepto.trim()) bloqueo = "Escribe el concepto.";
  else if (!compra && !categoriaId) bloqueo = "Elige la categoría.";
  else if (!compra && nombreCategoria === "Nómina" && !tercero) bloqueo = "Elige a quién se le paga la nómina.";
  else if (filas.some((f) => Number(f.monto) < 0) || Number(cruce) < 0) bloqueo = "Hay un monto negativo.";
  else if (total <= 0) bloqueo = "Escribe cuánto se paga.";
  else if (valorCruce > saldo) bloqueo = `Solo debe ${fmt(saldo)} de crédito.`;
  else if (compra && total > Number(compra.pendiente)) bloqueo = `A la compra le quedan ${fmt(compra.pendiente)} por pagar.`;

  const cambiarFila = (i, cambios) => setFilas((fs) => fs.map((f, j) => (j === i ? { ...f, ...cambios } : f)));

  const guardar = async (e) => {
    e.preventDefault();
    if (bloqueo) return;
    setEnviando(true);
    setError("");
    try {
      const r = await api.registrarEgreso({
        sesion_id: turno.id, concepto: concepto.trim(), pagos, cruce: valorCruce, notas: notas.trim() || null,
        ...(compra ? { compra_id: compra.id } : { categoria_gasto_id: categoriaId, tercero_id: tercero?.id ?? null }),
      });
      onHecho(r);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo={compra ? `Pagar la compra #${compra.numero}` : "Registrar gasto"} onClose={() => !enviando && onClose()} ancho={540}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {compra ? (
          <span className="muted">{compra.proveedor} · le quedan <strong className="num">{fmt(compra.pendiente)}</strong> por pagar · turno #{turno.numero}</span>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
              <Campo etiqueta="Categoría">
                <select className="inp" value={categoriaId} onChange={(e) => setCategoriaId(e.target.value)}>
                  {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select>
              </Campo>
              <Campo etiqueta="Concepto">
                <input className="inp" value={concepto} autoFocus placeholder="Ej.: hielo, arriendo de noviembre" onChange={(e) => setConcepto(e.target.value)} />
              </Campo>
            </div>
            <Seccion etiqueta={nombreCategoria === "Nómina" ? "A quién se le paga" : "A quién se le paga (opcional)"}>
              {tercero ? (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <strong style={{ overflowWrap: "anywhere" }}>{tercero.nombre}</strong>
                  <button type="button" className="btn btn-g" onClick={() => { setTercero(null); setCruce(""); }}>Quitar</button>
                </div>
              ) : (
                <BuscarTercero placeholder="Buscar persona por nombre o documento" onElegir={(t) => setTercero({ id: t.id, nombre: t.nombre, es_cliente: t.es_cliente })} />
              )}
            </Seccion>
          </>
        )}

        <Seccion etiqueta="Plata que sale de la caja">
          {metodos?.length === 0 && <span className="muted">No hay métodos de pago en las cajas del turno.</span>}
          {filas.map((f, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 130px auto", gap: 8 }}>
              <select className="inp" aria-label={`Método ${i + 1}`} value={f.metodo} onChange={(e) => cambiarFila(i, { metodo: e.target.value })}>
                {(metodos || []).map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
              </select>
              <input className="inp num" type="number" min="0" step="any" inputMode="decimal" aria-label={`Monto ${i + 1}`}
                value={f.monto} onChange={(e) => cambiarFila(i, { monto: e.target.value })} />
              <button type="button" className="btn btn-g" aria-label={`Quitar el método ${i + 1}`} disabled={filas.length === 1}
                onClick={() => setFilas((fs) => fs.filter((_, j) => j !== i))}><IconoQuitar /></button>
            </div>
          ))}
          {metodos?.length > 1 && (
            <button type="button" className="btn btn-s" style={{ alignSelf: "flex-start" }}
              onClick={() => setFilas((fs) => [...fs, { metodo: metodos.find((m) => !fs.some((x) => x.metodo === m.id))?.id ?? metodos[0].id, monto: "" }])}>
              Agregar otro método
            </button>
          )}
        </Seccion>

        {saldo > 0 && (
          <Campo etiqueta={`Descontar de su crédito (debe ${fmt(saldo)})`} ayuda="Cruce de cuentas: se abona a su deuda en vez de pagarle esa parte.">
            <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={cruce} placeholder="0"
              onChange={(e) => setCruce(e.target.value)} />
          </Campo>
        )}
        <Campo etiqueta="Notas (opcional)">
          <input className="inp" value={notas} onChange={(e) => setNotas(e.target.value)} />
        </Campo>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontWeight: 600 }}>Total</span>
          <span className="num" style={{ fontSize: 24, fontWeight: 700 }}>{fmt(total)}</span>
        </div>
        {bloqueo && (concepto || total > 0) && <div className="muted" role="status" style={{ fontSize: 14 }}>{bloqueo}</div>}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={!!bloqueo || enviando}>
            {enviando ? "Registrando…" : compra ? `Pagar ${fmt(total)}` : `Registrar ${fmt(total)}`}
          </button>
        </div>
      </form>
    </Modal>
  );
}
