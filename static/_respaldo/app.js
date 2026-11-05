const form = document.querySelector("#chat-form");
const input = document.querySelector("#chat-input");
const history = document.querySelector("#chat-history");
const sendButton = document.querySelector("#send-button");
const newChatButton = document.querySelector("#new-chat");

let conversacionId = null;

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
      body: JSON.stringify({ texto, conversacion_id: conversacionId }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible enviar el mensaje.");

    conversacionId = datos.conversacion_id || conversacionId;
    const tiempo = datos.tiempos?.t_total_ms;
    const etiquetas = [
      datos.intencion ? `Intención: ${datos.intencion}` : "",
      datos.herramienta ? `Herramienta: ${datos.herramienta}` : "",
      tiempo !== null && tiempo !== undefined ? `${tiempo} ms` : "",
    ].filter(Boolean);
    agregarMensaje(datos.respuesta || "No recibí una respuesta.", "agent", etiquetas.join(" · "));
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
  conversacionId = null;
  history.replaceChildren();
  agregarMensaje(
    "¡Hola! Puedo ayudarle a buscar materiales, consultar disponibilidad y responder preguntas de la biblioteca.",
    "agent",
    "Agente de biblioteca",
  );
  input.focus();
});
