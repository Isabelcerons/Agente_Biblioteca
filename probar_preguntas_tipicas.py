"""Prueba permanente de PREGUNTAS TÍPICAS con límites de tiempo para el Agente de Biblioteca.

Ejecuta la batería de 30 preguntas típicas del agente de biblioteca bajo
autenticación de prueba (usuario 102 / PIN 1234), midiendo tiempos de respuesta
de punta a punta y comprobando:
  - Intención y herramienta esperada (aceptando alternativas legítimas).
  - Contenido esperado (contiene, no contiene, contiene alguno, mínimo de materiales).
  - Tiempo máximo individual por pregunta según metas de latencia.
  - Tiempo promedio global (< 4.0 s).

Uso:
  python probar_preguntas_tipicas.py                 # En proceso con TestClient(app)
  python probar_preguntas_tipicas.py --servidor      # Contra http://127.0.0.1:8000
  python probar_preguntas_tipicas.py --misma-conversacion  # Peor caso de contexto acumulado
  python probar_preguntas_tipicas.py --solo "cacao"  # Filtrar preguntas específicas
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

# Forzar codificación UTF-8 en consolas de Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def normalizar(texto: Any) -> str:
    """Normaliza texto eliminando acentos y convirtiendo a minúsculas."""
    descompuesto = unicodedata.normalize("NFD", str(texto or "").casefold())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def limpiar_intencion(intencion: Any) -> str:
    """Elimina sufijos calificadores de la intención (ej. '(rápido)', '(llm)') y de sala (ej. ' · sala X' o ' · ...')."""
    if intencion is None:
        return ""
    texto = str(intencion)
    texto = re.sub(r"\s*·\s*.*$", "", texto)
    texto = re.sub(r"\s*\([^)]*\)\s*$", "", texto)
    texto = re.sub(r"\s*·\s*.*$", "", texto)
    return texto.strip().lower()


# Definición de la batería de 30 preguntas típicas y sus criterios de aceptación
CASOS_PREGUNTAS_TIPICAS: list[dict[str, Any]] = [
    {
        "id": 1,
        "pregunta": "Hola",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["saludo", "cortesia", "presentacion"],
        "herramientas": [None, "cortesia", "saludo", "presentacion"],
        "contiene_alguno": ["hola", "buen", "bienvenid", "ayudar", "puedo ayudar", "dia", "tarde"],
    },
    {
        "id": 2,
        "pregunta": "¿Quién eres?",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["presentacion", "saludo", "ayuda"],
        "no_intenciones": ["fuera_de_dominio"],
        "herramientas": [None, "presentacion", "saludo"],
        "contiene_alguno": ["agente", "biblioteca", "asistente", "uniputumayo", "institucion universitaria"],
        "no_contiene": ["fuera de mi dominio", "no puedo responder preguntas sobre"],
    },
    {
        "id": 3,
        "pregunta": "¿Qué puedes hacer?",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["presentacion", "ayuda", "saludo", "responder_con_documentos"],
        "herramientas": [None, "presentacion", "responder_con_documentos"],
        "contiene_alguno": ["buscar", "reservar", "prestamo", "renovar", "bibliografia", "tesis", "consultar", "catalogo", "ayudar"],
    },
    {
        "id": 4,
        "pregunta": "¿Qué libros tienes?",
        "categoria": "panorama",
        "max_seg": 3.0,
        "intenciones": ["panorama_catalogo", "panorama", "buscar_semantico", "responder_con_documentos"],
        "herramientas": ["panorama_catalogo", "buscar_semantico", None],
        "contiene_alguno": ["libro", "tesis", "catalogo", "titulo", "ejemplar", "contamos con", "acervo"],
        "regex": r"\d+",
    },
    {
        "id": 5,
        "pregunta": "¿Qué libros hay en la biblioteca?",
        "categoria": "panorama",
        "max_seg": 3.0,
        "intenciones": ["panorama_catalogo", "panorama", "buscar_semantico", "responder_con_documentos"],
        "herramientas": ["panorama_catalogo", "buscar_semantico", None],
        "contiene_alguno": ["libro", "tesis", "catalogo", "disponible", "contamos con", "ejemplar", "acervo"],
    },
    {
        "id": 6,
        "pregunta": "¿Qué libro me sugieres?",
        "categoria": "recomendar",
        "max_seg": 4.0,
        "intenciones": ["recomendar", "buscar_semantico", "presentacion", "saludo"],
        "herramientas": ["recomendar", "buscar_semantico", None],
        "contiene_alguno": ["tema", "area", "interes", "sugier", "recomiend", "programacion", "redes", "destacad", "administracion", "agroforestal", "libro"],
    },
    {
        "id": 7,
        "pregunta": "¿Cuál es el mejor libro de programación?",
        "categoria": "recomendar",
        "max_seg": 4.0,
        "intenciones": ["recomendar", "buscar_semantico", "buscar_exacto"],
        "herramientas": ["recomendar", "buscar_semantico", "buscar_exacto", None],
        "contiene_alguno": ["fundamentos de programacion", "como programar en java", "joyanes", "deitel", "programacion"],
    },
    {
        "id": 8,
        "pregunta": "Recomiéndame un libro para aprender a programar",
        "categoria": "recomendar",
        "max_seg": 4.0,
        "intenciones": ["recomendar", "buscar_semantico", "buscar_exacto"],
        "herramientas": ["recomendar", "buscar_semantico", "buscar_exacto"],
        "contiene_alguno": ["fundamentos de programacion", "como programar en java", "joyanes", "deitel", "programar", "programacion"],
        "min_materiales": 1,
    },
    {
        "id": 9,
        "pregunta": "¿Qué me recomiendas para mi tesis de agroforestería?",
        "categoria": "recomendar",
        "max_seg": 4.0,
        "intenciones": ["recomendar", "buscar_semantico", "investigacion"],
        "herramientas": ["recomendar", "buscar_semantico", "investigacion", None],
        "contiene_alguno": ["agroforesteria", "agroforestal", "sistemas agroforestales", "cacao", "arbol", "tesis", "cultivo"],
    },
    {
        "id": 10,
        "pregunta": "¿Tienen libros de inteligencia artificial?",
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["buscar_semantico", "buscar_exacto", "consultar_disponibilidad"],
        "herramientas": ["buscar_semantico", "buscar_exacto", "consultar_disponibilidad"],
        "contiene_alguno": ["russell", "norvig", "inteligencia artificial"],
    },
    {
        "id": 11,
        "pregunta": "Quiero un libro de contabilidad",
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["buscar_semantico", "buscar_exacto"],
        "herramientas": ["buscar_semantico", "buscar_exacto"],
        "contiene_alguno": ["contabilidad"],
        "min_materiales": 1,
    },
    {
        "id": 12,
        "pregunta": "¿Qué tesis hay?",
        "categoria": "panorama",
        "max_seg": 4.0,
        "intenciones": ["panorama_catalogo", "panorama", "buscar_semantico", "responder_con_documentos"],
        "herramientas": ["panorama_catalogo", "buscar_semantico", None],
        "contiene_alguno": ["tesis", "trabajos de grado", "cacao", "sacha inchi", "seguridad", "planes de negocio", "grado"],
    },
    {
        "id": 13,
        "pregunta": "¿Qué tesis hay sobre cacao?",
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["buscar_semantico", "buscar_exacto"],
        "herramientas": ["buscar_semantico", "buscar_exacto"],
        "contiene_alguno": ["cacao"],
        "min_materiales": 1,
    },
    {
        "id": 14,
        "pregunta": "¿De qué trata la tesis plan de negocios?",
        "categoria": "resumen",
        "max_seg": 4.0,
        "intenciones": ["resumir_material", "responder_con_documentos", "buscar_semantico"],
        "herramientas": ["resumir_material", "responder_con_documentos", "buscar_semantico"],
        "contiene_alguno": ["fuente", "plan de negocios", "empresa", "comercializacion", "produccion", "resumen"],
        "contiene": ["fuente"],
    },
    {
        "id": 15,
        "pregunta": "¿Cuál es el libro más prestado?",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["mas_prestados", "recomendar", "buscar_semantico", "panorama_catalogo"],
        "herramientas": ["mas_prestados", "recomendar", "buscar_semantico", None],
        "contiene_alguno": ["prestamo", "prestados", "mas prestado", "veces", "solicitado", "calculo", "redes"],
    },
    {
        "id": 16,
        "pregunta": "¿Está disponible Cálculo de una variable?",
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["consultar_disponibilidad", "buscar_exacto", "buscar_semantico"],
        "herramientas": ["consultar_disponibilidad", "buscar_exacto", "buscar_semantico"],
        "contiene_alguno": ["calculo de una variable", "disponible", "ejemplar"],
    },
    {
        "id": 17,
        "pregunta": "¿Dónde encuentro el libro Redes de computadoras?",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["ubicacion_material", "buscar_exacto", "consultar_disponibilidad", "buscar_semantico"],
        "herramientas": ["ubicacion_material", "buscar_exacto", "consultar_disponibilidad", "buscar_semantico", None],
        "contiene_alguno": ["c-06", "d-01", "estante", "sala", "ubicacion"],
    },
    {
        "id": 18,
        "pregunta": "¿Cuántos días me prestan un libro?",
        "categoria": "reglamento",
        "max_seg": 3.0,
        "intenciones": ["responder_con_documentos", "reglamento"],
        "herramientas": ["responder_con_documentos", None],
        "contiene": ["8 dias"],
        "no_comienza_con": ["renovacion", "renovaciones", "se permiten"],
        "no_contiene": ["se permiten como maximo"],
    },
    {
        "id": 19,
        "pregunta": "¿Cuánto es la multa por día?",
        "categoria": "reglamento",
        "max_seg": 3.0,
        "intenciones": ["responder_con_documentos", "reglamento"],
        "herramientas": ["responder_con_documentos", None],
        "contiene_alguno": ["1.000", "1000", "mil pesos"],
    },
    {
        "id": 20,
        "pregunta": "¿Cuál es el horario de la biblioteca?",
        "categoria": "reglamento",
        "max_seg": 3.0,
        "intenciones": ["responder_con_documentos", "reglamento"],
        "herramientas": ["responder_con_documentos", None],
        "contiene_alguno": ["lunes", "viernes", "horario", "atencion", "8:00", "7:00", "p. m.", "pm"],
    },
    {
        "id": 21,
        "pregunta": "¿Cuántos libros puedo sacar a la vez?",
        "categoria": "reglamento",
        "max_seg": 3.0,
        "intenciones": ["responder_con_documentos", "reglamento"],
        "no_intenciones": ["buscar_semantico"],
        "herramientas": ["responder_con_documentos", None],
        "no_herramientas": ["buscar_semantico"],
        "contiene_alguno": ["3", "tres", "libros", "ejemplares"],
    },
    {
        "id": 22,
        "pregunta": "¿Cómo cito un libro en APA?",
        "categoria": "reglamento",
        "max_seg": 3.0,
        "intenciones": ["responder_con_documentos", "citacion", "generar_bibliografia"],
        "herramientas": ["responder_con_documentos", None],
        "contiene_alguno": ["fuente", "apellido", "ano", "editorial", "autor", "apa", "titulo"],
    },
    {
        "id": 23,
        "pregunta": "Dame 3 referencias en APA sobre marketing",
        "categoria": "citacion",
        "max_seg": 4.0,
        "intenciones": ["generar_bibliografia"],
        "herramientas": ["generar_bibliografia"],
        "contiene_alguno": ["kotler", "marketing"],
    },
    {
        "id": 24,
        "pregunta": "¿Qué salas hay?",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["elegir_sala", "responder_con_documentos", "saludo", "panorama_catalogo"],
        "herramientas": [None, "elegir_sala", "responder_con_documentos"],
        "contiene_alguno": ["ingenieria", "agrarias", "administracion", "contaduria", "investigacion", "salas", "sala"],
    },
    {
        "id": 25,
        "pregunta": "¿Tengo multas?",
        "categoria": "tramites",
        "max_seg": 3.0,
        "intenciones": ["consultar_prestamos_y_multas"],
        "herramientas": ["consultar_prestamos_y_multas", None],
        "contiene_alguno": ["5.000", "5000", "multa"],
    },
    {
        "id": 26,
        "pregunta": "¿Qué libros tengo prestados?",
        "categoria": "tramites",
        "max_seg": 3.0,
        "intenciones": ["consultar_prestamos_y_multas"],
        "herramientas": ["consultar_prestamos_y_multas"],
        "contiene_alguno": ["fundamentos de seguridad en redes", "seguridad en redes"],
    },
    {
        "id": 27,
        "pregunta": "Renueva mi préstamo",
        "categoria": "tramites",
        "max_seg": 3.0,
        "intenciones": ["renovar_prestamo"],
        "herramientas": ["renovar_prestamo"],
        "contiene_alguno": ["no se puede renovar", "no puede renovar", "multa", "vencido", "sancion"],
    },
    {
        "id": 28,
        "pregunta": "Gracias",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["cortesia", "saludo", "despedida"],
        "herramientas": [None, "cortesia"],
        "contiene_alguno": ["con gusto", "un placer", "a la orden", "de nada", "para servirte", "ayudar", "orden"],
    },
    {
        "id": 29,
        "pregunta": "Adiós",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["cortesia", "despedida", "saludo"],
        "herramientas": [None, "cortesia", "despedida"],
        "contiene_alguno": ["hasta luego", "adios", "que tengas", "buen dia", "pronto", "volver"],
    },
    {
        "id": 30,
        "pregunta": "¿Cuál es la capital de Francia?",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["fuera_de_dominio"],
        "herramientas": [None],
        "contiene_alguno": ["fuera de mi dominio", "biblioteca", "solo puedo", "no puedo", "asuntos relacionados"],
    },
    {
        "id": 31,
        "pregunta": "¿Dónde encuentro el libro Redes de computadoras?",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["ubicacion_material"],
        "herramientas": ["ubicacion_material", None],
        "contiene_alguno": ["c-06", "d-01"],
        "no_contiene": ["a cual te refieres", "varias coincidencias"],
    },
    {
        "id": 32,
        "pregunta": "¿Dónde está «Contabilidad de costos»?",
        "sala": "ingenieria",
        "sala_esperada": "ingenieria",
        "categoria": "determinista",
        "max_seg": 3.0,
        "intenciones": ["ubicacion_material"],
        "herramientas": ["ubicacion_material", None],
        "contiene": ["contaduria y finanzas"],
        "no_contiene": ["no encontre ese material"],
    },
    {
        "id": 33,
        "pregunta": "Muéstrame más de «plan de negocios»",
        "categoria": "busqueda",
        "max_seg": 3.0,
        "intenciones": ["buscar_exacto", "ficha_material"],
        "herramientas": ["buscar_exacto", "ficha_material", None],
        "contiene_alguno": ["ficha", "autor", "administracion", "opciones", "programa"],
        "no_contiene": ["no encontre coincidencias"],
    },
    {
        "id": 34,
        "pregunta": "no",
        "previa": "Quiero reservar Cálculo",
        "categoria": "determinista",
        "max_seg": 1.5,
        "intenciones": ["cancelar_accion"],
        "herramientas": [None, "cancelar_accion"],
        "contiene_alguno": ["lo dejamos asi", "de acuerdo", "cancel"],
    },
    {
        "id": 35,
        "pregunta": "Quiero reservar «plan de negocios»",
        "sala": "ingenieria",
        "sala_esperada": "ingenieria",
        "mantener_accion_pendiente": True,
        "requiere_accion_pendiente": True,
        "categoria": "tramites",
        "max_seg": 3.0,
        "intenciones": ["reservar"],
        "herramientas": ["reservar"],
        "contiene_alguno": ["confirmo la reserva", "reserva de", "plan de negocios"],
        "no_contiene": ["soy camilo", "sala de administracion y negocios"],
    },
    {
        "id": 36,
        "pregunta": "Quiero un libro de contabilidad",
        "sala": "ingenieria",
        "sala_esperada": "ingenieria",
        "sugerencia_sala_esperada": "contaduria",
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["buscar_semantico", "buscar_exacto"],
        "herramientas": ["buscar_semantico", "buscar_exacto"],
        "contiene": ["contaduria y finanzas"],
        "no_contiene": ["calculo", "cálculo"],
    },
    {
        "id": 37,
        "pregunta": "Libros de marketing",
        "sala": "ingenieria",
        "sala_esperada": "ingenieria",
        "sugerencia_sala_esperada": "administracion",
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["buscar_semantico", "buscar_exacto"],
        "herramientas": ["buscar_semantico", "buscar_exacto"],
        "contiene": ["administracion y negocios"],
    },
    {
        "id": 38,
        "pregunta": "Libros de redes",
        "sala": "agro-ambiental",
        "sala_esperada": "agro-ambiental",
        "sugerencia_sala_esperada": "ingenieria",
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["buscar_semantico", "buscar_exacto"],
        "herramientas": ["buscar_semantico", "buscar_exacto"],
        "contiene": ["ingenieria y tecnologia"],
    },
    {
        "id": 39,
        "pregunta": "Libros de redes",
        "sala": "ingenieria",
        "sala_esperada": "ingenieria",
        "sugerencia_sala_esperada": None,
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["buscar_semantico", "buscar_exacto"],
        "herramientas": ["buscar_semantico", "buscar_exacto"],
        "contiene": ["redes de computadoras"],
    },
    {
        "id": 40,
        "pregunta": "Quiero un libro de contaminación ambiental",
        "sala": "ingenieria",
        "sala_esperada": "ingenieria",
        "sugerencia_sala_valida": ["agro-ambiental", None],
        "categoria": "busqueda",
        "max_seg": 4.0,
        "intenciones": ["buscar_semantico", "buscar_exacto"],
        "herramientas": ["buscar_semantico", "buscar_exacto"],
        "contiene_alguno": [
            "ciencias agrarias y ambientales",
            "no encontre material sobre contaminacion ambiental",
            "no encontre material sobre ese tema",
        ],
        "no_contiene": ["calculo", "cálculo", "bases de datos", "inteligencia artificial"],
    },
]


@dataclass
class ResultadoPregunta:
    caso: dict[str, Any]
    duracion_seg: float
    pasa: bool
    intencion: str
    herramienta: str | None
    respuesta: str
    motivos_fallo: list[str]


def evaluar_respuesta(caso: dict[str, Any], datos: dict[str, Any], duracion_seg: float, tolerancia: float = 1.0) -> ResultadoPregunta:
    """Verifica tiempo, intención, herramienta y contenido esperado de una respuesta."""
    motivos_fallo: list[str] = []

    # 1. Comprobación de tiempo máximo
    tiempo_max = caso["max_seg"] * tolerancia
    if duracion_seg > tiempo_max:
        motivos_fallo.append(f"Tiempo excedido: {duracion_seg:.2f} s > {tiempo_max:.2f} s")

    # 2. Comprobación de intención
    intencion_real = limpiar_intencion(datos.get("intencion"))
    intenciones_validas = [limpiar_intencion(i) for i in caso.get("intenciones", [])]
    no_intenciones = [limpiar_intencion(i) for i in caso.get("no_intenciones", [])]

    if intenciones_validas and intencion_real not in intenciones_validas:
        motivos_fallo.append(f"Intención inesperada: '{intencion_real}' no está en {intenciones_validas}")
    if no_intenciones and intencion_real in no_intenciones:
        motivos_fallo.append(f"Intención prohibida: '{intencion_real}' está en {no_intenciones}")

    # 3. Comprobación de herramienta
    herramienta_real = datos.get("herramienta")
    herramientas_validas = caso.get("herramientas")
    no_herramientas = caso.get("no_herramientas", [])

    es_caso_determinista = caso.get("categoria") in ("determinista", "cortesia", "saludo", "presentacion")
    herramienta_es_valida = (
        herramientas_validas is None
        or herramienta_real in herramientas_validas
        or (es_caso_determinista and (herramienta_real is None or herramienta_real == intencion_real))
    )

    if not herramienta_es_valida:
        motivos_fallo.append(f"Herramienta inesperada: '{herramienta_real}' no está en {herramientas_validas}")
    if no_herramientas and herramienta_real in no_herramientas:
        motivos_fallo.append(f"Herramienta prohibida: '{herramienta_real}' está en {no_herramientas}")

    # 4. Comprobación de contenido
    respuesta = str(datos.get("respuesta") or "")
    respuesta_norm = normalizar(respuesta)

    for prefijo in caso.get("no_comienza_con", []):
        if respuesta_norm.startswith(normalizar(prefijo)):
            motivos_fallo.append(f"Respuesta no debe comenzar con: '{prefijo}'")

    if caso.get("requiere_accion_pendiente") and not datos.get("accion_pendiente"):
        motivos_fallo.append("Se requería una accion_pendiente activa y no se encontró.")

    if caso.get("sala_esperada"):
        sala_actual_slug = (datos.get("sala") or {}).get("slug") if isinstance(datos.get("sala"), dict) else datos.get("sala")
        if sala_actual_slug != caso["sala_esperada"]:
            motivos_fallo.append(f"Sala esperada '{caso['sala_esperada']}', pero la respuesta tiene '{sala_actual_slug}'")

    if "sugerencia_sala_esperada" in caso:
        esperada = caso["sugerencia_sala_esperada"]
        sug_actual = datos.get("sugerencia_sala")
        sug_slug = sug_actual.get("slug") if isinstance(sug_actual, dict) else sug_actual
        if esperada is None and sug_slug is not None:
            motivos_fallo.append(f"No se esperaba sugerencia_sala, pero se recibió '{sug_slug}'")
        elif esperada is not None and sug_slug != esperada:
            motivos_fallo.append(f"sugerencia_sala esperada '{esperada}', pero se recibió '{sug_slug}'")

    if "sugerencia_sala_valida" in caso:
        validas = caso["sugerencia_sala_valida"]
        sug_actual = datos.get("sugerencia_sala")
        sug_slug = sug_actual.get("slug") if isinstance(sug_actual, dict) else sug_actual
        if sug_slug not in validas:
            motivos_fallo.append(f"sugerencia_sala '{sug_slug}' no está entre las opciones válidas {validas}")

    for fragmento in caso.get("contiene", []):
        if normalizar(fragmento) not in respuesta_norm:
            motivos_fallo.append(f"Falta fragmento obligatorio: '{fragmento}'")

    for fragmento in caso.get("no_contiene", []):
        if normalizar(fragmento) in respuesta_norm:
            motivos_fallo.append(f"Aparece fragmento prohibido: '{fragmento}'")

    algunos = caso.get("contiene_alguno", [])
    if algunos and not any(normalizar(f) in respuesta_norm for f in algunos):
        motivos_fallo.append(f"No contiene ninguno de los términos esperados: {algunos[:3]}...")

    min_mat = caso.get("min_materiales", 0)
    materiales = datos.get("materiales") or []
    if min_mat > 0 and len(materiales) < min_mat:
        motivos_fallo.append(f"Mínimo de materiales no alcanzado: {len(materiales)} < {min_mat}")

    patron_regex = caso.get("regex")
    if patron_regex and not re.search(patron_regex, respuesta, re.IGNORECASE):
        motivos_fallo.append(f"No cumple patrón regex '{patron_regex}'")

    pasa = len(motivos_fallo) == 0
    return ResultadoPregunta(
        caso=caso,
        duracion_seg=duracion_seg,
        pasa=pasa,
        intencion=datos.get("intencion") or "ninguna",
        herramienta=herramienta_real,
        respuesta=respuesta,
        motivos_fallo=motivos_fallo,
    )


def ejecutar_bateria(cliente: Any, casos: list[dict[str, Any]], misma_conversacion: bool = False, tolerancia: float = 1.0) -> list[ResultadoPregunta]:
    """Ejecuta los turnos enviando consultas a la API del agente."""
    # Login obligatorio con usuario demo 102 (Mariana Rosero Burbano)
    resp_login = cliente.post("/api/login", json={"codigo": "102", "pin": "1234"})
    if resp_login.status_code != 200:
        raise RuntimeError(f"Error al autenticar usuario 102: status={resp_login.status_code}, texto={resp_login.text}")

    resultados: list[ResultadoPregunta] = []
    conversacion_id: str | None = None

    for indice, caso in enumerate(casos):
        # Nueva conversación cada 8 preguntas para evitar sesgos por acumulación de historial
        if not misma_conversacion and indice > 0 and (indice % 8 == 0):
            conversacion_id = None

        sala_caso = caso.get("sala")
        if sala_caso and not misma_conversacion:
            conversacion_id = None

        if caso.get("previa"):
            resp_prev = cliente.post(
                "/api/chat",
                json={
                    "texto": caso["previa"],
                    "conversacion_id": conversacion_id,
                    "con_audio": False,
                    "sala": sala_caso,
                },
            )
            if resp_prev.status_code == 200:
                conversacion_id = resp_prev.json().get("conversacion_id") or conversacion_id

        payload_chat = {
            "texto": caso["pregunta"],
            "conversacion_id": conversacion_id,
            "con_audio": False,
        }
        if sala_caso:
            payload_chat["sala"] = sala_caso

        t_inicio = perf_counter()
        resp_chat = cliente.post(
            "/api/chat",
            json=payload_chat,
        )
        duracion = perf_counter() - t_inicio

        if resp_chat.status_code != 200:
            datos_erroneos = {
                "intencion": "error_http",
                "herramienta": None,
                "respuesta": f"HTTP {resp_chat.status_code}: {resp_chat.text}",
            }
            res = ResultadoPregunta(
                caso=caso,
                duracion_seg=duracion,
                pasa=False,
                intencion="error_http",
                herramienta=None,
                respuesta=datos_erroneos["respuesta"],
                motivos_fallo=[f"Respuesta HTTP {resp_chat.status_code}"],
            )
            resultados.append(res)
            continue

        datos = resp_chat.json()
        conversacion_id = datos.get("conversacion_id") or conversacion_id

        # Evaluar la respuesta contra los criterios declarados
        res = evaluar_respuesta(caso, datos, duracion, tolerancia=tolerancia)
        resultados.append(res)

        # Si el turno generó una acción pendiente, cancelarla inmediatamente con 'no'
        if datos.get("accion_pendiente") and not caso.get("mantener_accion_pendiente"):
            try:
                cliente.post(
                    "/api/chat",
                    json={
                        "texto": "no",
                        "conversacion_id": conversacion_id,
                        "con_audio": False,
                        "sala": sala_caso,
                    },
                )
            except Exception:
                pass

    return resultados


def imprimir_reporte(resultados: list[ResultadoPregunta]) -> bool:
    """Imprime la tabla formateada y el resumen cuantitativo."""
    ancho = 118
    print("=" * ancho)
    print(f"{'#':<3} {'Tiempo':<8} {'Meta':<6} {'Estado':<6} {'Intención':<22} {'Pregunta y respuesta recortada'}")
    print("=" * ancho)

    lentas: list[ResultadoPregunta] = []
    fallidas: list[ResultadoPregunta] = []
    tiempos: list[float] = []

    for r in resultados:
        tiempos.append(r.duracion_seg)
        meta_str = f"≤{r.caso['max_seg']:.1f}s"
        tiempo_str = f"{r.duracion_seg:.2f}s"
        estado_simbolo = "✓" if r.pasa else "✗"
        intencion_corta = (r.intencion[:20] + "..") if len(r.intencion) > 22 else r.intencion

        # Preparar texto compacto en una sola línea
        resp_limpia = " ".join(r.respuesta.split())
        if len(resp_limpia) > 55:
            resp_limpia = resp_limpia[:52] + "..."
        pregunta_corta = r.caso["pregunta"]
        if len(pregunta_corta) > 30:
            pregunta_corta = pregunta_corta[:27] + "..."

        detalle_linea = f"[{pregunta_corta}] {resp_limpia}"
        print(f"{r.caso['id']:<3} {tiempo_str:<8} {meta_str:<6} {estado_simbolo:<6} {intencion_corta:<22} {detalle_linea}")

        if r.duracion_seg > r.caso["max_seg"]:
            lentas.append(r)
        if not r.pasa:
            fallidas.append(r)

    total = len(resultados)
    aprobadas = total - len(fallidas)
    promedio = sum(tiempos) / total if total > 0 else 0.0

    print("=" * ancho)
    print("Resumen de la prueba permanente:")
    print(f"  • Total preguntas evaluadas : {total}")
    print(f"  • Tiempo promedio de turno  : {promedio:.2f} s (meta institucional: < 4.0 s)")
    print(f"  • Preguntas lentas (> meta) : {len(lentas)}")

    if lentas:
        print("    Detalle de lentas:")
        for l in lentas:
            print(f"      - #{l.caso['id']:02d} «{l.caso['pregunta']}»: {l.duracion_seg:.2f}s (meta ≤ {l.caso['max_seg']}s)")

    if fallidas:
        print(f"  • Preguntas con fallos      : {len(fallidas)}")
        for f in fallidas:
            print(f"      - #{f.caso['id']:02d} «{f.caso['pregunta']}»:")
            for motivo in f.motivos_fallo:
                print(f"          ✗ {motivo}")

    meta_promedio_cumplida = promedio < 4.0
    todo_pasa = (len(fallidas) == 0) and meta_promedio_cumplida

    print("-" * ancho)
    print(f"Resultado final: {aprobadas}/{total} PASA" + (" (ÉXITO TOTAL)" if todo_pasa else " (FALLOS DETECTADOS)"))
    print("=" * ancho)

    return todo_pasa


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba permanente de preguntas típicas con límites de latencia.")
    parser.add_argument(
        "--servidor",
        nargs="?",
        const="http://127.0.0.1:8000",
        default=None,
        help="Dirección del servidor HTTP en ejecución (por defecto http://127.0.0.1:8000 si se omite el valor).",
    )
    parser.add_argument(
        "--misma-conversacion",
        action="store_true",
        help="Mantiene la misma conversación a lo largo de las 30 preguntas para medir el peor caso.",
    )
    parser.add_argument(
        "--solo",
        type=str,
        default=None,
        help="Filtra y ejecuta únicamente las preguntas que contengan este texto.",
    )
    parser.add_argument(
        "--sin-refresco",
        action="store_true",
        help="Omite la sincronización de refrescar_demo() antes de iniciar.",
    )
    parser.add_argument(
        "--tolerancia",
        type=float,
        default=1.0,
        help="Factor multiplicador para el tiempo máximo de cada pregunta (por defecto 1.0).",
    )
    args = parser.parse_args()

    # Sincronización inicial del estado de demo del usuario 102
    if not args.sin_refresco:
        try:
            from refrescar_demo import refrescar_demo
            refrescar_demo()
        except Exception as error:
            print(f"[aviso] No se pudo ejecutar refrescar_demo(): {error}", file=sys.stderr)

    # Filtrar casos si se especificó --solo
    casos = CASOS_PREGUNTAS_TIPICAS
    if args.solo:
        filtro = normalizar(args.solo)
        casos = [c for c in casos if filtro in normalizar(c["pregunta"])]
        if not casos:
            print(f"No se encontraron preguntas que coincidan con '{args.solo}'.", file=sys.stderr)
            sys.exit(1)

    # Selección de cliente (httpx contra servidor remoto o TestClient in-process)
    if args.servidor:
        import httpx
        url_base = args.servidor.rstrip("/")
        print(f"Ejecutando pruebas contra servidor HTTP: {url_base}...")
        with httpx.Client(base_url=url_base, timeout=90.0) as cliente:
            resultados = ejecutar_bateria(cliente, casos, misma_conversacion=args.misma_conversacion, tolerancia=args.tolerancia)
    else:
        from fastapi.testclient import TestClient
        from app.main import app
        print("Ejecutando pruebas in-process con TestClient(app)...")
        with TestClient(app) as cliente:
            resultados = ejecutar_bateria(cliente, casos, misma_conversacion=args.misma_conversacion, tolerancia=args.tolerancia)

    todo_ok = imprimir_reporte(resultados)
    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()
