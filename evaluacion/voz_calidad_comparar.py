"""Comparación reproducible local; no usa datos personales ni sobrescribe audios."""
import io
import json
from pathlib import Path
import sys
from time import perf_counter
import wave
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from piper import PiperVoice
from piper.config import SynthesisConfig

TEXTOS = {
    'bienvenida': 'Hola, soy el asistente de la biblioteca. Puedo ayudarte a buscar libros y consultar tus préstamos. ¿Qué necesitas hoy?',
    'opciones': 'Encontré tres opciones. Primera: Introducción a la programación, con dos ejemplares disponibles. Segunda: Bases de datos, con un ejemplar. Tercera: Redes de computadores. ¿Cuál te interesa?',
    'numeros': 'Tienes 3 préstamos. El plazo es de 8 días y puedes renovar hasta 3 veces. La multa es de 1000 pesos por día. Hay 12 ejemplares y 5 están disponibles.',
}

def main():
    raiz = Path(__file__).resolve().parents[1]
    salida = raiz / 'evaluacion' / ('voz_calidad_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    salida.mkdir(exist_ok=False)
    filas = []
    for modelo in ('ald-medium', 'claude-high'):
        inicio = perf_counter()
        voz = PiperVoice.load(raiz / 'voces' / f'es_MX-{modelo}.onnx')
        carga = round((perf_counter() - inicio)*1000)
        for escala in ((1.0,) if modelo == 'ald-medium' else (1.0, 0.92)):
            for nombre, texto in TEXTOS.items():
                buf = io.BytesIO()
                inicio = perf_counter()
                with wave.open(buf, 'wb') as wav:
                    voz.synthesize_wav(texto, wav, syn_config=SynthesisConfig(length_scale=escala))
                ms = round((perf_counter()-inicio)*1000)
                datos = buf.getvalue()
                with wave.open(io.BytesIO(datos), 'rb') as wav:
                    assert wav.getnchannels()==1 and wav.getsampwidth()==2 and wav.getnframes()>0
                    duracion=wav.getnframes()/wav.getframerate()
                    frecuencia=wav.getframerate()
                archivo=f'voz_calidad_{modelo}_{escala}_{nombre}.wav'
                (salida/archivo).write_bytes(datos)
                fila=dict(modelo=modelo, escala=escala, muestra=nombre, texto=texto, carga_ms=carga,
                          t_tts_ms=ms, duracion_s=round(duracion,3), rtf=round(ms/1000/duracion,3),
                          frecuencia_hz=frecuencia, archivo=archivo)
                filas.append(fila)
                print(json.dumps({k:v for k,v in fila.items() if k!='texto'}), flush=True)
        del voz
    (salida/'voz_calidad_resultados.json').write_text(json.dumps(filas,ensure_ascii=False,indent=2),encoding='utf-8')
    print(salida)

if __name__=='__main__':
    main()
