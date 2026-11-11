let siguienteDialogo = 0;

function cargarEstilos() {
  const ruta = "/static/css/vistas.css";
  if (!document.querySelector(`link[rel="stylesheet"][href="${ruta}"]`)) {
    const enlace = document.createElement("link");
    enlace.rel = "stylesheet";
    enlace.href = ruta;
    document.head.append(enlace);
  }
}

function nodo(etiqueta, clase, contenido) {
  const elemento = document.createElement(etiqueta);
  if (clase) elemento.className = clase;
  if (contenido !== undefined) elemento.textContent = contenido;
  return elemento;
}

function tipoVisible(tipo) {
  return {
    libro: "Libro",
    tesis: "Tesis",
    articulo: "Artículo",
    recurso_digital: "Recurso digital",
  }[tipo] || tipo || "Material";
}

function fechaVisible(valor) {
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) return "Fecha no disponible";
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(fecha);
}

async function leerRespuesta(respuesta) {
  try {
    return await respuesta.json();
  } catch {
    throw new Error("El servidor devolvió una respuesta inválida.");
  }
}

export function montarMisReservas(contenedor) {
  if (!(contenedor instanceof HTMLElement)) {
    throw new TypeError("El contenedor de mis reservas debe ser un elemento HTML.");
  }
  cargarEstilos();
  const controlador = new AbortController();
  let solicitudActiva = null;
  let temporizador = 0;
  let destruida = false;
  let actualizacionLocal = false;
  const tituloDialogo = `mis-reservas-dialogo-${++siguienteDialogo}`;
  const tituloExistente = document.getElementById("titulo-mis-reservas");
  if (tituloExistente) {
    tituloExistente.textContent = "Mis reservas";
  }

  contenedor.innerHTML = `
    <section class="vistas vistas--mis-reservas" aria-labelledby="titulo-mis-reservas">
      <header class="vistas__encabezado">
        ${tituloExistente ? "" : '<h1 id="titulo-mis-reservas">Mis reservas</h1>'}
        <p>Las reservas se guardan 48 horas. Pasa por la biblioteca con tu carné.</p>
      </header>
      <p class="sr-only" data-estado role="status" aria-live="polite"></p>
      <div class="aviso" data-mensaje role="status" aria-live="polite" hidden style="display: none;"></div>
      <section data-activos aria-label="Reservas activas"></section>
      <section data-historial aria-labelledby="mis-reservas-historial-titulo" hidden></section>
      <dialog class="mis-reservas__dialogo" aria-labelledby="${tituloDialogo}">
        <div class="mis-reservas__dialogo-contenido">
          <h2 id="${tituloDialogo}" data-pregunta-dialogo></h2>
          <div class="mis-reservas__dialogo-acciones">
            <button class="btn btn--acento" type="button" data-confirmar>Confirmar</button>
            <button class="btn btn--fantasma" type="button" data-volver>Volver</button>
          </div>
        </div>
      </dialog>
    </section>
  `;

  const estado = contenedor.querySelector("[data-estado]");
  const mensaje = contenedor.querySelector("[data-mensaje]");
  const activos = contenedor.querySelector("[data-activos]");
  const historial = contenedor.querySelector("[data-historial]");
  const dialogo = contenedor.querySelector("dialog");
  const preguntaDialogo = contenedor.querySelector("[data-pregunta-dialogo]");
  const botonConfirmar = contenedor.querySelector("[data-confirmar]");
  const botonVolver = contenedor.querySelector("[data-volver]");
  let reservaPendiente = null;
  mensaje.style.display = "none";

  function mostrarMensaje(texto, error = false) {
    mensaje.textContent = texto;
    mensaje.hidden = !texto;
    if (texto) {
      mensaje.style.removeProperty("display");
    } else {
      mensaje.style.display = "none";
    }
    mensaje.className = `aviso${error ? " aviso--error" : " aviso--info"}`;
    mensaje.setAttribute("role", error ? "alert" : "status");
  }

  function actualizarCuentaRegresiva() {
    const ahora = Date.now();
    let hayVencida = false;
    activos.querySelectorAll("[data-expira]").forEach((cuenta) => {
      const expira = new Date(cuenta.dataset.expira).getTime();
      const inicio = new Date(cuenta.dataset.inicio).getTime();
      const duracion = Math.max(expira - inicio, 1);
      const restante = Math.max(0, expira - ahora);
      if (!restante) hayVencida = true;
      const horas = Math.floor(restante / 3_600_000);
      const minutos = Math.floor((restante % 3_600_000) / 60_000);
      cuenta.textContent = restante
        ? `Se guarda ${horas} h ${String(minutos).padStart(2, "0")} min más`
        : "La reserva ya venció.";
      cuenta.classList.toggle("mis-reservas__cuenta--reservado", restante < 24 * 3_600_000);
      cuenta.classList.toggle("mis-reservas__cuenta--prestado", restante < 3 * 3_600_000);
      const barra = cuenta.nextElementSibling;
      if (barra instanceof HTMLProgressElement) {
        barra.max = duracion;
        barra.value = restante;
        barra.classList.toggle("mis-reservas__barra--reservado", restante < 24 * 3_600_000);
        barra.classList.toggle("mis-reservas__barra--prestado", restante < 3 * 3_600_000);
      }
    });
    if (hayVencida) void refrescar();
  }

  function mostrarEsqueletos() {
    activos.setAttribute("aria-busy", "true");
    historial.hidden = true;
    const rejilla = nodo("div", "mis-reservas__rejilla");
    for (let indice = 0; indice < 2; indice += 1) {
      rejilla.append(nodo("div", "vistas__esqueleto mis-reservas__esqueleto"));
    }
    activos.replaceChildren(
      nodo("h2", "", "Reservas activas"),
      rejilla,
    );
    estado.textContent = "Cargando tus reservas…";
  }

  function abrirDialogo(reserva) {
    reservaPendiente = reserva;
    preguntaDialogo.textContent = `¿Cancelar tu reserva de «${reserva.titulo}»?`;
    dialogo.showModal();
    botonConfirmar.focus();
  }

  function crearTarjeta(reserva) {
    const tarjeta = nodo(
      "article",
      `lomo lomo--${["libro", "tesis", "articulo", "recurso_digital"].includes(reserva.tipo)
        ? reserva.tipo : "libro"} mis-reservas__tarjeta`,
    );
    tarjeta.append(
      nodo("p", "lomo__tipo", tipoVisible(reserva.tipo)),
      nodo("h3", "mis-reservas__titulo", reserva.titulo || "Título no indicado"),
      nodo("p", "lomo__autor", reserva.autor || "Autor no indicado"),
    );
    const insignia = reserva.ejemplar_id != null
      ? nodo("span", "estado estado--disponible", `Lista para recoger${reserva.estante ? ` · Estante ${reserva.estante}` : ""}`)
      : nodo("span", "estado estado--reservado", "En cola");
    tarjeta.append(insignia);

    const cuenta = nodo("p", "mis-reservas__cuenta");
    cuenta.dataset.expira = reserva.expira_en || "";
    cuenta.dataset.inicio = reserva.fecha_reserva || "";
    cuenta.setAttribute("aria-live", "off");
    const barra = document.createElement("progress");
    barra.className = "mis-reservas__barra mis-reservas__barra--disponible";
    barra.setAttribute("aria-label", `Tiempo restante de la reserva de ${reserva.titulo || "material"}`);
    tarjeta.append(cuenta, barra);

    const acciones = nodo("div", "mis-reservas__acciones");
    const cancelar = nodo("button", "btn btn--fantasma", "Cancelar reserva");
    cancelar.type = "button";
    cancelar.addEventListener("click", () => abrirDialogo(reserva), {
      signal: controlador.signal,
    });
    const preguntar = nodo("button", "btn btn--primario", "Preguntar al agente");
    preguntar.type = "button";
    preguntar.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("preguntar-agente", {
        detail: { texto: `¿Cuándo puedo recoger «${reserva.titulo}»?` },
      }));
    }, { signal: controlador.signal });
    acciones.append(cancelar, preguntar);
    tarjeta.append(acciones);
    return tarjeta;
  }

  function mostrarActivas(reservas) {
    activos.hidden = !reservas.length;
    if (!reservas.length) {
      activos.replaceChildren();
      return;
    }
    const rejilla = nodo("div", "mis-reservas__rejilla");
    reservas.forEach((reserva) => rejilla.append(crearTarjeta(reserva)));
    activos.replaceChildren(nodo("h2", "", "Reservas activas"), rejilla);
    actualizarCuentaRegresiva();
  }

  function mostrarHistorial(reservas) {
    historial.hidden = !reservas.length;
    if (!reservas.length) {
      historial.replaceChildren();
      return;
    }
    const lista = nodo("ul", "mis-reservas__historial-lista");
    reservas.forEach((reserva) => {
      const fila = nodo("li", "mis-reservas__historial-fila");
      const datos = nodo("div", "mis-reservas__historial-datos");
      datos.append(
        nodo("strong", "", reserva.titulo || "Título no indicado"),
        nodo("span", "texto-sec", `${fechaVisible(reserva.fecha_reserva)} · ${reserva.autor || "Autor no indicado"}`),
      );
      const estadoReserva = nodo(
        "span",
        `chip mis-reservas__estado mis-reservas__estado--${reserva.estado}`,
        { cumplida: "Cumplida", vencida: "Vencida", cancelada: "Cancelada" }[reserva.estado]
          || reserva.estado,
      );
      const reservarDeNuevo = nodo("button", "btn btn--fantasma", "Reservar de nuevo");
      reservarDeNuevo.type = "button";
      reservarDeNuevo.addEventListener("click", () => {
        window.dispatchEvent(new CustomEvent("preguntar-agente", {
          detail: { texto: `Quiero reservar «${reserva.titulo}»` },
        }));
      }, { signal: controlador.signal });
      fila.append(datos, estadoReserva, reservarDeNuevo);
      lista.append(fila);
    });
    const titulo = nodo("h2", "", "Historial");
    titulo.id = "mis-reservas-historial-titulo";
    historial.replaceChildren(titulo, lista);
  }

  function mostrarVacio() {
    activos.hidden = false;
    activos.replaceChildren();
    const vacio = nodo("div", "vistas__vacio");
    vacio.append(
      nodo("span", "vistas__vacio-icono", "⌕"),
      nodo("p", "", "No tienes reservas. Busca un libro en el chat y pulsa Reservar."),
    );
    const irAlChat = nodo("button", "btn btn--primario", "Ir al chat");
    irAlChat.type = "button";
    irAlChat.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("preguntar-agente"));
    }, { signal: controlador.signal });
    vacio.append(irAlChat);
    activos.replaceChildren(vacio);
  }

  async function refrescar() {
    if (destruida) return;
    solicitudActiva?.abort();
    solicitudActiva = new AbortController();
    mostrarEsqueletos();
    try {
      const respuesta = await fetch("/api/mis-reservas", {
        signal: solicitudActiva.signal,
      });
      const datos = await leerRespuesta(respuesta);
      if (destruida || solicitudActiva.signal.aborted) return;
      if (!respuesta.ok) {
        if (respuesta.status === 401) {
          activos.hidden = false;
          historial.hidden = true;
          const acceso = nodo("div", "vistas__vacio");
          acceso.append(nodo("p", "", "Inicia sesión para ver tus reservas."));
          const iniciarSesion = nodo("button", "btn btn--primario", "Iniciar sesión");
          iniciarSesion.type = "button";
          iniciarSesion.addEventListener("click", () => {
            window.dispatchEvent(new CustomEvent("pedir-login"));
          }, { signal: controlador.signal });
          acceso.append(iniciarSesion);
          activos.replaceChildren(acceso);
          activos.setAttribute("aria-busy", "false");
          estado.textContent = "Inicia sesión para ver tus reservas.";
          return;
        }
        throw new Error(datos.mensaje || "No fue posible cargar tus reservas.");
      }
      const reservasActivas = Array.isArray(datos.activas) ? datos.activas : [];
      const reservasHistorial = Array.isArray(datos.historial) ? datos.historial : [];
      mostrarActivas(reservasActivas);
      mostrarHistorial(reservasHistorial);
      if (!reservasActivas.length && !reservasHistorial.length) mostrarVacio();
      activos.setAttribute("aria-busy", "false");
      estado.textContent = `Reservas cargadas: ${reservasActivas.length} activas y ${reservasHistorial.length} en el historial.`;
    } catch (error) {
      if (error.name === "AbortError" || destruida) return;
      const aviso = nodo(
        "div",
        "aviso aviso--error mis-reservas__error",
      );
      aviso.setAttribute("role", "alert");
      aviso.append(nodo(
        "p",
        "",
        error.message || "No se pudieron cargar las reservas. Revisa tu conexión.",
      ));
      const reintentar = nodo("button", "btn btn--fantasma", "Reintentar");
      reintentar.type = "button";
      reintentar.addEventListener("click", () => void refrescar(), {
        signal: controlador.signal,
      });
      aviso.append(reintentar);
      activos.hidden = false;
      activos.replaceChildren(aviso);
      activos.setAttribute("aria-busy", "false");
      historial.hidden = true;
      estado.textContent = aviso.textContent;
    }
  }

  async function confirmarCancelacion() {
    if (!reservaPendiente || destruida) return;
    const reserva = reservaPendiente;
    botonConfirmar.disabled = true;
    estado.textContent = "Cancelando la reserva…";
    try {
      const respuesta = await fetch(`/api/reservas/${encodeURIComponent(reserva.reserva_id)}/cancelar`, {
        method: "POST",
      });
      const datos = await leerRespuesta(respuesta);
      if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible cancelar la reserva.");
      dialogo.close();
      reservaPendiente = null;
      await refrescar();
      mostrarMensaje(datos.mensaje || "La reserva se canceló.");
      actualizacionLocal = true;
      window.dispatchEvent(new CustomEvent("cuenta-cambio"));
      actualizacionLocal = false;
    } catch (error) {
      if (destruida) return;
      dialogo.close();
      reservaPendiente = null;
      await refrescar();
      mostrarMensaje(
        error.message || "No fue posible cancelar la reserva. Inténtalo de nuevo.",
        true,
      );
    } finally {
      botonConfirmar.disabled = false;
    }
  }

  botonConfirmar.addEventListener("click", () => void confirmarCancelacion(), {
    signal: controlador.signal,
  });
  botonVolver.addEventListener("click", () => {
    reservaPendiente = null;
    dialogo.close();
  }, { signal: controlador.signal });
  dialogo.addEventListener("close", () => {
    reservaPendiente = null;
  }, { signal: controlador.signal });
  window.addEventListener("cuenta-cambio", () => {
    if (!actualizacionLocal) void refrescar();
  }, { signal: controlador.signal });
  temporizador = window.setInterval(actualizarCuentaRegresiva, 60_000);
  void refrescar();

  return {
    refrescar,
    destruir() {
      destruida = true;
      window.clearInterval(temporizador);
      solicitudActiva?.abort();
      controlador.abort();
      if (dialogo.open) dialogo.close();
    },
  };
}
