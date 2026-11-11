/**
 * Biblioteca UniPutumayo — Escena Animada de la Biblioteca para el Chat
 * 
 * Componente modular y reutilizable que traslada las animaciones
 * vivas del inicio de sesión (estantería de lomos que respiran,
 * orbe inteligente latiendo y polvo dorado sutil) al entorno del chat.
 */

// Metadatos de los libros que componen la estantería viva
const LIBROS_DATOS = [
  {
    titulo: "PUTUMAYO",
    alto: "170px",
    ancho: "36px",
    colorLomo: "#1F4D3A",
    colorAcento: "#C9A227",
    respirando: "escena-lomo--respirando-1",
    filetes: 2,
  },
  {
    titulo: "SISTEMAS",
    etiqueta: "004",
    alto: "185px",
    ancho: "38px",
    colorLomo: "#8B5E3C",
    colorAcento: "#F6F1E7",
    respirando: "escena-lomo--respirando-2",
    filetes: 1,
  },
  {
    titulo: "ALGORITMOS",
    alto: "160px",
    ancho: "34px",
    colorLomo: "#9A3B2F",
    colorAcento: "#C9A227",
    marcador: true,
    filetes: 1,
  },
  {
    titulo: "AMAZONÍA",
    alto: "190px",
    ancho: "40px",
    colorLomo: "#1B3526",
    colorAcento: "#E3EDE6",
    respirando: "escena-lomo--respirando-3",
    filetes: 2,
  },
  {
    titulo: "INVESTIGAR",
    etiqueta: "APA 7",
    alto: "175px",
    ancho: "35px",
    colorLomo: "#C9A227",
    colorAcento: "#2A2A28",
    respirando: "escena-lomo--respirando-1",
  },
  {
    titulo: "CÁLCULO",
    alto: "180px",
    ancho: "37px",
    colorLomo: "#264837",
    colorAcento: "#C9A227",
    marcador: true,
    filetes: 1,
  },
  {
    titulo: "DERECHO",
    alto: "188px",
    ancho: "36px",
    colorLomo: "#7D2D24",
    colorAcento: "#F6F1E7",
    respirando: "escena-lomo--respirando-2",
    filetes: 2,
  },
  {
    titulo: "CATÁLOGO",
    etiqueta: "TESIS",
    alto: "172px",
    ancho: "38px",
    colorLomo: "#1F4D3A",
    colorAcento: "#C9A227",
    respirando: "escena-lomo--respirando-3",
  },
];

/**
 * Crea un elemento DOM con clase y atributos opcionales.
 */
function crearElemento(etiqueta, clase = "", atributos = {}) {
  const el = document.createElement(etiqueta);
  if (clase) el.className = clase;
  for (const [clave, valor] of Object.entries(atributos)) {
    if (valor !== null && valor !== undefined) {
      el.setAttribute(clave, valor);
    }
  }
  return el;
}

/**
 * Construye y monta la escena visual de la biblioteca dentro de un contenedor.
 *
 * @param {HTMLElement} contenedor - Elemento del DOM donde se insertará la escena.
 * @param {Object} [opciones={}]
 * @param {string} [opciones.saludo="Hola. ¿Qué quieres leer hoy?"] - Texto predeterminado del globo.
 * @param {string|null} [opciones.nombre=null] - Nombre del usuario autenticado o saludado.
 * @param {boolean} [opciones.compacta=false] - Forzar la versión de altura reducida (~120px).
 * @returns {Object} Controlador con métodos { saludar, pensar, hablar, destruir }.
 */
export function montarEscenaBiblioteca(
  contenedor,
  {
    saludo = "Hola. ¿Qué quieres leer hoy?",
    nombre = null,
    compacta = false,
  } = {}
) {
  if (!contenedor || !(contenedor instanceof HTMLElement)) {
    console.warn("[escena.js] Contenedor inválido o inexistente para montarEscenaBiblioteca.");
    return {
      saludar() {},
      pensar() {},
      hablar() {},
      destruir() {},
    };
  }

  // Raíz de la escena
  const raiz = crearElemento("div", `escena-raiz${compacta ? " escena-raiz--compacta" : ""}`);

  // 1. Partículas sutiles de polvo dorado (decorativas)
  const polvo = crearElemento("div", "escena-polvo", { "aria-hidden": "true" });
  for (let i = 1; i <= 6; i++) {
    const particula = crearElemento("span", `escena-particula escena-p${i}`);
    polvo.appendChild(particula);
  }
  raiz.appendChild(polvo);

  // 2. Fila del agente inteligente (orbe + bocadillo de saludo accesible)
  const agenteFila = crearElemento("div", "escena-agente");

  // Orbe y su halo concéntrico (decorativos)
  const orbeHalo = crearElemento("div", "escena-orbe-halo", { "aria-hidden": "true" });
  const orbe = crearElemento("span", "escena-orbe");
  orbeHalo.appendChild(orbe);
  agenteFila.appendChild(orbeHalo);

  // Bocadillo / Globo de saludo con soporte de lectura aria-live
  const globo = crearElemento("div", "escena-globo");
  const globoContenido = crearElemento("div", "escena-globo__contenido", { "aria-live": "polite" });

  const globoTexto = crearElemento("span", "escena-globo__texto");
  // Determinamos el saludo inicial de forma segura (sin innerHTML)
  let textoActual = nombre ? `Hola, ${nombre}. ¿Qué quieres leer hoy?` : saludo;
  globoTexto.textContent = textoActual;

  // Indicador de 3 puntos animados para cuando el agente está pensando
  const puntosPensando = crearElemento("span", "escena-puntos");
  puntosPensando.hidden = true;
  for (let j = 0; j < 3; j++) {
    const punto = crearElemento("span", "escena-punto");
    puntosPensando.appendChild(punto);
  }

  globoContenido.appendChild(globoTexto);
  globoContenido.appendChild(puntosPensando);
  globo.appendChild(globoContenido);
  agenteFila.appendChild(globo);

  raiz.appendChild(agenteFila);

  // 3. Estantería animada de libros (decorativa)
  const estanteria = crearElemento("div", "escena-estanteria", { "aria-hidden": "true" });
  const filaLibros = crearElemento("div", "escena-estanteria-libros");

  for (const libro of LIBROS_DATOS) {
    const clasesLomo = ["escena-lomo"];
    if (libro.respirando) {
      clasesLomo.push(libro.respirando);
    }
    const lomo = crearElemento("div", clasesLomo.join(" "));
    lomo.style.setProperty("--h", libro.alto);
    lomo.style.setProperty("--w", libro.ancho);
    lomo.style.setProperty("--color-lomo", libro.colorLomo);
    lomo.style.setProperty("--color-acento", libro.colorAcento);

    // Filete superior
    if (libro.filetes && libro.filetes >= 1) {
      lomo.appendChild(crearElemento("span", "escena-lomo-filete"));
    }

    // Etiqueta de clasificación (ej. 004, APA 7, TESIS)
    if (libro.etiqueta) {
      const etiqueta = crearElemento("span", "escena-lomo-etiqueta");
      etiqueta.textContent = libro.etiqueta;
      lomo.appendChild(etiqueta);
    }

    // Título vertical del lomo
    const textoLomo = crearElemento("span", "escena-lomo-texto");
    textoLomo.textContent = libro.titulo;
    lomo.appendChild(textoLomo);

    // Marcador de página que asoma por abajo
    if (libro.marcador) {
      lomo.appendChild(crearElemento("span", "escena-lomo-marcador"));
    }

    // Filete inferior
    if (libro.filetes && libro.filetes >= 2) {
      lomo.appendChild(crearElemento("span", "escena-lomo-filete"));
    }

    filaLibros.appendChild(lomo);
  }

  estanteria.appendChild(filaLibros);

  // Balda de madera con moldura y reflejo dorado
  const baldaMadera = crearElemento("div", "escena-estante-madera");
  const brilloMadera = crearElemento("span", "escena-estante-brillo");
  baldaMadera.appendChild(brilloMadera);
  estanteria.appendChild(baldaMadera);

  raiz.appendChild(estanteria);

  // Inserción en el contenedor objetivo
  contenedor.appendChild(raiz);

  // Control de estado interno y temporizadores de transición
  let estaPensando = false;
  let temporizadorTransicion = null;
  let esVisibleInterseccion = true;
  let esVisibleDocumento = typeof document !== "undefined" ? !document.hidden : true;

  /**
   * Pausa o reanuda las animaciones CSS para optimizar la batería y el rendimiento.
   */
  function actualizarEstadoPausa() {
    if (!raiz || !raiz.isConnected) return;
    const debePausar = !esVisibleInterseccion || !esVisibleDocumento;
    if (debePausar) {
      raiz.classList.add("escena--pausada");
    } else {
      raiz.classList.remove("escena--pausada");
    }
  }

  // Observador de intersección: pausa animaciones si la escena se desplaza fuera del viewport
  let observer = null;
  if (typeof IntersectionObserver !== "undefined") {
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          esVisibleInterseccion = entry.isIntersecting;
          actualizarEstadoPausa();
        }
      },
      { threshold: 0.05 }
    );
    observer.observe(raiz);
  }

  // Listener de visibilidad de pestaña: pausa cuando el usuario cambia de pestaña
  const alCambiarVisibilidad = () => {
    esVisibleDocumento = !document.hidden;
    actualizarEstadoPausa();
  };
  document.addEventListener("visibilitychange", alCambiarVisibilidad);

  /**
   * Cambia el texto del bocadillo con un desvanecimiento suave.
   *
   * @param {string} nuevoTexto
   */
  function cambiarTextoSuave(nuevoTexto) {
    if (temporizadorTransicion) {
      clearTimeout(temporizadorTransicion);
    }
    globoTexto.classList.add("escena-globo__texto--oculto");
    temporizadorTransicion = setTimeout(() => {
      globoTexto.textContent = nuevoTexto;
      globoTexto.classList.remove("escena-globo__texto--oculto");
      temporizadorTransicion = null;
    }, 150);
  }

  // Controlador devuelto
  return {
    /**
     * Actualiza el texto del bocadillo de saludo con una transición suave.
     * @param {string} texto
     */
    saludar(texto) {
      textoActual = String(texto || "");
      if (!estaPensando) {
        cambiarTextoSuave(textoActual);
      }
    },

    /**
     * Activa o desactiva el estado de reflexión del agente.
     * Al activarse, el orbe rota y brilla suavemente mientras el globo muestra "Pensando…".
     * Al desactivarse, vuelve al texto y apariencia normales.
     * @param {boolean} activo
     */
    pensar(activo) {
      estaPensando = Boolean(activo);
      if (estaPensando) {
        orbe.classList.add("escena-orbe--pensando");
        orbeHalo.classList.add("escena-orbe-halo--pensando");
        puntosPensando.hidden = false;
        cambiarTextoSuave("Pensando…");
      } else {
        orbe.classList.remove("escena-orbe--pensando");
        orbeHalo.classList.remove("escena-orbe-halo--pensando");
        puntosPensando.hidden = true;
        cambiarTextoSuave(textoActual);
      }
    },

    /**
     * Activa o desactiva la animación enérgica de habla del orbe
     * para acompañar la síntesis de voz (sin requerir Web Audio API).
     * @param {boolean} activo
     */
    hablar(activo) {
      if (activo) {
        orbe.classList.add("escena-orbe--hablando");
        orbeHalo.classList.add("escena-orbe-halo--hablando");
      } else {
        orbe.classList.remove("escena-orbe--hablando");
        orbeHalo.classList.remove("escena-orbe-halo--hablando");
      }
    },

    /**
     * Desmonta el componente del DOM, desconecta observadores y limpia eventos.
     */
    destruir() {
      if (temporizadorTransicion) {
        clearTimeout(temporizadorTransicion);
        temporizadorTransicion = null;
      }
      if (observer) {
        observer.disconnect();
        observer = null;
      }
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
      if (raiz && raiz.parentNode) {
        raiz.remove();
      }
    },
  };
}

/* ==========================================================================
   GUÍA DE INTEGRACIÓN — PASO 2 (Para conectar en el chat)
   ==========================================================================
   Cuando el constructor de la interfaz del chat (Copilot E) termine sus cambios,
   conectar este módulo en `static/js/chat.js` siguiendo estos sencillos pasos:

   1. Importar el módulo en la cabecera de `static/js/chat.js`:
      import { montarEscenaBiblioteca } from "./escena.js";

   2. Incluir la hoja de estilos en `static/index.html`:
      <link rel="stylesheet" href="/static/css/escena.css">

   3. En la función `bienvenida()` o al inicializar el contenedor de bienvenida:
      const contenedorBienvenida = section; // o elemento contenedor
      const escena = montarEscenaBiblioteca(contenedorBienvenida, {
        nombre: usuarioActual?.nombre || null,
        compacta: false // en pantallas < 768px se ajusta a modo compacto automáticamente
      });

   4. Al enviar una consulta (en `enviarTexto` o `form.addEventListener("submit")`):
      escena.pensar(true);

   5. Al recibir la respuesta del servidor (en el callback o bloque `finally`):
      escena.pensar(false);

   6. Al reproducir la respuesta con voz (en `reproducirRespuesta` o eventos de `audio`):
      audio.addEventListener("play", () => escena.hablar(true));
      audio.addEventListener("ended", () => escena.hablar(false));
      audio.addEventListener("pause", () => escena.hablar(false));

   7. Al existir mensajes en el historial o iniciar una conversación activa:
      La sección de bienvenida se oculta o se invoca `escena.destruir()`.
   ========================================================================== */
