"""Pruebas aisladas: no contactan DB, LLM, servidor ni STT reales."""
import io
from pathlib import Path
import sys
from time import perf_counter
import unittest
from unittest.mock import patch, MagicMock
from uuid import uuid4
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import main, agente, tts

ID=str(uuid4())

class Transcripcion(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(main.app) # sin context manager: no ejecutar lifespan
        self.auth=patch.object(main.auth,'usuario_de_token',return_value=None).start()
        self.db=patch.object(main,'conexion').start()
        self.cursor=self.db.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value=(None, {})
        self.stt=patch.object(main.stt,'transcribir',return_value={'texto':'cuatro cinco seis siete','t_stt_ms':123}).start()
        self.addCleanup(patch.stopall)

    def post(self, cid=ID):
        return self.client.post('/api/transcribir', data={} if cid is None else {'conversacion_id':cid}, files={'audio':('voz.wav',b'fake','audio/wav')})

    def test_invitado(self):
        r=self.post(); self.assertEqual(r.status_code,200)
        self.assertEqual(r.json(),dict(transcripcion='cuatro cinco seis siete',t_stt_ms=123,requiere_envio_seguro=False))

    def test_sin_conversacion(self):
        self.assertEqual(self.post(None).status_code,200); self.db.assert_not_called()

    def test_pin_oculto(self):
        self.cursor.fetchone.return_value=(None,{'esperando':'pin'})
        r=self.post(); self.assertEqual(r.json()['transcripcion'],'[PIN oculto]')
        self.assertTrue(r.json()['requiere_envio_seguro'])
        self.assertNotIn('cuatro',r.text)

    def test_cambio_estado_durante_stt(self):
        self.cursor.fetchone.side_effect=[(None,{}),(None,{'esperando':'pin'})]
        self.assertTrue(self.post().json()['requiere_envio_seguro'])

    def test_usuario_propio(self):
        self.auth.return_value={'id':7}; self.cursor.fetchone.return_value=(7,{'usuario_id':7})
        self.assertEqual(self.post().status_code,200)

    def test_usuario_ajeno(self):
        self.auth.return_value={'id':7}; self.cursor.fetchone.return_value=(8,{'esperando':'pin'})
        self.assertEqual(self.post().status_code,403); self.stt.assert_not_called()

    def test_invitado_no_puede_usar_conversacion_identificada(self):
        self.cursor.fetchone.return_value=(7,{})
        self.assertEqual(self.post().status_code,403); self.stt.assert_not_called()

    def test_estado_ajeno(self):
        self.cursor.fetchone.return_value=(None,{'usuario_id':7})
        self.assertEqual(self.post().status_code,403)

    def test_uuid_invalido(self):
        self.assertEqual(self.post('invalido').status_code,400); self.stt.assert_not_called()

    def test_no_existe(self):
        self.cursor.fetchone.return_value=None
        self.assertEqual(self.post().status_code,404); self.stt.assert_not_called()

    def test_error_no_filtra(self):
        self.stt.side_effect=ValueError('secreto-no-publicar')
        r=self.post(); self.assertEqual(r.status_code,422); self.assertNotIn('secreto',r.text)

    def test_db_falla_cerrado(self):
        self.db.side_effect=RuntimeError('credencial-no-publicar')
        r=self.post(); self.assertEqual(r.status_code,503); self.assertNotIn('credencial',r.text); self.stt.assert_not_called()

    def test_sesion_cambia(self):
        self.auth.side_effect=[None,{'id':7}]
        self.assertEqual(self.post().status_code,403)

class Seleccion(unittest.TestCase):
    def test_rutas_y_argumentos_comparables(self):
        casos=['Mis préstamos','Tienen el libro Cien años de soledad','¿Está disponible Cien años de soledad?',
               'Renovar mi préstamo','De qué trata la tesis de cacao','Genera bibliografía APA sobre cacao']
        resultados=[]
        for texto in casos:
            capturas=[]
            def ejecutar(nombre, argumentos, usuario, estado):
                capturas.append((nombre,argumentos.copy()))
                return 'Resultado de prueba', {'ok':True,'datos':[]}, [], None, 0
            with patch.object(agente,'_cargar_conversacion',return_value=(ID,None,{})), \
                 patch.object(agente,'_guardar_mensaje'), patch.object(agente,'_guardar_turno',return_value=1), \
                 patch.object(agente,'_mensaje_historial',return_value=[]), \
                 patch.object(agente,'_ejecutar_herramienta',side_effect=ejecutar), \
                 patch.object(agente,'_llamar_modelo',return_value=({'message':{}},2500)) as llm:
                inicio=perf_counter(); nuevo=agente.procesar_mensaje(texto); rapido=(perf_counter()-inicio)*1000
                llm.assert_not_called()
                with patch.object(agente,'_seleccion_directa_segura',return_value=False):
                    anterior=agente.procesar_mensaje(texto)
                self.assertEqual(capturas[0],capturas[1]); self.assertEqual(nuevo['respuesta'],anterior['respuesta'])
                resultados.append((texto,round(rapido,2),nuevo['tiempos']['t_llm_ms'],anterior['tiempos']['t_llm_ms']))
        print('Comparación rutas (tiempo Python ms; decisión nueva ms; decisión simulada previa ms):',resultados)

    def test_ambiguos_conservan_llm(self):
        for texto in ('Busca libros sobre redes','Quiero reservar un libro','Mis préstamos y horarios','No quiero renovar','No sé cuál elegir','¿Cuánto dura una reserva?'):
            self.assertFalse(agente._seleccion_directa_segura(texto),texto)

class Voz(unittest.TestCase):
    def test_carga_unica_concurrente(self):
        from concurrent.futures import ThreadPoolExecutor
        import piper
        voz=object()
        with patch.object(tts, '_voz', None), patch.object(piper.PiperVoice, 'load', return_value=voz) as cargar:
            with ThreadPoolExecutor(max_workers=4) as ejecutor:
                resultados=list(ejecutor.map(lambda _: tts.cargar_voz(), range(8)))
            self.assertTrue(all(r is voz for r in resultados))
            cargar.assert_called_once()

    def test_vacio_y_limite(self):
        with self.assertRaises(ValueError): tts.sintetizar('  ')
        voz=MagicMock()
        def sintetizar(texto, archivo, **kwargs):
            self.assertEqual(len(texto),600)
            archivo.setparams((1,2,22050,0,'NONE','not compressed')); archivo.writeframes(b'\x00\x00'*100)
        voz.synthesize_wav.side_effect=sintetizar
        with patch.object(tts,'cargar_voz',return_value=voz):
            r=tts.sintetizar('a'*700)
        self.assertEqual(set(r),{'wav_bytes','t_tts_ms','duracion_s'})

if __name__=='__main__': unittest.main(verbosity=2)
