"""Dos copias, tres cuentas y fechas de espera, sin conservar datos de prueba."""
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import herramientas, agente
from app.db import conectar


def main():
    conn = conectar()

    @contextmanager
    def transaccion_prueba():
        yield conn

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE codigo IN ('101','102','103') ORDER BY codigo")
            usuarios = [r[0] for r in cursor.fetchall()]
            cursor.execute("INSERT INTO material(titulo,autor,tipo) VALUES ('Prueba de copias y espera','Prueba','libro') RETURNING id")
            material_id = cursor.fetchone()[0]
            for _ in range(2):
                cursor.execute("INSERT INTO ejemplares(material_id,codigo_barras,estante) VALUES (%s,%s,'PRUEBA')", (material_id, uuid4().hex))
        with patch.object(herramientas, "conexion", transaccion_prueba):
            primera = herramientas.reservar(usuarios[0], material_id)
            assert primera["ok"] and primera["datos"]["ejemplar_asignado"]
            assert primera["datos"]["disponibilidad"]["disponibles"] == 1
            assert "Quedan 1 de 2" in primera["mensaje"]
            print("PASA: primera cuenta aparta una de dos copias")
            segunda = herramientas.reservar(usuarios[1], material_id)
            assert segunda["ok"] and segunda["datos"]["ejemplar_asignado"]
            with conn.cursor() as cursor:
                cursor.execute("SELECT count(DISTINCT ejemplar_id) FROM reservas WHERE material_id=%s AND ejemplar_id IS NOT NULL", (material_id,))
                assert cursor.fetchone()[0] == 2
            print("PASA: segunda cuenta obtiene una copia diferente")
            disponibilidad = herramientas.consultar_disponibilidad(material_id)["datos"]
            assert disponibilidad["disponibles"] == 0 and disponibilidad["reservados"] == 2
            assert disponibilidad["proxima_liberacion_reserva"]
            candidato = {"ok": True, "datos": [{"material_id": material_id, "titulo": "Prueba de copias y espera"}]}
            estado = {}
            with patch.object(herramientas, "resolver_material", return_value=candidato):
                texto, *_ = agente._ejecutar_herramienta("reservar", {"titulo": "Prueba"}, usuarios[2], estado)
            assert "quedará en espera" in texto and "apartado vence" in texto
            assert "quedará en espera" in estado["accion_pendiente"]["aviso"]
            print("PASA: tercera cuenta recibe el aviso antes de confirmar")
            tercera = herramientas.reservar(usuarios[2], material_id)
            assert tercera["ok"] and not tercera["datos"]["ejemplar_asignado"]
            assert "No se ha apartado un ejemplar" in tercera["mensaje"]
            assert tercera["datos"]["disponibilidad"]["reservas_en_espera"] == 1
            print("PASA: espera diferenciada y fecha de vencimiento del apartado")
            duplicada = herramientas.reservar(usuarios[0], material_id)
            assert not duplicada["ok"] and "Ya tiene una reserva" in duplicada["mensaje"]
            print("PASA: misma cuenta no puede duplicar su reserva")
            with conn.cursor() as cursor:
                cursor.execute("UPDATE reservas SET estado='cancelada' WHERE material_id=%s", (material_id,))
                cursor.execute("UPDATE ejemplares SET estado='prestado' WHERE material_id=%s", (material_id,))
                cursor.execute("INSERT INTO prestamos(ejemplar_id,usuario_id,fecha_vencimiento) SELECT id,%s,current_date+3 FROM ejemplares WHERE material_id=%s", (usuarios[0], material_id))
            datos = herramientas.consultar_disponibilidad(material_id)["datos"]
            assert datos["proximo_vencimiento"] and not datos["proxima_liberacion_reserva"]
            assert "devolución prevista" in herramientas.mensaje_disponibilidad(datos)
            with conn.cursor() as cursor:
                cursor.execute("UPDATE prestamos SET fecha_vencimiento=current_date-1,estado='vencido' WHERE ejemplar_id IN (SELECT id FROM ejemplares WHERE material_id=%s)", (material_id,))
            datos = herramientas.consultar_disponibilidad(material_id)["datos"]
            assert not datos["proximo_vencimiento"]
            assert "No hay una fecha" in herramientas.mensaje_disponibilidad(datos)
            print("PASA: devolución estimada futura; un vencido no promete una fecha pasada")
    finally:
        conn.rollback()
        conn.close()
    print("6/6 escenarios: PASA. Datos de prueba revertidos.")


if __name__ == "__main__":
    main()
