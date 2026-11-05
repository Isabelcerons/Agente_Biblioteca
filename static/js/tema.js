import { luna, sol } from "./iconos.js";

const raiz = () => document.documentElement;

function actualizarInterruptor() {
  const boton = document.querySelector("#interruptor-tema");
  if (!boton) return;
  const oscuro = raiz().dataset.tema === "oscuro";
  boton.setAttribute("aria-pressed", String(oscuro));
  const accion = oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
  boton.setAttribute(
    "aria-label",
    accion,
  );
  boton.innerHTML = `${oscuro ? sol : luna}<span>${accion}</span>`;
}

function guardarTema(tema) {
  raiz().dataset.tema = tema;
  try {
    localStorage.setItem("tema", tema);
  } catch {
    // El tema visual sigue funcionando cuando el almacenamiento está bloqueado.
  }
  actualizarInterruptor();
  return tema;
}

export function alternarTema() {
  return guardarTema(raiz().dataset.tema === "oscuro" ? "claro" : "oscuro");
}

export function iniciarTema() {
  let preferencia;
  try {
    preferencia = localStorage.getItem("tema");
  } catch {
    preferencia = null;
  }
  if (preferencia !== "claro" && preferencia !== "oscuro") {
    preferencia = window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "oscuro"
      : "claro";
  }
  raiz().dataset.tema = preferencia;
  const boton = document.querySelector("#interruptor-tema");
  if (boton) boton.onclick = alternarTema;
  actualizarInterruptor();
  const observador = new MutationObserver(actualizarInterruptor);
  observador.observe(raiz(), { attributes: true, attributeFilter: ["data-tema"] });
}
