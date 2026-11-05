import { convertirAWav16k } from "./wav.js";
import { procesarAudio, detenerAudioActual } from "./voz.js";

// Una sola captura por turno. Las pistas se cierran antes de procesar o hablar.
export function montarLlamada(cabecera, { raiz, obtenerConversacionId, entradaSegura, alTranscripcion, alResultado, antesDeIniciar, disponible }) {
  const panel = document.createElement("div");
  panel.className = "llamada";
  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = "btn btn--acento llamada__boton";
  const estado = document.createElement("span");
  estado.className = "llamada__estado";
  estado.setAttribute("role", "status");
  estado.setAttribute("aria-live", "polite");
  panel.append(boton, estado);
  cabecera.append(panel);
  let activa = false;
  let generacion = 0;
  let flujo = null;
  let contexto = null;
  let grabadora = null;
  let temporizador = 0;
  let pausa = 0;
  let esperaPausa = null;
  let estadoActual = "";

  function mostrar(texto, fase = "reposo") {
    estado.textContent = texto;
    estadoActual = fase;
    panel.dataset.estado = fase;
    boton.textContent = activa ? "Terminar llamada" : "Iniciar llamada";
    boton.setAttribute("aria-pressed", String(activa));
    raiz.querySelectorAll("[data-accion-microfono]").forEach((mic) => { mic.disabled = activa; });
  }
  function limpiarCaptura() {
    clearInterval(temporizador);
    temporizador = 0;
    if (grabadora?.state === "recording") grabadora.stop();
    grabadora = null;
    flujo?.getTracks().forEach((pista) => pista.stop());
    flujo = null;
    contexto?.close().catch(() => {});
    contexto = null;
  }
  function terminar(mensaje = "Llamada terminada") {
    activa = false;
    generacion += 1;
    limpiarCaptura();
    clearTimeout(pausa);
    esperaPausa?.();
    esperaPausa = null;
    detenerAudioActual();
    mostrar(mensaje);
  }
  const vigente = (id) => activa && generacion === id;

  async function escuchar(id) {
    if (!vigente(id)) return;
    mostrar("Conectando micrófono…", "conectando");
    try {
      const nuevoFlujo = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (!vigente(id)) { nuevoFlujo.getTracks().forEach((pista) => pista.stop()); return; }
      flujo = nuevoFlujo;
      contexto = new (window.AudioContext || window.webkitAudioContext)();
      await contexto.resume();
      if (!vigente(id)) return;
      const analizador = contexto.createAnalyser();
      analizador.fftSize = 2048;
      contexto.createMediaStreamSource(flujo).connect(analizador);
      const muestras = new Float32Array(analizador.fftSize);
      const partes = [];
      const recorder = new MediaRecorder(flujo);
      grabadora = recorder;
      let ultimoSonido = performance.now();
      const inicio = ultimoSonido;
      let vozMs = 0;
      let detectada = false;
      recorder.addEventListener("dataavailable", ({ data }) => { if (data.size) partes.push(data); });
      recorder.addEventListener("error", () => { if (vigente(id)) terminar("No se pudo grabar. Puedes iniciar otra llamada."); });
      recorder.addEventListener("stop", async () => {
        limpiarCaptura();
        if (!vigente(id)) return;
        if (!detectada || vozMs < 240) { terminar("No se detectó voz. Inicia la llamada cuando estés listo."); return; }
        mostrar("Transcribiendo…", "procesando");
        try {
          const wav = await convertirAWav16k(new Blob(partes, { type: recorder.mimeType }));
          if (!vigente(id)) return;
          const resultado = await procesarAudio(wav, obtenerConversacionId(), {
            entradaSegura: entradaSegura(), alTranscripcion,
            alEstado: (texto) => { if (vigente(id)) mostrar(texto, "procesando"); },
            vigente: () => vigente(id),
          });
          if (!vigente(id)) return;
          if (!resultado || resultado.ok === false) {
            await alResultado(resultado, "");
            terminar("No entendí la consulta. Puedes iniciar otra llamada.");
            return;
          }
          mostrar("Preparando respuesta de voz…", "procesando");
          const reproduccion = await alResultado(resultado, resultado.transcripcion || "", () => {
            if (vigente(id)) mostrar("Hablando…", "hablando");
          }, () => vigente(id));
          if (!vigente(id)) return;
          if (!reproduccion?.terminado || !await reproduccion.terminado) {
            terminar("La respuesta está en el chat. Inicia otra llamada para continuar.");
            return;
          }
          if (!vigente(id)) return;
          // Breve margen para que no quede sonido de los altavoces al reabrir.
          await new Promise((resolve) => { esperaPausa = resolve; pausa = window.setTimeout(resolve, 350); });
          esperaPausa = null;
          if (vigente(id)) escuchar(id);
        } catch {
          if (vigente(id)) terminar("No pudimos procesar la voz. Puedes iniciar otra llamada o escribir.");
        }
      }, { once: true });
      recorder.start();
      mostrar("Escuchando… Habla y haz una pausa para enviar.", "escuchando");
      temporizador = window.setInterval(() => {
        if (!vigente(id)) return;
        analizador.getFloatTimeDomainData(muestras);
        const rms = Math.sqrt(muestras.reduce((suma, valor) => suma + valor * valor, 0) / muestras.length);
        const ahora = performance.now();
        if (rms > 0.018) { vozMs += 50; ultimoSonido = ahora; if (vozMs >= 240) detectada = true; }
        if ((detectada && ahora - ultimoSonido > 1100) || ahora - inicio > (detectada ? 45000 : 20000)) {
          clearInterval(temporizador);
          recorder.stop();
        }
      }, 50);
    } catch {
      if (vigente(id)) terminar("No se pudo abrir el micrófono. Revisa el permiso e inicia otra llamada.");
    }
  }
  boton.addEventListener("click", () => {
    if (activa) { terminar(); return; }
    if (!disponible()) { mostrar("Espera a que termine la consulta actual."); return; }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { mostrar("Tu navegador no permite llamadas. Puedes escribir tu consulta."); return; }
    antesDeIniciar();
    activa = true;
    escuchar(++generacion);
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden && activa) terminar(); });
  window.addEventListener("pagehide", () => { if (activa) terminar(); });
  window.addEventListener("biblioteca-sesion-expirada", () => { if (activa) terminar(); });
  const observar = new MutationObserver(() => {
    if (activa && (!raiz.isConnected || raiz.closest("[hidden]"))) terminar();
  });
  observar.observe(document.body, { subtree: true, attributes: true, attributeFilter: ["hidden"], childList: true });
  // Una reproducción elegida manualmente debe cerrar la captura antes de sonar.
  raiz.addEventListener("click", (evento) => {
    if (activa && evento.target.closest(".orbita-voz, .mensaje__herramientas")) terminar();
  }, true);
  mostrar("Habla con el agente sin mantener pulsado el micrófono.");
  return { terminar, get activa() { return activa; }, get estado() { return estadoActual; } };
}
