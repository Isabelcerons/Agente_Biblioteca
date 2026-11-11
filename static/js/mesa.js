import { sintetizar } from "./api.js";
import { reproducirRespuesta, detenerAudioActual } from "./voz.js";

const CLAVE_MESA = "biblioteca-mesa-estudio";

// SVG estático para el ícono de mochila y marcador
const SVG_MOCHILA = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 10v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V10a5 5 0 0 0-5-5h-4a5 5 0 0 0-5 5z"/><path d="M9 5V3a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/><path d="M9 13h6"/><path d="M12 10v6"/></svg>';
const SVG_CHECK = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';

// Región accesible aria-live para notificar cambios a lectores de pantalla
let regionAriaLive = null;
function anunciarMesa(mensaje) {
  if (typeof document === "undefined" || !mensaje) return;
  try {
    if (!regionAriaLive || !regionAriaLive.isConnected) {
      regionAriaLive = document.getElementById("mesa-aria-live");
      if (!regionAriaLive) {
        regionAriaLive = document.createElement("div");
        regionAriaLive.id = "mesa-aria-live";
        regionAriaLive.className = "sr-only";
        regionAriaLive.setAttribute("role", "status");
        regionAriaLive.setAttribute("aria-live", "polite");
        regionAriaLive.setAttribute("aria-atomic", "true");
        document.body.append(regionAriaLive);
      }
    }
    regionAriaLive.textContent = "";
    window.requestAnimationFrame(() => {
      if (regionAriaLive) regionAriaLive.textContent = mensaje;
    });
  } catch {
    // Si falla el anuncio accesible, no interrumpe la ejecución
  }
}

// Carga segura de la mochila persistida en localStorage
function cargarMesa() {
  try {
    const crudo = localStorage.getItem(CLAVE_MESA);
    const lista = crudo ? JSON.parse(crudo) : [];
    return Array.isArray(lista) ? lista : [];
  } catch {
    return [];
  }
}

// Guarda en localStorage y emite evento global de sincronización
function guardarMesa(lista) {
  try {
    localStorage.setItem(CLAVE_MESA, JSON.stringify(lista));
  } catch {
    // Si localStorage está bloqueado o supera cuota, mantiene estado en sesión
  }
  window.dispatchEvent(new CustomEvent("mesa-cambio", { detail: { total: lista.length } }));
}

// Genera una clave única uniforme para comparar materiales o fuentes
export function obtenerClaveItem(itemOId) {
  if (itemOId == null) return "";
  if (typeof itemOId === "string" || typeof itemOId === "number") return `mat:${itemOId}`;
  if (itemOId.clave) return String(itemOId.clave);

  // Si es un fragmento de fuente (de Investigar)
  if (itemOId.tipo_item === "fuente" || (itemOId.texto && (itemOId.documento || itemOId.seccion))) {
    const doc = (itemOId.documento || "").trim().toLowerCase();
    const sec = (itemOId.seccion || "").trim().toLowerCase();
    const txt = (itemOId.texto || "").slice(0, 80).trim().toLowerCase();
    return `fuente:${itemOId.material_id ?? ""}:${doc}:${sec}:${txt}`;
  }

  // Si es un material del catálogo, vitrina o ficha
  if (itemOId.material_id != null) return `mat:${itemOId.material_id}`;
  if (itemOId.id != null) return `id:${itemOId.id}`;
  return "";
}

// Comprueba si un material o fragmento ya está guardado en la mochila
export function estaEnMesa(itemOId) {
  const claveBuscada = obtenerClaveItem(itemOId);
  if (!claveBuscada) return false;
  return cargarMesa().some((item) => obtenerClaveItem(item) === claveBuscada);
}

// Agrega o quita un material o fuente de la mochila de investigación
export function alternarEnMesa(elemento) {
  if (!elemento) return false;
  const clave = obtenerClaveItem(elemento);
  if (!clave) return false;

  const actual = cargarMesa();
  const existe = actual.some((item) => obtenerClaveItem(item) === clave);

  if (existe) {
    const filtrada = actual.filter((item) => obtenerClaveItem(item) !== clave);
    guardarMesa(filtrada);
    const nombre = elemento.titulo || elemento.documento || "elemento";
    anunciarMesa(`Eliminado de tu mochila: «${nombre}»`);
    return false;
  }

  // Guardar fragmento de fuente
  if (elemento.tipo_item === "fuente" || (elemento.texto && (elemento.documento || elemento.seccion))) {
    actual.push({
      clave,
      tipo_item: "fuente",
      documento: elemento.documento || "Documento sin título",
      seccion: elemento.seccion || "",
      texto: elemento.texto || "",
      material_id: elemento.material_id ?? null,
      similitud: elemento.similitud ?? null,
      titulo: elemento.documento ? `Fragmento de «${elemento.documento}»` : "Fragmento de fuente",
      autor: elemento.autor || "Institución Universitaria del Putumayo",
      anio: elemento.anio || "s. f.",
      tipo: "fuente",
    });
  } else {
    // Guardar material completo (libro, tesis, etc.)
    actual.push({
      clave,
      tipo_item: "material",
      material_id: elemento.material_id,
      titulo: elemento.titulo || "Material sin título",
      autor: elemento.autor || "Institución Universitaria del Putumayo",
      anio: elemento.anio || "s. f.",
      tipo: elemento.tipo || "libro",
      programa: elemento.programa || "",
      disponibles: Number(elemento.disponibles) || 0,
      total: Number(elemento.total) || 0,
    });
  }

  guardarMesa(actual);
  const nombre = elemento.titulo || elemento.documento || "material";
  anunciarMesa(`Guardado en tu mochila: «${nombre}»`);
  return true;
}

// Crea el botón accesible «Guardar en la mochila» para tarjetas y fichas
export function botonGuardarMesa(item, clase = "btn btn--fantasma") {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `btn-mochila ${clase}`;

  const icono = document.createElement("span");
  icono.className = "btn-mochila__icono";
  icono.setAttribute("aria-hidden", "true");

  const texto = document.createElement("span");
  texto.className = "btn-mochila__texto";

  btn.append(icono, texto);

  const nombreItem = item?.titulo || item?.documento || "material";

  const actualizar = () => {
    const guardado = estaEnMesa(item);
    btn.setAttribute("aria-pressed", String(guardado));
    btn.classList.toggle("btn-mochila--guardado", guardado);

    if (guardado) {
      icono.innerHTML = SVG_CHECK;
      texto.textContent = "Guardado ✓";
      btn.setAttribute("aria-label", `Guardado en la mochila: ${nombreItem}. Pulsa para quitar`);
      btn.title = `Guardado en la mochila: ${nombreItem} (pulsa para quitar)`;
    } else {
      icono.innerHTML = SVG_MOCHILA;
      texto.textContent = "Guardar en la mochila";
      btn.setAttribute("aria-label", `Guardar en la mochila: ${nombreItem}`);
      btn.title = `Guardar en la mochila: ${nombreItem}`;
    }
  };

  btn.addEventListener("click", (evento) => {
    evento.stopPropagation();
    alternarEnMesa(item);
    actualizar();
  });

  const alCambio = () => actualizar();
  window.addEventListener("mesa-cambio", alCambio);
  actualizar();
  return btn;
}

// Genera la referencia bibliográfica formal en norma APA 7
export function citaApa(item) {
  if (item.tipo_item === "fuente" || item.tipo === "fuente") {
    const doc = item.documento || "Institución Universitaria del Putumayo";
    const sec = item.seccion ? `, sección ${item.seccion}` : "";
    const fragmento = item.texto ? ` «${item.texto.replace(/\s+/g, " ").slice(0, 110)}…»` : "";
    return `Institución Universitaria del Putumayo (${item.anio || "s. f."}). ${doc}${sec}.${fragmento}`;
  }
  const autor = item.autor || "Institución Universitaria del Putumayo";
  const anio = item.anio || "s. f.";
  const tipo = item.tipo === "tesis" ? " [Tesis de grado, Institución Universitaria del Putumayo]." : ".";
  return `${autor} (${anio}). ${item.titulo}${tipo}`;
}

let mesaMontada = false;
let callbacksMesa = { alPreguntar: null, alVerMapa: null };

// Monta la mochila flotante de investigación en la interfaz
export function montarMesaEstudio({ alPreguntar, alVerMapa } = {}) {
  if (alPreguntar) callbacksMesa.alPreguntar = alPreguntar;
  if (alVerMapa) callbacksMesa.alVerMapa = alVerMapa;

  if (mesaMontada || typeof document === "undefined") return;
  mesaMontada = true;

  const botonFlotante = document.createElement("button");
  botonFlotante.type = "button";
  botonFlotante.className = "mesa-flotante-btn";
  botonFlotante.setAttribute("aria-label", "Abrir Mi mochila de investigación");

  const etiqueta = document.createElement("span");
  etiqueta.textContent = "🎒 Mi mochila";

  const contador = document.createElement("span");
  contador.className = "mesa-flotante-btn__contador";
  contador.textContent = "0";
  botonFlotante.append(etiqueta, contador);

  const modal = document.createElement("div");
  modal.className = "mesa-modal";
  modal.hidden = true;
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "mesa-modal-titulo");

  const panel = document.createElement("section");
  panel.className = "mesa-modal__panel";

  const cabecera = document.createElement("header");
  cabecera.className = "mesa-modal__cabecera";

  const titulo = document.createElement("h2");
  titulo.id = "mesa-modal-titulo";
  titulo.textContent = "🎒 Mi mochila de investigación";

  const cerrar = document.createElement("button");
  cerrar.type = "button";
  cerrar.className = "btn btn--fantasma";
  cerrar.textContent = "Cerrar";
  cerrar.setAttribute("aria-label", "Cerrar ventana de la mochila");
  cabecera.append(titulo, cerrar);

  const subtitulo = document.createElement("p");
  subtitulo.className = "texto-sec";
  subtitulo.textContent = "Guarda libros, tesis y fragmentos mientras exploras para escuchar un resumen general con tu voz elegida, consultarlos con el agente o descargar tus referencias en APA 7.";

  const lista = document.createElement("ul");
  lista.className = "mesa-lista";

  const contenedorVoz = document.createElement("div");
  const acciones = document.createElement("div");
  acciones.className = "mesa-modal__acciones";

  const btnEscuchar = document.createElement("button");
  btnEscuchar.type = "button";
  btnEscuchar.className = "btn btn--primario";
  btnEscuchar.textContent = "🔊 Escuchar resumen de mi mochila";

  const btnCopiarApa = document.createElement("button");
  btnCopiarApa.type = "button";
  btnCopiarApa.className = "btn btn--acento";
  btnCopiarApa.textContent = "📋 Copiar citas APA 7";

  const btnDescargar = document.createElement("button");
  btnDescargar.type = "button";
  btnDescargar.className = "btn btn--fantasma";
  btnDescargar.textContent = "⬇ Descargar plan (.md)";

  const btnVaciar = document.createElement("button");
  btnVaciar.type = "button";
  btnVaciar.className = "btn btn--fantasma";
  btnVaciar.textContent = "Vaciar mochila";

  acciones.append(btnEscuchar, btnCopiarApa, btnDescargar, btnVaciar);
  panel.append(cabecera, subtitulo, lista, contenedorVoz, acciones);
  modal.append(panel);
  document.body.append(botonFlotante, modal);

  const cerrarModal = () => {
    modal.hidden = true;
    detenerAudioActual();
    botonFlotante.focus();
  };

  const abrirModal = () => {
    pintar();
    modal.hidden = false;
    cerrar.focus();
  };

  function ejecutarPreguntar(texto) {
    cerrarModal();
    if (callbacksMesa.alPreguntar) callbacksMesa.alPreguntar(texto);
    else window.dispatchEvent(new CustomEvent("preguntar-agente", { detail: { texto } }));
  }

  function ejecutarVerMapa(materialId) {
    cerrarModal();
    if (callbacksMesa.alVerMapa) callbacksMesa.alVerMapa(materialId);
    else window.dispatchEvent(new CustomEvent("ver-en-mapa", { detail: { material_id: materialId } }));
  }

  function pintar() {
    const items = cargarMesa();
    contador.textContent = String(items.length);
    lista.replaceChildren();

    if (!items.length) {
      const vacio = document.createElement("li");
      vacio.className = "mesa-item mesa-item--vacio";
      vacio.textContent = "Tu mochila está vacía. Guarda libros, tesis o fragmentos con el botón «Guardar en la mochila» en el Catálogo, Investigar o el Chat.";
      lista.append(vacio);
      btnEscuchar.disabled = true;
      btnCopiarApa.disabled = true;
      btnDescargar.disabled = true;
      btnVaciar.disabled = true;
      return;
    }

    btnEscuchar.disabled = false;
    btnCopiarApa.disabled = false;
    btnDescargar.disabled = false;
    btnVaciar.disabled = false;

    items.forEach((item) => {
      const fila = document.createElement("li");
      fila.className = "mesa-item";

      const info = document.createElement("div");
      info.className = "mesa-item__info";

      const nombre = document.createElement("strong");
      const meta = document.createElement("small");

      if (item.tipo_item === "fuente" || item.tipo === "fuente") {
        nombre.textContent = item.documento || "Fragmento de fuente";
        meta.textContent = [item.seccion ? `Sección: ${item.seccion}` : "Fragmento literal", item.anio].filter(Boolean).join(" · ");
        info.append(nombre, meta);

        if (item.texto) {
          const cita = document.createElement("blockquote");
          cita.className = "mesa-item__cita";
          cita.textContent = item.texto.length > 140 ? `«${item.texto.slice(0, 140).trimEnd()}…»` : `«${item.texto}»`;
          info.append(cita);
        }
      } else {
        nombre.textContent = item.titulo;
        meta.textContent = `${item.autor} · ${item.anio} · ${item.tipo === "tesis" ? "Tesis" : "Libro"}`;
        info.append(nombre, meta);
      }

      const botones = document.createElement("div");
      botones.className = "catalogo__acciones";

      const preguntar = document.createElement("button");
      preguntar.type = "button";
      preguntar.className = "btn btn--fantasma";
      preguntar.textContent = "Preguntar";
      preguntar.setAttribute("aria-label", `Preguntar al agente sobre ${item.titulo || item.documento}`);
      preguntar.addEventListener("click", () => {
        const consulta = item.tipo_item === "fuente"
          ? (item.seccion ? `Cuéntame más sobre «${item.documento}» en la sección «${item.seccion}»` : `Cuéntame más sobre «${item.documento}»`)
          : `¿De qué trata «${item.titulo}»?`;
        ejecutarPreguntar(consulta);
      });

      botones.append(preguntar);

      if (item.material_id != null) {
        const mapa = document.createElement("button");
        mapa.type = "button";
        mapa.className = "btn btn--fantasma";
        mapa.textContent = "Mapa 2D";
        mapa.setAttribute("aria-label", `Ver ubicación de ${item.titulo || item.documento} en el mapa`);
        mapa.addEventListener("click", () => ejecutarVerMapa(item.material_id));
        botones.append(mapa);
      }

      const quitar = document.createElement("button");
      quitar.type = "button";
      quitar.className = "btn btn--fantasma";
      quitar.textContent = "Quitar";
      quitar.setAttribute("aria-label", `Quitar ${item.titulo || item.documento} de la mochila`);
      quitar.addEventListener("click", () => {
        alternarEnMesa(item);
        pintar();
      });

      botones.append(quitar);
      fila.append(info, botones);
      lista.append(fila);
    });
  }

  // Lectura por voz del resumen usando sintetizar de api.js (respeta la voz elegida)
  btnEscuchar.addEventListener("click", async () => {
    const items = cargarMesa();
    if (!items.length) return;

    btnEscuchar.disabled = true;
    btnEscuchar.textContent = "Sintetizando voz…";

    try {
      const total = items.length;
      const nombres = items.slice(0, 4).map((i, idx) => {
        const nombre = i.tipo_item === "fuente" ? (i.documento || "fragmento") : (i.titulo || "material");
        return `${idx + 1}, ${nombre}`;
      }).join("; ");

      const resumenTexto = `Tienes ${total} ${total === 1 ? "elemento guardado" : "elementos guardados"} en tu mochila de investigación: ${nombres}. Puedes pedir un resumen detallado o consultar las referencias en APA 7.`;
      const audio = await sintetizar(resumenTexto);
      contenedorVoz.replaceChildren();

      if (audio && audio.audio_wav_base64) {
        reproducirRespuesta(contenedorVoz, audio.audio_wav_base64, resumenTexto);
      } else {
        contenedorVoz.textContent = "No se recibió el audio de síntesis.";
      }
    } catch {
      contenedorVoz.textContent = "No se pudo sintetizar el resumen en voz.";
    } finally {
      btnEscuchar.disabled = false;
      btnEscuchar.textContent = "🔊 Escuchar resumen de mi mochila";
    }
  });

  // Copia de citas en APA 7 al portapapeles
  btnCopiarApa.addEventListener("click", async () => {
    const items = cargarMesa();
    const texto = items.map(citaApa).join("\n\n");
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(texto);
      } else {
        const area = document.createElement("textarea");
        area.value = texto;
        document.body.append(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      btnCopiarApa.textContent = "✓ Copiado en APA 7";
      anunciarMesa("Citas en formato APA 7 copiadas al portapapeles.");
      window.setTimeout(() => { btnCopiarApa.textContent = "📋 Copiar citas APA 7"; }, 2000);
    } catch {
      btnCopiarApa.textContent = "No se pudo copiar";
    }
  });

  // Descarga del plan de investigación estructurado en formato Markdown
  btnDescargar.addEventListener("click", () => {
    const items = cargarMesa();
    const lineas = [
      "# Mochila de Investigación · Biblioteca UniPutumayo",
      "",
      `Fecha: ${new Date().toLocaleDateString("es-CO")}`,
      "",
      "## Elementos guardados",
      ...items.map((i, idx) => {
        if (i.tipo_item === "fuente" || i.tipo === "fuente") {
          return `${idx + 1}. **${i.documento}**${i.seccion ? ` (${i.seccion})` : ""} — Fragmento de fuente\n   > "${(i.texto || "").replace(/\n/g, " ").slice(0, 200)}…"`;
        }
        return `${idx + 1}. **${i.titulo}** (${i.autor}, ${i.anio}) — ${i.tipo === "tesis" ? "Tesis" : "Libro"}`;
      }),
      "",
      "## Referencias en norma APA 7",
      ...items.map((i) => `- ${citaApa(i)}`),
      "",
    ];
    const blob = new Blob([lineas.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = "plan_investigacion_uniputumayo.md";
    enlace.click();
    URL.revokeObjectURL(url);
    anunciarMesa("Descargando plan de investigación en Markdown.");
  });

  // Vaciado de la mochila
  btnVaciar.addEventListener("click", () => {
    guardarMesa([]);
    detenerAudioActual();
    contenedorVoz.replaceChildren();
    pintar();
    anunciarMesa("Tu mochila ha sido vaciada.");
  });

  botonFlotante.addEventListener("click", abrirModal);
  cerrar.addEventListener("click", cerrarModal);

  modal.addEventListener("click", (evento) => {
    if (evento.target === modal) cerrarModal();
  });

  // Manejo de teclado: tecla Esc cierra el modal y devuelve el foco
  window.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape" && !modal.hidden) {
      evento.preventDefault();
      cerrarModal();
    }
  });

  window.addEventListener("mesa-cambio", pintar);
  pintar();
}

// Auto-montaje al cargar para asegurar que la mochila esté disponible en toda la aplicación
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => montarMesaEstudio(), { once: true });
  } else {
    setTimeout(() => montarMesaEstudio(), 0);
  }
}
