"""Prueba recogida, privacidad, avisos y orden de espera; revierte sus datos."""
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import herramientas, agente, auth
from app.db import conectar
from app.main import app
from fastapi.testclient import TestClient


def main():
    conn = conectar()

    @contextmanager
    def transaccion():
        yield conn

    try:
        with conn.cursor() as q:
            q.execute("SELECT id,codigo,nombre FROM usuarios WHERE codigo IN ('101','102','103','104') ORDER BY codigo")
            usuarios = [dict(zip(('id','codigo','nombre'), r)) for r in q.fetchall()]
            q.execute("INSERT INTO material(titulo,autor,tipo) VALUES ('Plan de negocios de prueba de recogida','Prueba','libro') RETURNING id")
            material_id = q.fetchone()[0]
            q.execute("INSERT INTO ejemplares(material_id,codigo_barras,estante) VALUES (%s,%s,'PRUEBA')", (material_id, uuid4().hex))
        with patch.object(herramientas, 'conexion', transaccion), patch.object(agente, 'conexion', transaccion), patch.object(agente, '_llamar_modelo', return_value=({'message': {}}, 0)):
            primera = herramientas.reservar(usuarios[0]['id'], material_id)
            segunda = herramientas.reservar(usuarios[1]['id'], material_id)
            tercera = herramientas.reservar(usuarios[2]['id'], material_id)
            assert primera['datos']['ejemplar_asignado'] and not segunda['datos']['ejemplar_asignado'] and not tercera['datos']['ejemplar_asignado']
            pregunta = '¿Cuándo puedo recoger «plan de negocios»?'
            lista = agente.procesar_mensaje(pregunta, usuario_sesion=usuarios[0])
            assert not lista['error'], lista
            assert lista['herramienta'] == 'consultar_recogida' and 'Puede recoger' in lista['respuesta'] and 'carné' in lista['respuesta']
            print('PASA: pregunta de la captura consulta reservas propias y el plazo de recogida')
            espera = herramientas.consultar_recogida(usuarios[1]['id'], pregunta)
            assert 'todavía no puede recogerla' in espera['mensaje']
            assert not any(r['material_id'] == material_id for r in herramientas.avisos_disponibilidad(usuarios[1]['id'])['listas_recoger'])
            print('PASA: una solicitud en espera no genera un aviso de recogida falso')
            ajena = herramientas.consultar_recogida(usuarios[3]['id'], pregunta)
            assert ajena['datos'] == [] and 'a su nombre' in ajena['mensaje']
            invitado = agente.procesar_mensaje(pregunta)
            assert invitado['requiere_login'] and invitado['esperando'] == 'codigo'
            print('PASA: privacidad entre cuentas y autenticación de invitados')
            with conn.cursor() as q:
                q.execute("UPDATE reservas SET expira_en=now()+interval '10 minutes' WHERE id=%s", (segunda['datos']['reserva_id'],))
            assert herramientas.cancelar_reserva(usuarios[0]['id'], primera['datos']['reserva_id'])['ok']
            avisos = herramientas.avisos_disponibilidad(usuarios[1]['id'])['listas_recoger']
            propia = next(r for r in avisos if r['reserva_id'] == segunda['datos']['reserva_id'])
            assert propia['ejemplar_id'] is not None
            assert datetime.fromisoformat(propia['expira_en']) > datetime.now(timezone.utc)+timedelta(hours=47)
            assert not any(r['reserva_id'] == tercera['datos']['reserva_id'] for r in herramientas.avisos_disponibilidad(usuarios[2]['id'])['listas_recoger'])
            print('PASA: se asigna primero a quien llegó primero y se renuevan sus 48 horas')
            nueva = herramientas.consultar_recogida(usuarios[1]['id'], pregunta)
            assert 'Puede recoger' in nueva['mensaje']
            with patch.object(auth, 'usuario_de_token', return_value=usuarios[1]):
                respuesta = TestClient(app).get('/api/avisos')
                assert respuesta.status_code == 200
                assert any(r['reserva_id'] == segunda['datos']['reserva_id'] for r in respuesta.json()['listas_recoger'])
            with patch.object(auth, 'usuario_de_token', return_value=None):
                assert TestClient(app).get('/api/avisos').status_code == 401
            print('PASA: endpoint de avisos con sesión y rechazo sin sesión')
            herramientas.avisos_disponibilidad(usuarios[1]['id'])
            with conn.cursor() as q:
                q.execute('SELECT count(*) FROM reservas WHERE material_id=%s AND ejemplar_id IS NOT NULL AND estado=\'activa\'', (material_id,))
                assert q.fetchone()[0] == 1
            print('PASA: consultar avisos repetidamente no duplica asignaciones')
    finally:
        conn.rollback()
        conn.close()
    print('6/6 comprobaciones: PASA. Datos de prueba revertidos.')


if __name__ == '__main__':
    main()
