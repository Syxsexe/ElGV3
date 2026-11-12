import { Fragment, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Barras, Columnas } from "../components/Graficas";
import Modal, { Campo, ErrorBanner } from "../components/Modal";
import { fmt, fmtCant, fmtFechaHora, margen } from "../format";
import { imprimirTicketVenta } from "../imprimir";
import { useIsMobile } from "../useMediaQuery";

const iso = (d) => d.toLocaleDateString("en-CA");
function rangoDe(preset) {
  const hoy = new Date();
  const y = hoy.getFullYear(), m = hoy.getMonth();
  if (preset === "hoy") return [iso(hoy), iso(hoy)];
  if (preset === "7") return [iso(new Date(hoy.getTime() - 6 * 86400000)), iso(hoy)];
  if (preset === "mes") return [iso(new Date(y, m, 1)), iso(hoy)];
  if (preset === "anterior") return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))];
  return null;
}
const PRESETS = [["hoy", "Hoy"], ["7", "7 días"], ["mes", "Este mes"], ["anterior", "Mes pasado"]];
const DIA = (d) => new Date(`${d}T12:00:00`);

function Cifra({ etiqueta, valor, nota, negativo }) {
  return (
    <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 4 }}>
      <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>{etiqueta}</span>
      <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 24, fontWeight: 700,
        color: negativo ? "var(--danger)" : undefined }}>{valor}</span>
      {nota && <span className="muted" style={{ fontSize: 12 }}>{nota}</span>}
    </div>
  );
}

function Bloque({ titulo, nota, children }) {
  return (
    <section className="card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
      <div>
        <h2 style={{ fontSize: 17 }}>{titulo}</h2>
        {nota && <span className="muted" style={{ fontSize: 12 }}>{nota}</span>}
      </div>
      {children}
    </section>
  );
}

// Detalle de una venta: líneas, cómo se pagó, a quién y quién la hizo.
function ModalVenta({ id, onClose }) {
  const [v, setV] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.venta(id).then(setV).catch((err) => setError(err.message)); }, [id]);
  return (
    <Modal titulo={v ? `Venta #${v.numero}` : "Venta"} onClose={onClose} ancho={520}>
      <ErrorBanner mensaje={error} />
      {!v && !error && <div className="muted">Cargando…</div>}
      {v && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="muted" style={{ fontSize: 13 }}>
            {fmtFechaHora(v.creada_en)} · vendió {v.usuario}
            {v.mesa && ` · mesa ${v.mesa}`}{v.cuenta_numero && ` (cuenta #${v.cuenta_numero})`}
          </div>
          <div style={{ fontSize: 14 }}><span className="lbl">Cliente: </span>{v.cliente || <span className="muted">Consumidor final</span>}</div>
          <div className="tabla">
            {v.lineas.map((l, i) => (
              <div key={i} className="tr" style={{ gridTemplateColumns: "50px 1fr 100px" }}>
                <span className="num">{fmtCant(l.cantidad)} ×</span>
                <span style={{ overflowWrap: "anywhere" }}>{l.nombre} <span className="muted num" style={{ fontSize: 12 }}>· {fmt(l.precio_unit)} c/u</span></span>
                <span className="r num">{fmt(l.subtotal)}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 4, fontSize: 14 }}>
            {Number(v.descuento) > 0 && <><span className="muted">Subtotal</span><span className="num">{fmt(v.subtotal)}</span>
              <span className="muted">Descuento</span><span className="num">− {fmt(v.descuento)}</span></>}
            <strong>Total</strong><strong className="num">{fmt(v.total)}</strong>
            {v.pagos.map((p, i) => <Fragment key={i}><span className="muted">{p.metodo}</span><span className="num">{fmt(p.monto)}</span></Fragment>)}
            {Number(v.fiado) > 0 && <><span className="muted">Crédito</span><span className="num">{fmt(v.fiado)}</span></>}
          </div>
          {v.notas && <div className="muted" style={{ fontSize: 13 }}>Notas: {v.notas}</div>}
          <button type="button" className="btn btn-s" style={{ alignSelf: "flex-start" }}
            onClick={() => imprimirTicketVenta(v, { reimpresion: true }).catch((err) => setError(err.message))}>
            Reimprimir ticket
          </button>
        </div>
      )}
    </Modal>
  );
}

// Las ventas del rango, con cómo se pagaron y a quién; tocar una abre su detalle.
function VentasDelRango({ desde, hasta, isMobile }) {
  const [q, setQ] = useState("");
  const [datos, setDatos] = useState(null); // {total, ventas}
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [abierta, setAbierta] = useState(null);
  const ultima = useRef(0);

  useEffect(() => {
    const mia = ++ultima.current;
    const t = setTimeout(() => api.ventasDelRango(desde, hasta, q.trim())
      .then((r) => { if (mia === ultima.current) { setError(""); setDatos(r); } })
      .catch((err) => { if (mia === ultima.current) { setError(err.message); setDatos(null); } }), 250);
    return () => clearTimeout(t);
  }, [desde, hasta, q]);

  const verMas = () => {
    const mia = ultima.current;
    setCargando(true);
    api.ventasDelRango(desde, hasta, q.trim(), datos.ventas.length)
      .then((r) => {
        if (mia !== ultima.current) return;
        // Si hubo ventas nuevas mientras se miraba, la página siguiente repite
        // algunas de arriba: se descartan las que ya están.
        setDatos((d) => {
          const vistas = new Set(d.ventas.map((v) => v.id));
          return { total: r.total, ventas: [...d.ventas, ...r.ventas.filter((v) => !vistas.has(v.id))] };
        });
      })
      .catch((err) => { if (mia === ultima.current) setError(err.message); })
      .finally(() => setCargando(false));
  };

  const columnas = isMobile ? "1fr auto" : "130px 70px minmax(0, 1fr) minmax(0, 1fr) 110px";
  return (
    <Bloque titulo="Ventas del periodo" nota={datos ? `${datos.total} ${Number(datos.total) === 1 ? "venta" : "ventas"} · toca una para ver su detalle` : null}>
      <input className="inp" type="search" aria-label="Buscar venta" placeholder="Buscar por cliente, mesa o número de venta"
        value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 380 }} />
      <ErrorBanner mensaje={error} />
      {datos && datos.ventas.length === 0 && <span className="muted" style={{ fontSize: 14 }}>{q.trim() ? "Ninguna venta coincide." : "Sin ventas en el rango."}</span>}
      {datos && datos.ventas.length > 0 && (
        <div className="tabla" role="table" aria-label="Ventas del periodo">
          {!isMobile && (
            <div className="th" role="row" style={{ gridTemplateColumns: columnas }}>
              <span>Fecha</span><span>N.º</span><span>Cliente</span><span>Método</span><span className="r">Total</span>
            </div>
          )}
          {datos.ventas.map((v) => (
            <button key={v.id} type="button" role="row" className="tr" onClick={() => setAbierta(v.id)}
              aria-label={`Venta #${v.numero} por ${fmt(v.total)}`}
              style={{ gridTemplateColumns: columnas, width: "100%", border: 0, background: "none", font: "inherit", color: "inherit", textAlign: "left", cursor: "pointer" }}>
              {isMobile ? (
                <>
                  <span style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                    <strong style={{ overflowWrap: "anywhere" }}>{v.cliente || (v.mesa ? `Mesa ${v.mesa}` : "Consumidor final")}</strong>
                    <span className="muted" style={{ fontSize: 12 }}>#{v.numero} · {fmtFechaHora(v.creada_en)} · {v.metodos || "—"}</span>
                  </span>
                  <span className="r num" style={{ fontWeight: 600 }}>{fmt(v.total)}</span>
                </>
              ) : (
                <>
                  <span className="num muted" style={{ fontSize: 13 }}>{fmtFechaHora(v.creada_en)}</span>
                  <span className="num">#{v.numero}</span>
                  <span style={{ overflowWrap: "anywhere" }}>
                    {v.cliente || <span className="muted">Consumidor final</span>}
                    {v.mesa && <span className="muted" style={{ fontSize: 12 }}> · mesa {v.mesa}</span>}
                  </span>
                  <span style={{ overflowWrap: "anywhere" }}>{v.metodos || <span className="muted">—</span>}</span>
                  <span className="r num" style={{ fontWeight: 600 }}>{fmt(v.total)}</span>
                </>
              )}
            </button>
          ))}
        </div>
      )}
      {datos && datos.ventas.length < Number(datos.total) && (
        <button type="button" className="btn btn-s" style={{ alignSelf: "center" }} disabled={cargando} onClick={verMas}>
          {cargando ? "Cargando…" : `Ver más (${Number(datos.total) - datos.ventas.length} restantes)`}
        </button>
      )}
      {abierta && <ModalVenta id={abierta} onClose={() => setAbierta(null)} />}
    </Bloque>
  );
}

// Reportes del negocio por rango de fechas (permiso reportes.ver).
export default function Reportes() {
  const isMobile = useIsMobile();
  const [preset, setPreset] = useState("mes");
  const [rango, setRango] = useState(() => rangoDe("mes"));
  const [rep, setRep] = useState(null);
  const [error, setError] = useState("");
  const ultima = useRef(0);

  useEffect(() => {
    const [desde, hasta] = rango;
    const mia = ++ultima.current; // también invalida una respuesta que siga en camino
    if (!desde || !hasta) return undefined;
    const t = setTimeout(() => api.reporte(desde, hasta)
      .then((r) => { if (mia === ultima.current) { setError(""); setRep(r); } })
      .catch((err) => { if (mia === ultima.current) { setError(err.message); setRep(null); } }), 150);
    return () => clearTimeout(t);
  }, [rango]);
  const incompleto = !rango[0] || !rango[1];

  const elegir = (p) => { setPreset(p); setRango(rangoDe(p)); };
  const res = rep?.resumen;
  const dias = (rep?.por_dia || []).map((d) => ({
    etiqueta: DIA(d.dia).toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short" }),
    corta: DIA(d.dia).toLocaleDateString("es-CO", { day: "numeric", month: rep.por_dia.length > 31 ? "short" : undefined }),
    valor: Number(d.ventas),
    detalle: [["Ventas", fmt(d.ventas)], ["N.º de ventas", d.cantidad], ["Gastos", fmt(d.gastos)]],
  }));

  return (
    <>
      <header style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Reportes</h1>
        {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Montos con impuestos incluidos, como se cobran</div>}
      </header>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div className="seg" role="tablist" aria-label="Periodo" style={{ maxWidth: "100%", overflowX: "auto" }}>
          {PRESETS.map(([k, n]) => (
            <button key={k} type="button" role="tab" aria-selected={preset === k} className={preset === k ? "on" : ""} onClick={() => elegir(k)}>{n}</button>
          ))}
        </div>
        <Campo etiqueta="Desde"><input className="inp" type="date" value={rango[0]} onChange={(e) => { setPreset(""); setRango([e.target.value, rango[1]]); }} /></Campo>
        <Campo etiqueta="Hasta"><input className="inp" type="date" value={rango[1]} onChange={(e) => { setPreset(""); setRango([rango[0], e.target.value]); }} /></Campo>
      </div>
      <ErrorBanner mensaje={error} />
      {incompleto && <div className="muted">Elige las dos fechas del rango.</div>}
      {!incompleto && !rep && !error && <div className="muted">Cargando…</div>}

      {res && !incompleto && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
            <Cifra etiqueta="Ventas" valor={fmt(res.total)}
              nota={`${res.cantidad} ${Number(res.cantidad) === 1 ? "venta" : "ventas"}${Number(res.descuentos) > 0 ? ` · descuentos ${fmt(res.descuentos)}` : ""}`} />
            <Cifra etiqueta="Costo de lo vendido" valor={fmt(res.costo)} />
            <Cifra etiqueta="Utilidad bruta" valor={fmt(res.utilidad_bruta)} nota={res.margen != null ? `Margen ${res.margen}%` : null}
              negativo={Number(res.utilidad_bruta) < 0} />
            <Cifra etiqueta="Gastos" valor={fmt(res.gastos)} nota="Sin pagos de compras (van al costo)" />
            <Cifra etiqueta="Premios de torneos" valor={fmt(res.premios)} />
            {Number(res.condonado) > 0 && <Cifra etiqueta="Crédito condonado" valor={fmt(res.condonado)} nota="Deuda perdonada: esa plata no llega" />}
            <Cifra etiqueta="Resultado" valor={fmt(res.resultado)}
              nota={`Ventas − costo − gastos − premios${Number(res.condonado) > 0 ? " − crédito condonado" : ""}`} negativo={Number(res.resultado) < 0} />
          </div>

          <Bloque titulo="Ventas por día" nota="Pasa el cursor o toca una barra para ver el detalle del día.">
            <Columnas key={rango.join("|")} datos={dias} titulo="Ventas por día" />
          </Bloque>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 380px), 1fr))", gap: 12 }}>
            <Bloque titulo="Ventas por categoría" nota="Antes de descuentos · margen sobre el precio">
              <Barras titulo="Ventas por categoría" datos={rep.por_categoria.map((c) => ({
                etiqueta: c.categoria, valor: Number(c.ventas),
                nota: `${c.tipo === "cocina" ? "Cocina" : "Tienda"} · margen ${margen(c.ventas, c.costo)}`,
              }))} />
            </Bloque>
            <Bloque titulo="Cómo pagaron">
              <Barras titulo="Ventas por método de pago" datos={rep.por_metodo.map((m) => ({ etiqueta: m.metodo, valor: Number(m.monto) }))} />
            </Bloque>
            <Bloque titulo="Gastos por categoría" nota="Sin anulados ni pagos de compras">
              <Barras titulo="Gastos por categoría" datos={rep.gastos_por_categoria.map((g) => ({ etiqueta: g.categoria, valor: Number(g.monto) }))} />
            </Bloque>
            <Bloque titulo="Torneos">
              {Number(rep.torneos.cantidad) === 0 ? <span className="muted" style={{ fontSize: 14 }}>Sin torneos en el rango.</span> : (
                <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 6, fontSize: 14 }}>
                  <span>Torneos</span><span className="num">{rep.torneos.cantidad}</span>
                  <span>Jugadores</span><span className="num">{rep.torneos.jugadores}</span>
                  <span>Recaudado</span><span className="num">{fmt(rep.torneos.recaudado)}</span>
                  <span>Premios</span><span className="num">{fmt(rep.torneos.premios)}</span>
                  <strong>Ganancia</strong><strong className="num">{fmt(rep.torneos.ganancia)}</strong>
                </div>
              )}
            </Bloque>
          </div>

          <Bloque titulo="Lo más vendido" nota="Antes de descuentos">
            {rep.productos.length === 0 ? <span className="muted" style={{ fontSize: 14 }}>Sin ventas en el rango.</span> : (
              <div className="tabla">
                <div className="th" style={{ gridTemplateColumns: "1fr 90px 120px 80px" }}>
                  <span>Artículo</span><span className="r">Unidades</span><span className="r">Ventas</span><span className="r">Margen</span>
                </div>
                {rep.productos.map((p) => (
                  <div key={p.id} className="tr" style={{ gridTemplateColumns: "1fr 90px 120px 80px" }}>
                    <span style={{ overflowWrap: "anywhere" }}>{p.nombre}</span>
                    <span className="r num">{fmtCant(p.unidades)}</span>
                    <span className="r num">{fmt(p.ventas)}</span>
                    <span className="r num">{margen(p.ventas, p.costo)}</span>
                  </div>
                ))}
              </div>
            )}
          </Bloque>

          <VentasDelRango desde={rango[0]} hasta={rango[1]} isMobile={isMobile} />

          <Bloque titulo="Detalle por día">
            <div className="tabla">
              <div className="th" style={{ gridTemplateColumns: "1fr 80px 120px 120px" }}>
                <span>Día</span><span className="r">Ventas</span><span className="r">Monto</span><span className="r">Gastos</span>
              </div>
              {rep.por_dia.filter((d) => Number(d.cantidad) > 0 || Number(d.gastos) > 0).map((d) => (
                <div key={d.dia} className="tr" style={{ gridTemplateColumns: "1fr 80px 120px 120px" }}>
                  <span>{DIA(d.dia).toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short", year: "numeric" })}</span>
                  <span className="r num">{d.cantidad}</span>
                  <span className="r num">{fmt(d.ventas)}</span>
                  <span className="r num">{fmt(d.gastos)}</span>
                </div>
              ))}
            </div>
          </Bloque>
        </>
      )}
    </>
  );
}
