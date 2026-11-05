import { enviarChat, obtenerMaterial, sintetizar, consultarSesion, obtenerConversacionActual, borrarConversacion } from "./api.js";
import { renderMarkdown } from "./markdown.js";
import { renderBibliografia } from "./bibliografia.js";
import { libroAbierto, microfono, enviar, play, reservar, resumen, alerta, iconos } from "./iconos.js";
import { montarVoz, reproducirRespuesta } from "./voz.js";
import { montarLlamada } from "./llamada.js";

const sugerencias = [
  ["catalogo", "Libros sobre seguridad en redes"],
  ["bitacora", "¿Cuántos días dura un préstamo?"],
  ["fuente", "¿Cómo cito un libro en APA?"],
  ["usuario", "¿Tengo multas?"],
  ["reservar", "Quiero renovar mi préstamo"],
  ["resumen", "¿De qué trata la tesis sobre cacao en el Putumayo?"],
];

const horaActual = () => new Intl.DateTimeFormat("es-CO", {
  hour: "2-digit",
  minute: "2-digit",
}).format(new Date());

function elemento(etiqueta, clase, texto) {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined) nodo.textContent = texto;
  return nodo;
}

function boton(texto, icono, clase = "btn btn--fantasma", ariaLabel = "") {
  const nodo = document.createElement("button");
  nodo.type = "button";
  nodo.className = clase;
  nodo.innerHTML = `${icono ? `<span aria-hidden="true">${icono}</span>` : ""}<span>${texto}</span>`;
  if (ariaLabel) nodo.setAttribute("aria-label", ariaLabel);
  return nodo;
}

const tipoVisible = (tipo) => ({
  libro: "Libro",
  tesis: "Tesis",
  articulo: "Artículo",
  recurso_digital: "Recurso digital",
}[tipo] || tipo || "Material");

const claveTipo = (tipo) => ["libro", "tesis", "articulo", "recurso_digital"].includes(tipo)
  ? tipo
  : "libro";

function nombreFuente(documento = "") {
  const normal = documento.toLocaleLowerCase("es");
  if (normal.includes("reglamento")) return "Reglamento";
  if (normal.includes("apa")) return "Guía APA";
  if (normal.includes("ieee")) return "Guía IEEE";
  if (normal.includes("frecuente") || normal.includes("pregunta")) return "Preguntas frecuentes";
  if (normal.includes("base de datos") || normal.includes("base_datos")) return "Guía de bases de datos";
  return documento || "Documento";
}

export function montarChat(contenedor, opciones = {}) {
  let conversacionId = null;
  try {
    conversacionId = sessionStorage.getItem("biblioteca-conversacion-id");
  } catch {
    conversacionId = null;
  }
  const mensajes = [];
  const resumentes = new Map();
  let ocupado = false;
  let generacion = 0;
  let usuarioActual = null;
  let leyendoVoz = false;
  let autoscroll = true;
  let ultimoTextoUsuario = "";
  let ultimoTextoRequiereLogin = "";
  let esperaVoz = null;
  let modoEntrada = "normal";
  let esperandoCodigo = false;
  let ultimaReproduccion = null;

  const cabecera = elemento("header", "chat-encabezado");
  const titulo = elemento("h1", "", "Conversar");
  titulo.id = "titulo-chat";
  titulo.tabIndex = -1;
  const accionesCabecera = elemento("div", "chat-acciones-cabecera");
  const chipUsuario = elemento("span", "usuario-chip", "Invitado");
  chipUsuario.setAttribute("aria-live", "polite");
  const botonSesion = boton("Iniciar sesión", "", "btn btn--fantasma");
  botonSesion.addEventListener("click", () => opciones.solicitarLogin?.(ultimoTextoRequiereLogin));
  const abrirCuenta = boton("Mi cuenta", "", "btn btn--fantasma");
  abrirCuenta.addEventListener("click", () => opciones.abrirCuenta?.());
  accionesCabecera.append(chipUsuario, botonSesion, abrirCuenta);
  cabecera.append(titulo, accionesCabecera);
  const botonBorrarChat = document.querySelector("#borrar-chat");

  const aviso = elemento("div", "aviso servicio-aviso");
  aviso.hidden = true;
  aviso.setAttribute("role", "status");
  const mensajesNodo = elemento("div", "chat-mensajes");
  mensajesNodo.setAttribute("aria-live", "polite");
  mensajesNodo.setAttribute("aria-relevant", "additions text");
  const composer = elemento("div", "barra-escritura");
  const form = elemento("form", "form-escritura");
  let input;
  const iconoPin = elemento("span", "entrada-pin-icono");
  iconoPin.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>';
  iconoPin.hidden = true;
  const mic = boton("", microfono, "btn btn--icono", "Grabar pregunta por voz");
  mic.dataset.accionMicrofono = "";
  const submit = boton("", enviar, "btn btn--icono btn--primario", "Enviar mensaje");
  submit.type = "submit";
  function enlazarEntrada(nodo) {
    nodo.addEventListener("input", ajustarEntrada);
    nodo.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" && (modoEntrada === "pin" || !evento.shiftKey)) {
        evento.preventDefault();
        form.requestSubmit();
      }
    });
  }

  function establecerModoEntrada(modo, codigoPendiente = false) {
    modoEntrada = modo;
    esperandoCodigo = codigoPendiente;
    if (modo === "pin") {
      const campo = document.createElement("input");
      campo.type = "password";
      campo.inputMode = "numeric";
      campo.maxLength = 4;
      campo.autocomplete = "off";
      campo.placeholder = "Escribe tu PIN de 4 dígitos (o dilo con el micrófono)";
      campo.setAttribute("aria-label", "Escribe tu PIN de 4 dígitos");
      campo.id = "entrada-chat";
      input.replaceWith(campo);
      input = campo;
      iconoPin.hidden = false;
    } else {
      const campo = document.createElement("textarea");
      campo.id = "entrada-chat";
      campo.rows = 1;
      campo.maxLength = 2000;
      campo.placeholder = esperandoCodigo
        ? "Escribe o di tu código (ej.: 101)"
        : "Escribe tu pregunta…";
      campo.setAttribute("aria-label", esperandoCodigo ? "Escribe o di tu código de usuario" : "Escribe tu mensaje");
      campo.autocomplete = "off";
      input.replaceWith(campo);
      input = campo;
      iconoPin.hidden = true;
    }
    enlazarEntrada(input);
  }

  input = document.createElement("textarea");
  input.id = "entrada-chat";
  input.rows = 1;
  input.maxLength = 2000;
  input.placeholder = "Escribe tu pregunta…";
  input.setAttribute("aria-label", "Escribe tu mensaje");
  input.autocomplete = "off";
  form.append(iconoPin, input, mic, submit);
  enlazarEntrada(input);
  const botonBajar = boton("Nuevos mensajes", "↓", "btn btn--acento boton-bajar", "Bajar a los mensajes nuevos");
  botonBajar.hidden = true;
  botonBajar.addEventListener("click", () => {
    autoscroll = true;
    desplazarAbajo(true);
    botonBajar.hidden = true;
  });
  composer.append(form);
  contenedor.replaceChildren();
  contenedor.className = "vista vista--activa";
  const raizChat = elemento("div", "chat-vista");
  raizChat.append(cabecera, aviso, mensajesNodo, composer);
  contenedor.append(raizChat, botonBajar);

  function guardarConversacion(id) {
    conversacionId = id || conversacionId;
    if (!conversacionId) return;
    if (botonBorrarChat) botonBorrarChat.hidden = !usuarioActual;
    try {
      sessionStorage.setItem("biblioteca-conversacion-id", conversacionId);
    } catch {
      // La conversación sigue activa durante esta visita aunque no se pueda guardar.
    }
  }

  function actualizarUsuario(usuario, invitado = false) {
    if (usuario) {
      usuarioActual = usuario;
      chipUsuario.textContent = usuario.nombre || "Identificado";
      chipUsuario.title = usuario.nombre || "";
      botonSesion.hidden = true;
    } else {
      usuarioActual = null;
      chipUsuario.textContent = invitado ? "Invitado" : "Inicia sesión";
      chipUsuario.removeAttribute("title");
      botonSesion.hidden = !invitado;
    }
    if (botonBorrarChat) botonBorrarChat.hidden = !usuario || !conversacionId;
    document.querySelector(".cabecera-movil")?.classList.toggle(
      "cabecera-movil--invitado",
      !usuario && invitado,
    );
    opciones.alActualizarUsuario?.(usuarioActual, invitado);
  }

  function desplazarAbajo(suave = true) {
    if (!autoscroll) {
      botonBajar.hidden = false;
      return;
    }
    const movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({
      top: document.documentElement.scrollHeight,
      behavior: suave && !movimientoReducido ? "smooth" : "instant",
    });
  }

  window.addEventListener("scroll", () => {
    const distancia = document.documentElement.scrollHeight - window.scrollY - window.innerHeight;
    autoscroll = distancia < 140;
    if (autoscroll) botonBajar.hidden = true;
  }, { passive: true });

  function bienvenida() {
    const section = elemento("section", "bienvenida");
    section.setAttribute("aria-labelledby", "bienvenida-titulo");
    const encabezado = elemento("h2", "", "¿Qué quieres leer hoy?");
    encabezado.id = "bienvenida-titulo";
    section.append(encabezado, elemento("p", "", "Busca una historia, consulta el catálogo o pregunta lo que necesites de la biblioteca."));
    const microfonoGrande = boton("", microfono, "microfono-grande", "Hablar con el agente");
    microfonoGrande.dataset.accionMicrofono = "";
    section.append(microfonoGrande);
    const rejilla = elemento("div", "sugerencias");
    sugerencias.forEach(([icono, texto]) => {
      const propuesta = boton(texto, iconos[icono] || "", "sugerencia");
      propuesta.addEventListener("click", () => enviarTexto(texto));
      rejilla.append(propuesta);
    });
    section.append(rejilla);
    mensajesNodo.replaceChildren(section);
  }

  function renderizarMensajeUsuario(mensaje) {
    const item = elemento("article", "mensaje mensaje--usuario");
    item.setAttribute("aria-label", mensaje.voz ? "Mensaje enviado por voz" : "Tu mensaje");
    const contenido = elemento("div", "mensaje__cuerpo");
    const meta = elemento("div", "mensaje__meta");
    if (mensaje.voz) meta.append(elemento("span", "", "🎙 Por voz"));
    meta.append(elemento("time", "", mensaje.hora || horaActual()));
    const texto = elemento("p", "mensaje__texto", mensaje.texto);
    contenido.append(meta, texto);
    item.append(contenido);
    return item;
  }

  function tarjetaAvisos(resultado, contenido) {
    const tarjetaAvisos = elemento("section", "aviso aviso--info avisos-bienvenida");
    tarjetaAvisos.setAttribute("aria-label", "Avisos de tu cuenta");
    const listaAvisos = elemento("ul");
    const avisos = resultado.avisos && typeof resultado.avisos === "object" && !Array.isArray(resultado.avisos)
      ? resultado.avisos : {};
    const pesos = (valor) => `$${Math.round(Number(valor) || 0).toLocaleString("es-CO")}`;
    const dias = (n) => (n === 1 ? "1 día" : `${n} días`);
    const cuando = (n) => (n <= 0 ? "vence hoy" : n === 1 ? "vence mañana" : `vence en ${n} días`);
    const hora = (iso) => {
      const fecha = new Date(iso);
      return Number.isNaN(fecha.getTime()) ? "pronto"
        : fecha.toLocaleString("es-CO", { weekday: "long", hour: "numeric", minute: "2-digit" });
    };
    const agregarAviso = (clase, texto) => listaAvisos.append(elemento("li", clase, texto));
    (avisos.vencidos || []).forEach((prestamo) => agregarAviso("aviso-categoria--prestado",
      `«${prestamo.titulo}» está vencido hace ${dias(Number(prestamo.dias_retraso) || 0)}.`));
    if (avisos.multas && Number(avisos.multas.total) > 0) {
      const cantidad = Number(avisos.multas.cantidad) || 1;
      agregarAviso("aviso-categoria--prestado",
        `${cantidad === 1 ? "Multa pendiente" : `${cantidad} multas pendientes`}: ${pesos(avisos.multas.total)}. Mientras exista, no podrá renovar ni pedir préstamos.`);
    }
    (avisos.por_vencer || []).forEach((prestamo) => agregarAviso("aviso-categoria--reservado",
      `«${prestamo.titulo}» ${cuando(Number(prestamo.dias_restantes))}.`));
    (avisos.reservas_por_expirar || []).forEach((reserva) => agregarAviso("aviso-categoria--reservado",
      `Su reserva de «${reserva.titulo}» se guarda hasta el ${hora(reserva.expira_en)}.`));
    if (listaAvisos.childElementCount) {
      tarjetaAvisos.append(listaAvisos);
      contenido.append(tarjetaAvisos);
    }
  }

  async function sincronizarSesion(resultado) {
    if (!resultado.sesion_iniciada) return;
    let usuario = resultado.usuario || null;
    try {
      const sesion = await consultarSesion();
      if (sesion?.autenticado && sesion.usuario) usuario = sesion.usuario;
    } catch {
      // La respuesta del chat también incluye el usuario, por si /api/sesion no responde.
    }
    if (usuario) actualizarUsuario(usuario);
  }

  function fuentesPara(resultado, contenedorFuentes) {
    const fuentes = Array.isArray(resultado.fuentes) ? resultado.fuentes : [];
    // Una sola etiqueta por documento + sección (varios fragmentos del mismo resumen no se repiten),
    // sin distinguir mayúsculas, y como máximo 3 chips
    const vistos = new Set();
    const elegibles = fuentes.filter((fuenteDato) => {
      if (!fuenteDato?.seccion) return false;
      const clave = `${fuenteDato.documento}|${fuenteDato.seccion}`.toLocaleLowerCase("es");
      if (vistos.has(clave)) return false;
      vistos.add(clave);
      return true;
    }).slice(0, 3);
    if (!elegibles.length) return;
    const fila = elemento("div", "fuentes");
    elegibles.forEach((fuenteDato) => {
      const chip = elemento("span", "chip chip--fuente", `${nombreFuente(fuenteDato.documento)} · ${fuenteDato.seccion}`);
      if (fuenteDato.similitud != null) {
        chip.title = `Similitud: ${Math.round(Number(fuenteDato.similitud) * 100)} %`;
      }
      fila.append(chip);
    });
    contenedorFuentes.append(fila);
  }

  function textoVisible(resultado) {
    let texto = String(resultado.respuesta || "No tengo una respuesta disponible todavía.");
    const tieneChips = Array.isArray(resultado.fuentes)
      && resultado.fuentes.some((fuenteDato) => fuenteDato?.seccion);
    if (tieneChips) {
      texto = texto.replace(/(?:^|\s)Fuente:\s*[^.\n]*(?:\s*›\s*[^.\n]*)?\.?/gi, " ");
      texto = texto.replace(/[ \t]{2,}/g, " ").replace(/\n[ \t]+/g, "\n").trim();
    }
    return texto;
  }

  function barraTiempos(resultado, detalles) {
    const tiempos = resultado.tiempos || {};
    const etiquetas = [
      ["t_stt_ms", "STT"],
      ["t_embedding_ms", "Embeddings"],
      ["t_busqueda_ms", "Búsqueda"],
      ["t_llm_ms", "LLM"],
      ["t_tts_ms", "TTS"],
      ["t_total_ms", "Total"],
    ];
    const lista = elemento("dl");
    etiquetas.forEach(([llave, etiqueta]) => {
      const valor = tiempos[llave] ?? (llave === "t_tts_ms" ? resultado.t_tts_ms : null);
      lista.append(elemento("dt", "", etiqueta), elemento("dd", "", valor == null ? "—" : `${Math.round(Number(valor))} ms`));
    });
    detalles.append(lista);
    const segmentos = [
      ["t_stt_ms", "barra-tiempos__stt", "Reconocimiento"],
      ["t_embedding_ms", "barra-tiempos__busqueda", "Embeddings"],
      ["t_busqueda_ms", "barra-tiempos__busqueda", "Búsqueda"],
      ["t_llm_ms", "barra-tiempos__llm", "Respuesta"],
      ["t_tts_ms", "barra-tiempos__tts", "Voz"],
    ];
    const valores = segmentos.map(([llave]) => Math.max(0, Number(tiempos[llave] ?? (llave === "t_tts_ms" ? resultado.t_tts_ms : 0)) || 0));
    const suma = valores.reduce((total, actual) => total + actual, 0);
    const barra = elemento("div", "barra-tiempos");
    barra.setAttribute("role", "img");
    barra.setAttribute("aria-label", `Distribución de tiempos: ${segmentos.map(([llave, , etiqueta]) => `${etiqueta} ${Math.round(Number(tiempos[llave]) || 0)} ms`).join(", ")}`);
    segmentos.forEach(([, clase], indice) => {
      if (!valores[indice]) return;
      const segmento = elemento("span", `barra-tiempos__segmento ${clase}`);
      segmento.style.width = `${Math.max(1, valores[indice] / (suma || 1) * 100)}%`;
      barra.append(segmento);
    });
    detalles.append(barra);
  }

  async function verResumen(material, area, botonResumen) {
    const contenido = area.querySelector("p");
    const abrir = area.classList.toggle("lomo__resumen--abierto");
    botonResumen.textContent = abrir ? "Ocultar resumen" : "Ver resumen";
    if (!abrir || contenido.dataset.cargado === "true") return;
    if (resumentes.has(material.material_id)) {
      contenido.textContent = resumentes.get(material.material_id);
      contenido.dataset.cargado = "true";
      return;
    }
    contenido.textContent = "Cargando resumen…";
    try {
      const datos = await obtenerMaterial(material.material_id);
      contenido.textContent = datos.resumen || datos.descripcion_corta || "No hay un resumen disponible para este material.";
    } catch {
      contenido.textContent = "No se pudo cargar el resumen. Inténtalo de nuevo.";
      contenido.dataset.cargado = "false";
      botonResumen.textContent = "Reintentar resumen";
      return;
    }
    contenido.dataset.cargado = "true";
    resumentes.set(material.material_id, contenido.textContent);
  }

  function esTesisDigital(material) {
    const estantes = Array.isArray(material.estantes)
      ? material.estantes
      : material.estante ? [material.estante] : [];
    return String(material.tipo || "").toLocaleLowerCase("es") === "tesis"
      && estantes.some((estante) => String(estante).trim().toLocaleLowerCase("es") === "repositorio digital");
  }

  function tarjetaMaterial(material) {
    const tarjeta = elemento("article", `lomo lomo--${claveTipo(material.tipo)} lomo-chat`);
    tarjeta.dataset.materialId = material.material_id;
    const tipo = elemento("p", "lomo__tipo", tipoVisible(material.tipo));
    const esDigital = esTesisDigital(material);
    if (esDigital) tipo.append(elemento("span", "chip lomo__digital", "Digital"));
    tarjeta.append(tipo);
    tarjeta.append(elemento("h3", "", material.titulo || "Material sin título"));
    tarjeta.append(elemento("p", "lomo__autor", [material.autor, material.anio].filter(Boolean).join(" · ") || "Autor no indicado"));
    const disponibles = Number(material.disponibles) || 0;
    const reservados = Number(material.reservados) || 0;
    const total = Number(material.total) || 0;
    const estado = elemento("span", `estado ${disponibles > 0 ? "estado--disponible" : reservados > 0 ? "estado--reservado" : "estado--prestado"}`,
      disponibles > 0 ? `${disponibles} de ${total} disponibles` : reservados > 0 ? "Reservado" : "Prestado");
    const pie = elemento("div", "lomo__pie");
    pie.append(elemento("span", "lomo__estante", (Array.isArray(material.estantes) && material.estantes.length ? material.estantes.map((estante) => `Estante ${estante}`).join(" · ") : "Estante no indicado")), estado);
    tarjeta.append(pie);

    if (material.similitud != null) {
      const porcentaje = Math.round(Number(material.similitud) * 100);
      const coincidencia = elemento("div", "coincidencia");
      const progreso = document.createElement("progress");
      progreso.max = 100;
      progreso.value = porcentaje;
      progreso.setAttribute("aria-label", `Coincidencia ${porcentaje} por ciento`);
      coincidencia.append(progreso, elemento("span", "", `${porcentaje} %`));
      tarjeta.append(coincidencia);
    }

    const resumenArea = elemento("div", "lomo__resumen");
    const resumenInterno = elemento("div");
    const resumenTexto = elemento("p");
    resumenInterno.append(resumenTexto);
    resumenArea.append(resumenInterno);
    tarjeta.append(resumenArea);
    const acciones = elemento("div", "lomo__acciones");
    const reservarBoton = boton("Reservar", reservar, "btn btn--acento");
    reservarBoton.disabled = total === 0;
    if (total === 0) {
      reservarBoton.title = "No hay ejemplares registrados para reservar.";
      reservarBoton.setAttribute("aria-label", "Reservar, no hay ejemplares disponibles");
    }
    reservarBoton.addEventListener("click", () => enviarTexto(`Quiero reservar «${material.titulo}»`));
    const verResumenBoton = boton("Ver resumen", resumen);
    verResumenBoton.addEventListener("click", () => verResumen(material, resumenArea, verResumenBoton));
    const mapaBoton = boton("Ver en el mapa", "⌖");
    mapaBoton.addEventListener("click", async () => {
      await opciones.navegar?.("mapa");
      opciones.resaltarMaterial?.(material.material_id);
    });
    acciones.append(reservarBoton, verResumenBoton, mapaBoton);
    if (esDigital && material.material_id != null) {
      const pdfBoton = boton("Ver PDF", iconos.fuente);
      pdfBoton.addEventListener("click", () => {
        window.open(`/api/tesis/${encodeURIComponent(material.material_id)}/pdf`, "_blank", "noopener,noreferrer");
      });
      acciones.append(pdfBoton);
    }
    tarjeta.append(acciones);
    return tarjeta;
  }

  function accionesSiguientes(resultado, textoUsuario) {
    const materiales = Array.isArray(resultado.materiales) ? resultado.materiales : [];
    const acciones = [];
    if (materiales.length) {
      const disponible = materiales.find((material) => Number(material.disponibles) > 0);
      if (disponible) acciones.push(["Resérvalo", `Quiero reservar «${disponible.titulo}»`]);
      const esResumen = [resultado.herramienta, resultado.intencion]
        .some((valor) => String(valor || "").includes("resumir_material"));
      if (esResumen) {
        const materialDigital = materiales.find(esTesisDigital);
        if (materialDigital) {
          acciones.push(["Ver PDF", null, () => {
            window.open(`/api/tesis/${encodeURIComponent(materialDigital.material_id)}/pdf`, "_blank", "noopener,noreferrer");
          }]);
        }
      } else {
        acciones.push(["¿De qué trata?", null, () => {
          const botonResumen = mensajesNodo.querySelector(`[data-material-id="${CSS.escape(String(materiales[0].material_id))}"] .lomo__acciones button:nth-child(2)`);
          botonResumen?.click();
        }]);
      }
      acciones.push(["Muéstrame más", `Muéstrame más libros sobre ${textoUsuario || ultimoTextoUsuario}`]);
    } else if (resultado.intencion === "consultar_prestamos_y_multas") {
      acciones.push(["Renovar mi préstamo", "Quiero renovar mi préstamo"], ["¿Cómo pago una multa?", "¿Cómo pago una multa?"]);
    } else if (resultado.intencion === "responder_con_documentos") {
      const texto = `${textoUsuario} ${resultado.respuesta || ""}`.toLocaleLowerCase("es");
      if (texto.includes("apa")) acciones.push(["¿Y en IEEE?", "¿Cómo cito en IEEE?"]);
      if (texto.includes("reglamento")) acciones.push(["¿Tengo multas?", "¿Tengo multas?"]);
    }
    if (resultado.bibliografia) {
      const norma = String(resultado.bibliografia.norma || "APA").toUpperCase();
      acciones.push(norma === "APA"
        ? ["En IEEE", cambiarNorma(textoUsuario, "IEEE")]
        : ["En APA", cambiarNorma(textoUsuario, "APA")]);
    }
    const fila = elemento("div", "pasos-siguientes");
    acciones.slice(0, 3).forEach(([etiqueta, texto, accion]) => {
      const paso = boton(etiqueta, "", "btn btn--fantasma");
      paso.addEventListener("click", () => accion ? accion() : enviarTexto(texto));
      fila.append(paso);
    });
    return fila.childElementCount ? fila : null;
  }

  function cambiarNorma(texto, norma) {
    const base = texto || ultimoTextoUsuario || "Genera una bibliografía";
    const sinNorma = base
      .replace(/\b(?:en\s+)?(?:formato\s+)?(?:norma\s+)?(?:APA|IEEE)\b/gi, "")
      .replace(/\s+([?.!,])/g, "$1")
      .trim();
    return `${sinNorma || "Genera una bibliografía"} en ${norma}`;
  }

  function reproducirEnTarjeta(contenido, resultado) {
    const botonEscuchar = boton("Escuchar", play);
    botonEscuchar.addEventListener("click", async () => {
      botonEscuchar.disabled = true;
      try {
        let base64 = resultado.audio_wav_base64;
        if (!base64) {
          const audio = await sintetizar(resultado.respuesta_voz || resultado.respuesta || "");
          base64 = audio.audio_wav_base64;
        }
        reproducirRespuesta(contenido, base64, resultado.respuesta_voz || resultado.respuesta || "");
      } catch {
        const estado = elemento("span", "texto-sec", "No se pudo preparar el audio. Inténtalo de nuevo.");
        contenido.append(estado);
      } finally {
        botonEscuchar.disabled = false;
      }
    });
    contenido.append(botonEscuchar);
  }

  function renderizarAgente(resultado, textoUsuario, voz = false, autoReproducir = false, eleccion = null, registro = null) {
    const item = elemento("article", "mensaje mensaje--agente");
    item.setAttribute("aria-label", "Respuesta del agente");
    const avatar = elemento("span", "mensaje__avatar");
    avatar.innerHTML = libroAbierto;
    avatar.setAttribute("aria-hidden", "true");
    const contenido = elemento("div", "mensaje__cuerpo");
    const meta = elemento("div", "mensaje__meta");
    meta.append(elemento("span", "", "Biblioteca · Agente"), elemento("time", "", registro?.hora || horaActual()));
    contenido.append(meta);

    if (resultado.error) {
      const error = elemento("div", "aviso aviso--error");
      const iconoError = elemento("span");
      iconoError.innerHTML = alerta;
      error.append(iconoError, elemento("p", "", "No pudimos completar la consulta. Inténtalo de nuevo."));
      const retry = boton("Reintentar", "", "btn btn--fantasma");
      retry.addEventListener("click", () => enviarTexto(textoUsuario));
      error.append(retry);
      contenido.append(error);
      item.append(avatar, contenido);
      return item;
    }

    if (resultado.bienvenida || (resultado.sesion_iniciada && !resultado.accion_pendiente)) {
      contenido.append(elemento("p", "mensaje__texto", resultado.respuesta));
      tarjetaAvisos(resultado, contenido);
      item.append(avatar, contenido);
      return item;
    }

    if (resultado.sesion_iniciada) tarjetaAvisos(resultado, contenido);

    if (resultado.ofrecerReintento) {
      contenido.append(elemento("p", "mensaje__texto", "Ya iniciaste sesión. ¿Quieres reintentar tu solicitud?"));
      const reintentar = boton("Reintentar", "", "btn btn--acento");
      reintentar.addEventListener("click", () => enviarTexto(textoUsuario));
      contenido.append(reintentar);
      item.append(avatar, contenido);
      return item;
    }

    const materiales = Array.isArray(resultado.materiales)
      ? resultado.materiales
      : resultado.material && typeof resultado.material === "object" ? [resultado.material] : [];
    const esResumenTesis = [resultado.herramienta, resultado.intencion]
      .some((valor) => String(valor || "").includes("resumir_material"));
    if (resultado.accion_pendiente) {
      contenido.append(elemento("p", "mensaje__texto", resultado.accion_pendiente.aviso || "Necesito tu confirmación:"));
    } else if (materiales.length) {
      if (esResumenTesis || ["consultar_disponibilidad", "recomendar_contexto"].includes(resultado.herramienta)) {
        const cuerpo = elemento("div", "mensaje__texto");
        cuerpo.innerHTML = renderMarkdown(textoVisible(resultado));
        contenido.append(cuerpo);
      } else {
        contenido.append(elemento("p", "mensaje__texto", `Encontré ${materiales.length} ${materiales.length === 1 ? "material" : "materiales"}:`));
      }
      const lomos = elemento("div", "lomos-chat");
      materiales.forEach((material) => lomos.append(tarjetaMaterial(material)));
      contenido.append(lomos);
    } else {
      const cuerpo = elemento("div", "mensaje__texto");
      cuerpo.innerHTML = renderMarkdown(textoVisible(resultado));
      contenido.append(cuerpo);
    }

    fuentesPara(resultado, contenido);
    if (resultado.bibliografia) contenido.append(renderBibliografia(resultado.bibliografia));

    const barra = elemento("div", "mensaje__herramientas");
    reproducirEnTarjeta(barra, resultado);
    const textoBase = materiales.length
      ? `Encontré ${materiales.length} ${materiales.length === 1 ? "material" : "materiales"}:\n${materiales.map((material) => [material.titulo, material.autor, material.anio].filter(Boolean).join(" · ")).join("\n")}`
      : resultado.respuesta || "";
    const referenciasTexto = resultado.bibliografia?.referencias?.map((referencia) => referencia.texto).filter(Boolean).join("\n") || "";
    const textoRespuesta = [textoBase, referenciasTexto].filter(Boolean).join("\n\n");
    const copiar = boton("Copiar respuesta", "", "btn btn--fantasma");
    copiar.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(textoRespuesta);
        copiar.querySelector("span:last-child").textContent = "Copiado";
        window.setTimeout(() => { copiar.querySelector("span:last-child").textContent = "Copiar respuesta"; }, 1800);
      } catch {
        copiar.querySelector("span:last-child").textContent = "No se pudo copiar";
      }
    });
    barra.append(copiar);
    contenido.append(barra);

    const detalles = elemento("details", "detalles-tecnicos");
    detalles.append(elemento("summary", "", "Detalles técnicos"));
    detalles.append(elemento("p", "", `Intención: ${resultado.intencion || "—"} · Herramienta: ${resultado.herramienta || "—"}`));
    barraTiempos(resultado, detalles);
    contenido.append(detalles);
    const siguiente = resultado.accion_pendiente ? null : accionesSiguientes(resultado, textoUsuario);
    if (siguiente) contenido.append(siguiente);

    if (resultado.accion_pendiente) {
      const confirmacion = elemento("section", "tarjeta confirmacion");
      const tipoAccion = resultado.accion_pendiente.tipo;
      const descripcionAccion = tipoAccion === "reservar"
        ? "la reserva"
        : tipoAccion === "cancelar_reserva" ? "la cancelación de la reserva" : "la renovación";
      const tituloConfirmacion = elemento("p", "confirmacion__titulo", `¿Confirmo ${descripcionAccion} de «${resultado.accion_pendiente.descripcion || "este material"}»?`);
      const iconoConfirmacion = elemento("span");
      iconoConfirmacion.innerHTML = reservar;
      tituloConfirmacion.prepend(iconoConfirmacion);
      confirmacion.append(tituloConfirmacion);
      const accionesConfirmacion = elemento("div", "confirmacion__acciones");
      const confirmar = boton("Confirmar", "", "btn btn--acento");
      const cancelar = boton("Cancelar", "", "btn btn--fantasma");
      const elegir = async (texto, eleccionTexto) => {
        if (ocupado) return;
        llamada.terminar("");
        confirmar.disabled = true;
        cancelar.disabled = true;
        if (registro) registro.eleccion = eleccionTexto;
        mensajes.push({ tipo: "usuario", texto, hora: horaActual(), voz: false });
        renderizar();
        await procesarMensaje(texto);
      };
      confirmar.addEventListener("click", () => elegir("sí", "Confirmar"));
      cancelar.addEventListener("click", () => elegir("no", "Cancelar"));
      accionesConfirmacion.append(confirmar, cancelar);
      if (eleccion) accionesConfirmacion.append(elemento("span", "texto-sec", `Elegiste: ${eleccion}`));
      confirmacion.append(accionesConfirmacion);
      contenido.append(confirmacion);
      if (eleccion) {
        confirmar.disabled = true;
        cancelar.disabled = true;
      }
    }

    if (resultado.requiere_login) {
      ultimoTextoRequiereLogin = textoUsuario;
      const filaSesion = elemento("div", "mensaje__herramientas");
      const iniciar = boton("Iniciar sesión", "", "btn btn--acento");
      iniciar.addEventListener("click", () => opciones.solicitarLogin?.(textoUsuario));
      filaSesion.append(iniciar);
      contenido.append(filaSesion);
    }

    item.append(avatar, contenido);
    if (autoReproducir && resultado.audio_wav_base64) {
      if (registro) registro.autoReproducir = false;
      ultimaReproduccion = reproducirRespuesta(contenido, resultado.audio_wav_base64, resultado.respuesta_voz || resultado.respuesta || "");
    }
    return item;
  }

  function renderizar() {
    if (!mensajes.length) {
      bienvenida();
      return;
    }
    const fragmento = document.createDocumentFragment();
    mensajes.forEach((mensaje) => {
      if (mensaje.tipo === "usuario") fragmento.append(renderizarMensajeUsuario(mensaje));
      else if (mensaje.tipo === "agente") fragmento.append(renderizarAgente(mensaje.resultado, mensaje.textoUsuario, mensaje.voz, mensaje.autoReproducir, mensaje.eleccion, mensaje));
      else fragmento.append(renderizarError(mensaje));
    });
    mensajesNodo.replaceChildren(fragmento);
    if (autoscroll) desplazarAbajo();
    else botonBajar.hidden = false;
  }

  function renderizarError(mensaje) {
    const item = elemento("article", "mensaje mensaje--agente");
    const avatar = elemento("span", "mensaje__avatar");
    avatar.innerHTML = libroAbierto;
    const cuerpo = elemento("div", "mensaje__cuerpo");
    const alertaNodo = elemento("div", "aviso aviso--error");
    const iconoError = elemento("span");
    iconoError.innerHTML = alerta;
    alertaNodo.append(iconoError, elemento("p", "", mensaje.texto || "No pudimos completar la consulta."));
    if (mensaje.reintentar) {
      const reintentar = boton("Reintentar", "", "btn btn--fantasma");
      reintentar.addEventListener("click", () => enviarTexto(mensaje.reintentar));
      alertaNodo.append(reintentar);
    } else if (mensaje.regrabar) {
      const reintentar = boton("Grabar de nuevo", microfono, "btn btn--fantasma");
      reintentar.addEventListener("click", () => voz.iniciar());
      alertaNodo.append(reintentar);
    }
    cuerpo.append(alertaNodo);
    item.append(avatar, cuerpo);
    return item;
  }

  function mostrarEtapa(etapa, voz, tiempo, conAudio) {
    if (!etapa.isConnected) return;
    const segundos = (Date.now() - tiempo) / 1000;
    let texto;
    if (voz && segundos < 2) texto = "Transcribiendo tu voz…";
    else if (segundos < 2.5 || voz && segundos < 4.5) texto = "Buscando en el catálogo…";
    else if (conAudio && segundos > 6) texto = "Preparando la voz…";
    else texto = "Escribiendo la respuesta…";
    etapa.textContent = texto;
  }

  async function procesarMensaje(texto, forzarAudio, entradaOculta = false) {
    if (ocupado || !texto.trim()) return null;
    ocupado = true;
    const generacionSolicitud = generacion;
    ultimoTextoUsuario = entradaOculta ? "" : texto;
    input.value = "";
    if (entradaOculta) establecerModoEntrada("normal");
    ajustarEntrada();
    submit.disabled = true;
    const espera = elemento("article", "mensaje mensaje--agente");
    const avatar = elemento("span", "mensaje__avatar");
    avatar.innerHTML = libroAbierto;
    const tarjeta = elemento("div", "mensaje__cuerpo");
    const pensando = elemento("div", "pensando");
    pensando.innerHTML = "<span></span><span></span><span></span>";
    pensando.setAttribute("aria-hidden", "true");
    const estado = elemento("p", "etapa-respuesta");
    estado.dataset.etapa = "";
    estado.setAttribute("role", "status");
    estado.setAttribute("aria-live", "polite");
    tarjeta.append(pensando, estado);
    espera.append(avatar, tarjeta);
    mensajesNodo.append(espera);
    const inicio = Date.now();
    const conAudio = forzarAudio ?? leyendoVoz;
    const intervaloEtapa = window.setInterval(() => mostrarEtapa(estado, false, inicio, conAudio), 350);
    mostrarEtapa(estado, false, inicio, conAudio);
    desplazarAbajo();
    try {
      const resultado = await enviarChat(texto, conversacionId, conAudio);
      if (generacionSolicitud !== generacion) return null;
      window.clearInterval(intervaloEtapa);
      espera.remove();
      guardarConversacion(resultado.conversacion_id);
      if (entradaOculta || resultado.entrada_oculta) {
        const usuario = mensajes.findLast?.((mensaje) => mensaje.tipo === "usuario");
        if (usuario) usuario.texto = "PIN enviado ••••";
      }
      if (resultado.esperando === "pin") establecerModoEntrada("pin");
      else establecerModoEntrada("normal", resultado.esperando === "codigo");
      const vozAutomatica = Boolean(resultado.audio_wav_base64 && conAudio);
      const textoSeguro = entradaOculta || resultado.entrada_oculta ? "" : texto;
      mensajes.push({ tipo: "agente", resultado, textoUsuario: textoSeguro, autoReproducir: vozAutomatica });
      renderizar();
      if (resultado.sesion_iniciada) await sincronizarSesion(resultado);
      else if (resultado.usuario) actualizarUsuario(resultado.usuario);
      return resultado;
    } catch {
      if (generacionSolicitud !== generacion) return null;
      window.clearInterval(intervaloEtapa);
      espera.remove();
      mensajes.push({
        tipo: "error",
        texto: "No pudimos conectar con el agente. Revisa tu conexión e inténtalo de nuevo.",
        reintentar: entradaOculta ? "" : texto,
      });
      renderizar();
      return null;
    } finally {
      if (generacionSolicitud === generacion) {
        ocupado = false;
        submit.disabled = false;
        input.focus({ preventScroll: true });
      }
    }
  }

  async function enviarTexto(texto) {
    const mensaje = String(texto || "").trim();
    if (!mensaje || ocupado) return;
    llamada.terminar("");
    const entradaOculta = modoEntrada === "pin";
    mensajes.push({
      tipo: "usuario",
      texto: entradaOculta ? "PIN enviado ••••" : mensaje,
      hora: horaActual(),
      voz: false,
    });
    renderizar();
    await procesarMensaje(mensaje, undefined, entradaOculta);
  }

  function mostrarTranscripcion(texto) {
    esperaVoz?.remove();
    esperaVoz = null;
    mensajes.push({ tipo: "usuario", texto, hora: horaActual(), voz: true });
    renderizar();
  }

  async function recibirVoz(resultado, transcripcion, alHablar, vigente = () => true) {
    const generacionSolicitud = generacion;
    esperaVoz?.remove();
    esperaVoz = null;
    if (!resultado || resultado.ok === false) {
      mensajes.push({
        tipo: "error",
        texto: "No entendí la grabación. Habla con claridad, revisa el micrófono e inténtalo de nuevo.",
        reintentar: "",
        regrabar: true,
      });
      renderizar();
      return;
    }
    if (!transcripcion) transcripcion = resultado.transcripcion || "";
    const entradaOculta = modoEntrada === "pin" || resultado.entrada_oculta || transcripcion === "[PIN oculto]";
    const transcripcionSegura = entradaOculta ? "PIN enviado ••••" : transcripcion || "Consulta por voz";
    if (!resultado.transcripcion_mostrada) mensajes.push({ tipo: "usuario", texto: transcripcionSegura, hora: horaActual(), voz: true });
    guardarConversacion(resultado.conversacion_id);
    if (resultado.esperando === "pin") establecerModoEntrada("pin");
    else establecerModoEntrada("normal", resultado.esperando === "codigo");
    const registro = {
      tipo: "agente",
      resultado,
      textoUsuario: entradaOculta ? "" : transcripcion,
      voz: true,
      autoReproducir: Boolean(resultado.audio_wav_base64),
    };
    mensajes.push(registro);
    ultimaReproduccion = null;
    if (registro.autoReproducir) alHablar?.();
    renderizar();
    if (resultado.sesion_iniciada) await sincronizarSesion(resultado);
    else if (resultado.usuario) actualizarUsuario(resultado.usuario);
    if (!resultado.audio_wav_base64 && resultado.respuesta) {
      try {
        const audio = await sintetizar(resultado.respuesta_voz || resultado.respuesta);
        if (generacionSolicitud !== generacion || !vigente()) return null;
        if (audio.audio_wav_base64) {
          resultado.audio_wav_base64 = audio.audio_wav_base64;
          registro.autoReproducir = true;
          alHablar?.();
          renderizar();
        }
      } catch {
        // Las tarjetas y el texto ya están disponibles aunque falle la voz local.
      }
    }
    return ultimaReproduccion;
  }

  function estadoVoz(texto) {
    if (!esperaVoz) {
      esperaVoz = elemento("article", "mensaje mensaje--agente");
      const avatar = elemento("span", "mensaje__avatar");
      avatar.innerHTML = libroAbierto;
      const tarjeta = elemento("div", "mensaje__cuerpo");
      const pensando = elemento("div", "pensando");
      pensando.innerHTML = "<span></span><span></span><span></span>";
      pensando.setAttribute("aria-hidden", "true");
      const estado = elemento("p", "etapa-respuesta");
      estado.setAttribute("role", "status");
      estado.setAttribute("aria-live", "polite");
      tarjeta.append(pensando, estado);
      esperaVoz.append(avatar, tarjeta);
      mensajesNodo.append(esperaVoz);
    }
    esperaVoz.querySelector(".etapa-respuesta").textContent = texto;
    desplazarAbajo();
  }

  function ajustarEntrada() {
    if (input instanceof HTMLTextAreaElement) {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
    } else {
      input.value = input.value.replace(/\D/g, "").slice(0, 4);
    }
  }

  form.addEventListener("submit", (evento) => {
    evento.preventDefault();
    enviarTexto(input.value);
  });

  const voz = montarVoz(composer, {
    habilitada: () => !llamada.activa,
    entradaSegura: () => modoEntrada === "pin",
    alTranscripcion: mostrarTranscripcion,
    raizMicrofonos: raizChat,
    obtenerConversacionId: () => conversacionId,
    alResultado: recibirVoz,
    alEstado: estadoVoz,
    alAviso: (texto) => {
      esperaVoz?.remove();
      esperaVoz = null;
      mensajes.push({ tipo: "error", texto, reintentar: "", regrabar: !texto.includes("límite") });
      renderizar();
    },
  });

  const llamada = montarLlamada(cabecera, {
    raiz: raizChat,
    disponible: () => !ocupado && !esperaVoz && !voz.ocupada,
    antesDeIniciar: () => voz.destruir(),
    obtenerConversacionId: () => conversacionId,
    entradaSegura: () => modoEntrada === "pin",
    alTranscripcion: mostrarTranscripcion,
    alResultado: recibirVoz,
  });

  document.querySelector("#nueva-conversacion")?.addEventListener("click", () => {
    llamada.terminar("");
    generacion += 1;
    ocupado = false;
    submit.disabled = false;
    voz.destruir();
    mensajes.length = 0;
    conversacionId = null;
    establecerModoEntrada("normal");
    ultimoTextoUsuario = "";
    ultimoTextoRequiereLogin = "";
    actualizarUsuario(usuarioActual, !usuarioActual);
    try {
      sessionStorage.removeItem("biblioteca-conversacion-id");
    } catch {
      // La conversación nueva funciona aunque no se pueda limpiar el almacenamiento.
    }
    opciones.limpiarCuenta?.();
    renderizar();
    input.value = "";
    input.focus();
  });

  botonBorrarChat?.addEventListener("click", async () => {
    if (!conversacionId || !usuarioActual || ocupado) return;
    if (!window.confirm("¿Borrar todo el chat guardado de este perfil?")) return;
    const id = conversacionId;
    botonBorrarChat.disabled = true;
    try {
      await borrarConversacion(id);
      if (conversacionId !== id) return;
      llamada.terminar("");
      generacion += 1;
      ocupado = false;
      submit.disabled = false;
      voz.destruir();
      mensajes.length = 0;
      conversacionId = null;
      if (botonBorrarChat) botonBorrarChat.hidden = true;
      establecerModoEntrada("normal");
      ultimoTextoUsuario = "";
      ultimoTextoRequiereLogin = "";
      try { sessionStorage.removeItem("biblioteca-conversacion-id"); } catch { /* Se limpió el chat en el servidor. */ }
      botonBorrarChat.hidden = true;
      mensajes.push({
        tipo: "agente",
        resultado: { bienvenida: true, respuesta: "Tu chat se borró. Puedes empezar una nueva conversación." },
        textoUsuario: "",
      });
      renderizar();
      input.value = "";
    } catch (error) {
      window.alert(error.message || "No se pudo borrar el chat. Inténtalo de nuevo.");
    } finally {
      botonBorrarChat.disabled = false;
    }
  });

  function establecerAvisoServicios(mensaje) {
    aviso.textContent = mensaje || "";
    aviso.hidden = !mensaje;
  }

  function establecerPreferencias({ voz: vozActiva } = {}) {
    leyendoVoz = Boolean(vozActiva);
  }

  actualizarUsuario(null, true);
  renderizar();
  return {
    enviarTexto,
    establecerAvisoServicios,
    establecerPreferencias,
    obtenerConversacionId: () => conversacionId,
    obtenerUsuario: () => usuarioActual,
    establecerIdentidad: (usuario, invitado = false) => actualizarUsuario(usuario, invitado),
    restaurarConversacion: async () => {
      const usuarioId = usuarioActual?.id;
      if (!usuarioId) return false;
      const carga = generacion;
      try {
        const anterior = await obtenerConversacionActual();
        if (carga !== generacion || Number(usuarioActual?.id) !== Number(usuarioId)) return false;
        if (!anterior?.conversacion_id || !Array.isArray(anterior.mensajes) || !anterior.mensajes.length) return false;
        conversacionId = anterior.conversacion_id;
        try { sessionStorage.setItem("biblioteca-conversacion-id", conversacionId); } catch { /* El servidor conserva la sesión. */ }
        const formatoHora = (fecha) => {
          const instante = new Date(fecha);
          return Number.isNaN(instante.getTime()) ? horaActual()
            : instante.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
        };
        mensajes.length = 0;
        anterior.mensajes.forEach((mensaje) => {
          const hora = formatoHora(mensaje.creado);
          if (mensaje.rol === "user") mensajes.push({ tipo: "usuario", texto: mensaje.contenido, hora, voz: false });
          else if (mensaje.rol === "assistant") mensajes.push({
            tipo: "agente",
            resultado: { respuesta: mensaje.contenido, respuesta_voz: mensaje.contenido, fuentes: [], materiales: [], herramienta: "historial_restaurado" },
            textoUsuario: "",
            hora,
          });
        });
        if (botonBorrarChat) botonBorrarChat.hidden = false;
        renderizar();
        return mensajes.length > 0;
      } catch {
        return false;
      }
    },
    mostrarBienvenida: (mensaje, avisos = []) => {
      mensajes.length = 0;
      mensajes.push({
        tipo: "agente",
        resultado: { bienvenida: true, respuesta: mensaje || "¡Bienvenido a la biblioteca!", avisos },
        textoUsuario: "",
      });
      renderizar();
    },
    ofrecerReintento: (texto) => {
      if (!texto) return;
      mensajes.push({
        tipo: "agente",
        resultado: { ofrecerReintento: true },
        textoUsuario: texto,
      });
      renderizar();
    },
    restablecerIdentidad: () => {
      llamada.terminar("");
      conversacionId = null;
      establecerModoEntrada("normal");
      ultimoTextoRequiereLogin = "";
      actualizarUsuario(null, true);
      try {
        sessionStorage.removeItem("biblioteca-conversacion-id");
      } catch {
        // El estado de la sesión también queda limpio en memoria.
      }
    },
    limpiar: () => {
      llamada.terminar("");
      generacion += 1;
      ocupado = false;
      submit.disabled = false;
      voz.destruir();
      esperaVoz?.remove();
      esperaVoz = null;
      mensajes.length = 0;
      conversacionId = null;
      if (botonBorrarChat) botonBorrarChat.hidden = true;
      establecerModoEntrada("normal");
      ultimoTextoUsuario = "";
      ultimoTextoRequiereLogin = "";
      try {
        sessionStorage.removeItem("biblioteca-conversacion-id");
      } catch {
        // El estado en memoria también queda limpio.
      }
      renderizar();
    },
  };
}
