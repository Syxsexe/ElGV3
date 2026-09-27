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

  if (res.status === 401) {
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

  cuentasAbiertas: () => request("/cuentas"),
  siguienteMesa: () => request("/cuentas/siguiente-mesa"),
  abrirCuenta: (cliente, mesa) =>
    request("/cuentas", { method: "POST", body: { cliente, mesa } }),
  obtenerCuenta: (id) => request(`/cuentas/${id}`),
  agregarItemCuenta: (cuentaId, item) =>
    request(`/cuentas/${cuentaId}/items`, { method: "POST", body: item }),
  cambiarCantidadItem: (itemId, cantidad) =>
    request(`/cuentas/items/${itemId}`, { method: "PATCH", body: { cantidad } }),
  quitarItem: (itemId) => request(`/cuentas/items/${itemId}`, { method: "DELETE" }),
  cobrarCuenta: (cuentaId, body) =>
    request(`/cuentas/${cuentaId}/cobrar`, { method: "POST", body }),
  cancelarCuenta: (cuentaId) =>
    request(`/cuentas/${cuentaId}/cancelar`, { method: "POST" }),

  buscarProductos: (q, tipo) =>
    request(`/productos/buscar?q=${encodeURIComponent(q)}${tipo ? `&tipo=${tipo}` : ""}`),
  combos: () => request("/productos/combos"),

  registrarVenta: (body) => request("/ventas", { method: "POST", body }),

  cajaSesionActiva: () => request("/caja/sesion-activa"),
  abrirCaja: (body) => request("/caja/abrir", { method: "POST", body }),
  previewCierre: () => request("/caja/preview-cierre"),
  cerrarCaja: (body) => request("/caja/cerrar", { method: "POST", body }),
  historialCaja: (desde, hasta) =>
    request(`/caja/historial?${desde ? `desde=${desde}&` : ""}${hasta ? `hasta=${hasta}` : ""}`),
  resumenHistorialCaja: (desde, hasta) =>
    request(`/caja/historial/resumen?${desde ? `desde=${desde}&` : ""}${hasta ? `hasta=${hasta}` : ""}`),
  detalleSesionCaja: (id) => request(`/caja/historial/${id}`),
};

export { ApiError };
