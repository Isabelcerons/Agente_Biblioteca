import { enviarChat, obtenerMaterial, sintetizar, consultarSesion, obtenerConversacionActual, borrarConversacion, obtenerCatalogo, obtenerPreferenciaVoz, obtenerBienvenidaSalas, adoptarConversacion } from "./api.js";
import { renderMarkdown } from "./markdown.js";
import { renderBibliografia } from "./bibliografia.js";
import { libroAbierto, microfono, enviar, play, reservar, resumen, alerta, iconos } from "./iconos.js";
import { montarVoz, reproducirRespuesta } from "./voz.js";
import { montarLlamada } from "./llamada.js";
import { montarEscenaBiblioteca } from "./escena.js";
import {
  crearChipSala,
  guardarSalaPreferida,
  leerSalaPreferida,
  montarOpcionesSalasChat,
  obtenerSalas,
  textoEleccionSala,
} from "./salas.js";

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

const METADATA_SALAS = {
  ingenieria: {
    slug: "ingenieria",
    nombre: "Sala de Ingeniería y Tecnología",
    nombre_corto: "Sala de Ingeniería",
    icono: "💻",
    bibliotecario: { nombre: "Andrés" },
  },
  "agro-ambiental": {
    slug: "agro-ambiental",
    nombre: "Sala de Ciencias Agrarias y Ambientales",
    nombre_corto: "Sala de Ciencias Agrarias y Ambientales",
    icono: "🌱",
    bibliotecario: { nombre: "Rosa" },
  },
  administracion: {
    slug: "administracion",
    nombre: "Sala de Administración y Negocios",
    nombre_corto: "Sala de Administración y Negocios",
    icono: "📈",
    bibliotecario: { nombre: "Camilo" },
  },
  contaduria: {
    slug: "contaduria",
    nombre: "Sala de Contaduría y Finanzas",
    nombre_corto: "Sala de Contaduría y Finanzas",
    icono: "🧾",
    bibliotecario: { nombre: "Lucía" },
  },
  investigacion: {
    slug: "investigacion",
    nombre: "Sala de Investigación y Escritura",
    nombre_corto: "Sala de Investigación y Escritura",
    icono: "✍️",
    bibliotecario: { nombre: "Elena" },
  },
};

function normalizarObjetoSala(sala) {
  if (!sala) return null;
  const slug = typeof sala === "string" ? sala : sala.slug;
  if (!slug || slug === "todas" || slug === "sin_sala") return null;
  const infoBase = METADATA_SALAS[slug] || {};
  if (typeof sala === "string") {
    return { ...infoBase, slug };
  }
  return {
    ...infoBase,
    ...sala,
    bibliotecario: sala.bibliotecario || infoBase.bibliotecario,
  };
}

function construirTextoBienvenidaConSala(textoOriginal, sala, usuario) {
  try {
    if (!sala) return String(textoOriginal || "");
    const slug = typeof sala === "string" ? sala : sala.slug;
    if (!slug || slug === "todas" || slug === "sin_sala") {
      return String(textoOriginal || "");
    }
    const salaInfo = normalizarObjetoSala(sala);
    if (!salaInfo) return String(textoOriginal || "");

    const nombreUsuario = usuario?.nombre ? String(usuario.nombre).trim() : null;
    const saludo = nombreUsuario ? `Hola, ${nombreUsuario}. ` : "Hola. ";
    const nombreSala = salaInfo.nombre_corto || salaInfo.nombre || "la sala";
    const textoSala = /^(la\s+)?sala/i.test(nombreSala)
      ? nombreSala.replace(/^la\s+/i, "")
      : `Sala de ${nombreSala}`;
    const bibliotecario = typeof salaInfo.bibliotecario === "object"
      ? salaInfo.bibliotecario?.nombre
      : (salaInfo.bibliotecario || "el bibliotecario");

    return `${saludo}Sigues en la ${textoSala} con ${bibliotecario}. ¿Qué buscas?`;
  } catch {
    return String(textoOriginal || "");
  }
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
  let escenaControlador = null;
  let chipSala = null;
  let salaActual = null;

  const alVozAgente = (evento) => {
    if (escenaControlador) {
      escenaControlador.hablar(Boolean(evento.detail?.hablando));
    }
  };
  window.addEventListener("voz-agente", alVozAgente);

  const cabecera = elemento("header", "chat-encabezado");
  const titulo = elemento("h1", "", "Conversar");
  titulo.id = "titulo-chat";
  titulo.tabIndex = -1;
  const accionesCabecera = elemento("div", "chat-acciones-cabecera");
  chipSala = crearChipSala(null, { alCambiar: cambiarSalaDesdeChat });
  chipSala.setAttribute("aria-live", "polite");
  const chipUsuario = elemento("span", "usuario-chip", "Invitado");
  chipUsuario.setAttribute("aria-live", "polite");
  const botonSesion = boton("Iniciar sesión", "", "btn btn--fantasma");
  botonSesion.addEventListener("click", () => opciones.solicitarLogin?.(ultimoTextoRequiereLogin));
  const abrirCuenta = boton("Mi cuenta", "", "btn btn--fantasma");
  abrirCuenta.addEventListener("click", () => opciones.abrirCuenta?.());
  accionesCabecera.append(chipSala, chipUsuario, botonSesion, abrirCuenta);
  cabecera.append(titulo, accionesCabecera);
  const botonBorrarChat = document.querySelector("#borrar-chat");
  sincronizarSalaDesdeStorage();
  obtenerSalas()
    .then((lista) => {
      if (Array.isArray(lista)) {
        lista.forEach((s) => {
          if (s?.slug) METADATA_SALAS[s.slug] = { ...METADATA_SALAS[s.slug], ...s };
        });
        if (salaActual?.slug) {
          actualizarSalaActual(salaActual.slug, { guardar: false });
        }
      }
    })
    .catch(() => {});

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
    try {
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
      if (escenaControlador) {
        const nuevoSaludo = salaActual
          ? construirTextoBienvenidaConSala("¿Qué sala quieres visitar hoy?", salaActual, usuario)
          : (usuario?.nombre
            ? `Hola, ${usuario.nombre}. ¿Qué sala quieres visitar hoy?`
            : "Hola. ¿Qué quieres explorar hoy?");
        escenaControlador.saludar(nuevoSaludo);
      }
      if (botonBorrarChat) botonBorrarChat.hidden = !usuario || !conversacionId;
      document.querySelector(".cabecera-movil")?.classList.toggle(
        "cabecera-movil--invitado",
        !usuario && invitado,
      );
      try {
        opciones.alActualizarUsuario?.(usuarioActual, invitado);
      } catch {
        // Callback externo protegido
      }
    } catch (error) {
      console.warn("Error al actualizar usuario:", error);
    }
  }

  function actualizarSalaActual(nuevaSala, { guardar = true } = {}) {
    const salaActivo = normalizarObjetoSala(nuevaSala);
    if (guardar) {
      guardarSalaPreferida(salaActivo ? salaActivo.slug : null);
    }
    salaActual = salaActivo;
    if (chipSala) {
      chipSala.actualizar?.(salaActual);
    }
    if (escenaControlador && !mensajes.length) {
      const saludo = salaActual
        ? construirTextoBienvenidaConSala("¿Qué sala quieres visitar hoy?", salaActual, usuarioActual)
        : (usuarioActual?.nombre
          ? `Hola, ${usuarioActual.nombre}. ¿Qué sala quieres visitar hoy?`
          : "Hola. ¿Qué quieres explorar hoy?");
      escenaControlador.saludar(saludo);
    }
    return salaActivo;
  }

  function sincronizarSalaDesdeStorage() {
    try {
      const preferida = leerSalaPreferida();
      if (preferida && preferida !== "todas" && preferida !== "sin_sala") {
        return actualizarSalaActual(preferida, { guardar: false });
      }
      return actualizarSalaActual(null, { guardar: false });
    } catch {
      return null;
    }
  }

  let menuSalasAbierto = null;

  function cerrarMenuSalasAbierto() {
    if (!menuSalasAbierto) return;
    menuSalasAbierto.panel.hidden = true;
    menuSalasAbierto.boton.setAttribute("aria-expanded", "false");
    menuSalasAbierto = null;
  }

  function montarMenuSalas({ contenedor, salas = null, salaActual: salaActiva = null, alElegir, compacto = false, textoBoton = "Elegir sala" } = {}) {
    if (!contenedor) return { wrapper: null, cerrar: cerrarMenuSalasAbierto };
    cerrarMenuSalasAbierto();

    const wrapper = document.createElement("div");
    wrapper.className = compacto ? "salas-menu salas-menu--compact" : "salas-menu";

    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = compacto ? "salas-menu__boton salas-menu__boton--compact" : "salas-menu__boton";
    boton.setAttribute("aria-haspopup", "menu");
    boton.setAttribute("aria-expanded", "false");
    const textoBotonLimpio = String(textoBoton || "Elegir sala").replace(/^☰\s*/, "");
    boton.innerHTML = '<span aria-hidden="true">☰</span><span>' + textoBotonLimpio + '</span>';

    const panel = document.createElement("div");
    panel.className = "salas-menu__panel";
    panel.setAttribute("role", "menu");
    panel.setAttribute("aria-label", "Elegir sala");
    panel.hidden = true;

    function crearItem(sala) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "salas-menu__item";
      item.setAttribute("role", "menuitem");
      const esGeneral = !sala || !sala.slug || sala.slug === "todas";
      const slug = esGeneral ? null : sala.slug;
      const activo = !slug && (!salaActiva || salaActiva.slug === null || salaActiva.slug === "todas")
        || Boolean(salaActiva && slug && salaActiva.slug === slug);
      item.setAttribute("aria-checked", String(Boolean(activo)));
      const icono = sala?.icono || (esGeneral ? "🏛️" : "📖");
      const nombre = sala?.nombre_corto || sala?.nombre || "Toda la biblioteca";
      const bibliotecario = typeof sala?.bibliotecario === "object"
        ? sala.bibliotecario?.nombre || "Equipo general"
        : (sala?.bibliotecario || (esGeneral ? "Equipo general" : "Bibliotecario"));
      const conteo = sala?.conteoTexto || (sala?.libros != null && sala?.tesis != null ? `${sala.libros} libros · ${sala.tesis} tesis` : "Catálogo completo");
      const iconoNodo = document.createElement("span");
      iconoNodo.className = "salas-menu__icono";
      iconoNodo.setAttribute("aria-hidden", "true");
      iconoNodo.textContent = icono;
      const textoNodo = document.createElement("span");
      textoNodo.className = "salas-menu__texto";
      const nombreNodo = document.createElement("span");
      nombreNodo.className = "salas-menu__nombre";
      nombreNodo.textContent = nombre;
      const metaNodo = document.createElement("span");
      metaNodo.className = "salas-menu__meta";
      metaNodo.textContent = bibliotecario;
      textoNodo.append(nombreNodo, metaNodo);
      const conteoNodo = document.createElement("span");
      conteoNodo.className = "salas-menu__conteo";
      conteoNodo.textContent = conteo;
      item.append(iconoNodo, textoNodo, conteoNodo);
      item.addEventListener("click", () => {
        const seleccion = esGeneral ? null : sala;
        const texto = textoEleccionSala(seleccion);
        if (typeof alElegir === "function") alElegir(seleccion, texto);
        cerrarMenuSalasAbierto();
      });
      return item;
    }

    function poblar(lista) {
      const opciones = Array.isArray(lista) && lista.length ? [...lista] : [];
      const general = {
        slug: null,
        nombre: "Toda la biblioteca",
        nombre_corto: "Toda la biblioteca",
        icono: "🏛️",
        bibliotecario: { nombre: "Equipo general" },
        conteoTexto: "Catálogo completo",
      };
      if (!opciones.some((item) => !item || !item.slug || item.slug === "todas")) {
        opciones.push(general);
      }
      panel.replaceChildren(...opciones.map(crearItem));
    }

    const abrir = () => {
      const lista = Array.isArray(salas) && salas.length ? salas : null;
      if (lista) {
        poblar(lista);
      } else {
        obtenerSalas().then((resultado) => {
          if (!panel.isConnected) return;
          poblar(Array.isArray(resultado) ? resultado : []);
        }).catch(() => poblar([]));
      }
      panel.hidden = false;
      const rect = boton.getBoundingClientRect();
      const panelHeight = Math.min(window.innerHeight * 0.6, 520);
      const espacioAbajo = window.innerHeight - rect.bottom - 8;
      const espacioArriba = rect.top - 8;
      const abrirArriba = espacioAbajo < panelHeight && espacioArriba > panelHeight;
      panel.style.top = abrirArriba ? "auto" : "calc(100% + 8px)";
      panel.style.bottom = abrirArriba ? "calc(100% + 8px)" : "auto";
      panel.style.maxHeight = `${panelHeight}px`;
      panel.style.overflowY = "auto";
      boton.setAttribute("aria-expanded", "true");
      menuSalasAbierto = { boton, panel };
      const items = [...panel.querySelectorAll('[role="menuitem"]')];
      if (items.length) items[0].focus();
    };

    boton.addEventListener("click", (evento) => {
      evento.preventDefault();
      evento.stopPropagation();
      if (menuSalasAbierto && menuSalasAbierto.panel !== panel) {
        cerrarMenuSalasAbierto();
      }
      if (panel.hidden) abrir();
      else cerrarMenuSalasAbierto();
    });

    document.addEventListener("click", (evento) => {
      if (!wrapper.contains(evento.target) && !panel.hidden) {
        cerrarMenuSalasAbierto();
      }
    }, true);

    document.addEventListener("keydown", (evento) => {
      if (evento.key !== "Escape" || panel.hidden || menuSalasAbierto?.panel !== panel) return;
      cerrarMenuSalasAbierto();
      boton.focus();
    }, true);

    wrapper.append(boton, panel);
    contenedor.append(wrapper);
    return { wrapper, cerrar: cerrarMenuSalasAbierto };
  }

  function cambiarSalaDesdeChat() {
    const destino = chipSala || document.querySelector(".salas-chip");
    if (destino && !destino.querySelector(".salas-menu")) {
      montarMenuSalas({
        contenedor: destino,
        salaActual,
        alElegir: (salaElegida, textoMensaje) => {
          const texto = textoMensaje || textoEleccionSala(salaElegida);
          actualizarSalaActual(salaElegida || null, { guardar: true });
          enviarTexto(texto);
        },
      });
      const botonMenu = destino.querySelector(".salas-menu__boton");
      botonMenu?.click();
      return;
    }
    const botonMenu = destino?.querySelector(".salas-menu__boton");
    if (botonMenu) botonMenu.click();
  }

  function mostrarBienvenidaSalas() {
    if (mensajes.length) return;
    const contenedor = mensajesNodo;
    if (!contenedor) return;

    const bienvenidaGrande = contenedor.querySelector(".bienvenida");
    if (bienvenidaGrande && bienvenidaGrande.isConnected) {
      bienvenidaGrande.hidden = true;
      bienvenidaGrande.dataset.bienvenidaOculta = "true";
    }

    const insertarMensaje = (nodo) => {
      const escena = contenedor.querySelector(".bienvenida");
      if (escena) {
        escena.after(nodo);
      } else {
        contenedor.append(nodo);
      }
    };

    const fallback = () => {
      if (mensajes.length) return;
      try {
        const salaActiva = salaActual || (leerSalaPreferida() ? normalizarObjetoSala(leerSalaPreferida()) : null);
        let textoFallback = usuarioActual?.nombre
          ? `Hola, ${usuarioActual.nombre}. ¿Qué sala quieres visitar hoy?`
          : "Hola. ¿Qué quieres explorar hoy? Puedes consultar toda la biblioteca o elegir una sala cuando quieras.";
        if (salaActiva) {
          textoFallback = construirTextoBienvenidaConSala("¿Qué sala quieres visitar hoy?", salaActiva, usuarioActual);
        }
        const mensajeFallback = renderizarAgente({
          bienvenida: true,
          respuesta: textoFallback,
          salas_opciones: [],
        }, "", false, false, null, { hora: horaActual() });
        const previo = mensajesNodo.querySelector("[data-bienvenida-salas]");
        if (previo) previo.remove();
        mensajeFallback.dataset.bienvenidaSalas = "true";
        insertarMensaje(mensajeFallback);
        const bienvenidaGrandeActiva = mensajesNodo.querySelector(".bienvenida");
        if (bienvenidaGrandeActiva) bienvenidaGrandeActiva.hidden = false;
      } catch {
        // Si falla la renderización, la vista queda en estado seguro y no bloquea el login.
      }
    };

    try {
      obtenerBienvenidaSalas(conversacionId)
        .then((resultado) => {
          try {
            if (!resultado || mensajes.length) return;
            const textoOriginal = String(resultado.mensaje || resultado.respuesta || "Hola. ¿Qué sala quieres visitar hoy?");
            const salaActiva = salaActual || (leerSalaPreferida() ? normalizarObjetoSala(leerSalaPreferida()) : null);
            let textoBienvenida = textoOriginal;
            if (salaActiva && /¿Qu[eé] sala quieres visitar hoy\?/i.test(textoOriginal)) {
              textoBienvenida = construirTextoBienvenidaConSala(textoOriginal, salaActiva, usuarioActual);
            }
            const opciones = Array.isArray(resultado.salas_opciones)
              ? resultado.salas_opciones
              : Array.isArray(resultado.salas)
                ? resultado.salas
                : [];
            const resultadoObj = {
              ...resultado,
              bienvenida: true,
              respuesta: textoBienvenida,
              mensaje: textoBienvenida,
              salas_opciones: opciones,
            };
            delete resultadoObj.sala;
            const mensaje = {
              tipo: "agente",
              resultado: resultadoObj,
              textoUsuario: "",
              autoReproducir: false,
            };
            const agente = renderizarAgente(mensaje.resultado, mensaje.textoUsuario, mensaje.voz, mensaje.autoReproducir, null, mensaje);
            const bannerVigente = contenedor.querySelector("[data-bienvenida-salas]");
            if (bannerVigente) bannerVigente.remove();
            agente.dataset.bienvenidaSalas = "true";
            insertarMensaje(agente);
          } catch {
            fallback();
          }
        })
        .catch(() => fallback());
    } catch {
      fallback();
    }
  }

  async function asegurarBienvenidaSalas() {
    const ultimo = mensajes[mensajes.length - 1];
    if (ultimo && ultimo.tipo === "agente") {
      const res = ultimo.resultado;
      const texto = String(res?.respuesta || res?.mensaje || "");
      if (res?.bienvenida || /¿Qu[eé] sala quieres visitar hoy\?/i.test(texto) || /Sigues en la /i.test(texto)) {
        return false;
      }
    }

    try {
      const resultado = await obtenerBienvenidaSalas(conversacionId);
      if (resultado?.conversacion_id) {
        guardarConversacion(resultado.conversacion_id);
      }
      const nombreUsuario = usuarioActual?.nombre;
      const salaActiva = salaActual || (leerSalaPreferida() ? normalizarObjetoSala(leerSalaPreferida()) : null);
      let textoBienvenida = String(
        resultado?.mensaje ||
        resultado?.respuesta ||
        (nombreUsuario ? `Hola, ${nombreUsuario}. ¿Qué sala quieres visitar hoy?` : "Hola. ¿Qué sala quieres visitar hoy?")
      );
      if (salaActiva && /¿Qu[eé] sala quieres visitar hoy\?/i.test(textoBienvenida)) {
        textoBienvenida = construirTextoBienvenidaConSala(textoBienvenida, salaActiva, usuarioActual);
      }
      const opciones = Array.isArray(resultado?.salas_opciones)
        ? resultado.salas_opciones
        : Array.isArray(resultado?.salas)
          ? resultado.salas
          : [];

      const resultadoObj = {
        ...resultado,
        bienvenida: true,
        respuesta: textoBienvenida,
        mensaje: textoBienvenida,
        salas_opciones: opciones,
      };
      delete resultadoObj.sala;

      mensajes.push({
        tipo: "agente",
        resultado: resultadoObj,
        textoUsuario: "",
        autoReproducir: false,
        hora: horaActual(),
      });
      if (botonBorrarChat) botonBorrarChat.hidden = !usuarioActual;
      renderizar();
      return true;
    } catch {
      const nombreUsuario = usuarioActual?.nombre;
      let textoBienvenida = nombreUsuario
        ? `Hola, ${nombreUsuario}. ¿Qué sala quieres visitar hoy?`
        : "Hola. ¿Qué sala quieres visitar hoy?";
      const salaActiva = salaActual || (leerSalaPreferida() ? normalizarObjetoSala(leerSalaPreferida()) : null);
      if (salaActiva) {
        textoBienvenida = construirTextoBienvenidaConSala(textoBienvenida, salaActiva, usuarioActual);
      }
      mensajes.push({
        tipo: "agente",
        resultado: {
          bienvenida: true,
          respuesta: textoBienvenida,
          mensaje: textoBienvenida,
          salas_opciones: [],
        },
        textoUsuario: "",
        autoReproducir: false,
        hora: horaActual(),
      });
      if (botonBorrarChat) botonBorrarChat.hidden = !usuarioActual;
      renderizar();
      return true;
    }
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

  let vitrinaDatos = null;

  function renderTarjetaVitrina(material) {
    const card = elemento("article", `libro-3d ${material.tipo === "tesis" ? "libro-3d--tesis" : ""}`);
    card.tabIndex = 0;
    card.setAttribute("aria-label", `Material destacado: ${material.titulo || "Sin título"}`);
    const top = elemento("div", "libro-3d__top");
    top.append(
      elemento("span", "", material.tipo === "tesis" ? "🎓 Tesis Putumayo" : "📘 Libro"),
      elemento("span", "", `${Number(material.disponibles) || 0}/${Number(material.total) || 0} disp.`),
    );
    const h4 = elemento("h4", "libro-3d__titulo", material.titulo || "Material");
    const autor = elemento("p", "libro-3d__autor", [material.autor, material.anio].filter(Boolean).join(" · "));
    const acciones = elemento("div", "libro-3d__acciones");
    const btnResumen = boton("🔊 Resumen", "", "btn btn--primario");
    btnResumen.addEventListener("click", (evento) => {
      evento.stopPropagation();
      leyendoVoz = true;
      enviarTexto(`¿De qué trata «${material.titulo}»?`);
    });
    const btnPregunta = boton("💬 Preguntar", "", "btn btn--fantasma");
    btnPregunta.addEventListener("click", (evento) => {
      evento.stopPropagation();
      enviarTexto(`¿Qué sabes sobre «${material.titulo}»?`);
    });
    const btnMapa = boton("⌖ Mapa", "", "btn btn--fantasma");
    btnMapa.addEventListener("click", async (evento) => {
      evento.stopPropagation();
      await opciones.navegar?.("mapa");
      opciones.resaltarMaterial?.(material.material_id);
    });
    const abrirFicha = () => {
      const texto = material.titulo ? `¿Qué puedes decirme sobre «${material.titulo}»?` : "Muéstrame más información de este material.";
      enviarTexto(texto);
    };
    card.addEventListener("click", abrirFicha);
    card.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        abrirFicha();
      }
    });
    acciones.append(btnResumen, btnPregunta, btnMapa);
    card.append(top, h4, autor, acciones);
    return card;
  }

  function bienvenida() {
    if (escenaControlador) {
      escenaControlador.destruir();
      escenaControlador = null;
    }
    const section = elemento("section", "bienvenida");
    section.setAttribute("aria-labelledby", "bienvenida-titulo");

    const contenedorEscena = elemento("div", "bienvenida__escena");
    const saludoInicial = salaActual
      ? construirTextoBienvenidaConSala("¿Qué sala quieres visitar hoy?", salaActual, usuarioActual)
      : (usuarioActual?.nombre
        ? `Hola, ${usuarioActual.nombre}. ¿Qué sala quieres visitar hoy?`
        : "Hola. ¿Qué quieres explorar hoy?");
    escenaControlador = montarEscenaBiblioteca(contenedorEscena, {
      nombre: usuarioActual?.nombre || null,
      saludo: saludoInicial,
    });

    montarMenuSalas({
      contenedor: contenedorEscena,
      salaActual,
      compacto: true,
      alElegir: (salaElegida, textoMensaje) => {
        const texto = textoMensaje || textoEleccionSala(salaElegida);
        actualizarSalaActual(salaElegida || null, { guardar: true });
        enviarTexto(texto);
      },
    });

    section.append(contenedorEscena);

    const hero = elemento("div", "bienvenida__hero");
    const heroTexto = elemento("div", "bienvenida__hero-texto");
    const sello = elemento("span", "bienvenida__sello");
    sello.append(elemento("span", "bienvenida__sello-punto"), elemento("span", "", "Sistema Experto + RAG Semántico Activo"));
    const encabezado = elemento("h2", "", "¿Qué quieres explorar o investigar hoy?");
    encabezado.id = "bienvenida-titulo";
    heroTexto.append(
      sello,
      encabezado,
      elemento("p", "", "Habla con tu voz, explora libros y tesis en vivo y revisa reglas de préstamo con ayuda del bibliotecario correcto."),
    );
    const microfonoGrande = boton("", microfono, "microfono-grande", "Hablar con el agente");
    microfonoGrande.dataset.accionMicrofono = "";
    hero.append(heroTexto, microfonoGrande);
    section.append(hero);

    const tablero = elemento("div", "tablero-vivo");
    tablero.setAttribute("aria-label", "Tablero vivo del servicio bibliotecario");
    const metricas = elemento("div", "bienvenida__metricas tablero-vivo__estadisticas");
    const crearMetrica = (valor, texto) => {
      const m = elemento("div", "bienvenida__metrica");
      const fuerte = elemento("strong", "", valor ?? "No disponible");
      m.append(fuerte, elemento("span", "", texto));
      return m;
    };
    const totalCatalogo = crearMetrica("No disponible", "Catálogo activo");
    const totalProgramas = crearMetrica("No disponible", "Programas");
    const totalBitacora = crearMetrica("No disponible", "Bitácora");
    const totalMapa = crearMetrica("No disponible", "Mapa del conocimiento");
    metricas.append(totalCatalogo, totalProgramas, totalBitacora, totalMapa);
    tablero.append(metricas);

    const pildoras = elemento("div", "tablero-pildoras");
    const reglaPildora = (texto, pregunta) => {
      const botonPildora = elemento("button", "tablero-pildora");
      botonPildora.type = "button";
      botonPildora.setAttribute("aria-label", texto);
      botonPildora.textContent = texto;
      botonPildora.addEventListener("click", () => enviarTexto(pregunta));
      return botonPildora;
    };
    pildoras.append(
      reglaPildora("Préstamo: 8 días", "¿Cuánto tiempo puedo tener un libro prestado?"),
      reglaPildora("Renovación: máximo 3", "¿Cuántas renovaciones me permite el reglamento?"),
      reglaPildora("Multa: $1.000/día", "¿Cuánto me cuesta una multa por retraso?"),
      reglaPildora("Reserva: 48 h", "¿Cuánto dura una reserva?"),
      reglaPildora("No se presta con multas", "¿Qué pasa si tengo multas pendientes?"),
    );
    tablero.append(pildoras);
    section.append(tablero);

    const cargarMetricasTablero = async () => {
      const solicitudes = await Promise.all([
        fetch("/api/catalogo?limite=1").then((respuesta) => (respuesta.ok ? respuesta.json() : null)).catch(() => null),
        fetch("/api/programas").then((respuesta) => (respuesta.ok ? respuesta.json() : null)).catch(() => null),
        fetch("/api/bitacora?limite=20").then((respuesta) => (respuesta.ok ? respuesta.json() : null)).catch(() => null),
        fetch("/api/mapa").then((respuesta) => (respuesta.ok ? respuesta.json() : null)).catch(() => null),
      ]);
      const [catalogo, programas, bitacora, mapa] = solicitudes;
      const formatear = (valor, unidad = "") => {
        if (valor == null || valor === "") return "No disponible";
        const numero = Number(valor);
        if (Number.isFinite(numero)) return `${numero.toLocaleString("es-CO")}${unidad ? ` ${unidad}` : ""}`;
        return String(valor);
      };
      totalCatalogo.querySelector("strong").textContent = catalogo?.total != null ? formatear(catalogo.total, "materiales") : "No disponible";
      totalProgramas.querySelector("strong").textContent = Array.isArray(programas?.programas) ? formatear(programas.programas.length, "programas") : "No disponible";
      totalBitacora.querySelector("strong").textContent = Array.isArray(bitacora?.resultados) ? formatear(bitacora.resultados.length, "interacciones") : "No disponible";
      totalMapa.querySelector("strong").textContent = Array.isArray(mapa?.puntos) ? formatear(mapa.puntos.length, "puntos") : "No disponible";
    };
    cargarMetricasTablero();

    const vitrina = elemento("div", "vitrina-viva");
    const vitrinaCab = elemento("div", "vitrina-viva__cabecera");
    vitrinaCab.append(elemento("h3", "", "✨ Estantería interactiva en vivo"));
    const filtros = elemento("div", "vitrina-viva__filtros");
    const carrusel = elemento("div", "vitrina-viva__carrusel");
    [
      ["", "Todo"],
      ["libro", "Libros"],
      ["tesis", "Tesis Regionales"],
    ].forEach(([tipoFiltro, etiqueta], idx) => {
      const f = elemento("button", "vitrina-viva__filtro", etiqueta);
      f.type = "button";
      f.setAttribute("aria-pressed", String(idx === 0));
      f.addEventListener("click", () => {
        filtros.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", "false"));
        f.setAttribute("aria-pressed", "true");
        const lista = (vitrinaDatos?.resultados || []).filter((m) => !tipoFiltro || m.tipo === tipoFiltro).slice(0, 10);
        carrusel.replaceChildren(...lista.map(renderTarjetaVitrina));
      });
      filtros.append(f);
    });
    vitrinaCab.append(filtros);
    vitrina.append(vitrinaCab, carrusel);
    section.append(vitrina);

    if (vitrinaDatos) {
      carrusel.replaceChildren(...(vitrinaDatos.resultados || []).slice(0, 10).map(renderTarjetaVitrina));
    } else {
      obtenerCatalogo({ limite: 16 }).then((datos) => {
        vitrinaDatos = datos;
        if ( datos?.estadisticas && metricas.isConnected ) {
          metricas.replaceChildren(
            crearMetrica(String(datos.estadisticas.materiales ?? 56), "Títulos en acervo"),
            crearMetrica(String(datos.estadisticas.disponibles ?? 80), "Ejemplares libres"),
            crearMetrica(String(datos.estadisticas.tesis ?? 6), "Tesis del Putumayo"),
            crearMetrica("10", "Reglas y Herramientas"),
          );
        }
        if (carrusel.isConnected) {
          carrusel.replaceChildren(...(datos.resultados || []).slice(0, 10).map(renderTarjetaVitrina));
        }
      }).catch(() => {});
    }

    const rejilla = elemento("div", "sugerencias");
    sugerencias.forEach(([icono, texto]) => {
      const propuesta = boton(texto, iconos[icono] || "", "sugerencia");
      propuesta.addEventListener("click", () => enviarTexto(texto));
      rejilla.append(propuesta);
    });
    section.append(rejilla);

    const accesoInvestigacion = elemento("a", "acceso-investigacion");
    accesoInvestigacion.href = "#investigacion";
    const iconoAcceso = elemento("span", "acceso-investigacion__icono");
    iconoAcceso.setAttribute("aria-hidden", "true");
    iconoAcceso.innerHTML = iconos.investigar || "";
    const textoAcceso = elemento("span", "acceso-investigacion__texto");
    textoAcceso.append(
      elemento("strong", "", "¿Tienes un trabajo de investigación?"),
      elemento("span", "", "Abre el Asistente de investigación: libros, tesis, fragmentos y citas APA para tu tema."),
    );
    const flechaAcceso = elemento("span", "acceso-investigacion__flecha", "→");
    flechaAcceso.setAttribute("aria-hidden", "true");
    accesoInvestigacion.append(iconoAcceso, textoAcceso, flechaAcceso);
    section.append(accesoInvestigacion);
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
    if (usuario) {
      if (conversacionId) {
        try {
          await adoptarConversacion(conversacionId);
        } catch {
          // Si ya pertenecía o no se pudo adoptar, se conserva la conversación
        }
      }
      actualizarUsuario(usuario);
    }
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
        const vozActual = obtenerPreferenciaVoz().voz_id;
        let base64 = resultado.voz_id === vozActual ? resultado.audio_wav_base64 : null;
        if (!base64) {
          const audio = await sintetizar(resultado.respuesta_voz || resultado.respuesta || "");
          if (obtenerPreferenciaVoz().voz_id !== vozActual) return;
          base64 = audio.audio_wav_base64;
          resultado.audio_wav_base64 = base64;
          resultado.voz_id = audio.voz_id || vozActual;
          resultado.aviso = audio.aviso;
          if (audio.aviso) contenido.append(elemento("span", "texto-sec", audio.aviso));
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

  function explicarRegla(regla) {
    const texto = String(regla || "").trim();
    if (!texto) return "¿Me explicas la regla del reglamento?";
    const clave = texto.toLocaleLowerCase("es");
    if (clave.includes("prestamo") || clave.includes("préstamo") || clave.includes("prestamos")) {
      return "Explícame la regla del reglamento sobre préstamos y plazos.";
    }
    if (clave.includes("multa") || clave.includes("multa")) {
      return "Explica la regla del reglamento sobre multas y sanciones.";
    }
    if (clave.includes("reserva") || clave.includes("reservas")) {
      return "Explica la regla del reglamento sobre reservas y renovación.";
    }
    return `Explica la regla del reglamento sobre ${texto}.`;
  }

  function crearPildoraRegla(mensaje, pregunta) {
    const pildora = elemento("button", "pildora-regla");
    pildora.type = "button";
    pildora.setAttribute("aria-label", mensaje);
    pildora.textContent = mensaje;
    pildora.addEventListener("click", () => {
      enviarTexto(pregunta || explicarRegla(mensaje));
    });
    return pildora;
  }

  function construirFuentesCompactas(resultado) {
    const fuentes = Array.isArray(resultado?.fuentes) ? resultado.fuentes : [];
    const elegibles = fuentes.filter((fuente) => fuente && (fuente.documento || fuente.seccion)).slice(0, 5);
    if (!elegibles.length) return null;
    const bloque = elemento("div", "detalles-tecnicos__bloque");
    bloque.append(elemento("p", "detalles-tecnicos__titulo", "Fuentes consultadas"));
    const lista = elemento("ul", "detalles-tecnicos__lista");
    elegibles.forEach((fuente) => {
      const item = elemento("li", "detalles-tecnicos__item");
      const titulo = nombreFuente(fuente.documento || "Documento");
      const seccion = fuente.seccion ? ` · ${fuente.seccion}` : "";
      const similitud = fuente.similitud != null ? ` · ${Math.round(Number(fuente.similitud) * 100)} %` : "";
      item.textContent = `${titulo}${seccion}${similitud}`;
      lista.append(item);
    });
    bloque.append(lista);
    return bloque;
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

    const esRespuestaEnVivo = Boolean(
      resultado?.enVivo
      && !resultado?.bienvenida
      && resultado?.herramienta !== "historial_restaurado"
    );

    if (resultado?.enVivo) {
      resultado.enVivo = false;
    }

    if (!resultado.bienvenida && resultado.herramienta !== "historial_restaurado") {
      if (resultado.sala !== undefined && resultado.sala !== null) {
        actualizarSalaActual(resultado.sala, { guardar: true });
      } else if (resultado.sala === null && esRespuestaEnVivo) {
        actualizarSalaActual(null, { guardar: true });
      }
    }

    if (resultado.bienvenida || (resultado.sesion_iniciada && !resultado.accion_pendiente)) {
      let respuesta = resultado.respuesta || "Hola. ¿Qué quieres explorar hoy?";
      const salaActiva = salaActual || (leerSalaPreferida() ? normalizarObjetoSala(leerSalaPreferida()) : null);
      if (salaActiva && /¿Qu[eé] sala quieres visitar hoy\?/i.test(respuesta)) {
        respuesta = construirTextoBienvenidaConSala(respuesta, salaActiva, usuarioActual);
      }
      contenido.append(elemento("p", "mensaje__texto", respuesta));
      if (resultado.aviso) contenido.append(elemento("p", "texto-sec", resultado.aviso));
      const menuSalas = elemento("div", "mensaje__herramientas");
      montarMenuSalas({
        contenedor: menuSalas,
        salas: Array.isArray(resultado.salas_opciones) && resultado.salas_opciones.length ? resultado.salas_opciones : null,
        salaActual: salaActiva,
        compacto: true,
        alElegir: (salaElegida, textoMensaje) => {
          const texto = textoMensaje || textoEleccionSala(salaElegida);
          actualizarSalaActual(salaElegida || null, { guardar: true });
          enviarTexto(texto);
        },
      });
      contenido.append(menuSalas);
      if (resultado.sugerencia_sala) {
        const sugerencia = resultado.sugerencia_sala;
        const botonSala = boton(`Ir a la ${sugerencia.nombre || "Sala"}`, "", "btn btn--fantasma", `Ir a la ${sugerencia.nombre || "sala"}`);
        botonSala.addEventListener("click", () => {
          const texto = textoEleccionSala({ slug: sugerencia.slug, nombre: sugerencia.nombre, nombre_corto: sugerencia.nombre });
          actualizarSalaActual({ slug: sugerencia.slug, nombre: sugerencia.nombre, nombre_corto: sugerencia.nombre }, { guardar: true });
          enviarTexto(texto);
        });
        const fila = elemento("div", "mensaje__herramientas");
        fila.append(botonSala);
        contenido.append(fila);
      }
      tarjetaAvisos(resultado, contenido);
      const barraBienvenida = elemento("div", "mensaje__herramientas");
      reproducirEnTarjeta(barraBienvenida, resultado);
      contenido.append(barraBienvenida);
      item.append(avatar, contenido);
      if (autoReproducir && resultado.audio_wav_base64) {
        if (registro) registro.autoReproducir = false;
        ultimaReproduccion = reproducirRespuesta(contenido, resultado.audio_wav_base64, resultado.respuesta_voz || resultado.respuesta || "");
      }
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

    if (resultado.aviso) contenido.append(elemento("p", "texto-sec", resultado.aviso));
    if (Array.isArray(resultado.salas_opciones) && resultado.salas_opciones.length) {
      const menuSalas = elemento("div", "mensaje__herramientas");
      montarMenuSalas({
        contenedor: menuSalas,
        salas: resultado.salas_opciones,
        salaActual,
        compacto: true,
        alElegir: (salaElegida, textoMensaje) => {
          const texto = textoMensaje || textoEleccionSala(salaElegida);
          actualizarSalaActual(salaElegida || null, { guardar: true });
          enviarTexto(texto);
        },
      });
      contenido.append(menuSalas);
    }
    if (resultado.sugerencia_sala) {
      const sugerencia = resultado.sugerencia_sala;
      const botonSala = boton(`Ir a la ${sugerencia.nombre || "Sala"}`, "", "btn btn--fantasma", `Ir a la ${sugerencia.nombre || "sala"}`);
      botonSala.addEventListener("click", () => {
        const texto = textoEleccionSala({ slug: sugerencia.slug, nombre: sugerencia.nombre, nombre_corto: sugerencia.nombre });
        actualizarSalaActual({ slug: sugerencia.slug, nombre: sugerencia.nombre, nombre_corto: sugerencia.nombre }, { guardar: true });
        enviarTexto(texto);
      });
      const fila = elemento("div", "mensaje__herramientas");
      fila.append(botonSala);
      contenido.append(fila);
    }
    fuentesPara(resultado, contenido);
    if (resultado.bibliografia) contenido.append(renderBibliografia(resultado.bibliografia));

    const pildoras = elemento("div", "reglas-expertas");
    if (resultado.intencion || resultado.herramienta) {
      const motor = crearPildoraRegla(
        `⚙ ${resultado.herramienta || resultado.intencion}`,
        `¿Qué significa la regla del motor experto para ${resultado.intencion || resultado.herramienta}?`,
      );
      pildoras.append(motor);
    }
    if (Array.isArray(resultado.fuentes) && resultado.fuentes.length) {
      const rag = crearPildoraRegla(
        `📚 RAG: ${resultado.fuentes.length} ${resultado.fuentes.length === 1 ? "evidencia" : "evidencias"}`,
        "Muéstrame las evidencias que sustentan esta respuesta.",
      );
      pildoras.append(rag);
    }
    if (resultado.accion_pendiente) {
      pildoras.append(crearPildoraRegla("🛡 Confirmación en 2 pasos", "¿Cómo funciona la confirmación de reserva y renovación?"));
    }
    if (resultado.tiempos?.t_total_ms != null) {
      pildoras.append(crearPildoraRegla(`⚡ ${Math.round(Number(resultado.tiempos.t_total_ms))} ms`, "¿Cuánto tarda esta respuesta en total?"));
    }
    if (resultado.intencion && resultado.intencion.toLowerCase().includes("regla")) {
      pildoras.append(crearPildoraRegla("📘 Reglamentos", "¿Me explicas la regla del reglamento aplicable?"));
    }
    if (resultado.herramienta && resultado.herramienta.toLowerCase().includes("prestamo")) {
      pildoras.append(crearPildoraRegla("📆 Préstamos", "Explica la regla del reglamento sobre préstamos."));
    }
    if (pildoras.childElementCount) contenido.append(pildoras);

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
    const fuentesCompactas = construirFuentesCompactas(resultado);
    if (fuentesCompactas) detalles.append(fuentesCompactas);
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
      mostrarBienvenidaSalas();
      return;
    }
    if (escenaControlador) {
      escenaControlador.destruir();
      escenaControlador = null;
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

  function crearTrazabilidadViva(conAudio = false) {
    const pasos = [
      "1. Interpretando intención y contexto de la sesión",
      "2. Evaluando reglas expertas y consultando vectores (pgvector)",
      conAudio ? "3. Redactando respuesta y sintetizando voz neuronal" : "3. Redactando respuesta verificada con fuentes",
    ];
    const caja = elemento("div", "inferencia-viva");
    const nodos = pasos.map((textoPaso, idx) => {
      const fila = elemento("div", `inferencia-viva__paso ${idx === 0 ? "inferencia-viva__paso--activo" : ""}`);
      fila.append(elemento("span", "inferencia-viva__punto"), elemento("span", "", textoPaso));
      caja.append(fila);
      return fila;
    });
    const actualizar = (segundos) => {
      const indiceActivo = segundos < 1.2 ? 0 : segundos < 3.2 ? 1 : 2;
      nodos.forEach((nodo, idx) => {
        nodo.classList.toggle("inferencia-viva__paso--listo", idx < indiceActivo);
        nodo.classList.toggle("inferencia-viva__paso--activo", idx === indiceActivo);
      });
    };
    return { caja, actualizar };
  }

  function mostrarEtapa(etapa, voz, tiempo, conAudio, trazabilidad) {
    if (!etapa.isConnected) return;
    const segundos = (Date.now() - tiempo) / 1000;
    let texto;
    if (voz && segundos < 2) texto = "Transcribiendo tu voz…";
    else if (segundos < 2.5 || voz && segundos < 4.5) texto = "Buscando en el catálogo…";
    else if (conAudio && segundos > 6) texto = "Preparando la voz…";
    else texto = "Escribiendo la respuesta…";
    etapa.textContent = texto;
    trazabilidad?.actualizar(segundos);
  }

  async function procesarMensaje(texto, forzarAudio, entradaOculta = false, escenaVisible = false) {
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
    const conAudio = forzarAudio ?? leyendoVoz;
    const trazabilidad = crearTrazabilidadViva(conAudio);
    tarjeta.append(pensando, estado, trazabilidad.caja);
    espera.append(avatar, tarjeta);
    if (!escenaVisible) {
      mensajesNodo.append(espera);
    }
    const inicio = Date.now();
    let intervaloEtapa = null;
    const refrescarEtapa = () => {
      if (document.hidden) return;
      mostrarEtapa(estado, false, inicio, conAudio, trazabilidad);
    };
    const iniciarEtapa = () => {
      if (document.hidden) return;
      intervaloEtapa ??= window.setInterval(refrescarEtapa, 350);
    };
    const detenerEtapa = () => {
      if (intervaloEtapa) {
        window.clearInterval(intervaloEtapa);
        intervaloEtapa = null;
      }
    };
    document.addEventListener("visibilitychange", refrescarEtapa, { once: false });
    iniciarEtapa();
    refrescarEtapa();
    if (!escenaVisible) {
      desplazarAbajo();
    }
    try {
      const resultado = await enviarChat(texto, conversacionId, conAudio);
      if (generacionSolicitud !== generacion) {
        if (escenaVisible && escenaControlador) escenaControlador.pensar(false);
        return null;
      }
      detenerEtapa();
      document.removeEventListener("visibilitychange", refrescarEtapa);
      if (!escenaVisible) espera.remove();
      if (escenaVisible && escenaControlador) {
        escenaControlador.pensar(false);
      }
      guardarConversacion(resultado.conversacion_id);
      if (entradaOculta || resultado.entrada_oculta) {
        const usuario = mensajes.findLast?.((mensaje) => mensaje.tipo === "usuario");
        if (usuario) usuario.texto = "PIN enviado ••••";
      }
      if (resultado.esperando === "pin") establecerModoEntrada("pin");
      else establecerModoEntrada("normal", resultado.esperando === "codigo");
      const vozAutomatica = Boolean(resultado.audio_wav_base64 && conAudio);
      const textoSeguro = entradaOculta || resultado.entrada_oculta ? "" : texto;
      resultado.enVivo = true;
      mensajes.push({ tipo: "agente", resultado, textoUsuario: textoSeguro, autoReproducir: vozAutomatica });
      renderizar();
      if (resultado.sesion_iniciada) await sincronizarSesion(resultado);
      else if (resultado.usuario) actualizarUsuario(resultado.usuario);
      return resultado;
    } catch {
      if (generacionSolicitud !== generacion) {
        if (escenaVisible && escenaControlador) escenaControlador.pensar(false);
        return null;
      }
      detenerEtapa();
      document.removeEventListener("visibilitychange", refrescarEtapa);
      if (!escenaVisible) espera.remove();
      if (escenaVisible && escenaControlador) {
        escenaControlador.pensar(false);
      }
      mensajes.push({
        tipo: "error",
        texto: "No pudimos conectar con el agente. Revisa tu conexión e inténtalo de nuevo.",
        reintentar: entradaOculta ? "" : texto,
      });
      renderizar();
      return null;
    } finally {
      detenerEtapa();
      document.removeEventListener("visibilitychange", refrescarEtapa);
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
    const escenaVisible = Boolean(escenaControlador && !mensajes.length);
    if (escenaVisible) {
      escenaControlador.pensar(true);
    }
    mensajes.push({
      tipo: "usuario",
      texto: entradaOculta ? "PIN enviado ••••" : mensaje,
      hora: horaActual(),
      voz: false,
    });
    if (!escenaVisible) {
      renderizar();
    }
    await procesarMensaje(mensaje, undefined, entradaOculta, escenaVisible);
  }

  function mostrarTranscripcion(texto) {
    esperaVoz?.remove();
    esperaVoz = null;
    const escenaVisible = Boolean(escenaControlador && !mensajes.length);
    if (escenaVisible) {
      escenaControlador.pensar(true);
    }
    mensajes.push({ tipo: "usuario", texto, hora: horaActual(), voz: true });
    if (!escenaVisible) {
      renderizar();
    }
  }

  async function recibirVoz(resultado, transcripcion, alHablar, vigente = () => true) {
    const generacionSolicitud = generacion;
    if (escenaControlador) {
      escenaControlador.pensar(false);
    }
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
    resultado.enVivo = true;
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
        const vozSolicitada = obtenerPreferenciaVoz().voz_id;
        const audio = await sintetizar(resultado.respuesta_voz || resultado.respuesta);
        if (generacionSolicitud !== generacion || !vigente()
          || obtenerPreferenciaVoz().voz_id !== vozSolicitada) return null;
        if (audio.audio_wav_base64) {
          resultado.audio_wav_base64 = audio.audio_wav_base64;
          resultado.voz_id = audio.voz_id;
          resultado.voz_usada = audio.voz_usada;
          resultado.aviso = audio.aviso;
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
    if (escenaControlador && !mensajes.length) {
      escenaControlador.pensar(true);
      return;
    }
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
    sincronizarSalaDesdeStorage();
    actualizarUsuario(usuarioActual, !usuarioActual);
    try {
      sessionStorage.removeItem("biblioteca-conversacion-id");
    } catch {
      // La conversación nueva funciona aunque no se pueda limpiar el almacenamiento.
    }
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
    const texto = String(mensaje ?? "").trim();
    aviso.textContent = texto;
    aviso.hidden = !texto;
  }

  function establecerPreferencias({ voz: vozActiva } = {}) {
    leyendoVoz = Boolean(vozActiva);
  }

  function leerUltimaRespuesta() {
    const botones = mensajesNodo.querySelectorAll(".mensaje--agente .mensaje__herramientas > button:first-child");
    const ultimoBoton = botones[botones.length - 1];
    if (ultimoBoton) {
      ultimoBoton.click();
      return true;
    }
    return false;
  }

  sincronizarSalaDesdeStorage();
  actualizarUsuario(null, true);
  renderizar();
  return {
    enviarTexto,
    establecerAvisoServicios,
    establecerPreferencias,
    leerUltimaRespuesta,
    obtenerConversacionId: () => conversacionId,
    obtenerUsuario: () => usuarioActual,
    tieneMensajes: () => mensajes.length > 0,
    establecerIdentidad: (usuario, invitado = false) => {
      try {
        sincronizarSalaDesdeStorage();
        actualizarUsuario(usuario, invitado);
      } catch (error) {
        console.warn("Error al establecer identidad:", error);
      }
    },
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
          if (mensaje.rol === "user") {
            mensajes.push({ tipo: "usuario", texto: mensaje.contenido, hora, voz: false });
          } else if (mensaje.rol === "assistant") {
            const esBienvenida = /¿Qu[eé] sala quieres visitar hoy\?/i.test(mensaje.contenido || "") || /Sigues en la /i.test(mensaje.contenido || "");
            mensajes.push({
              tipo: "agente",
              resultado: {
                bienvenida: esBienvenida,
                respuesta: mensaje.contenido,
                respuesta_voz: mensaje.contenido,
                fuentes: [],
                materiales: [],
                herramienta: "historial_restaurado",
              },
              textoUsuario: "",
              hora,
            });
          }
        });
        if (botonBorrarChat) botonBorrarChat.hidden = false;
        renderizar();
        return mensajes.length > 0;
      } catch {
        return false;
      }
    },
    asegurarBienvenidaSalas,
    mostrarBienvenidaSalas,
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
      try {
        llamada.terminar("");
        conversacionId = null;
        establecerModoEntrada("normal");
        ultimoTextoRequiereLogin = "";
        sincronizarSalaDesdeStorage();
        actualizarUsuario(null, true);
        try {
          sessionStorage.removeItem("biblioteca-conversacion-id");
        } catch {
          // El estado de la sesión también queda limpio en memoria.
        }
      } catch (error) {
        console.warn("Error al restablecer identidad:", error);
      }
    },
    limpiar: () => {
      try {
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
        sincronizarSalaDesdeStorage();
        renderizar();
      } catch (error) {
        console.warn("Error al limpiar:", error);
      }
    },
  };
}
