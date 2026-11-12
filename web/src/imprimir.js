// Impresión de tirillas (impresora térmica de 80 mm) desde el navegador: el
// documento se arma en un iframe oculto y se abre el diálogo de impresión del
// sistema, sin tocar la página. Funciona con cualquier impresora instalada.

import { api } from "./api";
import { fmt } from "./format";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const cant = (n) => Number(n).toLocaleString("es-CO", { maximumFractionDigits: 3 });

const ESTILO = `
  @page { size: 80mm auto; margin: 0; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 4mm 3mm 8mm; width: 80mm; color: #000;
         font: 13px/1.35 "DejaVu Sans Mono", "Courier New", monospace; }
  h1 { font-size: 22px; margin: 0; text-align: center; letter-spacing: .5px; }
  .centro { text-align: center; }
  .quien { font-size: 18px; font-weight: 700; text-align: center; margin: 4px 0 2px; }
  .linea { border-top: 1px dashed #000; margin: 6px 0; }
  .item { display: flex; gap: 6px; font-size: 16px; font-weight: 700; margin-top: 6px; }
  .item .n { min-width: 34px; }
  .sub { padding-left: 40px; font-size: 13px; }
  .coment { padding-left: 40px; font-size: 15px; font-weight: 700; }
  .nota { font-size: 15px; font-weight: 700; white-space: pre-wrap; }
  .marca { text-align: center; font-weight: 700; border: 1px solid #000; padding: 2px; margin-bottom: 4px; }
  .negocio { font-size: 17px; font-weight: 700; text-align: center; overflow-wrap: anywhere; }
  .fila { display: flex; justify-content: space-between; gap: 8px; }
  .fila > :first-child { overflow-wrap: anywhere; min-width: 0; }
  .fila > :last-child { white-space: nowrap; }
  .art { margin-top: 3px; overflow-wrap: anywhere; }
  .det { padding-left: 12px; }
  .total { font-size: 18px; font-weight: 700; margin: 2px 0; }
  .peq { font-size: 11px; }
  .pie { text-align: center; white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 4px; }
`;

function imprimirHtml(titulo, cuerpo) {
  const iframe = document.createElement("iframe");
  iframe.setAttribute("aria-hidden", "true");
  iframe.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden";
  iframe.srcdoc = `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${esc(titulo)}</title>
    <style>${ESTILO}</style></head><body>${cuerpo}</body></html>`;
  const quitar = () => setTimeout(() => iframe.remove(), 500);
  iframe.onload = () => {
    const w = iframe.contentWindow;
    w.addEventListener("afterprint", quitar);
    setTimeout(quitar, 120000); // por si el navegador no avisa al terminar
    w.focus();
    w.print();
  };
  document.body.appendChild(iframe);
}

// comanda: la respuesta de la API (numero, creada_en, usuario, mesa, nombre, notas, items).
export function imprimirComanda(comanda, { reimpresion = false } = {}) {
  const fecha = new Date(comanda.creada_en);
  const quien = [comanda.mesa && `Mesa ${comanda.mesa}`, comanda.nombre && comanda.nombre !== comanda.mesa && comanda.nombre]
    .filter(Boolean).join(" · ");
  const items = comanda.items.map((it) => `
    <div class="item"><span class="n">${esc(cant(it.cantidad))}×</span><span>${esc(it.nombre)}</span></div>
    ${it.componentes ? `<div class="sub">${esc(it.componentes)}</div>` : ""}
    ${it.comentario ? `<div class="coment">» ${esc(it.comentario)}</div>` : ""}`).join("");
  imprimirHtml(`Comanda ${comanda.numero}`, `
    ${reimpresion ? '<div class="marca">REIMPRESIÓN</div>' : ""}
    <h1>COMANDA #${esc(comanda.numero)}</h1>
    <div class="quien">${esc(quien)}</div>
    <div class="centro">Cuenta #${esc(comanda.cuenta_numero)} · ${esc(fecha.toLocaleDateString("es-CO"))}
      ${esc(fecha.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }))} · ${esc(comanda.usuario)}</div>
    <div class="linea"></div>
    ${items}
    <div class="linea"></div>
    ${comanda.notas ? `<div class="nota">Nota: ${esc(comanda.notas)}</div>` : ""}`);
}

// Siglas de los tipos de documento (código DIAN) para el ticket.
const SIGLA = { 11: "RC", 12: "TI", 13: "CC", 21: "TE", 22: "CE", 31: "NIT", 41: "Pasaporte", 42: "Doc. ext.",
  47: "PEP", 48: "PPT", 50: "NIT ext.", 91: "NUIP" };
const documento = (tipo, numero, dv) =>
  numero ? `${SIGLA[tipo] || "Doc."} ${numero}${dv != null ? `-${dv}` : ""}` : "";
const fila = (izq, der, clase = "") => `<div class="fila ${clase}"><span>${izq}</span><span>${der}</span></div>`;

// Ticket de venta para el cliente. venta: la respuesta de la API (detalle de
// la venta); empresa: los datos del negocio (o null si no se pudieron leer);
// cambio: solo se conoce al cobrar, no al reimprimir.
export function imprimirTicket(venta, empresa, { cambio = 0, reimpresion = false } = {}) {
  const fecha = new Date(venta.creada_en);
  const e = empresa || {};
  const lugar = [e.direccion, e.municipio].filter(Boolean).join(" · ");
  const donde = [venta.mesa && `Mesa ${venta.mesa}`, venta.cuenta_numero && `Cuenta #${venta.cuenta_numero}`]
    .filter(Boolean).join(" · ");
  const lineas = venta.lineas.map((l) => `
    <div class="art">${esc(l.nombre)}</div>
    ${fila(`<span class="det">${esc(cant(l.cantidad))} × ${esc(fmt(l.precio_unit))}</span>`, esc(fmt(l.subtotal)))}`).join("");
  const pagos = venta.pagos.map((p) => fila(esc(p.metodo), esc(fmt(p.monto)))).join("");
  // El valor se redondea como diferencia, para que base + impuesto sumen lo cobrado.
  const impuestos = (venta.impuestos || []).map((i) => ({
    ...i, base: Math.round(i.base), valor: Math.round(Number(i.base) + Number(i.valor)) - Math.round(i.base) }));
  imprimirHtml(`Venta ${venta.numero}`, `
    ${reimpresion ? '<div class="marca">REIMPRESIÓN</div>' : ""}
    ${e.nombre ? `<div class="negocio">${esc(e.nombre)}</div>` : ""}
    <div class="centro">
      ${e.numero_identificacion ? `<div>${esc(documento(e.tipo_identificacion, e.numero_identificacion, e.dv))}</div>` : ""}
      ${lugar ? `<div>${esc(lugar)}</div>` : ""}
      ${e.telefono ? `<div>Tel. ${esc(e.telefono)}</div>` : ""}
    </div>
    <div class="linea"></div>
    <div class="centro"><strong>VENTA #${esc(venta.numero)}</strong></div>
    <div class="centro">${esc(fecha.toLocaleDateString("es-CO"))}
      ${esc(fecha.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }))}</div>
    <div class="centro">Atendió: ${esc(venta.usuario)}</div>
    ${donde ? `<div class="centro">${esc(donde)}</div>` : ""}
    <div>Cliente: ${venta.cliente ? esc(venta.cliente) : "Consumidor final"}</div>
    ${venta.cliente_identificacion ? `<div>${esc(documento(venta.cliente_tipo_identificacion, venta.cliente_identificacion, venta.cliente_dv))}</div>` : ""}
    <div class="linea"></div>
    ${lineas}
    <div class="linea"></div>
    ${Number(venta.descuento) > 0 ? fila("Subtotal", esc(fmt(venta.subtotal))) + fila("Descuento", `− ${esc(fmt(venta.descuento))}`) : ""}
    ${fila("TOTAL", esc(fmt(venta.total)), "total")}
    ${pagos}
    ${Number(venta.fiado) > 0 ? fila("Crédito", esc(fmt(venta.fiado))) : ""}
    ${cambio > 0 ? fila("Recibido", esc(fmt(Number(venta.pagado) + cambio))) + fila("Cambio", esc(fmt(cambio))) : ""}
    ${impuestos.length ? `<div class="linea"></div><div class="peq">Impuestos incluidos</div>
      ${impuestos.map((i) => fila(`${esc(i.tributo)} ${esc(cant(i.tarifa))}% sobre ${esc(fmt(i.base))}`, esc(fmt(i.valor)), "peq")).join("")}` : ""}
    ${venta.notas ? `<div class="linea"></div><div>Notas: ${esc(venta.notas)}</div>` : ""}
    ${e.mensaje_ticket ? `<div class="linea"></div><div class="pie">${esc(e.mensaje_ticket)}</div>` : ""}`);
}

// Los datos del negocio casi no cambian: se guardan unos minutos para no
// esperar al servidor en cada ticket. Configuración los olvida al guardar.
const VIGENCIA_EMPRESA_MS = 5 * 60 * 1000;
let empresaGuardada = null; // {datos, hasta}

export function olvidarEmpresa() {
  empresaGuardada = null;
}

async function datosEmpresa() {
  if (empresaGuardada && empresaGuardada.hasta > Date.now()) return empresaGuardada.datos;
  try {
    const datos = await api.empresa();
    empresaGuardada = { datos, hasta: Date.now() + VIGENCIA_EMPRESA_MS };
    return datos;
  } catch {
    return null; // sin encabezado: la venta ya está hecha y no debe quedarse sin comprobante
  }
}

// Lee los datos del negocio e imprime. Si algo falla, la promesa lo rechaza
// con un mensaje para mostrarlo en pantalla.
export async function imprimirTicketVenta(venta, opciones) {
  const empresa = await datosEmpresa();
  try {
    imprimirTicket(venta, empresa, opciones);
  } catch (err) {
    console.error(err);
    throw new Error("No se pudo imprimir el ticket.");
  }
}
