const API_BASE = import.meta.env.VITE_API_BASE;
const TOKEN_KEY = "elg_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// AuthContext escucha este evento para sincronizar su estado en React: sin
// esto, un 401 limpia localStorage pero el `token` en memoria de React sigue
// viendo la sesión como activa (Layout no redirige a /login) hasta recargar.
export const UNAUTHORIZED_EVENT = "elg:unauthorized";

function notificarNoAutorizado() {
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
}

// FastAPI manda `detail` como string en nuestros errores de negocio (400/403),
// pero como un ARRAY de objetos {msg,...} en errores 422 de validación de
// Pydantic — sin esto, `new Error(array)` se convierte en "[object Object]" y
// el mensaje real nunca le llega al usuario.
function mensajeDeError(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d?.msg || JSON.stringify(d)).join("; ");
  }
  if (detail) return JSON.stringify(detail);
  return `Error ${status}`;
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Un 401 con token es una sesión vencida o revocada. Sin token (el propio
  // login) es "usuario o contraseña incorrectos": se muestra el detail del servidor.
  if (res.status === 401 && token) {
    clearToken();
    notificarNoAutorizado();
    throw new ApiError("Sesión expirada, vuelve a ingresar.", 401);
  }

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    throw new ApiError(mensajeDeError(data, res.status), res.status);
  }
  return data;
}

export const api = {
  login: (usuario, contrasena) =>
    request("/auth/login", { method: "POST", body: { usuario, contrasena } }),
  yo: () => request("/auth/yo"),
  cambiarMiContrasena: (actual, nueva) =>
    request("/auth/contrasena", { method: "POST", body: { actual, nueva } }),

  usuarios: () => request("/usuarios"),
  crearUsuario: (body) => request("/usuarios", { method: "POST", body }),
  editarUsuario: (id, body) => request(`/usuarios/${id}`, { method: "PATCH", body }),
  restablecerContrasena: (id, contrasena) =>
    request(`/usuarios/${id}/contrasena`, { method: "POST", body: { contrasena } }),
  roles: () => request("/roles"),
  permisos: () => request("/permisos"),
  crearRol: (body) => request("/roles", { method: "POST", body }),
  editarRol: (id, body) => request(`/roles/${id}`, { method: "PATCH", body }),
  borrarRol: (id) => request(`/roles/${id}`, { method: "DELETE" }),

  empresa: () => request("/config/empresa"),
  editarEmpresa: (body) => request("/config/empresa", { method: "PATCH", body }),
  tiposIdentificacion: () => request("/config/tipos-identificacion"),
  municipios: (q) => request(`/config/municipios?q=${encodeURIComponent(q)}`),
  cajas: () => request("/config/cajas"),
  metodosPago: () => request("/config/metodos-pago"),
  crearCaja: (body) => request("/config/cajas", { method: "POST", body }),
  editarCaja: (id, body) => request(`/config/cajas/${id}`, { method: "PATCH", body }),
  crearMetodoPago: (body) => request("/config/metodos-pago", { method: "POST", body }),
  editarMetodoPago: (id, body) => request(`/config/metodos-pago/${id}`, { method: "PATCH", body }),
  // catalogo: "mesas" | "categorias-gasto" | "juegos"
  catalogo: (catalogo, todos = false) => request(`/config/${catalogo}${todos ? "?todos=true" : ""}`),
  crearEnCatalogo: (catalogo, nombre) => request(`/config/${catalogo}`, { method: "POST", body: { nombre } }),
  editarEnCatalogo: (catalogo, id, body) => request(`/config/${catalogo}/${id}`, { method: "PATCH", body }),

  // filtros: {q, tipo, categoria_tipo}
  vendibles: (q, tipo, filtros = {}) =>
    request(`/catalogo/vendibles?${new URLSearchParams(Object.entries({ q, tipo, ...filtros }).filter(([, v]) => v))}`),
  categorias: () => request("/catalogo/categorias"),
  crearCategoria: (body) => request("/catalogo/categorias", { method: "POST", body }),
  editarCategoria: (id, body) => request(`/catalogo/categorias/${id}`, { method: "PATCH", body }),
  borrarCategoria: (id) => request(`/catalogo/categorias/${id}`, { method: "DELETE" }),
  impuestos: () => request("/catalogo/impuestos"),
  unidades: () => request("/catalogo/unidades"),
  articulos: (filtros = {}) =>
    request(`/catalogo/articulos?${new URLSearchParams(Object.entries(filtros).filter(([, v]) => v))}`),
  articulo: (id) => request(`/catalogo/articulos/${id}`),
  crearArticulo: (body) => request("/catalogo/articulos", { method: "POST", body }),
  editarArticulo: (id, body) => request(`/catalogo/articulos/${id}`, { method: "PATCH", body }),
  ajustarStock: (id, contado, motivo) =>
    request(`/catalogo/articulos/${id}/ajuste-stock`, { method: "POST", body: { contado, motivo } }),
  insumos: (q) => request(`/catalogo/insumos${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  crearInsumo: (body) => request("/catalogo/insumos", { method: "POST", body }),
  editarInsumo: (id, body) => request(`/catalogo/insumos/${id}`, { method: "PATCH", body }),
  preparaciones: () => request("/catalogo/preparaciones"),
  crearPreparacion: (body) => request("/catalogo/preparaciones", { method: "POST", body }),
  guardarPreparacion: (id, body) => request(`/catalogo/preparaciones/${id}`, { method: "PUT", body }),
  quitarPreparacion: (id) => request(`/catalogo/preparaciones/${id}`, { method: "DELETE" }),

  terceros: (filtros = {}) =>
    request(`/terceros?${new URLSearchParams(Object.entries(filtros).filter(([, v]) => v))}`),
  tercero: (id) => request(`/terceros/${id}`),
  responsabilidades: () => request("/terceros/responsabilidades"),
  crearTercero: (body) => request("/terceros", { method: "POST", body }),
  editarTercero: (id, body) => request(`/terceros/${id}`, { method: "PATCH", body }),

  turnoCaja: () => request("/caja/turno"),
  denominaciones: () => request("/caja/denominaciones"),
  // bases: {caja_id: monto} con todas las cajas activas
  abrirTurno: (bases, notas) => request("/caja/turnos", { method: "POST", body: { bases, notas } }),
  movimientoCaja: (turnoId, body) => request(`/caja/turnos/${turnoId}/movimientos`, { method: "POST", body }),
  // contados: {caja_id: monto} (cajas sin billetes); conteo: {denominacion_id: cantidad}
  cerrarTurno: (id, body) => request(`/caja/turnos/${id}/cerrar`, { method: "POST", body }),
  historialCaja: (filtros = {}) =>
    request(`/caja/turnos?${new URLSearchParams(Object.entries(filtros).filter(([, v]) => v))}`),
  detalleTurno: (id) => request(`/caja/turnos/${id}`),

  // cobro: {sesion_id, descuento, pagos: [{metodo_pago_id, monto}], fiado, cliente_id, notas}
  vender: (lineas, cobro) => request("/ventas", { method: "POST", body: { lineas, ...cobro } }),
  cupoCliente: (id) => request(`/clientes/${id}/cupo`),
  cuentas: () => request("/cuentas"),
  cuenta: (id) => request(`/cuentas/${id}`),
  abrirCuenta: (body) => request("/cuentas", { method: "POST", body }),
  editarCuenta: (id, body) => request(`/cuentas/${id}`, { method: "PATCH", body }),
  agregarACuenta: (id, articuloId, cantidad = 1) =>
    request(`/cuentas/${id}/items`, { method: "POST", body: { articulo_id: articuloId, cantidad } }),
  cantidadEnCuenta: (id, itemId, cantidad) =>
    request(`/cuentas/${id}/items/${itemId}`, { method: "PATCH", body: { cantidad } }),
  quitarDeCuenta: (id, itemId) => request(`/cuentas/${id}/items/${itemId}`, { method: "DELETE" }),
  cobrarCuenta: (id, cobro) => request(`/cuentas/${id}/cobrar`, { method: "POST", body: cobro }),
  cancelarCuenta: (id, motivo) => request(`/cuentas/${id}/cancelar`, { method: "POST", body: { motivo } }),

  creditos: (q) => request(`/creditos${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  credito: (clienteId) => request(`/creditos/${clienteId}`),
  // body: {sesion_id, metodo_pago_id, monto, aplicaciones?: [{cargo_id, monto}], notas}
  abonar: (clienteId, body) => request(`/creditos/${clienteId}/abonos`, { method: "POST", body }),
  cargoManual: (clienteId, body) => request(`/creditos/${clienteId}/cargos`, { method: "POST", body }),
  condonar: (cargoId, monto, motivo) =>
    request(`/creditos/cargos/${cargoId}/condonar`, { method: "POST", body: { monto, motivo } }),

  itemsCompra: (q) => request(`/compras/items${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  // filtros: {proveedor_id, pendientes, desde, hasta}
  compras: (filtros = {}) =>
    request(`/compras?${new URLSearchParams(Object.entries(filtros).filter(([, v]) => v))}`),
  compra: (id) => request(`/compras/${id}`),
  porPagar: () => request("/compras/por-pagar"),
  registrarCompra: (body) => request("/compras", { method: "POST", body }),
  borrarCompra: (id) => request(`/compras/${id}`, { method: "DELETE" }),
  // filtros: {desde, hasta, tipo: "gasto" | "compra", categoria_gasto_id}
  egresos: (filtros = {}) =>
    request(`/egresos?${new URLSearchParams(Object.entries(filtros).filter(([, v]) => v))}`),
  egreso: (id) => request(`/egresos/${id}`),
  // body: {sesion_id, concepto, compra_id | categoria_gasto_id, tercero_id, pagos, cruce, notas}
  registrarEgreso: (body) => request("/egresos", { method: "POST", body }),
  anularEgreso: (id, sesionId, motivo) =>
    request(`/egresos/${id}/anular`, { method: "POST", body: { sesion_id: sesionId, motivo } }),

  auditoria: (filtros) => {
    const params = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v));
    return request(`/auditoria?${params}`);
  },
};

export { ApiError };
