const form = document.querySelector("#chat-form");
const input = document.querySelector("#chat-input");
const history = document.querySelector("#chat-history");
const sendButton = document.querySelector("#send-button");
const newChatButton = document.querySelector("#new-chat");

window.conversacionId = null; // compartido con voz_basica.js

function agregarMensaje(texto, tipo, detalle = "") {
  const mensaje = document.createElement("article");
  mensaje.className = `message ${tipo}-message`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = tipo === "user" ? "T" : "B";

  const contenido = document.createElement("div");
  contenido.className = "message-content";
  const parrafo = document.createElement("p");
  parrafo.textContent = texto;
  contenido.append(parrafo);

  if (detalle) {
    const meta = document.createElement("small");
    meta.textContent = detalle;
    contenido.append(meta);
  }

  mensaje.append(avatar, contenido);
  history.append(mensaje);
  history.scrollTop = history.scrollHeight;
  return contenido;
}

form.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const texto = input.value.trim();
  if (!texto || sendButton.disabled) return;

  agregarMensaje(texto, "user");
  input.value = "";
  sendButton.disabled = true;
  sendButton.textContent = "Enviando…";

  try {
    const respuesta = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto, conversacion_id: window.conversacionId }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible enviar el mensaje.");

    window.conversacionId = datos.conversacion_id || window.conversacionId;
    const tiempo = datos.tiempos?.t_total_ms;
    const etiquetas = [
      datos.intencion ? `Intención: ${datos.intencion}` : "",
      datos.herramienta ? `Herramienta: ${datos.herramienta}` : "",
      tiempo !== null && tiempo !== undefined ? `${tiempo} ms` : "",
    ].filter(Boolean);
    const contenido = agregarMensaje(
      datos.respuesta || "No recibí una respuesta.",
      "agent",
      etiquetas.join(" · "),
    );
    if (datos.bibliografia) {
      try {
        const modulo = await import("/static/js/bibliografia.js");
        contenido.append(modulo.renderBibliografia(datos.bibliografia));
      } catch {
        const aviso = document.createElement("small");
        aviso.textContent = "No fue posible mostrar la bibliografía.";
        contenido.append(aviso);
      }
    }
  } catch (error) {
    agregarMensaje(error.message || "No fue posible conectar con el agente.", "agent");
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "Enviar";
    input.focus();
  }
});

input.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !evento.shiftKey) {
    evento.preventDefault();
    form.requestSubmit();
  }
});

newChatButton.addEventListener("click", () => {
  window.conversacionId = null;
  history.replaceChildren();
  agregarMensaje(
    "¡Hola! Puedo ayudarle a buscar materiales, consultar disponibilidad y responder preguntas de la biblioteca.",
    "agent",
    "Agente de biblioteca",
  );
  input.focus();
});
