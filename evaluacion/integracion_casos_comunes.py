"""Pruebas HTTP con datos reales; no confirma reservas ni modifica préstamos."""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import conexion


def main():
    base = 'http://127.0.0.1:8000'
    for _ in range(30):
        try:
            if httpx.get(base + '/api/salud', timeout=2).json()['ok']:
                break
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(1)
    pruebas = []
    with httpx.Client(base_url=base, timeout=120) as cliente:
        def turno(texto, cid=None):
            r = cliente.post('/api/chat', json={'texto': texto, 'conversacion_id': cid})
            r.raise_for_status()
            d = r.json()
            assert not d.get('error'), d
            return d

        a = turno('Necesito las reglas I, triple E, enormes APA.')
        assert 'autor-fecha' in a['respuesta'] and 'corchetes' in a['respuesta']
        assert 'APA:' in a['respuesta_voz'] and 'IEEE:' in a['respuesta_voz']
        pruebas.append('APA e IEEE dictados con alias: ambas guías y ambas normas por voz')
        b = turno('tengo un parcial , cual me recomiendas')
        assert b['intencion'] == 'aclarar_tema_estudio'
        c = turno('de redes', b['conversacion_id'])
        assert c['herramienta'] == 'buscar_semantico' and len(c['materiales']) >= 2
        esperado = c['materiales'][1]['material_id']
        d = turno('¿Está disponible el segundo?', c['conversacion_id'])
        assert d['herramienta'] == 'consultar_disponibilidad' and d['materiales'][0]['material_id'] == esperado, d
        pruebas.append('Parcial -> de redes -> disponibilidad del segundo resultado por su ID')
        e = turno('tengo un parcial mañana')
        f = turno('¿A qué hora abren?', e['conversacion_id'])
        assert f['herramienta'] == 'responder_con_documentos' and not f['requiere_login']
        g = turno('¿Cuántas horas tengo para recoger una reserva?')
        assert g['herramienta'] == 'responder_con_documentos' and not g['requiere_login']
        pruebas.append('Horarios y plazo de recogida generales no son una materia ni exigen login')
        h = turno('No quiero reservar Redes de computadoras')
        assert not h['accion_pendiente'] and not h['requiere_login']
        i = turno('Mis reservas')
        assert i['requiere_login'] and i['esperando'] == 'codigo'
        pruebas.append('Negación respetada y consulta personal protegida')
        p = turno('mi PIN es cero uno dos tres')
        assert p['entrada_oculta'] and not p['sesion_iniciada']
        with conexion() as conn, conn.cursor() as q:
            q.execute("SELECT contenido FROM mensajes WHERE conversacion_id=%s AND rol='user' ORDER BY id DESC LIMIT 1", (p['conversacion_id'],))
            assert q.fetchone()[0] == '[PIN oculto]'
            q.execute('SELECT entrada FROM bitacora_agente WHERE id=%s', (p['bitacora_id'],))
            assert q.fetchone()[0] == '[PIN oculto]'
        pruebas.append('PIN prefijado oculto en historial y bitácora reales, sin autenticar fuera de flujo')
        j = turno('¿De qué trata el libro «Sistemas agroforestales: principios y aplicaciones en los trópicos»?')
        assert j['herramienta'] == 'resumir_material' and j['fuentes'] and any(m['tipo'] == 'libro' for m in j['materiales']), j
        pruebas.append('Resumen de libro recuperado de reseña con fuente')
        login = cliente.post('/api/login', json={'codigo': '101', 'pin': '1234'})
        assert login.status_code == 200 and login.json()['ok']
        try:
            k = turno('Mis reservas')
            assert k['herramienta'] == 'consultar_prestamos_y_multas' and not k['accion_pendiente']
            l = turno('Quiero reservar «Administración de recursos humanos»')
            assert (l['accion_pendiente'] or {}).get('tipo') == 'reservar', l
            m = turno('sí, pero no', l['conversacion_id'])
            assert m['accion_pendiente'], m
            n = turno('no, gracias', m['conversacion_id'])
            assert not n['accion_pendiente'] and n['intencion'] == 'cancelar_accion', n
            pruebas.append('Con sesión: consulta reservas, conserva confirmación ambigua y cancela con cortesía sin reservar')
        finally:
            cliente.post('/api/logout')
    resultado = {'pruebas': pruebas, 'cantidad': len(pruebas), 'operaciones_confirmadas': 0}
    Path(__file__).with_suffix('.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resultado, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
