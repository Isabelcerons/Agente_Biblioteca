"""Auditoría reproducible: reglas reales, sin DB, reservas ni modelo externos.
Ejecutar: venv/Scripts/python.exe evaluacion/casos_contexto_auditoria.py
Las credenciales que aparecen son ficticias; nunca usar conversaciones reales.
"""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agente
from app.consultas import normalizar_consulta

ID = str(uuid4())
MATERIALES = [dict(material_id=901, titulo='Redes de computadores', autor='Autora A', disponibles=2, total=2),
              dict(material_id=902, titulo='Fundamentos de redes', autor='Autor B', disponibles=1, total=1)]

class ConversacionControlada:
    def __init__(self, estado=None, usuario=None, historial=None):
        self.estado=deepcopy(estado or {})
        self.usuario=usuario
        self.historial=deepcopy(historial or [])

    def turno(self, texto, llamada=None):
        llamadas=[]
        guardados=[]
        def guardar_mensaje(cid, rol, contenido):
            guardados.append((rol, contenido))
            self.historial.append(dict(role=rol,content=contenido))
        def guardar_turno(*args):
            self.historial.append(dict(role='assistant', content=args[4]))
            return 1
        def ejecutar(nombre, argumentos, usuario, estado):
            llamadas.append(dict(nombre=nombre, argumentos=deepcopy(argumentos)))
            if nombre in ('buscar_semantico','buscar_exacto','consultar_disponibilidad'):
                return agente._plantilla_busqueda(MATERIALES), dict(ok=True,datos=deepcopy(MATERIALES)), [], None, 0
            if nombre in ('consultar_recogida','reservar','renovar_prestamo') and usuario is None:
                estado['esperando']='codigo'
                return 'Inicia sesión para esta operación',None,[],None,0
            return 'Respuesta controlada', dict(ok=True,datos=[]), [], None, 0
        modelo={'message': {'tool_calls': [] if llamada is None else [dict(function=dict(name=llamada[0],arguments=llamada[1]))]}}
        db=MagicMock()
        db.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value=None
        with ExitStack() as stack:
            for nombre in ('conexion',):
                stack.enter_context(patch.object(agente,nombre,db))
            stack.enter_context(patch.object(agente,'_cargar_conversacion',return_value=(ID,self.usuario['id'] if self.usuario else None,self.estado)))
            stack.enter_context(patch.object(agente,'_guardar_mensaje',side_effect=guardar_mensaje))
            stack.enter_context(patch.object(agente,'_guardar_turno',side_effect=guardar_turno))
            stack.enter_context(patch.object(agente,'_mensaje_historial',side_effect=lambda cid: deepcopy(self.historial)))
            stack.enter_context(patch.object(agente,'_llamar_modelo',return_value=(modelo,1)))
            stack.enter_context(patch.object(agente,'_ejecutar_herramienta',side_effect=ejecutar))
            stack.enter_context(patch.object(agente.herramientas,'enriquecer_materiales',side_effect=deepcopy))
            confirmar=stack.enter_context(patch.object(agente,'_confirmar_pendiente',return_value=('Confirmación simulada',dict(ok=True))))
            login=stack.enter_context(patch.object(agente.auth,'iniciar_sesion',return_value=dict(ok=False,mensaje='PIN ficticio rechazado')))
            r=agente.procesar_mensaje(texto,ID,modo_voz=True,usuario_sesion=self.usuario)
            assert r['intencion']!='error', r
            return dict(entrada=texto,intencion=r['intencion'],respuesta=r['respuesta'],herramientas=llamadas,
                        entrada_oculta=r['entrada_oculta'],mensajes=guardados,estado=deepcopy(self.estado),
                        confirmaciones=confirmar.call_count,login_intentos=login.call_count)

def pendiente():
    return dict(accion_pendiente=dict(tipo='reservar',descripcion='Redes de computadores',
        expira=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),parametros=dict(material_id=901)))

def main():
    resultados=[]
    def caso(nombre, resultado, comprobar):
        assert comprobar(resultado), (nombre,resultado)
        resultados.append((nombre,resultado))

    c=ConversacionControlada()
    caso('parcial_pide_materia',c.turno('Tengo un parcial mañana'),lambda r:r['estado'].get('tema_estudio_pendiente') is True)
    caso('de_redes_resuelve_materia',c.turno('de redes'),lambda r:r['herramientas'][0]['argumentos']['consulta']=='Busco libros sobre redes para estudiar')
    c=ConversacionControlada(estado=dict(tema_estudio_pendiente=True))
    caso('si_tras_materia_vuelve_a_preguntar',c.turno('sí'),lambda r:r['estado'].get('tema_estudio_pendiente') is True and not r['herramientas'])
    caso('no_tras_materia_cancela',c.turno('no'),lambda r:r['estado'].get('tema_estudio_pendiente') is False)
    c=ConversacionControlada(estado=dict(tema_estudio_pendiente=True))
    caso('cambio_tema_horario',c.turno('¿Cuál es el horario de la biblioteca?'),lambda r:r['herramientas'][0]['nombre']=='responder_con_documentos' and not r['estado']['tema_estudio_pendiente'])
    c=ConversacionControlada(estado=dict(tema_estudio_pendiente=True))
    caso('hora_no_es_materia_pero_se_busca',c.turno('¿A qué hora abren?'),lambda r:'hora abren' in r['herramientas'][0]['argumentos']['consulta'])
    c=ConversacionControlada(estado=dict(tema_estudio_pendiente=True))
    caso('codigo_interrumpe_aclaracion',c.turno('mi código es ciento uno'),lambda r:r['estado']['esperando']=='pin' and r['estado']['tema_estudio_pendiente'])
    caso('pin_desnudo_se_oculta',c.turno('cero uno dos tres'),lambda r:r['entrada_oculta'] and r['login_intentos']==1 and r['mensajes'][0][1]=='[PIN oculto]')
    c=ConversacionControlada(estado=dict(esperando='pin',codigo_login='101'))
    caso('pin_con_prefijo_se_guarda_crudo',c.turno('mi PIN es cero uno dos tres'),lambda r:not r['entrada_oculta'] and r['login_intentos']==0 and r['mensajes'][0][1]=='mi PIN es cero uno dos tres')
    c=ConversacionControlada(estado=dict(tema_estudio_pendiente=True))
    caso('pin_durante_materia_se_busca',c.turno('mi PIN es cero uno dos tres'),lambda r:not r['entrada_oculta'] and 'PIN' in r['herramientas'][0]['argumentos']['consulta'])
    c=ConversacionControlada()
    c.turno('Busco libros sobre redes')
    caso('ese_libro_sobrescribe_titulo_llm',c.turno('¿Está disponible ese libro?',('consultar_disponibilidad',dict(titulo='Redes de computadores'))),lambda r:r['herramientas'][0]['argumentos']['titulo']!='Redes de computadores')
    caso('reserva_segundo_sobrescribe_titulo_llm',c.turno('Reserva el segundo',('reservar',dict(titulo='Fundamentos de redes'))),lambda r:r['herramientas'][0]['argumentos']['titulo']=='segundo')
    caso('primero_depende_llm',c.turno('el primero',('consultar_disponibilidad',dict(titulo='Redes de computadores'))),lambda r:r['herramientas'][0]['argumentos']['titulo']=='Redes de computadores')
    caso('segundo_sin_llm_no_resuelve',c.turno('el segundo'),lambda r:not r['herramientas'] and 'Solo puedo' in r['respuesta'])
    caso('recomendacion_depende_llm',c.turno('¿Cuál me recomiendas?',('buscar_semantico',dict(consulta='redes'))),lambda r:r['herramientas'][0]['argumentos']['consulta']=='redes')
    for texto in ('sí','no','sí, por favor','no, gracias'):
        c=ConversacionControlada(estado=pendiente(),usuario=dict(id=7,nombre='Ficticio'))
        r=c.turno(texto)
        caso('confirmacion_'+texto,r,lambda r:r['confirmaciones']==(1 if texto=='sí' else 0) and not r['estado']['accion_pendiente'])
    for texto in ('¿Cuándo puedo recoger mi reserva?','¿A qué hora se pueden recoger los libros?', '¿Cuántas horas tengo para recoger una reserva?'):
        c=ConversacionControlada()
        caso('recogida_'+texto,c.turno(texto),lambda r:r['herramientas'][0]['nombre']=='consultar_recogida' and r['estado']['esperando']=='codigo')
    for texto in ('Explícame normas APA y triple E','Explícame enormes APA y i e e e','Genera bibliografía IEEE sobre redes'):
        c=ConversacionControlada()
        r=c.turno(texto)
        caso('normas_'+texto,r,lambda r:r['herramientas'][0]['nombre'] in ('responder_con_documentos','generar_bibliografia'))
    # Verifica tambi?n el gate REAL, que retorna antes de cualquier herramienta/DB.
    estado_gate={}
    respuesta_gate=agente._ejecutar_herramienta('consultar_recogida', {'titulo':'horas'}, None, estado_gate)
    assert estado_gate['esperando']=='codigo' and 'iniciar sesi' in respuesta_gate[0]
    assert normalizar_consulta('mi código es 101 y PIN 0123')=='mi código es 101 y PIN 0123'
    for nombre,r in resultados:
        print(json.dumps(dict(caso=nombre,**r),ensure_ascii=True))
    print('CASOS VERIFICADOS:',len(resultados))

if __name__=='__main__':main()

