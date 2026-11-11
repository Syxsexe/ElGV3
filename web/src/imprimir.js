// Impresión de tirillas (impresora térmica de 80 mm) desde el navegador: el
// documento se arma en un iframe oculto y se abre el diálogo de impresión del
// sistema, sin tocar la página. Funciona con cualquier impresora instalada.

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
