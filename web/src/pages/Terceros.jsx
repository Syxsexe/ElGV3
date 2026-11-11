import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { ErrorBanner } from "../components/Modal";
import ModalTercero from "../components/ModalTercero";
import { documento, fmt } from "../format";

// Lista de clientes o proveedores (rol), con búsqueda por nombre o documento.
// sinTitulo: cuando va dentro de otra página que ya lo pone (Proveedores).
export default function Terceros({ rol, sinTitulo = false }) {
  const { puede } = useAuth();
  const [q, setQ] = useState("");
  const [lista, setLista] = useState([]);
  const [editando, setEditando] = useState(null); // {id} | {nuevo: true}
  const [error, setError] = useState("");
  const [recargas, setRecargas] = useState(0);
  const ultima = useRef(0);
  const esCliente = rol === "cliente";
  const puedeCrear = esCliente || puede("compras.registrar");

  useEffect(() => {
    const mia = ++ultima.current; // una respuesta de una búsqueda anterior se descarta
    const t = setTimeout(() => {
      api.terceros({ rol, q: q.trim() })
        .then((r) => {
          if (mia !== ultima.current) return;
          setError("");
          setLista(r);
        })
        .catch((err) => mia === ultima.current && setError(err.message));
    }, 200);
    return () => clearTimeout(t);
  }, [rol, q, recargas]);

  const columnas = esCliente ? "1fr 190px 130px 110px 70px 80px" : "1fr 190px 170px 130px 80px";
  const activo = (t) => (esCliente ? t.cliente_activo : t.proveedor_activo);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {!sinTitulo && <h1 style={{ fontSize: 28 }}>{esCliente ? "Clientes" : "Proveedores"}</h1>}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <input className="inp" placeholder="Buscar por nombre o documento" value={q} onChange={(e) => setQ(e.target.value)}
          style={{ maxWidth: 360 }} />
        {puedeCrear && (
          <button type="button" className="btn btn-p" style={{ marginLeft: "auto" }} onClick={() => setEditando({ nuevo: true })}>
            {esCliente ? "+ Nuevo cliente" : "+ Nuevo proveedor"}
          </button>
        )}
      </div>
      <ErrorBanner mensaje={error} />
      <div className="card tabla">
        <div className="th" style={{ gridTemplateColumns: columnas }}>
          <span>Nombre</span><span>Documento</span>
          {esCliente ? (
            <><span>Teléfono</span><span className="r">Cupo</span><span className="r">Días</span></>
          ) : (
            <><span>Contacto</span><span>Teléfono</span></>
          )}
          <span>Estado</span>
        </div>
        {lista.map((t) => (
          <div key={t.id} className="tr" style={{ gridTemplateColumns: columnas, cursor: "pointer" }} onClick={() => setEditando({ id: t.id })}>
            <span>
              <strong>{t.nombre}</strong>
              {t.es_cliente && t.es_proveedor && <span className="muted" style={{ fontSize: 12 }}> · cliente y proveedor</span>}
            </span>
            <span className="num muted">{documento(t) || "—"}</span>
            {esCliente ? (
              <>
                <span className="muted">{t.telefono || "—"}</span>
                <span className="r num">{Number(t.limite_credito) > 0 ? fmt(t.limite_credito) : <span className="muted">Sin crédito</span>}</span>
                <span className="r num">{t.dias_credito}</span>
              </>
            ) : (
              <><span className="muted">{t.contacto || "—"}</span><span className="muted">{t.telefono || "—"}</span></>
            )}
            <span><span className={`chip ${activo(t) ? "ok" : "neu"}`}>{activo(t) ? "Activo" : "Inactivo"}</span></span>
          </div>
        ))}
        {lista.length === 0 && <div className="muted" style={{ padding: 20 }}>Nadie con esa búsqueda.</div>}
      </div>
      {editando && (
        <ModalTercero terceroId={editando.id} rol={rol} onClose={() => setEditando(null)}
          onGuardado={() => { setEditando(null); setRecargas((n) => n + 1); }} />
      )}
    </div>
  );
}
