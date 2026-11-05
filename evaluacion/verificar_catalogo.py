"""Aceptación del catálogo público en Edge y de sus filtros. Usa CATALOGO_URL para elegir el servidor (por defecto localhost:8000)."""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

CARPETA = Path(__file__).resolve().parent
sys.path.insert(0, str(CARPETA.parent))
BASE_URL = os.environ.get("CATALOGO_URL", "http://127.0.0.1:8000").rstrip("/")


def verificar_backend():
    """Consulta la aplicación actual sin lifespan ni escrituras en los datos."""
    from fastapi.testclient import TestClient
    from app.main import app, conexion

    cliente = TestClient(app)
    respuesta = cliente.get("/api/catalogo", params={"limite": 200})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT count(*), count(*) FILTER (WHERE tipo='libro'), count(*) FILTER (WHERE tipo='tesis') FROM public.material")
        materiales, libros, tesis = cursor.fetchone()
        cursor.execute("SELECT count(*) FROM public.ejemplares")
        ejemplares = cursor.fetchone()[0]
    assert datos["estadisticas"]["materiales"] == materiales == datos["total"]
    assert datos["estadisticas"]["libros"] == libros
    assert datos["estadisticas"]["tesis"] == tesis
    assert datos["estadisticas"]["ejemplares"] == ejemplares
    filas = []
    for offset in range(0, materiales, 12):
        pagina = cliente.get("/api/catalogo", params={"limite": 12, "offset": offset}).json()
        filas.extend(pagina["resultados"])
    assert len(filas) == len({fila["material_id"] for fila in filas}) == materiales
    assert sum(fila["total"] for fila in filas) == ejemplares
    for tipo in datos["tipos"]:
        filtrados = cliente.get("/api/catalogo", params={"tipo": tipo, "limite": 200}).json()
        esperados = [fila for fila in filas if fila["tipo"] == tipo]
        assert filtrados["total"] == len(esperados)
        assert all(fila["tipo"] == tipo for fila in filtrados["resultados"])
        assert filtrados["estadisticas"] == datos["estadisticas"]
    for programa in datos["programas"]:
        filtrados = cliente.get("/api/catalogo", params={"programa": programa, "disponible": True, "limite": 200}).json()
        assert filtrados["total"] == len([fila for fila in filas if fila["programa"] == programa and fila["disponibles"] > 0])
    for fila in filas:
        ficha = cliente.get(f"/api/material/{fila['material_id']}")
        assert ficha.status_code == 200, ficha.text
        ficha = ficha.json()
        assert all(ficha[campo] == fila[campo] for campo in ("total", "disponibles", "reservados", "prestados"))
        assert len(ficha["ejemplares"]) == fila["total"]
        assert "resumen" in ficha
    assert cliente.get("/api/material/-1").status_code == 404
    for parametros in ({"limite": 0}, {"limite": 201}, {"offset": -1}, {"q": "a" * 501}):
        assert cliente.get("/api/catalogo", params=parametros).status_code == 422
    print(f"TestClient: {materiales} títulos ({libros} libros, {tesis} tesis), {ejemplares} ejemplares; filtros, páginas, fichas y validación: PASA")


def main():
    verificar_backend()
    errores = []
    pruebas = []
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="msedge", headless=True)
        pagina = navegador.new_page(viewport={"width": 1440, "height": 1000})
        pagina.set_default_timeout(30000)
        pagina.on("pageerror", lambda error: errores.append(str(error)))
        pagina.on("console", lambda mensaje: errores.append(mensaje.text) if mensaje.type == "error" else None)
        pagina.goto(f"{BASE_URL}/#catalogo")
        pagina.locator("#entrar-invitado").click()

        def esperar():
            pagina.wait_for_function('document.querySelector(".catalogo__rejilla") && !document.querySelector(".catalogo__rejilla").hasAttribute("aria-busy") && !document.querySelector(".catalogo__estado").textContent.includes("Consultando")')

        def cambiar(accion):
            with pagina.expect_response(lambda r: "/api/catalogo?" in r.url and r.request.method == "GET"):
                accion()
            esperar()

        esperar()
        datos = pagina.request.get(f"{BASE_URL}/api/catalogo?limite=200").json()
        assert datos["estadisticas"]["materiales"] == datos["total"]
        assert datos["estadisticas"]["ejemplares"] == sum(r["total"] for r in datos["resultados"])
        assert pagina.locator(".catalogo__numero strong").first.inner_text() == str(datos["total"])
        ids = []
        while True:
            ids.extend(pagina.locator(".catalogo__tarjeta").evaluate_all("(nodos) => nodos.map(n => Number(n.dataset.materialId))"))
            if pagina.locator("[data-siguiente]").is_disabled():
                break
            cambiar(lambda: pagina.locator("[data-siguiente]").click())
        assert len(ids) == len(set(ids)) == datos["total"]
        assert set(ids) == {r["material_id"] for r in datos["resultados"]}
        pruebas.append("Todos los materiales accesibles, sin duplicados, y totales correctos")
        assert pagina.locator('.navegacion [data-vista="catalogo"]').get_attribute("aria-current") == "page"
        cambiar(lambda: pagina.locator('[data-actualizar]').click())
        cambiar(lambda: pagina.locator('.catalogo select[name="tipo"]').select_option("libro"))
        assert pagina.locator(".catalogo__tipo").all_text_contents() and set(pagina.locator(".catalogo__tipo").all_text_contents()) == {"Libro"}
        assert f"de {datos['estadisticas']['libros']} materiales" in pagina.locator(".catalogo__estado").inner_text()
        cambiar(lambda: pagina.locator('.catalogo select[name="tipo"]').select_option("tesis"))
        assert set(pagina.locator(".catalogo__tipo").all_text_contents()) == {"Tesis"}
        pruebas.append("Filtros de libros y tesis con sus cantidades")
        cambiar(lambda: pagina.get_by_role("button", name="Limpiar filtros", exact=True).click())
        assert f"de {datos['total']} materiales" in pagina.locator(".catalogo__estado").inner_text()
        programa = datos["programas"][0]
        cambiar(lambda: pagina.locator('.catalogo select[name="programa"]').select_option(programa))
        assert set(pagina.locator(".catalogo__programa").all_text_contents()) == {programa}
        cambiar(lambda: pagina.locator('.catalogo input[name="disponible"]').check())
        assert all(not t.startswith("0 de") for t in pagina.locator(".catalogo__tarjeta .estado").all_text_contents())
        pruebas.append("Filtros combinados de programa y disponibilidad")
        cambiar(lambda: pagina.get_by_role("button", name="Limpiar filtros", exact=True).click())
        titulo = datos["resultados"][0]["titulo"]
        pagina.locator('.catalogo input[name="q"]').fill(titulo)
        cambiar(lambda: pagina.get_by_role("button", name="Buscar", exact=True).click())
        assert titulo in pagina.locator(".catalogo__tarjeta h2").all_text_contents()
        pagina.locator(".catalogo__tarjeta").filter(has_text=titulo).get_by_role("button", name="Ver ficha", exact=True).first.click()
        pagina.locator("dialog[open] [data-ficha] h3").wait_for()
        assert pagina.locator("#titulo-ficha-catalogo").inner_text() == titulo
        assert "Ejemplares:" in pagina.locator("dialog[open]").inner_text()
        assert "Ubicación:" in pagina.locator("dialog[open]").inner_text()
        pagina.locator("dialog[open]").get_by_role("button", name="Cerrar", exact=True).click()
        pruebas.append("Búsqueda por título y ficha completa")
        pagina.locator(".catalogo__tarjeta").first.get_by_role("button", name="Ver ficha", exact=True).click()
        pagina.locator("dialog[open]").get_by_role("button", name="Ver en el mapa", exact=True).click()
        pagina.wait_for_function('location.hash === "#panel/mapa" && document.querySelector("[data-panel-contenido=mapa] canvas")')
        pagina.locator('.navegacion [data-vista="catalogo"]').click()
        esperar()
        pruebas.append("Ficha enlazada con el mapa y vuelta al catálogo")
        pagina.locator('.catalogo input[name="q"]').fill("zzzz000sinmateriales")
        cambiar(lambda: pagina.get_by_role("button", name="Buscar", exact=True).click())
        assert pagina.locator(".catalogo__tarjeta").count() == 0
        assert "No hay materiales" in pagina.locator(".catalogo__estado").inner_text()
        cambiar(lambda: pagina.get_by_role("button", name="Limpiar filtros", exact=True).click())
        assert pagina.locator(".catalogo__tarjeta").count() == min(12, datos["total"])
        pruebas.append("Búsqueda sin resultados y recuperación al limpiar filtros")
        pagina.route("**/api/catalogo?*", lambda ruta: ruta.fulfill(status=200, content_type="application/json", body="null"), times=1)
        cambiar(lambda: pagina.locator("[data-actualizar]").click())
        assert "Pulsa Actualizar" in pagina.locator(".catalogo__estado").inner_text()
        assert pagina.locator(".catalogo__tarjeta").count() == 0
        cambiar(lambda: pagina.locator("[data-actualizar]").click())
        assert pagina.locator(".catalogo__tarjeta").count() > 0
        pruebas.append("Error de respuesta y recuperación con Actualizar")
        pagina.screenshot(path=str(CARPETA / "catalogo_escritorio.png"), full_page=True)
        pagina.set_viewport_size({"width": 390, "height": 844})
        for tema in ("claro", "oscuro"):
            pagina.evaluate("(tema) => document.documentElement.dataset.tema = tema", tema)
            pagina.evaluate('window.scrollTo({top: 0, behavior: "instant"})')
            assert pagina.locator(".catalogo__tarjeta h2").first.evaluate('(nodo) => getComputedStyle(nodo).color === getComputedStyle(document.querySelector(".catalogo__numero strong")).color')
            assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
            pagina.screenshot(path=str(CARPETA / f"catalogo_movil_{tema}.png"))
            pagina.locator(".catalogo__tarjeta").first.get_by_role("button", name="Ver ficha", exact=True).click()
            pagina.locator("dialog[open] [data-ficha] h3").wait_for()
            assert pagina.evaluate('document.querySelector("dialog[open]").scrollWidth <= document.querySelector("dialog[open]").clientWidth')
            pagina.keyboard.press("Escape")
            assert pagina.locator("dialog[open]").count() == 0
        assert pagina.locator('.navegacion-movil [data-vista="catalogo"]').is_visible()
        pruebas.append("Catálogo móvil a 390 px, claro y oscuro, sin desborde")
        pagina.locator(".catalogo__tarjeta .btn--primario").first.click()
        pagina.wait_for_function('location.hash === "#chat" && !document.querySelector(".pensando")')
        assert "iniciar sesión" in pagina.locator(".chat-mensajes").inner_text()
        pruebas.append("Reservar desde el catálogo inicia el flujo del chat y exige sesión")
        assert not errores, errores
        navegador.close()
    (CARPETA / "catalogo_resultados.json").write_text(json.dumps({"url": BASE_URL, "estadisticas": datos["estadisticas"], "pruebas": pruebas, "errores": errores}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(pruebas)}/{len(pruebas)} comprobaciones de catálogo: PASA")


if __name__ == "__main__":
    main()
