"""Síntesis de voz local con Piper."""

import io
import threading
import wave
from pathlib import Path
from time import perf_counter
from typing import Any

from app.config import PIPER_LENGTH_SCALE, PIPER_VOZ

_voz: Any = None
_candado_carga = threading.Lock()
_candado_sintesis = threading.Lock()
_SOLUCION_VOZ = (
    "Descarga la voz con "
    "`python -m piper.download_voices es_MX-claude-high --data-dir voces`."
)


def cargar_voz() -> Any:
    """Carga una sola instancia de Piper para todo el proceso."""
    global _voz
    if _voz is None:
        with _candado_carga:
            if _voz is None:
                if not PIPER_VOZ.is_file():
                    raise FileNotFoundError(
                        f"No se encontró la voz Piper en {PIPER_VOZ}. {_SOLUCION_VOZ}"
                    )
                if not Path(f"{PIPER_VOZ}.json").is_file():
                    raise FileNotFoundError("Falta el archivo JSON de configuración de la voz Piper.")
                from piper import PiperVoice

                _voz = PiperVoice.load(PIPER_VOZ)
    return _voz


def esta_listo() -> bool:
    """Indica si la voz de Piper terminó de cargarse."""
    return _voz is not None


def sintetizar(texto: str) -> dict[str, Any]:
    """Genera un WAV en memoria, limitando la entrada a 600 caracteres."""
    texto = texto.strip()
    if not texto:
        raise ValueError("El texto para sintetizar no puede estar vacío.")
    texto = texto[:600]

    salida = io.BytesIO()
    with _candado_sintesis:
        voz = cargar_voz()
        inicio = perf_counter()
        with wave.open(salida, "wb") as archivo:
            from piper.config import SynthesisConfig

            voz.synthesize_wav(
                texto, archivo,
                syn_config=SynthesisConfig(length_scale=PIPER_LENGTH_SCALE),
            )
        t_tts_ms = round((perf_counter() - inicio) * 1000)

    wav_bytes = salida.getvalue()
    with wave.open(io.BytesIO(wav_bytes), "rb") as archivo:
        duracion_s = archivo.getnframes() / archivo.getframerate()
    return {
        "wav_bytes": wav_bytes,
        "t_tts_ms": t_tts_ms,
        "duracion_s": duracion_s,
    }
