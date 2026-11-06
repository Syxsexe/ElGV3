export const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");

export const fmtFechaHora = (iso) =>
  new Date(iso).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" });

// Cantidades (stock, gramos): sin decimales de sobra.
export const fmtCant = (n) => Number(n).toLocaleString("es-CO", { maximumFractionDigits: 3 });

// Margen sobre el precio de venta: (precio − costo) / precio.
export const margen = (precio, costo) =>
  Number(precio) > 0 ? `${Math.round(((precio - costo) / precio) * 100)}%` : "—";

// Costos por unidad de insumo ($/g suele ser fracción): hasta 4 decimales.
export const fmtCosto = (n) =>
  "$ " + Number(n).toLocaleString("es-CO", { maximumFractionDigits: Math.abs(n) < 100 ? 4 : 0 });
