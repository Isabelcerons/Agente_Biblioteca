const EJEMPLOS = [
  "cómo proteger una red de una empresa",
  "cultivos de la Amazonía",
  "aprender a programar desde cero",
];

function cargarEstilos() {
  const ruta = "/static/css/vistas.css";
  if (!document.querySelector(`link[rel="stylesheet"][href="${ruta}"]`)) {
    const enlace = document.createElement("link");
    enlace.rel = "stylesheet";
    enlace.href = ruta;
    document.head.append(enlace);
  }
}

function nodo(etiqueta, clase, contenido) {
  const elemento = document.createElement(etiqueta);
  if (clase) elemento.className = clase;
  if (contenido !== undefined) elemento.textContent = contenido;
  return elemento;
}

function tiempo(valor) {
  return `${Math.round(Number(valor || 0))} ms`;
}

function tipoVisible(tipo) {
  return {
    libro: "Libro",
    tesis: "Tesis",
    articulo: "Artículo",
    recurso_digital: "Recurso digital",
  }[tipo] || tipo || "Material";
}

function crearLomo(material, similitud = null, indice = 0, animar = true) {
  const tarjeta = nodo("article", `lomo lomo--${[
    "libro", "tesis", "articulo", "recurso_digital",
  ].includes(material.tipo) ? material.tipo : "libro"} vistas__lomo`);
  if (animar && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    tarjeta.classList.add("vistas__entrada");
    tarjeta.style.setProperty("--retardo-entrada", `${indice * 60}ms`);
  }
  tarjeta.append(
    nodo("p", "lomo__tipo", tipoVisible(material.tipo)),
    nodo("h3", "", material.titulo || "Título no indicado"),
    nodo("p", "lomo__autor", material.autor || "Autor no indicado"),
  );
  const pie = nodo("div", "lomo__pie");
  pie.append(
    nodo("span", "lomo__estante", material.anio ? String(material.anio) : "Acervo"),
    nodo(
      "span",
      `estado ${Number(material.disponibles) > 0 ? "estado--disponible" : "estado--prestado"}`,
      Number(material.disponibles) > 0 ? "Disponible" : "Sin ejemplares disponibles",
    ),
  );
  tarjeta.append(pie);
  if (similitud !== null) {
    const porcentaje = Math.round(Math.max(0, Math.min(1, Number(similitud) || 0)) * 100);
    const coincidencia = nodo("div", "coincidencia");
    const barra = document.createElement("progress");
    barra.max = 100;
    barra.value = porcentaje;
    barra.setAttribute("aria-label", `Similitud ${porcentaje} por ciento`);
    coincidencia.append(barra, nodo("span", "", `${porcentaje} %`));
    tarjeta.append(coincidencia);
  }
  return tarjeta;
}

export function montarDemo(contenedor) {
  if (!(contenedor instanceof HTMLElement)) {
    throw new TypeError("El contenedor de la demostración debe ser un elemento HTML.");
  }
  cargarEstilos();
  const controlador = new AbortController();
  contenedor.innerHTML = `
    <section class="vistas vistas--demo" aria-labelledby="demo-titulo">
      <header class="vistas__encabezado">
        <h1 id="demo-titulo">SQL vs pgvector</h1>
        <p>La misma pregunta, dos formas de buscar.</p>
      </header>
      <form class="vistas__busqueda-demo" role="search">
        <label class="sr-only" for="demo-consulta">Pregunta para comparar las búsquedas</label>
        <input id="demo-consulta" type="search" maxlength="500" required
          placeholder="¿Qué te gustaría encontrar?" autocomplete="off">
        <button class="btn btn--primario" type="submit">Buscar</button>
      </form>
      <div class="vistas__ejemplos" aria-label="Ejemplos de búsqueda"></div>
      <p class="sr-only" data-demo-estado role="status" aria-live="polite"></p>
      <div class="vistas__comparacion" data-demo-resultados aria-busy="false"></div>
      <p class="vistas__conclusion">SQL busca palabras; pgvector entiende el significado.</p>
    </section>
  `;
  const formulario = contenedor.querySelector(".vistas__busqueda-demo");
  const entrada = contenedor.querySelector("#demo-consulta");
  const ejemplos = contenedor.querySelector(".vistas__ejemplos");
  const resultados = contenedor.querySelector("[data-demo-resultados]");
  const estado = contenedor.querySelector("[data-demo-estado]");
  let solicitudActiva = null;
  let destruido = false;

  function mostrarCargando() {
    resultados.setAttribute("aria-busy", "true");
    const columnas = ["Búsqueda exacta (SQL)", "Búsqueda semántica (pgvector)"].map((titulo) => {
      const columna = nodo("section", "vistas__columna");
      columna.append(nodo("h2", "", titulo), nodo("div", "vistas__codigo", "Preparando consulta…"));
      const esqueletos = nodo("div", "vistas__esqueletos");
      for (let indice = 0; indice < 2; indice += 1) {
        esqueletos.append(nodo("div", "vistas__esqueleto"));
      }
      columna.append(esqueletos);
      return columna;
    });
    resultados.replaceChildren(...columnas);
    estado.textContent = "Buscando en SQL y pgvector…";
  }

  function mostrarColumna(titulo, lista, duracion, semantica, q, detalleTiempo) {
    const columna = nodo("section", "vistas__columna");
    columna.setAttribute("aria-label", titulo);
    columna.append(nodo("h2", "", titulo));
    const codigo = nodo("code", "vistas__codigo");
    if (semantica) {
      codigo.textContent = "ORDER BY embedding <=> embedding_de_la_consulta\n-- distancia coseno, índice HNSW";
    } else {
      const literal = q.replaceAll("'", "''");
      codigo.textContent =
        `SELECT titulo, autor FROM material WHERE titulo ILIKE '%${literal}%' OR autor ILIKE '%${literal}%'`;
    }
    columna.append(codigo);
    const filaResumen = nodo("div", "vistas__resumen-demo");
    const resumenPrincipal = nodo("div", "vistas__resumen-principal");
    resumenPrincipal.append(
      nodo("strong", "vistas__contador", String(lista.length)),
      nodo("span", "", "resultados"),
    );
    filaResumen.append(
      resumenPrincipal,
      nodo("span", "vistas__resumen-secundario", detalleTiempo || tiempo(duracion)),
    );
    columna.append(filaResumen);
    if (!lista.length) {
      const vacio = nodo("div", "vistas__vacio");
      vacio.setAttribute("role", "status");
      vacio.append(
        nodo("span", "vistas__vacio-icono", "⌕"),
        nodo(
          "p",
          "",
          semantica
            ? "No encontramos materiales relacionados con esta consulta."
            : "0 resultados: ningún título contiene esa frase exacta.",
        ),
      );
      columna.append(vacio);
    } else {
      const tarjetas = nodo("div", "vistas__tarjetas-demo");
      lista.forEach((material, indice) => tarjetas.append(
        crearLomo(material, semantica ? material.similitud : null, indice),
      ));
      columna.append(tarjetas);
    }
    return columna;
  }

  function renderizar(datos, q) {
    const exactos = Array.isArray(datos.sql) ? datos.sql : [];
    const semanticos = Array.isArray(datos.pgvector) ? datos.pgvector : [];
    const tiempos = datos.tiempos || {};
    const duracionSemantica = Number(tiempos.t_embedding_ms || 0)
      + Number(tiempos.t_busqueda_ms || 0);
    resultados.replaceChildren(
      mostrarColumna(
        "Búsqueda exacta (SQL)",
        exactos,
        tiempos.t_sql_ms,
        false,
        q,
        tiempo(tiempos.t_sql_ms),
      ),
      mostrarColumna(
        "Búsqueda semántica (pgvector)",
        semanticos,
        duracionSemantica,
        true,
        q,
        `embedding ${tiempo(tiempos.t_embedding_ms)} + búsqueda ${tiempo(tiempos.t_busqueda_ms)} = ${tiempo(duracionSemantica)}`,
      ),
    );
    resultados.setAttribute("aria-busy", "false");
    estado.textContent =
      `Comparación lista: ${exactos.length} resultados exactos y ${semanticos.length} semánticos.`;
  }

  async function buscar(consulta) {
    const q = consulta.trim();
    if (!q || destruido) return;
    solicitudActiva?.abort();
    solicitudActiva = new AbortController();
    entrada.value = q;
    mostrarCargando();
    try {
      const respuesta = await fetch(`/api/demo?q=${encodeURIComponent(q)}`, {
        signal: solicitudActiva.signal,
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible ejecutar la demostración.");
      if (!destruido && !solicitudActiva.signal.aborted) renderizar(datos, q);
    } catch (error) {
      if (error.name === "AbortError" || destruido) return;
      const aviso = nodo("div", "aviso aviso--error vistas__error");
      aviso.setAttribute("role", "alert");
      aviso.append(
        nodo("p", "", error.message || "No se pudo completar la búsqueda. Revisa tu conexión."),
      );
      const reintentar = nodo("button", "btn btn--fantasma", "Reintentar");
      reintentar.type = "button";
      reintentar.addEventListener("click", () => buscar(q), {
        signal: controlador.signal,
      });
      aviso.append(reintentar);
      resultados.replaceChildren(aviso);
      resultados.setAttribute("aria-busy", "false");
      estado.textContent = "Ocurrió un error al buscar. Puedes reintentar.";
    }
  }

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    void buscar(entrada.value);
  }, { signal: controlador.signal });
  EJEMPLOS.forEach((ejemplo) => {
    const boton = nodo("button", "btn btn--fantasma vistas__ejemplo", ejemplo);
    boton.type = "button";
    boton.addEventListener("click", () => void buscar(ejemplo), {
      signal: controlador.signal,
    });
    ejemplos.append(boton);
  });
  void buscar(EJEMPLOS[0]);
  return {
    destruir() {
      destruido = true;
      solicitudActiva?.abort();
      controlador.abort();
    },
  };
}
