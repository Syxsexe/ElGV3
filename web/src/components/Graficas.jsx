import { useEffect, useRef, useState } from "react";
import { fmt } from "../format";

// Gráficas en SVG propio (sin librerías). Una sola serie por gráfica: un solo
// color (el acento), sin leyenda (el título dice qué se ve). Barras de 24 px
// como máximo con 4 px redondeados en la punta y base recta; cuadrícula de
// 1 px; cada barra muestra su detalle al pasar el cursor o tocarla. Los mismos
// números están en tablas junto a la gráfica.

const COLOR = "var(--accent)";
const COLOR_ACTIVO = "var(--accent-hover)";
const GRILLA = "var(--border)";
const compacto = new Intl.NumberFormat("es-CO", { notation: "compact", maximumFractionDigits: 1 });

// Un tope "redondo" para el eje: 1, 2, 2.5 o 5 por una potencia de 10.
function topeRedondo(max) {
  if (max <= 0) return 1;
  const potencia = 10 ** Math.floor(Math.log10(max));
  const paso = [1, 2, 2.5, 5, 10].find((m) => m * potencia >= max);
  return paso * potencia;
}

// Barra con la punta redondeada y la base recta (crece desde la línea base).
function barra(x, y, ancho, alto) {
  const r = Math.min(4, alto, ancho / 2);
  return `M${x},${y + alto} V${y + r} Q${x},${y} ${x + r},${y} H${x + ancho - r} Q${x + ancho},${y} ${x + ancho},${y + r} V${y + alto} Z`;
}

function useAncho() {
  const ref = useRef(null);
  const [ancho, setAncho] = useState(0);
  useEffect(() => {
    if (!ref.current) return undefined;
    const obs = new ResizeObserver(([e]) => setAncho(e.contentRect.width));
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, ancho];
}

// Columnas verticales (ej. ventas por día). datos = [{etiqueta, corta, valor, detalle: [[nombre, texto]]}].
export function Columnas({ datos, titulo, alto = 220 }) {
  const [ref, ancho] = useAncho();
  const [activo, setActivo] = useState(null);
  const izq = 56, der = 8, arriba = 12, abajo = 26;
  const plotW = Math.max(ancho - izq - der, 0);
  const plotH = alto - arriba - abajo;
  const tope = topeRedondo(Math.max(0, ...datos.map((d) => d.valor)));
  const banda = datos.length ? plotW / datos.length : 0;
  const anchoBarra = Math.max(Math.min(24, banda * 0.7), 2);
  const cadaCuanto = Math.max(1, Math.ceil(datos.length / Math.max(1, Math.floor(plotW / 56))));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * tope);
  const sel = activo != null ? datos[activo] : null;

  return (
    <figure ref={ref} style={{ margin: 0, position: "relative" }} aria-label={titulo}>
      {ancho > 0 && (
        <svg width={ancho} height={alto} role="img" aria-label={titulo} style={{ display: "block", overflow: "visible" }}
          onPointerLeave={() => setActivo(null)}>
          {ticks.map((t) => {
            const y = arriba + plotH - (t / tope) * plotH;
            return (
              <g key={t}>
                <line x1={izq} x2={izq + plotW} y1={y} y2={y} stroke={GRILLA} strokeWidth="1" />
                <text x={izq - 8} y={y} dy="0.32em" textAnchor="end" fontSize="11" fill="var(--text-muted)">
                  {t === 0 ? "0" : `$${compacto.format(t)}`}
                </text>
              </g>
            );
          })}
          {datos.map((d, i) => {
            const h = (d.valor / tope) * plotH;
            const x = izq + i * banda + (banda - anchoBarra) / 2;
            return (
              <g key={d.etiqueta}>
                {h > 0 && <path className="barra-y" style={{ animationDelay: `${Math.min(i * 15, 300)}ms` }} d={barra(x, arriba + plotH - h, anchoBarra, h)} fill={i === activo ? COLOR_ACTIVO : COLOR} />}
                {i % cadaCuanto === 0 && (
                  <text x={izq + i * banda + banda / 2} y={alto - 8} textAnchor="middle" fontSize="11" fill="var(--text-muted)">{d.corta}</text>
                )}
                {/* Zona de toque: toda la columna, más grande que la barra. */}
                <rect x={izq + i * banda} y={arriba} width={banda} height={plotH} fill="transparent"
                  onPointerEnter={() => setActivo(i)} onPointerDown={() => setActivo(i)}>
                  <title>{`${d.etiqueta}: ${fmt(d.valor)}`}</title>
                </rect>
              </g>
            );
          })}
        </svg>
      )}
      {sel && (
        <div role="status" className="card" style={{
          position: "absolute", top: 0, pointerEvents: "none", padding: "8px 10px", fontSize: 13, whiteSpace: "nowrap",
          left: Math.min(Math.max(izq + activo * banda + banda / 2 - 80, 0), Math.max(ancho - 170, 0)),
          boxShadow: "0 4px 12px rgba(28,25,23,.12)",
        }}>
          <strong>{sel.etiqueta}</strong>
          {sel.detalle.map(([n, v]) => (
            <div key={n} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <span className="muted">{n}</span><span className="num">{v}</span>
            </div>
          ))}
        </div>
      )}
    </figure>
  );
}

// Barras horizontales con el valor en la punta (ej. ventas por categoría).
// datos = [{etiqueta, valor, nota?}]; nota va debajo de la etiqueta.
export function Barras({ datos, titulo, formato = fmt }) {
  const max = Math.max(0, ...datos.map((d) => d.valor));
  return (
    <div role="list" aria-label={titulo} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {datos.map((d) => (
        <div key={d.etiqueta} role="listitem" title={`${d.etiqueta}: ${formato(d.valor)}`}
          style={{ display: "grid", gridTemplateColumns: "minmax(80px, 30%) minmax(0, 1fr) auto", gap: 10, alignItems: "center" }}>
          <span style={{ fontSize: 13, overflowWrap: "anywhere", lineHeight: 1.25 }}>
            {d.etiqueta}{d.nota && <span className="muted" style={{ display: "block", fontSize: 11 }}>{d.nota}</span>}
          </span>
          {/* El carril es el 100 %: el largo de la barra es proporcional al valor. */}
          <span style={{ display: "block", minWidth: 0 }}>
            <span className="barra-x" style={{
              display: "block", height: 14, borderRadius: "0 4px 4px 0", background: COLOR,
              width: `${max > 0 ? (d.valor / max) * 100 : 0}%`, minWidth: d.valor > 0 ? 2 : 0,
            }} />
          </span>
          <span className="num" style={{ fontSize: 13, whiteSpace: "nowrap", textAlign: "right" }}>{formato(d.valor)}</span>
        </div>
      ))}
      {datos.length === 0 && <span className="muted" style={{ fontSize: 14 }}>Sin datos en el rango.</span>}
    </div>
  );
}
