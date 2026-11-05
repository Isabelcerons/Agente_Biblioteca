"""Reconocimiento de voz local con faster-whisper."""

import re
import tempfile
import threading
from pathlib import Path
from time import perf_counter
from typing import Any

from app.config import WHISPER_MODEL, WHISPER_THREADS
from app.numeros import extraer_codigo, _normalizar
from app.consultas import normalizar_consulta

_modelo: Any = None
_candado_carga = threading.Lock()
_candado_transcripcion = threading.Lock()
_MENSAJE_SIN_AUDIO = "No se escuchó nada, intente de nuevo"
_PROMPT_INICIAL = (
    "Biblioteca, préstamo, renovar, reservar, multa, APA, IEEE, tesis, "
    "código de estudiante."
)


def cargar_modelo() -> Any:
    """Carga una sola instancia de Whisper para todo el proceso."""
    global _modelo
    if _modelo is None:
        with _candado_carga:
            if _modelo is None:
                from faster_whisper import WhisperModel

                # Se carga UNA sola vez; int8 en CPU con tantos hilos como núcleos físicos
                _modelo = WhisperModel(
                    WHISPER_MODEL,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=WHISPER_THREADS,
                )
    return _modelo


def esta_listo() -> bool:
    """Indica si el modelo de Whisper terminó de cargarse."""
    return _modelo is not None


def _extension_audio(audio_bytes: bytes) -> str:
    """Conserva una extensión reconocible por FFmpeg según la firma del audio."""
    if audio_bytes.startswith(b"RIFF") and audio_bytes[8:12] == b"WAVE":
        return ".wav"
    if audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        return ".webm"
    if audio_bytes.startswith(b"OggS"):
        return ".ogg"
    if audio_bytes.startswith(b"ID3") or (
        len(audio_bytes) > 1 and audio_bytes[0] == 0xFF and audio_bytes[1] & 0xE0 == 0xE0
    ):
        return ".mp3"
    if len(audio_bytes) > 12 and audio_bytes[4:8] == b"ftyp":
        return ".mp4"
    return ".audio"


def transcribir(audio_bytes: bytes) -> dict[str, Any]:
    """Transcribe un audio en español y elimina siempre el archivo temporal."""
    if not audio_bytes:
        raise ValueError(_MENSAJE_SIN_AUDIO)
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise ValueError("El audio supera el límite de 10 MB.")

    ruta_temporal: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=_extension_audio(audio_bytes),
            delete=False,
        ) as archivo:
            ruta_temporal = archivo.name
            archivo.write(audio_bytes)

        with _candado_transcripcion:
            modelo = cargar_modelo()
            inicio = perf_counter()
            try:
                # La decodificación del audio ocurre aquí y en la iteración de segmentos
                segmentos, info = modelo.transcribe(
                    ruta_temporal,
                    language="es",
                    beam_size=1,
                    vad_filter=True,
                    initial_prompt=_PROMPT_INICIAL,
                )
                texto = " ".join(segmento.text.strip() for segmento in segmentos).strip()
                # Reintenta una frase de identificación dudosa con más alternativas.
                # El contexto enseña la gramática; no contiene códigos ni PIN válidos.
                normalizado = _normalizar(texto)
                if (
                    float(getattr(info, "duration", 0) or 0) < 10
                    and re.search(r"\b(?:codigo|digo|siento)\b", normalizado)
                    and not extraer_codigo(texto)
                ):
                    alternativas, _ = modelo.transcribe(
                        ruta_temporal, language="es", beam_size=5, vad_filter=True,
                        initial_prompt="Mi código es. Soy el usuario. Código de usuario. PIN.",
                        condition_on_previous_text=False,
                    )
                    alternativa = " ".join(s.text.strip() for s in alternativas).strip()
                    if extraer_codigo(alternativa) and re.search(r"\bcodigo\b", _normalizar(alternativa)):
                        texto = alternativa
            except Exception as error:
                # Audio corrupto o formato no soportado: mensaje amable, no error técnico
                raise ValueError(
                    "No pude leer el audio. Grábelo de nuevo, por favor."
                ) from error
            t_stt_ms = round((perf_counter() - inicio) * 1000)
            # Correcciones de homófonos frecuentes de Whisper en este dominio
            texto = normalizar_consulta(texto)
            texto = re.sub(r"\bsito\b", "cito", texto, flags=re.I)
            texto = re.sub(r"\bsitar\b", "citar", texto, flags=re.I)
            texto = re.sub(r"\bsita\b", "cita", texto, flags=re.I)

        duracion_s = float(getattr(info, "duration", 0.0) or 0.0)
        if duracion_s < 0.3 or not texto:
            raise ValueError(_MENSAJE_SIN_AUDIO)
        return {
            "texto": texto,
            "idioma": getattr(info, "language", None) or "es",
            "duracion_s": duracion_s,
            "t_stt_ms": t_stt_ms,
        }
    finally:
        if ruta_temporal is not None:
            Path(ruta_temporal).unlink(missing_ok=True)
