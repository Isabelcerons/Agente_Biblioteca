"""Recomendación sobre resultados propios, criterio explícito y continuación segura."""
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import agente
from fastapi.testclient import TestClient
from app.main import app


def main():
    for frase in ('cual es el mejor', '¿Cuál de estos libros me recomiendas?', 'cuál me recomiendas de esos', 'qué libro me recomiendas', 'con cuál empiezo', 'recomiéndame el mejor'):
        assert agente._pide_recomendacion_contextual(frase), frase
    for frase in ('cuál es el mejor jugador', 'cuál es la capital de Francia', 'qué libro sobre cacao recomiendas'):
        assert not agente._pide_recomendacion_contextual(frase), frase
    lista = {'conversacion_id': 'prueba', 'usuario_id': 8,
             'expira': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
             'items': [{'material_id': 1, 'titulo': 'Opción A', 'similitud': .4},
                       {'material_id': 2, 'titulo': 'Opción B', 'similitud': .8}]}
    with patch.object(agente.herramientas, 'enriquecer_materiales', side_effect=lambda items: [{**m, 'disponibles': 1, 'total': 2} for m in items]) as enriquecer:
        for cid, usuario in (('otra', 8), ('prueba', 9)):
            texto, materiales = agente._recomendar_resultados({'catalogo_contexto': deepcopy(lista)}, cid, usuario)
            assert not materiales and 'tema' in texto
        enriquecer.assert_not_called()
        estado = {'catalogo_contexto': deepcopy(lista)}
        texto, materiales = agente._recomendar_resultados(estado, 'prueba', 8)
        assert materiales[0]['material_id'] == 2 and 'más relacionado' in texto
        assert estado['catalogo_contexto']['items'][0]['material_id'] == 2
        sin_orden = deepcopy(lista)
        for item in sin_orden['items']:
            item['similitud'] = None
        texto, materiales = agente._recomendar_resultados({'catalogo_contexto': sin_orden}, 'prueba', 8)
        assert not materiales and 'materia' in texto
    print('PASA: usuario/conversación propios, afinidad y lista sin ranking', flush=True)
    cliente = TestClient(app)
    def turno(texto, cid=None):
        r = cliente.post('/api/chat', json={'texto': texto, 'conversacion_id': cid}).json()
        assert not r.get('error'), r
        return r
    a = turno('tengo un parcial, cual me recomiendas')
    b = turno('redes y comunicaciones', a['conversacion_id'])
    assert len(b['materiales']) >= 2
    esperado = max(b['materiales'], key=lambda m: m['similitud'])['material_id']
    c = turno('cual es el mejor', b['conversacion_id'])
    assert c['herramienta'] == 'recomendar_contexto' and c['materiales'][0]['material_id'] == esperado, c
    assert 'más relacionado' in c['respuesta'] and 'Solo puedo' not in c['respuesta']
    d = turno('reserva ese libro', c['conversacion_id'])
    assert d['requiere_login'] and not d['accion_pendiente']
    e = turno('¿Cuál me recomiendas?')
    assert e['intencion'] == 'aclarar_recomendacion' and 'tema' in e['respuesta']
    print('PASA: parcial -> redes -> cuál es el mejor -> referencia al recomendado con login; sin contexto pide tema', flush=True)


if __name__ == '__main__':
    main()
