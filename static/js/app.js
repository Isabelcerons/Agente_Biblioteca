import { iconos } from "./iconos.js";
import { iniciarTema } from "./tema.js";
import { montarChat } from "./chat.js";
import { montarCuenta } from "./cuenta.js";
import { cancelarReserva, cerrarSesion, obtenerAvisosDisponibilidad } from "./api.js";
import { montarSesion } from "./sesion.js";
import { montarTesis } from "./tesis.js";

const raiz = document.querySelector(".app-shell");
const panelCuenta = document.querySelector("#panel-cuenta");
const contenidoCuenta = document.querySelector("#cuenta-contenido");
const overlayCuenta = document.querySelector("#cuenta-overlay");
const botonPlegarCuenta = document.querySelector("#plegar-cuenta");
const botonLeerVoz = document.querySelector("#leer-voz");
const botonMenuMovil = document.querySelector("#abrir-menu-movil");
const menuMovil = document.querySelector("#menu-movil");
const contenidoMenuMovil = document.querySelector("#contenido-menu-movil");
const vistas = new Map([...document.querySelectorAll("[data-contenedor-vista]")].map((vista) => [vista.dataset.contenedorVista, vista]));
const montadas = new Set();
const montadasPanel = new Set();
const promesasPanel = new Map();
const panelPestanas = [...document.querySelectorAll("[data-pestana-panel]")];
const panelContenidos = new Map([...document.querySelectorAll("[data-panel-contenido]")].map((nodo) => [nodo.dataset.panelContenido, nodo]));
const contenidoReservas = document.querySelector("#mis-reservas-contenido");
let instanciaMapa = null;
let cuenta = null;
let reservasVista = null;
let catalogoVista = null;
let promesaCatalogo = null;
let promesaReservas = null;
let chat = null;
let sesion = null;
let tesis = null;
let servicios = {};
let consultandoSalud = false;
let cuentaPlegada = cargarPreferencia("biblioteca-cuenta-plegada", true);
let usuarioIdentificadoActual = false;
let codigoAvisos = null;
let consultaAvisos = false;

async function actualizarAvisosDisponibilidad() {
  if (!codigoAvisos || consultaAvisos) return;
  const codigo = codigoAvisos;
  consultaAvisos = true;
  try {
    const datos = await obtenerAvisosDisponibilidad();
    if (codigo !== codigoAvisos) return;
    let aviso = document.querySelector("#avisos-disponibilidad");
    if (!aviso) {
      aviso = document.createElement("section");
      aviso.id = "avisos-disponibilidad";
      aviso.className = "aviso aviso--info";
      aviso.setAttribute("role", "status");
      document.querySelector(".chat-encabezado")?.after(aviso);
    }
    const listas = datos.listas_recoger || [];
    aviso.hidden = !listas.length;
    aviso.replaceChildren();
    if (listas.length) {
      const texto = document.createElement("p");
      texto.textContent = `Ya puedes recoger: ${listas.map((r) => `«${r.titulo}»`).join(", ")}. Consulta el plazo en Mis reservas y lleva tu carné.`;
      const enlace = document.createElement("a");
      enlace.href = "#mis-reservas";
      enlace.textContent = "Ver mis reservas";
      aviso.append(texto, enlace);
    }
  } catch {
    // La próxima comprobación reintenta sin interrumpir el chat.
  } finally {
    consultaAvisos = false;
  }
}
let cerrarMenuEnMovil = () => {};

const nombresVistas = {
  catalogo: "Catálogo",
  chat: "Conversar",
  "mis-reservas": "Mis reservas",
  panel: "Panel técnico",
  // La bibliografía no tiene vista propia: se pide desde el chat
  // ("dame 5 referencias en APA sobre cacao") y se muestra con botón Copiar.
};

function cargarPreferencia(clave, valorInicial) {
  try {
    const valor = localStorage.getItem(clave);
    return valor === null ? valorInicial : valor === "true";
  } catch {
    return valorInicial;
  }
}

function guardarPreferencia(clave, valor) {
  try {
    localStorage.setItem(clave, String(valor));
  } catch {
    // La preferencia se mantiene en memoria aunque el almacenamiento no esté disponible.
  }
}

function mostrarErrorVista(contenedor, mensaje) {
  let aviso = contenedor.querySelector("[data-error-vista]");
  if (!aviso) {
    aviso = document.createElement("div");
    aviso.className = "aviso aviso--error";
    aviso.dataset.errorVista = "";
    contenedor.append(aviso);
  }
  aviso.replaceChildren(document.createElement("span"), document.createElement("p"));
  aviso.firstElementChild.innerHTML = iconos.alerta;
  aviso.lastElementChild.textContent = mensaje;
}

function asegurarTitulo(vista, llave) {
  let encabezado = vista.querySelector("h1");
  if (!encabezado) {
    encabezado = document.createElement("h1");
    encabezado.className = "sr-only";
    encabezado.textContent = nombresVistas[llave];
    vista.prepend(encabezado);
  }
  encabezado.id = `titulo-${llave}`;
  encabezado.tabIndex = -1;
}

function actualizarNavegacion(activa) {
  document.querySelectorAll("[data-vista]").forEach((enlace) => {
    if (enlace.dataset.vista === activa) enlace.setAttribute("aria-current", "page");
    else enlace.removeAttribute("aria-current");
  });
}

function resolverRuta(valor = location.hash.slice(1)) {
  const ruta = String(valor || "chat").replace(/^#/, "");
  const aliasPanel = { mapa: "mapa", sql: "sql", bitacora: "bitacora" };
  if (aliasPanel[ruta]) return { vista: "panel", pestana: aliasPanel[ruta], hash: `panel/${aliasPanel[ruta]}` };
  if (ruta === "panel" || ruta.startsWith("panel/")) {
    const pestana = ruta.split("/")[1];
    const valida = panelContenidos.has(pestana) ? pestana : "mapa";
    return { vista: "panel", pestana: valida, hash: `panel/${valida}` };
  }
  if (ruta === "mis-reservas") return { vista: "mis-reservas", pestana: null, hash: ruta };
  if (ruta === "catalogo") return { vista: "catalogo", pestana: null, hash: ruta };
  if (ruta === "mi-cuenta") return { vista: "chat", pestana: null, hash: "chat", abrirCuenta: true };
  return { vista: "chat", pestana: null, hash: "chat" };
}

function actualizarPestanasPanel(activa) {
  panelPestanas.forEach((pestana) => {
    const seleccionada = pestana.dataset.pestanaPanel === activa;
    pestana.setAttribute("aria-selected", String(seleccionada));
    pestana.tabIndex = seleccionada ? 0 : -1;
    const panel = panelContenidos.get(pestana.dataset.pestanaPanel);
    if (panel) panel.hidden = !seleccionada;
  });
}

function navegarPestanaPanel(llave) {
  const pestana = panelPestanas.find((elemento) => elemento.dataset.pestanaPanel === llave);
  if (!pestana) return;
  location.hash = `panel/${llave}`;
  pestana.focus({ preventScroll: true });
}

panelPestanas.forEach((pestana, indice) => {
  pestana.addEventListener("click", () => navegarPestanaPanel(pestana.dataset.pestanaPanel));
  pestana.addEventListener("keydown", (evento) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(evento.key)) return;
    evento.preventDefault();
    const siguiente = evento.key === "Home" ? 0
      : evento.key === "End" ? panelPestanas.length - 1
        : (indice + (evento.key === "ArrowRight" ? 1 : -1) + panelPestanas.length) % panelPestanas.length;
    navegarPestanaPanel(panelPestanas[siguiente].dataset.pestanaPanel);
  });
});

async function montarPestanaPanel(llave) {
  if (montadasPanel.has(llave)) return;
  if (promesasPanel.has(llave)) return promesasPanel.get(llave);
  const contenedor = panelContenidos.get(llave);
  const tarea = (async () => {
    try {
      if (llave === "mapa") {
        const modulo = await import("./mapa.js");
        instanciaMapa = await modulo.montarMapa(contenedor);
      } else if (llave === "sql") {
        const modulo = await import("./vistas/sql_vs_pgvector.js");
        await modulo.montarDemo(contenedor);
      } else if (llave === "bitacora") {
        const modulo = await import("./vistas/bitacora.js");
        await modulo.montarBitacora(contenedor);
      }
      montadasPanel.add(llave);
      contenedor.querySelector("[data-error-vista]")?.remove();
    } catch {
      mostrarErrorVista(contenedor, `No fue posible cargar ${llave === "mapa" ? "el mapa del conocimiento" : nombresVistas.panel.toLocaleLowerCase("es")}. Comprueba que la vista esté disponible e inténtalo más tarde.`);
    }
  })();
  promesasPanel.set(llave, tarea);
  await tarea;
  promesasPanel.delete(llave);
}

function mostrarReservasInvitado() {
  const mensaje = document.createElement("p");
  mensaje.className = "cuenta-vacia";
  mensaje.textContent = "Inicia sesión… para consultar tus reservas.";
  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = "btn btn--acento";
  boton.textContent = "Iniciar sesión";
  boton.addEventListener("click", () => sesion?.mostrarLogin());
  contenidoReservas.replaceChildren(mensaje, boton);
}

async function montarReservas() {
  if (!chat?.obtenerUsuario()) {
    mostrarReservasInvitado();
    return;
  }
  if (reservasVista) {
    await reservasVista.refrescar?.();
    return;
  }
  if (promesaReservas) return promesaReservas;
  promesaReservas = (async () => {
    try {
      const modulo = await import("./vistas/mis_reservas.js");
      reservasVista = await modulo.montarMisReservas(contenidoReservas);
      if (reservasVista?.refrescar) await reservasVista.refrescar();
      montadas.add("mis-reservas");
    } catch {
      mostrarErrorVista(contenidoReservas, "Mis reservas todavía no está disponible. Inténtalo de nuevo más tarde.");
    } finally {
      promesaReservas = null;
    }
  })();
  return promesaReservas;
}

async function montarCatalogo() {
  if (catalogoVista) return catalogoVista.refrescar();
  if (promesaCatalogo) return promesaCatalogo;
  promesaCatalogo = (async () => {
    try {
      const modulo = await import("./vistas/catalogo.js");
      catalogoVista = modulo.montarCatalogo(vistas.get("catalogo"));
      await catalogoVista.refrescar();
    } catch {
      mostrarErrorVista(vistas.get("catalogo"), "No se pudo abrir el catálogo. Vuelve a intentarlo.");
    } finally {
      promesaCatalogo = null;
    }
  })();
  return promesaCatalogo;
}

function cambiarVista(nombre, moverFoco = true) {
  const ruta = resolverRuta(nombre);
  const llave = ruta.vista;
  const vistaActiva = vistas.get(llave) || vistas.get("chat");
  vistas.forEach((vista, nombreVista) => {
    const activa = nombreVista === llave;
    vista.hidden = !activa;
    vista.classList.toggle("vista--activa", activa);
  });
  actualizarNavegacion(llave);
  if (llave === "panel") actualizarPestanasPanel(ruta.pestana);
  if (location.hash !== `#${ruta.hash}`) history.replaceState(null, "", `#${ruta.hash}`);
  if (ruta.abrirCuenta) abrirPanelCuenta();
  const montar = llave === "panel"
    ? montarPestanaPanel(ruta.pestana)
    : llave === "mis-reservas" ? montarReservas() : llave === "catalogo" ? montarCatalogo() : Promise.resolve();
  return montar.then(() => {
    asegurarTitulo(vistaActiva, llave);
    if (moverFoco) vistaActiva.querySelector("h1")?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
    if (llave === "panel" && ruta.pestana === "mapa") {
      window.requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
    }
  });
}

function resaltarMaterial(id) {
  if (typeof instanciaMapa?.resaltarMaterial === "function") instanciaMapa.resaltarMaterial(id);
}

function estaEnEscritorio() {
  return window.matchMedia("(min-width: 1100px)").matches;
}

function abrirPanelCuenta() {
  if (estaEnEscritorio()) {
    cuentaPlegada = false;
    guardarPreferencia("biblioteca-cuenta-plegada", false);
    raiz.classList.remove("app-shell--cuenta-plegada");
    botonPlegarCuenta.setAttribute("aria-expanded", "true");
    botonPlegarCuenta.setAttribute("aria-label", "Plegar panel Mi cuenta");
    return;
  }
  panelCuenta.classList.add("panel-cuenta--abierto");
  overlayCuenta.hidden = false;
  document.querySelector("#abrir-cuenta-movil")?.setAttribute("aria-expanded", "true");
  botonPlegarCuenta.setAttribute("aria-expanded", "true");
  botonPlegarCuenta.setAttribute("aria-label", "Cerrar panel Mi cuenta");
  panelCuenta.querySelector("h2")?.focus?.({ preventScroll: true });
}

function cerrarPanelCuenta() {
  panelCuenta.classList.remove("panel-cuenta--abierto");
  overlayCuenta.hidden = true;
  document.querySelector("#abrir-cuenta-movil")?.setAttribute("aria-expanded", "false");
  botonPlegarCuenta.setAttribute("aria-expanded", "false");
  botonPlegarCuenta.setAttribute("aria-label", estaEnEscritorio() ? "Desplegar panel Mi cuenta" : "Abrir panel Mi cuenta");
}

function configurarPanelCuenta() {
  const aplicarEstado = () => {
    if (estaEnEscritorio()) {
      panelCuenta.classList.remove("panel-cuenta--abierto");
      overlayCuenta.hidden = true;
      raiz.classList.toggle("app-shell--cuenta-plegada", cuentaPlegada);
      botonPlegarCuenta.setAttribute("aria-expanded", String(!cuentaPlegada));
      botonPlegarCuenta.setAttribute("aria-label", cuentaPlegada ? "Desplegar panel Mi cuenta" : "Plegar panel Mi cuenta");
    } else {
      raiz.classList.remove("app-shell--cuenta-plegada");
      if (!panelCuenta.classList.contains("panel-cuenta--abierto")) cerrarPanelCuenta();
      else overlayCuenta.hidden = false;
    }
  };
  botonPlegarCuenta.addEventListener("click", () => {
    if (estaEnEscritorio()) {
      cuentaPlegada = !cuentaPlegada;
      guardarPreferencia("biblioteca-cuenta-plegada", cuentaPlegada);
      aplicarEstado();
    } else if (panelCuenta.classList.contains("panel-cuenta--abierto")) cerrarPanelCuenta();
    else abrirPanelCuenta();
  });
  overlayCuenta.addEventListener("click", cerrarPanelCuenta);
  window.addEventListener("resize", aplicarEstado);
  aplicarEstado();
}

function actualizarServicios(datos = {}) {
  servicios = datos;
  document.querySelectorAll("[data-servicio]").forEach((nodo) => {
    const nombre = nodo.dataset.servicio;
    const conocido = typeof servicios[nombre] === "boolean";
    const disponible = servicios[nombre] === true;
    nodo.classList.toggle("servicio--ok", disponible);
    nodo.classList.toggle("servicio--error", conocido && !disponible);
    nodo.classList.toggle("servicio--espera", !conocido);
    const estado = !conocido ? "pendiente de comprobar" : disponible ? "disponible" : "no disponible";
    nodo.setAttribute("aria-label", `${nombre}: ${estado}`);
    nodo.title = `${nombre}: ${estado}`;
  });
  const avisos = [];
  if (servicios.ollama === false) avisos.push("Ollama no responde: las respuestas pueden fallar. Inicie Ollama.");
  if (servicios.postgresql === false) avisos.push("PostgreSQL no responde: las consultas al catálogo pueden fallar.");
  if (servicios.whisper === false) avisos.push("Whisper no responde: las consultas por voz pueden fallar.");
  if (servicios.piper === false) avisos.push("Piper no responde: no se podrán escuchar respuestas generadas.");
  chat?.establecerAvisoServicios(avisos.join(" "));
}

async function consultarSalud() {
  if (consultandoSalud) return;
  consultandoSalud = true;
  try {
    const respuesta = await (await import("./api.js")).obtenerSalud();
    actualizarServicios(respuesta.servicios || {});
  } catch {
    actualizarServicios({});
    chat?.establecerAvisoServicios("No se pudo comprobar la conexión con la aplicación. Reintentando en unos segundos…");
    window.setTimeout(consultarSalud, 5000);
  } finally {
    consultandoSalud = false;
  }
}

function inicializarPreferencias() {
  iniciarTema();
  let leerVoz = cargarPreferencia("biblioteca-leer-voz", false);
  const establecer = () => {
    botonLeerVoz.setAttribute("aria-pressed", String(leerVoz));
    botonLeerVoz.title = leerVoz ? "Desactivar lectura en voz alta" : "Activar lectura en voz alta";
    chat?.establecerPreferencias({ voz: leerVoz });
    const espejoVoz = contenidoMenuMovil?.querySelector("[data-espejo-voz]");
    if (espejoVoz) espejoVoz.setAttribute("aria-pressed", String(leerVoz));
  };
  botonLeerVoz.addEventListener("click", () => {
    leerVoz = !leerVoz;
    guardarPreferencia("biblioteca-leer-voz", leerVoz);
    establecer();
  });
  document.querySelectorAll(".navegacion a").forEach((enlace) => { enlace.title = enlace.getAttribute("aria-label"); });
  document.querySelector("#nueva-conversacion").setAttribute("aria-label", "Nueva conversación");
  document.querySelector("#nueva-conversacion").title = "Nueva conversación";
  const botonTema = document.querySelector("#interruptor-tema");
  const actualizarTooltipTema = () => { botonTema.title = botonTema.getAttribute("aria-label") || ""; };
  new MutationObserver(actualizarTooltipTema).observe(botonTema, { attributes: true, attributeFilter: ["aria-label"] });
  actualizarTooltipTema();
  establecer();
  return establecer;
}

function actualizarUsuario(usuario) {
  codigoAvisos = usuario?.codigo || null;
  if (!usuario) document.querySelector("#avisos-disponibilidad")?.remove();
  else void actualizarAvisosDisponibilidad();
  if (usuario && !usuarioIdentificadoActual) {
    let preferenciaManual = false;
    try {
      preferenciaManual = localStorage.getItem("biblioteca-cuenta-plegada") !== null;
    } catch {
      preferenciaManual = false;
    }
    if (!preferenciaManual && estaEnEscritorio()) {
      cuentaPlegada = false;
      raiz.classList.remove("app-shell--cuenta-plegada");
      botonPlegarCuenta.setAttribute("aria-expanded", "true");
      botonPlegarCuenta.setAttribute("aria-label", "Plegar panel Mi cuenta");
    }
  }
  usuarioIdentificadoActual = Boolean(usuario);
  if (usuario) cuenta.actualizar(usuario);
  else cuenta.limpiar();
}

cuenta = montarCuenta(contenidoCuenta, {
  alRenovar: (titulo) => chat?.enviarTexto(`Quiero renovar «${titulo}»`),
  alLogin: () => sesion?.mostrarLogin(),
  alCancelar: cancelarReserva,
  alCerrar: async () => {
    await cerrarSesion();
    chat?.limpiar();
    chat?.restablecerIdentidad();
    cuenta.limpiar();
    sesion?.cerrar();
  },
});
configurarPanelCuenta();
chat = montarChat(vistas.get("chat"), {
  abrirCuenta: abrirPanelCuenta,
  navegar: (vista) => {
    location.hash = vista;
    return cambiarVista(vista, true);
  },
  resaltarMaterial,
  alActualizarUsuario: (usuario, invitado) => {
    actualizarUsuario(usuario);
    tesis?.actualizarSesion(usuario);
    if (!usuario && invitado) cuenta.mostrarInvitado();
    const chipMovil = document.querySelector("#usuario-chip-movil");
    const botonSesionMovil = document.querySelector("#iniciar-sesion-movil");
    if (usuario) {
      chipMovil.textContent = usuario.nombre || "Identificado";
      chipMovil.title = usuario.nombre || "";
      botonSesionMovil.hidden = true;
    } else {
      chipMovil.textContent = invitado ? "Invitado" : "Inicia sesión";
      chipMovil.removeAttribute("title");
      botonSesionMovil.hidden = !invitado;
    }
  },
  solicitarLogin: (texto) => sesion?.mostrarLogin(texto),
  limpiarCuenta: () => cuenta.limpiar(),
});
const actualizarPreferencias = inicializarPreferencias();
actualizarPreferencias();

function configurarMenuMovil() {
  const serviciosMoviles = document.querySelector(".servicios-panel").cloneNode(true);
  const preferenciasMoviles = document.querySelector(".preferencias").cloneNode(true);
  const botonNuevaMovil = document.querySelector("#nueva-conversacion").cloneNode(true);
  const botonBorrarChatMovil = document.querySelector("#borrar-chat").cloneNode(true);
  const botonTesisMovil = document.querySelector("#subir-tesis").cloneNode(true);
  const indicadorTesisMovil = document.querySelector("#estado-subida-tesis").cloneNode(true);
  const enlacePanelMovil = document.querySelector(".enlace-panel-tecnico").cloneNode(true);
  botonNuevaMovil.removeAttribute("id");
  botonBorrarChatMovil.removeAttribute("id");
  botonBorrarChatMovil.addEventListener("click", () => document.querySelector("#borrar-chat").click());
  new MutationObserver(() => {
    botonBorrarChatMovil.hidden = document.querySelector("#borrar-chat").hidden;
    botonBorrarChatMovil.disabled = document.querySelector("#borrar-chat").disabled;
  }).observe(document.querySelector("#borrar-chat"), { attributes: true, attributeFilter: ["hidden", "disabled"] });
  botonTesisMovil.removeAttribute("id");
  indicadorTesisMovil.removeAttribute("id");
  enlacePanelMovil.addEventListener("click", cerrarMenuMovil);
  botonNuevaMovil.addEventListener("click", () => {
    document.querySelector("#nueva-conversacion").click();
    cerrarMenuMovil();
  });
  const botonVozMovil = preferenciasMoviles.querySelector("#leer-voz");
  botonVozMovil.removeAttribute("id");
  botonVozMovil.dataset.espejoVoz = "";
  botonVozMovil.addEventListener("click", () => document.querySelector("#leer-voz").click());
  const botonTemaMovil = preferenciasMoviles.querySelector("#interruptor-tema");
  botonTemaMovil.removeAttribute("id");
  const botonTemaOriginal = document.querySelector("#interruptor-tema");
  botonTemaMovil.addEventListener("click", () => botonTemaOriginal.click());
  const sincronizarTema = () => {
    botonTemaMovil.innerHTML = botonTemaOriginal.innerHTML;
    botonTemaMovil.setAttribute("aria-label", botonTemaOriginal.getAttribute("aria-label") || "");
    botonTemaMovil.setAttribute("aria-pressed", botonTemaOriginal.getAttribute("aria-pressed") || "false");
  };
  new MutationObserver(sincronizarTema).observe(botonTemaOriginal, { attributes: true, childList: true, subtree: true });
  sincronizarTema();
  contenidoMenuMovil.append(botonNuevaMovil, botonBorrarChatMovil, botonTesisMovil, indicadorTesisMovil, serviciosMoviles, preferenciasMoviles, enlacePanelMovil);

  const cerrarMenu = document.querySelector("#cerrar-menu-movil");
  const cerrarFondo = document.querySelector("#cerrar-menu-fondo");
  function abrir() {
    menuMovil.hidden = false;
    botonMenuMovil.setAttribute("aria-expanded", "true");
    cerrarMenu.focus();
  }
  function cerrarMenuMovil() {
    menuMovil.hidden = true;
    botonMenuMovil.setAttribute("aria-expanded", "false");
    botonMenuMovil.focus();
  }
  botonMenuMovil.addEventListener("click", abrir);
  cerrarMenu.addEventListener("click", cerrarMenuMovil);
  cerrarFondo.addEventListener("click", cerrarMenuMovil);
  document.querySelector("#abrir-cuenta-movil").addEventListener("click", abrirPanelCuenta);
  window.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape" && !menuMovil.hidden
      && !document.querySelector("#dialogo-subir-tesis:not([hidden])")) cerrarMenuMovil();
  });
  return { botonTesisMovil, indicadorTesisMovil };
}

const controlesTesisMoviles = configurarMenuMovil();
document.querySelector("#iniciar-sesion-movil").addEventListener("click", () => sesion?.mostrarLogin());
tesis = montarTesis({
  boton: document.querySelector("#subir-tesis"),
  indicador: document.querySelector("#estado-subida-tesis"),
  botonMovil: controlesTesisMoviles.botonTesisMovil,
  indicadorMovil: controlesTesisMoviles.indicadorTesisMovil,
  obtenerUsuario: () => chat?.obtenerUsuario(),
  solicitarLogin: () => sesion?.mostrarLogin(),
  navegar: (vista) => {
    location.hash = vista;
    return cambiarVista(vista, true);
  },
  enviarPregunta: (texto) => chat?.enviarTexto(texto),
  resaltarMaterial,
});
sesion = montarSesion({
  alEntrar: (usuario, mensajeBienvenida, avisos, textoPendiente) => {
    chat.limpiar();
    chat.establecerIdentidad(usuario);
    void (async () => {
      const restaurada = await chat.restaurarConversacion();
      if (!restaurada) chat.mostrarBienvenida(mensajeBienvenida, avisos);
      if (textoPendiente) chat.ofrecerReintento(textoPendiente);
    })();
  },
  alInvitado: () => {
    chat.limpiar();
    chat.establecerIdentidad(null, true);
  },
  alExpirar: () => {
    chat.limpiar();
    chat.restablecerIdentidad();
    cuenta.limpiar();
  },
});
window.addEventListener("biblioteca-sesion-expirada", () => sesion?.expirar());
window.addEventListener("pedir-login", () => sesion?.mostrarLogin());
window.addEventListener("preguntar-agente", async (evento) => {
  const texto = String(evento.detail?.texto || "").trim();
  location.hash = "chat";
  await cambiarVista("chat", true);
  if (texto) await chat?.enviarTexto(texto);
});
window.addEventListener("ver-en-mapa", async (evento) => {
  const materialId = evento.detail?.material_id;
  location.hash = "panel/mapa";
  await cambiarVista("panel/mapa", false);
  if (materialId != null) {
    window.requestAnimationFrame(() => resaltarMaterial(materialId));
  }
});
window.addEventListener("cuenta-cambio", async () => {
  await cuenta?.refrescar();
  await reservasVista?.refrescar?.();
  await actualizarAvisosDisponibilidad();
});

if (typeof ResizeObserver !== "undefined") {
  const actualizarEspacioFijo = () => {
    if (window.matchMedia("(min-width: 768px)").matches) {
      document.documentElement.style.removeProperty("--zona-fija-movil");
      return;
    }
    const altoComposer = document.querySelector(".barra-escritura")?.getBoundingClientRect().height || 0;
    const altoNav = document.querySelector(".navegacion-movil")?.getBoundingClientRect().height || 0;
    document.documentElement.style.setProperty("--zona-fija-movil", `${Math.ceil(altoComposer + altoNav + 16)}px`);
  };
  const observadorFijo = new ResizeObserver(actualizarEspacioFijo);
  observadorFijo.observe(document.querySelector(".barra-escritura"));
  observadorFijo.observe(document.querySelector(".navegacion-movil"));
  window.addEventListener("resize", actualizarEspacioFijo);
  actualizarEspacioFijo();
}

window.addEventListener("hashchange", () => {
  const hash = location.hash.slice(1);
  cambiarVista(hash, !hash.startsWith("panel/"));
});
const inicial = location.hash.slice(1);
cambiarVista(inicial, false);
consultarSalud();
window.setInterval(consultarSalud, 30000);
window.setInterval(actualizarAvisosDisponibilidad, 30000);
window.addEventListener("focus", actualizarAvisosDisponibilidad);

document.querySelectorAll(".navegacion-movil a").forEach((enlace) => {
  enlace.title = enlace.getAttribute("aria-label");
});
document.querySelectorAll("[data-icono]").forEach((nodo) => {
  nodo.innerHTML = iconos[nodo.dataset.icono] || "";
});
