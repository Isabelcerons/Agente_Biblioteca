import { convertirAWav16k } from "./wav.js";
import { enviarVoz, enviarChat } from "./api.js";
import { microfono, detener, play, repetir } from "./iconos.js";

let audioActual = null;
let contextoAudio = null;
let cuadroAnimacion = 0;
let urlAudioActual = null;
let orbeActual = null;
let finalizarAudio = null;

export async function procesarAudio(wav, conversacionId, { entradaSegura, alTranscripcion, alEstado, vigente = () => true } = {}) {
  if (entradaSegura) return enviarVoz(wav, conversacionId);
  const formulario = new FormData();
  formulario.append("audio", wav, "consulta.wav");
  if (conversacionId) formulario.append("conversacion_id", conversacionId);
  const respuesta = await fetch("/api/transcribir", { method: "POST", body: formulario, credentials: "same-origin" });
  if (!vigente()) return null;
  if ([404, 405].includes(respuesta.status)) return enviarVoz(wav, conversacionId);
  if (!respuesta.ok) throw new Error("No se pudo transcribir la voz.");
  const datos = await respuesta.json();
  if (!vigente()) return null;
  if (datos.requiere_envio_seguro) return enviarVoz(wav, conversacionId);
  const texto = String(datos.transcripcion || "").trim();
  if (!texto) throw new Error("No se detectó voz. Inténtalo de nuevo.");
  alTranscripcion?.(texto);
  alEstado?.("Buscando en el catálogo…");
  const resultado = await enviarChat(texto, conversacionId, false);
  return {
    ...resultado,
    tiempos: { ...resultado.tiempos, t_stt_ms: datos.t_stt_ms ?? resultado.tiempos?.t_stt_ms },
    transcripcion: texto,
    transcripcion_mostrada: true,
  };
}

export function detenerAudioActual() {
  finalizarAudio?.(false);
  finalizarAudio = null;
  if (cuadroAnimacion) cancelAnimationFrame(cuadroAnimacion);
  cuadroAnimacion = 0;
  if (orbeActual) {
    orbeActual.style.transform = "";
    orbeActual.style.opacity = "";
    orbeActual.setAttribute("aria-label", "La voz del agente está en reposo");
  }
  orbeActual = null;
  if (audioActual) {
    audioActual.pause();
    audioActual.currentTime = 0;
    audioActual.removeAttribute("src");
    audioActual.load();
  }
  audioActual = null;
  if (urlAudioActual) URL.revokeObjectURL(urlAudioActual);
  urlAudioActual = null;
  if (contextoAudio && contextoAudio.state !== "closed") contextoAudio.close().catch(() => {});
  contextoAudio = null;
}

function boton(texto, icono, clase = "btn btn--fantasma") {
  const elemento = document.createElement("button");
  elemento.type = "button";
  elemento.className = clase;
  elemento.innerHTML = `${icono}<span>${texto}</span>`;
  return elemento;
}

export function reproducirRespuesta(contenedor, base64, texto = "") {
  detenerAudioActual();
  const controles = document.createElement("div");
  controles.className = "orbita-voz";
  const orbe = document.createElement("span");
  orbe.className = "orbe-voz";
  orbe.setAttribute("aria-label", "La voz del agente está en reposo");
  orbeActual = orbe;
  const pausar = boton("Pausar", detener);
  const repetirBoton = boton("Repetir", repetir);
  controles.append(orbe, pausar, repetirBoton);
  contenedor.append(controles);

  const url = base64
    ? URL.createObjectURL(new Blob([Uint8Array.from(atob(base64), (caracter) => caracter.charCodeAt(0))], { type: "audio/wav" }))
    : null;
  if (!url) {
    orbe.setAttribute("aria-label", "No se recibió el audio");
    pausar.disabled = true;
    repetirBoton.disabled = true;
    return { iniciar: () => {} };
  }

  urlAudioActual = url;
  const audio = new Audio(url);
  let resolver;
  const terminado = new Promise((resolve) => { resolver = resolve; });
  finalizarAudio = resolver;
  audio.addEventListener("ended", () => resolver(true), { once: true });
  audio.addEventListener("error", () => resolver(false), { once: true });
  audioActual = audio;
  let fuente;
  let analizador;
  let datos;
  const reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  try {
    contextoAudio = new (window.AudioContext || window.webkitAudioContext)();
    fuente = contextoAudio.createMediaElementSource(audio);
    analizador = contextoAudio.createAnalyser();
    analizador.fftSize = 128;
    datos = new Uint8Array(analizador.frequencyBinCount);
    fuente.connect(analizador);
    analizador.connect(contextoAudio.destination);
  } catch {
    contextoAudio = null;
    fuente = null;
  }

  const animar = () => {
    if (!analizador || !audio || audio.paused) return;
    analizador.getByteTimeDomainData(datos);
    const energia = datos.reduce((acumulado, valor) => acumulado + Math.abs(valor - 128), 0) / datos.length / 128;
    if (reducido) {
      orbe.style.opacity = String(.58 + energia * .42);
    } else {
      const escala = 1 + Math.min(.38, energia * .9);
      orbe.style.transform = `scale(${escala})`;
      orbe.style.boxShadow = `0 0 ${12 + energia * 34}px rgb(201 162 39 / ${.35 + energia * .55})`;
    }
    cuadroAnimacion = requestAnimationFrame(animar);
  };

  const iniciar = async () => {
    if (audioActual !== audio) return;
    try {
      if (contextoAudio?.state === "suspended") await contextoAudio.resume();
      if (audioActual !== audio) return;
      await audio.play();
      pausar.innerHTML = `${detener}<span>Pausar</span>`;
      orbe.setAttribute("aria-label", "La voz del agente está hablando");
      animar();
    } catch {
      resolver(false);
      orbe.setAttribute("aria-label", "No se pudo reproducir el audio");
      pausar.innerHTML = `${play}<span>Escuchar</span>`;
    }
  };
  pausar.addEventListener("click", async () => {
    if (audio.paused) await iniciar();
    else {
      audio.pause();
      pausar.innerHTML = `${play}<span>Reanudar</span>`;
      orbe.setAttribute("aria-label", "La voz del agente está pausada");
    }
  });
  repetirBoton.addEventListener("click", () => {
    audio.currentTime = 0;
    iniciar();
  });
  audio.addEventListener("ended", () => {
    if (cuadroAnimacion) cancelAnimationFrame(cuadroAnimacion);
    cuadroAnimacion = 0;
    orbe.style.transform = "";
    orbe.style.opacity = "";
    orbe.setAttribute("aria-label", "La voz del agente terminó");
    pausar.innerHTML = `${play}<span>Escuchar</span>`;
  });
  audio.addEventListener("error", () => {
    orbe.setAttribute("aria-label", "No se pudo reproducir el audio");
  }, { once: true });
  repetirBoton.setAttribute("aria-label", texto ? `Repetir respuesta: ${texto.slice(0, 100)}` : "Repetir respuesta");
  iniciar();
  return { iniciar, audio, terminado };
}

export function montarVoz(contenedor, { alResultado, alAviso, alEstado, alTranscripcion, entradaSegura, habilitada = () => true, obtenerConversacionId, raizMicrofonos = contenedor }) {
  const panel = document.createElement("section");
  panel.className = "voz-panel";
  panel.hidden = true;
  panel.setAttribute("aria-label", "Grabación de voz");
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-label", "Onda de audio en vivo");
  const contador = document.createElement("span");
  contador.className = "voz-contador";
  contador.textContent = "00:00";
  const acciones = document.createElement("div");
  acciones.className = "voz-panel__acciones";
  const enviar = boton("Detener y enviar", detener, "btn btn--primario");
  const cancelar = boton("Cancelar", detener);
  acciones.append(enviar, cancelar);
  panel.append(canvas, contador, acciones);
  contenedor.prepend(panel);

  let flujo = null;
  let grabadora = null;
  let contexto = null;
  let intervalo = 0;
  let animacion = 0;
  let inicio = 0;
  let cancelarAlDetener = false;
  let ocupada = false;
  let teclaEspacioPresionada = false;
  let generacionVoz = 0;

  const dibujarOnda = (fuente) => {
    const escala = window.devicePixelRatio || 1;
    const ancho = canvas.clientWidth;
    const alto = canvas.clientHeight;
    canvas.width = Math.max(1, Math.floor(ancho * escala));
    canvas.height = Math.max(1, Math.floor(alto * escala));
    const lienzo = canvas.getContext("2d");
    const analizador = contexto.createAnalyser();
    analizador.fftSize = 1024;
    const muestras = new Uint8Array(analizador.fftSize);
    fuente.connect(analizador);
    const dibujar = () => {
      if (!panel.isConnected || panel.hidden) return;
      analizador.getByteTimeDomainData(muestras);
      lienzo.clearRect(0, 0, canvas.width, canvas.height);
      lienzo.beginPath();
      lienzo.lineWidth = 2 * escala;
      lienzo.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--laton").trim() || "#C9A227";
      for (let indice = 0; indice < muestras.length; indice += 1) {
        const x = indice / (muestras.length - 1) * canvas.width;
        const y = muestras[indice] / 255 * canvas.height;
        if (indice === 0) lienzo.moveTo(x, y);
        else lienzo.lineTo(x, y);
      }
      lienzo.stroke();
      animacion = requestAnimationFrame(dibujar);
    };
    dibujar();
  };

  const terminarFlujo = () => {
    if (intervalo) clearInterval(intervalo);
    if (animacion) cancelAnimationFrame(animacion);
    intervalo = 0;
    animacion = 0;
    flujo?.getTracks().forEach((pista) => pista.stop());
    flujo = null;
    if (contexto && contexto.state !== "closed") contexto.close().catch(() => {});
    contexto = null;
    raizMicrofonos.querySelectorAll("[data-accion-microfono]").forEach((botonMic) => botonMic.classList.remove("btn-microfono--grabando"));
  };

  const detenerGrabacion = (cancelar = false) => {
    if (!grabadora || grabadora.state === "inactive") return;
    cancelarAlDetener = cancelar;
    grabadora.stop();
  };

  const iniciar = async (porTeclado = false) => {
    if (!habilitada()) return;
    const generacionInicio = generacionVoz;
    if (ocupada || grabadora?.state === "recording") {
      detenerGrabacion();
      return;
    }
    detenerAudioActual();
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      alAviso("Este navegador no permite grabar audio. Usa un navegador actualizado con acceso al micrófono.");
      return;
    }
    try {
      const permiso = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (generacionInicio !== generacionVoz || !habilitada()) {
        permiso.getTracks().forEach((pista) => pista.stop());
        return;
      }
      flujo = permiso;
      contexto = new (window.AudioContext || window.webkitAudioContext)();
      panel.hidden = false;
      const entrada = contexto.createMediaStreamSource(flujo);
      dibujarOnda(entrada);
      const partes = [];
      grabadora = new MediaRecorder(flujo);
      grabadora.addEventListener("dataavailable", (evento) => {
        if (evento.data.size) partes.push(evento.data);
      });
      grabadora.addEventListener("stop", async () => {
        const generacionSolicitud = generacionVoz;
        const cancelarCaptura = cancelarAlDetener;
        cancelarAlDetener = false;
        terminarFlujo();
        panel.hidden = true;
        if (cancelarCaptura) return;
        ocupada = true;
        raizMicrofonos.querySelectorAll("[data-accion-microfono]").forEach((botonMic) => { botonMic.disabled = true; });
        const inicioEnvio = Date.now();
        alEstado?.("Transcribiendo tu voz…");
        const progreso = window.setInterval(() => {
          if (generacionSolicitud !== generacionVoz) {
            window.clearInterval(progreso);
            return;
          }
          const segundos = (Date.now() - inicioEnvio) / 1000;
          alEstado?.(segundos < 2 ? "Transcribiendo tu voz…" : segundos < 4.5 ? "Buscando en el catálogo…" : segundos > 6 ? "Preparando la voz…" : "Escribiendo la respuesta…");
        }, 500);
        try {
          const wav = await convertirAWav16k(new Blob(partes, { type: grabadora.mimeType }));
          window.clearInterval(progreso);
          const resultado = await procesarAudio(wav, obtenerConversacionId(), {
            entradaSegura: entradaSegura?.(), alTranscripcion, alEstado,
            vigente: () => generacionSolicitud === generacionVoz,
          });
          window.clearInterval(progreso);
          if (generacionSolicitud === generacionVoz) {
            await alResultado(resultado, resultado.transcripcion || "");
          }
        } catch {
          window.clearInterval(progreso);
          if (generacionSolicitud === generacionVoz) {
            alAviso("No pudimos procesar la grabación. Revisa tu conexión e inténtalo de nuevo.");
          }
        } finally {
          ocupada = false;
          raizMicrofonos.querySelectorAll("[data-accion-microfono]").forEach((botonMic) => { botonMic.disabled = !habilitada(); });
        }
      }, { once: true });
      grabadora.start();
      inicio = Date.now();
      raizMicrofonos.querySelectorAll("[data-accion-microfono]").forEach((botonMic) => botonMic.classList.add("btn-microfono--grabando"));
      actualizarContador();
      intervalo = window.setInterval(actualizarContador, 250);
      if (porTeclado && !teclaEspacioPresionada) detenerGrabacion();
    } catch {
      terminarFlujo();
      alAviso("No fue posible acceder al micrófono. Pulse el candado junto a la dirección → Micrófono → Permitir, y recargue.");
    }
  };

  function actualizarContador() {
    const segundos = Math.floor((Date.now() - inicio) / 1000);
    contador.textContent = `${String(Math.floor(segundos / 60)).padStart(2, "0")}:${String(segundos % 60).padStart(2, "0")}`;
    if (segundos >= 60) {
      alAviso("Alcanzaste el límite de 60 segundos; enviaremos tu consulta.");
      detenerGrabacion();
    }
  }

  raizMicrofonos.addEventListener("click", (evento) => {
    const botonMic = evento.target instanceof Element ? evento.target.closest("[data-accion-microfono]") : null;
    if (botonMic && raizMicrofonos.contains(botonMic)) iniciar();
  });
  enviar.addEventListener("click", () => detenerGrabacion());
  cancelar.addEventListener("click", () => {
    cancelarAlDetener = true;
    detenerGrabacion(true);
    if (!grabadora || grabadora.state === "inactive") {
      terminarFlujo();
      panel.hidden = true;
    }
  });

  const esCampoTexto = (elemento) => elemento instanceof HTMLElement
    && (elemento.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(elemento.tagName));
  window.addEventListener("keydown", (evento) => {
    if (evento.code === "Space" && !evento.repeat && !esCampoTexto(evento.target)) {
      teclaEspacioPresionada = true;
      evento.preventDefault();
      iniciar(true);
    }
  });
  window.addEventListener("keyup", (evento) => {
    if (evento.code === "Space") teclaEspacioPresionada = false;
    if (evento.code === "Space" && grabadora?.state === "recording") {
      evento.preventDefault();
      detenerGrabacion();
    }
  });
  return {
    iniciar,
    get ocupada() { return ocupada || grabadora?.state === "recording"; },
    detener: detenerGrabacion,
    destruir: () => {
      generacionVoz += 1;
      cancelarAlDetener = true;
      detenerGrabacion(true);
      terminarFlujo();
      panel.hidden = true;
      detenerAudioActual();
    },
  };
}
