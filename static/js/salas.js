/**
 * Biblioteca UniPutumayo — Módulo de Salas Temáticas y Bibliotecarios
 *
 * Cada sala agrupa los materiales por programa académico y cuenta con un
 * bibliotecario especializado. Este módulo gestiona la obtención de salas,
 * las tarjetas-puerta animadas (versión completa y versión compacta para el chat),
 * el chip de cabecera y la persistencia de la sala elegida.
 *
 * Basado en:
 * - CONTRATO (.misiones/contrato_salas.md)
 * - ADENDA (.misiones/contrato_salas_adenda.md - prioridad de conversación)
 * - Lenguaje visual de estantería viva, lomos que respiran, polvo dorado y brillo latón
 *   (static/css/login.css y static/css/escena.css).
 */

// Clave para guardar la sala preferida en el almacenamiento local
const CLAVE_STORAGE_SALA = "biblioteca-sala";

// Caché en memoria para evitar peticiones repetidas a /api/salas
let cacheSalas = null;

/**
 * Paleta de colores estables por sala (versión clara y versión oscura).
 * Representa la identidad visual de cada área académica y sus lomos.
 */
export const COLORES_SALAS = {
  ingenieria: {
    claro: "#B54A3C",
    oscuro: "#F08A7C",
    fondoClaro: "rgb(181 74 60 / 10%)",
    fondoOscuro: "rgb(240 138 124 / 15%)",
  },
  "agro-ambiental": {
    claro: "#2E7D4F",
    oscuro: "#6CC08F",
    fondoClaro: "rgb(46 125 79 / 10%)",
    fondoOscuro: "rgb(108 192 143 / 15%)",
  },
  administracion: {
    claro: "#8B5E3C",
    oscuro: "#D9A577",
    fondoClaro: "rgb(139 94 60 / 10%)",
    fondoOscuro: "rgb(217 165 119 / 15%)",
  },
  contaduria: {
    claro: "#7A4E9C",
    oscuro: "#C29BE8",
    fondoClaro: "rgb(122 78 156 / 10%)",
    fondoOscuro: "rgb(194 155 232 / 15%)",
  },
  investigacion: {
    claro: "#A07A00",
    oscuro: "#E8C14A",
    fondoClaro: "rgb(160 122 0 / 10%)",
    fondoOscuro: "rgb(232 193 74 / 15%)",
  },
  todas: {
    claro: "#C9A227",
    oscuro: "#E3B84E",
    fondoClaro: "rgb(201 162 39 / 10%)",
    fondoOscuro: "rgb(227 184 78 / 15%)",
  },
};

/**
 * Normaliza un slug de sala eliminando tildes y caracteres especiales.
 * @param {string|null|undefined} slug
 * @returns {string} Slug canónico o "todas"
 */
function normalizarSlug(slug) {
  if (!slug || slug === "todas" || slug === "sin_sala") return "todas";
  const limpio = String(slug)
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  if (limpio.includes("ingenier")) return "ingenieria";
  if (limpio.includes("agro") || limpio.includes("ambient")) return "agro-ambiental";
  if (limpio.includes("administra") || limpio.includes("negocio")) return "administracion";
  if (limpio.includes("contad") || limpio.includes("finanz")) return "contaduria";
  if (limpio.includes("investiga") || limpio.includes("escrit")) return "investigacion";
  return limpio;
}

/**
 * Devuelve el color estable asociado a una sala según su slug.
 * Permite especificar si se desea el color para tema oscuro o detecta
 * automáticamente el tema actual del documento.
 *
 * @param {string|null} slug - Identificador de la sala
 * @param {boolean|string|null} [modoOscuro=null] - Opcional: true/'oscuro' fuerza el tono oscuro
 * @returns {string} Código hexadecimal del color
 */
export function colorDeSala(slug, modoOscuro = null) {
  const clave = normalizarSlug(slug);
  const colores = COLORES_SALAS[clave] || COLORES_SALAS.todas;

  let esOscuro = false;
  if (typeof modoOscuro === "boolean") {
    esOscuro = modoOscuro;
  } else if (typeof modoOscuro === "string") {
    esOscuro = modoOscuro.toLowerCase().includes("oscur");
  } else if (typeof document !== "undefined" && document.documentElement?.dataset?.tema === "oscuro") {
    esOscuro = true;
  }

  return esOscuro ? colores.oscuro : colores.claro;
}

colorDeSala.paleta = COLORES_SALAS;

/**
 * Genera el texto en lenguaje natural para la elección de una sala,
 * tal como la usuaria lo diría en el chat (adenda §3 y §5).
 * Ej: "Quiero ir a la Sala de Ingeniería" o "Quiero ir a Toda la biblioteca".
 *
 * @param {Object|null} sala - Objeto de sala o null para "Toda la biblioteca"
 * @returns {string} Frase de elección lista para enviar al chat
 */
export function textoEleccionSala(sala) {
  if (!sala || !sala.slug || sala.slug === "todas") {
    return "Quiero ir a Toda la biblioteca";
  }
  const nombre = sala.nombre_corto || sala.nombre || "la sala";
  if (/^sala\b/i.test(nombre)) {
    return `Quiero ir a la ${nombre}`;
  }
  return `Quiero ir a la Sala de ${nombre}`;
}

/**
 * Guarda en localStorage el slug de la sala preferida del usuario.
 * Si se recibe null, valor vacío o "todas", remueve la preferencia guardada.
 *
 * @param {string|null} slug - Slug de la sala elegida o null para toda la biblioteca
 */
export function guardarSalaPreferida(slug) {
  try {
    if (!slug || slug === "todas") {
      localStorage.removeItem(CLAVE_STORAGE_SALA);
    } else {
      localStorage.setItem(CLAVE_STORAGE_SALA, String(slug).trim());
    }
  } catch (error) {
    console.warn("No fue posible guardar la sala preferida en localStorage:", error);
  }
}

/**
 * Lee desde localStorage el slug de la sala preferida.
 *
 * @returns {string|null} Slug guardado o null si no existe o hubo un error
 */
export function leerSalaPreferida() {
  try {
    const valor = localStorage.getItem(CLAVE_STORAGE_SALA);
    return valor ? valor.trim() : null;
  } catch (error) {
    console.warn("No fue posible leer la sala preferida de localStorage:", error);
    return null;
  }
}

/**
 * Obtiene la lista de salas desde la API del backend (/api/salas) con credenciales
 * same-origin y almacenamiento en caché en memoria.
 * Si la petición falla o la respuesta no es satisfactoria, devuelve un arreglo
 * vacío [] para que la interfaz muestre únicamente "Toda la biblioteca".
 *
 * @param {Object} [opciones={}]
 * @param {boolean} [opciones.forzar=false] - Si es true, ignora la caché y consulta de nuevo
 * @returns {Promise<Array<Object>>} Lista de salas temáticas
 */
export async function obtenerSalas({ forzar = false } = {}) {
  if (cacheSalas && !forzar) {
    return cacheSalas;
  }

  try {
    const respuesta = await fetch("/api/salas", {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    if (!respuesta.ok) {
      console.warn("Respuesta no satisfactoria al obtener salas:", respuesta.status);
      return [];
    }

    const datos = await respuesta.json();
    const lista = Array.isArray(datos)
      ? datos
      : Array.isArray(datos?.salas)
      ? datos.salas
      : [];

    cacheSalas = lista;
    return lista;
  } catch (error) {
    console.warn("Error al conectar con /api/salas:", error);
    return [];
  }
}

/**
 * Invalida la caché en memoria de salas (útil para pruebas o recargas).
 */
export function limpiarCacheSalas() {
  cacheSalas = null;
}

/**
 * Crea y retorna el elemento DOM correspondiente al chip de sala para la
 * cabecera del chat ("💻 Sala de Ingeniería · Andrés" + botón "Cambiar de sala").
 * Para null o sin sala muestra: "🏛️ Toda la biblioteca".
 *
 * @param {Object|null} sala - Objeto con datos de la sala o null para "Toda la biblioteca"
 * @param {Object} opciones
 * @param {Function} [opciones.alCambiar] - Callback al presionar el botón "Cambiar de sala"
 * @returns {HTMLElement} Elemento del chip listo para insertar en el encabezado
 */
export function crearChipSala(sala, { alCambiar } = {}) {
  const chip = document.createElement("div");
  chip.className = "salas-chip";
  chip.setAttribute("role", "status");

  function configurarContenido(s) {
    const esTodaLaBiblioteca = !s || !s.slug || s.slug === "todas";
    const slug = esTodaLaBiblioteca ? "todas" : s.slug;
    const colorLuz = colorDeSala(slug);

    chip.style.setProperty("--color-sala", colorLuz);
    chip.dataset.sala = slug;

    const icono = esTodaLaBiblioteca ? "🏛️" : s.icono || "📖";
    const nombre = esTodaLaBiblioteca
      ? "Toda la biblioteca"
      : s.nombre_corto || s.nombre || "Sala de biblioteca";

    const bibliotecarioNombre = !esTodaLaBiblioteca
      ? typeof s.bibliotecario === "object"
        ? s.bibliotecario?.nombre
        : s.bibliotecario
      : null;

    const textoEtiqueta = bibliotecarioNombre
      ? `${icono} ${nombre} · ${bibliotecarioNombre}`
      : `${icono} ${nombre}`;

    chip.innerHTML = `
      <span class="salas-chip__indicador" aria-hidden="true"></span>
      <span class="salas-chip__texto">${textoEtiqueta}</span>
      <button
        type="button"
        class="salas-chip__boton-cambiar"
        aria-label="Cambiar de sala de la biblioteca. Sala actual: ${nombre}"
        title="Cambiar de sala"
      >
        <span class="salas-chip__boton-texto">Cambiar</span>
        <svg class="salas-chip__boton-icono" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M4 6l4 4 4-4" />
        </svg>
      </button>
    `;

    const botonCambiar = chip.querySelector(".salas-chip__boton-cambiar");
    botonCambiar.addEventListener("click", (evento) => {
      evento.preventDefault();
      evento.stopPropagation();
      if (typeof alCambiar === "function") {
        alCambiar(s);
      }
    });
  }

  configurarContenido(sala);

  chip.actualizar = (nuevaSala) => {
    configurarContenido(nuevaSala);
  };

  return chip;
}

/**
 * Genera el elemento visual para el mini-estante decorativo con lomos
 * del color característico de la sala, con animación viva de respiración
 * idéntica a la escena de biblioteca y login (escena.css / login.css).
 *
 * @param {string} slug - Slug de la sala
 * @param {boolean} [esCompacta=false] - Si es para la versión reducida de chat
 * @returns {string} HTML del mini-estante animado
 */
function renderizarMiniEstante(slug, esCompacta = false) {
  const color = colorDeSala(slug);
  const claseCompacta = esCompacta ? " salas-mini-estante--compacto" : "";
  return `
    <div class="salas-mini-estante${claseCompacta}" aria-hidden="true" style="--color-sala: ${color};">
      <div class="salas-mini-estante__balda">
        <span class="salas-mini-lomo salas-mini-lomo--1 salas-mini-lomo--respirando-1"></span>
        <span class="salas-mini-lomo salas-mini-lomo--2 salas-mini-lomo--respirando-2"></span>
        <span class="salas-mini-lomo salas-mini-lomo--3 salas-mini-lomo--respirando-3"></span>
        <span class="salas-mini-lomo salas-mini-lomo--4 salas-mini-lomo--respirando-1"></span>
      </div>
    </div>
  `;
}

/**
 * Genera partículas sutiles de polvo dorado que flotan dentro de la tarjeta,
 * emulando el polvo dorado de la escena y el login (polvo-dorado / escena-polvo).
 *
 * @returns {string} HTML del polvo dorado
 */
function renderizarPolvoDorado() {
  return `
    <div class="salas-polvo" aria-hidden="true">
      <span class="salas-particula salas-p1"></span>
      <span class="salas-particula salas-p2"></span>
      <span class="salas-particula salas-p3"></span>
    </div>
  `;
}

/**
 * Construye el objeto de tarjeta para "Toda la biblioteca".
 *
 * @param {Array<Object>} salas - Lista de salas para totalizar libros y tesis si existen
 * @returns {Object} Representación unificada de la opción general
 */
function construirOpcionTodaLaBiblioteca(salas = []) {
  let totalLibros = 0;
  let totalTesis = 0;

  for (const s of salas) {
    totalLibros += Number(s.libros) || 0;
    totalTesis += Number(s.tesis) || 0;
  }

  const conteo = totalLibros > 0 || totalTesis > 0
    ? `${totalLibros} libros · ${totalTesis} tesis`
    : "Catálogo completo";

  return {
    slug: null,
    nombre: "Toda la biblioteca",
    nombre_corto: "Toda la biblioteca",
    descripcion: "Consulta general y abierta. Explora todos los libros, tesis y reglamentos sin restricción de sala.",
    icono: "🏛️",
    bibliotecario: {
      nombre: "Equipo general",
      saludo: "Bienvenido al catálogo general de la biblioteca. ¿Qué necesitas encontrar hoy?",
    },
    conteoTexto: conteo,
    esGeneral: true,
  };
}

/**
 * Monta la vista de selección de salas dentro de un contenedor.
 *
 * Soporta dos modos:
 * 1. Modo completo (pantalla/vista de bienvenida opcional):
 *    - Título serif: "¿A qué sala quieres ir?"
 *    - Subtítulo explicativo
 *    - Cuadrícula responsive de 3 columnas (desktop), 2 (tablet), 1 (móvil)
 * 2. Modo compacto (`compacta: true` - Adenda §2 y §5):
 *    - Diseñado específicamente para incrustarse DENTRO de la burbuja del agente en el chat.
 *    - Tarjetas compactas de interacción rápida con lomos que respiran y brillo latón.
 *
 * Animaciones visuales inspiradas en login.css y escena.css:
 * - Lomos de libros que respiran suavemente con ritmo alternado.
 * - Partículas de polvo dorado flotando con sutil brillo de latón.
 * - Leve rotación 3D ("la puerta se abre") y halo dorado de latón al pasar el mouse.
 * - Accesibilidad plena (ARIA, foco visible, teclado) y respeto por `prefers-reduced-motion`.
 *
 * @param {HTMLElement} contenedor - Elemento del DOM donde se montará la vista
 * @param {Object} opciones
 * @param {Object|string|null} [opciones.salaActual=null] - Sala seleccionada previamente
 * @param {Function} opciones.alElegir - Callback (sala, textoMensaje) al seleccionar
 * @param {Array<Object>|null} [opciones.salas=null] - Lista opcional de salas pre-cargadas
 * @param {boolean} [opciones.compacta=false] - Activa la versión compacta para burbujas de chat
 * @param {string|null} [opciones.titulo=null] - Título personalizado opcional
 * @param {string|null} [opciones.subtitulo=null] - Subtítulo personalizado opcional
 * @returns {{ destruir: Function }} Manejador para desmontar el componente limpiamente
 */
export function montarSelectorSala(contenedor, {
  salaActual = null,
  alElegir,
  salas = null,
  compacta = false,
  titulo = null,
  subtitulo = null,
} = {}) {
  if (!contenedor) {
    console.warn("montarSelectorSala: contenedor no especificado.");
    return { destruir: () => {} };
  }

  let destruido = false;
  const slugActual = typeof salaActual === "string" ? salaActual : salaActual?.slug || null;

  // Raíz principal del selector
  const raiz = document.createElement("section");
  raiz.className = compacta ? "salas-selector salas-selector--compacto" : "salas-selector";
  raiz.setAttribute("aria-labelledby", "salas-titulo-selector");

  // Encabezado decorativo (se omite en modo compacto a menos que se pase explícitamente)
  if (!compacta || titulo) {
    const encabezado = document.createElement("header");
    encabezado.className = "salas-encabezado";
    const textoTitulo = titulo || "¿A qué sala quieres ir?";
    const textoSubtitulo = subtitulo || "Cada sala tiene su bibliotecario. Te atenderá con los libros y tesis de su área.";

    encabezado.innerHTML = `
      ${!compacta ? `<span class="salas-emblema" aria-hidden="true">🏛️</span>` : ""}
      <h2 id="salas-titulo-selector" class="salas-titulo">${textoTitulo}</h2>
      ${textoSubtitulo ? `<p class="salas-subtitulo">${textoSubtitulo}</p>` : ""}
    `;
    raiz.appendChild(encabezado);
  }

  // Contenedor de la cuadrícula de tarjetas
  const rejilla = document.createElement("div");
  rejilla.className = compacta ? "salas-rejilla salas-rejilla--compacta" : "salas-rejilla";
  rejilla.setAttribute("role", "region");
  rejilla.setAttribute("aria-label", "Salas temáticas de la biblioteca");
  raiz.appendChild(rejilla);

  // Renderiza una tarjeta-puerta para una sala dada
  function crearBotonTarjeta(sala) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = compacta
      ? "salas-tarjeta-puerta salas-tarjeta-puerta--compacta"
      : "salas-tarjeta-puerta";

    const esGeneral = !sala.slug || sala.slug === "todas";
    const slug = esGeneral ? "todas" : sala.slug;
    boton.dataset.sala = slug;

    const esActiva = slugActual === (sala.slug || null) || (esGeneral && slugActual === null);
    if (esActiva) {
      boton.classList.add("salas-tarjeta-puerta--activa");
      boton.setAttribute("aria-pressed", "true");
    } else {
      boton.setAttribute("aria-pressed", "false");
    }

    const color = colorDeSala(slug);
    boton.style.setProperty("--color-sala", color);

    const icono = sala.icono || (esGeneral ? "🏛️" : "📖");
    const nombre = sala.nombre || (esGeneral ? "Toda la biblioteca" : "Sala temática");
    const bibliotecario = typeof sala.bibliotecario === "object"
      ? sala.bibliotecario?.nombre
      : (sala.bibliotecario || (esGeneral ? "Equipo general" : "Bibliotecario"));

    const conteo = sala.conteoTexto || (
      sala.libros !== undefined && sala.tesis !== undefined
        ? `${sala.libros} libros · ${sala.tesis} tesis`
        : (esGeneral ? "Catálogo completo" : "Material disponible")
    );

    const descripcion = sala.descripcion || (
      esGeneral
        ? "Consulta abierta en toda la biblioteca sin delimitación de área."
        : "Colección especializada para estudiantes y docentes."
    );

    boton.setAttribute(
      "aria-label",
      `${nombre}. Te atiende ${bibliotecario}. ${conteo}. ${descripcion}`
    );

    // Contenido de la tarjeta puerta con marco, hoja batiente, lomos vivos y polvo dorado
    boton.innerHTML = `
      <div class="salas-tarjeta-puerta__marco">
        <div class="salas-tarjeta-puerta__hoja">
          ${renderizarPolvoDorado()}

          <div class="salas-tarjeta-puerta__cabecera">
            <span class="salas-tarjeta-puerta__icono" aria-hidden="true">${icono}</span>
            <div class="salas-tarjeta-puerta__titulos">
              <span class="salas-tarjeta-puerta__nombre">${nombre}</span>
              <span class="salas-tarjeta-puerta__bibliotecario">
                <span class="salas-tarjeta-puerta__atencion-icono" aria-hidden="true">👤</span>
                Te atiende <strong>${bibliotecario}</strong>
              </span>
            </div>
            ${esActiva ? `<span class="salas-tarjeta-puerta__distintivo">Sala actual</span>` : ""}
          </div>

          ${!compacta ? `<p class="salas-tarjeta-puerta__desc">${descripcion}</p>` : ""}

          ${renderizarMiniEstante(slug, compacta)}

          <div class="salas-tarjeta-puerta__pie">
            <span class="salas-tarjeta-puerta__conteo">
              <svg class="salas-tarjeta-puerta__conteo-icono" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M2 3.5A1.5 1.5 0 0 1 3.5 2H7v12H3.5A1.5 1.5 0 0 1 2 12.5z" />
                <path d="M14 3.5A1.5 1.5 0 0 0 12.5 2H9v12h3.5a1.5 1.5 0 0 0 1.5-1.5z" />
              </svg>
              ${conteo}
            </span>
            <span class="salas-tarjeta-puerta__accion" aria-hidden="true">
              Entrar <span class="salas-tarjeta-puerta__flecha">→</span>
            </span>
          </div>
        </div>
      </div>
    `;

    // Al hacer clic, se obtiene el objeto y el texto en lenguaje natural (Adenda §5)
    boton.addEventListener("click", (evento) => {
      evento.preventDefault();
      const seleccion = esGeneral ? null : sala;
      const textoMensaje = textoEleccionSala(seleccion);
      guardarSalaPreferida(seleccion ? seleccion.slug : null);
      if (typeof alElegir === "function") {
        alElegir(seleccion, textoMensaje);
      }
    });

    return boton;
  }

  // Navegación accesible con teclado dentro de la cuadrícula
  function manejarTecladoRejilla(evento) {
    const tarjetas = Array.from(rejilla.querySelectorAll(".salas-tarjeta-puerta"));
    const indiceActual = tarjetas.indexOf(document.activeElement);
    if (indiceActual === -1) return;

    let nuevoIndice = null;
    let columnas = 1;
    if (compacta) {
      columnas = window.innerWidth >= 520 ? 2 : 1;
    } else {
      columnas = window.innerWidth >= 1100 ? 3 : window.innerWidth >= 640 ? 2 : 1;
    }

    switch (evento.key) {
      case "ArrowRight":
        nuevoIndice = (indiceActual + 1) % tarjetas.length;
        break;
      case "ArrowLeft":
        nuevoIndice = (indiceActual - 1 + tarjetas.length) % tarjetas.length;
        break;
      case "ArrowDown":
        if (indiceActual + columnas < tarjetas.length) {
          nuevoIndice = indiceActual + columnas;
        }
        break;
      case "ArrowUp":
        if (indiceActual - columnas >= 0) {
          nuevoIndice = indiceActual - columnas;
        }
        break;
      case "Home":
        nuevoIndice = 0;
        break;
      case "End":
        nuevoIndice = tarjetas.length - 1;
        break;
      default:
        return;
    }

    if (nuevoIndice !== null) {
      evento.preventDefault();
      tarjetas[nuevoIndice]?.focus();
    }
  }

  rejilla.addEventListener("keydown", manejarTecladoRejilla);

  function poblarCuadricula(listaSalas) {
    if (destruido) return;
    rejilla.innerHTML = "";

    const tarjetaGeneral = construirOpcionTodaLaBiblioteca(listaSalas);

    if (!listaSalas || listaSalas.length === 0) {
      const botonGeneral = crearBotonTarjeta(tarjetaGeneral);
      rejilla.appendChild(botonGeneral);
      return;
    }

    for (const sala of listaSalas) {
      const botonSala = crearBotonTarjeta(sala);
      rejilla.appendChild(botonSala);
    }

    const botonGeneral = crearBotonTarjeta(tarjetaGeneral);
    rejilla.appendChild(botonGeneral);
  }

  // Carga inicial: datos provistos o API
  if (salas && Array.isArray(salas)) {
    poblarCuadricula(salas);
  } else {
    if (cacheSalas) {
      poblarCuadricula(cacheSalas);
    } else {
      rejilla.innerHTML = `
        <div class="salas-cargando" role="status" aria-live="polite">
          <span class="salas-cargando__orbe" aria-hidden="true"></span>
          <span class="salas-cargando__texto">Preparando las salas de la biblioteca…</span>
        </div>
      `;
    }

    obtenerSalas()
      .then((lista) => {
        if (!destruido) poblarCuadricula(lista);
      })
      .catch(() => {
        if (!destruido) poblarCuadricula([]);
      });
  }

  contenedor.appendChild(raiz);

  return {
    destruir() {
      destruido = true;
      rejilla.removeEventListener("keydown", manejarTecladoRejilla);
      raiz.remove();
    },
  };
}

/**
 * Función de conveniencia para montar las opciones de sala DENTRO de la burbuja
 * del chat (Adenda §2 y §5).
 *
 * @param {HTMLElement} contenedorBurbuja - Elemento de la burbuja del agente
 * @param {Object} opciones
 * @param {Function} opciones.alElegir - Callback (sala, textoMensaje)
 * @param {Array<Object>|null} [opciones.salas=null] - Opciones devueltas por salas_opciones
 * @param {Object|string|null} [opciones.salaActual=null] - Sala actualmente seleccionada
 * @returns {{ destruir: Function }}
 */
export function montarOpcionesSalasChat(contenedorBurbuja, {
  salaActual = null,
  alElegir,
  salas = null,
} = {}) {
  return montarSelectorSala(contenedorBurbuja, {
    salaActual,
    alElegir,
    salas,
    compacta: true,
  });
}

/* ==========================================================================
   GUÍA DE INTEGRACIÓN — PASO 2 (Ajustada a la ADENDA y requerimientos)
   ==========================================================================

   1. Flujo Conversacional Inicial (Adenda §2):
      - Al entrar y en cada "Nueva conversación", el primer mensaje del agente
        es un saludo + la pregunta "¿Qué sala quieres visitar hoy?".
      - El mensaje del asistente incluye el campo `salas_opciones` con la lista de salas.
      - En la burbuja del mensaje se monta la versión compacta:
          const selector = montarOpcionesSalasChat(burbujaMensaje, {
            salas: mensaje.salas_opciones,
            salaActual,
            alElegir: (sala, textoMensaje) => {
              // Adenda §5: se envía como si la usuaria lo hubiera escrito/dicho
              // "Quiero ir a la Sala de Ingeniería"
              enviarMensajeUsuario(textoMensaje);
              guardarSalaPreferida(sala ? sala.slug : null);
              actualizarChipCabecera(sala);
            }
          });

   2. Selección por Lenguaje Natural y Voz (Adenda §3 y §4):
      - La usuaria puede escribir o decir:
        "quiero la de ingeniería", "llévame a la sala de agrarias",
        "la de contabilidad", "toda la biblioteca", "cámbiame de sala".
      - El backend procesa la intención determinista `elegir_sala`, responde con el
        saludo propio del bibliotecario de esa sala y devuelve `sala`.
      - Al recibir la respuesta, el frontend actualiza el chip de la cabecera con
        `chip.actualizar(respuesta.sala)`.

   3. Chip en la cabecera:
      - Creado con `const chip = crearChipSala(salaActual, { alCambiar })`.
      - Al pulsar "Cambiar", puede abrir un diálogo modal con `montarSelectorSala(modal, ...)`
        o enviar "¿Qué salas hay?" al chat.

   4. Parámetro `sala` en peticiones del chat y voz:
      - `POST /api/chat` y `POST /api/voz` aceptan `"sala": slug | null`.
      - Si llega `sugerencia_sala: { slug, nombre, motivo }`, se muestra el botón
        para cambiar de sala directamente.
   ========================================================================== */
