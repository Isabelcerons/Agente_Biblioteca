/**
 * wav.js — Conversión de audio del navegador a WAV PCM 16 kHz mono (lo que espera /api/voz).
 * Se reutiliza en la interfaz nueva (voz.js).
 */

const FRECUENCIA_OBJETIVO = 16000;

/**
 * Convierte el Blob grabado por MediaRecorder (webm/ogg) a un Blob WAV 16 kHz mono.
 * 1) decodifica con AudioContext, 2) remuestrea con OfflineAudioContext a 16 kHz y 1 canal,
 * 3) codifica PCM de 16 bits con cabecera RIFF.
 */
export async function convertirAWav16k(blob) {
  const datos = await blob.arrayBuffer();
  const contexto = new (window.AudioContext || window.webkitAudioContext)();
  let original;
  try {
    original = await contexto.decodeAudioData(datos);
  } finally {
    contexto.close();
  }
  const muestras = Math.max(1, Math.ceil(original.duration * FRECUENCIA_OBJETIVO));
  const offline = new OfflineAudioContext(1, muestras, FRECUENCIA_OBJETIVO);
  const fuente = offline.createBufferSource();
  fuente.buffer = original; // al conectar a un destino mono, los canales se mezclan
  fuente.connect(offline.destination);
  fuente.start();
  const remuestreado = await offline.startRendering();
  return codificarWav(remuestreado.getChannelData(0), FRECUENCIA_OBJETIVO);
}

/** Codifica muestras float32 [-1, 1] como WAV PCM 16 bits mono. */
function codificarWav(muestras, frecuencia) {
  const buffer = new ArrayBuffer(44 + muestras.length * 2);
  const vista = new DataView(buffer);
  const texto = (pos, s) => { for (let i = 0; i < s.length; i++) vista.setUint8(pos + i, s.charCodeAt(i)); };
  texto(0, "RIFF");
  vista.setUint32(4, 36 + muestras.length * 2, true);
  texto(8, "WAVE");
  texto(12, "fmt ");
  vista.setUint32(16, 16, true);          // tamaño del bloque fmt
  vista.setUint16(20, 1, true);           // PCM
  vista.setUint16(22, 1, true);           // mono
  vista.setUint32(24, frecuencia, true);
  vista.setUint32(28, frecuencia * 2, true); // bytes por segundo
  vista.setUint16(32, 2, true);           // bytes por muestra
  vista.setUint16(34, 16, true);          // bits por muestra
  texto(36, "data");
  vista.setUint32(40, muestras.length * 2, true);
  let pos = 44;
  for (let i = 0; i < muestras.length; i++, pos += 2) {
    const s = Math.max(-1, Math.min(1, muestras[i]));
    vista.setInt16(pos, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

/** Reproduce un WAV en base64 y devuelve el elemento Audio (para repetir o detener). */
export function reproducirBase64(base64) {
  const audio = new Audio(`data:audio/wav;base64,${base64}`);
  audio.play().catch(() => { /* el navegador puede bloquear la reproducción automática */ });
  return audio;
}
