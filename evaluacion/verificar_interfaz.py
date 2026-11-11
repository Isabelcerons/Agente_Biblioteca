"""Aceptación en Edge real. Requiere playwright y la API en localhost:8000."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from playwright.sync_api import sync_playwright
from base_datos import ejecutar
from evaluacion.evaluar import (
    capturar_base, restaurar_base, capturar_estado_autenticacion,
    restaurar_estado_autenticacion, capturar_ids_sesiones, cerrar_sesiones_nuevas,
)


def main():
    ejecutar("UPDATE public.reservas SET estado = 'activa', expira_en = now() + interval '48 hours' WHERE id = 1")
    base = capturar_base()
    estado = capturar_estado_autenticacion()
    sesiones = capturar_ids_sesiones()
    errores = []
    errores_consola = []
    comprobaciones = []
    carpeta = RAIZ / "evaluacion"
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(channel="msedge", headless=True)
            contexto = navegador.new_context(viewport={"width": 1440, "height": 1000})
            pagina = contexto.new_page()
            pagina.on("pageerror", lambda error: errores.append(str(error)))
            pagina.on("console", lambda mensaje: errores_consola.append(mensaje.text) if mensaje.type == "error" else None)
            pagina.goto("http://127.0.0.1:8000")
            pagina.locator("#entrar-invitado").click()
            assert pagina.locator(".navegacion").inner_text().splitlines() == ["Chat", "Catálogo", "Investigar", "Mi cuenta", "Mis reservas"]
            comprobaciones.append("Menú con cinco entradas exactas")
            boton_nueva = pagina.locator("#nueva-conversacion")
            assert boton_nueva.is_visible()
            assert boton_nueva.evaluate("(nodo) => nodo.scrollHeight <= nodo.clientHeight + 4")
            comprobaciones.append("Botón Nueva conversación visible y sin partir en escritorio")
            cantidad_errores = len(errores)
            cantidad_errores_consola = len(errores_consola)
            pagina.locator('.navegacion [data-vista="investigacion"]').click()
            pagina.locator("#vista-investigacion").wait_for(state="visible")
            assert pagina.locator("#titulo-investigacion").inner_text() == "Asistente de investigación"
            pagina.set_viewport_size({"width": 390, "height": 844})
            assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert errores[cantidad_errores:] == [], errores[cantidad_errores:]
            assert errores_consola[cantidad_errores_consola:] == [], errores_consola[cantidad_errores_consola:]
            comprobaciones.append("Navegación a Investigación, título visible y móvil sin errores ni desborde")
            pagina.set_viewport_size({"width": 1440, "height": 1000})
            for nombre in ("mapa", "sql", "bitacora"):
                pagina.evaluate("(ruta) => location.hash = ruta", f"panel/{nombre}")
                panel = pagina.locator(f'[data-panel-contenido="{nombre}"]')
                panel.wait_for(state="visible")
                pagina.wait_for_function("(selector) => document.querySelector(selector).innerText.trim().length > 20", arg=f'[data-panel-contenido="{nombre}"]')
            pagina.screenshot(path=str(carpeta / "panel_tecnico.png"), full_page=True)
            comprobaciones.append("Tres pestañas del panel técnico")
            pagina.evaluate('location.hash = "chat"')
            pagina.locator("#entrada-chat").wait_for(state="visible")
            pagina.set_viewport_size({"width": 390, "height": 844})
            for tema in ("claro", "oscuro"):
                pagina.evaluate("(t) => document.documentElement.dataset.tema = t", tema)
                pagina.wait_for_timeout(300)
                assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
                pagina.screenshot(path=str(carpeta / f"interfaz_movil_{tema}.png"), full_page=True)
            comprobaciones.append("390 px sin desborde en ambos temas")
            pagina.set_viewport_size({"width": 1440, "height": 1000})

            def enviar(texto):
                pagina.locator("#entrada-chat").fill(texto)
                pagina.locator("#entrada-chat").press("Enter")
                pagina.wait_for_function('!document.querySelector(".pensando")')

            enviar("mi código es ciento uno")
            pagina.locator('input#entrada-chat[type="password"]').wait_for()
            enviar("1234")
            pagina.wait_for_function('document.querySelector(".chat-encabezado .usuario-chip").textContent.includes("Carlos")')
            assert "1234" not in pagina.locator(".chat-mensajes").inner_text()
            assert "PIN enviado" in pagina.locator(".chat-mensajes").inner_text()
            assert pagina.locator("#subir-tesis").is_visible()
            pagina.screenshot(path=str(carpeta / "login_chat.png"), full_page=True)
            comprobaciones.append("Login en chat, chip actualizado, subir tesis y PIN oculto")
            contexto.close()

            contexto = navegador.new_context(viewport={"width": 1440, "height": 1000})
            pagina = contexto.new_page()
            pagina.on("pageerror", lambda error: errores.append(str(error)))
            pagina.goto("http://127.0.0.1:8000")
            pagina.locator("#codigo-sesion").fill("108")
            pagina.locator("#pin-sesion").fill("1234")
            pagina.locator("#entrar-sesion").click()
            pagina.locator("#pantalla-sesion").wait_for(state="hidden")
            pagina.locator('.navegacion [data-vista="mi-cuenta"]').click()
            cancelar = pagina.locator("#cuenta-contenido").get_by_role("button", name="Cancelar", exact=True).first
            cancelar.wait_for(state="visible")
            cancelar.click()
            pagina.locator("dialog[open]").wait_for()
            pagina.screenshot(path=str(carpeta / "cancelacion_reserva.png"), full_page=True)
            with pagina.expect_response(lambda r: "/cancelar" in r.url and r.request.method == "POST") as respuesta:
                pagina.locator("dialog[open]").get_by_role("button", name="Confirmar", exact=True).click()
            assert respuesta.value.status == 200 and respuesta.value.json()["ok"]
            pagina.get_by_text("No tienes reservas activas.", exact=True).wait_for()
            comprobaciones.append("Cancelación confirmada desde Mi cuenta")
            assert not errores, errores
            comprobaciones.append("Sin errores de JavaScript")
            navegador.close()
    finally:
        restaurar_base(base)
        cerrar_sesiones_nuevas(sesiones)
        restaurar_estado_autenticacion(estado)
        (carpeta / "interfaz_resultados.json").write_text(json.dumps({"comprobaciones": comprobaciones, "errores": errores}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(comprobaciones)}/{len(comprobaciones)} comprobaciones de interfaz: PASA")


if __name__ == "__main__":
    main()
