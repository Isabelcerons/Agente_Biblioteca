import { microfono } from "../iconos.js";

function cargarEstilos() {
  const ruta = "/static/css/vistas.css";
  if (!document.querySelector(`link[rel="stylesheet"][href="${ruta}"]`)) {
    const enlace = document.createElement("link");
    enlace.rel = "stylesheet";
    enlace.href = ruta;
    document.head.append(enlace);
  }
}

function elemento(etiqueta, clase, texto) {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined) nodo.textContent = texto;
  return nodo;
}

function numero(valor) {
  return Number.isFinite(Number(valor)) ? Number(valor) : 0;
}

function fechaValida(valor) {
  const fecha = new Date(valor);
  return Number.isNaN(fecha.getTime()) ? null : fecha;
}

function esError(fila) {
  return Boolean(fila.error);
}

function esDeHoy(fila, hoy) {
  const fecha = fechaValida(fila.creado);
  return fecha && fecha.getFullYear() === hoy.getFullYear()
    && fecha.getMonth() === hoy.getMonth()
    && fecha.getDate() === hoy.getDate();
}

function horaVisible(valor) {
  const fecha = fechaValida(valor);
  return fecha
    ? new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" }).format(fecha)
    : "—";
}

function barraTiempos(fila) {
  const valores = [
    { nombre: "Reconocimiento de voz (STT)", clase: "stt", valor: numero(fila.t_stt_ms) },
    {
      nombre: "Búsqueda (embedding + recuperación)",
      clase: "busqueda",
      valor: numero(fila.t_embedding_ms) + numero(fila.t_busqueda_ms),
    },
    { nombre: "Respuesta del modelo (LLM)", clase: "llm", valor: numero(fila.t_llm_ms) },
    { nombre: "Síntesis de voz (TTS)", clase: "tts", valor: numero(fila.t_tts_ms) },
  ];
  const total = valores.reduce((suma, item) => suma + item.valor, 0);
  const barra = elemento("div", "barra-tiempos");
  barra.setAttribute("role", "img");
  barra.setAttribute(
    "aria-label",
    valores.map((item) => `${item.nombre}: ${item.valor} ms`).join("; "),
  );
  barra.title = valores
    .map((item) => `${item.nombre}: ${item.valor} ms`)
    .join(" · ");
  valores.forEach((item) => {
    const segmento = elemento("span", `barra-tiempos__segmento barra-tiempos__${item.clase}`);
    segmento.style.width = `${total ? (item.valor / total) * 100 : 0}%`;
    segmento.setAttribute("aria-hidden", "true");
    barra.append(segmento);
  });
  return barra;
}

export function montarBitacora(contenedor) {
  if (!(contenedor instanceof HTMLElement)) {
    throw new TypeError("El contenedor de la bitácora debe ser un elemento HTML.");
  }
  cargarEstilos();
  const controlador = new AbortController();
  let filas = [];
  let solicitudActiva = null;
  let interseccion = true;
  let destruida = false;
  let observador;
  contenedor.innerHTML = `
    <section class="vistas vistas--bitacora" aria-labelledby="bitacora-titulo">
      <header class="vistas__encabezado vistas__encabezado--fila">
        <div><h1 id="bitacora-titulo">Bitácora</h1>
          <p>Un registro transparente de las interacciones con el asistente.</p></div>
        <button class="btn btn--fantasma" type="button" data-actualizar>Actualizar</button>
      </header>
      <div class="vistas__metricas" data-metricas aria-label="Resumen de actividad"></div>
      <div class="vistas__filtros">
        <label class="campo">Filtrar por texto
          <input type="search" data-filtro placeholder="Pregunta, intención o herramienta">
        </label>
        <label class="vistas__casilla"><input type="checkbox" data-solo-voz> Solo voz</label>
        <label class="vistas__casilla"><input type="checkbox" data-solo-errores> Solo errores</label>
      </div>
      <div class="leyenda vistas__leyenda-tiempo" aria-label="Leyenda del desglose de tiempos"></div>
      <p class="sr-only" data-estado role="status" aria-live="polite"></p>
      <div class="vistas__tabla-contenedor" data-tabla></div>
    </section>
  `;
  const metricas = contenedor.querySelector("[data-metricas]");
  const tabla = contenedor.querySelector("[data-tabla]");
  const estado = contenedor.querySelector("[data-estado]");
  const filtro = contenedor.querySelector("[data-filtro]");
  const soloVoz = contenedor.querySelector("[data-solo-voz]");
  const soloErrores = contenedor.querySelector("[data-solo-errores]");
  const botonActualizar = contenedor.querySelector("[data-actualizar]");
  const leyenda = contenedor.querySelector(".vistas__leyenda-tiempo");
  const partesLeyenda = [
    ["stt", "STT · reconocimiento de voz"],
    ["busqueda", "Búsqueda · embedding + recuperación"],
    ["llm", "LLM · respuesta"],
    ["tts", "TTS · síntesis de voz"],
  ];
  partesLeyenda.forEach(([clase, nombre]) => {
    const item = elemento("span", "leyenda__item");
    const muestra = elemento("i", `leyenda__color barra-tiempos__${clase}`);
    muestra.setAttribute("aria-hidden", "true");
    item.append(muestra, elemento("span", "", nombre));
    leyenda.append(item);
  });

  function dibujarMetricas() {
    const hoy = new Date();
    const delDia = filas.filter((fila) => esDeHoy(fila, hoy));
    const promedio = delDia.length
      ? delDia.reduce((suma, fila) => suma + numero(fila.t_total_ms), 0) / delDia.length
      : 0;
    const voz = delDia.filter((fila) => fila.es_voz).length;
    const porcentajeVoz = delDia.length ? Math.round((voz / delDia.length) * 100) : 0;
    const errores = delDia.filter(esError).length;
    const tarjetas = [
      ["Interacciones de hoy", String(delDia.length)],
      ["Tiempo promedio de respuesta", `${(promedio / 1000).toFixed(1)} s`],
      ["% por voz", `${porcentajeVoz} %`],
      ["Errores", String(errores)],
    ].map(([etiqueta, valor]) => {
      const tarjeta = elemento("article", "tarjeta vistas__metrica");
      tarjeta.append(elemento("p", "texto-sec", etiqueta), elemento("strong", "", valor));
      return tarjeta;
    });
    metricas.replaceChildren(...tarjetas);
  }

  function dibujarFilas() {
    const busqueda = filtro.value.trim().toLocaleLowerCase("es");
    const filtradas = filas.filter((fila) => {
      if (soloVoz.checked && !fila.es_voz) return false;
      if (soloErrores.checked && !esError(fila)) return false;
      const texto = [
        fila.entrada, fila.intencion, fila.herramienta, fila.respuesta, fila.error,
      ].filter(Boolean).join(" ").toLocaleLowerCase("es");
      return !busqueda || texto.includes(busqueda);
    });
    if (!filtradas.length) {
      const vacio = elemento(
        "div",
        "vistas__vacio",
        filas.length ? "No hay interacciones que coincidan con estos filtros."
          : "Todavía no hay interacciones registradas.",
      );
      vacio.setAttribute("role", "status");
      tabla.replaceChildren(vacio);
      estado.textContent = vacio.textContent;
      return;
    }

    const contenedorTabla = elemento("div", "vistas__tabla-scroll");
    const tablaHtml = document.createElement("table");
    tablaHtml.className = "vistas__tabla";
    const cabecera = document.createElement("thead");
    const filaCabecera = document.createElement("tr");
    ["Hora", "Pregunta", "Intención", "Herramienta", "Tiempo total", "Desglose"].forEach((titulo) => {
      filaCabecera.append(elemento("th", "", titulo));
    });
    cabecera.append(filaCabecera);
    const cuerpo = document.createElement("tbody");
    filtradas.forEach((fila) => {
      const tr = document.createElement("tr");
      if (esError(fila)) {
        tr.classList.add("aviso--error");
        tr.title = fila.error;
      }
      const pregunta = elemento("span", "vistas__pregunta");
      pregunta.title = fila.entrada || "";
      pregunta.append(elemento(
        "span",
        "vistas__pregunta-texto",
        fila.entrada || "Pregunta no disponible",
      ));
      if (fila.es_voz) {
        const icono = elemento("span", "vistas__microfono");
        icono.innerHTML = microfono;
        icono.setAttribute("role", "img");
        icono.setAttribute("aria-label", "Consulta por voz");
        pregunta.append(icono);
      }
      const herramienta = elemento("span", "chip", fila.herramienta || "—");
      const campos = [
        ["Hora", horaVisible(fila.creado)],
        ["Pregunta", pregunta],
        ["Intención", fila.intencion || "—"],
        ["Herramienta", herramienta],
        ["Tiempo total", `${numero(fila.t_total_ms)} ms`],
        ["Desglose", barraTiempos(fila)],
      ];
      campos.forEach(([etiqueta, valor]) => {
        const td = document.createElement("td");
        td.dataset.label = etiqueta;
        if (typeof valor === "string") td.textContent = valor;
        else td.append(valor);
        tr.append(td);
      });
      cuerpo.append(tr);
    });
    tablaHtml.append(cabecera, cuerpo);
    contenedorTabla.append(tablaHtml);
    tabla.replaceChildren(contenedorTabla);
    estado.textContent = `Se muestran ${filtradas.length} de ${filas.length} interacciones.`;
  }

  function mostrarCargando() {
    tabla.setAttribute("aria-busy", "true");
    tabla.replaceChildren(elemento("p", "vistas__estado", "Cargando la bitácora…"));
    estado.textContent = "Cargando la bitácora…";
  }

  async function refrescar() {
    if (destruida) return;
    solicitudActiva?.abort();
    solicitudActiva = new AbortController();
    botonActualizar.disabled = true;
    mostrarCargando();
    try {
      const respuesta = await fetch("/api/bitacora?limite=50", {
        signal: solicitudActiva.signal,
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible consultar la bitácora.");
      if (destruida || solicitudActiva.signal.aborted) return;
      filas = Array.isArray(datos.resultados) ? datos.resultados : [];
      dibujarMetricas();
      dibujarFilas();
      tabla.setAttribute("aria-busy", "false");
    } catch (error) {
      if (error.name === "AbortError" || destruida) return;
      const aviso = elemento(
        "div",
        "aviso aviso--error",
        error.message || "No fue posible cargar la bitácora. Revisa tu conexión.",
      );
      aviso.setAttribute("role", "alert");
      tabla.replaceChildren(aviso);
      tabla.setAttribute("aria-busy", "false");
      estado.textContent = aviso.textContent;
    } finally {
      if (!destruida) botonActualizar.disabled = false;
    }
  }

  botonActualizar.addEventListener("click", () => void refrescar(), {
    signal: controlador.signal,
  });
  [filtro, soloVoz, soloErrores].forEach((control) => {
    control.addEventListener("input", dibujarFilas, { signal: controlador.signal });
    control.addEventListener("change", dibujarFilas, { signal: controlador.signal });
  });
  function vistaVisible() {
    if (document.visibilityState !== "visible") return false;
    const estilo = getComputedStyle(contenedor);
    if (estilo.display === "none" || estilo.visibility === "hidden" || estilo.opacity === "0") {
      return false;
    }
    if (observador) return interseccion;
    return contenedor.isConnected && contenedor.getClientRects().length > 0;
  }
  observador = "IntersectionObserver" in window
    ? new IntersectionObserver((entradas) => {
      interseccion = entradas.some((entrada) => entrada.isIntersecting);
    })
    : null;
  observador?.observe(contenedor);
  const temporizador = window.setInterval(() => {
    if (vistaVisible()) void refrescar();
  }, 20_000);
  document.addEventListener("visibilitychange", () => {
    if (vistaVisible()) void refrescar();
  }, { signal: controlador.signal });
  void refrescar();
  return {
    refrescar,
    destruir() {
      destruida = true;
      window.clearInterval(temporizador);
      observador?.disconnect();
      solicitudActiva?.abort();
      controlador.abort();
    },
  };
}
