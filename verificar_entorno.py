"""
verificar_entorno.py — Fase 0 del Agente de Biblioteca (UniPutumayo).

Comprueba que el entorno esté listo antes de programar:
  1. Python >= 3.13          4. Ollama con qwen2.5:3b, qwen2.5:1.5b y embeddinggemma (768 dim)
  2. Conexión a PostgreSQL   5. Piper genera prueba.wav con la voz es_MX-claude-high
  3. Extensión pgvector      6. faster-whisper (base, int8, CPU) transcribe un audio corto

Uso:  .\\venv\\Scripts\\python.exe verificar_entorno.py
Sale con código 0 si los 6 chequeos pasan y 1 si alguno falla.
"""
import os
import sys
import time
import wave
from pathlib import Path

# Trabajar siempre desde la carpeta del proyecto (las rutas .env y voces/ son relativas)
os.chdir(Path(__file__).resolve().parent)

# La consola de Windows puede no usar UTF-8; se fuerza para ver tildes y «»
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Valores usados si no existe .env (sin contraseñas)
VALORES_POR_DEFECTO = {
    "PG_HOST": "localhost",
    "PG_PORT": "5432",
    "PG_DB": "postgres",
    "PG_USER": "postgres",
    "PG_PASSWORD": "",
    "OLLAMA_HOST": "http://localhost:11434",
    "LLM_MODEL": "qwen2.5:3b",
    "LLM_MODEL_RESPALDO": "qwen2.5:1.5b",
    "EMBED_MODEL": "embeddinggemma",
    "WHISPER_MODEL": "base",
    "PIPER_VOZ": "voces/es_MX-claude-high.onnx",
}

if Path(".env").is_file():
    try:
        from dotenv import load_dotenv

        load_dotenv(".env")
    except Exception as error:
        print(f"No se pudo leer .env con python-dotenv: {error}")
        print("Solución: instala python-dotenv y vuelve a ejecutar el verificador.")
else:
    print("No existe .env; copia .env.example a .env. Se usarán valores por defecto.")

CONFIG = {
    clave: os.getenv(clave, valor)
    for clave, valor in VALORES_POR_DEFECTO.items()
}
VOZ_PIPER = None


class FalloChequeo(Exception):
    def __init__(self, detalle, soluciones):
        super().__init__(detalle)
        self.detalle = detalle
        if isinstance(soluciones, str):
            soluciones = [soluciones]
        self.soluciones = soluciones


def comprobar_python():
    version = sys.version_info
    version_texto = f"{version.major}.{version.minor}.{version.micro}"
    if version < (3, 13):
        raise FalloChequeo(
            f"Versión detectada: Python {version_texto}; se requiere 3.13 o superior.",
            "Usa py -3.13 o activa el entorno virtual correspondiente.",
        )
    return f"Python {version_texto}"


def comprobar_postgresql():
    try:
        import psycopg

        conexion = psycopg.connect(
            host=CONFIG["PG_HOST"],
            port=int(CONFIG["PG_PORT"]),
            dbname=CONFIG["PG_DB"],
            user=CONFIG["PG_USER"],
            password=CONFIG["PG_PASSWORD"],
            connect_timeout=5,
        )
        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
        finally:
            conexion.close()
        return f"Conexión correcta. {version}"
    except Exception as error:
        codigo = getattr(error, "sqlstate", None)
        texto_error = str(error)
        # Errores de autenticación: contraseña incorrecta o vacía
        if (
            codigo == "28P01"
            or "password authentication failed" in texto_error.lower()
            or "no password supplied" in texto_error.lower()
        ):
            solucion = "Escribe la contraseña del usuario de PostgreSQL en PG_PASSWORD dentro de .env."
        elif "No module named" in texto_error and "psycopg" in texto_error:
            solucion = "Instala el controlador con `py -m pip install \"psycopg[binary]\"`."
        else:
            solucion = (
                "Inicia el servicio: en PowerShell como administrador "
                "`Start-Service postgresql-x64-17`."
            )
        raise FalloChequeo(f"No se pudo conectar a PostgreSQL: {texto_error}", solucion) from error


def comprobar_vector():
    try:
        import psycopg

        with psycopg.connect(
            host=CONFIG["PG_HOST"],
            port=int(CONFIG["PG_PORT"]),
            dbname=CONFIG["PG_DB"],
            user=CONFIG["PG_USER"],
            password=CONFIG["PG_PASSWORD"],
            connect_timeout=5,
        ) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT default_version, installed_version "
                    "FROM pg_available_extensions WHERE name = 'vector'"
                )
                fila = cursor.fetchone()
        if fila is None:
            raise FalloChequeo(
                "La extensión vector no aparece entre las extensiones disponibles.",
                "Reinstala pgvector para PostgreSQL 17.",
            )
        version_defecto, version_instalada = fila
        if version_instalada:
            return (
                f"vector está instalada en esta base de datos "
                f"(versión {version_instalada}; predeterminada {version_defecto})."
            )
        return (
            f"vector está disponible (versión predeterminada {version_defecto}), "
            "pero aún no está instalada en esta base de datos."
        )
    except FalloChequeo:
        raise
    except Exception as error:
        raise FalloChequeo(
            f"No se pudo consultar la extensión vector: {error}",
            "Verifica la conexión a PostgreSQL e instala pgvector para PostgreSQL 17.",
        ) from error


def _nombre_modelo(modelo):
    if isinstance(modelo, dict):
        nombre = modelo.get("name") or modelo.get("model")
    else:
        nombre = getattr(modelo, "name", None) or getattr(modelo, "model", None)
    return nombre or ""


def _extraer_embedding(respuesta):
    if isinstance(respuesta, dict):
        embeddings = respuesta.get("embeddings")
    else:
        embeddings = getattr(respuesta, "embeddings", None)
    if embeddings is None or len(embeddings) == 0:
        raise ValueError("Ollama no devolvió ningún vector de embedding.")
    return embeddings[0]


def comprobar_ollama():
    try:
        import ollama

        cliente = ollama.Client(host=CONFIG["OLLAMA_HOST"])
        respuesta = cliente.list()
    except Exception as error:
        raise FalloChequeo(
            f"No se pudo consultar Ollama: {error}",
            "Abre Ollama o ejecuta `ollama serve`.",
        ) from error

    modelos = respuesta.get("models", []) if isinstance(respuesta, dict) else getattr(
        respuesta, "models", []
    )
    nombres = set()
    for modelo in modelos:
        nombre = _nombre_modelo(modelo)
        if nombre.endswith(":latest"):
            nombre = nombre[:-len(":latest")]
        nombres.add(nombre)

    requeridos = [
        CONFIG["LLM_MODEL"],
        CONFIG["LLM_MODEL_RESPALDO"],
        CONFIG["EMBED_MODEL"],
    ]
    faltantes = [nombre for nombre in requeridos if nombre not in nombres]
    problemas = [
        FalloChequeo(
            f"Falta el modelo {nombre}.",
            f"Ejecuta `ollama pull {nombre}`.",
        )
        for nombre in faltantes
    ]

    dimension = None
    try:
        embedding = _extraer_embedding(
            cliente.embed(model=CONFIG["EMBED_MODEL"], input="Prueba de embedding.")
        )
        dimension = len(embedding)
        if dimension != 768:
            problemas.append(
                FalloChequeo(
                    f"El embedding de {CONFIG['EMBED_MODEL']} mide {dimension}; se requieren 768 dimensiones.",
                    f"Comprueba que el modelo {CONFIG['EMBED_MODEL']} esté instalado correctamente.",
                )
            )
    except Exception as error:
        problemas.append(
            FalloChequeo(
                f"No se pudo generar el embedding de prueba: {error}",
                f"Ejecuta `ollama pull {CONFIG['EMBED_MODEL']}` y verifica Ollama.",
            )
        )

    if problemas:
        detalle = "; ".join(str(problema) for problema in problemas)
        soluciones = [solucion for problema in problemas for solucion in problema.soluciones]
        raise FalloChequeo(detalle, soluciones)

    return (
        f"Modelos requeridos disponibles ({', '.join(requeridos)}; "
        f"se aceptó la etiqueta :latest). Embedding: {dimension} dimensiones."
    )


def comprobar_piper():
    global VOZ_PIPER

    try:
        from piper import PiperVoice

        voz = PiperVoice.load(CONFIG["PIPER_VOZ"])
        with wave.open("prueba.wav", "wb") as archivo:
            voz.synthesize_wav(
                "Bienvenido a la biblioteca de la Universidad del Putumayo.",
                archivo,
            )
        VOZ_PIPER = voz

        ruta = Path("prueba.wav")
        if not ruta.is_file():
            raise FileNotFoundError("Piper no creó prueba.wav.")
        tamano = ruta.stat().st_size
        if tamano <= 10 * 1024:
            raise ValueError(f"prueba.wav pesa {tamano} bytes; se requieren más de 10 KB.")
        with wave.open(str(ruta), "rb") as archivo:
            duracion = archivo.getnframes() / archivo.getframerate()
        return f"Audio generado correctamente ({tamano} bytes, {duracion:.2f} s)."
    except Exception as error:
        ruta_voz = Path(CONFIG["PIPER_VOZ"])
        if not ruta_voz.is_file():
            solucion = (
                "Descarga la voz con "
                "`python -m piper.download_voices es_MX-claude-high --data-dir voces`."
            )
        elif "No module named" in str(error) and "piper" in str(error):
            solucion = "Instala Piper con `py -m pip install piper-tts`."
        else:
            solucion = (
                "Verifica la voz y que piper-tts 1.8 esté instalado; "
                "si falta la voz, ejecuta "
                "`python -m piper.download_voices es_MX-claude-high --data-dir voces`."
            )
        raise FalloChequeo(f"No se pudo sintetizar audio con Piper: {error}", solucion) from error


def _crear_audio_whisper(ruta):
    if VOZ_PIPER is not None:
        with wave.open(str(ruta), "wb") as archivo:
            VOZ_PIPER.synthesize_wav(
                "Hola, esta es una prueba de la biblioteca",
                archivo,
            )
        return "audio generado con Piper"

    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(16000)
        archivo.writeframes(b"\x00\x00" * 16000)
    return "silencio de 1 segundo generado con wave (Piper no disponible)"


def comprobar_whisper():
    ruta_audio = Path("tmp_whisper.wav")
    try:
        from faster_whisper import WhisperModel

        origen_audio = _crear_audio_whisper(ruta_audio)
        modelo = WhisperModel(
            CONFIG["WHISPER_MODEL"],
            device="cpu",
            compute_type="int8",
        )
        inicio = time.perf_counter()
        segmentos, _ = modelo.transcribe(str(ruta_audio), language="es")
        texto = " ".join(segmento.text.strip() for segmento in segmentos).strip()
        tiempo_transcripcion = time.perf_counter() - inicio
        return (
            f"Transcripción ({origen_audio}): «{texto or '(sin texto)'}». "
            f"Tiempo de transcripción: {tiempo_transcripcion:.2f} s."
        )
    except Exception as error:
        if "No module named" in str(error) and "faster_whisper" in str(error):
            solucion = "Instala faster-whisper con `py -m pip install faster-whisper`."
        else:
            solucion = (
                f"Verifica que faster-whisper pueda cargar el modelo "
                f"{CONFIG['WHISPER_MODEL']} en CPU con compute_type=int8."
            )
        raise FalloChequeo(f"No se pudo transcribir audio: {error}", solucion) from error
    finally:
        if ruta_audio.exists():
            try:
                ruta_audio.unlink()
            except OSError as error:
                print(f"No se pudo borrar {ruta_audio}: {error}")


def ejecutar():
    chequeos = [
        ("Python", comprobar_python),
        ("PostgreSQL", comprobar_postgresql),
        ("Extensión vector", comprobar_vector),
        ("Ollama", comprobar_ollama),
        ("Piper", comprobar_piper),
        ("faster-whisper", comprobar_whisper),
    ]
    correctos = 0

    for nombre, chequeo in chequeos:
        inicio = time.perf_counter()
        try:
            detalle = chequeo()
        except FalloChequeo as error:
            duracion = time.perf_counter() - inicio
            print(f"[FALLA] {nombre} ({duracion:.2f} s): {error.detalle}")
            for solucion in error.soluciones:
                print(f"Solución: {solucion}")
        except Exception as error:
            duracion = time.perf_counter() - inicio
            print(f"[FALLA] {nombre} ({duracion:.2f} s): Error inesperado: {error}")
            print("Solución: Revisa el detalle, las dependencias y la configuración del chequeo.")
        else:
            correctos += 1
            duracion = time.perf_counter() - inicio
            print(f"[OK] {nombre} ({duracion:.2f} s): {detalle}")

    print(f"\n{correctos}/6 chequeos OK")
    return 0 if correctos == 6 else 1


if __name__ == "__main__":
    raise SystemExit(ejecutar())
