// Envío de formularios sin doble clic: mientras el envío está en curso, un
// segundo submit (clic o Enter) se ignora y el formulario queda con
// aria-busy="true" (styles.css atenúa su botón de enviar).
//   <form onSubmit={unaVez(guardar)}>
const enCurso = new WeakSet();

export const unaVez = (fn) => async (e) => {
  const form = e.currentTarget;
  if (enCurso.has(form)) {
    e.preventDefault();
    return undefined;
  }
  enCurso.add(form);
  form.setAttribute("aria-busy", "true");
  try {
    return await fn(e);
  } finally {
    enCurso.delete(form);
    form.removeAttribute("aria-busy");
  }
};
