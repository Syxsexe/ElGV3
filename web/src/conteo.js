// Total de un conteo de billetes y monedas: {denominacion_id: cantidad}.
export const totalConteo = (denominaciones, cantidades) =>
  denominaciones.reduce((s, d) => s + d.valor * (cantidades[d.id] || 0), 0);
