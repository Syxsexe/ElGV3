import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { fmt, fmtCant, fmtFecha } from "../format";
import { useIsMobile } from "../useMediaQuery";

const hora = (iso) => new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
const GRANDE = { fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontWeight: 700 };

function Tarjeta({ titulo, enlace, children }) {
  return (
    <section className="card" aria-label={titulo} style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
        <h2 style={{ fontSize: 16 }}>{titulo}</h2>
        {enlace && <Link to={enlace[0]} style={{ fontSize: 13 }}>{enlace[1]}</Link>}
      </div>
      {children}
    </section>
  );
}

function Fila({ izquierda, derecha, peligro }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 14 }}>
      <span style={{ overflowWrap: "anywhere", minWidth: 0 }}>{izquierda}</span>
      <span className="num" style={{ whiteSpace: "nowrap", color: peligro ? "var(--danger)" : undefined, fontWeight: 600 }}>{derecha}</span>
    </div>
  );
}

// Tablero: el turno, las ventas de hoy y lo que pide atención.
export default function Inicio() {
  const { usuario, puede } = useAuth();
  const isMobile = useIsMobile();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");

  const cargar = useCallback(() => api.inicio()
    .then((d) => { setError(""); setDatos(d); })
    .catch((err) => setError(err.message)), []);
  useEffect(() => { cargar(); }, [cargar]);

  const t = datos?.turno;
  return (
    <>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Hola, {usuario?.usuario}</h1>
        <div style={{ display: "flex", gap: 10 }}>
          <Link to="/venta" className="btn btn-p">Nueva venta</Link>
          <Link to="/cuentas" className="btn btn-s">Cuentas</Link>
        </div>
      </header>
      {error && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>{error}</span>
          <button type="button" className="btn btn-s" onClick={cargar}>Reintentar</button>
        </div>
      )}
      {!datos && !error && <div className="muted">Cargando…</div>}

      {datos && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))", gap: 14, alignItems: "start" }}>
          <Tarjeta titulo="Turno de caja" enlace={["/caja", "Ir a Caja"]}>
            {t ? (
              <>
                <span className="muted" style={{ fontSize: 13 }}>Turno #{t.numero} · desde las {hora(t.abierta_en)} · {t.abierta_por}</span>
                <span className="num" style={{ ...GRANDE, fontSize: 26 }}>{fmt(t.total)}</span>
                <span className="muted" style={{ fontSize: 13, marginTop: -6 }}>{t.ventas} {Number(t.ventas) === 1 ? "venta" : "ventas"} en el turno</span>
                {t.cajas.map((c) => <Fila key={c.caja} izquierda={`Esperado en ${c.caja}`} derecha={fmt(c.esperado)} />)}
              </>
            ) : (
              <>
                <span>No hay turno abierto.</span>
                <Link to="/caja" className="btn btn-p" style={{ alignSelf: "flex-start" }}>Abrir turno</Link>
              </>
            )}
          </Tarjeta>

          <Tarjeta titulo="Ventas de hoy" enlace={puede("reportes.ver") ? ["/reportes", "Reportes"] : null}>
            <span className="num" style={{ ...GRANDE, fontSize: 26 }}>{fmt(datos.hoy.total)}</span>
            <span className="muted" style={{ fontSize: 13, marginTop: -6 }}>{datos.hoy.ventas} {Number(datos.hoy.ventas) === 1 ? "venta" : "ventas"}</span>
            {Number(datos.hoy.tienda) > 0 && <Fila izquierda="Tienda" derecha={fmt(datos.hoy.tienda)} />}
            {Number(datos.hoy.cocina) > 0 && <Fila izquierda="Cocina" derecha={fmt(datos.hoy.cocina)} />}
            {Number(datos.hoy.mixta) > 0 && <Fila izquierda="Tienda y cocina juntas" derecha={fmt(datos.hoy.mixta)} />}
            {Number(datos.hoy.fiado) > 0 && <Fila izquierda="De eso, a crédito" derecha={fmt(datos.hoy.fiado)} />}
          </Tarjeta>

          <Tarjeta titulo="Cuentas abiertas" enlace={["/cuentas", "Ver cuentas"]}>
            {Number(datos.cuentas.abiertas) === 0 ? <span className="muted">No hay cuentas abiertas.</span> : (
              <>
                <span className="num" style={{ ...GRANDE, fontSize: 26 }}>{fmt(datos.cuentas.total)}</span>
                <span className="muted" style={{ fontSize: 13, marginTop: -6 }}>
                  por cobrar en {datos.cuentas.abiertas} {Number(datos.cuentas.abiertas) === 1 ? "cuenta" : "cuentas"}
                </span>
              </>
            )}
          </Tarjeta>

          <Tarjeta titulo="Abonos de hoy" enlace={["/creditos", "Créditos"]}>
            {Number(datos.abonos_hoy.cantidad) === 0 ? <span className="muted">Hoy no se han recibido abonos.</span> : (
              <>
                <span className="num" style={{ ...GRANDE, fontSize: 26 }}>{fmt(datos.abonos_hoy.total)}</span>
                <span className="muted" style={{ fontSize: 13, marginTop: -6 }}>
                  {datos.abonos_hoy.cantidad} {Number(datos.abonos_hoy.cantidad) === 1 ? "abono" : "abonos"}
                  {Number(datos.abonos_hoy.cantidad) > datos.abonos_hoy.ultimos.length && ` (se ven los últimos ${datos.abonos_hoy.ultimos.length})`}
                </span>
                {datos.abonos_hoy.ultimos.map((a) => (
                  <Link key={a.id} to={`/creditos?cliente=${a.cliente_id}`} style={{ color: "inherit", textDecoration: "none" }}>
                    <Fila izquierda={<>{a.nombre} <span className="muted" style={{ fontSize: 12 }}>· {a.metodo} · {hora(a.creado_en)}</span></>}
                      derecha={fmt(a.monto)} />
                  </Link>
                ))}
              </>
            )}
          </Tarjeta>

          <Tarjeta titulo="Créditos vencidos" enlace={["/creditos", "Créditos"]}>
            {Number(datos.cartera_vencida.clientes) === 0 ? <span className="muted">Nadie tiene deudas vencidas.</span> : (
              <>
                <span className="num" style={{ ...GRANDE, fontSize: 26, color: "var(--danger)" }}>{fmt(datos.cartera_vencida.total)}</span>
                <span className="muted" style={{ fontSize: 13, marginTop: -6 }}>
                  {datos.cartera_vencida.clientes} {Number(datos.cartera_vencida.clientes) === 1 ? "cliente" : "clientes"}
                </span>
                {datos.cartera_vencida.top.map((c) => (
                  <Link key={c.cliente_id} to={`/creditos?cliente=${c.cliente_id}`} style={{ color: "inherit", textDecoration: "none" }}>
                    <Fila izquierda={<>{c.nombre} <span className="muted" style={{ fontSize: 12 }}>· desde {fmtFecha(c.desde)}</span></>}
                      derecha={fmt(c.vencido)} peligro />
                  </Link>
                ))}
              </>
            )}
          </Tarjeta>

          <Tarjeta titulo="Stock bajo"
            enlace={puede(["inventario.editar", "compras.registrar"]) ? [puede("compras.registrar") ? "/proveedores" : "/inventario", puede("compras.registrar") ? "Comprar" : "Inventario"] : null}>
            {Number(datos.bajo_minimo.total) === 0 ? <span className="muted">Ningún producto de tienda tiene stock bajo.</span> : (
              <>
                <span className="muted" style={{ fontSize: 13 }}>
                  {datos.bajo_minimo.total} {Number(datos.bajo_minimo.total) === 1 ? "producto" : "productos"}
                  {Number(datos.bajo_minimo.total) > datos.bajo_minimo.productos.length && ` (se ven ${datos.bajo_minimo.productos.length})`}
                </span>
                {datos.bajo_minimo.productos.map((p) => (
                  <Fila key={p.id} izquierda={p.nombre} derecha={`${fmtCant(p.stock)} / mín. ${fmtCant(p.stock_minimo)}`} peligro={Number(p.stock) <= 0} />
                ))}
              </>
            )}
          </Tarjeta>

          {datos.por_pagar && (
            <Tarjeta titulo="Por pagar a proveedores" enlace={["/proveedores", "Proveedores"]}>
              {Number(datos.por_pagar.total) === 0 ? <span className="muted">No se le debe nada a ningún proveedor.</span> : (
                <>
                  <span className="num" style={{ ...GRANDE, fontSize: 26 }}>{fmt(datos.por_pagar.total)}</span>
                  <span className="muted" style={{ fontSize: 13, marginTop: -6 }}>
                    en {datos.por_pagar.compras} {Number(datos.por_pagar.compras) === 1 ? "compra" : "compras"}
                  </span>
                </>
              )}
            </Tarjeta>
          )}
        </div>
      )}
    </>
  );
}
