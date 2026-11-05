"""
medir_velocidad.py — Mide los tiempos del agente contra el servidor en marcha (Fase A).

Uso:  python medir_velocidad.py <etiqueta> [--repeticiones 3]
      (requiere el servidor en http://127.0.0.1:8000)

Casos (los mismos de la medición de la usuaria):
  1. Voz "Hola"                       → /api/voz   (STT + agente + TTS)
  2. TTS de una frase                 → /api/tts
  3. Búsqueda semántica por texto     → /api/chat
  4. Pregunta de reglamento (RAG+LLM) → /api/chat
  5. Búsqueda por voz                 → /api/voz con evaluacion/audios/voz_01_busqueda.wav

Hace 1 llamada de calentamiento por caso y luego N repeticiones; reporta la MEDIANA de cada etapa.
Guarda el resultado en evaluacion/velocidad_<etiqueta>.json para comparar antes y después.
"""
import argparse
import json
import statistics
import sys
import time
import wave
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8000"
FRASE_TTS = "Encontré cinco libros sobre seguridad de redes. El primero es Fundamentos de seguridad en redes, de William Stallings, con dos ejemplares disponibles."


def audio_hola(cliente: httpx.Client) -> bytes:
    """Genera (una vez) un WAV con la palabra "Hola" usando el propio TTS del servidor."""
    ruta = RAIZ / "evaluacion" / "audios" / "voz_00_hola.wav"
    if not ruta.exists():
        import base64
        r = cliente.post(f"{BASE}/api/tts", json={"texto": "Hola, buenas tardes."}).json()
        ruta.write_bytes(base64.b64decode(r["audio_wav_base64"]))
    return ruta.read_bytes()


def duracion_wav(datos: bytes) -> float:
    import io
    with wave.open(io.BytesIO(datos)) as w:
        return w.getnframes() / w.getframerate()


def medir(cliente: httpx.Client, caso: str) -> dict:
    """Ejecuta un caso y devuelve los tiempos por etapa (ms) y el tiempo de pared."""
    t0 = time.perf_counter()
    if caso == "voz_hola":
        r = cliente.post(f"{BASE}/api/voz", files={"audio": ("hola.wav", audio_hola(cliente), "audio/wav")}).json()
    elif caso == "voz_busqueda":
        datos = (RAIZ / "evaluacion" / "audios" / "voz_01_busqueda.wav").read_bytes()
        r = cliente.post(f"{BASE}/api/voz", files={"audio": ("b.wav", datos, "audio/wav")}).json()
    elif caso == "tts_frase":
        r = cliente.post(f"{BASE}/api/tts", json={"texto": FRASE_TTS}).json()
        r = {"tiempos": {"t_tts_ms": r.get("t_tts_ms")}}
    elif caso == "texto_busqueda":
        r = cliente.post(f"{BASE}/api/chat", json={"texto": "Busco libros sobre cómo proteger una red de una empresa"}).json()
    elif caso == "texto_reglamento":
        r = cliente.post(f"{BASE}/api/chat", json={"texto": "¿Qué pasa si devuelvo tarde un libro?"}).json()
    pared = round((time.perf_counter() - t0) * 1000)
    t = r.get("tiempos") or {}
    return {
        "stt": t.get("t_stt_ms"), "embedding": t.get("t_embedding_ms"), "busqueda": t.get("t_busqueda_ms"),
        "llm": t.get("t_llm_ms"), "tts": t.get("t_tts_ms"), "total": t.get("t_total_ms") or pared, "pared": pared,
        "herramienta": r.get("herramienta"), "respuesta": (r.get("respuesta") or "")[:160],
        "transcripcion": r.get("transcripcion"),
    }


def mediana(valores):
    v = [x for x in valores if isinstance(x, (int, float))]
    return round(statistics.median(v)) if v else None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("etiqueta")
    p.add_argument("--repeticiones", type=int, default=3)
    p.add_argument("--casos", default="", help="lista separada por comas (por defecto, todos)")
    a = p.parse_args()
    casos = ["voz_hola", "tts_frase", "texto_busqueda", "texto_reglamento", "voz_busqueda"]
    if a.casos:
        casos = [c for c in casos if c in a.casos.split(",")]
    salida = {"etiqueta": a.etiqueta, "salud": None, "casos": {}}
    with httpx.Client(timeout=600) as c:
        salida["salud"] = c.get(f"{BASE}/api/salud").json()
        for caso in casos:
            medir(c, caso)  # calentamiento (no cuenta)
            muestras = [medir(c, caso) for _ in range(a.repeticiones)]
            fila = {k: mediana([m[k] for m in muestras]) for k in ("stt", "embedding", "busqueda", "llm", "tts", "total", "pared")}
            fila["ejemplo"] = {k: muestras[-1][k] for k in ("herramienta", "respuesta", "transcripcion")}
            salida["casos"][caso] = fila
            print(f"{caso:18} " + " ".join(f"{k}={fila[k]}" for k in ("stt", "embedding", "busqueda", "llm", "tts", "total")))
    destino = RAIZ / "evaluacion" / f"velocidad_{a.etiqueta}.json"
    if a.casos and destino.exists():
        # Medición parcial: se actualizan solo esos casos en el archivo existente
        previo = json.loads(destino.read_text(encoding="utf-8"))
        previo["casos"].update(salida["casos"])
        salida = previo
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Guardado en", destino)


if __name__ == "__main__":
    main()
