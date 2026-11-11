import { obtenerCatalogo, obtenerMaterial } from "../api.js";

const tipos = { libro: "Libro", tesis: "Tesis", articulo: "Artículo", recurso_digital: "Recurso digital" };
const crear = (tag, clase, texto) => {
  const nodo = document.createElement(tag);
  nodo.className = clase || "";
  if (texto !== undefined) nodo.textContent = texto;
  return nodo;
};

export function montarCatalogo(contenedor) {
  let offset = 0;
  let generacion = 0;
  let fichaGeneracion = 0;
  const limite = 12;
  contenedor.innerHTML = `
    <header class="catalogo__cabecera"><div><p class="texto-sec">Explora la biblioteca</p><h1 id="titulo-catalogo" tabindex="-1">Catálogo</h1><p>Todos los libros y tesis, en un solo lugar.</p></div><button type="button" class="btn btn--fantasma" data-actualizar>Actualizar</button></header>
    <div class="catalogo__estadisticas" aria-label="Totales de la biblioteca"></div>
    <form class="catalogo__filtros" role="search" aria-label="Buscar en el catálogo">
      <label class="campo catalogo__busqueda">Título, autor o tema<input name="q" type="search" maxlength="500" placeholder="Ej.: Plan de negocios" autocomplete="off"></label>
      <label class="campo">Tipo<select name="tipo"><option value="">Todos los materiales</option></select></label>
      <label class="campo">Programa<select name="programa"><option value="">Todos los programas</option></select></label>
      <label class="catalogo__disponibles"><input name="disponible" type="checkbox"> Solo con ejemplares disponibles</label>
      <div class="catalogo__acciones"><button class="btn btn--primario" type="submit">Buscar</button><button class="btn btn--fantasma" type="reset">Limpiar filtros</button></div>
    </form>
    <p class="catalogo__estado" role="status" aria-live="polite"></p>
    <div class="catalogo__rejilla"></div>
    <nav class="catalogo__paginas" aria-label="Páginas del catálogo"><button class="btn btn--fantasma" type="button" data-anterior>← Anterior</button><span data-pagina></span><button class="btn btn--fantasma" type="button" data-siguiente>Siguiente →</button></nav>
    <dialog class="catalogo__dialogo" aria-labelledby="titulo-ficha-catalogo"><header><h2 id="titulo-ficha-catalogo">Ficha del material</h2><button class="btn btn--fantasma" type="button" data-cerrar>Cerrar</button></header><div data-ficha></div></dialog>`;
  const form = contenedor.querySelector("form");
  const estado = contenedor.querySelector(".catalogo__estado");
  const rejilla = contenedor.querySelector(".catalogo__rejilla");
  const anterior = contenedor.querySelector("[data-anterior]");
  const siguiente = contenedor.querySelector("[data-siguiente]");
  const dialogo = contenedor.querySelector("dialog");
  const ficha = contenedor.querySelector("[data-ficha]");
  const solicitar = (texto) => {
    if (dialogo.open) dialogo.close();
    window.dispatchEvent(new CustomEvent("preguntar-agente", { detail: { texto } }));
  };

  function completarSelect(nombre, valores, etiquetas = {}) {
    const select = form.elements[nombre];
    const anterior = select.value;
    select.querySelectorAll("option:not(:first-child)").forEach((o) => o.remove());
    valores.forEach((valor) => {
      const option = crear("option", "", etiquetas[valor] || valor);
      option.value = valor;
      select.append(option);
    });
    select.value = anterior;
  }

  function botonReservar(material) {
    const boton = crear("button", "btn btn--primario", material.disponibles > 0 ? "Reservar" : "Solicitar en espera");
    boton.type = "button";
    boton.addEventListener("click", () => solicitar(`Quiero reservar «${material.titulo}»`));
    return boton;
  }

  async function abrirFicha(material) {
    const solicitud = ++fichaGeneracion;
    ficha.replaceChildren(crear("p", "texto-sec", "Cargando ficha…"));
    contenedor.querySelector("#titulo-ficha-catalogo").textContent = material.titulo;
    if (!dialogo.open) dialogo.showModal();
    try {
      const datos = await obtenerMaterial(material.material_id);
      if (solicitud !== fichaGeneracion || !dialogo.open) return;
      datos.material_id = datos.material_id ?? material.material_id;
      ficha.replaceChildren(crear("p", "texto-sec", [datos.autor, datos.anio, tipos[datos.tipo]].filter(Boolean).join(" · ")));
      ficha.append(crear("p", "", datos.programa || "Programa no indicado"));
      if (datos.tema) ficha.append(crear("p", "", `Tema: ${datos.tema}`));
      ficha.append(crear("p", "", `Ubicación: ${datos.estantes?.join(" · ") || "Por confirmar"}`));
      ficha.append(crear("p", "", `Ejemplares: ${datos.total} · Disponibles: ${datos.disponibles} · Reservados: ${datos.reservados} · Prestados: ${datos.prestados}`));
      if (datos.editorial) ficha.append(crear("p", "", `Editorial: ${datos.editorial}`));
      if (datos.isbn) ficha.append(crear("p", "", `ISBN: ${datos.isbn}`));
      ficha.append(crear("h3", "", "Resumen"), crear("p", "catalogo__resumen", datos.resumen || datos.descripcion_corta || "Este material todavía no tiene un resumen disponible."));
      const acciones = crear("div", "catalogo__acciones");
      acciones.append(botonReservar(datos));
      const preguntar = crear("button", "btn btn--fantasma", "Preguntar al agente");
      preguntar.type = "button";
      preguntar.addEventListener("click", () => solicitar(`¿De qué trata «${datos.titulo}»?`));
      acciones.append(preguntar);
      const mapa = crear("button", "btn btn--fantasma", "Ver en el mapa");
      mapa.type = "button";
      mapa.addEventListener("click", () => {
        dialogo.close();
        window.dispatchEvent(new CustomEvent("ver-en-mapa", { detail: { material_id: material.material_id } }));
      });
      acciones.append(mapa);
      ficha.append(acciones);
    } catch {
      if (solicitud !== fichaGeneracion || !dialogo.open) return;
      ficha.replaceChildren(crear("p", "aviso aviso--error", "No se pudo cargar la ficha. Cierra e inténtalo de nuevo."));
    }
  }

  function tarjeta(material) {
    const tarjeta = crear("article", "tarjeta catalogo__tarjeta");
    tarjeta.dataset.materialId = material.material_id;
    tarjeta.append(crear("p", "catalogo__tipo", tipos[material.tipo] || material.tipo));
    const titulo = crear("h2", "", material.titulo);
    titulo.id = `catalogo-material-${material.material_id}`;
    tarjeta.setAttribute("aria-labelledby", titulo.id);
    tarjeta.append(titulo);
    tarjeta.append(crear("p", "texto-sec", [material.autor, material.anio].filter(Boolean).join(" · ")));
    tarjeta.append(crear("p", "catalogo__programa", material.programa || "Programa no indicado"));
    tarjeta.append(crear("p", `estado ${material.disponibles > 0 ? "estado--disponible" : "estado--reservado"}`, `${material.disponibles} de ${material.total} ejemplares disponibles`));
    tarjeta.append(crear("p", "texto-sec", `Reservados: ${material.reservados} · Prestados: ${material.prestados}`));
    tarjeta.append(crear("p", "catalogo__estante", material.estantes?.join(" · ") || "Ubicación por confirmar"));
    const acciones = crear("div", "catalogo__acciones");
    const ver = crear("button", "btn btn--fantasma", "Ver ficha");
    ver.type = "button";
    ver.setAttribute("aria-haspopup", "dialog");
    ver.addEventListener("click", () => abrirFicha(material));
    acciones.append(ver, botonReservar(material));
    tarjeta.append(acciones);
    return tarjeta;
  }

  async function refrescar() {
    const solicitud = ++generacion;
    const parametros = { limite, offset, q: form.elements.q.value.trim() };
    if (form.elements.tipo.value) parametros.tipo = form.elements.tipo.value;
    if (form.elements.programa.value) parametros.programa = form.elements.programa.value;
    if (form.elements.disponible.checked) parametros.disponible = "true";
    estado.textContent = "Consultando catálogo…";
    rejilla.setAttribute("aria-busy", "true");
    anterior.disabled = siguiente.disabled = true;
    try {
      const datos = await obtenerCatalogo(parametros);
      if (solicitud !== generacion) return;
      if (offset && offset >= datos.total) { offset = 0; return refrescar(); }
      completarSelect("tipo", datos.tipos || [], tipos);
      completarSelect("programa", datos.programas || []);
      const estadisticas = contenedor.querySelector(".catalogo__estadisticas");
      estadisticas.replaceChildren();
      const s = datos.estadisticas || {};
      for (const [valor, etiqueta] of [[s.materiales, "Títulos en catálogo"], [s.libros, "Libros"], [s.tesis, "Tesis"], [s.ejemplares, "Ejemplares en total"]]) {
        const tarjeta = crear("div", "catalogo__numero");
        tarjeta.append(crear("strong", "", String(valor ?? "—")), crear("span", "", etiqueta));
        estadisticas.append(tarjeta);
      }
      rejilla.replaceChildren(...datos.resultados.map(tarjeta));
      estado.textContent = datos.total
        ? `Mostrando ${offset + 1}–${Math.min(offset + limite, datos.total)} de ${datos.total} materiales${parametros.q || parametros.tipo || parametros.programa || parametros.disponible ? " que coinciden con tus filtros" : ""}.`
        : "No hay materiales que coincidan con tu búsqueda. Prueba otro término o limpia los filtros.";
      anterior.disabled = offset === 0;
      siguiente.disabled = offset + limite >= datos.total;
      contenedor.querySelector("[data-pagina]").textContent = datos.total ? `Página ${Math.floor(offset / limite) + 1} de ${Math.ceil(datos.total / limite)}` : "Sin resultados";
    } catch {
      if (solicitud !== generacion) return;
      estado.textContent = "No pudimos consultar el catálogo. Pulsa Actualizar para reintentar.";
      rejilla.replaceChildren();
      contenedor.querySelector("[data-pagina]").textContent = "";
    } finally {
      if (solicitud === generacion) rejilla.removeAttribute("aria-busy");
    }
  }
  form.addEventListener("submit", (e) => { e.preventDefault(); offset = 0; void refrescar(); });
  form.addEventListener("change", (e) => { if (e.target.name !== "q") { offset = 0; void refrescar(); } });
  form.addEventListener("reset", () => { offset = 0; setTimeout(refrescar, 0); });
  anterior.addEventListener("click", () => { offset = Math.max(0, offset - limite); void refrescar(); });
  siguiente.addEventListener("click", () => { offset += limite; void refrescar(); });
  contenedor.querySelector("[data-actualizar]").addEventListener("click", () => void refrescar());
  contenedor.querySelector("[data-cerrar]").addEventListener("click", () => dialogo.close());
  dialogo.addEventListener("close", () => { fichaGeneracion++; });
  window.addEventListener("hashchange", () => { if (location.hash !== "#catalogo" && dialogo.open) dialogo.close(); });
  return { refrescar };
}
