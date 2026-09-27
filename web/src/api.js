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
    const detail = data?.detail || `Error ${res.status}`;
    throw new ApiError(detail, res.status);
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
};

export { ApiError };
