"""Regresión de la transcripción reportada y recuperación conjunta APA/IEEE."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from app.main import app
from app.consultas import normalizar_consulta


def main():
    for frase in ("Necesito las reglas I, triple E, enormes APA.", "Necesito las normas i e e e y APA", "Explícame las normas triple E y APA"):
        corregida = normalizar_consulta(frase)
        assert "IEEE" in corregida and "triple" not in corregida
    for frase in ("1234", "uno dos tres cuatro", "mi código es ciento uno", "enormes libros", "un triple enlace"):
        assert normalizar_consulta(frase) == frase
    cliente = TestClient(app)
    for pregunta in ("Necesito las reglas I, triple E, enormes APA.", "Necesito las normas IEEE y APA"):
        resultado = cliente.post('/api/chat', json={"texto": pregunta}).json()
        assert not resultado.get('error'), resultado
        assert resultado['herramienta'] == 'responder_con_documentos'
        assert resultado['respuesta'].startswith('APA\n') and '\nIEEE\n' in resultado['respuesta']
        assert 'autor-fecha' in resultado['respuesta'] and 'corchetes' in resultado['respuesta']
        assert 'APA:' in resultado['respuesta_voz'] and 'IEEE:' in resultado['respuesta_voz']
        assert 'corchetes' in resultado['respuesta_voz'], resultado['respuesta_voz']
        assert any('IEEE' in f['documento'] for f in resultado['fuentes'])
        assert any('APA' in f['documento'] for f in resultado['fuentes'])
        print('PASA:', pregunta, '\n', resultado['respuesta_voz'], flush=True)
    for pregunta in ('¿Cómo cito un libro en APA?', '¿Cómo cito un libro en IEEE?'):
        resultado = cliente.post('/api/chat', json={"texto": pregunta}).json()
        assert not resultado.get('error') and 'formato' in resultado['respuesta'].lower(), resultado
        print('PASA:', pregunta, flush=True)
    print('Regresión de normas y privacidad: PASA')


if __name__ == '__main__':
    main()
