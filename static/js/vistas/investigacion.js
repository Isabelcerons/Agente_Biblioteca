import { investigar, obtenerMaterial, obtenerProgramas } from "../api.js";
import { iconos } from "../iconos.js";

// Todos los datos del endpoint se insertan con textContent: solo los iconos
// (SVG estáticos de iconos.js) usan innerHTML.
const tipos = { libro: "Libro", tesis: "Tesis", articulo: "Artículo", recurso_digital: "Recurso digital" };
const iconoTipo = { libro: "libro-abierto", tesis: "resumen", articulo: "fuente", recurso_digital: "catalogo" };
const ejemplos = [
  "Cultivo de cacao en el Putumayo",
  "Seguridad en redes informáticas",
  "Emprendimiento y planes de negocio",
];
const MAX_TEMA = 500;
const LARGO_FRAGMENTO = 320;

const crear = (etiqueta, clase, texto) => {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined && texto !== null) nodo.textContent = String(texto);
  return nodo;
};

const icono = (nombre, clase = "inv-icono") => {
  const nodo = crear("span", clase);
  nodo.setAttribute("aria-hidden", "true");
  nodo.innerHTML = iconos[nombre] || "";
  return nodo;
};

const boton = (texto, clase = "btn btn--fantasma", nombreIcono = "") => {
  const nodo = crear("button", clase);
  nodo.type = "button";
  if (nombreIcono) nodo.append(icono(nombreIcono));
  nodo.append(crear("span", "", texto));
  return nodo;
};

const porcentaje = (valor) => {
  const numero = Number(valor);
  return Number.isFinite(numero) ? Math.round(Math.max(0, Math.min(1, numero)) * 100) : null;
};

const lista = (valor) => (Array.isArray(valor) ? valor : []);

export function montarInvestigacion(contenedor) {
  let generacion = 0;
  let fichaGeneracion = 0;
  let programasCargados = false;

  contenedor.replaceChildren();
  const cabecera = crear("header", "inv-cabecera");
  const textoCabecera = crear("div", "inv-cabecera__texto");
  const titulo = crear("h1", "", "Asistente de investigación");
  titulo.id = "titulo-investigacion";
  titulo.tabIndex = -1;
  textoCabecera.append(
    crear("p", "inv-antetitulo", "Sala de consulta"),
    titulo,
    crear("p", "inv-intro", "Cuéntanos tu tema y buscamos en los libros y tesis de la biblioteca: te mostramos qué materiales consultar, los fragmentos que lo respaldan y sus referencias en APA."),
  );
  cabecera.append(icono("investigar", "inv-cabecera__sello"), textoCabecera);

  const formulario = crear("form", "inv-formulario tarjeta");
  formulario.setAttribute("role", "search");
  formulario.setAttribute("aria-label", "Buscar evidencia para una investigación");
  formulario.noValidate = true;

  const campoTema = crear("label", "campo inv-campo-tema");
  campoTema.htmlFor = "inv-tema";
  campoTema.append(crear("span", "", "¿Sobre qué tema estás investigando?"));
  const tema = crear("textarea");
  tema.id = "inv-tema";
  tema.name = "tema";
  tema.rows = 2;
  tema.maxLength = MAX_TEMA;
  tema.required = true;
  tema.placeholder = "Ej.: impacto del cultivo de cacao en la economía campesina del Putumayo";
  tema.setAttribute("aria-describedby", "inv-tema-ayuda inv-tema-error");
  const ayudaTema = crear("small", "inv-ayuda", `Escribe una frase corta o una pregunta (máximo ${MAX_TEMA} caracteres). Pulsa Enter para buscar.`);
  ayudaTema.id = "inv-tema-ayuda";
  const errorTema = crear("small", "campo-error");
  errorTema.id = "inv-tema-error";
  campoTema.append(tema, ayudaTema, errorTema);

  const campoPrograma = crear("label", "campo inv-campo-programa");
  campoPrograma.htmlFor = "inv-programa";
  campoPrograma.append(crear("span", "", "Programa académico (opcional)"));
  const programa = crear("select");
  programa.id = "inv-programa";
  programa.name = "programa";
  const todos = crear("option", "", "Todos los programas");
  todos.value = "";
  programa.append(todos);
  campoPrograma.append(programa);

  const acciones = crear("div", "inv-formulario__acciones");
  const investigarBoton = crear("button", "btn btn--primario inv-enviar");
  investigarBoton.type = "submit";
  investigarBoton.append(icono("buscar"), crear("span", "", "Investigar en el acervo"));
  const limpiar = boton("Limpiar", "btn btn--fantasma");
  acciones.append(investigarBoton, limpiar);

  const ejemplosNodo = crear("div", "inv-ejemplos");
  const etiquetaEjemplos = crear("p", "inv-ejemplos__titulo", "¿Sin ideas? Prueba con:");
  etiquetaEjemplos.id = "inv-ejemplos-titulo";
  const listaEjemplos = crear("ul", "inv-chips");
  listaEjemplos.setAttribute("aria-labelledby", etiquetaEjemplos.id);
  ejemplos.forEach((texto) => {
    const item = crear("li");
    const chip = boton(texto, "chip inv-chip", "libro-abierto");
    chip.addEventListener("click", () => buscar(texto));
    item.append(chip);
    listaEjemplos.append(item);
  });
  ejemplosNodo.append(etiquetaEjemplos, listaEjemplos);

  formulario.append(campoTema, campoPrograma, acciones, ejemplosNodo);

  const estado = crear("p", "inv-estado");
  estado.setAttribute("role", "status");
  estado.setAttribute("aria-live", "polite");
  const resultados = crear("div", "inv-resultados");
  resultados.setAttribute("aria-live", "off");

  const dialogo = crear("dialog", "catalogo__dialogo inv-dialogo");
  dialogo.setAttribute("aria-labelledby", "inv-ficha-titulo");
  const dialogoCabecera = crear("header");
  const dialogoTitulo = crear("h2", "", "Ficha del material");
  dialogoTitulo.id = "inv-ficha-titulo";
  const cerrar = boton("Cerrar");
  cerrar.addEventListener("click", () => dialogo.close());
  dialogoCabecera.append(dialogoTitulo, cerrar);
  const ficha = crear("div");
  ficha.dataset.ficha = "";
  dialogo.append(dialogoCabecera, ficha);
  dialogo.addEventListener("close", () => { fichaGeneracion++; });

  contenedor.append(cabecera, formulario, estado, resultados, dialogo);
  mostrarInicio();

  function pedirAgente(texto) {
    if (dialogo.open) dialogo.close();
    window.dispatchEvent(new CustomEvent("preguntar-agente", { detail: { texto } }));
  }

  async function cargarProgramas() {
    if (programasCargados) return;
    try {
      const datos = await obtenerProgramas();
      const valores = lista(datos?.programas).filter((valor) => typeof valor === "string" && valor.trim());
      const elegido = programa.value;
      programa.querySelectorAll("option:not(:first-child)").forEach((opcion) => opcion.remove());
      valores.forEach((valor) => {
        const opcion = crear("option", "", valor);
        opcion.value = valor;
        programa.append(opcion);
      });
      programa.value = valores.includes(elegido) ? elegido : "";
      programasCargados = true;
    } catch {
      // Sin la lista se puede investigar igual en todo el acervo.
      todos.textContent = "Todos los programas (lista no disponible)";
    }
  }

  function mostrarInicio() {
    const vacio = crear("section", "inv-vacio");
    vacio.setAttribute("aria-label", "Cómo funciona");
    const pasos = crear("ol", "inv-pasos");
    [
      ["buscar", "Escribe tu tema", "Usa las palabras con las que lo explicarías a tu director o directora."],
      ["catalogo", "Revisa los materiales", "Libros y tesis del acervo ordenados por cercanía con tu tema."],
      ["fuente", "Cita con confianza", "Cada idea remite a un fragmento real y a su referencia en APA."],
    ].forEach(([nombre, tituloPaso, texto]) => {
      const paso = crear("li", "inv-paso");
      paso.append(icono(nombre, "inv-paso__icono"), crear("strong", "", tituloPaso), crear("span", "texto-sec", texto));
      pasos.append(paso);
    });
    vacio.append(pasos);
    resultados.replaceChildren(vacio);
  }

  function mostrarCarga() {
    const carga = crear("div", "inv-carga");
    carga.setAttribute("aria-hidden", "true");
    for (let i = 0; i < 3; i += 1) carga.append(crear("div", "inv-carga__tarjeta"));
    resultados.replaceChildren(carga);
  }

  function mostrarError(mensaje) {
    const aviso = crear("div", "aviso aviso--error inv-aviso");
    aviso.setAttribute("role", "alert");
    const cuerpo = crear("div");
    const reintentar = boton("Reintentar", "btn btn--fantasma", "repetir");
    reintentar.addEventListener("click", () => buscar(tema.value));
    cuerpo.append(crear("p", "", mensaje), reintentar);
    aviso.append(icono("alerta"), cuerpo);
    resultados.replaceChildren(aviso);
  }

  function validar() {
    const valor = tema.value.trim();
    let mensaje = "";
    if (!valor) mensaje = "Escribe el tema que quieres investigar.";
    else if (valor.length > MAX_TEMA) mensaje = `El tema puede tener hasta ${MAX_TEMA} caracteres.`;
    errorTema.textContent = mensaje;
    if (mensaje) tema.setAttribute("aria-invalid", "true");
    else tema.removeAttribute("aria-invalid");
    return mensaje ? null : valor;
  }

  async function buscar(texto) {
    if (typeof texto === "string") tema.value = texto;
    const valor = validar();
    if (!valor) {
      tema.focus();
      return;
    }
    const solicitud = ++generacion;
    const programaElegido = programa.value || null;
    investigarBoton.disabled = true;
    investigarBoton.lastElementChild.textContent = "Buscando en los estantes…";
    formulario.setAttribute("aria-busy", "true");
    resultados.setAttribute("aria-busy", "true");
    estado.textContent = `Buscando evidencia sobre «${valor}»${programaElegido ? ` en ${programaElegido}` : ""}…`;
    mostrarCarga();
    try {
      const datos = await investigar(valor, programaElegido);
      if (solicitud !== generacion) return;
      if (!datos || typeof datos !== "object") throw new Error("Respuesta no válida");
      pintar(datos, programaElegido);
    } catch (error) {
      if (solicitud !== generacion) return;
      estado.textContent = "No pudimos completar la búsqueda.";
      mostrarError(error?.message || "No pudimos consultar el acervo. Inténtalo de nuevo en un momento.");
    } finally {
      if (solicitud === generacion) {
        investigarBoton.disabled = false;
        investigarBoton.lastElementChild.textContent = "Investigar en el acervo";
        formulario.removeAttribute("aria-busy");
        resultados.removeAttribute("aria-busy");
      }
    }
  }

  function seccion(clase, nombreIcono, textoTitulo, idTitulo, conteo) {
    const nodo = crear("section", `inv-seccion ${clase}`);
    nodo.setAttribute("aria-labelledby", idTitulo);
    const encabezado = crear("h2", "inv-seccion__titulo");
    encabezado.id = idTitulo;
    encabezado.append(icono(nombreIcono), crear("span", "", textoTitulo));
    if (conteo !== undefined) encabezado.append(crear("span", "inv-contador", conteo));
    nodo.append(encabezado);
    return nodo;
  }

  function pintar(datos, programaElegido) {
    const materiales = lista(datos.materiales).filter((m) => m && m.material_id != null);
    const fuentes = lista(datos.fuentes).filter((f) => f && typeof f.texto === "string");
    const subtemas = lista(datos.subtemas).filter((s) => typeof s === "string" && s.trim());
    const referencias = lista(datos.bibliografia).filter((r) => typeof r === "string" && r.trim());
    const porId = new Map(materiales.map((m) => [String(m.material_id), m]));
    const temaMostrado = typeof datos.tema === "string" && datos.tema ? datos.tema : tema.value.trim();
    const nodos = [];

    const resumen = seccion("inv-respuesta", "libro-abierto", "Lo que encontramos en el acervo", "inv-titulo-respuesta");
    const meta = crear("p", "inv-respuesta__meta");
    meta.append(crear("span", "", "Tema: "), crear("strong", "", temaMostrado));
    if (programaElegido) meta.append(crear("span", "", " · Programa: "), crear("strong", "", programaElegido));
    resumen.append(meta);
    const texto = typeof datos.respuesta === "string" ? datos.respuesta : "";
    if (texto) resumen.append(textoConCitas(texto, porId));
    if (datos.ok === false) {
      const ayuda = crear("div", "aviso aviso--info inv-aviso");
      const cuerpo = crear("div");
      cuerpo.append(crear("p", "", "Sugerencias: usa palabras más generales, revisa la ortografía o busca en todos los programas."));
      const accionesAyuda = crear("div", "inv-acciones");
      if (programaElegido) {
        const sinFiltro = boton("Buscar en todos los programas", "btn btn--fantasma", "filtro");
        sinFiltro.addEventListener("click", () => { programa.value = ""; buscar(); });
        accionesAyuda.append(sinFiltro);
      }
      const alAgente = boton("Preguntar al agente", "btn btn--fantasma", "chat");
      alAgente.addEventListener("click", () => pedirAgente(`Busco materiales sobre ${temaMostrado}`));
      accionesAyuda.append(alAgente);
      cuerpo.append(accionesAyuda);
      ayuda.append(icono("alerta"), cuerpo);
      resumen.append(ayuda);
    }
    nodos.push(resumen);

    if (subtemas.length) {
      const nodo = seccion("inv-subtemas", "filtro", "Sigue explorando", "inv-titulo-subtemas");
      nodo.append(crear("p", "texto-sec", "Temas del catálogo relacionados. Pulsa uno para afinar la búsqueda."));
      const chips = crear("ul", "inv-chips");
      subtemas.forEach((subtema) => {
        const item = crear("li");
        const chip = boton(subtema, "chip chip--fuente inv-chip", "buscar");
        chip.setAttribute("aria-label", `Investigar el subtema ${subtema}`);
        chip.addEventListener("click", () => {
          buscar(subtema);
          titulo.scrollIntoView({ block: "start", behavior: movimientoReducido() ? "instant" : "smooth" });
        });
        item.append(chip);
        chips.append(item);
      });
      nodo.append(chips);
      nodos.push(nodo);
    }

    if (materiales.length) {
      const nodo = seccion("inv-materiales", "catalogo", "Materiales recomendados", "inv-titulo-materiales", materiales.length);
      const rejilla = crear("ul", "inv-rejilla");
      materiales.forEach((material, indice) => rejilla.append(tarjetaMaterial(material, indice)));
      nodo.append(rejilla);
      nodos.push(nodo);
    }

    if (fuentes.length) {
      const nodo = seccion("inv-fuentes", "fuente", "Fragmentos de las fuentes", "inv-titulo-fuentes", fuentes.length);
      nodo.append(crear("p", "texto-sec", "Texto literal de los documentos indexados que respalda cada recomendación."));
      const listaFuentes = crear("ul", "inv-lista-fuentes");
      fuentes.forEach((fuente) => listaFuentes.append(tarjetaFuente(fuente, porId.get(String(fuente.material_id)))));
      nodo.append(listaFuentes);
      nodos.push(nodo);
    }

    if (referencias.length) nodos.push(seccionBibliografia(referencias, materiales));

    resultados.replaceChildren(...nodos);
    estado.textContent = datos.ok === false
      ? "No encontramos evidencia suficiente para ese tema."
      : `Encontramos ${materiales.length} ${materiales.length === 1 ? "material" : "materiales"} y ${fuentes.length} ${fuentes.length === 1 ? "fragmento" : "fragmentos"} sobre «${temaMostrado}».`;
    resumen.tabIndex = -1;
    resumen.focus({ preventScroll: true });
    resumen.scrollIntoView({ block: "start", behavior: movimientoReducido() ? "instant" : "smooth" });
  }

  function textoConCitas(texto, porId) {
    const cuerpo = crear("div", "inv-respuesta__texto");
    texto.split(/\n{2,}/).map((parte) => parte.trim()).filter(Boolean).forEach((parrafo) => {
      const p = crear("p");
      const patron = /\[material\s+(\d+)\]/gi;
      let ultimo = 0;
      let coincidencia;
      while ((coincidencia = patron.exec(parrafo)) !== null) {
        p.append(document.createTextNode(parrafo.slice(ultimo, coincidencia.index)));
        const material = porId.get(coincidencia[1]);
        if (material) {
          const cita = crear("a", "inv-cita", material.titulo ? `Ver «${material.titulo}»` : "Ver material");
          cita.href = `#inv-material-${coincidencia[1]}`;
          cita.addEventListener("click", (evento) => {
            evento.preventDefault();
            const destino = resultados.querySelector(`#inv-material-${CSS.escape(coincidencia[1])}`);
            destino?.scrollIntoView({ block: "center", behavior: movimientoReducido() ? "instant" : "smooth" });
            destino?.focus({ preventScroll: true });
          });
          p.append(cita);
        } else {
          p.append(document.createTextNode(coincidencia[0]));
        }
        ultimo = patron.lastIndex;
      }
      p.append(document.createTextNode(parrafo.slice(ultimo)));
      cuerpo.append(p);
    });
    return cuerpo;
  }

  function disponibilidad(material) {
    const disponibles = Number(material.disponibles);
    const total = Number(material.total);
    if (!Number.isFinite(disponibles) || !Number.isFinite(total) || total <= 0) {
      return crear("p", "estado", "Disponibilidad por confirmar");
    }
    return crear(
      "p",
      `estado ${disponibles > 0 ? "estado--disponible" : "estado--reservado"}`,
      disponibles > 0 ? `${disponibles} de ${total} ejemplares disponibles` : `Sin ejemplares libres (${total} en total)`,
    );
  }

  function medidor(valor, etiqueta) {
    const pct = porcentaje(valor);
    if (pct === null) return crear("span");
    const nodo = crear("span", "inv-afinidad");
    nodo.title = "Qué tan cerca está el contenido de tu tema";
    const barra = crear("span", "inv-afinidad__barra");
    barra.setAttribute("aria-hidden", "true");
    const relleno = crear("span", "inv-afinidad__relleno");
    relleno.style.width = `${pct}%`;
    barra.append(relleno);
    nodo.append(barra, crear("span", "", `${etiqueta} ${pct} %`));
    return nodo;
  }

  function tarjetaMaterial(material, indice) {
    const item = crear("li", "inv-tarjeta tarjeta");
    item.id = `inv-material-${material.material_id}`;
    item.tabIndex = -1;
    const tipo = String(material.tipo || "");
    const cabeza = crear("div", "inv-tarjeta__cabeza");
    const lomo = icono(iconoTipo[tipo] || "libro-abierto", "inv-tarjeta__lomo");
    const etiquetas = crear("p", "inv-tarjeta__tipo");
    etiquetas.append(crear("span", "", tipos[tipo] || tipo || "Material"), crear("span", "inv-orden", `#${indice + 1}`));
    cabeza.append(lomo, etiquetas);

    const tituloMaterial = crear("h3", "inv-tarjeta__titulo");
    const abrir = crear("button", "inv-tarjeta__abrir", material.titulo || "Material sin título");
    abrir.type = "button";
    abrir.setAttribute("aria-haspopup", "dialog");
    abrir.addEventListener("click", () => abrirFicha(material));
    tituloMaterial.append(abrir);

    const autoria = [material.autor, material.anio].filter((v) => v !== null && v !== undefined && String(v).trim()).join(" · ");
    const accionesTarjeta = crear("div", "inv-acciones");
    const ver = boton("Ver ficha", "btn btn--fantasma", "libro-abierto");
    ver.setAttribute("aria-haspopup", "dialog");
    ver.setAttribute("aria-label", `Ver ficha de ${material.titulo || "material"}`);
    ver.addEventListener("click", () => abrirFicha(material));
    const disponible = Number(material.disponibles) > 0;
    const reservar = boton(disponible ? "Reservar" : "Solicitar en espera", "btn btn--primario", "reservar");
    reservar.setAttribute("aria-label", `${disponible ? "Reservar" : "Solicitar en espera"} ${material.titulo || "material"}`);
    reservar.addEventListener("click", () => pedirAgente(`Quiero reservar «${material.titulo}»`));
    accionesTarjeta.append(ver, reservar);

    item.append(cabeza, tituloMaterial);
    if (autoria) item.append(crear("p", "texto-sec", autoria));
    item.append(disponibilidad(material), medidor(material.similitud, "Afinidad con tu tema:"), accionesTarjeta);
    return item;
  }

  function tarjetaFuente(fuente, material) {
    const item = crear("li", "inv-fuente");
    const cabeza = crear("div", "inv-fuente__cabeza");
    const datosFuente = crear("div");
    datosFuente.append(crear("p", "inv-fuente__documento", fuente.documento || material?.titulo || "Documento"));
    if (fuente.seccion) datosFuente.append(crear("p", "inv-fuente__seccion", `Sección: ${fuente.seccion}`));
    cabeza.append(icono("fuente", "inv-fuente__icono"), datosFuente);

    const textoCompleto = fuente.texto.trim();
    const cita = crear("blockquote", "inv-fuente__texto");
    const largo = textoCompleto.length > LARGO_FRAGMENTO;
    const parrafo = crear("p", "", largo ? `${textoCompleto.slice(0, LARGO_FRAGMENTO).trimEnd()}…` : textoCompleto);
    cita.append(parrafo);

    const pie = crear("div", "inv-fuente__pie");
    pie.append(medidor(fuente.similitud, "Coincidencia:"));
    const accionesFuente = crear("div", "inv-acciones");
    if (largo) {
      const expandir = boton("Leer fragmento completo", "btn btn--fantasma");
      expandir.setAttribute("aria-expanded", "false");
      expandir.addEventListener("click", () => {
        const abierto = expandir.getAttribute("aria-expanded") === "true";
        parrafo.textContent = abierto ? `${textoCompleto.slice(0, LARGO_FRAGMENTO).trimEnd()}…` : textoCompleto;
        expandir.setAttribute("aria-expanded", String(!abierto));
        expandir.lastElementChild.textContent = abierto ? "Leer fragmento completo" : "Mostrar menos";
      });
      accionesFuente.append(expandir);
    }
    if (fuente.material_id != null) {
      const ver = boton("Ver material", "btn btn--fantasma", "libro-abierto");
      ver.setAttribute("aria-haspopup", "dialog");
      ver.addEventListener("click", () => abrirFicha(material || { material_id: fuente.material_id, titulo: fuente.documento }));
      accionesFuente.append(ver);
    }
    pie.append(accionesFuente);
    item.append(cabeza, cita, pie);
    return item;
  }

  function referenciaConFormato(referencia, materiales) {
    // Pone en cursiva el título del material dentro de la referencia APA, sin innerHTML.
    const li = crear("li");
    const tituloMaterial = materiales
      .map((m) => String(m.titulo || "").trim())
      .filter((t) => t && referencia.includes(t))
      .sort((a, b) => b.length - a.length)[0];
    if (!tituloMaterial) {
      li.textContent = referencia;
      return li;
    }
    const inicio = referencia.indexOf(tituloMaterial);
    li.append(
      document.createTextNode(referencia.slice(0, inicio)),
      crear("em", "", tituloMaterial),
      document.createTextNode(referencia.slice(inicio + tituloMaterial.length)),
    );
    return li;
  }

  function seccionBibliografia(referencias, materiales) {
    const nodo = seccion("inv-bibliografia", "resumen", "Referencias en APA", "inv-titulo-bibliografia", referencias.length);
    nodo.append(crear("p", "texto-sec", "Revisa los datos con la ficha antes de entregarlas en tu trabajo."));
    const listaRefs = crear("ol", "inv-referencias");
    referencias.forEach((referencia) => listaRefs.append(referenciaConFormato(referencia, materiales)));
    const pie = crear("div", "inv-acciones");
    const copiar = boton("Copiar referencias", "btn btn--acento", "check");
    const anuncio = crear("span", "inv-anuncio");
    anuncio.setAttribute("role", "status");
    anuncio.setAttribute("aria-live", "polite");
    copiar.addEventListener("click", async () => {
      try {
        if (!navigator.clipboard?.writeText) throw new Error("Portapapeles no disponible");
        await navigator.clipboard.writeText(referencias.join("\n"));
        anuncio.textContent = "Referencias copiadas.";
        window.setTimeout(() => { anuncio.textContent = ""; }, 2500);
      } catch {
        const seleccion = window.getSelection();
        const rango = document.createRange();
        rango.selectNodeContents(listaRefs);
        seleccion?.removeAllRanges();
        seleccion?.addRange(rango);
        anuncio.textContent = "Selección lista: pulsa Ctrl+C para copiar.";
      }
    });
    pie.append(copiar, anuncio);
    nodo.append(listaRefs, pie);
    return nodo;
  }

  async function abrirFicha(material) {
    const solicitud = ++fichaGeneracion;
    dialogoTitulo.textContent = material.titulo || "Ficha del material";
    ficha.replaceChildren(crear("p", "texto-sec", "Cargando ficha…"));
    if (!dialogo.open) dialogo.showModal();
    try {
      const datos = await obtenerMaterial(material.material_id);
      if (solicitud !== fichaGeneracion || !dialogo.open) return;
      dialogoTitulo.textContent = datos.titulo || material.titulo || "Ficha del material";
      ficha.replaceChildren(crear("p", "texto-sec", [datos.autor, datos.anio, tipos[datos.tipo] || datos.tipo].filter(Boolean).join(" · ")));
      ficha.append(crear("p", "", datos.programa || "Programa no indicado"));
      if (datos.tema) ficha.append(crear("p", "", `Tema: ${datos.tema}`));
      ficha.append(crear("p", "", `Ubicación: ${lista(datos.estantes).join(" · ") || "Por confirmar"}`));
      ficha.append(crear("p", "", `Ejemplares: ${datos.total ?? "—"} · Disponibles: ${datos.disponibles ?? "—"} · Reservados: ${datos.reservados ?? "—"} · Prestados: ${datos.prestados ?? "—"}`));
      if (datos.editorial) ficha.append(crear("p", "", `Editorial: ${datos.editorial}`));
      if (datos.isbn) ficha.append(crear("p", "", `ISBN: ${datos.isbn}`));
      ficha.append(crear("h3", "", "Resumen"), crear("p", "catalogo__resumen", datos.resumen || datos.descripcion_corta || "Este material todavía no tiene un resumen disponible."));
      const accionesFicha = crear("div", "catalogo__acciones");
      const disponible = Number(datos.disponibles) > 0;
      const reservar = boton(disponible ? "Reservar" : "Solicitar en espera", "btn btn--primario", "reservar");
      reservar.addEventListener("click", () => pedirAgente(`Quiero reservar «${datos.titulo}»`));
      const preguntar = boton("Preguntar al agente", "btn btn--fantasma", "chat");
      preguntar.addEventListener("click", () => pedirAgente(`¿De qué trata «${datos.titulo}»?`));
      const mapa = boton("Ver en el mapa", "btn btn--fantasma");
      mapa.addEventListener("click", () => {
        dialogo.close();
        window.dispatchEvent(new CustomEvent("ver-en-mapa", { detail: { material_id: material.material_id } }));
      });
      accionesFicha.append(reservar, preguntar, mapa);
      ficha.append(accionesFicha);
    } catch {
      if (solicitud !== fichaGeneracion || !dialogo.open) return;
      ficha.replaceChildren(crear("p", "aviso aviso--error", "No se pudo cargar la ficha. Cierra e inténtalo de nuevo."));
    }
  }

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    buscar();
  });
  tema.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey && !evento.isComposing) {
      evento.preventDefault();
      formulario.requestSubmit();
    }
  });
  tema.addEventListener("input", () => {
    if (tema.getAttribute("aria-invalid") === "true" && tema.value.trim()) validar();
  });
  limpiar.addEventListener("click", () => {
    generacion++;
    tema.value = "";
    programa.value = "";
    errorTema.textContent = "";
    tema.removeAttribute("aria-invalid");
    investigarBoton.disabled = false;
    investigarBoton.lastElementChild.textContent = "Investigar en el acervo";
    formulario.removeAttribute("aria-busy");
    resultados.removeAttribute("aria-busy");
    estado.textContent = "";
    mostrarInicio();
    tema.focus();
  });
  window.addEventListener("hashchange", () => {
    if (location.hash !== "#investigacion" && dialogo.open) dialogo.close();
  });

  return {
    refrescar: cargarProgramas,
    buscar,
  };
}

function movimientoReducido() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
