"""Verifica la API de investigación y su interfaz en Edge headless."""
import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
sys.path.insert(0, str(RAIZ))
BASE_URL = os.environ.get("INVESTIGACION_URL", "http://127.0.0.1:8000").rstrip("/")


def comprobar_api(pruebas):
    """Ejecuta solicitudes de solo lectura contra la aplicación en proceso."""
    from fastapi.testclient import TestClient

    from app.db import conexion
    from app.main import app

    cliente = TestClient(app)
    respuesta = cliente.post(
        "/api/investigacion",
        json={"tema": "cultivo de cacao en el Putumayo"},
    )
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["ok"] is True
    materiales = datos["materiales"]
    fuentes = datos["fuentes"]
    assert 1 <= len(materiales) <= 5
    assert len(fuentes) >= 1
    ids = {str(material["material_id"]) for material in materiales}
    citas = re.findall(r"\[material\s+(\d+)\]", datos["respuesta"], flags=re.IGNORECASE)
    assert citas and set(citas) <= ids
    fuentes_por_id = {}
    for fuente in fuentes:
        fuentes_por_id.setdefault(str(fuente["material_id"]), []).append(fuente["texto"])
    extractos = re.findall(
        r": «([^»]*)»(?:…)?\s*\[material\s+(\d+)\]",
        datos["respuesta"],
        flags=re.IGNORECASE,
    )
    assert extractos
    for extracto, material_id in extractos:
        assert any(
            fragmento.startswith(extracto)
            for fragmento in fuentes_por_id.get(material_id, [])
        ), f"El extracto del material {material_id} no es prefijo de su fuente."
    assert datos["bibliografia"]
    assert all(isinstance(referencia, str) and referencia.strip() for referencia in datos["bibliografia"])
    pruebas.append("API: evidencia, citas, extractos y referencias APA")

    respuesta = cliente.post(
        "/api/investigacion",
        json={"tema": "seguridad en redes", "programa": "Ingeniería de Sistemas"},
    )
    assert respuesta.status_code == 200, respuesta.text
    filtrados = respuesta.json()
    assert filtrados["ok"] is True
    ids_filtrados = [material["material_id"] for material in filtrados["materiales"]]
    assert ids_filtrados
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, programa FROM public.material WHERE id = ANY(%s)",
            (ids_filtrados,),
        )
        programas = {material_id: programa for material_id, programa in cursor.fetchall()}
    assert set(programas) == set(ids_filtrados)
    assert all(
        (programa or "").strip().casefold() == "ingeniería de sistemas".casefold()
        for programa in programas.values()
    ), programas
    pruebas.append("API: filtro exacto por Ingeniería de Sistemas")

    respuesta = cliente.post(
        "/api/investigacion",
        json={"tema": "astrofísica cuántica de agujeros negros supermasivos"},
    )
    assert respuesta.status_code == 200, respuesta.text
    sin_evidencia = respuesta.json()
    assert sin_evidencia["ok"] is False
    assert sin_evidencia["materiales"] == []
    assert sin_evidencia["fuentes"] == []
    assert sin_evidencia["bibliografia"] == []
    pruebas.append("API: tema sin evidencia devuelve listas vacías")

    respuesta = cliente.post("/api/investigacion", json={"tema": "   "})
    assert respuesta.status_code == 422, respuesta.text
    pruebas.append("API: tema vacío devuelve 422")


def comprobar_interfaz(pruebas, errores):
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(channel="msedge", headless=True)
        pagina = navegador.new_page(viewport={"width": 1440, "height": 900})
        pagina.set_default_timeout(30000)
        pagina.on("pageerror", lambda error: errores.append(str(error)))
        pagina.on(
            "console",
            lambda mensaje: errores.append(mensaje.text) if mensaje.type == "error" else None,
        )
        pagina.goto(f"{BASE_URL}/#investigacion")
        pagina.locator("#entrar-invitado").click()
        pagina.locator("#vista-investigacion").wait_for(state="visible")
        pagina.locator("#titulo-investigacion").wait_for(state="visible")
        assert pagina.locator("#inv-tema").is_visible()
        assert pagina.locator("#inv-programa").is_visible()
        pruebas.append("Interfaz: acceso invitado, navegación y formulario")

        pagina.locator(".inv-chip").filter(has_text="Cultivo de cacao en el Putumayo").click()
        pagina.locator(".inv-materiales").wait_for(state="visible")
        pagina.locator(".inv-fuentes").wait_for(state="visible")
        pagina.locator(".inv-bibliografia").wait_for(state="visible")
        boton_ficha = pagina.locator(".inv-materiales .inv-tarjeta button[aria-haspopup='dialog']").first
        boton_ficha.click()
        pagina.locator("dialog[open]").wait_for(state="visible")
        pagina.locator("dialog[open] [data-ficha] h3").wait_for(state="visible")
        pagina.locator("dialog[open]").get_by_role("button", name="Cerrar", exact=True).click()
        assert pagina.locator("dialog[open]").count() == 0
        pruebas.append("Interfaz: resultados completos y ficha modal abre/cierra")

        pagina.evaluate("document.documentElement.dataset.tema = 'claro'")
        assert pagina.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert not errores, errores
        pagina.screenshot(path=str(CARPETA / "investigacion_escritorio.png"), full_page=True)
        pruebas.append("Escritorio 1440x900: sin desborde ni errores de JavaScript")

        pagina.set_viewport_size({"width": 390, "height": 844})
        for tema in ("claro", "oscuro"):
            pagina.evaluate("(valor) => document.documentElement.dataset.tema = valor", tema)
            pagina.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            assert pagina.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert not errores, errores
            if tema == "claro":
                pagina.screenshot(
                    path=str(CARPETA / "investigacion_movil_claro.png"),
                    full_page=True,
                )
            else:
                pagina.screenshot(
                    path=str(CARPETA / "investigacion_movil_oscuro.png"),
                    full_page=True,
                )
            pruebas.append(f"Móvil 390x844, tema {tema}: sin desborde ni errores de JavaScript")
        navegador.close()


def main():
    pruebas = []
    errores = []
    comprobar_api(pruebas)
    comprobar_interfaz(pruebas, errores)
    resultados = {
        "url": BASE_URL,
        "comprobaciones": pruebas,
        "errores": errores,
    }
    (CARPETA / "investigacion_resultados.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{len(pruebas)}/{len(pruebas)} comprobaciones de investigación: PASA")


if __name__ == "__main__":
    main()
