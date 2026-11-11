"""Configuración común para las fases de conocimiento y backend."""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _variable(nombre: str, permitir_vacio: bool = False) -> str:
    """Obtiene una variable obligatoria sin proporcionar credenciales ficticias."""
    valor = os.getenv(nombre)
    if valor is None or (not valor and not permitir_vacio):
        raise RuntimeError(
            f"Falta la variable obligatoria {nombre} en el archivo .env."
        )
    return valor


PG_HOST = _variable("PG_HOST")
PG_PORT = int(_variable("PG_PORT"))
PG_DB = _variable("PG_DB")
PG_USER = _variable("PG_USER")
PG_PASSWORD = _variable("PG_PASSWORD", permitir_vacio=True)

OLLAMA_HOST = _variable("OLLAMA_HOST")
LLM_MODEL = _variable("LLM_MODEL")
LLM_MODEL_RESPALDO = _variable("LLM_MODEL_RESPALDO")
EMBED_MODEL = _variable("EMBED_MODEL")
WHISPER_MODEL = _variable("WHISPER_MODEL")
PIPER_VOZ = (RAIZ / os.getenv("PIPER_VOZ", "voces/es_MX-claude-high.onnx")).resolve()
# Menor que 1 acelera fonemas conservando el tono y la prosodia del modelo.
PIPER_LENGTH_SCALE = float(os.getenv("PIPER_LENGTH_SCALE", "0.92"))
if not 0.75 <= PIPER_LENGTH_SCALE <= 1.25:
    raise RuntimeError("PIPER_LENGTH_SCALE debe estar entre 0.75 y 1.25.")

DIAS_PRESTAMO = 8
MAX_RENOVACIONES = 3
MULTA_POR_DIA = 1000
HORAS_RESERVA = 48
TOP_K = 5

# --- Rendimiento (Fase A): configurables en .env, con valores pensados para CPU de 12 GB ---
# Ventana de contexto del LLM: 2048 basta para el prompt del sistema + 6 mensajes + 3 fragmentos.
NUM_CTX = int(os.getenv("NUM_CTX", "2048"))
# Tope de fichas generadas por el LLM al redactar (la decisión de herramienta usa menos).
NUM_PREDICT = int(os.getenv("NUM_PREDICT", "200"))
# Topes optimizados para velocidad en CPU (Misión Gemini-1)
NUM_PREDICT_TOOL_CALLING = int(os.getenv("NUM_PREDICT_TOOL_CALLING", "64"))
NUM_PREDICT_REDACCION = int(os.getenv("NUM_PREDICT_REDACCION", "120"))
UMBRAL_RELEVANCIA_SALA = float(os.getenv("UMBRAL_RELEVANCIA_SALA", "0.35"))
# Tiempo que Ollama mantiene los modelos en memoria entre consultas (evita recargarlos).
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "30m")
# Hilos de CPU para faster-whisper: núcleos FÍSICOS (los lógicos con hyperthreading no ayudan).
WHISPER_THREADS = int(os.getenv("WHISPER_THREADS", str(max(1, (os.cpu_count() or 2) // 2))))
# Modo híbrido: modelo que REDACTA las respuestas con documentos (la decisión de
# herramienta sigue con LLM_MODEL). Por defecto, el mismo modelo principal.
LLM_MODEL_REDACCION = os.getenv("LLM_MODEL_REDACCION", LLM_MODEL)
