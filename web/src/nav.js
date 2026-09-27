// Grupos de navegación del Sidebar/TabBar, iconos y rutas tomados de los
// mockups (Sidebar.dc.html / TabBar.dc.html). Solo Cuentas y Nueva venta
// están implementados en este piloto; el resto queda visible pero
// deshabilitado, para mantener la fidelidad visual del diseño completo.

export const SIDEBAR_GROUPS = [
  {
    name: "Operación",
    items: [
      { label: "Inicio", path: null, d: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" },
      { label: "Nueva venta", path: "/venta", d: "M3 4h2l2.4 11h11l2-8H6.2M9 20h.01M17 20h.01" },
      { label: "Consulta precios", path: null, d: "M3 12V4h8l10 10-8 8zM7.5 7.5h.01" },
      { label: "Cuentas", path: "/cuentas", d: "M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6" },
      { label: "Caja", path: null, d: "M3 7h18v12H3zM3 7l3-4h12l3 4M16 13h2" },
    ],
  },
  {
    name: "Clientes",
    items: [
      { label: "Clientes", path: null, d: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21c0-4 3-6 7-6s7 2 7 6M17 3a4 4 0 0 1 0 8M22 21c0-3-1.5-5-4-5.6" },
      { label: "Créditos", path: null, d: "M2 6h20v12H2zM2 10h20M6 15h4" },
    ],
  },
  {
    name: "Inventario",
    items: [
      { label: "Inventario", path: null, d: "M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10" },
      { label: "Preparaciones", path: null, d: "M4 10h16v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4zM2 10h20M9 6c0-1 1-1 1-2M14 6c0-1 1-1 1-2" },
      { label: "Proveedores", path: null, d: "M2 6h12v10H2zM14 10h4l3 3v3h-7M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" },
    ],
  },
  {
    name: "Negocio",
    items: [
      { label: "Gastos", path: null, d: "M12 3v14M6 11l6 6 6-6M4 21h16" },
      { label: "Torneos", path: null, d: "M7 4h10v5a5 5 0 0 1-10 0zM7 6H4a3 3 0 0 0 3 4M17 6h3a3 3 0 0 1-3 4M12 14v4M8 21h8" },
      { label: "Documentos", path: null, d: "M6 3h8l4 4v14H6zM14 3v4h4M9 13h6M9 17h6" },
      { label: "Doc. fiscales", path: null, d: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4" },
      { label: "Reportes", path: null, d: "M4 20V10M10 20V4M16 20v-7M22 20H2" },
      { label: "Libros", path: null, d: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 21a2 2 0 0 1 2-2h13" },
    ],
  },
  {
    name: "Administración",
    items: [
      { label: "Usuarios", path: null, d: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.5-6 8-6s8 2 8 6" },
      { label: "Auditoría", path: null, d: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5" },
    ],
  },
];

export const TABBAR_ITEMS = [
  { label: "Inicio", path: null, d: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" },
  { label: "Vender", path: "/venta", d: "M3 4h2l2.4 11h11l2-8H6.2M9 20h.01M17 20h.01" },
  { label: "Cuentas", path: "/cuentas", d: "M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6" },
  { label: "Caja", path: null, d: "M3 7h18v12H3zM3 7l3-4h12l3 4M16 13h2" },
  { label: "Más", path: null, d: "M4 6h16M4 12h16M4 18h16" },
];
