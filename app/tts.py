"""Síntesis local con Piper y, opcionalmente, clonación autorizada con XTTS."""

import importlib.util
import io
import os
import tempfile
import threading
import wave
from pathlib import Path
from time import perf_counter
from typing import Any

from app.config import PIPER_LENGTH_SCALE, PIPER_VOZ, RAIZ

_voces_piper: dict[str, Any] = {}
_modelo_xtts: Any = None
_candado_carga = threading.Lock()
_candado_sintesis = threading.Lock()
_MODELO_SHARVARD = RAIZ / "voces" / "es_ES-sharvard-medium.onnx"
_EXTENSIONES_AUDIO = {".wav", ".ogg", ".mp3", ".m4a", ".flac", ".opus"}

_VOCES = {
    "claude": {
        "nombre": "Claude · Español de México",
        "modelo": PIPER_VOZ,
        "speaker_id": None,
        "motor": "piper",
    },
    "ald": {
        "nombre": "Ald · Español de México",
        "modelo": RAIZ / "voces" / "es_MX-ald-medium.onnx",
        "speaker_id": None,
        "motor": "piper",
    },
    "sharvard_f": {
        "nombre": "Sharvard · Voz femenina",
        "modelo": _MODELO_SHARVARD,
        "speaker_id": 1,
        "motor": "piper",
    },
    "sharvard_m": {
        "nombre": "Sharvard · Voz masculina",
        "modelo": _MODELO_SHARVARD,
        "speaker_id": 0,
        "motor": "piper",
    },
    "personalizada": {
        "nombre": "Voz personalizada · muestra autorizada",
        "motor": "xtts",
    },
}


def _referencia_personalizada() -> Path | None:
    carpeta = RAIZ / "voz que quiero"
    if not carpeta.is_dir():
        return None
    audios = sorted(
        (archivo for archivo in carpeta.iterdir()
         if archivo.is_file() and archivo.suffix.lower() in _EXTENSIONES_AUDIO),
        key=lambda archivo: archivo.name.lower(),
    )
    return audios[0] if audios else None


def listar_voces() -> list[dict[str, Any]]:
    """Lista las voces para la interfaz sin cargar los modelos en memoria."""
    voces = []
    for identificador, voz in _VOCES.items():
        if voz["motor"] == "piper":
            modelo = voz["modelo"]
            disponible = modelo.is_file() and Path(f"{modelo}.json").is_file()
            detalle = "" if disponible else "Descarga el modelo Piper para habilitar esta voz."
        else:
            referencia = _referencia_personalizada()
            disponible = referencia is not None and importlib.util.find_spec("TTS") is not None
            if referencia is None:
                detalle = "Agrega un audio autorizado a la carpeta «voz que quiero»."
            elif importlib.util.find_spec("TTS") is None:
                detalle = "Falta instalar coqui-tts y PyTorch para activar la voz personalizada."
            else:
                detalle = "El modelo XTTS-v2 se descarga al generar la primera prueba."
        voces.append({
            "id": identificador,
            "nombre": voz["nombre"],
            "disponible": disponible,
            "detalle": detalle,
            "requiere_cpml": voz["motor"] == "xtts",
        })
    return voces


def cargar_voz() -> Any:
    """Carga la voz Piper configurada para precalentar el servidor."""
    return _cargar_piper("claude")


def _cargar_piper(identificador: str) -> Any:
    voz = _VOCES.get(identificador)
    if voz is None or voz["motor"] != "piper":
        raise ValueError("La voz seleccionada no está disponible.")
    ruta = Path(voz["modelo"])
    if not ruta.is_file():
        raise FileNotFoundError(f"Falta el modelo de voz {ruta.name}.")
    if not Path(f"{ruta}.json").is_file():
        raise FileNotFoundError(f"Falta {ruta.name}.json, necesario para cargar la voz.")
    clave_modelo = str(ruta.resolve())
    modelo_en_cache = _voces_piper.get(clave_modelo)
    if modelo_en_cache is None:
        with _candado_carga:
            modelo_en_cache = _voces_piper.get(clave_modelo)
            if modelo_en_cache is None:
                from piper import PiperVoice

                modelo_en_cache = PiperVoice.load(ruta)
                _voces_piper[clave_modelo] = modelo_en_cache
    return modelo_en_cache


def _cargar_xtts(acepto_cpml: bool) -> Any:
    global _modelo_xtts
    if not acepto_cpml:
        raise PermissionError("La voz personalizada requiere aceptar primero la licencia no comercial de XTTS-v2.")
    if importlib.util.find_spec("TTS") is None:
        raise RuntimeError(
            "Falta instalar la voz personalizada. Ejecuta instalar_voz_personalizada.bat."
        )
    if _modelo_xtts is None:
        with _candado_carga:
            if _modelo_xtts is None:
                # El valor se establece solo cuando la persona acepta en la interfaz.
                os.environ["COQUI_TOS_AGREED"] = "1"
                from TTS.api import TTS
                import TTS.tts.models.xtts as xtts_model

                # XTTS usa torchaudio.load(), que desde torchaudio 2.9 depende de
                # TorchCodec y de DLL de FFmpeg compartido. El archivo de referencia
                # que generamos es WAV PCM16, así que podemos leerlo sin esa capa.
                xtts_model.load_audio = _cargar_audio_xtts

                _modelo_xtts = TTS(
                    "tts_models/multilingual/multi-dataset/xtts_v2",
                    progress_bar=False,
                ).to("cpu")
    return _modelo_xtts


def _cargar_audio_xtts(ruta: str | Path, tasa_objetivo: int) -> Any:
    """Carga el WAV PCM de referencia sin requerir TorchCodec ni FFmpeg DLLs."""
    import numpy as np
    import torch
    import torchaudio

    with wave.open(str(ruta), "rb") as archivo:
        canales = archivo.getnchannels()
        ancho = archivo.getsampwidth()
        tasa = archivo.getframerate()
        cuadros = archivo.readframes(archivo.getnframes())
    if ancho != 2:
        raise ValueError("El audio temporal de referencia debe ser WAV PCM de 16 bits.")
    muestras = np.frombuffer(cuadros, dtype="<i2").astype(np.float32) / 32768.0
    if canales > 1:
        muestras = muestras.reshape(-1, canales).mean(axis=1)
    audio = torch.from_numpy(muestras.copy()).unsqueeze(0)
    if tasa != tasa_objetivo:
        audio = torchaudio.functional.resample(audio, tasa, tasa_objetivo)
    return audio.clamp_(-1.0, 1.0)


def esta_listo() -> bool:
    """Indica si al menos un modelo Piper se cargó correctamente."""
    return bool(_voces_piper)


def _referencia_wav(referencia: Path) -> str:
    """Decodifica el audio de referencia local a WAV PCM temporal para XTTS."""
    import numpy as np
    from faster_whisper.audio import decode_audio

    tasa = 24000
    muestras = decode_audio(str(referencia), sampling_rate=tasa)
    if len(muestras) < tasa * 6:
        raise ValueError("El audio de referencia debe contener al menos 6 segundos de voz clara.")
    muestras = muestras[:tasa * 30]
    archivo_temporal = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    ruta_temporal = archivo_temporal.name
    archivo_temporal.close()
    pcm = (np.clip(muestras, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(ruta_temporal, "wb") as destino:
        destino.setnchannels(1)
        destino.setsampwidth(2)
        destino.setframerate(tasa)
        destino.writeframes(pcm.tobytes())
    return ruta_temporal


def sintetizar(
    texto: str,
    voz_id: str = "claude",
    acepto_cpml: bool = False,
) -> dict[str, Any]:
    """Genera un WAV en memoria con la voz seleccionada."""
    texto = texto.strip()
    if not texto:
        raise ValueError("El texto para sintetizar no puede estar vacío.")
    texto = texto[:600]
    if voz_id not in _VOCES:
        raise ValueError("La voz solicitada no está en la lista permitida.")

    with _candado_sintesis:
        inicio = perf_counter()
        salida = io.BytesIO()
        if voz_id == "personalizada":
            referencia = _referencia_personalizada()
            if referencia is None:
                raise FileNotFoundError("No encontré un audio en la carpeta «voz que quiero».")
            xtts = _cargar_xtts(acepto_cpml)
            ruta_temporal = _referencia_wav(referencia)
            try:
                muestras = xtts.tts(
                    text=texto,
                    speaker_wav=ruta_temporal,
                    language="es",
                    split_sentences=True,
                )
            finally:
                Path(ruta_temporal).unlink(missing_ok=True)
            import numpy as np

            pcm = (np.clip(np.asarray(muestras), -1.0, 1.0) * 32767).astype("<i2")
            with wave.open(salida, "wb") as archivo:
                archivo.setnchannels(1)
                archivo.setsampwidth(2)
                archivo.setframerate(24000)
                archivo.writeframes(pcm.tobytes())
        else:
            modelo = _cargar_piper(voz_id)
            from piper.config import SynthesisConfig

            syn_config = SynthesisConfig(
                length_scale=PIPER_LENGTH_SCALE,
                speaker_id=_VOCES[voz_id]["speaker_id"],
            )
            with wave.open(salida, "wb") as archivo:
                modelo.synthesize_wav(texto, archivo, syn_config=syn_config)

        t_tts_ms = round((perf_counter() - inicio) * 1000)
        wav_bytes = salida.getvalue()
        with wave.open(io.BytesIO(wav_bytes), "rb") as archivo:
            duracion_s = archivo.getnframes() / archivo.getframerate()
    return {
        "wav_bytes": wav_bytes,
        "t_tts_ms": t_tts_ms,
        "duracion_s": duracion_s,
        "voz_id": voz_id,
    }
