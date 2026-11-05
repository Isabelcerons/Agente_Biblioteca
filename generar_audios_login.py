"""Generador de audios de prueba para inicio de sesión por voz.

Genera los archivos de audio con Piper (app.tts.sintetizar) y los guarda
en evaluacion/audios/ sin sobrescribir si ya existen.
"""

from pathlib import Path


_AUDIOS: list[tuple[str, str]] = [
    ("voz_06_codigo_101.wav", "Mi código es ciento uno."),
    ("voz_07_codigo_102.wav", "Mi código es ciento dos."),
    ("voz_08_pin.wav", "Uno, dos, tres, cuatro."),
    ("voz_09_pin_malo.wav", "Nueve, nueve, nueve, nueve."),
]


def generar_audios() -> list[tuple[str, bool, int]]:
    """Genera los audios de login si no existen y retorna su estado."""
    from app.tts import sintetizar
    directorio_audios = Path(__file__).resolve().parent / "evaluacion" / "audios"
    directorio_audios.mkdir(parents=True, exist_ok=True)

    reporte: list[tuple[str, bool, int]] = []
    print("=== Generación de audios de login por voz ===")
    for nombre_archivo, texto in _AUDIOS:
        ruta = directorio_audios / nombre_archivo
        if ruta.is_file():
            tamanio = ruta.stat().st_size
            reporte.append((nombre_archivo, False, tamanio))
            print(f"  [EXISTE]   {nombre_archivo:<25} ({tamanio:,} bytes)")
        else:
            resultado = sintetizar(texto)
            wav_bytes = resultado.get("wav_bytes", b"")
            ruta.write_bytes(wav_bytes)
            tamanio = len(wav_bytes)
            reporte.append((nombre_archivo, True, tamanio))
            print(f"  [GENERADO] {nombre_archivo:<25} ({tamanio:,} bytes) <- \"{texto}\"")

    return reporte


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voz", help="Modelo Piper para estas muestras, sin modificar .env")
    args = parser.parse_args()
    if args.voz:
        os.environ["PIPER_VOZ"] = args.voz
    generar_audios()


if __name__ == "__main__":
    main()
