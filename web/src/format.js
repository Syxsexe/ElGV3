export const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");

// Plata con 2 decimales como máximo: sumar floats deja colas (0.1 + 0.2).
export const centavos = (n) => Math.round(n * 100) / 100;

// "25 de nov de 2026" para fechas sin hora ("2026-11-25") o el día de un
// timestamp con zona (se toma la fecha tal como viene, en la hora del negocio).
export const fmtFecha = (iso) =>
  new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });

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

// Dígito de verificación DIAN de un NIT (sin el DV); null si no es un NIT válido.
const PESOS_DV = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71];
export function digitoVerificacion(nit) {
  if (!/^\d{1,15}$/.test(nit || "")) return null;
  const suma = [...nit].reverse().reduce((s, d, i) => s + Number(d) * PESOS_DV[i], 0) % 11;
  return suma < 2 ? suma : 11 - suma;
}

// "NIT 900123456-8", "CC 1085…", o "" si no tiene documento.
export function documento(t) {
  if (!t?.numero_identificacion) return "";
  const sigla = { 13: "CC", 31: "NIT", 22: "CE", 41: "Pas.", 12: "TI", 11: "RC" }[t.tipo_identificacion] || "Doc.";
  return `${sigla} ${t.numero_identificacion}${t.dv != null ? `-${t.dv}` : ""}`;
}
