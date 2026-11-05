function escapar(texto) {
  return String(texto ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function enLinea(texto) {
  return escapar(texto)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

export function renderMarkdown(texto) {
  const lineas = String(texto ?? "").replace(/\r\n?/g, "\n").split("\n");
  const bloques = [];
  let parrafo = [];
  let lista = null;

  const cerrarParrafo = () => {
    if (parrafo.length) {
      bloques.push(`<p>${parrafo.map(enLinea).join("<br>")}</p>`);
      parrafo = [];
    }
  };
  const cerrarLista = () => {
    if (lista) {
      bloques.push(`</${lista}>`);
      lista = null;
    }
  };

  for (const linea of lineas) {
    const coincidencia = linea.match(/^\s*(?:-\s+|(\d+)\.\s+)(.*)$/);
    if (coincidencia) {
      cerrarParrafo();
      const tipo = coincidencia[1] ? "ol" : "ul";
      if (lista !== tipo) {
        cerrarLista();
        lista = tipo;
        bloques.push(`<${lista}>`);
      }
      bloques.push(`<li>${enLinea(coincidencia[2])}</li>`);
    } else if (!linea.trim()) {
      cerrarParrafo();
      cerrarLista();
    } else {
      cerrarLista();
      parrafo.push(linea);
    }
  }
  cerrarParrafo();
  cerrarLista();
  return bloques.join("");
}
