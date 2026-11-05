import { renderBibliografia } from "../bibliografia.js";

function cargarEstilos() {
  const ruta = "/static/css/vistas.css";
  if (!document.querySelector(`link[rel="stylesheet"][href="${ruta}"]`)) {
    const enlace = document.createElement("link");
    enlace.rel = "stylesheet";
    enlace.href = ruta;
    document.head.append(enlace);
  }
}

function crear(etiqueta, clase, texto) {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined) nodo.textContent = texto;
  return nodo;
}

export function montarBibliografiaVista(contenedor) {
  if (!(contenedor instanceof HTMLElement)) {
    throw new TypeError("El contenedor de bibliografía debe ser un elemento HTML.");
  }
  cargarEstilos();
  const controlador = new AbortController();
  let solicitudActiva = null;
  let destruida = false;
  let norma = "APA";
  contenedor.innerHTML = `
    <section class="vistas vistas--bibliografia" aria-labelledby="bibliografia-titulo">
      <header class="vistas__encabezado">
        <h1 id="bibliografia-titulo">Bibliografía</h1>
        <p>Arma una lista de referencias con libros y tesis del acervo. Solo usa los datos del catálogo; si falta un dato, lo omite.</p>
      </header>
      <form class="vistas__form-bibliografia">
        <label class="campo">Tema
          <input name="tema" type="text" maxlength="500" required
            placeholder="Por ejemplo, biodiversidad de la Amazonía">
        </label>
        <div class="vistas__form-fila">
          <label class="campo">Cantidad
            <select name="cantidad">
              <option value="3">3 referencias</option>
              <option value="5" selected>5 referencias</option>
              <option value="8">8 referencias</option>
              <option value="10">10 referencias</option>
            </select>
          </label>
          <fieldset class="vistas__normas">
            <legend>Norma</legend>
            <div class="vistas__segmentados" role="group" aria-label="Norma bibliográfica">
              <button type="button" class="btn btn--segmentado" data-norma="APA" aria-pressed="true">APA</button>
              <button type="button" class="btn btn--segmentado" data-norma="IEEE" aria-pressed="false">IEEE</button>
            </div>
          </fieldset>
          <button class="btn btn--primario" type="submit">Generar</button>
        </div>
      </form>
      <p class="sr-only" data-estado role="status" aria-live="polite"></p>
      <div class="vistas__resultado-bibliografia" data-resultado aria-busy="false"></div>
    </section>
  `;
  const formulario = contenedor.querySelector(".vistas__form-bibliografia");
  const entradaTema = formulario.elements.namedItem("tema");
  const entradaCantidad = formulario.elements.namedItem("cantidad");
  const resultado = contenedor.querySelector("[data-resultado]");
  const estado = contenedor.querySelector("[data-estado]");
  const botonesNorma = [...contenedor.querySelectorAll("[data-norma]")];

  function elegirNorma(valor) {
    norma = valor;
    botonesNorma.forEach((boton) => {
      boton.setAttribute("aria-pressed", String(boton.dataset.norma === norma));
    });
  }

  function mostrarBibliografia(bibliografia, respuestaAgente) {
    const referencias = Array.isArray(bibliografia?.referencias)
      ? bibliografia.referencias
      : [];
    if (!referencias.length) {
      const mensaje = crear(
        "p",
        "aviso aviso--info",
        respuestaAgente
          || "No encontramos referencias del acervo para ese tema. Prueba con otra búsqueda.",
      );
      resultado.replaceChildren(mensaje);
      estado.textContent = mensaje.textContent;
      return;
    }

    const lista = renderBibliografia(bibliografia);
    const contenido = lista.querySelector(".bibliografia-contenido");
    const entradas = contenido
      ? [...contenido.querySelectorAll("li, .bibliografia-entrada")]
      : [];
    referencias.forEach((referencia, indice) => {
      const materialId = referencia.material_id;
      const entrada = entradas[indice];
      if (materialId === null || materialId === undefined || !entrada) return;
      const enlace = crear("a", "vistas__ver-mapa", "Ver en el mapa");
      enlace.href = "#mapa";
      enlace.addEventListener("click", () => {
        // Evento de integración: C1 puede escuchar "ver-en-mapa" para resaltar el material.
        window.dispatchEvent(new CustomEvent("ver-en-mapa", {
          detail: { material_id: materialId },
        }));
      }, { signal: controlador.signal });
      entrada.append(enlace);
    });
    resultado.replaceChildren(lista);
    estado.textContent = `Bibliografía lista: ${referencias.length} referencias en formato ${bibliografia.norma || norma}.`;
  }

  async function generar(tema, cantidad) {
    if (destruida) return;
    solicitudActiva?.abort();
    solicitudActiva = new AbortController();
    resultado.setAttribute("aria-busy", "true");
    const pensando = crear("p", "pensando", "Buscando en el catálogo…");
    for (let indice = 0; indice < 3; indice += 1) {
      pensando.append(document.createElement("span"));
    }
    resultado.replaceChildren(pensando);
    estado.textContent = "Buscando referencias en el catálogo…";
    try {
      const respuesta = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          texto: `Genera una bibliografía en ${norma} de ${cantidad} referencias sobre ${tema}`,
          conversacion_id: null,
        }),
        signal: solicitudActiva.signal,
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible generar la bibliografía.");
      if (destruida || solicitudActiva.signal.aborted) return;
      mostrarBibliografia(datos.bibliografia, datos.respuesta);
    } catch (error) {
      if (error.name === "AbortError" || destruida) return;
      const aviso = crear(
        "div",
        "aviso aviso--error",
        error.message || "No se pudo generar la bibliografía. Revisa tu conexión e inténtalo de nuevo.",
      );
      aviso.setAttribute("role", "alert");
      resultado.replaceChildren(aviso);
      estado.textContent = aviso.textContent;
    } finally {
      if (!destruida) resultado.setAttribute("aria-busy", "false");
    }
  }

  botonesNorma.forEach((boton) => {
    boton.addEventListener("click", () => elegirNorma(boton.dataset.norma), {
      signal: controlador.signal,
    });
  });
  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    void generar(entradaTema.value.trim(), Number(entradaCantidad.value));
  }, { signal: controlador.signal });
  return {
    destruir() {
      destruida = true;
      solicitudActiva?.abort();
      controlador.abort();
    },
  };
}
