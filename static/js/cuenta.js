import { obtenerCuenta, obtenerMisReservas } from "./api.js";
import { cerrarSesion as iconoCerrar } from "./iconos.js";

const meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

function convertirFecha(valor, diasRetraso = 0) {
  if (!valor) return null;
  const iso = new Date(valor);
  if (!Number.isNaN(iso.getTime())) return iso;
  const partes = String(valor).toLocaleLowerCase("es").match(
    /(\d{1,2}) de (enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?: a las (\d{1,2})(?::(\d{2}))? (a\. m\.|p\. m\.))?/,
  );
  if (!partes) return null;
  const ahora = new Date();
  let anio = ahora.getFullYear();
  let hora = Number(partes[3]) || 0;
  if (partes[5]?.startsWith("p") && hora < 12) hora += 12;
  if (partes[5]?.startsWith("a") && hora === 12) hora = 0;
  let resultado = new Date(anio, meses.indexOf(partes[2]), Number(partes[1]), hora, Number(partes[4]) || 0);
  if (!Number(diasRetraso) && resultado < ahora && resultado.toDateString() !== ahora.toDateString()) {
    resultado = new Date(anio + 1, meses.indexOf(partes[2]), Number(partes[1]), hora, Number(partes[4]) || 0);
  }
  return resultado;
}

const fecha = (valor, opciones = { day: "numeric", month: "long" }, diasRetraso = 0) => {
  const fechaValor = convertirFecha(valor, diasRetraso);
  if (!fechaValor) return "Fecha no disponible";
  return new Intl.DateTimeFormat("es-CO", opciones).format(fechaValor);
};

const dinero = (valor) => new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
}).format(Number(valor) || 0);

function diasHasta(valor, diasRetraso = 0) {
  if (Number(diasRetraso) > 0) return -Number(diasRetraso);
  const limite = convertirFecha(valor);
  if (!limite) return null;
  return Math.ceil((limite.setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86400000);
}

function crear(tag, clase, texto) {
  const elemento = document.createElement(tag);
  if (clase) elemento.className = clase;
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
}

export function montarCuenta(contenedor, { alRenovar, alCerrar, alLogin, alCancelar }) {
  let usuarioActual = null;
  let generacion = 0;
  let mensajeAccion = null;

  const dialogo = document.createElement("dialog");
  dialogo.className = "cuenta-dialogo";
  dialogo.setAttribute("aria-labelledby", "cuenta-dialogo-titulo");
  const textoDialogo = crear("p", "", "");
  textoDialogo.id = "cuenta-dialogo-titulo";
  const accionesDialogo = crear("div", "cuenta-dialogo__acciones");
  const botonConfirmarCancelacion = crear("button", "btn btn--acento", "Confirmar");
  botonConfirmarCancelacion.type = "button";
  const volverCancelacion = crear("button", "btn btn--fantasma", "Volver");
  volverCancelacion.type = "button";
  accionesDialogo.append(botonConfirmarCancelacion, volverCancelacion);
  dialogo.append(textoDialogo, accionesDialogo);
  document.body.append(dialogo);

  const vacio = () => {
    contenedor.replaceChildren(crear("p", "cuenta-vacia", "Inicia sesión para ver tu cuenta."));
  };

  function mostrarInvitado() {
    const mensaje = crear("p", "cuenta-vacia", "Inicia sesión… para ver tu cuenta, préstamos, reservas y multas.");
    const boton = crear("button", "btn btn--acento", "Iniciar sesión");
    boton.type = "button";
    boton.addEventListener("click", () => alLogin?.());
    contenedor.replaceChildren(mensaje, boton);
  }

  function claveTexto(valor) {
    return String(valor || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("es");
  }

  async function completarIdsReservas(reservasOriginales) {
    const reservas = reservasOriginales.map((reserva) => ({ ...reserva }));
    if (!reservas.some((reserva) => reserva.reserva_id == null && reserva.id == null)) {
      return { reservas, aviso: "" };
    }

    // Compatibilidad con servidores anteriores que no incluían reserva_id.
    try {
      const respuesta = await obtenerMisReservas();
      const filas = Array.isArray(respuesta)
        ? respuesta
        : Array.isArray(respuesta?.activas)
          ? respuesta.activas
          : Array.isArray(respuesta?.reservas)
          ? respuesta.reservas
          : Array.isArray(respuesta?.datos?.reservas) ? respuesta.datos.reservas : null;
      if (!filas) throw new Error("La respuesta de reservas no tiene un formato válido.");
      const disponibles = filas.map((reserva) => ({ ...reserva })).filter(
        (reserva) => reserva.reserva_id != null || reserva.id != null,
      );
      reservas.forEach((reserva) => {
        if (reserva.reserva_id != null || reserva.id != null) return;
        const indice = disponibles.findIndex((candidata) => (
          claveTexto(candidata.titulo) === claveTexto(reserva.titulo)
          && (Number.isNaN(Date.parse(reserva.expira_en))
            || !candidata.expira_en
            || Date.parse(candidata.expira_en) === Date.parse(reserva.expira_en))
        ));
        if (indice < 0) return;
        const [coincidencia] = disponibles.splice(indice, 1);
        reserva.reserva_id = coincidencia.reserva_id ?? coincidencia.id;
      });
      return { reservas, aviso: "" };
    } catch {
      return {
        reservas,
        aviso: "No se pudieron cargar los identificadores de tus reservas. Inténtalo de nuevo más tarde.",
      };
    }
  }

  function confirmarCancelacion(titulo) {
    textoDialogo.textContent = `¿Cancelar tu reserva de «${titulo}»?`;
    return new Promise((resolver) => {
      const controladores = new AbortController();
      const terminar = (valor) => dialogo.close(valor);
      botonConfirmarCancelacion.addEventListener("click", () => terminar("confirmar"), { signal: controladores.signal });
      volverCancelacion.addEventListener("click", () => terminar("volver"), { signal: controladores.signal });
      dialogo.addEventListener("close", () => {
        controladores.abort();
        resolver(dialogo.returnValue);
      }, { once: true });
      dialogo.showModal();
      volverCancelacion.focus({ preventScroll: true });
    });
  }

  function dibujar(usuario, datos, avisoReservas = "") {
    contenedor.replaceChildren();
    if (mensajeAccion) {
      contenedor.append(crear("p", `aviso aviso--${mensajeAccion.tipo}`, mensajeAccion.texto));
    }
    const cabecera = crear("header", "cuenta-usuario");
    const avatar = crear("span", "cuenta-avatar");
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = (usuario.nombre || "?").split(/\s+/).slice(0, 2).map((parte) => parte[0] || "").join("").toUpperCase();
    const identidad = document.createElement("div");
    identidad.append(
      crear("h3", "", usuario.nombre || "Usuario"),
      crear("p", "texto-sec", usuario.codigo || ""),
      crear("p", "texto-sec", [usuario.tipo, usuario.programa].filter(Boolean).join(" · ")),
    );
    cabecera.append(avatar, identidad);
    contenedor.append(cabecera);

    const prestamos = Array.isArray(datos.prestamos) ? datos.prestamos : [];
    const multas = Array.isArray(datos.multas) ? datos.multas : [];
    const tieneMultasPendientes = Number(datos.total_multas) > 0
      || multas.some((multa) => multa.pendiente !== false
        && !["pagada", "paga", "cancelada", "saldada"].includes(String(multa.estado || "").toLocaleLowerCase("es")));
    const bloquePrestamos = crear("section", "cuenta-seccion");
    bloquePrestamos.append(crear("h3", "", `Préstamos (${prestamos.length})`));
    if (!prestamos.length) bloquePrestamos.append(crear("p", "texto-sec", "No tienes préstamos activos."));
    prestamos.forEach((prestamo) => {
      const item = crear("article", "cuenta-item");
      item.append(crear("strong", "", prestamo.titulo || "Material"));
      const vencimiento = fecha(prestamo.fecha_vencimiento, { day: "numeric", month: "long" }, prestamo.dias_retraso);
      const dias = diasHasta(prestamo.fecha_vencimiento, prestamo.dias_retraso);
      const renovaciones = Number(prestamo.renovaciones) || 0;
      item.append(crear("p", "", dias !== null && dias < 0
        ? `Vencido hace ${Math.abs(dias)} ${Math.abs(dias) === 1 ? "día" : "días"}`
        : `Vence el ${vencimiento}`));
      const barra = crear("div", `dias-barra${dias !== null && dias < 0 ? " dias-barra--vencida" : dias !== null && dias <= 3 ? " dias-barra--alerta" : ""}`);
      barra.setAttribute("role", "img");
      barra.setAttribute("aria-label", dias !== null && dias < 0 ? `Préstamo vencido hace ${Math.abs(dias)} días` : `${Math.max(0, dias ?? 0)} días restantes`);
      const relleno = document.createElement("span");
      relleno.style.width = `${dias !== null && dias < 0 ? 100 : Math.max(0, Math.min(100, (dias ?? 0) / 8 * 100))}%`;
      barra.append(relleno);
      item.append(barra, crear("p", "texto-sec", `${renovaciones} de 3 renovaciones`));
      if (alRenovar) {
        const boton = crear("button", "btn btn--fantasma", "Renovar");
        boton.type = "button";
        const motivoNoRenovable = tieneMultasPendientes
          ? "Tiene multas pendientes"
          : dias !== null && dias < 0
            ? "Vencido: no se puede renovar"
            : renovaciones >= 3
              ? "Máximo de renovaciones alcanzado"
              : "";
        if (motivoNoRenovable) {
          boton.disabled = true;
          boton.textContent = motivoNoRenovable;
          boton.title = motivoNoRenovable;
          boton.setAttribute("aria-label", motivoNoRenovable);
        } else {
          boton.addEventListener("click", () => alRenovar(prestamo.titulo));
        }
        item.append(boton);
      }
      bloquePrestamos.append(item);
    });
    contenedor.append(bloquePrestamos);

    const reservas = Array.isArray(datos.reservas) ? datos.reservas : [];
    const bloqueReservas = crear("section", "cuenta-seccion");
    bloqueReservas.append(crear("h3", "", `Reservas (${reservas.length})`));
    if (!reservas.length) bloqueReservas.append(crear("p", "texto-sec", "No tienes reservas activas."));
    reservas.forEach((reserva) => {
      const item = crear("article", "cuenta-item");
      item.append(crear("strong", "", reserva.titulo || "Material"));
      item.append(crear("p", "", `Se guarda hasta el ${fecha(reserva.expira_en, { day: "numeric", month: "long", hour: "numeric", minute: "2-digit" })}`));
      const botonCancelar = crear("button", "btn btn--fantasma", "Cancelar");
      botonCancelar.type = "button";
      const reservaId = reserva.reserva_id ?? reserva.id;
      botonCancelar.disabled = reservaId == null;
      if (botonCancelar.disabled) botonCancelar.title = "No se pudo obtener el identificador de esta reserva.";
      botonCancelar.addEventListener("click", async () => {
        if (await confirmarCancelacion(reserva.titulo || "este material") !== "confirmar") return;
        botonCancelar.disabled = true;
        try {
          if (typeof alCancelar !== "function") throw new Error("No está disponible la cancelación de reservas.");
          const resultado = await alCancelar(reservaId);
          if (!resultado?.ok) {
            mensajeAccion = { tipo: "error", texto: resultado?.mensaje || "No se pudo cancelar la reserva." };
          } else {
            mensajeAccion = { tipo: "info", texto: resultado.mensaje || "Reserva cancelada." };
            window.dispatchEvent(new CustomEvent("cuenta-cambio"));
            return;
          }
          await actualizar(usuarioActual);
        } catch (error) {
          mensajeAccion = { tipo: "error", texto: error.message || "No se pudo cancelar la reserva. Inténtalo de nuevo." };
          await actualizar(usuarioActual);
        }
      });
      item.append(botonCancelar);
      bloqueReservas.append(item);
    });
    if (avisoReservas) bloqueReservas.append(crear("p", "aviso aviso--error", avisoReservas));
    const enlaceReservas = crear("a", "cuenta-enlace-reservas", "Ver todas mis reservas");
    enlaceReservas.href = "#mis-reservas";
    bloqueReservas.append(enlaceReservas);
    contenedor.append(bloqueReservas);

    const bloqueMultas = crear("section", "cuenta-seccion");
    bloqueMultas.append(crear("h3", "", `Multas (${multas.length})`));
    if (!multas.length) bloqueMultas.append(crear("p", "texto-sec", "No tienes multas pendientes."));
    multas.forEach((multa) => {
      const item = crear("article", "cuenta-item");
      item.append(crear("strong", "", dinero(multa.valor)));
      item.append(crear("p", "", `${Number(multa.dias) || 0} días · Pendiente`));
      bloqueMultas.append(item);
    });
    if (Number(datos.total_multas) > 0) bloqueMultas.append(crear("p", "cuenta-total", `Total pendiente: ${dinero(datos.total_multas)}`));
    contenedor.append(bloqueMultas);

    const botonCerrar = document.createElement("button");
    botonCerrar.type = "button";
    botonCerrar.className = "btn btn--fantasma cuenta-cerrar";
    const icono = document.createElement("span");
    icono.className = "icono";
    icono.innerHTML = iconoCerrar;
    icono.setAttribute("aria-hidden", "true");
    botonCerrar.replaceChildren(icono, document.createTextNode("Cerrar sesión"));
    botonCerrar.addEventListener("click", async () => {
      botonCerrar.disabled = true;
      try {
        await alCerrar?.();
        vacio();
      } catch {
        botonCerrar.disabled = false;
        const aviso = crear("p", "aviso aviso--error", "No se pudo cerrar la sesión. Inténtalo de nuevo.");
        contenedor.prepend(aviso);
      }
    });
    contenedor.append(botonCerrar);
  }

  async function actualizar(usuario) {
    if (!usuario) {
      usuarioActual = null;
      generacion += 1;
      vacio();
      return;
    }
    usuarioActual = usuario;
    const solicitud = ++generacion;
    contenedor.replaceChildren(crear("p", "texto-sec", "Actualizando tu cuenta…"));
    try {
      const datos = await obtenerCuenta();
      const reservas = await completarIdsReservas(Array.isArray(datos.reservas) ? datos.reservas : []);
      if (solicitud !== generacion) return;
      dibujar(usuario, { ...datos, reservas: reservas.reservas }, reservas.aviso);
    } catch {
      if (solicitud !== generacion) return;
      contenedor.replaceChildren(crear("p", "cuenta-vacia", "No se pudo actualizar tu cuenta ahora. Inténtalo de nuevo en un momento."));
    }
  }

  vacio();
  return {
    actualizar,
    refrescar: () => actualizar(usuarioActual),
    mostrarInvitado,
    limpiar: () => {
      usuarioActual = null;
      mensajeAccion = null;
      generacion += 1;
      vacio();
    },
  };
}
