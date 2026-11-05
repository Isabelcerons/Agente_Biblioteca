"""Comprueba aclaración de materia y continuación con recomendaciones reales."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.agente import procesar_mensaje, _estudio_sin_tema


def main():
    assert _estudio_sin_tema('tengo un parcial, cual me recomiendas')
    assert _estudio_sin_tema('tengo un examen mañana')
    assert not _estudio_sin_tema('tengo un parcial de redes, qué libro me recomiendas')
    assert not _estudio_sin_tema('quiero estudiar contabilidad para un examen')
    a = procesar_mensaje('tengo un parcial , cual me recomiendas')
    assert not a['error'] and a['intencion'] == 'aclarar_tema_estudio', a
    assert a['herramienta'] is None and 'materia' in a['respuesta']
    b = procesar_mensaje('de redes', a['conversacion_id'])
    assert not b['error'] and b['conversacion_id'] == a['conversacion_id'], b
    assert b['herramienta'] == 'buscar_semantico' and b['materiales'], b
    assert any('red' in m['titulo'].lower() or 'seguridad' in m['titulo'].lower() for m in b['materiales'])
    print('PASA: pregunta la materia y recomienda materiales al responder de redes', flush=True)
    c = procesar_mensaje('Tengo un parcial mañana, recomiéndame algo')
    d = procesar_mensaje('no', c['conversacion_id'])
    assert not d['error'] and d['intencion'] == 'cancelar_accion' and not d['materiales']
    print('PASA: se puede cancelar la aclaración sin hacer búsquedas', flush=True)
    e = procesar_mensaje('tengo un parcial, qué me recomiendas')
    f = procesar_mensaje('mis multas', e['conversacion_id'])
    assert f['requiere_login'] and f['esperando'] == 'codigo'
    print('PASA: cambiar a un trámite personal mantiene el inicio de sesión', flush=True)


if __name__ == '__main__':
    main()
