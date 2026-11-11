"""Pruebas automáticas y reales del contrato de Salas de Biblioteca."""

from __future__ import annotations

import sys
from typing import Any
from fastapi.testclient import TestClient

from app.main import app
from app.db import conexion


def ejecutar_pruebas() -> None:
    pasadas = 0
    total_pruebas = 10

    with TestClient(app) as client:
        # Inicio de sesión con usuario 102 (Mariana) y PIN 1234
        login_resp = client.post("/api/login", json={"codigo": "102", "pin": "1234"})
        if login_resp.status_code != 200:
            print(f"[FALLA] Login inicial falló: {login_resp.status_code} - {login_resp.text}")
            sys.exit(1)

        # -------------------------------------------------------------
        # (1) GET /api/salas -> 5 salas y suma de totales == número de materiales en la BD
        # -------------------------------------------------------------
        try:
            resp = client.get("/api/salas")
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            salas_lista = datos.get("salas", [])
            assert len(salas_lista) == 5, f"Esperadas 5 salas, obtenidas {len(salas_lista)}"
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM public.material")
                total_bd = cursor.fetchone()[0]
            suma_totales = sum(s["total"] for s in salas_lista)
            assert suma_totales == total_bd, f"Suma de totales ({suma_totales}) != total en BD ({total_bd})"
            print(f"[PASA] (1) GET /api/salas -> 5 salas y suma de totales ({suma_totales}) == materiales BD ({total_bd})")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (1) GET /api/salas: {error}")

        # -------------------------------------------------------------
        # (2) GET /api/salas/bienvenida -> mensaje contiene "Mariana" y "¿Qué sala" y salas_opciones con 5 elementos
        # -------------------------------------------------------------
        cid_conv: str | None = None
        try:
            resp = client.get("/api/salas/bienvenida")
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            mensaje = datos.get("mensaje", "")
            assert "Mariana" in mensaje, f"Mensaje no contiene 'Mariana': {mensaje}"
            assert "¿Qué sala" in mensaje, f"Mensaje no contiene '¿Qué sala': {mensaje}"
            opciones = datos.get("salas_opciones", [])
            assert len(opciones) == 5, f"Esperadas 5 opciones de sala, obtenidas {len(opciones)}"
            cid_conv = datos.get("conversacion_id")
            assert cid_conv is not None, "conversacion_id no fue devuelto en bienvenida"
            print(f"[PASA] (2) GET /api/salas/bienvenida -> mensaje contiene 'Mariana', '¿Qué sala' y 5 opciones")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (2) GET /api/salas/bienvenida: {error}")

        # -------------------------------------------------------------
        # (3) chat "quiero la sala de ingeniería" -> sala.slug == "ingenieria" y la respuesta menciona "Andrés"
        # -------------------------------------------------------------
        try:
            resp = client.post("/api/chat", json={"texto": "quiero la sala de ingeniería", "conversacion_id": cid_conv})
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            sala = datos.get("sala")
            assert isinstance(sala, dict), f"sala no es un objeto: {sala}"
            assert sala.get("slug") == "ingenieria", f"Esperado slug 'ingenieria', obtenido '{sala.get('slug')}'"
            respuesta = datos.get("respuesta", "")
            assert "Andrés" in respuesta, f"La respuesta no menciona a Andrés: {respuesta}"
            print(f"[PASA] (3) chat 'quiero la sala de ingeniería' -> sala.slug == 'ingenieria' y respuesta menciona a 'Andrés'")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (3) chat 'quiero la sala de ingeniería': {error}")

        # -------------------------------------------------------------
        # (4) en esa conversación "libros sobre redes" -> todos los materiales devueltos tienen sala ingenieria
        # -------------------------------------------------------------
        try:
            resp = client.post("/api/chat", json={"texto": "libros sobre redes", "conversacion_id": cid_conv})
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            materiales = datos.get("materiales", [])
            assert len(materiales) > 0, "No se devolvieron materiales para 'libros sobre redes'"
            with conexion() as conn, conn.cursor() as cursor:
                for mat in materiales:
                    mid = mat.get("material_id")
                    assert mid is not None, f"Material sin material_id: {mat}"
                    cursor.execute(
                        "SELECT s.slug FROM public.material AS m JOIN public.salas AS s ON s.id = m.sala_id WHERE m.id = %s",
                        (mid,),
                    )
                    fila = cursor.fetchone()
                    assert fila and fila[0] == "ingenieria", f"Material {mid} pertenece a sala '{fila[0] if fila else None}', no 'ingenieria'"
            print(f"[PASA] (4) en sala ingeniería 'libros sobre redes' -> {len(materiales)} materiales verificados en SQL con sala 'ingenieria'")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (4) 'libros sobre redes' en ingenieria: {error}")

        # -------------------------------------------------------------
        # (5) nueva conversación, "llévame a la de contabilidad" -> sala contaduria;
        #     luego "libros sobre redes" -> sugerencia_sala.slug == "ingenieria"
        # -------------------------------------------------------------
        cid2: str | None = None
        try:
            resp1 = client.post("/api/chat", json={"texto": "llévame a la de contabilidad"})
            assert resp1.status_code == 200, f"Status {resp1.status_code} != 200"
            datos1 = resp1.json()
            cid2 = datos1.get("conversacion_id")
            assert cid2 is not None, "conversacion_id no fue devuelto en nueva conversación"
            sala1 = datos1.get("sala")
            assert isinstance(sala1, dict), f"sala no es dict: {sala1}"
            assert sala1.get("slug") == "contaduria", f"Esperado slug 'contaduria', obtenido '{sala1.get('slug')}'"

            resp2 = client.post("/api/chat", json={"texto": "libros sobre redes", "conversacion_id": cid2})
            assert resp2.status_code == 200, f"Status {resp2.status_code} != 200"
            datos2 = resp2.json()
            sug = datos2.get("sugerencia_sala")
            assert isinstance(sug, dict), f"sugerencia_sala esperada como dict, obtenido {sug}"
            assert sug.get("slug") == "ingenieria", f"Esperado sugerencia_sala 'ingenieria', obtenido '{sug.get('slug')}'"
            print(f"[PASA] (5) nueva conversación 'llévame a la de contabilidad' -> sala contaduria; luego 'libros sobre redes' -> sugerencia_sala.slug == 'ingenieria'")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (5) contaduría -> sugerencia_sala redes: {error}")

        # -------------------------------------------------------------
        # (6) "¿Cuántos días dura un préstamo?" en sala contaduria -> herramienta responder_con_documentos y contiene "8"
        # -------------------------------------------------------------
        try:
            resp = client.post("/api/chat", json={"texto": "¿Cuántos días dura un préstamo?", "conversacion_id": cid2})
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            assert datos.get("herramienta") == "responder_con_documentos", f"Herramienta esperada 'responder_con_documentos', obtenida '{datos.get('herramienta')}'"
            respuesta = datos.get("respuesta", "")
            assert "8" in respuesta, f"La respuesta no contiene '8': {respuesta}"
            print(f"[PASA] (6) '¿Cuántos días dura un préstamo?' en sala contaduria -> herramienta responder_con_documentos y contiene '8'")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (6) reglamento en contaduria: {error}")

        # -------------------------------------------------------------
        # (7) sala agro-ambiental + "Genera una bibliografía en APA sobre cultivos" -> todas las referencias con material de esa sala (SQL)
        # -------------------------------------------------------------
        try:
            resp = client.post(
                "/api/chat",
                json={"texto": "Genera una bibliografía en APA sobre cultivos", "sala": "agro-ambiental"},
            )
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            bib = datos.get("bibliografia")
            assert isinstance(bib, dict), f"bibliografia esperada como dict: {bib}"
            referencias = bib.get("referencias", [])
            assert len(referencias) > 0, f"No se obtuvieron referencias: {datos.get('respuesta')}"
            with conexion() as conn, conn.cursor() as cursor:
                for ref in referencias:
                    mid = ref.get("material_id")
                    assert mid is not None, f"Referencia sin material_id: {ref}"
                    cursor.execute(
                        "SELECT s.slug FROM public.material AS m JOIN public.salas AS s ON s.id = m.sala_id WHERE m.id = %s",
                        (mid,),
                    )
                    fila = cursor.fetchone()
                    assert fila and fila[0] == "agro-ambiental", f"Material {mid} pertenece a sala '{fila[0] if fila else None}', no 'agro-ambiental'"
            print(f"[PASA] (7) sala agro-ambiental + bibliografía APA sobre cultivos -> {len(referencias)} referencias de esa sala (verificado en SQL)")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (7) bibliografía en agro-ambiental: {error}")

        # -------------------------------------------------------------
        # (8) sin sala, "libros sobre redes" -> funciona como antes (materiales de cualquier sala)
        # -------------------------------------------------------------
        try:
            resp = client.post("/api/chat", json={"texto": "libros sobre redes", "sala": ""})
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            assert datos.get("sala") is None, f"Esperada sala None, obtenida '{datos.get('sala')}'"
            materiales = datos.get("materiales", [])
            assert len(materiales) > 0, "No se encontraron materiales sin sala"
            print(f"[PASA] (8) sin sala 'libros sobre redes' -> sala None y {len(materiales)} materiales encontrados")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (8) búsqueda sin sala: {error}")

        # -------------------------------------------------------------
        # (9) "busco libros de contabilidad" sin sala -> salas_opciones presente o propuesta de la Sala de Contaduría, sin cambiar la sala sola
        # -------------------------------------------------------------
        try:
            resp = client.post("/api/chat", json={"texto": "busco libros de contabilidad", "sala": ""})
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            assert datos.get("sala") is None, f"La sala no debió cambiar sola: {datos.get('sala')}"
            opciones = datos.get("salas_opciones")
            respuesta = datos.get("respuesta", "")
            tiene_opciones = bool(opciones and len(opciones) > 0)
            propone_contaduria = "Contaduría" in respuesta or "contaduria" in respuesta.lower() or (
                opciones is not None and any(o.get("slug") == "contaduria" for o in opciones)
            )
            assert tiene_opciones or propone_contaduria, f"No hay salas_opciones ni propuesta de Contaduría en respuesta: {respuesta}"
            print(f"[PASA] (9) 'busco libros de contabilidad' sin sala -> sala None y propuesta/opciones de Sala de Contaduría")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (9) propuesta de sala sin cambiar sola: {error}")

        # -------------------------------------------------------------
        # (10) "toda la biblioteca" -> sala null
        # -------------------------------------------------------------
        try:
            # En cid_conv (que estaba en ingenieria), pedimos toda la biblioteca
            resp = client.post("/api/chat", json={"texto": "toda la biblioteca", "conversacion_id": cid_conv})
            assert resp.status_code == 200, f"Status {resp.status_code} != 200"
            datos = resp.json()
            assert datos.get("sala") is None, f"Esperada sala None tras 'toda la biblioteca', obtenida {datos.get('sala')}"
            print(f"[PASA] (10) 'toda la biblioteca' -> sala null")
            pasadas += 1
        except Exception as error:
            print(f"[FALLA] (10) 'toda la biblioteca': {error}")

    print(f"\n{pasadas}/{total_pruebas} PASA")
    if pasadas < total_pruebas:
        sys.exit(1)


if __name__ == "__main__":
    ejecutar_pruebas()
