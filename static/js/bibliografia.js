export function renderBibliografia(datos) {
  const seccion = document.createElement("section");
  seccion.className = "bibliografia";
  const titulo = document.createElement("h3");
  titulo.textContent = `Bibliografía (${datos.norma || "APA"})`;

  const contenido = document.createElement("div");
  contenido.className = "bibliografia-contenido";
  const referencias = Array.isArray(datos.referencias) ? datos.referencias : [];
  if ((datos.norma || "APA") === "IEEE") {
    referencias.forEach((referencia) => {
      const entrada = document.createElement("p");
      entrada.className = "bibliografia-entrada";
      entrada.innerHTML = referencia.html || "";
      contenido.append(entrada);
    });
  } else {
    const lista = document.createElement("ol");
    referencias.forEach((referencia) => {
      const entrada = document.createElement("li");
      entrada.innerHTML = referencia.html || "";
      lista.append(entrada);
    });
    contenido.append(lista);
  }

  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = "bibliografia-copiar";
  boton.textContent = "Copiar";
  const anuncio = document.createElement("span");
  anuncio.className = "bibliografia-anuncio";
  anuncio.setAttribute("aria-live", "polite");
  anuncio.setAttribute("role", "status");

  const textoPlano = referencias
    .map((referencia) => referencia.texto || "")
    .join("\n");
  boton.addEventListener("click", async () => {
    const textoHtml = contenido.innerHTML;
    try {
      if (navigator.clipboard?.write && typeof ClipboardItem !== "undefined") {
        try {
          await navigator.clipboard.write([
            new ClipboardItem({
              "text/html": new Blob([textoHtml], { type: "text/html" }),
              "text/plain": new Blob([textoPlano], { type: "text/plain" }),
            }),
          ]);
        } catch (error) {
          if (!navigator.clipboard.writeText) throw error;
          await navigator.clipboard.writeText(textoPlano);
        }
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(textoPlano);
      } else {
        throw new Error("El portapapeles no está disponible.");
      }
      anuncio.textContent = "¡Copiado!";
      window.setTimeout(() => {
        anuncio.textContent = "";
      }, 2000);
    } catch {
      const seleccion = window.getSelection();
      const rango = document.createRange();
      rango.selectNodeContents(contenido);
      seleccion?.removeAllRanges();
      seleccion?.addRange(rango);
      anuncio.textContent = "Pulse Ctrl+C para copiar.";
    }
  });

  seccion.append(titulo, contenido, boton, anuncio);
  return seccion;
}
