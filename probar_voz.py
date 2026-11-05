"""Prueba de aceptación de STT, TTS y endpoints de voz."""

import base64
import unicodedata
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.tts import sintetizar

_RAIZ = Path(__file__).resolve().parent
_CARPETA_AUDIOS = _RAIZ / "evaluacion" / "audios"
_PREGUNTAS = [
    (
        "voz_01_busqueda.wav",
        "Busco libros sobre seguridad de redes",
        ("seguridad", "redes"),
        "buscar_semantico",
    ),
    (
        "voz_02_reglamento.wav",
        "¿Cuántos días dura un préstamo?",
        ("prestamo",),
        "responder_con_documentos",
    ),
    (
        "voz_03_apa.wav",
        "¿Cómo cito un libro en APA?",
        ("apa",),
        "responder_con_documentos",
    ),
    (
        "voz_04_cuenta.wav",
        "Quiero ver mis multas",
        ("multas",),
        "cuenta",
    ),
    (
        "voz_05_fuera.wav",
        "¿Quién ganó el mundial de fútbol?",
        ("mundial", "futbol"),
        "fuera_de_dominio",
    ),
]
_RESULTADOS: list[tuple[str, bool]] = []


def _registrar(nombre: str, cumple: bool, detalle: str = "") -> None:
    _RESULTADOS.append((nombre, cumple))
    print(f"[{'PASA' if cumple else 'FALLA'}] {nombre}{': ' + detalle if detalle else ''}")


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def _decodificar_audio(datos: dict[str, Any]) -> bytes:
    audio = datos.get("audio_wav_base64")
    return base64.b64decode(audio) if audio else b""


def _herramienta_esperada(
    caso: str,
    herramienta: str | None,
    respuesta: str,
    intencion: str,
) -> bool:
    if caso == "cuenta":
        return (
            herramienta == "consultar_prestamos_y_multas"
            or "codigo" in _normalizar(respuesta)
        )
    if caso == "fuera_de_dominio":
        return herramienta is None or "fuera_de_dominio" in intencion
    return herramienta == caso


def _ejecutar() -> None:
    _CARPETA_AUDIOS.mkdir(parents=True, exist_ok=True)
    with TestClient(app) as cliente:
        for numero, (nombre, pregunta, palabras, caso_herramienta) in enumerate(
            _PREGUNTAS, start=1
        ):
            ruta = _CARPETA_AUDIOS / nombre
            try:
                if ruta.is_file():
                    audio_entrada = ruta.read_bytes()
                else:
                    audio_entrada = sintetizar(pregunta)["wav_bytes"]
                    ruta.write_bytes(audio_entrada)
                _registrar(f"{nombre}: audio disponible", True)
            except Exception as error:
                audio_entrada = b""
                _registrar(f"{nombre}: audio disponible", False, str(error))

            try:
                respuesta_http = cliente.post(
                    "/api/voz",
                    files={"audio": (nombre, audio_entrada, "audio/wav")},
                )
                datos = respuesta_http.json()
            except Exception as error:
                datos = {}
                _registrar(f"{nombre}: respuesta HTTP", False, str(error))
                _registrar(f"{nombre}: palabra clave", False)
                _registrar(f"{nombre}: herramienta", False)
                _registrar(f"{nombre}: audio y bitácora", False)
                continue

            transcripcion = datos.get("transcripcion", "")
            texto_normalizado = _normalizar(transcripcion)
            _registrar(
                f"{nombre}: palabra clave",
                respuesta_http.status_code == 200
                and any(palabra in texto_normalizado for palabra in palabras),
                transcripcion or datos.get("mensaje", ""),
            )
            herramienta = datos.get("herramienta")
            respuesta_voz = datos.get("respuesta_voz", "")
            _registrar(
                f"{nombre}: herramienta",
                _herramienta_esperada(
                    caso_herramienta,
                    herramienta,
                    respuesta_voz,
                    datos.get("intencion", ""),
                ),
                str(herramienta),
            )
            if caso_herramienta == "cuenta":
                _registrar(
                    f"{nombre}: requiere inicio de sesión",
                    datos.get("requiere_login") is True
                    and "iniciar sesión" in datos.get("respuesta", "").lower(),
                    datos.get("respuesta", ""),
                )

            audio_respuesta = _decodificar_audio(datos)
            tiempos = datos.get("tiempos", {})
            try:
                filas = cliente.get("/api/bitacora", params={"limite": 100}).json().get(
                    "resultados", []
                )
                fila_turno = next(
                    (
                        fila
                        for fila in filas
                        if fila.get("conversacion_id") == datos.get("conversacion_id")
                        and fila.get("entrada") == transcripcion
                    ),
                    {},
                )
                tiene_tiempos_bitacora = (
                    fila_turno.get("t_stt_ms") is not None
                    and fila_turno.get("t_tts_ms") is not None
                )
            except Exception:
                tiene_tiempos_bitacora = False
            audio_y_bitacora = len(audio_respuesta) > 10 * 1024 and tiene_tiempos_bitacora
            _registrar(
                f"{nombre}: audio > 10 KB y bitácora completa",
                audio_y_bitacora,
                f"{len(audio_respuesta)} bytes",
            )
            print(
                f"{nombre} | transcripción: {transcripcion}\n"
                f"  herramienta: {herramienta}\n"
                f"  respuesta_voz: {respuesta_voz}\n"
                f"  audio de respuesta: {len(audio_respuesta)} bytes\n"
                f"  tiempos (ms): STT={tiempos.get('t_stt_ms')}, "
                f"LLM={tiempos.get('t_llm_ms')}, TTS={tiempos.get('t_tts_ms')}, "
                f"total={tiempos.get('t_total_ms')}"
            )
            if numero == 1 and audio_respuesta:
                (_CARPETA_AUDIOS / "respuesta_01.wav").write_bytes(audio_respuesta)

        respuesta_error = cliente.post(
            "/api/voz",
            files={"audio": ("basura.wav", b"x" * 100, "audio/wav")},
        )
        try:
            datos_error = respuesta_error.json()
        except ValueError:
            datos_error = {}
        _registrar(
            "audio basura: error STT en JSON",
            respuesta_error.status_code in {200, 422}
            and datos_error.get("ok") is False
            and datos_error.get("etapa") == "stt",
            str(datos_error),
        )

        respuesta_chat = cliente.post(
            "/api/chat",
            json={"texto": "Hola", "con_audio": True},
        )
        try:
            datos_chat = respuesta_chat.json()
            audio_chat = _decodificar_audio(datos_chat)
        except ValueError:
            datos_chat = {}
            audio_chat = b""
        _registrar(
            "/api/chat con_audio",
            respuesta_chat.status_code == 200
            and bool(audio_chat)
            and datos_chat.get("t_tts_ms") is not None,
            f"{len(audio_chat)} bytes",
        )

        respuesta_tts = cliente.post("/api/tts", json={"texto": "Prueba de voz."})
        try:
            datos_tts = respuesta_tts.json()
            audio_tts = _decodificar_audio(datos_tts)
        except ValueError:
            datos_tts = {}
            audio_tts = b""
        _registrar(
            "/api/tts",
            respuesta_tts.status_code == 200
            and bool(audio_tts)
            and datos_tts.get("t_tts_ms") is not None,
            f"{len(audio_tts)} bytes",
        )

    _probar_login_voz()
    correctos = sum(cumple for _, cumple in _RESULTADOS)
    print(f"\n{correctos}/{len(_RESULTADOS)} PASA")
    if correctos != len(_RESULTADOS):
        raise SystemExit(1)


def _probar_login_voz() -> None:
    """Comprueba STT real, cookie y privacidad; restaura intentos y sesiones."""
    from evaluacion.evaluar import (
        capturar_estado_autenticacion, capturar_ids_sesiones,
        cerrar_sesiones_nuevas, restaurar_estado_autenticacion,
    )
    from generar_audios_login import generar_audios

    generar_audios()
    estado = capturar_estado_autenticacion()
    sesiones = capturar_ids_sesiones()
    try:
        with TestClient(app) as cliente:
            def voz(nombre, conversacion=None):
                return cliente.post(
                    "/api/voz", data={"conversacion_id": conversacion} if conversacion else {},
                    files={"audio": (nombre, (_CARPETA_AUDIOS / nombre).read_bytes(), "audio/wav")},
                ).json()

            for codigo, nombre, multa in (("101", "voz_06_codigo_101.wav", False), ("102", "voz_07_codigo_102.wav", True)):
                cliente.post("/api/logout")
                primero = voz(nombre)
                _registrar(f"Voz {codigo}: pide PIN", primero.get("esperando") == "pin")
                segundo = voz("voz_08_pin.wav", primero.get("conversacion_id"))
                _registrar(f"Voz {codigo}: sesión y cookie", segundo.get("sesion_iniciada") is True and bool(cliente.cookies.get("sesion_biblioteca")))
                _registrar(f"Voz {codigo}: PIN oculto", segundo.get("transcripcion") == "[PIN oculto]" and "token_sesion" not in segundo)
                if multa:
                    _registrar("Voz 102: aviso de multa", "5.000" in segundo.get("respuesta", ""))
            cliente.post("/api/logout")
            primero = voz("voz_06_codigo_101.wav")
            malo = voz("voz_09_pin_malo.wav", primero.get("conversacion_id"))
            _registrar("Voz: PIN incorrecto", not malo.get("sesion_iniciada") and "Te quedan" in malo.get("respuesta", "") and malo.get("transcripcion") == "[PIN oculto]")
    finally:
        cerrar_sesiones_nuevas(sesiones)
        restaurar_estado_autenticacion(estado)


if __name__ == "__main__":
    _ejecutar()
