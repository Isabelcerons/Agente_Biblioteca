"""Regresiones deseadas de contexto. Sin DB ni operaciones de negocio reales."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import agente, main
from app.numeros import extraer_pin, pin_explicito
from fastapi.testclient import TestClient

ID=str(uuid4())
ITEMS=[dict(material_id=91,titulo='Redes alfa',disponibles=1,total=1),dict(material_id=92,titulo='Redes beta',disponibles=1,total=1)]

def contexto(cid=ID,usuario=None,segundos=300):
    return dict(conversacion_id=cid,usuario_id=usuario,items=deepcopy(ITEMS),
                expira=(datetime.now(timezone.utc)+timedelta(seconds=segundos)).isoformat())

class Rig:
    def __init__(self, estado=None, usuario=None, real=False):
        self.estado=deepcopy(estado or {}); self.usuario=usuario; self.real=real
    def __enter__(self):
        self.stack=ExitStack()
        def mock(obj,nombre,**kw): return self.stack.enter_context(patch.object(obj,nombre,**kw))
        self.db=mock(agente,'conexion')
        self.db.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value=None
        self.cargar=mock(agente,'_cargar_conversacion',return_value=(ID,self.usuario['id'] if self.usuario else None,self.estado))
        self.mensajes=mock(agente,'_guardar_mensaje');self.guardar=mock(agente,'_guardar_turno',return_value=1)
        mock(agente,'_mensaje_historial',return_value=[])
        self.llm=mock(agente,'_llamar_modelo',return_value=({'message':{}},1))
        self.login=mock(agente.auth,'iniciar_sesion',return_value=dict(ok=False,mensaje='Reintenta'))
        self.confirmar=mock(agente,'_confirmar_pendiente',return_value=('Confirmado simulado',dict(ok=True)))
        mock(agente.herramientas,'enriquecer_materiales',side_effect=deepcopy)
        self.disponibilidad=mock(agente.herramientas,'consultar_disponibilidad',return_value=dict(ok=True,datos=deepcopy(ITEMS[1])))
        mock(agente.herramientas,'mensaje_disponibilidad',return_value='Disponible')
        self.resolver=mock(agente.herramientas,'resolver_material',return_value=dict(ok=True,datos=deepcopy(ITEMS)))
        self.prestamos=mock(agente.herramientas,'prestamos_activos_usuario',return_value=dict(ok=True,datos=[dict(prestamo_id=1,titulo='Redes alfa'),dict(prestamo_id=2,titulo='Redes beta')]))
        self.reservas=mock(agente.herramientas,'reservas_activas_usuario',return_value=[dict(reserva_id=11,material_id=91,titulo='Redes alfa'),dict(reserva_id=12,material_id=92,titulo='Redes beta')])
        self.validar=mock(agente.herramientas,'validar_renovacion',return_value=dict(ok=True))
        for nombre in ('reservar','renovar_prestamo','cancelar_reserva'):
            mock(agente.herramientas,nombre,side_effect=AssertionError('Operación real prohibida en prueba'))
        self.ejecutar=None
        if not self.real:
            self.ejecutar=mock(agente,'_ejecutar_herramienta',return_value=('Respuesta controlada',dict(ok=True,datos=deepcopy(ITEMS)),[],None,0))
        return self
    def turno(self,texto):
        r=agente.procesar_mensaje(texto,ID,usuario_sesion=self.usuario)
        assert r['intencion']!='error',r
        return r
    def __exit__(self,*args):self.stack.close()

class Pin(unittest.TestCase):
    def test_prefijos_y_ceros(self):
        for texto in ('mi PIN es cero uno dos tres','el PIN es 0123','PIN: 0123'):
            self.assertTrue(pin_explicito(texto));self.assertEqual(extraer_pin(texto),'0123')
        self.assertIsNone(extraer_pin('dame 0123 libros'))
        self.assertFalse(pin_explicito('pintura al óleo'))
    def test_explicitos_validos_invalidos_nunca_salen_crudos(self):
        for texto in ('mi PIN es 0123','el PIN es dos','PIN incorrecto secreto','PIN'):
            for estado in ({},{'tema_estudio_pendiente':True},{'esperando':'pin','codigo_login':'101'}):
                with self.subTest(texto=texto,estado=estado), Rig(estado) as rig:
                    r=rig.turno(texto)
                    self.assertTrue(r['entrada_oculta']);rig.llm.assert_not_called();rig.ejecutar.assert_not_called()
                    self.assertEqual(rig.mensajes.call_args.args[2],'[PIN oculto]')
                    self.assertEqual(rig.guardar.call_args.args[3],'[PIN oculto]')
                    if texto != 'PIN': self.assertNotIn(texto,r['respuesta'])
                    if estado.get('esperando')!='pin':rig.login.assert_not_called()
    def test_autentica_solo_con_codigo_y_estado(self):
        with Rig({'esperando':'pin','codigo_login':'101'}) as rig:
            rig.turno('mi PIN es 0123');rig.login.assert_called_once_with('101','0123','chat')
        with Rig({'esperando':'pin'}) as rig:
            rig.turno('PIN 0123');rig.login.assert_not_called()

class Confirmacion(unittest.TestCase):
    def test_cortesia_y_contradiccion(self):
        for texto in ('sí, por favor','sí gracias','confirmo, por favor'):
            self.assertTrue(agente._es_afirmativo(texto),texto)
        for texto in ('no, gracias','no por favor'):
            self.assertTrue(agente._es_negativo(texto),texto)
        for texto in ('sí pero no','sí, no gracias','no, sí','sí si no hay cola'):
            self.assertFalse(agente._es_afirmativo(texto));self.assertFalse(agente._es_negativo(texto))
    def test_pendiente_ambigua_se_conserva(self):
        pendiente=dict(tipo='reservar',params=dict(material_id=91),expira=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat())
        with Rig({'accion_pendiente':pendiente},dict(id=7,nombre='Ficticio')) as rig:
            rig.turno('sí pero no sé');self.assertTrue(rig.estado['accion_pendiente']);rig.confirmar.assert_not_called();rig.llm.assert_not_called()
            rig.turno('sí, por favor');rig.confirmar.assert_called_once();self.assertIsNone(rig.estado['accion_pendiente'])

class Clasificacion(unittest.TestCase):
    def test_reglas_publicas_y_personales(self):
        for texto in ('¿Cuántas horas tengo para recoger una reserva?','¿A qué hora se pueden recoger libros?','¿A qué hora abren?','¿Cuándo cierran?','¿Cómo pago una multa?','¿Dónde pagar una multa?'):
            self.assertEqual(agente.intencion_por_palabras(texto),'responder_con_documentos',texto)
        for texto in ('Mis reservas','Quiero ver mis reservas'):
            self.assertEqual(agente.intencion_por_palabras(texto),'consultar_prestamos_y_multas')
        self.assertEqual(agente.intencion_por_palabras('¿Cuándo puedo recoger mi reserva?'),'consultar_recogida')
    def test_renovacion_sin_titulo(self):
        for texto in ('Renueva mi préstamo','¿Puedo renovar mi préstamo?','Quiero renovar mi préstamo'):
            self.assertEqual(agente.intencion_por_palabras(texto),'renovar_prestamo')
            self.assertEqual(agente._titulo_renovacion(texto),'',texto)
    def test_negaciones_sin_login_ni_propuesta(self):
        for texto in ('No quiero reservar','No reservar','Si no hay ejemplares, no quiero estar en cola'):
            with Rig() as rig:
                r=rig.turno(texto);rig.ejecutar.assert_not_called();rig.login.assert_not_called();self.assertFalse(r['accion_pendiente'])
    def test_materia_y_cambio_pregunta(self):
        with Rig({'tema_estudio_pendiente':True}) as rig:
            rig.turno('de redes');self.assertEqual(rig.ejecutar.call_args.args[1]['consulta'],'Busco libros sobre redes para estudiar')
        for texto in ('¿A qué hora abren?','¿Dónde pagar una multa?'):
            with Rig({'tema_estudio_pendiente':True}) as rig:
                rig.turno(texto);self.assertEqual(rig.ejecutar.call_args.args[0],'responder_con_documentos')
        with Rig({'tema_estudio_pendiente':True}) as rig:
            rig.turno('¿Qué quieres decir?');rig.ejecutar.assert_not_called();self.assertTrue(rig.estado['tema_estudio_pendiente'])
    def test_normas_no_se_revierten(self):
        with Rig() as rig:
            rig.turno('Explícame enormes APA y triple E')
            self.assertEqual(rig.ejecutar.call_args.args[1]['pregunta'],'Explícame normas APA y IEEE')

class Referencias(unittest.TestCase):
    def test_snapshot_acotado_persistido(self):
        with Rig() as rig:
            rig.turno('Busco libros sobre redes')
            snapshot=rig.estado['catalogo_contexto']
            self.assertEqual(len(snapshot['items']),2);self.assertEqual(snapshot['conversacion_id'],ID)
            self.assertIs(rig.guardar.call_args.args[2],rig.estado)
            rig.turno('Reserva el segundo');self.assertEqual(rig.ejecutar.call_args.args[1]['_referencia_id'],92)
    def test_ambiguedad_rango_caducidad_otra_conversacion(self):
        for texto,snapshot in (('ese libro',contexto()),('el quinto',contexto()),('el segundo',contexto(segundos=-1)),('el primero',contexto(cid=str(uuid4()))),('el primero',contexto(usuario=8))):
            with Rig({'catalogo_contexto':snapshot}) as rig:
                r=rig.turno(texto);self.assertEqual(r['intencion'],'aclarar_material');rig.ejecutar.assert_not_called();rig.llm.assert_not_called()
    def test_disponibilidad_id_real_sin_resolver_titulo(self):
        with Rig({'catalogo_contexto':contexto()},real=True) as rig:
            rig.turno('¿Está disponible el segundo?');rig.disponibilidad.assert_called_once_with(92);rig.resolver.assert_not_called()
    def test_reserva_requiere_login_y_confirmacion(self):
        with Rig({'catalogo_contexto':contexto()},real=True) as rig:
            r=rig.turno('Reserva el segundo');self.assertEqual(r['esperando'],'codigo');rig.disponibilidad.assert_not_called()
        with Rig({'catalogo_contexto':contexto(usuario=7)},dict(id=7,nombre='Ficticio'),real=True) as rig:
            r=rig.turno('Reserva el segundo');self.assertEqual(r['accion_pendiente']['tipo'],'reservar');self.assertEqual(rig.estado['accion_pendiente']['params']['material_id'],92);rig.confirmar.assert_not_called()
    def test_nuevo_tema_invalida(self):
        with Rig({'catalogo_contexto':contexto()}) as rig:
            rig.turno('horario biblioteca');self.assertNotIn('catalogo_contexto',rig.estado)
    def test_seleccion_prestamo_propio(self):
        with Rig(usuario=dict(id=7,nombre='Ficticio'),real=True) as rig:
            rig.turno('Renueva mi préstamo');self.assertEqual(len(rig.estado['seleccion_propia']['items']),2)
            r=rig.turno('el segundo');self.assertEqual(r['accion_pendiente']['tipo'],'renovar_prestamo');rig.validar.assert_called_once_with(7,2)
    def test_seleccion_reserva_propia(self):
        with Rig(usuario=dict(id=7,nombre='Ficticio'),real=True) as rig:
            rig.turno('Cancela mi reserva');self.assertEqual(len(rig.estado['seleccion_propia']['items']),2)
            r=rig.turno('Redes beta');self.assertEqual(r['accion_pendiente']['tipo'],'cancelar_reserva');self.assertEqual(rig.estado['accion_pendiente']['params']['reserva_id'],12)
    def test_seleccion_propia_revalida_ids(self):
        with Rig(usuario=dict(id=7,nombre='Ficticio'),real=True) as rig:
            rig.turno('Renueva mi préstamo');rig.prestamos.return_value=dict(ok=True,datos=[dict(prestamo_id=1,titulo='Redes alfa')])
            r=rig.turno('el segundo');self.assertFalse(r['accion_pendiente']);rig.validar.assert_not_called()

class Transcripcion(unittest.TestCase):
    def test_pin_explicito_fuera_estado_y_revalidacion(self):
        client=TestClient(main.app)
        for texto in ('mi PIN es 0123','el PIN es error','PIN'):
            with patch.object(main.auth,'usuario_de_token',return_value=None),patch.object(main,'_validar_conversacion_transcripcion',return_value=False) as validar,patch.object(main.stt,'transcribir',return_value=dict(texto=texto,t_stt_ms=12)):
                r=client.post('/api/transcribir',files={'audio':('audio.wav',b'fake')})
                self.assertEqual(r.status_code,200);self.assertEqual(r.json()['transcripcion'],'[PIN oculto]');self.assertTrue(r.json()['requiere_envio_seguro']);self.assertEqual(validar.call_count,2)
    def test_ajena_no_transcribe(self):
        from fastapi import HTTPException
        with patch.object(main.auth,'usuario_de_token',return_value=None),patch.object(main,'_validar_conversacion_transcripcion',side_effect=HTTPException(403,'Ajena')),patch.object(main.stt,'transcribir') as stt:
            r=TestClient(main.app).post('/api/transcribir',files={'audio':('audio.wav',b'fake')})
            self.assertEqual(r.status_code,403);stt.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
