/**
 * voz_basica.js — Micrófono provisional para la interfaz mínima (antes del rediseño).
 * Clic para grabar, clic para detener; envía WAV 16 kHz a /api/voz y reproduce la respuesta.
 */
import { convertirAWav16k, reproducirBase64 } from "/static/js/wav.js";
import { renderBibliografia } from "/static/js/bibliografia.js";

const boton = document.querySelector("#mic-button");
const historial = document.querySelector("#chat-history");
let grabador = null;
let trozos = [];
let ultimoAudio = null;

function agregar(texto, tipo, detalle = "") {
  const art = document.createElement("article");
  art.className = `message ${tipo}-message`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = tipo === "user" ? "🎤" : "B";
  const cont = document.createElement("div");
  cont.className = "message-content";
  const p = document.createElement("p");
  p.textContent = texto;
  cont.append(p);
  if (detalle) {
    const s = document.createElement("small");
    s.textContent = detalle;
    cont.append(s);
  }
  art.append(avatar, cont);
  historial.append(art);
  historial.scrollTop = historial.scrollHeight;
  return cont;
}

async function iniciar() {
  try {
    const flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
    trozos = [];
    grabador = new MediaRecorder(flujo);
    grabador.ondataavailable = (e) => e.data.size && trozos.push(e.data);
    grabador.onstop = () => {
      flujo.getTracks().forEach((t) => t.stop());
      enviar(new Blob(trozos, { type: grabador.mimeType }));
    };
    grabador.start();
    boton.textContent = "⏹ Detener";
    boton.classList.add("grabando");
    boton.setAttribute("aria-label", "Detener grabación");
  } catch {
    agregar("No tengo permiso para usar el micrófono. Pulse el candado junto a la dirección del navegador, permita el micrófono y vuelva a intentarlo.", "agent");
  }
}

async function enviar(blob) {
  boton.disabled = true;
  boton.textContent = "Procesando…";
  boton.classList.remove("grabando");
  try {
    const wav = await convertirAWav16k(blob);
    const form = new FormData();
    form.append("audio", wav, "voz.wav");
    if (window.conversacionId) form.append("conversacion_id", window.conversacionId);
    const r = await fetch("/api/voz", { method: "POST", body: form });
    const d = await r.json();
    if (d.ok === false || !r.ok) throw new Error(d.mensaje || "No pude procesar el audio.");
    window.conversacionId = d.conversacion_id || window.conversacionId;
    agregar(d.transcripcion || "(sin transcripción)", "user", "Por voz");
    const t = d.tiempos || {};
    const cont = agregar(d.respuesta || "Sin respuesta.", "agent",
      `Herramienta: ${d.herramienta || "—"} · STT ${t.t_stt_ms ?? "—"} ms · LLM ${t.t_llm_ms ?? "—"} ms · TTS ${t.t_tts_ms ?? "—"} ms · total ${t.t_total_ms ?? "—"} ms`);
    if (d.bibliografia) cont.append(renderBibliografia(d.bibliografia));
    if (d.audio_wav_base64) {
      ultimoAudio = reproducirBase64(d.audio_wav_base64);
      const repetir = document.createElement("button");
      repetir.type = "button";
      repetir.className = "text-button";
      repetir.textContent = "▶ Escuchar de nuevo";
      const audio = ultimoAudio;
      repetir.addEventListener("click", () => { audio.currentTime = 0; audio.play(); });
      cont.append(repetir);
    } else if (d.aviso) {
      cont.append(Object.assign(document.createElement("small"), { textContent: d.aviso }));
    }
  } catch (e) {
    agregar(e.message || "No pude procesar el audio.", "agent");
  } finally {
    boton.disabled = false;
    boton.textContent = "🎤 Hablar";
    boton.setAttribute("aria-label", "Grabar pregunta por voz");
  }
}

boton.addEventListener("click", () => {
  if (grabador && grabador.state === "recording") {
    grabador.stop();
  } else {
    if (ultimoAudio) ultimoAudio.pause();
    iniciar();
  }
});
