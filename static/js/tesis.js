import { obtenerProgramas, obtenerProgresoTesis, subirTesis } from "./api.js";
import { iconos } from "./iconos.js";

const TAMANO_MAXIMO = 25 * 1024 * 1024;
const ETAPAS = [
  "Subiendo archivo",
  "Leyendo PDF…",
  "Dividiendo en fragmentos…",
  "Generando embeddings",
  "Actualizando el mapa…",
  "Lista",
];

function crear(etiqueta, clase, texto) {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined) nodo.textContent = texto;
  return nodo;
}

function crearBoton(texto, clase) {
  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = clase;
  boton.textContent = texto;
  return boton;
}

function errorDeCampo(campo, mensaje) {
  const nodo = document.querySelector(`#${campo.getAttribute("aria-describedby")}`);
  campo.setAttribute("aria-invalid", "true");
  if (nodo) nodo.textContent = mensaje;
}

export function montarTesis({
  boton,
  indicador,
  botonMovil,
  indicadorMovil,
  obtenerUsuario,
  solicitarLogin,
  navegar,
  enviarPregunta,
  resaltarMaterial,
}) {
  const app = document.querySelector(".app-shell");
  const dialogo = crear("div", "tesis-modal");
  dialogo.id = "dialogo-subir-tesis";
  dialogo.setAttribute("role", "dialog");
  dialogo.setAttribute("aria-modal", "true");
  dialogo.setAttribute("aria-labelledby", "titulo-subir-tesis");
  dialogo.hidden = true;

  const panel = crear("section", "tesis-modal__panel");
  const encabezado = crear("header", "tesis-modal__encabezado");
  const titulo = crear("h2", "", "Subir tesis al repositorio");
  titulo.id = "titulo-subir-tesis";
  const cerrar = crearBoton("Cerrar", "btn btn--icono tesis-modal__cerrar");
  cerrar.setAttribute("aria-label", "Cerrar diálogo");
  cerrar.innerHTML = iconos.x;
  encabezado.append(titulo, cerrar);

  const descripcion = crear("p", "tesis-modal__descripcion", "El texto del PDF se indexa para que el agente pueda buscarla y responder sobre ella.");
  const errorGeneral = crear("p", "tesis-modal__error");
  errorGeneral.setAttribute("role", "alert");
  errorGeneral.hidden = true;

  const formulario = document.createElement("form");
  formulario.className = "tesis-formulario";
  formulario.noValidate = true;

  const zonaArchivo = crear("label", "tesis-archivo", "Arrastra aquí el PDF o haz clic para elegirlo");
  zonaArchivo.htmlFor = "tesis-pdf";
  const iconoArchivo = crear("span", "tesis-archivo__icono");
  iconoArchivo.innerHTML = iconos.fuente;
  iconoArchivo.setAttribute("aria-hidden", "true");
  const etiquetaArchivo = crear("span", "tesis-archivo__etiqueta", "Archivo PDF (máximo 25 MB)");
  const detalleArchivo = crear("span", "tesis-archivo__detalle", "Ningún archivo seleccionado");
  const archivo = document.createElement("input");
  archivo.id = "tesis-pdf";
  archivo.name = "pdf";
  archivo.type = "file";
  archivo.accept = "application/pdf,.pdf";
  archivo.required = true;
  archivo.setAttribute("aria-describedby", "error-tesis-pdf");
  const errorArchivo = crear("small", "campo-error");
  errorArchivo.id = "error-tesis-pdf";
  zonaArchivo.append(iconoArchivo, etiquetaArchivo, detalleArchivo, archivo);
  formulario.append(zonaArchivo, errorArchivo);

  function agregarCampo(etiquetaTexto, id, tipo, nombre, minimo, maximo) {
    const grupo = crear("label", "campo", etiquetaTexto);
    const campo = document.createElement("input");
    campo.id = id;
    campo.name = nombre;
    campo.type = tipo;
    campo.required = true;
    campo.setAttribute("aria-describedby", `error-${id}`);
    if (minimo !== undefined) campo.min = String(minimo);
    if (maximo !== undefined) campo.max = String(maximo);
    const error = crear("small", "campo-error");
    error.id = `error-${id}`;
    grupo.append(campo, error);
    formulario.append(grupo);
    return campo;
  }

  const campoTitulo = agregarCampo("Título", "tesis-titulo", "text", "titulo");
  const campoAutor = agregarCampo("Autor(es)", "tesis-autor", "text", "autor");
  const campoAnio = agregarCampo("Año", "tesis-anio", "number", "anio", 1990, new Date().getFullYear());
  const grupoPrograma = crear("label", "campo", "Programa");
  const programa = document.createElement("select");
  programa.id = "tesis-programa";
  programa.name = "programa";
  programa.required = true;
  programa.setAttribute("aria-describedby", "error-tesis-programa");
  const opcionInicial = document.createElement("option");
  opcionInicial.value = "";
  opcionInicial.textContent = "Selecciona un programa";
  programa.append(opcionInicial);
  const campoOtro = document.createElement("input");
  campoOtro.id = "tesis-programa-otro";
  campoOtro.type = "text";
  campoOtro.placeholder = "Escribe el nombre del programa";
  campoOtro.setAttribute("aria-label", "Nombre de otro programa");
  campoOtro.setAttribute("aria-describedby", "error-tesis-programa");
  campoOtro.hidden = true;
  const errorPrograma = crear("small", "campo-error");
  errorPrograma.id = "error-tesis-programa";
  grupoPrograma.append(programa, campoOtro, errorPrograma);
  formulario.append(grupoPrograma);

  const accionesFormulario = crear("div", "tesis-formulario__acciones");
  const enviar = crearBoton("Subir y procesar", "btn btn--acento");
  enviar.type = "submit";
  const cancelar = crearBoton("Cancelar", "btn btn--fantasma");
  accionesFormulario.append(enviar, cancelar);
  formulario.append(accionesFormulario);

  const vistaProgreso = crear("section", "tesis-progreso");
  vistaProgreso.setAttribute("aria-label", "Progreso del procesamiento");
  const textoProgreso = crear("p", "tesis-progreso__mensaje", "Preparando la carga…");
  textoProgreso.setAttribute("role", "status");
  textoProgreso.setAttribute("aria-live", "polite");
  const listaPasos = crear("ol", "tesis-pasos");
  listaPasos.setAttribute("aria-label", "Pasos del procesamiento");
  const pasos = ETAPAS.map((etapa, indice) => {
    const item = crear("li", "tesis-pasos__item");
    const estado = crear("span", "tesis-pasos__estado");
    estado.setAttribute("role", "img");
    const etiqueta = crear("span", "tesis-pasos__etiqueta", etapa);
    item.append(estado, etiqueta);
    listaPasos.append(item);
    return { item, estado, etiqueta, indice };
  });
  const barraProgreso = crear("div", "tesis-progreso__barra");
  barraProgreso.setAttribute("role", "progressbar");
  barraProgreso.setAttribute("aria-label", "Progreso total de la carga");
  barraProgreso.setAttribute("aria-valuemin", "0");
  barraProgreso.setAttribute("aria-valuemax", "100");
  const rellenoProgreso = crear("span", "tesis-progreso__relleno");
  barraProgreso.append(rellenoProgreso);
  const porcentajeProgreso = crear("p", "tesis-progreso__porcentaje", "0 %");
  vistaProgreso.append(textoProgreso, listaPasos, barraProgreso, porcentajeProgreso);

  const vistaFinal = crear("section", "tesis-final");
  const mensajeFinal = crear("p", "tesis-final__mensaje");
  mensajeFinal.setAttribute("role", "status");
  mensajeFinal.setAttribute("aria-live", "polite");
  const accionesFinales = crear("div", "tesis-formulario__acciones");
  vistaFinal.append(mensajeFinal, accionesFinales);

  panel.append(encabezado, descripcion, errorGeneral, formulario, vistaProgreso, vistaFinal);
  dialogo.append(panel);
  document.body.append(dialogo);

  let autenticado = false;
  let modalAbierto = false;
  let vistaActual = "formulario";
  let archivoSeleccionado = null;
  let cargaId = null;
  let materialId = null;
  let porcentajeActual = 0;
  let temporizadorSondeo = 0;
  let programasCargados = false;
  let cargandoProgramas = false;
  let envioPendiente = false;
  let textoEstadoServidor = "";
  let elementoFocoPrevio = null;
  let inertPrevio = false;
  let desbordamientoPrevio = "";

  function limpiarErroresCampo() {
    [archivo, campoTitulo, campoAutor, campoAnio, programa, campoOtro].forEach((campo) => {
      campo.removeAttribute("aria-invalid");
      const error = document.querySelector(`#${campo.getAttribute("aria-describedby")}`);
      if (error) error.textContent = "";
    });
    errorArchivo.textContent = "";
  }

  function mostrarErrorGeneral(mensaje) {
    errorGeneral.textContent = mensaje || "";
    errorGeneral.hidden = !mensaje;
  }

  function actualizarControles() {
    const puedeSubir = autenticado;
    [boton, botonMovil].forEach((nodo) => { nodo.hidden = !puedeSubir; });
    const mostrarIndicador = Boolean(cargaId && vistaActual === "progreso" && !modalAbierto && autenticado);
    [indicador, indicadorMovil].forEach((nodo) => {
      nodo.hidden = !mostrarIndicador;
      nodo.querySelector("span:last-child").textContent = `Procesando tesis… ${porcentajeActual} %`;
      nodo.setAttribute("aria-label", `Procesando tesis, ${porcentajeActual} por ciento. Abrir progreso.`);
      nodo.title = `Procesando tesis… ${porcentajeActual} %`;
    });
  }

  function detenerSondeo() {
    if (temporizadorSondeo) window.clearTimeout(temporizadorSondeo);
    temporizadorSondeo = 0;
  }

  function mostrarVista(nombre) {
    vistaActual = nombre;
    formulario.hidden = nombre !== "formulario";
    vistaProgreso.hidden = nombre !== "progreso";
    vistaFinal.hidden = nombre !== "final";
    actualizarControles();
  }

  function cerrarDialogo(restaurarFoco = true) {
    if (!modalAbierto) return;
    detenerSondeo();
    modalAbierto = false;
    dialogo.hidden = true;
    app.inert = inertPrevio;
    document.body.style.overflow = desbordamientoPrevio;
    actualizarControles();
    if (restaurarFoco && elementoFocoPrevio?.isConnected && !elementoFocoPrevio.hidden) {
      elementoFocoPrevio.focus({ preventScroll: true });
    }
  }

  function mostrarDialogo(origen) {
    if (!autenticado || !obtenerUsuario?.()) {
      solicitarLogin?.();
      return;
    }
    elementoFocoPrevio = origen || boton;
    if (cargaId && vistaActual === "progreso") mostrarVista("progreso");
    else if (vistaActual !== "formulario") mostrarVista("formulario");
    modalAbierto = true;
    inertPrevio = app.inert;
    desbordamientoPrevio = document.body.style.overflow;
    app.inert = true;
    document.body.style.overflow = "hidden";
    dialogo.hidden = false;
    window.requestAnimationFrame(() => cerrar.focus({ preventScroll: true }));
    if (cargaId && vistaActual === "progreso") sondearProgreso();
    void cargarProgramas();
    actualizarControles();
  }

  function abrirDesde(evento) {
    mostrarDialogo(evento.currentTarget);
  }

  async function cargarProgramas() {
    if (programasCargados || cargandoProgramas) return;
    cargandoProgramas = true;
    mostrarErrorGeneral("");
    try {
      // El backend responde {programas: [...]}; se acepta también una lista directa
      const respuestaProgramas = await obtenerProgramas();
      const datos = Array.isArray(respuestaProgramas) ? respuestaProgramas : respuestaProgramas?.programas;
      if (!Array.isArray(datos)) throw new Error("No pudimos cargar la lista de programas. Inténtalo de nuevo.");
      const seleccion = programa.value;
      programa.replaceChildren(opcionInicial.cloneNode(true));
      datos.forEach((nombre) => {
        const opcion = document.createElement("option");
        opcion.value = String(nombre);
        opcion.textContent = String(nombre);
        programa.append(opcion);
      });
      const otro = document.createElement("option");
      otro.value = "__otro__";
      otro.textContent = "Otro…";
      programa.append(otro);
      programa.value = seleccion;
      programasCargados = true;
    } catch (error) {
      mostrarErrorGeneral(error.message || "No pudimos cargar la lista de programas. Inténtalo de nuevo.");
    } finally {
      cargandoProgramas = false;
    }
  }

  function validarArchivo(archivoNuevo) {
    if (!archivoNuevo) return "Selecciona un archivo PDF.";
    if (!archivoNuevo.name.toLocaleLowerCase("es").endsWith(".pdf")) return "El archivo debe tener formato PDF.";
    if (archivoNuevo.type && archivoNuevo.type !== "application/pdf") return "El archivo seleccionado no es un PDF válido.";
    if (archivoNuevo.size > TAMANO_MAXIMO) return "El PDF debe pesar 25 MB o menos.";
    return "";
  }

  function establecerArchivo(archivoNuevo) {
    const error = validarArchivo(archivoNuevo);
    textoEstadoServidor = "";
    mostrarErrorGeneral("");
    archivoSeleccionado = error ? null : archivoNuevo;
    detalleArchivo.textContent = archivoSeleccionado
      ? `${archivoSeleccionado.name} · ${(archivoSeleccionado.size / (1024 * 1024)).toFixed(2)} MB`
      : "Ningún archivo seleccionado";
    zonaArchivo.classList.toggle("tesis-archivo--seleccionado", Boolean(archivoSeleccionado));
    if (error) errorDeCampo(archivo, error);
    else {
      archivo.removeAttribute("aria-invalid");
      errorArchivo.textContent = "";
    }
  }

  function validarFormulario() {
    limpiarErroresCampo();
    mostrarErrorGeneral(textoEstadoServidor);
    let valido = true;
    if (!archivoSeleccionado || validarArchivo(archivoSeleccionado)) {
      errorDeCampo(archivo, validarArchivo(archivoSeleccionado));
      valido = false;
    }
    if (!campoTitulo.value.trim()) {
      errorDeCampo(campoTitulo, "Escribe el título de la tesis.");
      valido = false;
    }
    if (!campoAutor.value.trim()) {
      errorDeCampo(campoAutor, "Escribe al menos un autor.");
      valido = false;
    }
    const anio = Number(campoAnio.value);
    if (!campoAnio.value || !Number.isInteger(anio) || anio < 1990 || anio > new Date().getFullYear()) {
      errorDeCampo(campoAnio, `Ingresa un año entre 1990 y ${new Date().getFullYear()}.`);
      valido = false;
    }
    const programaFinal = programa.value === "__otro__" ? campoOtro.value.trim() : programa.value;
    if (!programaFinal) {
      errorDeCampo(programa.value === "__otro__" ? campoOtro : programa, "Selecciona o escribe el programa.");
      valido = false;
    }
    return { valido, programaFinal };
  }

  function renderizarProgreso(datos = {}) {
    const etapa = String(datos.etapa || "recibida");
    const indiceActual = {
      recibida: 1,
      leyendo: 1,
      fragmentando: 2,
      embeddings: 3,
      mapa: 4,
      lista: 5,
    }[etapa] ?? 0;
    const porcentaje = Number(datos.porcentaje);
    porcentajeActual = Number.isFinite(porcentaje) ? Math.max(0, Math.min(100, Math.round(porcentaje))) : porcentajeActual;
    pasos.forEach(({ item, estado, etiqueta, indice }) => {
      const hecho = etapa === "lista" || indice < indiceActual || (etapa === "recibida" && indice === 0);
      const enCurso = etapa !== "lista" && indice === indiceActual;
      item.classList.toggle("tesis-pasos__item--hecho", hecho);
      item.classList.toggle("tesis-pasos__item--activo", enCurso);
      if (enCurso) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
      estado.replaceChildren();
      if (hecho) {
        estado.textContent = "✓";
        estado.setAttribute("aria-label", "Hecho");
      } else if (enCurso) {
        const spinner = crear("span", "tesis-spinner");
        spinner.setAttribute("aria-hidden", "true");
        estado.append(spinner);
        estado.setAttribute("aria-label", "En curso");
      } else {
        estado.textContent = "·";
        estado.setAttribute("aria-label", "Pendiente");
      }
      if (etapa === "embeddings" && indice === 3) {
        const avance = Number(datos.avance);
        const total = Number(datos.total);
        etiqueta.textContent = Number.isFinite(avance) && Number.isFinite(total)
          ? `${ETAPAS[indice]} (${avance}/${total})`
          : ETAPAS[indice];
      } else {
        etiqueta.textContent = ETAPAS[indice];
      }
    });
    barraProgreso.setAttribute("aria-valuenow", String(porcentajeActual));
    rellenoProgreso.style.width = `${porcentajeActual}%`;
    porcentajeProgreso.textContent = `${porcentajeActual} %`;
    textoProgreso.textContent = datos.mensaje || "Tu tesis se está procesando.";
    actualizarControles();
  }

  function mostrarFinalCorrecto(datos) {
    detenerSondeo();
    cargaId = null;
    materialId = datos.material_id ?? materialId;
    const tituloTesis = datos.titulo || campoTitulo.value.trim() || "tu tesis";
    mensajeFinal.textContent = `¡Lista! «${tituloTesis}» ya está en el catálogo, en el mapa y disponible para el chat.`;
    accionesFinales.replaceChildren();
    const preguntar = crearBoton("Preguntar sobre esta tesis", "btn btn--acento");
    const mapa = crearBoton("Ver en el mapa", "btn btn--fantasma");
    const pdf = crearBoton("Ver PDF", "btn btn--fantasma");
    preguntar.addEventListener("click", async () => {
      cerrarDialogo(false);
      await navegar?.("chat");
      enviarPregunta?.(`¿De qué trata la tesis «${tituloTesis}»?`);
    });
    mapa.addEventListener("click", async () => {
      cerrarDialogo(false);
      await navegar?.("mapa");
      resaltarMaterial?.(materialId);
    });
    pdf.addEventListener("click", () => {
      if (materialId != null) {
        window.open(`/api/tesis/${encodeURIComponent(materialId)}/pdf`, "_blank", "noopener,noreferrer");
      }
    });
    accionesFinales.append(preguntar, mapa, pdf);
    textoEstadoServidor = "";
    mostrarVista("final");
  }

  function mostrarErrorProcesamiento(mensaje) {
    detenerSondeo();
    cargaId = null;
    mensajeFinal.textContent = mensaje || "No fue posible procesar el PDF. Inténtalo con otro archivo.";
    accionesFinales.replaceChildren();
    const reintentar = crearBoton("Intentar con otro archivo", "btn btn--acento");
    reintentar.addEventListener("click", reiniciarFormulario);
    accionesFinales.append(reintentar);
    mostrarVista("final");
  }

  function programarSondeo() {
    detenerSondeo();
    if (modalAbierto && cargaId) temporizadorSondeo = window.setTimeout(sondearProgreso, 1500);
  }

  async function sondearProgreso() {
    if (!modalAbierto || !cargaId) return;
    temporizadorSondeo = 0;
    try {
      const datos = await obtenerProgresoTesis(cargaId);
      if (!modalAbierto || !cargaId) return;
      renderizarProgreso(datos);
      if (datos.etapa === "lista") {
        mostrarFinalCorrecto(datos);
        return;
      }
      if (datos.etapa === "error") {
        mostrarErrorProcesamiento(datos.error || datos.mensaje);
        return;
      }
    } catch {
      if (!modalAbierto || !cargaId) return;
      textoProgreso.textContent = "No se pudo consultar el progreso. Reintentando…";
    }
    programarSondeo();
  }

  function reiniciarFormulario() {
    detenerSondeo();
    cargaId = null;
    materialId = null;
    porcentajeActual = 0;
    textoEstadoServidor = "";
    formulario.reset();
    archivo.value = "";
    archivoSeleccionado = null;
    detalleArchivo.textContent = "Ningún archivo seleccionado";
    zonaArchivo.classList.remove("tesis-archivo--seleccionado");
    campoOtro.hidden = true;
    limpiarErroresCampo();
    mostrarErrorGeneral("");
    mostrarVista("formulario");
    actualizarControles();
    archivo.focus({ preventScroll: true });
  }

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (envioPendiente) return;
    const { valido, programaFinal } = validarFormulario();
    if (!valido) {
      formulario.querySelector('[aria-invalid="true"]')?.focus({ preventScroll: true });
      return;
    }
    const datos = new FormData();
    datos.append("pdf", archivoSeleccionado);
    datos.append("titulo", campoTitulo.value.trim());
    datos.append("autor", campoAutor.value.trim());
    datos.append("anio", campoAnio.value);
    datos.append("programa", programaFinal);
    envioPendiente = true;
    enviar.disabled = true;
    enviar.textContent = "Subiendo archivo…";
    textoEstadoServidor = "";
    mostrarErrorGeneral("");
    try {
      const respuesta = await subirTesis(datos);
      if (!respuesta?.carga_id || respuesta.material_id == null) {
        throw new Error("La carga se recibió, pero no fue posible obtener su identificador de seguimiento.");
      }
      cargaId = respuesta.carga_id;
      materialId = respuesta.material_id;
      porcentajeActual = 0;
      mostrarVista("progreso");
      renderizarProgreso({ etapa: "recibida", mensaje: "Archivo recibido. Iniciando el procesamiento." });
      if (modalAbierto) sondearProgreso();
    } catch (error) {
      if (error.status === 401) {
        cerrarDialogo(false);
        solicitarLogin?.();
      } else {
        textoEstadoServidor = error.message || "No fue posible subir la tesis. Inténtalo de nuevo.";
        mostrarErrorGeneral(textoEstadoServidor);
      }
    } finally {
      envioPendiente = false;
      enviar.disabled = false;
      enviar.textContent = "Subir y procesar";
    }
  });

  programa.addEventListener("change", () => {
    const otro = programa.value === "__otro__";
    campoOtro.hidden = !otro;
    if (otro) campoOtro.focus({ preventScroll: true });
    programa.removeAttribute("aria-invalid");
    errorPrograma.textContent = "";
    textoEstadoServidor = "";
    mostrarErrorGeneral("");
  });
  [campoTitulo, campoAutor, campoAnio, campoOtro].forEach((campo) => {
    campo.addEventListener("input", () => {
      campo.removeAttribute("aria-invalid");
      const error = document.querySelector(`#${campo.getAttribute("aria-describedby")}`);
      if (error) error.textContent = "";
      textoEstadoServidor = "";
      mostrarErrorGeneral("");
    });
  });
  archivo.addEventListener("change", () => establecerArchivo(archivo.files?.[0] || null));
  ["dragenter", "dragover"].forEach((evento) => {
    zonaArchivo.addEventListener(evento, (e) => {
      e.preventDefault();
      zonaArchivo.classList.add("tesis-archivo--arrastrando");
    });
  });
  ["dragleave", "drop"].forEach((evento) => {
    zonaArchivo.addEventListener(evento, (e) => {
      e.preventDefault();
      zonaArchivo.classList.remove("tesis-archivo--arrastrando");
      if (evento === "drop") establecerArchivo(e.dataTransfer?.files?.[0] || null);
    });
  });
  [boton, botonMovil].forEach((nodo) => nodo.addEventListener("click", abrirDesde));
  [indicador, indicadorMovil].forEach((nodo) => nodo.addEventListener("click", abrirDesde));
  cerrar.addEventListener("click", () => cerrarDialogo());
  cancelar.addEventListener("click", () => cerrarDialogo());
  dialogo.addEventListener("click", (evento) => {
    if (evento.target === dialogo) cerrarDialogo();
  });
  window.addEventListener("keydown", (evento) => {
    if (!modalAbierto) return;
    if (evento.key === "Escape") {
      evento.preventDefault();
      cerrarDialogo();
      return;
    }
    if (evento.key !== "Tab") return;
    const enfocables = [...dialogo.querySelectorAll('button:not(:disabled), input:not(:disabled):not([type="hidden"]), select:not(:disabled), [tabindex]:not([tabindex="-1"])')]
      .filter((nodo) => !nodo.hidden && nodo.getClientRects().length);
    if (!enfocables.length) {
      evento.preventDefault();
      dialogo.focus();
      return;
    }
    const primero = enfocables[0];
    const ultimo = enfocables[enfocables.length - 1];
    if (evento.shiftKey && document.activeElement === primero) {
      evento.preventDefault();
      ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault();
      primero.focus();
    }
  });
  window.addEventListener("biblioteca-sesion-expirada", () => {
    if (modalAbierto) cerrarDialogo(false);
  });

  function actualizarSesion(usuario = obtenerUsuario?.()) {
    autenticado = Boolean(usuario);
    actualizarControles();
  }

  actualizarSesion();
  return { actualizarSesion };
}
