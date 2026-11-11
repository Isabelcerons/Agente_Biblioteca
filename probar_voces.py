"""Comprueba la selección de voz de los endpoints de síntesis y conversación."""

import base64
import hashlib
import io
import wave
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import app

_RAIZ = Path(__file__).resolve().parent
_RESULTADOS: list[bool] = []


def _comprobar(descripcion: str, cumple: bool) -> None:
    _RESULTADOS.append(cumple)
    print(f"[{'PASA' if cumple else 'FALLA'}] {descripcion}")


def _audio(datos: dict[str, Any]) -> bytes:
    contenido = datos.get("audio_wav_base64")
    return base64.b64decode(contenido) if contenido else b""


def _wav_valido(contenido: bytes) -> bool:
    if len(contenido) <= 10 * 1024:
        return False
    try:
        with wave.open(io.BytesIO(contenido), "rb") as archivo:
            return archivo.getnframes() > 0 and archivo.getframerate() > 0
    except (wave.Error, EOFError):
        return False


def _ejecutar() -> None:
    voces_funcionales: list[tuple[str, bytes]] = []
    with TestClient(app) as cliente:
        respuesta_voces = cliente.get("/api/voces")
        voces = respuesta_voces.json().get("voces", []) if respuesta_voces.is_success else []
        _comprobar("GET /api/voces", respuesta_voces.is_success and bool(voces))

        for voz in voces:
            voz_id = voz["id"]
            respuesta = cliente.post(
                "/api/tts",
                json={
                    "texto": "La biblioteca responde con la voz que seleccionaste para esta conversación.",
                    "voz_id": voz_id,
                    "acepto_cpml": False,
                },
            )
            datos = respuesta.json()
            audio = _audio(datos)
            coincide = datos.get("voz_usada") == voz_id
            aviso_fallback = (
                bool(datos.get("aviso")) and datos.get("voz_usada") == "claude"
            )
            _comprobar(
                f"/api/tts voz {voz_id}: WAV válido y voz informada",
                respuesta.status_code == 200 and _wav_valido(audio)
                and (coincide or aviso_fallback),
            )
            if respuesta.status_code == 200 and _wav_valido(audio) and coincide:
                voces_funcionales.append((voz_id, audio))

        sonidos_distintos = any(
            hashlib.sha256(audio_a).digest() != hashlib.sha256(audio_b).digest()
            for indice, (_, audio_a) in enumerate(voces_funcionales)
            for _, audio_b in voces_funcionales[indice + 1:]
        )
        _comprobar("Dos voces generan audios distintos", sonidos_distintos)

        respuesta_desconocida = cliente.post(
            "/api/tts", json={"texto": "Prueba de voz desconocida.", "voz_id": "voz-inexistente"}
        )
        desconocida = respuesta_desconocida.json()
        _comprobar(
            "Voz desconocida usa la voz predeterminada con aviso",
            respuesta_desconocida.status_code == 200
            and desconocida.get("voz_usada") == "claude"
            and bool(desconocida.get("aviso"))
            and _wav_valido(_audio(desconocida)),
        )

        voz_prueba = next(
            (voz_id for voz_id, _ in voces_funcionales if voz_id != "personalizada"),
            "claude",
        )
        respuesta_chat = cliente.post(
            "/api/chat",
            json={
                "texto": "¿Cuántos días dura un préstamo?",
                "con_audio": True,
                "voz_id": voz_prueba,
            },
        )
        chat = respuesta_chat.json()
        _comprobar(
            "/api/chat con_audio respeta voz_id",
            respuesta_chat.status_code == 200
            and bool(_audio(chat))
            and chat.get("voz_usada") == voz_prueba,
        )

        ruta_audio = _RAIZ / "evaluacion" / "audios" / "voz_02_reglamento.wav"
        try:
            audio_entrada = ruta_audio.read_bytes()
        except OSError:
            audio_entrada = b""
        respuesta_voz = cliente.post(
            "/api/voz",
            data={"voz_id": voz_prueba},
            files={"audio": ("voz_02_reglamento.wav", audio_entrada, "audio/wav")},
        )
        datos_voz = respuesta_voz.json()
        _comprobar(
            "/api/voz respeta voz_id",
            bool(audio_entrada)
            and respuesta_voz.status_code == 200
            and bool(_audio(datos_voz))
            and datos_voz.get("voz_usada") == voz_prueba,
        )

    correctos = sum(_RESULTADOS)
    print(f"\n{correctos}/{len(_RESULTADOS)} PASA")
    if correctos != len(_RESULTADOS):
        raise SystemExit(1)


if __name__ == "__main__":
    _ejecutar()
