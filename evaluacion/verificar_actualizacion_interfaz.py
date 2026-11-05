"""Rechaza módulos sin versión y abre el catálogo como invitado y con sesión."""
import json
import time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"


def main():
    for _ in range(30):
        try:
            with urlopen(BASE + "/api/salud", timeout=2):
                break
        except OSError:
            time.sleep(1)
    errores = []
    antiguas = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for identificado in (False, True):
            contexto = browser.new_context(viewport={"width": 1440, "height": 1000})
            def bloquear_antiguos(ruta):
                if "?v=" not in ruta.request.url:
                    antiguas.append(ruta.request.url)
                    ruta.fulfill(content_type="text/javascript", body="throw new Error('Módulo antiguo reutilizado');")
                else:
                    ruta.continue_()
            contexto.route("**/static/js/**", bloquear_antiguos)
            pagina = contexto.new_page()
            pagina.on("pageerror", lambda e: errores.append(str(e)))
            respuesta = pagina.goto(BASE + "/?actualizar=interfaz")
            assert respuesta.headers["cache-control"] == "no-store"
            if identificado:
                pagina.locator("#codigo-sesion").fill("101")
                pagina.locator("#pin-sesion").fill("1234")
                pagina.locator("#entrar-sesion").click()
                pagina.locator("#pantalla-sesion").wait_for(state="hidden")
            else:
                pagina.locator("#entrar-invitado").click()
            pagina.locator('.navegacion [data-vista="catalogo"]').click()
            pagina.locator(".catalogo__tarjeta").first.wait_for()
            assert pagina.locator(".catalogo__tarjeta").count() == 12
            assert pagina.evaluate("location.hash") == "#catalogo"
            pagina.screenshot(path=str(Path(__file__).parent / f"catalogo_actualizado_{'sesion' if identificado else 'invitado'}.png"), full_page=False)
            if identificado:
                pagina.request.post(BASE + "/api/logout")
            contexto.close()
        contexto = browser.new_context(viewport={"width": 1440, "height": 1000})
        intentos = []
        def conexion_temporal(ruta):
            intentos.append(ruta.request.url)
            if len(intentos) == 1:
                ruta.fulfill(status=503, content_type="application/json", body='{"mensaje":"Reinicio temporal"}')
            else:
                ruta.continue_()
        contexto.route("**/api/salud", conexion_temporal)
        pagina = contexto.new_page()
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        pagina.goto(BASE + "/?actualizar=conexion")
        pagina.locator("#entrar-invitado").click()
        pagina.wait_for_function('document.querySelector(".servicio-aviso").textContent.includes("Reintentando")')
        assert "Ollama no responde" not in pagina.locator(".servicio-aviso").inner_text()
        assert pagina.locator(".servicio--error").count() == 0
        pagina.wait_for_function('document.querySelector(".servicio-aviso").hidden && document.querySelectorAll(".servicio--ok").length >= 4', timeout=20000)
        contexto.close()
        browser.close()
    assert not antiguas, antiguas
    assert not errores, errores
    print(json.dumps({"catalogo_invitado": "PASA", "catalogo_con_sesion": "PASA", "recuperacion_conexion": "PASA", "modulos_antiguos": antiguas, "errores": errores}, ensure_ascii=False))


if __name__ == "__main__":
    main()
