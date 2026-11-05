"""Verifica las preguntas reportadas usando historial real y una sesión autenticada."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient
from app.main import app
from evaluacion.evaluar import (
    capturar_estado_autenticacion, restaurar_estado_autenticacion,
    capturar_ids_sesiones, cerrar_sesiones_nuevas,
)


def main():
    estado = capturar_estado_autenticacion()
    sesiones = capturar_ids_sesiones()
    try:
        with TestClient(app, follow_redirects=True) as cliente:
            login = cliente.post("/api/login", json={"codigo": "101", "pin": "1234"})
            assert login.status_code == 200 and login.json()["ok"]
            saludo = cliente.post("/api/chat", json={"texto": "Hola"}).json()
            conversacion = saludo["conversacion_id"]
            for pregunta, esperado in (
                ("¿Cuántos días dura un préstamo?", "8"),
                ("¿Cómo cito un libro en APA?", "Editorial"),
            ):
                respuesta = cliente.post("/api/chat", json={"texto": pregunta, "conversacion_id": conversacion})
                datos = respuesta.json()
                assert respuesta.status_code == 200, respuesta.text
                assert not datos.get("error"), datos
                assert datos["conversacion_id"] == conversacion
                assert datos["herramienta"] == "responder_con_documentos", datos
                assert esperado in datos["respuesta"], datos
                print(f"PASA: {pregunta}", flush=True)
    finally:
        cerrar_sesiones_nuevas(sesiones)
        restaurar_estado_autenticacion(estado)


if __name__ == "__main__":
    main()
