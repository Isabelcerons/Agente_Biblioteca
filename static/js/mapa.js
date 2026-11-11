const COLORES_CATEGORIA = {
  claro: {
    sistemas: "#B54A3C",
    agroforestal: "#2E7D4F",
    ambiental: "#2B7A99",
    administracion: "#8B5E3C",
    contaduria: "#7A4E9C",
    transversal: "#A07A00",
    otros: "#5F6B73",
  },
  oscuro: {
    sistemas: "#F08A7C",
    agroforestal: "#6CC08F",
    ambiental: "#6FBCD9",
    administracion: "#D9A577",
    contaduria: "#C29BE8",
    transversal: "#E8C14A",
    otros: "#A9B4BC",
  },
};

const COLORES_TIPO = {
  claro: ["#286A8A", "#A34F76", "#657B32", "#5C5B9A", "#A85D35", "#477A70"],
  oscuro: ["#78B8D5", "#D989AF", "#B2C875", "#A3A0E0", "#E0A078", "#82C5B5"],
};

export const PALETA_PROGRAMAS = COLORES_CATEGORIA;

export function normalizarPrograma(nombre) {
  return String(nombre || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export function clavePrograma(nombre) {
  const norm = normalizarPrograma(nombre);
  if (!norm) return "otros";
  if (norm.includes("sistema")) return "sistemas";
  if (norm.includes("agroforest")) return "agroforestal";
  if (norm.includes("ambiental")) return "ambiental";
  if (norm.includes("administra")) return "administracion";
  if (norm.includes("contadur")) return "contaduria";
  if (norm.includes("transversal")) return "transversal";
  return "otros";
}

export function colorPorPrograma(nombre, tema = "claro") {
  const clave = clavePrograma(nombre);
  const colores = PALETA_PROGRAMAS[tema] || PALETA_PROGRAMAS.claro;
  return colores[clave] || colores.otros;
}

const CATEGORIAS_CONOCIDAS = [
  ["ingenieria de sistemas", "sistemas"],
  ["sistemas", "sistemas"],
  ["ingenieria agroforestal", "agroforestal"],
  ["agroforestal", "agroforestal"],
  ["ingenieria ambiental", "ambiental"],
  ["ambiental", "ambiental"],
  ["administracion de empresas", "administracion"],
  ["administracion", "administracion"],
  ["contaduria publica", "contaduria"],
  ["contaduria", "contaduria"],
  ["transversal", "transversal"],
];

const EJEMPLOS = [
  "cómo proteger una red de una empresa",
  "cultivos de la Amazonía",
  "aprender a programar desde cero",
];

const limitar = (valor, minimo, maximo) =>
  Math.min(maximo, Math.max(minimo, valor));

function texto(elemento, valor) {
  elemento.textContent = valor ?? "";
}

function tipoVisible(tipo) {
  return {
    libro: "Libro",
    tesis: "Tesis",
    articulo: "Artículo",
    recurso_digital: "Recurso digital",
  }[tipo] || tipo || "Tipo no indicado";
}

export function montarMapa(contenedor, { alAbrirFicha, resaltar } = {}) {
  if (!(contenedor instanceof HTMLElement)) {
    throw new TypeError("El contenedor del mapa debe ser un elemento HTML.");
  }

  contenedor.innerHTML = `
    <style>
      .mapa { color: var(--texto); }
      .mapa__estilos { display: none; }
      .mapa__busqueda { display: grid; gap: var(--espacio-3); }
      .mapa__formulario { display: flex; flex-wrap: wrap; align-items: end; gap: var(--espacio-3); }
      .mapa__formulario .campo { flex: 1 1 280px; }
      .mapa__ejemplos { display: flex; flex-wrap: wrap; gap: var(--espacio-2); }
      .mapa__ejemplo { min-height: 36px; padding: 5px 10px; font-size: .88rem; }
      .mapa__controles { display: flex; flex-wrap: wrap; align-items: center; gap: var(--espacio-3); }
      .mapa__controles .campo { min-width: 180px; }
      .mapa__exploracion { display: grid; min-width: 0; grid-template-columns: minmax(0, 1fr) minmax(220px, 290px); gap: var(--espacio-4); align-items: start; }
      .mapa__exploracion--sin-cercanos { grid-template-columns: minmax(0, 1fr); }
      .mapa__lienzo { position: relative; container-type: inline-size; width: 100%; min-width: 0; overflow: hidden; border: 1px solid var(--borde); border-radius: var(--radio-lg); background: var(--superficie); }
      .mapa__canvas { display: block; width: 100%; min-width: 0; height: clamp(320px, min(70vh, 75cqw), 620px); touch-action: none; cursor: grab; }
      .mapa__canvas:active { cursor: grabbing; }
      .mapa__lienzo--listo .mapa__canvas { animation: mapa-aparecer 250ms ease-out both; }
      @keyframes mapa-aparecer { from { opacity: .35; } to { opacity: 1; } }
      .mapa__tooltip { position: absolute; z-index: 2; display: none; width: min(260px, calc(100% - 16px)); padding: 10px 12px; border: 1px solid var(--borde); border-radius: var(--radio); background: var(--superficie); box-shadow: var(--sombra-grande); pointer-events: none; font-size: .86rem; }
      .mapa__tooltip strong, .mapa__tooltip span { display: block; }
      .mapa__tooltip strong { line-height: 1.3; }
      .mapa__tooltip span { margin-top: 3px; color: var(--texto-sec); }
      .mapa__disponibilidad { font-weight: 600; }
      .mapa__panel-cercanos { max-height: 620px; overflow: auto; }
      .mapa__cercanos { display: grid; gap: var(--espacio-2); padding: 0; margin: var(--espacio-3) 0 0; list-style: none; }
      .mapa__cercano { display: grid; width: 100%; gap: 3px; padding: 10px 12px; border: 1px solid var(--borde); border-radius: var(--radio); background: var(--superficie); color: var(--texto); cursor: pointer; text-align: left; }
      .mapa__cercano:hover { background: var(--verde-claro); }
      .mapa__cercano small { color: var(--texto-sec); }
      .mapa__leyenda { margin-block: var(--espacio-3) var(--espacio-4); }
      .mapa__explicacion { margin-top: var(--espacio-3); color: var(--texto-sec); }
      .mapa__varianza { margin-top: 4px; font-size: .82rem; }
      .mapa__estado { margin-block: var(--espacio-3); }
      .mapa__fondo-ficha { position: fixed; z-index: 20; inset: 0; display: grid; place-items: center; padding: 16px; background: rgb(0 0 0 / 55%); }
      .mapa__ficha { width: min(680px, 100%); max-height: min(85vh, 850px); overflow: auto; }
      .mapa__ficha-cabecera { display: flex; justify-content: space-between; align-items: start; gap: var(--espacio-3); }
      .mapa__ficha h2 { overflow-wrap: anywhere; }
      .mapa__ejemplares { display: grid; gap: var(--espacio-2); padding-left: 20px; }
      .mapa__resumen { white-space: pre-wrap; }
      @media (max-width: 760px) {
        .mapa__exploracion { grid-template-columns: minmax(0, 1fr); }
        .mapa__panel-cercanos { max-height: none; }
        .mapa__canvas { height: clamp(320px, min(70vh, 75cqw), 480px); }
      }
      @media (max-width: 420px) {
        .mapa__formulario .btn { width: 100%; }
      }
      @media (prefers-reduced-motion: reduce) {
        .mapa__lienzo--listo .mapa__canvas { animation: none; }
      }
    </style>
    <section class="mapa" aria-label="Explorador del mapa del conocimiento">
      <div class="mapa__busqueda tarjeta">
        <form class="mapa__formulario">
          <label class="campo">Explora un tema
            <input class="mapa__entrada" type="search" maxlength="500" required
              placeholder="Escribe una pregunta o tema">
          </label>
          <button class="btn btn--primario" type="submit">Buscar en el mapa</button>
        </form>
        <div class="mapa__ejemplos" aria-label="Ejemplos de búsqueda"></div>
      </div>
      <div class="mapa__controles" style="margin-top: var(--espacio-4)">
        <label class="campo">Colorear por
          <select class="mapa__modo">
            <option value="programa">Programa</option>
            <option value="tipo">Tipo</option>
          </select>
        </label>
        <button class="btn btn--fantasma mapa__centrar" type="button">Centrar</button>
        <button class="btn btn--fantasma mapa__limpiar" type="button" hidden>Limpiar búsqueda</button>
      </div>
      <div class="mapa__leyenda leyenda" aria-label="Leyenda del mapa"></div>
      <p class="mapa__estado texto-sec" role="status" aria-live="polite">Cargando el mapa…</p>
      <div class="mapa__exploracion">
        <div class="mapa__lienzo">
          <canvas class="mapa__canvas" tabindex="0"
            aria-label="Mapa bidimensional de libros y tesis. Usa las flechas para recorrer materiales, Enter para abrir una ficha, y arrastra o usa la rueda para explorar.">
            El mapa requiere un navegador compatible con canvas.
          </canvas>
          <div class="mapa__tooltip" role="tooltip"></div>
        </div>
        <aside class="mapa__panel-cercanos tarjeta" aria-labelledby="mapa-cercanos-titulo" hidden>
          <h2 id="mapa-cercanos-titulo">Más cercanos</h2>
          <ol class="mapa__cercanos"></ol>
        </aside>
      </div>
      <p class="mapa__explicacion">Cada punto es un libro o tesis; los que hablan de temas parecidos quedan cerca. Así funciona pgvector.</p>
      <p class="mapa__varianza texto-sec"></p>
      <div class="mapa__fichas"></div>
    </section>
  `;

  const canvas = contenedor.querySelector(".mapa__canvas");
  const lienzo = contenedor.querySelector(".mapa__lienzo");
  const exploracion = contenedor.querySelector(".mapa__exploracion");
  exploracion.classList.add("mapa__exploracion--sin-cercanos");
  const tooltip = contenedor.querySelector(".mapa__tooltip");
  const estado = contenedor.querySelector(".mapa__estado");
  const entrada = contenedor.querySelector(".mapa__entrada");
  const formulario = contenedor.querySelector(".mapa__formulario");
  const panelCercanos = contenedor.querySelector(".mapa__panel-cercanos");
  const listaCercanos = contenedor.querySelector(".mapa__cercanos");
  const botonLimpiar = contenedor.querySelector(".mapa__limpiar");
  const leyenda = contenedor.querySelector(".mapa__leyenda");
  const modo = contenedor.querySelector(".mapa__modo");
  const varianzaTexto = contenedor.querySelector(".mapa__varianza");
  const ctx = canvas.getContext("2d");
  const reduccionMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)");
  const controladores = new AbortController();
  const opcionResaltado = resaltar ?? new URLSearchParams(window.location.search).get("resaltar");
  let observadorTamano;
  let observadorTema;
  let observadorVisibilidad;
  let temporizadorResaltado = 0;
  let animacionResaltado = 0;
  let animacionCentrado = 0;
  let destruido = false;

  const estadoMapa = {
    puntos: [],
    cercanos: [],
    consulta: null,
    limites: null,
    ancho: 0,
    alto: 0,
    escala: 1,
    desplazarX: 0,
    desplazarY: 0,
    arrastre: null,
    puntoActivo: -1,
    hover: null,
    dialogo: null,
    resaltadoId: null,
    resaltadoHasta: 0,
    resaltarPendiente: null,
    tooltipFijo: false,
  };

  function colorCss(variable, alternativa) {
    return getComputedStyle(document.documentElement).getPropertyValue(variable).trim()
      || alternativa;
  }

  function colorCategoria(nombre) {
    const tema = document.documentElement.dataset.tema === "oscuro" ? "oscuro" : "claro";
    if (modo && modo.value === "tipo") {
      const clave = normalizarPrograma(nombre);



      let hash = 2166136261;
      for (const caracter of clave) {
        hash = Math.imul(hash ^ caracter.charCodeAt(0), 16777619);
      }
      return COLORES_TIPO[tema][(hash >>> 0) % COLORES_TIPO[tema].length];
    }
    return colorPorPrograma(nombre, tema);
  }

  function categoria(punto) {
    return modo.value === "tipo"
      ? tipoVisible(punto.tipo)
      : punto.programa || "Sin programa";
  }

  function colorDe(punto) {
    return colorCategoria(categoria(punto));
  }

  function dibujarLeyenda() {
    const categorias = [...new Set(estadoMapa.puntos.map(categoria))].sort((a, b) =>
      a.localeCompare(b, "es"));
    leyenda.replaceChildren();
    categorias.forEach((nombre) => {
      const item = document.createElement("span");
      item.className = "leyenda__item";
      const muestra = document.createElement("i");
      muestra.className = "leyenda__color";
      muestra.style.backgroundColor = colorCategoria(nombre);
      const etiqueta = document.createElement("span");
      texto(etiqueta, nombre);
      item.append(muestra, etiqueta);
      leyenda.append(item);
    });
  }

  function limitesEscena() {
    const xs = estadoMapa.puntos.map((punto) => Number(punto.x));
    const ys = estadoMapa.puntos.map((punto) => Number(punto.y));
    if (estadoMapa.consulta) {
      xs.push(Number(estadoMapa.consulta.x));
      ys.push(Number(estadoMapa.consulta.y));
    }
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangoX = Math.max(maxX - minX, 1e-6);
    const rangoY = Math.max(maxY - minY, 1e-6);
    const margenX = rangoX * 0.08;
    const margenY = rangoY * 0.08;
    return {
      minX: minX - margenX,
      maxX: maxX + margenX,
      minY: minY - margenY,
      maxY: maxY + margenY,
    };
  }

  function aPantalla(x, y) {
    const limites = limitesEscena();
    const margen = 28;
    const ancho = Math.max(1, estadoMapa.ancho - margen * 2);
    const alto = Math.max(1, estadoMapa.alto - margen * 2);
    const baseX = margen + ((x - limites.minX) / (limites.maxX - limites.minX)) * ancho;
    const baseY = estadoMapa.alto - margen
      - ((y - limites.minY) / (limites.maxY - limites.minY)) * alto;
    const centroX = estadoMapa.ancho / 2;
    const centroY = estadoMapa.alto / 2;
    return {
      x: centroX + (baseX - centroX) * estadoMapa.escala + estadoMapa.desplazarX,
      y: centroY + (baseY - centroY) * estadoMapa.escala + estadoMapa.desplazarY,
    };
  }

  function puntosCercanos() {
    return new Set(estadoMapa.cercanos.map((punto) => punto.material_id));
  }

  function dibujarEstrella(x, y, radioExterior = 10, radioInterior = 4.5) {
    ctx.beginPath();
    for (let indice = 0; indice < 10; indice += 1) {
      const radio = indice % 2 === 0 ? radioExterior : radioInterior;
      const angulo = -Math.PI / 2 + (indice * Math.PI) / 5;
      const px = x + Math.cos(angulo) * radio;
      const py = y + Math.sin(angulo) * radio;
      if (indice === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  function dibujar() {
    if (!ctx || estadoMapa.ancho <= 0 || estadoMapa.alto <= 0) return;
    ctx.clearRect(0, 0, estadoMapa.ancho, estadoMapa.alto);
    const superficie = colorCss("--superficie", "#FFFDF8");
    const borde = colorCss("--borde", "#DDD5C7");
    ctx.fillStyle = superficie;
    ctx.fillRect(0, 0, estadoMapa.ancho, estadoMapa.alto);

    if (!estadoMapa.puntos.length) return;

    const cercanos = puntosCercanos();
    if (estadoMapa.consulta) {
      const origen = aPantalla(estadoMapa.consulta.x, estadoMapa.consulta.y);
      for (const punto of estadoMapa.cercanos) {
        const material = estadoMapa.puntos.find(
          (elemento) => elemento.material_id === punto.material_id,
        );
        if (!material) continue;
        const destino = aPantalla(material.x, material.y);
        const similitud = limitar(Number(punto.similitud) || 0, 0, 1);
        ctx.beginPath();
        ctx.moveTo(origen.x, origen.y);
        ctx.lineTo(destino.x, destino.y);
        ctx.strokeStyle = colorCss("--laton", "#C9A227");
        ctx.globalAlpha = 0.2 + similitud * 0.65;
        ctx.lineWidth = 0.7 + similitud * 1.8;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    estadoMapa.puntos.forEach((punto, indice) => {
      const posicion = aPantalla(punto.x, punto.y);
      const destacado = cercanos.has(punto.material_id);
      const resaltado = String(punto.material_id) === String(estadoMapa.resaltadoId)
        && performance.now() < estadoMapa.resaltadoHasta;
      const atenuado = estadoMapa.consulta && !destacado;
      const radio = destacado || resaltado ? 9 : 6;
      ctx.globalAlpha = atenuado ? 0.22 : 1;
      ctx.fillStyle = colorDe(punto);
      ctx.strokeStyle = colorCss("--superficie", "#FFFDF8");
      ctx.lineWidth = 1.7;
      if (punto.tipo === "tesis") {
        ctx.beginPath();
        ctx.moveTo(posicion.x, posicion.y - radio);
        ctx.lineTo(posicion.x + radio, posicion.y);
        ctx.lineTo(posicion.x, posicion.y + radio);
        ctx.lineTo(posicion.x - radio, posicion.y);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.strokeStyle = colorCss("--madera", "#8B5E3C");
        ctx.lineWidth = 1.25;
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.arc(posicion.x, posicion.y, radio, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }
      if (destacado) {
        ctx.beginPath();
        ctx.arc(posicion.x, posicion.y, radio + 4, 0, Math.PI * 2);
        ctx.strokeStyle = colorCss("--laton", "#C9A227");
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
      if (resaltado) {
        const progreso = 1 - (estadoMapa.resaltadoHasta - performance.now()) / 2000;
        const pulso = reduccionMovimiento.matches ? 0 : (1 + Math.sin(progreso * Math.PI * 8)) / 2;
        ctx.beginPath();
        ctx.arc(posicion.x, posicion.y, radio + 8 + pulso * 9, 0, Math.PI * 2);
        ctx.strokeStyle = colorCss("--laton", "#C9A227");
        ctx.globalAlpha = 1 - pulso * 0.3;
        ctx.lineWidth = 3;
        ctx.stroke();
      }
      if (indice === estadoMapa.puntoActivo) {
        ctx.beginPath();
        ctx.arc(posicion.x, posicion.y, radio + 7, 0, Math.PI * 2);
        ctx.strokeStyle = colorCss("--texto", "#2A2A28");
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    });

    if (estadoMapa.consulta) {
      const posicion = aPantalla(estadoMapa.consulta.x, estadoMapa.consulta.y);
      ctx.save();
      ctx.fillStyle = colorCss("--laton", "#C9A227");
      ctx.strokeStyle = colorCss("--texto", "#2A2A28");
      ctx.lineWidth = 1;
      dibujarEstrella(posicion.x, posicion.y);
      ctx.restore();
      ctx.fillStyle = colorCss("--texto", "#2A2A28");
      ctx.font = "600 12px Inter, sans-serif";
      ctx.textAlign = "left";
      ctx.fillText("Tu búsqueda", posicion.x + 13, posicion.y - 9);
    }

    ctx.strokeStyle = borde;
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, estadoMapa.ancho - 1, estadoMapa.alto - 1);
  }

  function posicionPunto(evento) {
    const rect = canvas.getBoundingClientRect();
    const x = evento.clientX - rect.left;
    const y = evento.clientY - rect.top;
    let masCercano = null;
    let menorDistancia = 16;
    estadoMapa.puntos.forEach((punto) => {
      const posicion = aPantalla(punto.x, punto.y);
      const distancia = Math.hypot(posicion.x - x, posicion.y - y);
      if (distancia < menorDistancia) {
        menorDistancia = distancia;
        masCercano = punto;
      }
    });
    return masCercano;
  }

  function mostrarTooltip(punto, evento) {
    if (!punto) {
      if (estadoMapa.tooltipFijo && performance.now() < estadoMapa.resaltadoHasta) return;
      tooltip.style.display = "none";
      estadoMapa.hover = null;
      return;
    }
    estadoMapa.tooltipFijo = false;
    estadoMapa.hover = punto;
    tooltip.replaceChildren();
    const titulo = document.createElement("strong");
    texto(titulo, punto.titulo);
    const autor = document.createElement("span");
    texto(autor, `${punto.autor || "Autor no indicado"}${punto.anio ? ` · ${punto.anio}` : ""}`);
    const tipo = document.createElement("span");
    texto(tipo, tipoVisible(punto.tipo));
    const disponibles = Number(punto.disponibles) || 0;
    const total = Number(punto.total) || 0;
    const disponibilidad = document.createElement("span");
    disponibilidad.className = "mapa__disponibilidad";
    disponibilidad.style.color = colorCss(
      disponibles > 0 ? "--disponible-texto" : "--prestado-texto",
      disponibles > 0 ? "#23633E" : "#9A3B2F",
    );
    texto(disponibilidad, `${disponibles} de ${total} disponibles`);
    tooltip.append(titulo, autor, tipo, disponibilidad);
    const rect = lienzo.getBoundingClientRect();
    const ancho = tooltip.offsetWidth || 250;
    const alto = tooltip.offsetHeight || 105;
    tooltip.style.left = `${limitar(evento.clientX - rect.left + 12, 8, rect.width - ancho - 8)}px`;
    tooltip.style.top = `${limitar(evento.clientY - rect.top + 12, 8, rect.height - alto - 8)}px`;
    tooltip.style.display = "block";
  }

  function mostrarTooltipFijo(punto) {
    const posicion = aPantalla(punto.x, punto.y);
    const rect = canvas.getBoundingClientRect();
    estadoMapa.tooltipFijo = true;
    mostrarTooltip(punto, {
      clientX: rect.left + posicion.x,
      clientY: rect.top + posicion.y,
    });
    estadoMapa.tooltipFijo = true;
  }

  function resaltarMaterial(id) {
    if (destruido || id === null || id === undefined || String(id).trim() === "") return;
    if (!estadoMapa.puntos.length) {
      estadoMapa.resaltarPendiente = id;
      return;
    }
    if (!estadoMapa.ancho || !estadoMapa.alto) {
      estadoMapa.resaltarPendiente = id;
      return;
    }
    const punto = estadoMapa.puntos.find(
      (elemento) => String(elemento.material_id) === String(id),
    );
    if (!punto) {
      estadoMapa.resaltarPendiente = null;
      texto(estado, "No encontré ese material en el mapa.");
      return;
    }
    estadoMapa.resaltarPendiente = null;
    estadoMapa.resaltadoId = punto.material_id;
    estadoMapa.resaltadoHasta = performance.now() + 2000;
    estadoMapa.puntoActivo = estadoMapa.puntos.indexOf(punto);
    estadoMapa.escala = 1;
    estadoMapa.desplazarX = 0;
    estadoMapa.desplazarY = 0;
    const posicionInicial = aPantalla(punto.x, punto.y);
    const escalaFinal = 2.8;
    const desplazamientoFinalX =
      (estadoMapa.ancho / 2 - posicionInicial.x) * escalaFinal;
    const desplazamientoFinalY =
      (estadoMapa.alto / 2 - posicionInicial.y) * escalaFinal;
    if (animacionCentrado) cancelAnimationFrame(animacionCentrado);
    if (reduccionMovimiento.matches) {
      estadoMapa.escala = escalaFinal;
      estadoMapa.desplazarX = desplazamientoFinalX;
      estadoMapa.desplazarY = desplazamientoFinalY;
      mostrarTooltipFijo(punto);
    } else {
      tooltip.style.display = "none";
      const inicio = performance.now();
      const animarCentrado = (ahora) => {
        if (destruido) return;
        const progreso = limitar((ahora - inicio) / 360, 0, 1);
        const suave = progreso * progreso * (3 - 2 * progreso);
        estadoMapa.escala = 1 + (escalaFinal - 1) * suave;
        estadoMapa.desplazarX = desplazamientoFinalX * suave;
        estadoMapa.desplazarY = desplazamientoFinalY * suave;
        dibujar();
        if (progreso < 1) {
          animacionCentrado = requestAnimationFrame(animarCentrado);
        } else {
          mostrarTooltipFijo(punto);
          animacionCentrado = 0;
        }
      };
      animacionCentrado = requestAnimationFrame(animarCentrado);
    }
    texto(estado, `Mostrando «${punto.titulo}» en el mapa`);
    window.clearTimeout(temporizadorResaltado);
    if (animacionResaltado) cancelAnimationFrame(animacionResaltado);
    const animarAnillo = () => {
      if (destruido) return;
      dibujar();
      if (performance.now() < estadoMapa.resaltadoHasta) {
        animacionResaltado = requestAnimationFrame(animarAnillo);
      } else {
        estadoMapa.resaltadoId = null;
        estadoMapa.tooltipFijo = false;
        tooltip.style.display = "none";
        dibujar();
      }
    };
    if (!reduccionMovimiento.matches) {
      animacionResaltado = requestAnimationFrame(animarAnillo);
    } else {
      dibujar();
      temporizadorResaltado = window.setTimeout(() => {
        estadoMapa.resaltadoId = null;
        estadoMapa.tooltipFijo = false;
        tooltip.style.display = "none";
        dibujar();
      }, 2000);
    }
  }

  async function abrirFicha(materialId, origen = document.activeElement) {
    if (alAbrirFicha) {
      alAbrirFicha(materialId);
      return;
    }
    const fondo = document.createElement("div");
    fondo.className = "mapa__fondo-ficha";
    fondo.innerHTML = `
      <article class="mapa__ficha tarjeta" role="dialog" aria-modal="true"
        aria-labelledby="mapa-ficha-titulo" tabindex="-1">
        <div class="mapa__ficha-cabecera">
          <div><p class="texto-sec">Ficha del material</p><h2 id="mapa-ficha-titulo">Cargando…</h2></div>
          <button class="btn btn--icono mapa__cerrar" type="button" aria-label="Cerrar ficha">×</button>
        </div>
        <div class="mapa__ficha-contenido" aria-live="polite"></div>
      </article>
    `;
    contenedor.querySelector(".mapa__fichas").append(fondo);
    const dialogo = fondo.querySelector(".mapa__ficha");
    const cerrar = () => {
      fondo.remove();
      estadoMapa.dialogo = null;
      if (origen instanceof HTMLElement && origen.isConnected) origen.focus();
    };
    estadoMapa.dialogo = { fondo, cerrar };
    fondo.querySelector(".mapa__cerrar").addEventListener("click", cerrar, {
      signal: controladores.signal,
    });
    fondo.addEventListener("click", (evento) => {
      if (evento.target === fondo) cerrar();
    }, { signal: controladores.signal });
    fondo.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape") {
        evento.preventDefault();
        cerrar();
      } else if (evento.key === "Tab") {
        const enfocados = [...fondo.querySelectorAll(
          'button:not(:disabled), a[href], input:not(:disabled), [tabindex]:not([tabindex="-1"])',
        )];
        if (!enfocados.length) return;
        const primero = enfocados[0];
        const ultimo = enfocados[enfocados.length - 1];
        if (evento.shiftKey && (
          document.activeElement === primero || document.activeElement === dialogo
        )) {
          evento.preventDefault();
          ultimo.focus();
        } else if (!evento.shiftKey && (
          document.activeElement === ultimo || document.activeElement === dialogo
        )) {
          evento.preventDefault();
          primero.focus();
        }
      }
    }, { signal: controladores.signal });
    dialogo.focus();
    try {
      const respuesta = await fetch(`/api/material/${encodeURIComponent(materialId)}`, {
        signal: controladores.signal,
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible cargar la ficha.");
      texto(fondo.querySelector("#mapa-ficha-titulo"), datos.titulo);
      const contenido = fondo.querySelector(".mapa__ficha-contenido");
      const autor = document.createElement("p");
      autor.className = "texto-sec";
      texto(
        autor,
        [datos.autor, datos.anio, datos.editorial].filter(Boolean).join(" · "),
      );
      const detalles = document.createElement("p");
      texto(
        detalles,
        [tipoVisible(datos.tipo), datos.programa, datos.tema].filter(Boolean).join(" · "),
      );
      contenido.append(autor, detalles);
      if (datos.ejemplares?.length) {
        const tituloEjemplares = document.createElement("h3");
        tituloEjemplares.textContent = "Ejemplares";
        const ejemplares = document.createElement("ul");
        ejemplares.className = "mapa__ejemplares";
        for (const ejemplar of datos.ejemplares) {
          const item = document.createElement("li");
          item.textContent = `${ejemplar.estante || "Sin estante"} · ${ejemplar.estado}`;
          ejemplares.append(item);
        }
        contenido.append(tituloEjemplares, ejemplares);
      }
      if (datos.resumen) {
        const tituloResumen = document.createElement("h3");
        tituloResumen.textContent = "Resumen";
        const resumen = document.createElement("p");
        resumen.className = "mapa__resumen";
        texto(resumen, datos.resumen);
        contenido.append(tituloResumen, resumen);
      }
    } catch (error) {
      if (error.name === "AbortError" || destruido) return;
      const mensaje = document.createElement("p");
      mensaje.className = "aviso aviso--error";
      texto(mensaje, error.message || "No fue posible cargar la ficha.");
      fondo.querySelector(".mapa__ficha-contenido").replaceChildren(mensaje);
    }
  }

  function anunciarPunto() {
    const punto = estadoMapa.puntos[estadoMapa.puntoActivo];
    if (!punto) return;
    texto(
      estado,
      `${estadoMapa.puntoActivo + 1} de ${estadoMapa.puntos.length}: ${punto.titulo}, `
      + `${punto.autor || "autor no indicado"}${punto.anio ? `, ${punto.anio}` : ""}.`,
    );
    dibujar();
  }

  function renderizarCercanos(cercanos) {
    estadoMapa.cercanos = cercanos;
    exploracion.classList.toggle("mapa__exploracion--sin-cercanos", !cercanos.length);
    listaCercanos.replaceChildren();
    for (const punto of cercanos) {
      const item = document.createElement("li");
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "mapa__cercano";
      const titulo = document.createElement("span");
      texto(titulo, punto.titulo);
      const similitud = document.createElement("small");
      texto(similitud, `${Math.round(Number(punto.similitud) * 100)} % de similitud`);
      boton.append(titulo, similitud);
      boton.addEventListener("click", () => abrirFicha(punto.material_id, boton), {
        signal: controladores.signal,
      });
      item.append(boton);
      listaCercanos.append(item);
    }
    panelCercanos.hidden = !cercanos.length;
    botonLimpiar.hidden = false;
  }

  async function buscar(consulta) {
    if (!consulta.trim()) return;
    estado.setAttribute("aria-busy", "true");
    texto(estado, "Proyectando tu búsqueda…");
    try {
      const respuesta = await fetch(
        `/api/mapa/proyectar?q=${encodeURIComponent(consulta.trim())}&k=5`,
        { signal: controladores.signal },
      );
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible proyectar la búsqueda.");
      estadoMapa.consulta = { x: datos.x, y: datos.y };
      renderizarCercanos(datos.cercanos || []);
      estadoMapa.escala = 1;
      estadoMapa.desplazarX = 0;
      estadoMapa.desplazarY = 0;
      texto(estado, `Búsqueda proyectada. ${datos.cercanos?.length || 0} materiales cercanos.`);
      dibujar();
    } catch (error) {
      if (error.name === "AbortError" || destruido) return;
      texto(estado, error.message || "Error de red al proyectar la búsqueda.");
    } finally {
      estado.removeAttribute("aria-busy");
    }
  }

  function limpiarBusqueda() {
    estadoMapa.consulta = null;
    estadoMapa.cercanos = [];
    entrada.value = "";
    renderizarCercanos([]);
    botonLimpiar.hidden = true;
    estadoMapa.escala = 1;
    estadoMapa.desplazarX = 0;
    estadoMapa.desplazarY = 0;
    texto(estado, `${estadoMapa.puntos.length} materiales en el mapa.`);
    dibujar();
  }

  function centrar() {
    estadoMapa.escala = 1;
    estadoMapa.desplazarX = 0;
    estadoMapa.desplazarY = 0;
    dibujar();
  }

  function redimensionar() {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = window.devicePixelRatio || 1;
    estadoMapa.ancho = rect.width;
    estadoMapa.alto = rect.height;
    canvas.width = Math.round(rect.width * ratio);
    canvas.height = Math.round(rect.height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    dibujar();
    if (estadoMapa.resaltarPendiente !== null && estadoMapa.puntos.length) {
      resaltarMaterial(estadoMapa.resaltarPendiente);
    }
  }

  contenedor.querySelector(".mapa__ejemplos").replaceChildren(
    ...EJEMPLOS.map((ejemplo) => {
      const boton = document.createElement("button");
      boton.className = "btn btn--fantasma mapa__ejemplo";
      boton.type = "button";
      texto(boton, ejemplo);
      boton.addEventListener("click", () => {
        entrada.value = ejemplo;
        buscar(ejemplo);
      }, { signal: controladores.signal });
      return boton;
    }),
  );
  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    buscar(entrada.value);
  }, { signal: controladores.signal });
  contenedor.querySelector(".mapa__centrar").addEventListener("click", centrar, {
    signal: controladores.signal,
  });
  botonLimpiar.addEventListener("click", limpiarBusqueda, { signal: controladores.signal });
  modo.addEventListener("change", () => {
    dibujarLeyenda();
    dibujar();
  }, { signal: controladores.signal });

  canvas.addEventListener("pointerdown", (evento) => {
    canvas.setPointerCapture(evento.pointerId);
    estadoMapa.arrastre = {
      x: evento.clientX,
      y: evento.clientY,
      inicialX: estadoMapa.desplazarX,
      inicialY: estadoMapa.desplazarY,
      movimiento: false,
    };
  }, { signal: controladores.signal });
  canvas.addEventListener("pointermove", (evento) => {
    if (estadoMapa.arrastre) {
      const dx = evento.clientX - estadoMapa.arrastre.x;
      const dy = evento.clientY - estadoMapa.arrastre.y;
      if (Math.hypot(dx, dy) > 3) estadoMapa.arrastre.movimiento = true;
      estadoMapa.desplazarX = estadoMapa.arrastre.inicialX + dx;
      estadoMapa.desplazarY = estadoMapa.arrastre.inicialY + dy;
      dibujar();
      return;
    }
    if (estadoMapa.tooltipFijo && performance.now() < estadoMapa.resaltadoHasta) return;
    const punto = posicionPunto(evento);
    mostrarTooltip(punto, evento);
    canvas.style.cursor = punto ? "pointer" : "grab";
  }, { signal: controladores.signal });
  canvas.addEventListener("pointerup", (evento) => {
    const arrastre = estadoMapa.arrastre;
    estadoMapa.arrastre = null;
    if (arrastre && !arrastre.movimiento) {
      const punto = posicionPunto(evento);
      if (punto) abrirFicha(punto.material_id, canvas);
    }
  }, { signal: controladores.signal });
  canvas.addEventListener("pointercancel", () => {
    estadoMapa.arrastre = null;
  }, { signal: controladores.signal });
  canvas.addEventListener("pointerleave", () => {
    if (!estadoMapa.arrastre && !estadoMapa.tooltipFijo) tooltip.style.display = "none";
  }, { signal: controladores.signal });
  canvas.addEventListener("wheel", (evento) => {
    evento.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const x = evento.clientX - rect.left;
    const y = evento.clientY - rect.top;
    const centroX = estadoMapa.ancho / 2;
    const centroY = estadoMapa.alto / 2;
    const factor = evento.deltaY < 0 ? 1.12 : 1 / 1.12;
    const nuevaEscala = limitar(estadoMapa.escala * factor, 0.65, 12);
    const puntoX = (x - centroX - estadoMapa.desplazarX) / estadoMapa.escala;
    const puntoY = (y - centroY - estadoMapa.desplazarY) / estadoMapa.escala;
    estadoMapa.escala = nuevaEscala;
    estadoMapa.desplazarX = x - centroX - puntoX * nuevaEscala;
    estadoMapa.desplazarY = y - centroY - puntoY * nuevaEscala;
    dibujar();
  }, { passive: false, signal: controladores.signal });
  canvas.addEventListener("keydown", (evento) => {
    if (!estadoMapa.puntos.length) return;
    const cambio = {
      ArrowRight: 1,
      ArrowDown: 1,
      ArrowLeft: -1,
      ArrowUp: -1,
    }[evento.key];
    if (cambio) {
      evento.preventDefault();
      estadoMapa.puntoActivo = estadoMapa.puntoActivo < 0
        ? (cambio > 0 ? 0 : estadoMapa.puntos.length - 1)
        : (estadoMapa.puntoActivo + cambio + estadoMapa.puntos.length)
          % estadoMapa.puntos.length;
      anunciarPunto();
    } else if (evento.key === "Enter" && estadoMapa.puntos[estadoMapa.puntoActivo]) {
      evento.preventDefault();
      abrirFicha(estadoMapa.puntos[estadoMapa.puntoActivo].material_id, canvas);
    }
  }, { signal: controladores.signal });

  observadorTamano = new ResizeObserver(redimensionar);
  observadorTamano.observe(canvas);
  observadorTamano.observe(lienzo);
  observadorTamano.observe(contenedor);
  if ("IntersectionObserver" in window) {
    observadorVisibilidad = new IntersectionObserver((entradas) => {
      if (entradas.some((entrada) => entrada.isIntersecting)) redimensionar();
    });
    observadorVisibilidad.observe(contenedor);
  }
  window.addEventListener("resize", redimensionar, { signal: controladores.signal });
  redimensionar();
  observadorTema = new MutationObserver(() => {
    dibujarLeyenda();
    dibujar();
  });
  observadorTema.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-tema"],
  });

  if (opcionResaltado !== null && opcionResaltado !== undefined) {
    estadoMapa.resaltarPendiente = opcionResaltado;
  }
  void (async () => {
    try {
      const respuesta = await fetch("/api/mapa", { signal: controladores.signal });
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible cargar el mapa.");
      if (destruido) return;
      estadoMapa.puntos = datos.puntos || [];
      estadoMapa.limites = datos.limites || null;
      const porcentaje = (datos.varianza_explicada || [])
        .reduce((total, valor) => total + Number(valor || 0), 0) * 100;
      texto(
        varianzaTexto,
        `Este plano conserva el ${porcentaje.toFixed(1)} % de la información de los 768 números de cada embedding`,
      );
      dibujarLeyenda();
      if (!estadoMapa.puntos.length) {
        texto(estado, "Aún no hay mapa: ejecute python calcular_mapa.py");
        return;
      }
      texto(estado, `${estadoMapa.puntos.length} materiales en el mapa.`);
      lienzo.classList.add("mapa__lienzo--listo");
      if (reduccionMovimiento.matches) lienzo.classList.remove("mapa__lienzo--listo");
      dibujar();
      if (estadoMapa.resaltarPendiente !== null) {
        resaltarMaterial(estadoMapa.resaltarPendiente);
      }
    } catch (error) {
      if (error.name === "AbortError" || destruido) return;
      texto(estado, error.message || "Error de red: no fue posible cargar el mapa.");
      estado.classList.add("aviso", "aviso--error");
    }
  })();

  function destruir() {
    if (destruido) return;
    destruido = true;
    controladores.abort();
    observadorTamano?.disconnect();
    observadorTema?.disconnect();
    observadorVisibilidad?.disconnect();
    window.clearTimeout(temporizadorResaltado);
    if (animacionResaltado) cancelAnimationFrame(animacionResaltado);
    if (animacionCentrado) cancelAnimationFrame(animacionCentrado);
    if (estadoMapa.dialogo) estadoMapa.dialogo.cerrar();
    tooltip.style.display = "none";
  }

  return { resaltarMaterial, destruir };
}
