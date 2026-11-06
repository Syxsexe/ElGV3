export const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");

export const fmtFechaHora = (iso) =>
  new Date(iso).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" });
