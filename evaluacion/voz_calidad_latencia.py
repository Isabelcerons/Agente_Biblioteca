"""Mide solo selección de herramienta con Ollama real, sin ejecutar operaciones."""
import json
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agente
filas=[]
for texto in ('Mis préstamos','Tienen el libro Cien años de soledad'):
    mensajes=[{'role':'system','content':agente._prompt_sistema()},{'role':'user','content':texto}]
    inicio=perf_counter()
    respuesta,ms=agente._llamar_modelo(mensajes,True,128)
    nombre,args=agente._llamada_herramienta(respuesta)
    fila={'texto':texto,'decision_previa_real_ms':round(ms),'pared_ms':round((perf_counter()-inicio)*1000),'herramienta_llm':nombre,'argumentos_llm':args}
    inicio=perf_counter(); directa=agente._seleccion_directa_segura(texto)
    fila.update(directa=directa,seleccion_local_ms=round((perf_counter()-inicio)*1000,3))
    assert directa
    filas.append(fila); print(json.dumps(fila,ensure_ascii=True),flush=True)
Path('evaluacion/voz_calidad_latencia_llm.json').write_text(json.dumps(filas,ensure_ascii=False,indent=2),encoding='utf-8')
