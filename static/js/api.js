import { leerSalaPreferida } from "./salas.js";

async function solicitar(ruta, opciones = {}, aceptarError = false) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, { ...opciones, credentials: "same-origin" });
  } catch {
    throw new Error("No fue posible conectar con la biblioteca. Revisa tu conexión e inténtalo de nuevo.");
  }
  let datos;
  try {
    datos = await respuesta.json();
  } catch {
    datos = null;
  }
  if (!respuesta.ok) {
    if (respuesta.status === 401 && !["/api/sesion", "/api/login"].includes(ruta)) {
      window.dispatchEvent(new CustomEvent("biblioteca-sesion-expirada"));
    }
    if (aceptarError && datos?.ok === false) return datos;
    throw new Error("No pudimos completar la solicitud. Inténtalo de nuevo en un momento.");
  }
  return datos;
}

function obtenerSalaActualParaAPI(sala = null) {
  if (sala !== null && sala !== undefined && sala !== "") return sala;
  const preferida = leerSalaPreferida();
  return preferida && preferida !== "todas" ? preferida : null;
}

export function obtenerPreferenciaVoz() {
  try {
    return {
      voz_id: localStorage.getItem("biblioteca-voz-agente") || "claude",
      acepto_cpml: localStorage.getItem("biblioteca-acepto-cpml") === "true",
    };
  } catch {
    return { voz_id: "claude", acepto_cpml: false };
  }
}

export function enviarChat(texto, conversacionId, conAudio = false, sala = null) {
  return solicitar("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      texto,
      conversacion_id: conversacionId || null,
      con_audio: conAudio,
      sala: obtenerSalaActualParaAPI(sala),
      ...obtenerPreferenciaVoz(),
    }),
  });
}

export function enviarVoz(blob, conversacionId, sala = null) {
  const formulario = new FormData();
  const voz = obtenerPreferenciaVoz();
  const salaActual = obtenerSalaActualParaAPI(sala);
  formulario.append("audio", blob, "consulta.wav");
  if (conversacionId) formulario.append("conversacion_id", conversacionId);
  if (salaActual) formulario.append("sala", salaActual);
  else formulario.append("sala", "");
  formulario.append("voz_id", voz.voz_id);
  formulario.append("acepto_cpml", String(voz.acepto_cpml));
  return solicitar("/api/voz", { method: "POST", body: formulario }, true);
}

export async function obtenerBienvenidaSalas(conversacionId = null) {
  const url = new URL("/api/salas/bienvenida", window.location.origin);
  if (conversacionId) url.searchParams.set("conversacion_id", conversacionId);
  try {
    return await solicitar(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    }, true);
  } catch {
    return null;
  }
}

export function sintetizar(texto) {
  const voz = obtenerPreferenciaVoz();
  return solicitar("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto, ...voz }),
  });
}

export function obtenerVoces() {
  return solicitar("/api/voces");
}

export function prepararVoz(vozId) {
  return solicitar(`/api/voces/${encodeURIComponent(vozId)}/preparar`, { method: "POST" });
}

export function obtenerSalud() {
  return solicitar("/api/salud");
}

export function obtenerCuenta() {
  return solicitar("/api/cuenta");
}

export function obtenerMisReservas() {
  return solicitar("/api/mis-reservas");
}

export function obtenerConversacionActual() {
  return solicitar("/api/conversacion/actual");
}

export function adoptarConversacion(conversacionId) {
  return solicitar(`/api/conversacion/${encodeURIComponent(conversacionId)}/adoptar`, {
    method: "POST",
  });
}

export function borrarConversacion(conversacionId) {
  return solicitar(`/api/conversacion/${encodeURIComponent(conversacionId)}`, {
    method: "DELETE",
  });
}

export async function cancelarReserva(reservaId) {
  let respuesta;
  const ruta = `/api/reservas/${encodeURIComponent(reservaId)}/cancelar`;
  try {
    respuesta = await fetch(ruta, {
      method: "POST",
      credentials: "same-origin",
    });
  } catch {
    throw new Error("No fue posible conectar con la biblioteca. Revisa tu conexión e inténtalo de nuevo.");
  }
  let datos;
  try {
    datos = await respuesta.json();
  } catch {
    datos = null;
  }
  if (respuesta.status === 401) {
    window.dispatchEvent(new CustomEvent("biblioteca-sesion-expirada"));
  }
  if (!respuesta.ok) {
    const mensaje = datos?.mensaje || datos?.detail;
    if ([404, 409].includes(respuesta.status)) {
      return { ok: false, mensaje: mensaje || "La reserva ya no está disponible para cancelar." };
    }
    throw new Error(mensaje || "No pudimos cancelar la reserva. Inténtalo de nuevo.");
  }
  if (typeof datos?.ok !== "boolean") {
    throw new Error("La respuesta al cancelar la reserva no es válida.");
  }
  return { ok: datos.ok, mensaje: datos.mensaje || (datos.ok ? "Reserva cancelada." : "No se pudo cancelar la reserva.") };
}

export function obtenerMaterial(id) {
  return solicitar(`/api/material/${encodeURIComponent(id)}`);
}

export function investigar(tema, programa = null) {
  return solicitar("/api/investigacion", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tema, programa: programa || null }),
  }, true);
}

export function obtenerCatalogo(parametros = {}) {
  return solicitar(`/api/catalogo?${new URLSearchParams(parametros)}`);
}

async function solicitarTesis(ruta, opciones = {}) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, { ...opciones, credentials: "same-origin" });
  } catch {
    throw new Error("No fue posible conectar con la biblioteca. Revisa tu conexión e inténtalo de nuevo.");
  }
  let datos;
  try {
    datos = await respuesta.json();
  } catch {
    datos = null;
  }
  if (!respuesta.ok) {
    if (respuesta.status === 401) {
      window.dispatchEvent(new CustomEvent("biblioteca-sesion-expirada"));
    }
    const error = new Error(datos?.mensaje || "No pudimos completar la solicitud. Inténtalo de nuevo en un momento.");
    error.status = respuesta.status;
    throw error;
  }
  return datos;
}

export function obtenerProgramas() {
  return solicitarTesis("/api/programas");
}

export function subirTesis(formulario) {
  return solicitarTesis("/api/tesis", { method: "POST", body: formulario });
}

export function obtenerProgresoTesis(cargaId) {
  return solicitarTesis(`/api/tesis/progreso/${encodeURIComponent(cargaId)}`);
}

export function consultarSesion() {
  return solicitar("/api/sesion");
}

export function obtenerAvisosDisponibilidad() {
  return solicitar("/api/avisos");
}

export async function iniciarSesion(codigo, pin) {
  let respuesta;
  try {
    respuesta = await fetch("/api/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo, pin }),
    });
  } catch {
    return { status: 0, mensaje: "No fue posible conectar con la biblioteca. Revisa tu conexión e inténtalo de nuevo." };
  }
  let datos;
  try {
    datos = await respuesta.json();
  } catch {
    datos = {};
  }
  return { ...datos, status: respuesta.status };
}

export function cerrarSesion() {
  return solicitar("/api/logout", {
    method: "POST",
  });
}
