import { consultarSesion, iniciarSesion } from "./api.js";

const claveInvitado = "biblioteca-invitado";

export function montarSesion({ alEntrar, alInvitado, alExpirar }) {
  const pantalla = document.querySelector("#pantalla-sesion");
  const aplicacion = document.querySelector(".app-shell");
  const formulario = document.querySelector("#formulario-sesion");
  const campoCodigo = document.querySelector("#codigo-sesion");
  const campoPin = document.querySelector("#pin-sesion");
  const botonEntrar = document.querySelector("#entrar-sesion");
  const botonInvitado = document.querySelector("#entrar-invitado");
  const botonMostrarPin = document.querySelector("#mostrar-pin");
  const aviso = document.querySelector("#sesion-aviso");
  const errorCodigo = document.querySelector("#error-codigo-sesion");
  const errorPin = document.querySelector("#error-pin-sesion");
  let textoPendiente = "";
  let temporizadorBloqueo = 0;
  let solicitudActiva = false;
  let temporizadorSalida = 0;
  let entradaResuelta = false;

  function mostrarAviso(mensaje) {
    aviso.textContent = mensaje || "";
    aviso.hidden = !mensaje;
  }

  function limpiarErrores() {
    campoCodigo.removeAttribute("aria-invalid");
    campoPin.removeAttribute("aria-invalid");
    errorCodigo.textContent = "";
    errorPin.textContent = "";
  }

  function errorCampo(campo, texto, nodoError) {
    campo.setAttribute("aria-invalid", "true");
    nodoError.textContent = texto;
    campo.focus();
  }

  function limpiarTemporizadorBloqueo() {
    if (temporizadorBloqueo) window.clearInterval(temporizadorBloqueo);
    temporizadorBloqueo = 0;
  }

  function establecerBloqueo(hasta, mensaje) {
    limpiarTemporizadorBloqueo();
    const fin = new Date(hasta).getTime();
    const actualizar = () => {
      const faltan = Math.max(0, Math.ceil((fin - Date.now()) / 1000));
      if (!Number.isFinite(fin) || faltan <= 0) {
        limpiarTemporizadorBloqueo();
        botonEntrar.disabled = false;
        botonEntrar.textContent = "Entrar";
        mostrarAviso(mensaje ? `${mensaje} Ya puedes intentarlo de nuevo.` : "Ya puedes intentarlo de nuevo.");
        return;
      }
      const minutos = Math.floor(faltan / 60);
      const segundos = faltan % 60;
      mostrarAviso(`${mensaje || "Has alcanzado el límite de intentos."} Inténtalo de nuevo en ${minutos ? `${minutos} min ` : ""}${segundos} s.`);
      botonEntrar.disabled = true;
      botonEntrar.textContent = "Bloqueado";
    };
    actualizar();
    if (botonEntrar.disabled) temporizadorBloqueo = window.setInterval(actualizar, 1000);
  }

  function mostrarLogin(texto = "", mensaje = "") {
    textoPendiente = texto || "";
    window.clearTimeout(temporizadorSalida);
    limpiarTemporizadorBloqueo();
    solicitudActiva = false;
    botonEntrar.disabled = false;
    botonEntrar.textContent = "Entrar";
    pantalla.hidden = false;
    pantalla.classList.remove("pantalla-sesion--salida");
    aplicacion.hidden = true;
    limpiarErrores();
    mostrarAviso(mensaje);
    campoPin.type = "password";
    botonMostrarPin.setAttribute("aria-pressed", "false");
    botonMostrarPin.setAttribute("aria-label", "Mostrar PIN");
    botonMostrarPin.textContent = "Mostrar";
    window.requestAnimationFrame(() => campoCodigo.focus({ preventScroll: true }));
  }

  function finalizarEntrada(callback) {
    entradaResuelta = true;
    callback?.();
    aplicacion.hidden = false;
    const reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.requestAnimationFrame(() => pantalla.classList.add("pantalla-sesion--salida"));
    temporizadorSalida = window.setTimeout(() => {
      pantalla.hidden = true;
      pantalla.classList.remove("pantalla-sesion--salida");
      temporizadorSalida = 0;
      document.querySelector("#entrada-chat")?.focus({ preventScroll: true });
    }, reducido ? 0 : 240);
  }

  function guardarInvitado(valor) {
    try {
      if (valor) sessionStorage.setItem(claveInvitado, "true");
      else sessionStorage.removeItem(claveInvitado);
    } catch {
      // La entrada como invitado sigue funcionando durante esta pestaña.
    }
  }

  function entrarInvitado() {
    if (solicitudActiva) return;
    textoPendiente = "";
    limpiarTemporizadorBloqueo();
    mostrarAviso("");
    campoPin.value = "";
    guardarInvitado(true);
    finalizarEntrada(alInvitado);
  }

  function atenderResultado(resultado) {
    const { status } = resultado;
    if (status === 200 && resultado.ok === true && resultado.usuario) {
      guardarInvitado(false);
      const pendiente = textoPendiente;
      textoPendiente = "";
      campoPin.value = "";
      limpiarErrores();
      mostrarAviso("");
      finalizarEntrada(() => alEntrar?.(
        resultado.usuario,
        resultado.mensaje_bienvenida,
        resultado.avisos || {}, // objeto {vencidos, multas, por_vencer, reservas_por_expirar}
        pendiente,
      ));
      return;
    }
    if (status === 401) {
      const intentos = Number(resultado.intentos_restantes);
      const mensaje = resultado.mensaje || "El código o PIN no es correcto.";
      mostrarAviso(`${mensaje}${Number.isFinite(intentos) && !mensaje.includes("Te quedan") ? ` Te quedan ${intentos} intentos.` : ""}`);
      errorCampo(campoPin, "Verifica tu PIN e inténtalo de nuevo.", errorPin);
      return;
    }
    if (status === 429) {
      establecerBloqueo(resultado.bloqueado_hasta, resultado.mensaje || "Has alcanzado el límite de intentos.");
      return;
    }
    if (status === 422) {
      mostrarAviso(resultado.mensaje || "Revisa los datos ingresados e inténtalo de nuevo.");
      errorCampo(campoCodigo, "Verifica el código de usuario.", errorCodigo);
      return;
    }
    mostrarAviso(resultado.mensaje || "No fue posible iniciar sesión. Revisa tu conexión e inténtalo de nuevo.");
    campoCodigo.focus();
  }

  campoCodigo.addEventListener("input", () => {
    campoCodigo.value = campoCodigo.value.replace(/\D/g, "").slice(0, 10);
    campoCodigo.removeAttribute("aria-invalid");
    errorCodigo.textContent = "";
    mostrarAviso("");
  });
  campoPin.addEventListener("input", () => {
    campoPin.value = campoPin.value.replace(/\D/g, "").slice(0, 4);
    campoPin.removeAttribute("aria-invalid");
    errorPin.textContent = "";
    mostrarAviso("");
  });
  botonMostrarPin.addEventListener("click", () => {
    const mostrar = campoPin.type === "password";
    campoPin.type = mostrar ? "text" : "password";
    botonMostrarPin.setAttribute("aria-pressed", String(mostrar));
    botonMostrarPin.setAttribute("aria-label", mostrar ? "Ocultar PIN" : "Mostrar PIN");
    botonMostrarPin.textContent = mostrar ? "Ocultar" : "Mostrar";
    campoPin.focus({ preventScroll: true });
  });
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (solicitudActiva || botonEntrar.disabled) return;
    limpiarErrores();
    mostrarAviso("");
    if (!/^\d{3,10}$/.test(campoCodigo.value)) {
      campoPin.value = "";
      errorCampo(campoCodigo, "Ingresa tu código de usuario (3 a 10 dígitos)", errorCodigo);
      return;
    }
    if (!/^\d{4}$/.test(campoPin.value)) {
      campoPin.value = "";
      errorCampo(campoPin, "Ingresa un PIN de 4 dígitos.", errorPin);
      return;
    }
    const codigo = campoCodigo.value;
    const pin = campoPin.value;
    campoPin.value = "";
    solicitudActiva = true;
    botonEntrar.disabled = true;
    botonEntrar.textContent = "Entrando…";
    try {
      atenderResultado(await iniciarSesion(codigo, pin));
    } catch {
      mostrarAviso("No fue posible iniciar sesión. Revisa tu conexión e inténtalo de nuevo.");
      campoCodigo.focus();
    } finally {
      solicitudActiva = false;
      if (!temporizadorBloqueo && !pantalla.hidden && botonEntrar.textContent === "Entrando…") {
        botonEntrar.disabled = false;
        botonEntrar.textContent = "Entrar";
      }
    }
  });
  botonInvitado.addEventListener("click", entrarInvitado);

  async function comprobarSesion() {
    try {
      const respuesta = await consultarSesion();
      if (entradaResuelta) return;
      if (respuesta?.autenticado && respuesta.usuario) {
        guardarInvitado(false);
        const saludo = respuesta.mensaje_bienvenida || (respuesta.usuario.nombre
          ? `¡Bienvenido, ${respuesta.usuario.nombre}!`
          : "¡Bienvenido a la biblioteca!");
        finalizarEntrada(() => alEntrar?.(
          respuesta.usuario,
          saludo,
          respuesta.avisos || {},
          "",
        ));
        return;
      }
      let invitado = false;
      try {
        invitado = sessionStorage.getItem(claveInvitado) === "true";
      } catch {
        invitado = false;
      }
      if (invitado) finalizarEntrada(alInvitado);
      else mostrarLogin();
    } catch {
      if (!entradaResuelta) mostrarLogin("", "No pudimos comprobar tu sesión. Inicia sesión para continuar.");
    }
  }

  function cerrar() {
    guardarInvitado(false);
    textoPendiente = "";
    campoCodigo.value = "";
    campoPin.value = "";
    campoPin.type = "password";
    botonMostrarPin.setAttribute("aria-pressed", "false");
    botonMostrarPin.setAttribute("aria-label", "Mostrar PIN");
    botonMostrarPin.textContent = "Mostrar";
    mostrarLogin();
  }

  function expirar() {
    alExpirar?.();
    cerrar();
    mostrarAviso("Tu sesión expiró.");
  }

  void comprobarSesion();
  return { mostrarLogin, cerrar, expirar };
}
