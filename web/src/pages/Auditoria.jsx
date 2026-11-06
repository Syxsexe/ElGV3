import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { ErrorBanner } from "../components/Modal";
import { fmtFechaHora } from "../format";

const ACCIONES = ["login", "caja", "venta", "cuenta", "credito", "gasto", "compra",
  "inventario", "cliente", "torneo", "documento", "usuario", "sistema"];
const POR_PAGINA = 100;

export default function Auditoria() {
  const { puede } = useAuth();
  const [filtros, setFiltros] = useState({ desde: "", hasta: "", usuario_id: "", accion: "" });
  const [eventos, setEventos] = useState([]);
  const [hayMas, setHayMas] = useState(false);
  const [usuarios, setUsuarios] = useState([]);
  const [error, setError] = useState("");

  // La lista de usuarios para filtrar solo la ve quien gestiona usuarios.
  useEffect(() => {
    if (puede("usuarios.gestionar")) api.usuarios().then(setUsuarios).catch(() => {});
  }, [puede]);

  const buscar = useCallback((antes) => {
    api.auditoria({ ...filtros, antes, limite: POR_PAGINA })
      .then((pagina) => {
        setError("");
        setEventos((previos) => (antes ? [...previos, ...pagina] : pagina));
        setHayMas(pagina.length === POR_PAGINA);
      })
      .catch((err) => setError(err.message));
  }, [filtros]);

  useEffect(() => {
    buscar();
  }, [buscar]);

  const cambiar = (campo) => (e) => setFiltros((f) => ({ ...f, [campo]: e.target.value }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h1 style={{ fontSize: 28 }}>Auditoría</h1>
      <div style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span className="lbl">Desde</span>
          <input className="inp" type="date" value={filtros.desde} onChange={cambiar("desde")} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span className="lbl">Hasta</span>
          <input className="inp" type="date" value={filtros.hasta} onChange={cambiar("hasta")} />
        </label>
        {usuarios.length > 0 && (
          <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span className="lbl">Usuario</span>
            <select className="inp" value={filtros.usuario_id} onChange={cambiar("usuario_id")}>
              <option value="">Todos</option>
              {usuarios.map((u) => <option key={u.id} value={u.id}>{u.usuario}</option>)}
            </select>
          </label>
        )}
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span className="lbl">Acción</span>
          <select className="inp" value={filtros.accion} onChange={cambiar("accion")}>
            <option value="">Todas</option>
            {ACCIONES.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
      </div>
      <ErrorBanner mensaje={error} />
      <div className="card" style={{ overflow: "hidden" }}>
        <div className="th" style={{ gridTemplateColumns: "130px 110px 90px 1fr" }}>
          <span>Fecha</span><span>Usuario</span><span>Acción</span><span>Detalle</span>
        </div>
        {eventos.map((e) => (
          <div key={e.id} className="tr" style={{ gridTemplateColumns: "130px 110px 90px 1fr", fontSize: 13 }}>
            <span className="num muted">{fmtFechaHora(e.creado_en)}</span>
            <span>{e.usuario || <span className="muted">sistema</span>}</span>
            <span><span className="chip neu">{e.accion}</span></span>
            <span style={{ overflowWrap: "anywhere" }}>{e.detalle}</span>
          </div>
        ))}
        {eventos.length === 0 && <div className="muted" style={{ padding: 20 }}>Sin eventos con esos filtros.</div>}
      </div>
      {hayMas && (
        <button type="button" className="btn btn-s" style={{ alignSelf: "center" }}
          onClick={() => buscar(eventos[eventos.length - 1].id)}>Cargar más</button>
      )}
    </div>
  );
}
