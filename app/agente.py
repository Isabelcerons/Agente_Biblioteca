"""Gestor conversacional del agente de biblioteca."""

import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from time import perf_counter
from typing import Any
from uuid import UUID

import ollama

from app import herramientas, auth, salas
from app.numeros import extraer_codigo, extraer_pin, palabras_a_numero, pin_explicito
from app.consultas import normalizar_consulta
from app.config import (
    KEEP_ALIVE,
    LLM_MODEL,
    LLM_MODEL_RESPALDO,
    LLM_MODEL_REDACCION,
    NUM_CTX,
    NUM_PREDICT,
    NUM_PREDICT_TOOL_CALLING,
    NUM_PREDICT_REDACCION,
    OLLAMA_HOST,
)
from app.db import conexion
from app.formatos import fecha_es, pesos

_CLIENTE = ollama.Client(host=OLLAMA_HOST)
_AFIRMATIVOS = {"si", "sí", "confirmo", "dale", "de acuerdo", "claro", "ok", "hagalo", "hágalo"}
_NEGATIVOS = {"no", "cancela", "cancelar", "mejor no"}
_HERRAMIENTAS = {
    "consultar_recogida",
    "buscar_semantico",
    "resumir_material",
    "buscar_exacto",
    "consultar_disponibilidad",
    "reservar",
    "cancelar_reserva",
    "renovar_prestamo",
    "consultar_prestamos_y_multas",
    "responder_con_documentos",
    "generar_bibliografia",
    "presentacion",
    "cortesia",
    "panorama_catalogo",
    "mas_prestados",
    "ubicacion_material",
    "recomendar",
}

TOOLS = [
    {"type": "function", "function": {"name": "consultar_recogida", "description": "Consulta cuándo recoger o retirar las reservas propias del usuario.", "parameters": {"type": "object", "properties": {"titulo": {"type": "string"}}}}},
    {
        "type": "function",
        "function": {
            "name": "buscar_semantico",
            "description": "Busca por tema o recomienda bibliografía.",
            "parameters": {
                "type": "object",
                "properties": {"consulta": {"type": "string"}},
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumir_material",
            "description": "Resume un libro desde su reseña disponible o una tesis desde su resumen y páginas del PDF.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "pregunta": {"type": "string"},
                },
                "required": ["titulo", "pregunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancelar_reserva",
            "description": "Cancela una reserva activa del usuario identificado.",
            "parameters": {
                "type": "object",
                "properties": {"titulo": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generar_bibliografia",
            "description": "Arma una lista de referencias bibliográficas (bibliografía) en APA o IEEE sobre un tema con material del acervo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tema": {"type": "string"},
                    "cantidad": {"type": "integer", "minimum": 1, "maximum": 15},
                    "norma": {"type": "string", "enum": ["APA", "IEEE"]},
                },
                "required": ["tema"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_exacto",
            "description": "Busca un título o autor concreto.",
            "parameters": {
                "type": "object",
                "properties": {"texto": {"type": "string"}},
                "required": ["texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidad",
            "description": "Consulta la disponibilidad de un título; el sistema resuelve el material.",
            "parameters": {
                "type": "object",
                "properties": {"titulo": {"type": "string"}},
                "required": ["titulo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reservar",
            "description": "Prepara una reserva para confirmación explícita.",
            "parameters": {
                "type": "object",
                "properties": {"titulo": {"type": "string"}},
                "required": ["titulo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "renovar_prestamo",
            "description": "Prepara la renovación de un préstamo del usuario.",
            "parameters": {
                "type": "object",
                "properties": {"titulo": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_prestamos_y_multas",
            "description": "Consulta los préstamos, multas y reservas del usuario identificado.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "responder_con_documentos",
            "description": "Consulta reglamento, citación APA/IEEE, bases de datos y preguntas frecuentes.",
            "parameters": {
                "type": "object",
                "properties": {"pregunta": {"type": "string"}},
                "required": ["pregunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "presentacion",
            "description": "Presenta al agente de biblioteca y explica los servicios y salas disponibles.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cortesia",
            "description": "Responde con cortesía breve ante saludos, agradecimientos o despedidas.",
            "parameters": {
                "type": "object",
                "properties": {"tipo": {"type": "string", "enum": ["gracias", "despedida"]}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "panorama_catalogo",
            "description": "Ofrece un panorama general del acervo con totales por sala y títulos destacados.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mas_prestados",
            "description": "Consulta los libros y materiales con mayor número de préstamos en el catálogo.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ubicacion_material",
            "description": "Indica el estante físico y disponibilidad de un libro o material en la biblioteca.",
            "parameters": {
                "type": "object",
                "properties": {"titulo": {"type": "string"}},
                "required": ["titulo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recomendar",
            "description": "Recomienda libros o materiales del catálogo según afinidad temática o popularidad.",
            "parameters": {
                "type": "object",
                "properties": {"tema": {"type": "string"}},
            },
        },
    },
]


def _normalizar(texto: str) -> str:
    """Normaliza tildes y mayúsculas para comparar intenciones."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(caracter for caracter in descompuesto if unicodedata.category(caracter) != "Mn")


def _extraer_peticion_bibliografia(texto: str) -> dict[str, Any] | None:
    """Reconoce peticiones de construcción y separa tema, norma y cantidad."""
    normalizado = _normalizar(texto)
    if re.match(r"^\s*¿?\s*como\b", normalizado):
        return None

    nombre = re.search(r"\b(?:bibliograf\w*|referencias?)\b", normalizado)
    if not nombre:
        return None
    tiene_norma = bool(re.search(r"\b(?:apa|ieee)\b", normalizado))
    verbo_generador = bool(
        re.search(
            r"\b(?:genera\w*|arma\w*|haz\w*|hace\w*|dame|da|darme|"
            r"prepara\w*|elabora\w*|construye\w*|crea\w*)\b",
            normalizado,
        )
    )
    pide_lista = bool(re.search(r"\blista\s+de\s+referencias\b", normalizado))
    if not (verbo_generador or pide_lista or tiene_norma):
        return None

    norma = "IEEE" if re.search(r"\bieee\b", normalizado) else "APA"
    cantidades = {
        "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
        "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
        "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
        "quince": 15,
    }
    cantidad = 5
    cantidad_match = re.search(
        r"\b(\d+|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|"
        r"nueve|diez|once|doce|trece|catorce|quince)\b"
        r"\s+(?:referencias?|fuentes?|entradas)\b",
        normalizado,
    )
    if cantidad_match:
        token = cantidad_match.group(1)
        cantidad = min(15, max(1, int(token) if token.isdigit() else cantidades[token]))

    original_nombre = re.search(
        r"\b(?:bibliograf\w*|referencias?)\b", texto, re.IGNORECASE
    )
    tema = ""
    if original_nombre:
        separador = re.search(
            r"\b(?:sobre|acerca\s+de|para|de)\b",
            texto[original_nombre.end():],
            re.IGNORECASE,
        )
        if separador:
            inicio_tema = original_nombre.end() + separador.end()
            tema = texto[inicio_tema:]
        else:
            tema = texto[original_nombre.end():]

    tema = re.sub(
        r"\b(?:en\s+formato\s+|formato\s+)?(?:APA|IEEE)\b",
        " ",
        tema,
        flags=re.IGNORECASE,
    )
    tema = re.sub(
        r"\b(?:\d+|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|"
        r"nueve|diez|once|doce|trece|catorce|quince)"
        r"(?:\s+(?:referencias?|fuentes?|entradas))?\b",
        " ",
        tema,
        flags=re.IGNORECASE,
    )
    tema = re.sub(
        r"\b(?:por\s+favor|bibliograficas?|referencias?|lista|formato)\b",
        " ",
        tema,
        flags=re.IGNORECASE,
    )
    tema = re.sub(r"\s+", " ", tema).strip(" \t\r\n.,;:!?¿¡«»\"'")
    if not tema:
        return None
    return {"tema": tema, "cantidad": cantidad, "norma": norma}


def _es_pregunta_identidad(texto: str) -> bool:
    """Detecta preguntas sobre la identidad y capacidades del agente."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    patrones = (
        r"\b(?:quien|que)\s+eres\b",
        r"\bcomo\s+te\s+llamas\b",
        r"\bcual\s+es\s+tu\s+nombre\b",
        r"\bcon\s+quien\s+hablo\b",
        r"\bque\s+(?:puedes|sabes)\s+hacer\b",
        r"\ben\s+que\s+me\s+puedes\s+ayudar\b",
        r"\bpara\s+que\s+sirves\b",
        r"\bque\s+servicios\s+(?:prestas|ofreces|tienen)\b",
        r"\bcuales\s+son\s+tus\s+funciones\b",
        r"\bcomo\s+me\s+puedes\s+ayudar\b",
        r"\bcomo\s+funcionas\b",
        r"^que\s+haces$",
    )
    return any(re.search(patron, normal) for patron in patrones)


def _es_cortesia(texto: str) -> tuple[bool, str]:
    """Detecta agradecimientos y despedidas habituales."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    if re.fullmatch(r"(?:muchas\s+|muchisimas\s+|mil\s+)?gracias(?:\s+a\s+ti|\s+por\s+todo|\s+amigo|\s+asistente)?", normal):
        return True, "gracias"
    if re.fullmatch(r"te\s+agradezco(?:\s+mucho)?", normal):
        return True, "gracias"
    if re.fullmatch(r"(?:adios|chao|hasta\s+luego|hasta\s+pronto|nos\s+vemos|hasta\s+la\s+proxima)(?:\s+gracias)?", normal):
        return True, "despedida"
    if re.fullmatch(r"(?:que\s+tengas|feliz)\s+(?:buen\s+dia|un\s+buen\s+dia|feliz\s+dia|tarde|noche)", normal):
        return True, "despedida"
    return False, ""


def _es_panorama_catalogo(texto: str) -> bool:
    """Detecta si se pide un panorama o visión general del catálogo."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    patrones = (
        r"^(?:que|cuales)\s+libros\s+(?:tienes?|hay|tienen)\b",
        r"^(?:que|cual|cuales)\s+(?:material|materiales|acervo|titulos|obras)\s+(?:tienes?|hay|tienen)\b",
        r"^que\s+tienes?\b",
        r"^que\s+hay\s+en\s+la\s+biblioteca\b",
        r"^(?:mostrar|ver|consultar|dame|muestra)\s+(?:el\s+)?catalogo\b",
        r"^catalogo(?:\s+general)?$",
        r"^que\s+puedo\s+leer\b",
        r"^con\s+que\s+libros\s+cuentan\b",
    )
    return any(re.search(patron, normal) for patron in patrones)


def _es_mas_prestados(texto: str) -> bool:
    """Detecta si se pregunta por los libros más prestados o populares."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    return bool(re.search(
        r"\b(?:libro|libros|material|materiales|obra|obras)?\s*"
        r"(?:mas\s+prestados?|mas\s+populares?|mas\s+pedidos?|mas\s+leidos?|mas\s+solicitados?)\b|"
        r"\bcual(?:es)?\s+es\s+el\s+(?:libro\s+)?mas\s+prestado\b",
        normal
    ))


def _extraer_peticion_ubicacion(texto: str) -> tuple[bool, str | None]:
    """Detecta si se pregunta por el estante o ubicación de un material concreto."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    match = re.search(
        r"\b(?:donde\s+(?:encuentro|esta|ubico|queda|se\s+encuentra)|en\s+que\s+estante\s+esta)\s+(?:el\s+libro\s+|la\s+tesis\s+|el\s+material\s+|el\s+ejemplar\s+|el\s+|la\s+)?(.+)",
        normal
    )
    if not match:
        if re.search(r"\b(?:estante|ubicacion)\s+(?:de|del)\b", normal):
            sub = re.search(r"\b(?:estante|ubicacion)\s+(?:de|del)\s+(.+)", texto, re.I)
            if sub:
                return True, _titulo_material(sub.group(1))
        return False, None
    comillas = re.search(r"[«“\"']([^»”\"']+)[»”\"']", texto)
    if comillas and comillas.group(1).strip():
        return True, comillas.group(1).strip().strip("¿?¡!.,:;")
    titulo_candidato = _titulo_material(texto)
    titulo_limpio = re.sub(
        r"(?i)^(?:d[oó]nde\s+(?:encuentro|est[aá]|ubico|queda|se\s+encuentra)|en\s+qu[eé]\s+estante\s+est[aá]|cu[aá]l\s+es\s+la\s+ubicaci[oó]n\s+de)\s*",
        "",
        titulo_candidato
    )
    titulo_limpio = re.sub(r"(?i)^(?:el\s+libro\s+|la\s+tesis\s+|el\s+material\s+|el\s+|la\s+)", "", titulo_limpio).strip(" ¿?!¡.,:;")
    return True, titulo_limpio


def _extraer_peticion_recomendacion(texto: str) -> tuple[bool, str | None]:
    """Detecta si se pide una recomendación, separando el tema si existe."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    es_recomendacion = bool(re.search(
        r"\b(?:recomi[eé]nda(?:me|r)?|sugi[eé]re(?:me|r)?|cual\s+es\s+el\s+mejor\b|que\s+libro\s+me\s+(?:sugieres|recomiendas))\b",
        normal
    ))
    if not es_recomendacion:
        return False, None
    # Ver si hay un tema específico
    tema_match = re.search(
        r"\b(?:de|sobre|en|para)\s+([a-zA-ZáéíóúñÁÉÍÓÚÑ\s]{3,})$",
        texto.strip(" ¿?!¡.,:;"),
        re.I
    )
    if tema_match:
        tema_candidato = tema_match.group(1).strip()
        tema_norm = _normalizar(tema_candidato)
        if tema_norm in ("leer", "estudiar", "la biblioteca", "el catalogo", "hoy", "manana", "un libro", "un buen libro", "los libros"):
            return True, None
        return True, tema_candidato
    return True, None


def intencion_por_palabras(texto: str) -> str:
    """Elige una herramienta según patrones deterministas con alta confianza."""
    normalizado = _normalizar(texto)

    # Identidad y cortesía
    if _es_pregunta_identidad(texto):
        return "presentacion"
    cortesia_val, _ = _es_cortesia(texto)
    if cortesia_val:
        return "cortesia"

    # Panorama y popularidad en catálogo
    if _es_panorama_catalogo(texto):
        return "panorama_catalogo"
    if _es_mas_prestados(texto):
        return "mas_prestados"

    # Ubicación y estantes
    es_ubicacion, _ = _extraer_peticion_ubicacion(texto)
    if es_ubicacion:
        return "ubicacion_material"

    # Recomendaciones (con o sin tema)
    es_recom, _ = _extraer_peticion_recomendacion(texto)
    if es_recom:
        return "recomendar"

    # Préstamos y cuenta del usuario: "¿Qué libros tengo prestados?", "mis préstamos"
    if re.search(
        r"\b(?:que\s+libros?\s+tengo\s+prestados?|que\s+tengo\s+prestado|libros?\s+que\s+tengo\s+prestados?|cuales\s+son\s+mis\s+prestamos|mis\s+prestamos|mis\s+libros\s+prestados)\b",
        normalizado,
    ):
        return "consultar_prestamos_y_multas"

    # Reglamento: "¿Cuántos libros puedo sacar a la vez?"
    if re.search(
        r"\b(?:cuantos?|cuantas?)\s+(?:libros?|ejemplares|materiales|tesis)?\s*(?:puedo|se\s+pueden?)\s*(?:sacar|prestar|pedir|llevar|tener)\b",
        normalizado,
    ):
        return "responder_con_documentos"

    if re.search(r"\b(como|donde)\b.*\b(pag(?:o|ar|a)|pagar)\b.*\bmultas?\b", normalizado):
        return "responder_con_documentos"
    if re.fullmatch(r"(?:(?:quiero|puedo)\s+(?:ver|consultar)\s+)?mis reservas[ .!?¿¡]*", normalizado):
        return "consultar_prestamos_y_multas"
    if re.search(r"\b(recoger|retirar)\b", normalizado):
        if re.search(r"\b(cuantas horas|cuantos dias|cuanto tiempo|plazo|horario)\b", normalizado) or (
            re.search(r"\ba que hora\b", normalizado)
            and not re.search(r"\b(mi|mis)\s+(reserva|reservas|libro|libros)\b", normalizado)
        ):
            return "responder_con_documentos"
        return "consultar_recogida"
    if re.search(r"\b(a que hora|cuando)\s+(abren|cierran|abre|cierra)\b", normalizado):
        return "responder_con_documentos"
    if re.search(
        r"cancel(a|ar|e|o)?.*reserv|anul(a|ar).*reserv|"
        r"ya no (quiero|necesito).*reserv|quit(a|ar).*reserv|"
        r"elimin(a|ar).*reserv",
        normalizado,
    ):
        return "cancelar_reserva"
    # Preguntas SOBRE las normas ("¿cuántas veces puedo renovar?", "¿cuánto dura una reserva?")
    # van al reglamento, no al trámite. "¿Puedo renovar MI préstamo?" sigue siendo trámite.
    if re.search(
        r"\b(cuantas veces|cuantos dias|cuantas horas|cuanto tiempo|cuanto dura|"
        r"cuanto cuesta|como funciona|que pasa si|cada cuanto|hasta cuando se)\b",
        normalizado,
    ):
        return "responder_con_documentos"
    if re.search(
        r"\b(de que trata|resum\w*|sobre que es)\b",
        normalizado,
    ):
        return "resumir_material"
    if "reserv" in normalizado:
        return "reservar"
    if (
        "renovaciones" in normalizado
        or "multa por" in normalizado
        or re.search(r"\b(?:cuanto\s+(?:es|cuesta|vale|se\s+paga|cobran)|cual\s+es|valor|tarifa|costo)\b.*\bmulta", normalizado)
    ):
        return "responder_con_documentos"
    if "renov" in normalizado or re.search(r"\brenueva\b", normalizado):
        return "renovar_prestamo"
    if re.search(r"\b(cuantos|cuanto)\s+dias\b", normalizado):
        return "responder_con_documentos"
    if any(palabra in normalizado for palabra in ("multa", "debo", "mi cuenta", "mis libros", "mis prestamos")):
        return "consultar_prestamos_y_multas"
    if _extraer_peticion_bibliografia(texto):
        return "generar_bibliografia"
    if any(palabra in normalizado for palabra in ("apa", "ieee", "citar", "cita", "referencia")):
        return "responder_con_documentos"
    if any(
        palabra in normalizado
        # Temas del reglamento (pérdida, daño, retrasos, horarios, sanciones)
        for palabra in (
            "reglamento", "horario", "sancion", "carne", "perd", "pierd", "extravi",
            "dano", "danad", "retraso", "devuelvo tarde", "entrego tarde", "norma",
        )
    ):
        return "responder_con_documentos"
    if any(palabra in normalizado for palabra in ("disponib", "hay ejemplar")):
        return "consultar_disponibilidad"
    if "tienen el libro" in normalizado or "tienen el titulo" in normalizado:
        return "buscar_exacto"
    if re.search(r"\b(?:mu[eé]strame\s+m[aá]s|ver\s+m[aá]s|m[aá]s\s+informaci[oó]n|ficha\s+de|detalle\s+de)\b", normalizado):
        return "buscar_exacto"
    if re.search(r"[\"“”«][^\"“”»]+[\"“”»]", texto) or re.search(r"\bautor\b", normalizado):
        return "buscar_exacto"
    temas_no_autores = (
        r"\b(?:contabilidad|contaminacion|marketing|redes|programacion|ecologia|cultivo|costos|finanzas|"
        r"sistemas|ia|inteligencia|calculo|algebra|quimica|fisica|biologia|administracion|negocios|"
        r"derecho|economia|investigacion|metodologia|ambiental|ambientales|medio\s+ambiente)\b"
    )
    if re.search(
        r"\b(libro|libros|titulo|obra|material|buscar|busco|tienen)\b.*"
        r"\bde\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ]+",
        texto,
    ) and not re.search(temas_no_autores, normalizado):
        return "buscar_exacto"
    if any(
        palabra in normalizado
        for palabra in (
            "libro", "libros", "tesis", "articulo", "sobre", "tema", "recomi",
            "bibliografia", "busco", "red", "cultivo", "contabilidad",
            "contaminacion", "ambiental", "ambiente",
        )
    ):
        return "buscar_semantico"
    if re.search(r"\b(prestamo|prestamos)\b", normalizado):
        return "consultar_prestamos_y_multas"
    return "fuera_de_dominio"


def _seleccion_directa_segura(texto: str) -> bool:
    """Omite decisión LLM solo donde los argumentos ya se reconstruyen localmente."""
    normalizado = _normalizar(texto)
    if re.search(r"\b(y|o|pero|tambien|luego|no|si|quizas)\b|[;\n]", normalizado):
        return False
    nombre = intencion_por_palabras(texto)
    if nombre == "consultar_prestamos_y_multas":
        return bool(re.fullmatch(
            r"[¿?¡!., ]*(?:(?:consulta|consultar|revisa|revisar|ver|dime|muestra|mostrar)\s+)?"
            r"(?:mi cuenta|mis prestamos|mis multas|mis libros)[¿?¡!., ]*", normalizado
        ))
    return nombre in {"buscar_exacto", "consultar_disponibilidad", "renovar_prestamo",
                      "resumir_material", "generar_bibliografia"}


def limpiar_para_voz(texto: str) -> str:
    """Prepara una respuesta breve para TTS sin códigos ni símbolos de formato."""
    texto = _limpiar_respuesta(texto)
    # En voz la cita completa "Fuente: Documento › Sección." es larga: se deja "Según Documento."
    citas = re.findall(r"Fuente:\s*([^›.\n]+?)\s*›[^\n]*?\.(?=\s|$)", texto)
    texto = re.sub(r"\s*Fuente:\s*[^\n]*?›[^\n]*?\.(?=\s|$)", "", texto).strip()
    if citas:
        texto = f"Según {citas[0].strip()}. {texto}"
    if "\n" in texto:
        texto = "\n".join(texto.splitlines()[:3])
    texto = re.sub(r"\b\d{10}\b", "", texto)
    texto = re.sub(r"(?i)(\bpin\s*(?:es|:)?\s*)\d{4}\b", r"\1oculto", texto)
    texto = re.sub(r"\$([\d.,]+)", lambda match: f"{match.group(1).replace('.', '').replace(',', '')} pesos", texto)
    texto = re.sub(
        r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:[+-]\d{2}:\d{2}|Z)?)?",
        _fecha_en_texto,
        texto,
    )
    texto = texto.replace("›", ", ")
    texto = re.sub(r"https?://\S+", "", texto)
    texto = re.sub(r"[\*#_>\|\[\]]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    frases = re.split(r"(?<=[.!?])\s+", texto)
    return " ".join(frases[:4])


def _limpiar_respuesta(texto: str) -> str:
    texto = texto.replace("Documento de demostración para el taller", "")
    texto = texto.replace("**", "")
    texto = re.sub(
        r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:[+-]\d{2}:\d{2}|Z)?)?",
        _fecha_en_texto,
        texto,
    )
    lineas = [
        re.sub(r"[ \t]+", " ", linea).strip()
        for linea in texto.splitlines()
    ]
    return "\n".join(linea for linea in lineas if linea)


def _fecha_en_texto(coincidencia: re.Match[str]) -> str:
    return fecha_es(coincidencia.group(0))


def _numero_en_palabras(numero: int) -> str:
    """Expresa cantidades de dinero en español para la respuesta de voz."""
    unidades = (
        "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis",
        "siete", "ocho", "nueve",
    )
    especiales = {
        10: "diez", 11: "once", 12: "doce", 13: "trece", 14: "catorce",
        15: "quince", 16: "dieciséis", 17: "diecisiete", 18: "dieciocho",
        19: "diecinueve", 20: "veinte", 21: "veintiuno", 22: "veintidós",
        23: "veintitrés", 24: "veinticuatro", 25: "veinticinco",
        26: "veintiséis", 27: "veintisiete", 28: "veintiocho",
        29: "veintinueve",
    }

    def menor_mil(valor: int) -> str:
        if valor < 10:
            return unidades[valor]
        if valor < 30:
            return especiales[valor]
        if valor < 100:
            decenas = ("", "", "veinte", "treinta", "cuarenta", "cincuenta",
                       "sesenta", "setenta", "ochenta", "noventa")
            return decenas[valor // 10] + (
                f" y {unidades[valor % 10]}" if valor % 10 else ""
            )
        centenas = {
            100: "cien", 200: "doscientos", 300: "trescientos",
            400: "cuatrocientos", 500: "quinientos", 600: "seiscientos",
            700: "setecientos", 800: "ochocientos", 900: "novecientos",
        }
        base = valor // 100 * 100
        prefijo = "ciento" if base == 100 else centenas[base]
        return prefijo + (f" {menor_mil(valor % 100)}" if valor % 100 else "")

    if numero < 1000:
        return menor_mil(numero)
    if numero < 1_000_000:
        millares, resto = divmod(numero, 1000)
        prefijo = "mil" if millares == 1 else f"{menor_mil(millares)} mil"
        return prefijo + (f" {menor_mil(resto)}" if resto else "")
    millones, resto = divmod(numero, 1_000_000)
    prefijo = "un millón" if millones == 1 else f"{menor_mil(millones)} millones"
    return prefijo + (f" {_numero_en_palabras(resto)}" if resto else "")


def _pesos_en_voz(texto: str) -> str:
    """Sustituye el formato monetario por palabras antes de sintetizar la voz."""
    return re.sub(
        r"\$([\d.,]+)",
        lambda match: (
            f"{_numero_en_palabras(int(match.group(1).replace('.', '').replace(',', '')))} pesos"
        ),
        texto,
    )


def _resumir_avisos(avisos: dict[str, Any]) -> str:
    """Construye una sola frase de avisos, ordenada por prioridad."""
    partes: list[str] = []
    vencidos = avisos.get("vencidos") or []
    if vencidos:
        partes.extend(
            f"«{prestamo['titulo']}» está vencido hace "
            f"{prestamo['dias_retraso']} "
            f"{'día' if int(prestamo['dias_retraso']) == 1 else 'días'}"
            for prestamo in vencidos
        )
    multas = avisos.get("multas") or {}
    cantidad_multas = int(multas.get("cantidad") or 0)
    if cantidad_multas:
        partes.append(
            f"tiene {'una multa pendiente' if cantidad_multas == 1 else f'{cantidad_multas} multas pendientes'} "
            f"por {pesos(multas.get('total'))}"
        )

    for prestamo in avisos.get("por_vencer") or []:
        dias = int(prestamo["dias_restantes"])
        periodo = "hoy" if dias == 0 else "mañana" if dias == 1 else "en 2 días"
        partes.append(f"«{prestamo['titulo']}» vence {periodo}")

    ahora = datetime.now().astimezone()
    for reserva in avisos.get("reservas_por_expirar") or []:
        fecha = datetime.fromisoformat(str(reserva["expira_en"]))
        local = fecha.astimezone() if fecha.tzinfo else fecha
        periodo = "hoy" if local.date() == ahora.date() else "mañana"
        detalle = fecha_es(reserva["expira_en"])
        hora = detalle.split(" a las ", 1)
        texto_hora = f" a las {hora[1]}" if len(hora) == 2 else ""
        partes.append(f"su reserva de «{reserva['titulo']}» expira {periodo}{texto_hora}")
    return f"Tenga en cuenta: {'; '.join(partes)}." if partes else ""


def _extraer(objeto: Any, clave: str, defecto: Any = None) -> Any:
    if isinstance(objeto, dict):
        return objeto.get(clave, defecto)
    return getattr(objeto, clave, defecto)


def _cargar_conversacion(
    conversacion_id: str | None,
    modo_voz: bool,
    usuario_sesion: dict[str, Any] | None = None,
) -> tuple[str, int | None, dict[str, Any]]:
    try:
        identificador = UUID(conversacion_id) if conversacion_id else None
    except (ValueError, TypeError, AttributeError):
        identificador = None
    with conexion() as conn, conn.cursor() as cursor:
        if identificador is not None:
            cursor.execute(
                "SELECT id, usuario_id, estado FROM public.conversaciones WHERE id = %s",
                (identificador,),
            )
            fila = cursor.fetchone()
            if fila:
                estado = fila[2] if isinstance(fila[2], dict) else {}
                usuario_esperado = int(usuario_sesion["id"]) if usuario_sesion else None
                if fila[1] == usuario_esperado and estado.get("usuario_id") in (
                    None,
                    usuario_esperado,
                ):
                    return str(fila[0]), fila[1], estado
        estado = {
            "usuario_id": int(usuario_sesion["id"]) if usuario_sesion else None,
            "accion_pendiente": None,
            "esperando": None,
            "accion_tras_codigo": None,
            "sala": None,
        }
        cursor.execute(
            """
            INSERT INTO public.conversaciones (canal, usuario_id, estado)
            VALUES (%s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                "voz" if modo_voz else "texto",
                int(usuario_sesion["id"]) if usuario_sesion else None,
                json.dumps(estado),
            ),
        )
        return (
            str(cursor.fetchone()[0]),
            int(usuario_sesion["id"]) if usuario_sesion else None,
            estado,
        )


def _guardar_mensaje(conversacion_id: str, rol: str, contenido: str) -> None:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.mensajes (conversacion_id, rol, contenido) VALUES (%s, %s, %s)",
            (conversacion_id, rol, contenido),
        )


def _guardar_turno(
    conversacion_id: str,
    usuario_id: int | None,
    estado: dict[str, Any],
    entrada: str,
    respuesta: str,
    error: str | None,
    es_voz: bool,
    intencion: str,
    herramienta: str | None,
    fuentes: list[dict[str, Any]],
    herramienta_resultado: dict[str, Any] | None,
    tiempos: dict[str, int | None],
) -> int:
    """Guarda estado, mensajes y una fila de bitácora para cada turno."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.conversaciones
            SET usuario_id = %s, estado = %s::jsonb, actualizada = now()
            WHERE id = %s
            """,
            (usuario_id, json.dumps(estado, ensure_ascii=False), conversacion_id),
        )
        cursor.execute(
            "INSERT INTO public.mensajes (conversacion_id, rol, contenido) VALUES (%s, 'assistant', %s)",
            (conversacion_id, respuesta),
        )
        if herramienta_resultado is not None:
            resumen = {
                "ok": herramienta_resultado.get("ok"),
                "mensaje": herramienta_resultado.get("mensaje"),
                "datos": herramienta_resultado.get("datos"),
            }
            cursor.execute(
                "INSERT INTO public.mensajes (conversacion_id, rol, contenido) VALUES (%s, 'tool', %s)",
                (conversacion_id, json.dumps(resumen, ensure_ascii=False, default=str)),
            )
        cursor.execute(
            """
            INSERT INTO public.bitacora_agente
                (conversacion_id, entrada, es_voz, intencion, herramienta, fragmentos,
                 respuesta, error, t_stt_ms, t_embedding_ms, t_busqueda_ms,
                 t_llm_ms, t_tts_ms, t_total_ms)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                conversacion_id,
                entrada,
                es_voz,
                intencion,
                herramienta,
                json.dumps(fuentes, ensure_ascii=False, default=str),
                respuesta,
                error,
                tiempos.get("t_stt_ms"),
                tiempos.get("t_embedding_ms"),
                tiempos.get("t_busqueda_ms"),
                tiempos.get("t_llm_ms"),
                tiempos.get("t_tts_ms"),
                tiempos.get("t_total_ms"),
            ),
        )
        return int(cursor.fetchone()[0])


def _mensaje_historial(conversacion_id: str) -> list[dict[str, str]]:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT rol, contenido FROM public.mensajes
            WHERE conversacion_id = %s AND rol IN ('user', 'assistant')
            ORDER BY creado DESC, id DESC
            LIMIT 4
            """,
            (conversacion_id,),
        )
        mensajes = cursor.fetchall()
    return [
        {"role": rol, "content": re.sub(r"\b\d{10}\b", "[código]", contenido or "")}
        for rol, contenido in reversed(mensajes)
    ]


def _llamar_modelo(
    mensajes: list[dict[str, Any]],
    con_herramientas: bool,
    num_predict: int,
) -> tuple[Any, float]:
    """Intenta el modelo principal y una sola vez el modelo de respaldo.

    Modo híbrido (Fase A): la DECISIÓN de herramienta (tool calling) usa el modelo
    principal (qwen2.5:3b); la REDACCIÓN de respuestas con documentos usa
    LLM_MODEL_REDACCION (qwen2.5:1.5b), que es ~2 veces más rápido en CPU.
    """
    inicio = perf_counter()
    ultimo_error: Exception | None = None
    if con_herramientas:
        modelos = (LLM_MODEL, LLM_MODEL_RESPALDO)
    else:
        modelos = tuple(dict.fromkeys((LLM_MODEL_REDACCION, LLM_MODEL, LLM_MODEL_RESPALDO)))
    for modelo in modelos:
        try:
            parametros: dict[str, Any] = {
                "model": modelo,
                "messages": mensajes,
                "options": {
                    "temperature": 0,
                    "num_ctx": NUM_CTX,
                    "num_predict": num_predict,
                },
                "keep_alive": KEEP_ALIVE,
            }
            if con_herramientas:
                parametros["tools"] = TOOLS
            return _CLIENTE.chat(**parametros), (perf_counter() - inicio) * 1000
        except Exception as error:
            ultimo_error = error
    raise RuntimeError(
        "El modelo de lenguaje no está disponible; inicie Ollama."
    ) from ultimo_error


_MAPA_AREAS: list[tuple[str, list[str]]] = [
    (
        "ingenieria",
        [
            "ingenieria y tecnologia", "ingenieria", "sistemas", "tecnologia",
            "programacion", "inteligencia artificial", "ia", "software",
            "computacion", "redes",
        ],
    ),
    (
        "agro-ambiental",
        [
            "ciencias agrarias y ambientales", "ciencias agrarias", "agro-ambiental",
            "agroambiental", "agro forestal", "agroforestal", "ambiental",
            "agraria", "agrarias", "agro", "cultivos", "ecologia", "suelos",
            "bosques",
        ],
    ),
    (
        "administracion",
        [
            "administracion y negocios", "administracion de empresas",
            "administracion", "negocios", "marketing", "empresas", "gestion",
        ],
    ),
    (
        "contaduria",
        [
            "contaduria y finanzas", "contaduria publica", "contaduria",
            "contabilidad", "finanzas", "costos", "tributaria",
        ],
    ),
    (
        "investigacion",
        [
            "investigacion y escritura", "investigacion", "metodologia",
            "escritura", "redaccion", "metodologia de la investigacion",
            "tesis de grado",
        ],
    ),
]


def _detectar_area_sala(texto: str) -> str | None:
    """Identifica el slug de sala correspondiente a palabras clave o sinónimos en el texto."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    for slug, palabras in _MAPA_AREAS:
        for palabra in palabras:
            if re.search(rf"\b{re.escape(palabra)}\b", normal):
                return slug
    return None


def _es_consulta_salas(texto: str) -> bool:
    """Verifica si el usuario pregunta qué salas hay o pide cambiar de sala sin indicar cuál."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    if re.search(r"\b(?:que|cuales)\s+(?:son\s+las\s+|hay\s+de\s+|tienen\s+de\s+)?salas\b", normal):
        return True
    if re.search(r"\b(?:cambia(?:me|r)?|cambio)\s+(?:de\s+)?sala\b", normal):
        return True
    if re.search(r"\b(?:ver|mostrar|listar|cuales)\s+salas\b", normal):
        return True
    if normal in ("salas", "que salas hay", "cuales salas hay", "cambiame de sala", "cambiar de sala"):
        return True
    return False


def _es_quitar_sala(texto: str) -> bool:
    """Detecta si el usuario desea volver a toda la biblioteca."""
    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    if re.search(r"\b(?:toda\s+la\s+biblioteca|toda\s+biblioteca|todas\s+las\s+salas|sin\s+sala|salir\s+de\s+la\s+sala|quitar\s+sala)\b", normal):
        return True
    if normal in ("toda la biblioteca", "toda biblioteca", "todas", "general", "sin sala"):
        return True
    return False


_VERBOS_TRAMITE_CONSULTA = re.compile(
    r"\b("
    r"reserv\w*|aparta\w*|renov\w*|cancel\w*|prest\w*|devolv\w*|devolver\w*|disponib\w*|"
    r"ubic\w*|donde\b|estante\w*|cit\w*|referenc\w*|resum\w*|"
    r"recomiend\w*|recomendar\w*|sugier\w*|sugerir\w*|mejor\w*|trata\w*|"
    r"muestr\w*|busc\w*|ejemplar\w*|material\w*|libros?\b|tesis\b|"
    r"titul\w*|autor\w*|articulo\w*|acervo\b|cuanto\w*|dias\b|"
    r"multa\w*|sancion\w*|reglamento\w*|horario\w*"
    r")\b",
    re.IGNORECASE,
)

_PALABRAS_RELLENO_SALA = {
    "la", "el", "las", "los", "un", "una",
    "sala", "salas", "area", "areas", "seccion",
    "de", "del", "a", "al", "en",
    "quiero", "quisiera", "deseo", "me", "gustaria", "yo",
    "ir", "entrar", "pasar", "pasame", "llevame", "vamos",
    "cambia", "cambiar", "cambiame",
    "por", "favor", "porfa",
}


def _es_titulo_material_existente(texto: str) -> bool:
    """Verifica si el texto coincide con el título de un material del catálogo."""
    limpio = _normalizar(texto).strip(" ¿?!¡.,:;\"'“”«»")
    if not limpio or len(limpio) < 4:
        return False
    # No confundir nombres cortos de áreas temáticas con títulos de material
    areas_puras = {
        "ingenieria", "sistemas", "tecnologia", "agro-ambiental", "agroambiental",
        "agraria", "agrarias", "agro", "administracion", "negocios", "contaduria",
        "finanzas", "costos", "investigacion", "escritura",
    }
    if limpio in areas_puras:
        return False

    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM public.material
                WHERE lower(unaccent(titulo)) = lower(unaccent(%s))
                LIMIT 1
                """,
                (limpio,),
            )
            if cursor.fetchone():
                return True
            palabras = limpio.split()
            if len(palabras) >= 2:
                cursor.execute(
                    """
                    SELECT 1 FROM public.material
                    WHERE lower(unaccent(titulo)) ILIKE lower(unaccent(%s))
                    LIMIT 1
                    """,
                    (f"%{limpio}%",),
                )
                if cursor.fetchone():
                    return True
    except Exception:
        pass
    return False


def _es_intencion_elegir_sala(texto: str) -> str | None:
    """Devuelve el slug de sala si la intención es elegir una sala específica, o None."""
    # 1. Título entre comillas: nunca es cambio de sala
    if re.search(r"[«»\"'“”]", texto):
        return None

    normal = _normalizar(texto).strip(" ¿?!¡.,:;")
    if not normal:
        return None

    if _es_quitar_sala(texto) or _es_consulta_salas(texto):
        return None

    # 1b. Verbos o acciones de trámite o consulta: nunca es cambio de sala
    if _VERBOS_TRAMITE_CONSULTA.search(normal):
        return None

    # 1c. Coincide con título de material existente: nunca es cambio de sala
    if _es_titulo_material_existente(texto):
        return None

    es_comando_sala = bool(re.search(
        r"^(?:(?:por\s+favor\s+)?(?:yo\s+)?(?:quiero|quisiera|me\s+gustaria|deseo)\s+)?"
        r"(?:ir\s+a\s+|entrar\s+a\s+|llevame\s+a\s+|vamos\s+a\s+|pasame\s+a\s+|cambia(?:r|me)?\s+a\s+)?"
        r"(?:la\s+)?(?:sala\s+de\s+|sala\s+|la\s+de\s+)",
        normal,
    ))

    # 2. Extraer palabras no relleno
    tokens = [t for t in normal.split() if t not in _PALABRAS_RELLENO_SALA]
    reducido = " ".join(tokens)
    if not reducido:
        return None

    # Para caso corto (<= 6 palabras) o comando de sala:
    # verificar que lo que queda reducido coincida estrictamente con un área del mapa
    for slug, palabras in _MAPA_AREAS:
        for palabra in palabras:
            palabra_norm = _normalizar(palabra)
            if reducido == palabra_norm:
                return slug

    # Si hay comando explícito de sala ("quiero ir a la sala de ...") permitir detección de área
    if es_comando_sala:
        slug = _detectar_area_sala(reducido)
        if slug:
            return slug

    return None


def _prompt_sistema(sala_info: dict[str, Any] | None = None) -> str:
    sala_txt = f" Sala actual: {sala_info['nombre']}." if sala_info else ""
    return (
        f"Asistente de la biblioteca UniPutumayo.{sala_txt} Elige UNA herramienta para la consulta. "
        "No inventes datos ni pidas PIN o códigos en chat. Sé breve y cordial en español."
    )


def _es_saludo_puro(texto: str) -> bool:
    normalizado = re.sub(r"[.,!¡¿?]", " ", _normalizar(texto))
    normalizado = re.sub(r"\s+", " ", normalizado).strip()
    # Acepta combinaciones: "hola", "buenas tardes", "hola buenas tardes", "hola, buenos días biblioteca"
    return bool(
        re.fullmatch(
            r"(?:(?:hola|hey|saludos|que tal|buenas|buenos dias|buenas tardes|buenas noches)\s?){1,3}"
            r"(?:(?:por favor|biblioteca|agente|asistente)\s?)?",
            normalizado + " ",
        )
    )


def _pregunta_fuera_de_dominio(texto: str) -> bool:
    normalizado = _normalizar(texto)
    if not re.search(
        r"\b(capital|presidente|poblacion|clima|receta|partido|resultado)\s+de\b",
        normalizado,
    ):
        return False
    return not any(
        palabra in normalizado
        for palabra in ("biblioteca", "libro", "material", "tesis", "busco", "buscar", "sobre")
    )


def _es_afirmativo(texto: str) -> bool:
    limpio = re.sub(r"[,;.!¡¿?]+", " ", _normalizar(texto)).strip()
    limpio = re.sub(r"\s+(?:por favor|gracias)$", "", re.sub(r"\s+", " ", limpio))
    return limpio in {_normalizar(valor) for valor in _AFIRMATIVOS}


def _es_negativo(texto: str) -> bool:
    limpio = re.sub(r"[,;.!¡¿?]+", " ", _normalizar(texto)).strip()
    limpio = re.sub(r"\s+(?:por favor|gracias)$", "", re.sub(r"\s+", " ", limpio))
    return limpio in {_normalizar(valor) for valor in _NEGATIVOS}


def _titulo_renovacion(texto: str) -> str:
    """Separa el título de frases genéricas como «mi préstamo»."""
    titulo = _normalizar(texto)
    titulo = re.sub(
        r"\b(quiero|por favor|me gustaria|quisiera|puedo|puedes|renueva|renovar|renovacion)\b",
        " ",
        titulo,
    )
    titulo = re.sub(r"\b(mi|mis|el|un|una)?\s*prestamos?\b", " ", titulo)
    return re.sub(r"\s+", " ", titulo).strip(" .,!¡¿?")


def _titulo_cancelacion(texto: str) -> str:
    """Separa el título de la solicitud para cancelar una reserva."""
    texto = texto.strip().strip("¿?¡!.,:;\"'“”«»")
    titulo = re.sub(
        r"(?i)^\s*(?:por favor|porfa|quiero|quisiera|me gustaria|me gustaría|"
        r"ya no quiero|ya no necesito|puedes|puede|podrias|podría)?\s*",
        "",
        texto,
    )
    titulo = re.sub(
        r"(?i)^\s*(?:cancelar|cancela|cancele|cancelo|anular|anula|anule|"
        r"anulo|quitar|quita|quite|eliminar|elimina|elimine)\s*",
        "",
        titulo,
    )
    titulo = re.sub(r"(?i)^\s*(?:mi|la|una|el)?\s*reservas?\s*(?:de|del)?\s*", "", titulo)
    return titulo.strip().strip("¿?¡!.,:;\"'“”«»")


def _titulo_material(texto: str) -> str:
    """Quita la frase de petición para buscar solo el título o autor."""
    titulo = texto.strip().strip("¿?¡!.,:;\"'“”«»")
    # Cortesías iniciales ("por favor", "hola") no son parte del título
    titulo = re.sub(r"(?i)^\s*(?:hola|por favor|porfa)[\s,]*", "", titulo)
    titulo = re.sub(
        r"(?i)^\s*(?:quiero|quisiera|me gustaria|me gustaría|busco|buscar|buscame|búscame|"
        r"tienen|hay|consultar|ver|dime|indiqueme|indíqueme|necesito|podrias|podrías|"
        r"mu[eé]strame\s+m[aá]s\s+(?:de\s+)?|ver\s+m[aá]s\s+(?:de\s+)?|m[aá]s\s+informaci[oó]n\s+(?:de\s+)?|"
        r"ficha\s+(?:de|del)?\s*|detalle\s+(?:de|del)?\s*)?\s*"
        r"(?:res[eé]rv(?:ame|amelo|ármelo|armelo|ar|a)|disponibilidad|disponible|"
        r"buscar|consultar)?\s*"
        r"(?:de|el|la|los|las|un|una)?\s*"
        r"(?:libros?|material|ejemplar|titulo)?\s*",
        "",
        titulo,
    )
    titulo = re.sub(r"(?i)^de\s+", "", titulo)
    comillas = re.search(r"[«“\"']([^»”\"']+)[»”\"']", titulo)
    if comillas and comillas.group(1).strip():
        return comillas.group(1).strip().strip("¿?¡!.,:;")
    return titulo.strip().strip("¿?¡!.,:;\"'“”«»")


def _titulo_resumen_material(texto: str) -> str:
    """Extrae el título de preguntas directas sobre el contenido de una tesis."""
    comillas = re.search(r"[«“\"']([^»”\"']+)[»”\"']", texto)
    if comillas and comillas.group(1).strip():
        return comillas.group(1).strip().strip("¿?¡!.,:;")
    titulo = texto.strip().strip("¿?¡!.,:;\"'“”«»")
    titulo = re.sub(
        r"(?i)^\s*(?:de qué trata|de que trata|resúmeme|resumeme|resume|"
        r"sobre qué es|sobre que es)\s*",
        "",
        titulo,
    )
    titulo = re.sub(
        r"(?i)^\s*(?:la|el|una|un)?\s*(?:tesis|libro|material)\s*",
        "",
        titulo,
    )
    titulo = re.sub(r"^[«“\"']+|[»”\"']+$", "", titulo).strip()
    return titulo.strip("¿?¡!.,:;")


def _es_error_tecnico(resultado: dict[str, Any] | None) -> str | None:
    if not resultado or resultado.get("ok", True):
        return None
    mensaje = str(resultado.get("mensaje", ""))
    if mensaje.lower().startswith(("no fue posible", "no está disponible", "no esta disponible")):
        return mensaje
    return None


def _plantilla_busqueda(
    materiales: list[dict[str, Any]], sala_info: dict[str, Any] | None = None
) -> str:
    if not materiales:
        if sala_info:
            return f"En la {sala_info['nombre']} no encontré material sobre eso en el acervo."
        return "No encontré material sobre eso en el acervo."
    prefijo = f"En la {sala_info['nombre']} encontré:\n" if sala_info else ""
    lineas = []
    for material in materiales[:5]:
        disp = int(material.get("disponibles") or 0)
        tot = int(material.get("total") or 0)
        if disp > 0:
            texto_disp = "disponible" if disp == 1 and tot == 1 else "disponibles"
            disponibilidad = f"{disp} de {tot} {texto_disp}"
        else:
            disponibilidad = "sin ejemplares disponibles"
        linea = f"«{material.get('titulo', 'Sin título')}», de {material.get('autor', 'autor no registrado')} ({material.get('tipo', 'material')}); {disponibilidad}."
        lineas.append(linea)
    return prefijo + "\n".join(lineas)


def _formato_ficha_material(material: dict[str, Any]) -> str:
    """Genera la ficha completa de un material con autor, año, tipo, programa, sala, disponibilidad, estante/PDF y opciones."""
    titulo = material.get("titulo", "Sin título")
    autor = material.get("autor", "Autor no registrado")
    anio = material.get("anio") or "No registrado"
    tipo = str(material.get("tipo") or "Material").capitalize()
    prog = material.get("programa") or "General"
    sala = material.get("sala_nombre") or "Colección general"
    disp = int(material.get("disponibles") or 0)
    tot = int(material.get("total") or 0)
    disp_txt = f"{disp} de {tot} disponibles" if disp > 0 else "sin ejemplares disponibles"

    estantes = material.get("estantes") or []
    if estantes:
        estante_txt = f"Estante {', '.join(estantes)}"
    elif str(material.get("tipo", "")).lower() == "tesis":
        estante_txt = "Colección de tesis / Formato digital (PDF) para consulta en sala"
    else:
        estante_txt = "Colección general"

    lineas = [
        f"Ficha del material «{titulo}»:",
        f"• Autor: {autor}",
        f"• Año: {anio}",
        f"• Tipo: {tipo}",
        f"• Programa: {prog}",
        f"• Sala: {sala}",
        f"• Disponibilidad: {disp_txt}",
        f"• Ubicación: {estante_txt}",
        f"\nOpciones: Puedes pedirme reservarlo («Quiero reservar este material»), resumir su contenido («De qué trata») o consultar su disponibilidad.",
    ]
    return "\n".join(lineas)


def _limpiar_texto_resumen_extractivo(texto_crudo: str) -> str:
    """Limpia el texto de un resumen de tesis o reseña de libro:
    - Quita encabezados markdown y encabezados sueltos al inicio sin punto.
    - Une palabras partidas por el corte de línea/PDF ('clari dad' -> 'claridad')
      solo si la unión forma una palabra que aparece en el resto del texto.
    """
    texto = _limpiar_respuesta(texto_crudo)
    texto = re.sub(r"^#+\s+[^\n]+\n*", "", texto).strip()

    lineas = texto.splitlines()
    while lineas:
        primera = lineas[0].strip()
        if not primera:
            lineas.pop(0)
            continue
        if not primera.endswith((".", "!", "?", ":")) and len(primera.split()) <= 15:
            lineas.pop(0)
        else:
            break
    texto = "\n".join(lineas).strip()

    texto = re.sub(r"(\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]+)-\s*\n\s*([a-zA-ZáéíóúñÁÉÍÓÚÑ]+\b)", r"\1\2", texto)

    texto_normalizado = _normalizar(texto)

    def _reemplazar_partida(match: re.Match) -> str:
        p1 = match.group(1)
        p2 = match.group(2)
        unida = p1 + p2
        unida_norm = _normalizar(unida)
        patron_palabra = rf"\b{re.escape(unida_norm)}\b"
        if len(re.findall(patron_palabra, texto_normalizado)) >= 1:
            return unida
        return match.group(0)

    texto = re.sub(
        r"\b([a-zA-ZáéíóúñÁÉÍÓÚÑ]{2,})\s+([a-zA-ZáéíóúñÁÉÍÓÚÑ]{2,})\b",
        _reemplazar_partida,
        texto,
    )

    return texto.strip()


def _plantilla_bibliografia(
    resultado: dict[str, Any], sala_info: dict[str, Any] | None = None
) -> str:
    datos = resultado.get("datos") or {}
    referencias = datos.get("referencias") or []
    if not referencias:
        if sala_info:
            return f"En la {sala_info['nombre']} no encontré material del acervo sobre ese tema para armar la bibliografía."
        return "No encontré material del acervo sobre ese tema para armar la bibliografía."
    norma = datos.get("norma", "APA")
    tema = datos.get("tema", "")
    orden = "ordenadas alfabéticamente"
    if norma == "IEEE":
        orden += "; en un documento real IEEE numera por orden de aparición"
    prefijo = f"En la {sala_info['nombre']} encontré" if sala_info else "Encontré"
    cant_ref = len(referencias)
    texto_ref = "1 referencia" if cant_ref == 1 else f"{cant_ref} referencias"
    lineas = [
        f"{prefijo} {texto_ref} en formato {norma} sobre «{tema}» ({orden}):"
    ]
    lineas.extend(
        f"{indice}. {referencia['texto']}"
        for indice, referencia in enumerate(referencias, start=1)
    )
    aviso = str(resultado.get("mensaje") or "")
    if aviso.startswith("La norma «"):
        lineas.insert(0, aviso.split("Encontré", 1)[0].strip())
    return "\n".join(lineas)


def _plantilla_cuenta(datos: dict[str, Any]) -> str:
    partes: list[str] = []
    prestamos = datos.get("prestamos", [])
    if prestamos:
        for prestamo in prestamos:
            estado = (
                f", {prestamo.get('dias_retraso', 0)} días de retraso"
                if int(prestamo.get("dias_retraso") or 0) > 0
                else ""
            )
            partes.append(
                f"Préstamo: «{prestamo['titulo']}», vence {fecha_es(prestamo['fecha_vencimiento'])}, "
                f"{prestamo['renovaciones']} renovaciones{estado}."
            )
    else:
        partes.append("No tiene préstamos activos.")
    multas = datos.get("multas", [])
    if multas:
        partes.append(
            "Multas pendientes: "
            + ", ".join(
                f"{pesos(multa['valor'])} por {multa.get('dias', 0)} días"
                for multa in multas
            )
            + f". Total: {pesos(datos.get('total_multas'))}."
        )
    else:
        partes.append("No tiene multas pendientes.")
    reservas = datos.get("reservas", [])
    if reservas:
        partes.append(
            "Reservas activas: "
            + "; ".join(f"«{r['titulo']}», vence {fecha_es(r['expira_en'])}" for r in reservas)
            + "."
        )
    return " ".join(partes)


def _fuentes_de_resultado(nombre: str, resultado: dict[str, Any]) -> list[dict[str, Any]]:
    if nombre in ("presentacion", "cortesia"):
        return []
    if nombre == "resumir_material":
        return [
            {
                "id": None,
                "documento": fuente.get("titulo"),
                "seccion": fuente.get("seccion"),
                "similitud": None,
            }
            for fuente in resultado.get("fuentes", [])[:5]
        ]
    if nombre == "generar_bibliografia":
        return [
            {
                "id": fuente.get("material_id"),
                "documento": fuente.get("titulo"),
                "seccion": None,
                "similitud": fuente.get("similitud"),
            }
            for fuente in resultado.get("fuentes", [])
            if isinstance(fuente, dict) and fuente.get("similitud") is not None
        ][:5]
    datos = resultado.get("datos")
    elementos = datos if isinstance(datos, list) else []
    fuentes: list[dict[str, Any]] = []
    for elemento in elementos:
        if not isinstance(elemento, dict) or "similitud" not in elemento:
            continue
        if nombre == "responder_con_documentos":
            fuentes.append(
                {
                    "id": elemento.get("id"),
                    "documento": elemento.get("documento"),
                    "seccion": elemento.get("seccion"),
                    "similitud": elemento.get("similitud"),
                }
            )
        else:
            fuentes.append(
                {
                    "id": elemento.get("material_id"),
                    "documento": elemento.get("titulo"),
                    "seccion": None,
                    "similitud": elemento.get("similitud"),
                }
            )
    if nombre == "responder_con_documentos":
        fuentes.sort(key=lambda fuente: float(fuente.get("similitud") or 0), reverse=True)
        distintas = []
        for fuente in fuentes:
            if not any(f.get("documento") == fuente.get("documento") for f in distintas):
                distintas.append(fuente)
        return (distintas if len(distintas) > 1 else fuentes)[:2]
    return fuentes[:5]


def _renderizar_documentos(
    pregunta: str, fragmentos: list[dict[str, Any]], tiempos: dict[str, Any]
) -> tuple[str, float, str | None]:
    if not fragmentos or max(float(item.get("similitud", 0)) for item in fragmentos) < 0.35:
        return "No tengo esa información en los documentos de la biblioteca.", 0, None
    normas = [n for n in ("apa", "ieee") if re.search(rf"\b{n}\b", _normalizar(pregunta))]
    if len(normas) > 1:
        partes, total_llm = [], 0
        for norma in normas:
            propios = [f for f in fragmentos if f.get("tipo") == norma]
            consulta = re.sub(r"\b(?:APA|IEEE)\b", "", pregunta, flags=re.I) + " " + norma.upper()
            if propios:
                texto, demora, error = _renderizar_documentos(consulta, propios, tiempos)
                if error:
                    return texto, demora, error
                partes.append(f"**{norma.upper()}**\n{texto}")
                total_llm += demora
            else:
                partes.append(f"No pude recuperar la guía {norma.upper()} en esta consulta.")
        return "\n\n".join(partes), total_llm, None
    if normas and any(f.get("resumen_norma") for f in fragmentos):
        # Se seleccionan frases completas de las guías, sin inventar reglas.
        candidatos, vistos = [], set()
        for item in fragmentos:
            limpio = _limpiar_respuesta(str(item.get("texto") or ""))
            for frase in re.split(r"(?<=[.!?])\s+", limpio):
                normal = _normalizar(frase)
                if not (30 <= len(frase) <= 400 and frase[0].isupper() and frase.endswith(".") and normal not in vistos):
                    continue
                puntaje = sum(peso for patron, peso in ((r"autor.fecha", 3), (r"corchetes", 3), (r"orden.*(?:aparicion|cita)", 3), (r"alfabetic", 2), (r"lista.*(?:referencias|final)", 1), (r"cita.*textual", 1)) if re.search(patron, normal))
                if puntaje:
                    vistos.add(normal)
                    candidatos.append((puntaje, frase, item))
        if candidatos:
            elegidos = sorted(candidatos, key=lambda f: -f[0])[:3]
            elegidos.sort(key=lambda f: (f[2].get("orden", 0), str(f[2].get("texto", "")).find(f[1])))
            texto = " ".join(f[1] for f in elegidos)
            fuentes = dict.fromkeys(f"Fuente: {f[2].get('documento')} › {f[2].get('seccion') or 'General'}." for f in elegidos)
            return texto + " " + " ".join(fuentes), 0, None
    seleccion = sorted(
        fragmentos, key=lambda item: float(item.get("similitud", 0)), reverse=True
    )[:3]

    normal_p = _normalizar(pregunta)

    # Punto 1: Plazo de préstamo ("¿Cuántos días me prestan un libro?", "¿Cuánto dura un préstamo?"):
    es_pregunta_dias_prestamo = bool(re.search(
        r"\b(?:cuantos?\s+dias|cuanto\s+tiempo|duracion|plazo|periodo|tiempo)\s+(?:me\s+)?(?:prestan?|dura|es\s+el\s+prestamo)\b|"
        r"\b(?:prestan?|prestamo)\s+(?:por\s+)?(?:cuantos?\s+dias|cuanto\s+tiempo|que\s+plazo)\b|"
        r"\bcuantos?\s+dias\s+me\s+prestan\b",
        normal_p,
    ))
    if es_pregunta_dias_prestamo and not re.search(r"\brenov\w*", normal_p):
        faq_duracion = next(
            (f for f in fragmentos if "cuanto dura un prestamo" in _normalizar(str(f.get("seccion") or "")) or "8 dias calendario" in _normalizar(str(f.get("texto") or ""))),
            None,
        )
        doc_nombre = (faq_duracion.get("documento") if faq_duracion else None) or "Preguntas frecuentes de la biblioteca"
        seccion_nombre = (faq_duracion.get("seccion") if faq_duracion else None) or "¿Cuánto dura un préstamo externo?"
        texto_plazo = "Los libros se prestan por 8 días calendario (el periodo ordinario de préstamo externo es de 8 días calendario). La fecha exacta que aparece en el sistema es la que debe tener en cuenta."
        return f"{texto_plazo} Fuente: {doc_nombre} › {seccion_nombre}.", 0.0, None

    # Pregunta sobre valor o tarifa de la multa por día / retraso ("¿Cuánto es la multa por día?"):
    es_pregunta_multa_dia = bool(re.search(
        r"\b(?:cuanto\s+(?:es|cuesta|vale|se\s+paga|se\s+cobra|cobran)|cual\s+es|valor|tarifa|costo)\b.*\bmulta\b|"
        r"\bmulta\b.*\b(?:por\s+dia|diaria|cuanto|valor|tarifa|costo|retraso|mora)\b",
        normal_p,
    ))
    if es_pregunta_multa_dia:
        frag_multa = next(
            (
                f for f in fragmentos
                if "1.000" in str(f.get("texto") or "") or "1000" in str(f.get("texto") or "") or "multa" in str(f.get("seccion") or "").lower()
            ),
            None,
        )
        doc_nombre = (frag_multa.get("documento") if frag_multa else None) or "Reglamento de préstamos"
        seccion_nombre = (frag_multa.get("seccion") if frag_multa else None) or "Multas"
        texto_multa = (
            "La devolución posterior a la fecha de vencimiento genera una multa de "
            "$1.000 por día calendario de retraso y por cada ejemplar, de acuerdo con el registro del sistema."
        )
        return f"{texto_multa} Fuente: {doc_nombre} › {seccion_nombre}.", 0.0, None

    # Pregunta específica del reglamento sobre límite de libros simultáneos:
    if re.search(r"\b(?:cuantos?|cuantas?)\s+(?:libros?|ejemplares|materiales)?\s*(?:puedo|se\s+pueden?)\s*(?:sacar|prestar|pedir|llevar|tener)\b", normal_p):
        doc_reglamento = next((f for f in seleccion if "reglamento" in str(f.get("documento", "")).lower()), seleccion[0] if seleccion else None)
        doc_nombre = (doc_reglamento.get("documento") if doc_reglamento else None) or "Reglamento de préstamos"
        seccion_nombre = (doc_reglamento.get("seccion") if doc_reglamento else None) or "Condiciones de préstamo"
        texto_extractivo = (
            "El reglamento indexado indica que la cantidad de ejemplares y la duración permitida "
            "dependen del perfil del usuario y del tipo de recurso, pero no fija un límite numérico exacto de libros simultáneos."
        )
        return f"{texto_extractivo} Fuente: {doc_nombre} › {seccion_nombre}.", 0.0, None

    # Reordenar fragmentos de FAQ: prioriza la pregunta de la FAQ más parecida a la del usuario (sección),
    # y descarta FAQ cuyo tema principal sea otro (renovar != prestar)
    faq_frags = [
        f for f in fragmentos
        if str(f.get("tipo", "")).lower() == "faq" or "preguntas frecuentes" in str(f.get("documento", "")).lower()
    ]
    if faq_frags:
        def _score_faq(f: dict[str, Any]) -> float:
            score = float(f.get("similitud", 0))
            sec = _normalizar(str(f.get("seccion") or ""))
            if re.search(r"\brenov\w*", sec) and not re.search(r"\brenov\w*", normal_p):
                score -= 0.50
            if re.search(r"\brenov\w*", normal_p) and not re.search(r"\brenov\w*", sec):
                score -= 0.30
            palabras_u = set(re.findall(r"\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]{4,}\b", normal_p))
            palabras_s = set(re.findall(r"\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]{4,}\b", sec))
            score += len(palabras_u.intersection(palabras_s)) * 0.15
            return score

        faq_frags.sort(key=_score_faq, reverse=True)
        if faq_frags and _score_faq(faq_frags[0]) > float(seleccion[0].get("similitud", 0)):
            seleccion[0] = faq_frags[0]

    # Punto 3: Reglamento / FAQ rápido:
    # Si el mejor fragmento es de Preguntas frecuentes o Reglamento con similitud >= 0.55,
    # responder EXTRACTIVO (la respuesta de la FAQ o las 1-3 frases del fragmento, limpias) + "Fuente: ...", sin LLM.
    mejor_frag = seleccion[0]
    sim_mejor = float(mejor_frag.get("similitud", 0))
    doc_mejor = str(mejor_frag.get("documento", "")).lower()
    tipo_mejor = str(mejor_frag.get("tipo", "")).lower()
    es_faq_o_reglamento = (
        tipo_mejor in ("faq", "reglamento")
        or "preguntas frecuentes" in doc_mejor
        or "reglamento" in doc_mejor
    )
    if es_faq_o_reglamento and sim_mejor >= 0.55:
        texto_crudo = str(mejor_frag.get("texto") or "").strip()
        texto_limpio = _limpiar_respuesta(texto_crudo)
        texto_limpio = re.sub(r"^#+\s+[^\n]+\n*", "", texto_limpio).strip()

        frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto_limpio) if f.strip()]
        texto_extractivo = " ".join(frases[:3]).strip()
        if not texto_extractivo:
            texto_extractivo = texto_limpio

        cita = f"Fuente: {mejor_frag.get('documento')} › {mejor_frag.get('seccion') or 'General'}."
        return f"{texto_extractivo} {cita}".strip(), 0.0, None

    # Citación (APA/IEEE): respuesta EXTRACTIVA. El modelo de 3B tiende a deformar los
    # formatos, así que si un fragmento trae "Formato: ..." se copia literal con su ejemplo.
    if re.search(r"\b(apa|ieee|cit[ao]|citar|referencia)", _normalizar(pregunta)):
        # Se revisa el top-5: primero los de la misma sección que el mejor fragmento
        top5 = sorted(fragmentos, key=lambda item: float(item.get("similitud", 0)), reverse=True)[:5]
        mejor_seccion = top5[0].get("seccion")
        candidatos = [i for i in top5 if i.get("seccion") == mejor_seccion] + [
            i for i in top5 if i.get("seccion") != mejor_seccion
        ]
        for item in candidatos:
            limpio = _limpiar_respuesta(str(item.get("texto") or ""))
            formato = re.search(r"Formato(?: general)?:\s*(.+?)(?=\s*Ejemplo|\n|$)", limpio, re.S)
            if formato:
                ejemplo = re.search(r"Ejemplo[^:]*:\s*(.+?)(?=\n|$)", limpio, re.S)
                texto = f"El formato es: {formato.group(1).strip()}"
                if ejemplo:
                    texto += f" Ejemplo: {ejemplo.group(1).strip()}"
                cita = f"Fuente: {item.get('documento')} › {item.get('seccion') or 'General'}."
                return f"{texto} {cita}", 0, None

    contexto = "\n\n".join(
        f"[{item.get('documento')} › {item.get('seccion') or 'General'}]\n"
        f"{_limpiar_respuesta(str(item.get('texto') or ''))}"
        for item in seleccion
    )
    mensajes = [
        {
            "role": "system",
            "content": (
                "Eres el asistente de la biblioteca. Responde en español, en tono cordial, "
                "usando la información de los textos de referencia. El primer texto es el "
                "más relevante: úsalo. Explica el formato y da el ejemplo si aparece, "
                "copiándolos tal como están escritos; nunca inventes formatos, datos ni ejemplos. "
                "No menciones la palabra 'fragmentos' ni 'textos de referencia'. "
                "Solo di que no tienes la información si ninguno trata el tema. "
                "Máximo cuatro frases."
            ),
        },
        {"role": "user", "content": f"Textos de referencia:\n{contexto}\n\nPregunta: {pregunta}"},
    ]
    try:
        respuesta, tiempo = _llamar_modelo(
            mensajes, con_herramientas=False, num_predict=NUM_PREDICT_REDACCION
        )
        contenido = _extraer(_extraer(respuesta, "message", {}), "content", "")
        texto = _limpiar_respuesta(str(contenido or ""))
        no_sabe = re.search(
            # Frases con que el modelo pequeño "se niega" aunque el texto sí responda
            r"\b(no la tengo|no tienes? .{0,20}informacion|no tengo.{0,30}informacion|"
            r"no encontre|no encuentro|no halle|no hallo|no tratan|no trata|"
            r"no (se )?mencionan?|no especifican?|no (se )?incluyen?|"
            r"no cuento con esa informacion|no dispongo de esa informacion)\b",
            _normalizar(texto),
        )
        if not texto or (
            no_sabe and float(seleccion[0].get("similitud", 0)) >= 0.45
        ):
            mejor = _limpiar_respuesta(str(seleccion[0].get("texto") or ""))
            frases = re.split(r"(?<=[.!?])\s+", mejor)
            texto = " ".join(frases[:3]).strip()
        if not texto:
            return "No tengo esa información en los documentos de la biblioteca.", tiempo, None
        citas = " ".join(
            f"Fuente: {item.get('documento')} › {item.get('seccion') or 'General'}."
            for item in seleccion[:2]
        )
        return f"{texto} {citas}".strip(), tiempo, None
    except Exception as error:
        return (
            "El modelo de lenguaje no está disponible; inicie Ollama.",
            0,
            str(error),
        )


def _ejecutar_herramienta(
    nombre: str,
    argumentos: dict[str, Any],
    usuario_id: int | None,
    estado: dict[str, Any],
    sala_slug: str | None = None,
) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]], str | None, float]:
    """Resuelve argumentos de lenguaje natural y ejecuta o prepara una acción."""
    sala_info = salas.sala_por_slug(sala_slug)
    if nombre == "presentacion":
        if sala_info:
            bibliotecario = sala_info.get("bibliotecario", {}).get("nombre", "el bibliotecario")
            nombre_sala = sala_info.get("nombre", "la sala")
            respuesta = (
                f"Soy el agente virtual de la biblioteca de la Institución Universitaria del Putumayo, "
                f"y te atiendo desde la {nombre_sala} junto a {bibliotecario}. "
                "Puedo ayudarte a buscar libros y tesis, revisar estantes y disponibilidad, "
                "gestionar préstamos y reservas, y orientarte sobre el reglamento institucional "
                "y las normas de citación (APA e IEEE). ¿En qué te colaboro hoy?"
            )
        else:
            respuesta = (
                "Soy el agente de la biblioteca de la Institución Universitaria del Putumayo. "
                "Puedo ayudarte a explorar nuestro catálogo de libros y tesis, conocer la disponibilidad "
                "y ubicación en estantes, gestionar tus préstamos o reservas, y resolver dudas sobre "
                "el reglamento y normas de citación (APA e IEEE). Contamos con 5 salas temáticas: "
                "Ingeniería y Tecnología, Ciencias Agrarias y Ambientales, Administración y Negocios, "
                "Contaduría y Finanzas, e Investigación y Escritura. ¿Qué deseas consultar?"
            )
        resultado = {"ok": True, "mensaje": respuesta, "datos": None}
        return respuesta, resultado, [], None, 0

    if nombre == "cortesia":
        tipo = argumentos.get("tipo", "gracias")
        if tipo == "despedida":
            respuesta = "¡Hasta luego! Que tengas un excelente día. La biblioteca está a tu disposición cuando lo necesites."
        else:
            respuesta = "¡Con mucho gusto! Estoy a tu orden para cualquier otra consulta sobre el acervo o los servicios de la biblioteca."
        resultado = {"ok": True, "mensaje": respuesta, "datos": None}
        return respuesta, resultado, [], None, 0

    if nombre == "panorama_catalogo":
        resultado = herramientas.panorama_catalogo(sala_slug=sala_slug)
        return resultado["mensaje"], resultado, [], _es_error_tecnico(resultado), 0

    if nombre == "mas_prestados":
        resultado = herramientas.mas_prestados(sala_slug=sala_slug)
        return resultado["mensaje"], resultado, [], _es_error_tecnico(resultado), 0

    if nombre == "ubicacion_material":
        titulo = str(argumentos.get("titulo") or "").strip()
        resultado = herramientas.ubicacion_material(titulo, sala_slug=sala_slug)
        return resultado["mensaje"], resultado, [], _es_error_tecnico(resultado), 0

    if nombre == "recomendar":
        tema = argumentos.get("tema")
        if tema:
            tema = str(tema).strip()
        resultado = herramientas.recomendar(tema=tema, sala_slug=sala_slug)
        return resultado["mensaje"], resultado, _fuentes_de_resultado(nombre, resultado), _es_error_tecnico(resultado), 0

    if nombre in (
        "consultar_recogida",
        "reservar",
        "cancelar_reserva",
        "renovar_prestamo",
        "consultar_prestamos_y_multas",
    ) and usuario_id is None:
        estado["esperando"] = "codigo"
        estado["accion_tras_login"] = {"nombre": nombre, "argumentos": argumentos}
        return (
            "Para eso necesitas iniciar sesión. Dime tu código de usuario (por ejemplo: «mi código es ciento uno») o usa el botón Iniciar sesión.",
            None,
            [],
            None,
            0,
        )

    if nombre == "consultar_recogida":
        resultado = herramientas.consultar_recogida(int(usuario_id), str(argumentos.get("titulo", "")))
        return resultado["mensaje"], resultado, [], _es_error_tecnico(resultado), 0
    if nombre == "buscar_semantico":
        resultado = herramientas.buscar_semantico(
            str(argumentos.get("consulta", "")),
            sala_slug=sala_slug,
        )
        if resultado.get("sugerencia_sala"):
            respuesta = resultado["mensaje"]
        elif resultado["ok"]:
            respuesta = _plantilla_busqueda(resultado["datos"], sala_info)
        else:
            respuesta = resultado["mensaje"]
    elif nombre == "buscar_exacto":
        titulo_buscado = _titulo_material(str(argumentos.get("texto", "")))
        # Punto 4: Si se busca un material concreto (como "muéstrame más de...", etc.):
        # Usa la misma resolución de títulos que reservar (resolver_material en todo el catálogo)
        candidato = herramientas.resolver_material(titulo_buscado, sala_slug=None)
        if candidato.get("ok") and candidato.get("datos"):
            materiales_resueltos = herramientas.enriquecer_materiales(candidato["datos"][:1])
            if materiales_resueltos:
                mat = materiales_resueltos[0]
                respuesta = _formato_ficha_material(mat)
                resultado = {"ok": True, "mensaje": respuesta, "datos": materiales_resueltos}
                return respuesta, resultado, _fuentes_de_resultado(nombre, resultado), None, 0

        resultado = herramientas.buscar_exacto(
            titulo_buscado,
            sala_slug=sala_slug,
        )
        if resultado.get("sugerencia_sala"):
            respuesta = resultado["mensaje"]
        elif resultado["ok"]:
            materiales_res = herramientas.enriquecer_materiales(resultado["datos"])
            if len(materiales_res) == 1:
                respuesta = _formato_ficha_material(materiales_res[0])
            else:
                respuesta = _plantilla_busqueda(resultado["datos"], sala_info)
        else:
            respuesta = resultado["mensaje"]
    elif nombre == "consultar_disponibilidad":
        candidato = (
            _candidato_referido(argumentos, estado)
            if "_referencia_id" in argumentos else herramientas.resolver_material(
                _titulo_material(str(argumentos.get("titulo", ""))),
                sala_slug=None,
            )
        )
        if not candidato["ok"] or not candidato["datos"]:
            resultado = candidato
            if candidato.get("sugerencia_sala"):
                respuesta = candidato["mensaje"]
            elif str(candidato["mensaje"]).lower().startswith("no fue posible"):
                respuesta = candidato["mensaje"]
            else:
                respuesta = "No encontré ese material en el acervo."
        elif len(candidato["datos"]) > 1:
            estado["desambiguacion_pendiente"] = {
                "tipo": "consultar_disponibilidad",
                "items": candidato["datos"],
                "expira": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }
            estado["catalogo_contexto"] = {
                "conversacion_id": estado.get("conversacion_id"),
                "usuario_id": usuario_id,
                "items": candidato["datos"],
                "expira": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }
            resultado = candidato
            respuesta = _plantilla_busqueda(candidato["datos"], sala_info)
        else:
            material = candidato["datos"][0]
            resultado = herramientas.consultar_disponibilidad(int(material["material_id"]))
            if candidato.get("tiempos"):
                resultado["tiempos"] = candidato["tiempos"]
            datos = resultado.get("datos") or {}
            if resultado["ok"]:
                datos["similitud"] = material.get("similitud")
                enriquecidos = herramientas.enriquecer_materiales([datos])
                mat_sala = enriquecidos[0].get("sala_nombre") if enriquecidos else None
                respuesta = _plantilla_busqueda([datos], sala_info)
                respuesta += " " + herramientas.mensaje_disponibilidad(datos)
                if mat_sala and (not sala_info or sala_info.get("nombre") != mat_sala):
                    respuesta += f" Está en la {mat_sala}."
            else:
                respuesta = resultado["mensaje"]
    elif nombre == "consultar_prestamos_y_multas":
        resultado = herramientas.consultar_prestamos_y_multas(int(usuario_id))
        respuesta = _plantilla_cuenta(resultado["datos"]) if resultado["ok"] else resultado["mensaje"]
    elif nombre == "responder_con_documentos":
        resultado = herramientas.responder_con_documentos(str(argumentos.get("pregunta", "")))
        fuentes = _fuentes_de_resultado(nombre, resultado)
        if not resultado["ok"] and str(resultado["mensaje"]).lower().startswith("no fue posible"):
            return resultado["mensaje"], resultado, fuentes, resultado["mensaje"], 0
        respuesta, tiempo, error = _renderizar_documentos(
            str(argumentos.get("pregunta", "")),
            resultado["datos"] if resultado["ok"] else [],
            resultado.get("tiempos", {}),
        )
        return respuesta, resultado, fuentes, error, tiempo
    elif nombre == "resumir_material":
        pregunta = str(argumentos.get("pregunta") or "")
        resultado = herramientas.resumir_material(
            str(argumentos.get("titulo") or ""),
            pregunta,
            sala_slug=sala_slug,
        )
        if not resultado.get("ok"):
            return (
                str(resultado.get("mensaje") or "No encontré ese material o una reseña disponible."),
                resultado,
                _fuentes_de_resultado(nombre, resultado),
                _es_error_tecnico(resultado),
                0,
            )
        fragmentos = resultado.get("datos") or []

        # Punto 4: resumir_material extractivo desde el resumen (3-4 frases limpias) + fuente; LLM solo si no hay resumen
        resumenes = [
            f for f in fragmentos
            if f.get("tipo") in ("resumen_tesis", "resena_libro") and str(f.get("texto") or "").strip()
        ]
        if resumenes:
            mejor_resumen = resumenes[0]
            texto_limpio = _limpiar_texto_resumen_extractivo(str(mejor_resumen.get("texto") or ""))
            frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto_limpio) if f.strip()]
            texto = " ".join(frases[:4])
            seccion = str(mejor_resumen.get("seccion") or ("Resumen" if mejor_resumen.get("tipo") == "resumen_tesis" else "Reseña"))
            cita = f"Fuente: «{mejor_resumen.get('documento')}» › {seccion}."
            respuesta = f"{texto} {cita}".strip()
            resultado["mensaje"] = respuesta
            return (
                respuesta,
                resultado,
                _fuentes_de_resultado(nombre, resultado),
                None,
                0.0,
            )

        contexto = "\n\n".join(
            f"[{fragmento.get('documento')} › "
            f"{'Resumen' if fragmento.get('tipo') == 'resumen_tesis' else fragmento.get('seccion') or 'Página'}]\n"
            f"{_limpiar_respuesta(str(fragmento.get('texto') or ''))}"
            for fragmento in fragmentos
        )
        mensajes = [
            {
                "role": "system",
                "content": (
                    "Resume en español, en máximo cuatro frases, únicamente con los "
                    "textos entregados. No agregues datos ni afirmaciones que no estén "
                    "en ellos. No escribas citas ni fuentes; se añadirán por separado."
                ),
            },
            {
                "role": "user",
                "content": f"Textos del material:\n{contexto}\n\nPregunta: {pregunta}",
            },
        ]
        inicio = perf_counter()
        try:
            respuesta_modelo = _CLIENTE.chat(
                model=LLM_MODEL_REDACCION,
                messages=mensajes,
                options={
                    "temperature": 0,
                    "num_ctx": NUM_CTX,
                    "num_predict": NUM_PREDICT_REDACCION,
                },
                keep_alive=KEEP_ALIVE,
            )
            texto = _limpiar_respuesta(
                str(_extraer(_extraer(respuesta_modelo, "message", {}), "content", "") or "")
            )
            frases = [frase for frase in re.split(r"(?<=[.!?])\s+", texto) if frase]
            texto = " ".join(frases[:4])
            if not texto:
                raise RuntimeError("El modelo no devolvió un resumen.")
        except Exception as error:
            mensaje_error = f"No fue posible resumir el material: {error}"
            resultado["ok"] = False
            resultado["mensaje"] = mensaje_error
            return mensaje_error, resultado, [], mensaje_error, 0

        fuentes_cita: list[str] = []
        for fuente in resultado.get("fuentes", []):
            seccion = str(fuente.get("seccion") or "Resumen")
            etiqueta = (
                "Resumen"
                if fuente.get("tipo") == "resumen_tesis"
                else seccion
            )
            cita = f"«{fuente.get('titulo')}» › {etiqueta}"
            if cita not in fuentes_cita:
                fuentes_cita.append(cita)
            if len(fuentes_cita) == 2:
                break
        citas = f"Fuente: {'; '.join(fuentes_cita)}"
        if texto[-1:] in ".!?":
            respuesta = f"{texto[:-1]} {citas}{texto[-1]}"
        else:
            respuesta = f"{texto} {citas}"
        resultado["mensaje"] = respuesta
        return (
            respuesta,
            resultado,
            _fuentes_de_resultado(nombre, resultado),
            None,
            (perf_counter() - inicio) * 1000,
        )
    elif nombre == "generar_bibliografia":
        resultado = herramientas.generar_bibliografia(
            str(argumentos.get("tema", "")),
            int(argumentos.get("cantidad", 5)),
            str(argumentos.get("norma", "APA")),
            sala_slug=sala_slug,
        )
        if resultado.get("sugerencia_sala"):
            respuesta = resultado["mensaje"]
        elif resultado.get("ok"):
            respuesta = _plantilla_bibliografia(resultado, sala_info)
        else:
            respuesta = resultado.get("mensaje", "No encontré material del acervo sobre ese tema para armar la bibliografía.")
    elif nombre == "reservar":
        candidato = (
            _candidato_referido(argumentos, estado)
            if "_referencia_id" in argumentos else herramientas.resolver_material(
                _titulo_material(str(argumentos.get("titulo", "")))
            )
        )
        if not candidato["ok"] or not candidato["datos"]:
            respuesta = (
                candidato["mensaje"]
                if str(candidato["mensaje"]).lower().startswith("no fue posible")
                else "No encontré ese material en el acervo."
            )
            return respuesta, candidato, [], _es_error_tecnico(candidato), 0
        if len(candidato["datos"]) > 1:
            estado["desambiguacion_pendiente"] = {
                "tipo": "reservar",
                "items": candidato["datos"],
                "expira": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }
            estado["catalogo_contexto"] = {
                "conversacion_id": estado.get("conversacion_id"),
                "usuario_id": usuario_id,
                "items": candidato["datos"],
                "expira": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }
            return (
                "Encontré varias opciones. Indíqueme cuál desea reservar:\n"
                + _plantilla_busqueda(candidato["datos"]),
                candidato,
                _fuentes_de_resultado(nombre, candidato),
                None,
                0,
            )
        material = candidato["datos"][0]
        disponibilidad = herramientas.consultar_disponibilidad(int(material["material_id"]))
        if not disponibilidad.get("ok"):
            return disponibilidad["mensaje"], disponibilidad, [], _es_error_tecnico(disponibilidad), 0
        aviso = herramientas.mensaje_disponibilidad(disponibilidad["datos"])
        if not disponibilidad["datos"]["disponibles"]:
            aviso += " Si confirma, su solicitud quedará en espera, sin un ejemplar apartado."
        pendiente = {
            "tipo": "reservar",
            "aviso": aviso,
            "params": {"material_id": int(material["material_id"])},
            "descripcion": material["titulo"],
            "expira": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        }
        estado["accion_pendiente"] = pendiente
        estado["accion_tras_codigo"] = None
        estado["esperando"] = None
        return (
            aviso + f" ¿Confirmo la reserva de «{material['titulo']}»?",
            {
                "ok": True,
                "mensaje": "Reserva pendiente de confirmación.",
                "datos": material,
                "tiempos": candidato.get("tiempos", {}),
            },
            _fuentes_de_resultado(nombre, candidato),
            None,
            0,
        )
    elif nombre == "cancelar_reserva":
        reservas = herramientas.reservas_activas_usuario(int(usuario_id))
        if not reservas:
            return "No tiene reservas activas.", {
                "ok": True,
                "mensaje": "No tiene reservas activas.",
                "datos": [],
            }, [], None, 0
        titulo_solicitado = str(argumentos.get("titulo") or "").strip()
        if titulo_solicitado:
            titulo_normalizado = _normalizar(titulo_solicitado).strip()
            coincidencias = [
                reserva
                for reserva in reservas
                if titulo_normalizado in _normalizar(reserva["titulo"])
                or _normalizar(reserva["titulo"]) in titulo_normalizado
            ]
            if not coincidencias:
                candidato = herramientas.resolver_material(titulo_solicitado)
                if not candidato.get("ok") and str(candidato.get("mensaje", "")).lower().startswith(
                    ("no fue posible", "no está disponible", "no esta disponible")
                ):
                    return candidato["mensaje"], candidato, [], candidato["mensaje"], 0
                ids = {
                    int(material["material_id"])
                    for material in candidato.get("datos") or []
                    if material.get("material_id") is not None
                }
                coincidencias = [
                    reserva for reserva in reservas
                    if int(reserva["material_id"]) in ids
                ]
        else:
            coincidencias = reservas
        if not coincidencias:
            return "No encontré esa reserva a su nombre.", {
                "ok": False,
                "mensaje": "No encontré esa reserva a su nombre.",
                "datos": None,
            }, [], None, 0
        if "_propia_id" in argumentos:
            coincidencias = [r for r in reservas if int(r['reserva_id']) == argumentos['_propia_id']]
        if len(coincidencias) > 1:
            _guardar_seleccion_propia(estado, nombre, coincidencias, usuario_id)
            titulos = ", ".join(f"«{reserva['titulo']}»" for reserva in coincidencias[:5])
            return (
                f"¿Cuál reserva desea cancelar? Tiene estas: {titulos}.",
                {"ok": True, "mensaje": "Hay varias reservas activas.", "datos": coincidencias},
                [],
                None,
                0,
            )
        reserva = coincidencias[0]
        pendiente = {
            "tipo": "cancelar_reserva",
            "params": {"reserva_id": int(reserva["reserva_id"])},
            "descripcion": reserva["titulo"],
            "expira": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        }
        estado["accion_pendiente"] = pendiente
        estado["accion_tras_codigo"] = None
        estado["esperando"] = None
        return (
            f"¿Confirmo la cancelación de su reserva de «{reserva['titulo']}»?",
            {
                "ok": True,
                "mensaje": "Cancelación pendiente de confirmación.",
                "datos": reserva,
            },
            [],
            None,
            0,
        )
    elif nombre == "renovar_prestamo":
        lista = herramientas.prestamos_activos_usuario(int(usuario_id))
        if not lista["ok"]:
            return lista["mensaje"], lista, [], None, 0
        prestamos = lista["datos"]
        if not prestamos:
            return "No tiene préstamos activos que pueda renovar.", lista, [], None, 0
        titulo_solicitado = _normalizar(str(argumentos.get("titulo") or "")).strip()
        if titulo_solicitado:
            coincidencias = [
                prestamo
                for prestamo in prestamos
                if titulo_solicitado in _normalizar(prestamo["titulo"])
                or _normalizar(prestamo["titulo"]) in titulo_solicitado
            ]
        else:
            coincidencias = prestamos
        if "_propia_id" in argumentos:
            coincidencias = [p for p in prestamos if int(p['prestamo_id']) == argumentos['_propia_id']]
        if len(coincidencias) > 1:
            _guardar_seleccion_propia(estado, nombre, coincidencias, usuario_id)
            titulos = ", ".join(f"«{prestamo['titulo']}»" for prestamo in coincidencias[:5])
            return f"¿Cuál préstamo desea renovar? Tiene estos: {titulos}.", lista, [], None, 0
        if not coincidencias:
            return "No encontré ese préstamo entre los suyos.", lista, [], None, 0
        prestamo = coincidencias[0]
        validacion = herramientas.validar_renovacion(int(usuario_id), int(prestamo["prestamo_id"]))
        if not validacion["ok"]:
            return validacion["mensaje"], validacion, [], None, 0
        pendiente = {
            "tipo": "renovar_prestamo",
            "params": {"prestamo_id": int(prestamo["prestamo_id"])},
            "descripcion": prestamo["titulo"],
            "expira": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        }
        estado["accion_pendiente"] = pendiente
        estado["accion_tras_codigo"] = None
        estado["esperando"] = None
        return (
            f"¿Confirmo la renovación de «{prestamo['titulo']}»?",
            {"ok": True, "mensaje": "Renovación pendiente de confirmación.", "datos": prestamo},
            [],
            None,
            0,
        )
    else:
        resultado = {"ok": False, "mensaje": "No puedo realizar esa operación.", "datos": None}
        respuesta = resultado["mensaje"]
    return respuesta, resultado, _fuentes_de_resultado(nombre, resultado), None, 0


def _confirmar_pendiente(
    pendiente: dict[str, Any], usuario_id: int | None
) -> tuple[str, dict[str, Any]]:
    if usuario_id is None:
        return "Para reservar, renovar o consultar tu cuenta necesitas iniciar sesión con tu código y PIN.", {
            "ok": False,
            "mensaje": "Falta identificar al usuario.",
            "datos": None,
        }
    tipo = pendiente.get("tipo")
    params = pendiente.get("params") or {}
    if tipo == "reservar":
        resultado = herramientas.reservar(usuario_id, int(params["material_id"]))
    elif tipo == "cancelar_reserva":
        resultado = herramientas.cancelar_reserva(usuario_id, int(params["reserva_id"]))
    elif tipo == "renovar_prestamo":
        resultado = herramientas.renovar_prestamo(usuario_id, int(params["prestamo_id"]))
    else:
        resultado = {"ok": False, "mensaje": "La acción pendiente no es válida.", "datos": None}
    if tipo == "reservar" and resultado.get("ok"):
        datos = resultado.get("datos") or {}
        respuesta = (
            f"Reserva creada para «{datos.get('titulo', 'el material')}». "
            f"Vence el {fecha_es(datos['expira_en'])}."
            if datos.get("expira_en")
            else resultado["mensaje"]
        )
    elif tipo == "renovar_prestamo" and resultado.get("ok"):
        datos = resultado.get("datos") or {}
        respuesta = (
            f"«{datos.get('titulo', 'El préstamo')}» quedó renovado hasta "
            f"{fecha_es(datos['fecha_vencimiento'])}. Le quedan "
            f"{datos.get('renovaciones_restantes', 0)} renovaciones."
            if datos.get("fecha_vencimiento")
            else resultado["mensaje"]
        )
    else:
        respuesta = resultado.get("mensaje", "No fue posible completar el trámite.")
    return respuesta, resultado


def _llamada_herramienta(modelo_respuesta: Any) -> tuple[str | None, dict[str, Any]]:
    mensaje = _extraer(modelo_respuesta, "message", {})
    llamadas = _extraer(mensaje, "tool_calls", []) or []
    if not llamadas:
        return None, {}
    funcion = _extraer(llamadas[0], "function", {})
    nombre = _extraer(funcion, "name")
    argumentos = _extraer(funcion, "arguments", {})
    if isinstance(argumentos, str):
        try:
            argumentos = json.loads(argumentos)
        except json.JSONDecodeError:
            argumentos = {}
    return nombre, argumentos if isinstance(argumentos, dict) else {}


def _respuesta_error(error: Exception) -> str:
    mensaje = str(error)
    if "PostgreSQL" in mensaje or "postgres" in mensaje.lower() or "database" in mensaje.lower():
        return "No fue posible conectar con PostgreSQL. Verifique que el servicio de base de datos esté disponible."
    return mensaje or "Ocurrió un error al procesar su solicitud."


def _estudio_sin_tema(texto: str) -> bool:
    """Una recomendación para un examen necesita conocer la materia o tema."""
    normal = _normalizar(texto)
    if not re.search(r"\b(parcial|examen|evaluacion)\b", normal):
        return False
    tema = re.search(r"\b(?:de|sobre|en|estudiar)\s+(.+)", normal)
    if tema:
        generico = r"^(?:hoy|manana|ayer|lunes|martes|miercoles|jueves|viernes|sabado|domingo|la universidad|mi universidad|tus libros|la biblioteca)\b"
        if not re.search(generico, tema.group(1)):
            return False
    return True


def _guardar_seleccion_propia(estado, nombre, items, usuario):
    clave = "prestamo_id" if nombre == "renovar_prestamo" else "reserva_id"
    estado["seleccion_propia"] = {
        "usuario_id": usuario, "nombre": nombre,
        "expira": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        "items": [{"id": int(m[clave]), "titulo": str(m['titulo'])[:300]} for m in items[:5]],
    }


def _referencia_propia(texto, estado, usuario):
    lista = estado.get('seleccion_propia')
    if not lista:
        return None
    normal = _normalizar(texto).strip(' .,!¡¿?«»"')
    ordinales = {'el primero': 0, 'primero': 0, 'el segundo': 1, 'segundo': 1,
                 'el tercero': 2, 'tercero': 2, 'el cuarto': 3, 'cuarto': 3,
                 'el quinto': 4, 'quinto': 4}
    items = lista.get('items') or []
    indice = ordinales.get(normal)
    coincide = [m for m in items if _normalizar(m['titulo']) == normal]
    try:
        vigente = datetime.fromisoformat(lista['expira']) > datetime.now(timezone.utc)
    except (KeyError, ValueError, TypeError):
        vigente = False
    if usuario is None or lista.get('usuario_id') != usuario or not vigente:
        estado.pop('seleccion_propia', None)
        if indice is not None or coincide:
            return (None, {}, "La selección venció o cambió la sesión. Pide de nuevo tus préstamos o reservas.")
        return None
    if indice is not None:
        if indice >= len(items):
            return (None, {}, "Indica una opción entre las que acabo de mostrar.")
        coincide = [items[indice]]
    if len(coincide) == 1:
        item = coincide[0]
        return (lista['nombre'], {'titulo': item['titulo'], '_propia_id': item['id']}, None)
    if len(coincide) > 1:
        return (None, {}, "Hay títulos repetidos; dime el ordinal de la lista.")
    estado.pop('seleccion_propia', None)
    return None


def _pide_recomendacion_contextual(texto: str) -> bool:
    normal = re.sub(r"\s+", " ", _normalizar(texto)).strip(" .,!¡¿?")
    opciones = r"(?:(?:estos|esos)(?: libros|materiales|resultados)?|ellos|los anteriores)"
    return bool(re.fullmatch(
        rf"(?:(?:y|entonces) )?(?:(?:cual(?: de {opciones})? (?:es|seria) (?:el )?(?:mejor|mas recomendable))|"
        rf"(?:cual(?: de {opciones})? (?:(?:me )?recomiendas|me recomendarias|deberia leer))|"
        r"(?:que (?:libro|material) me recomiendas)|(?:recomiendame el mejor)|"
        rf"(?:con cual (?:empiezo|comienzo))|(?:recomiendame uno de {opciones}))"
        rf"(?: de {opciones})?"
        r"(?: para (?:(?:mi|el|un) )?(?:parcial|examen|estudiar|empezar))?", normal
    ))


def _recomendar_resultados(estado: dict[str, Any], cid: str, usuario: int | None):
    """Recomienda por afinidad de la búsqueda previa, no por una calidad inventada."""
    lista = estado.get("catalogo_contexto") or {}
    try:
        vigente = datetime.fromisoformat(lista["expira"]) > datetime.now(timezone.utc)
    except (KeyError, ValueError, TypeError):
        vigente = False
    if not vigente or lista.get("conversacion_id") != cid or lista.get("usuario_id") != usuario or not lista.get("items"):
        estado["tema_estudio_pendiente"] = True
        return "¿Sobre qué tema necesitas el libro, o entre cuáles opciones quieres elegir? Dime la materia para recomendarte algo del catálogo.", []
    items = lista["items"]
    con_afinidad = [m for m in items if isinstance(m.get("similitud"), (int, float))]
    if not con_afinidad and len(items) > 1:
        estado["tema_estudio_pendiente"] = True
        return "¿Sobre qué tema o materia necesitas la recomendación? El orden de esa lista no indica cuál es mejor para estudiar; dime el tema y afino la búsqueda.", []
    elegido = max(con_afinidad, key=lambda m: m["similitud"]) if con_afinidad else items[0]
    materiales = herramientas.enriquecer_materiales([elegido])
    if not materiales:
        return "Necesito actualizar esa búsqueda antes de recomendarte un libro. Dime el tema otra vez.", []
    material = materiales[0]
    motivo = "porque fue el resultado más relacionado con el tema de tu búsqueda" if con_afinidad else "porque es la opción que acabamos de consultar"
    respuesta = f"De las opciones que te mostré, empezaría por «{material['titulo']}», {motivo}."
    if material.get("autor"):
        respuesta += f" Su autoría corresponde a {material['autor']}."
    respuesta += f" Hay {material.get('disponibles', 0)} de {material.get('total', 0)} ejemplares disponibles."
    lista["items"] = [elegido]
    lista["expira"] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    return respuesta, materiales


def _referencia_catalogo(texto: str, estado: dict[str, Any], cid: str, usuario: int | None):
    """Referencia cerrada; nunca inferir un primer resultado entre varias opciones."""
    normal = _normalizar(texto).strip(" .,!¡¿?")
    patron = (r"(?:(?P<accion>reserva|reservar|esta disponible|hay disponible)\s+)?"
              r"(?:el\s+)?(?P<ref>primero|segundo|tercero|cuarto|quinto|ese libro|este libro|ese|este)")
    match = re.fullmatch(patron, normal)
    if not match:
        return None
    lista = estado.get("catalogo_contexto") or {}
    try:
        vigente = datetime.fromisoformat(lista["expira"]) > datetime.now(timezone.utc)
    except (KeyError, ValueError, TypeError):
        vigente = False
    items = lista.get("items") or []
    if not vigente or lista.get("conversacion_id") != cid or lista.get("usuario_id") != usuario or not items:
        return (None, {}, "Necesito una búsqueda reciente en esta conversación. Dime el título o el tema.")
    ordinales = {"primero": 0, "segundo": 1, "tercero": 2, "cuarto": 3, "quinto": 4}
    indice = ordinales.get(match['ref'])
    if indice is None:
        if len(items) != 1:
            return (None, {}, "¿Cuál de los resultados? Dime primero, segundo o el título completo.")
        indice = 0
    if indice >= len(items):
        return (None, {}, "Ese número no está entre los resultados. Indica una opción de la lista.")
    item = items[indice]
    nombre = "reservar" if match['accion'] in ("reserva", "reservar") else "consultar_disponibilidad"
    return (nombre, {"titulo": item['titulo'], "_referencia_id": item['material_id']}, None)


def _candidato_referido(argumentos: dict[str, Any], estado: dict[str, Any]):
    """Usado solo después de resolver la referencia local, revalidada y acotada."""
    referencia = argumentos.get("_referencia_id")
    lista = estado.get("catalogo_contexto") or {}
    try:
        vigente = datetime.fromisoformat(lista["expira"]) > datetime.now(timezone.utc)
    except (KeyError, ValueError, TypeError):
        vigente = False
    if referencia is not None and vigente:
        for item in lista.get("items", []):
            if item['material_id'] == referencia and item['titulo'] == argumentos.get('titulo'):
                return {"ok": True, "datos": [item]}
    return {"ok": False, "datos": [], "mensaje": "Repite la búsqueda para seleccionar ese material."}


def procesar_mensaje(
    texto: str,
    conversacion_id: str | None = None,
    modo_voz: bool = False,
    t_stt_ms: int | None = None,
    usuario_sesion: dict[str, Any] | None = None,
    sala: str | None = None,
) -> dict[str, Any]:
    """Procesa un turno completo y registra estado, mensajes y tiempos."""
    texto = normalizar_consulta(texto)
    inicio_total = perf_counter()
    identificador: str | None = None
    usuario_id: int | None = None
    estado: dict[str, Any] = {
        "usuario_id": None,
        "accion_pendiente": None,
        "esperando": None,
        "accion_tras_codigo": None,
        "sala": None,
    }
    respuesta = ""
    intencion = "fuera_de_dominio"
    herramienta_usada: str | None = None
    fuentes: list[dict[str, Any]] = []
    herramienta_resultado: dict[str, Any] | None = None
    materiales: list[dict[str, Any]] = []
    error_texto: str | None = None
    bibliografia_datos: dict[str, Any] | None = None
    avisos: dict[str, Any] | None = None
    requiere_login = False
    sesion_iniciada = False
    entrada_oculta = False
    token_sesion = None
    salas_opciones: list[dict[str, Any]] | None = None
    sugerencia_sala: dict[str, Any] | None = None
    entrada_oculta = pin_explicito(texto)
    entrada_segura = "[PIN oculto]" if entrada_oculta else texto
    tiempos: dict[str, int | None] = {
        "t_stt_ms": t_stt_ms,
        "t_embedding_ms": None,
        "t_busqueda_ms": None,
        "t_llm_ms": None,
        "t_tts_ms": None,
        "t_total_ms": None,
    }
    try:
        identificador, usuario_id, estado = _cargar_conversacion(
            conversacion_id, modo_voz, usuario_sesion
        )
        if usuario_sesion is not None:
            usuario_id = int(usuario_sesion["id"])
            estado["usuario_id"] = usuario_id
            estado["esperando"] = None
            estado["codigo_login"] = None
            estado["accion_tras_login"] = None
        estado.setdefault("usuario_id", usuario_id)
        estado.setdefault("accion_pendiente", None)
        estado.setdefault("esperando", None)
        estado.setdefault("accion_tras_codigo", None)
        estado.setdefault("codigo_login", None)
        estado.setdefault("accion_tras_login", None)
        estado.setdefault("sala", None)
        if usuario_sesion is None:
            estado["accion_pendiente"] = None
        usuario_id = (
            int(usuario_sesion["id"])
            if usuario_sesion is not None
            else estado.get("usuario_id", usuario_id)
        )

        if sala is not None:
            sala_param = str(sala).strip().lower()
            if sala_param in ("", "todas", "toda", "general", "null", "none"):
                estado["sala"] = None
            else:
                s_obj = salas.sala_por_slug(sala_param) or salas.sala_por_slug(_detectar_area_sala(sala_param))
                if s_obj:
                    estado["sala"] = s_obj["slug"]
        sala_actual_slug = estado.get("sala")
        normal_turno = _normalizar(texto)
        if not entrada_oculta and re.search(r"\bno\s+(?:(?:quiero|deseo|necesito)\s+)?reservar\b", normal_turno):
            estado["accion_pendiente"] = None
            intencion = "cancelar_accion"
            respuesta = "De acuerdo, no prepararé ninguna reserva. Puedes consultar la disponibilidad indicando el título."
        if not entrada_oculta and re.search(r"\b(?:si no hay|si esta en espera|si toca esperar)\b", normal_turno) and re.search(r"\b(?:no|sin)\b.*\b(?:espera|esperar|cola|reserv)\w*", normal_turno):
            estado["accion_pendiente"] = None
            intencion = "aclarar_reserva"
            respuesta = "Entendido: no aceptaré una solicitud en espera. Consulta primero la disponibilidad del título; cualquier reserva requerirá otra confirmación."
        if entrada_oculta and (estado.get("esperando") != "pin" or not estado.get("codigo_login")):
            intencion = "identificacion_segura"
            respuesta = "Para enviar tu PIN, inicia primero el flujo seguro con tu código o el botón Iniciar sesión."
        if not respuesta and estado.get("esperando") == "pin":
            pin = extraer_pin(texto)
            if pin is not None and estado.get("codigo_login"):
                entrada_oculta = True
                entrada_segura = "[PIN oculto]"
                login = auth.iniciar_sesion(estado.get("codigo_login") or "", pin, "chat")
                intencion = "identificacion_segura"
                if login["ok"]:
                    usuario_sesion = login["usuario"]
                    usuario_id = int(usuario_sesion["id"])
                    estado["usuario_id"] = usuario_id
                    sesion_iniciada = True
                    token_sesion = login["token"]
                    avisos = login["avisos"]
                    respuesta = login["mensaje_bienvenida"]
                    estado["esperando"] = None
                    estado["codigo_login"] = None
                    accion = estado.pop("accion_tras_login", None)
                    if accion:
                        detalle, herramienta_resultado, fuentes, error_texto, _ = _ejecutar_herramienta(
                            accion["nombre"], accion["argumentos"], usuario_id, estado, sala_slug=sala_actual_slug
                        )
                        herramienta_usada = accion["nombre"]
                        respuesta += " " + detalle
                else:
                    respuesta = login["mensaje"]
                    if login.get("intentos_restantes") is not None and "Te quedan" not in respuesta:
                        respuesta += f" Te quedan {login['intentos_restantes']} intentos."
            elif pin_explicito(texto) or palabras_a_numero(texto) is not None:
                entrada_oculta = True
                entrada_segura = "[PIN oculto]"
                intencion = "identificacion_segura"
                respuesta = "El PIN debe tener 4 dígitos. Inténtalo de nuevo o di cancelar."
            else:
                estado["esperando"] = None
                estado["codigo_login"] = None
                estado["accion_tras_login"] = None
        _guardar_mensaje(identificador, "user", entrada_segura)

        pendiente = estado.get("accion_pendiente")
        if pendiente and not respuesta:
            try:
                expiracion = datetime.fromisoformat(pendiente.get("expira", ""))
                if expiracion.tzinfo is None:
                    expiracion = expiracion.replace(tzinfo=timezone.utc)
                vigente = expiracion >= datetime.now(timezone.utc)
            except (TypeError, ValueError):
                vigente = False
            if not vigente:
                estado["accion_pendiente"] = None
            elif _es_afirmativo(texto):
                respuesta, herramienta_resultado = _confirmar_pendiente(pendiente, usuario_id)
                error_texto = _es_error_tecnico(herramienta_resultado)
                herramienta_usada = pendiente.get("tipo")
                intencion = f"{herramienta_usada} (confirmación)"
                estado["accion_pendiente"] = None
                estado["accion_tras_codigo"] = None
                estado["esperando"] = None
            elif _es_negativo(texto):
                estado["accion_pendiente"] = None
                intencion = "cancelar_accion"
                respuesta = "De acuerdo, cancelé la operación."
            else:
                intencion = "aclarar_confirmacion"
                respuesta = "La operación sigue pendiente. Dime sí para confirmar o no para cancelar."

        # Manejo de desambiguación pendiente (ej. tras listar varias opciones para reservar o consultar)
        if not respuesta and (desambiguacion := estado.get("desambiguacion_pendiente")):
            try:
                exp_d = datetime.fromisoformat(desambiguacion.get("expira", ""))
                if exp_d.tzinfo is None:
                    exp_d = exp_d.replace(tzinfo=timezone.utc)
                vigente_d = exp_d >= datetime.now(timezone.utc)
            except (TypeError, ValueError):
                vigente_d = False

            if not vigente_d:
                estado.pop("desambiguacion_pendiente", None)
            else:
                normal_d = _normalizar(texto).strip(" ¿?!¡.,:;")
                if _es_negativo(texto) or normal_d in (
                    "no", "ninguno", "ninguna", "cancelar", "cancela",
                    "olvidalo", "olvidelo", "olvídelo", "olvídalo",
                    "ya no", "nada", "dejar asi", "dejarlo asi",
                ):
                    estado.pop("desambiguacion_pendiente", None)
                    estado.pop("catalogo_contexto", None)
                    intencion = "cancelar_accion (rápido)"
                    tiempos["t_llm_ms"] = 0
                    respuesta = "De acuerdo, lo dejamos así."
                    herramienta_resultado = {"ok": True, "mensaje": respuesta, "datos": None}
                else:
                    items_d = desambiguacion.get("items", [])
                    item_elegido = None
                    ordinal_map = {
                        "primero": 0, "primera": 0, "el primero": 0, "la primera": 0, "1": 0, "el 1": 0,
                        "segundo": 1, "segunda": 1, "el segundo": 1, "la segunda": 1, "2": 1, "el 2": 1,
                        "tercero": 2, "tercera": 2, "el tercero": 2, "la tercera": 2, "3": 2, "el 3": 2,
                        "cuarto": 3, "cuarta": 3, "el cuarto": 3, "la cuarta": 3, "4": 3, "el 4": 3,
                        "quinto": 4, "quinta": 4, "el quinto": 4, "la quinta": 4, "5": 4, "el 5": 4,
                    }
                    if normal_d in ordinal_map:
                        idx = ordinal_map[normal_d]
                        if idx < len(items_d):
                            item_elegido = items_d[idx]
                    else:
                        palabra_c = re.sub(r"^(?:el\s+de|la\s+de|el\s+libro\s+de|el\s+|la\s+|autor)\s+", "", normal_d).strip()
                        for it in items_d:
                            autor_it = _normalizar(str(it.get("autor") or ""))
                            titulo_it = _normalizar(str(it.get("titulo") or ""))
                            if palabra_c and (palabra_c in autor_it or palabra_c in titulo_it):
                                item_elegido = it
                                break
                    if item_elegido:
                        estado.pop("desambiguacion_pendiente", None)
                        tipo_accion = desambiguacion.get("tipo", "reservar")
                        intencion = f"{tipo_accion} (rápido)"
                        herramienta_usada = tipo_accion
                        tiempos["t_llm_ms"] = 0
                        args = {"titulo": item_elegido["titulo"], "_referencia_id": item_elegido.get("material_id")}
                        respuesta, herramienta_resultado, fuentes, error_texto, _ = _ejecutar_herramienta(
                            tipo_accion, args, usuario_id, estado, sala_slug=sala_actual_slug
                        )

        if not respuesta:
            contextual = re.match(r"^(?:mi codigo(?: es| les)?|codigo(?: es| les)?|soy el)\s+", _normalizar(texto))
            codigo_encontrado = extraer_codigo(texto) if contextual or estado.get("esperando") == "codigo" else None
            if codigo_encontrado:
                estado["accion_pendiente"] = None
                estado["accion_tras_codigo"] = None
                estado["esperando"] = None
                if usuario_sesion is not None:
                    respuesta = f"Ya iniciaste sesión como {usuario_sesion['nombre']}."
                else:
                    estado["esperando"] = "pin"
                    estado["codigo_login"] = codigo_encontrado
                    respuesta = "Gracias. Ahora dime tu PIN de 4 dígitos."
                intencion = "identificacion_segura"
            elif usuario_sesion is not None and re.search(r"\busuario\s+\d{3,10}\b", _normalizar(texto)):
                intencion = "identificacion_segura"
                respuesta = f"Ya iniciaste sesión como {usuario_sesion['nombre']}. Solo puedo consultar tu propia cuenta."
            elif _es_quitar_sala(texto):
                intencion = "elegir_sala (rápido)"
                estado["sala"] = None
                sala_actual_slug = None
                respuesta = "Ahora estamos consultando en toda la biblioteca. ¿Qué buscas?"
                salas_opciones = None
                sugerencia_sala = None
            elif _es_consulta_salas(texto):
                intencion = "elegir_sala (rápido)"
                opciones = [salas.opcion_sala(s) for s in salas.listar_salas()]
                salas_opciones = opciones
                respuesta = (
                    "Tenemos 5 salas temáticas: Sala de Ingeniería y Tecnología, "
                    "Sala de Ciencias Agrarias y Ambientales, Sala de Administración y Negocios, "
                    "Sala de Contaduría y Finanzas, y Sala de Investigación y Escritura. "
                    "¿A cuál te gustaría ir?"
                )
                sugerencia_sala = None
            elif (slug_elegido := _es_intencion_elegir_sala(texto)) is not None:
                estado["sala"] = slug_elegido
                sala_actual_slug = slug_elegido
                sala_info = salas.sala_por_slug(slug_elegido)
                intencion = f"elegir_sala (rápido) · sala {slug_elegido}"
                bibliotecario = sala_info["bibliotecario"]["nombre"]
                nombre_sala = sala_info["nombre"]
                libros = sala_info["libros"]
                tesis = sala_info["tesis"]
                total = sala_info.get("total", libros + tesis)
                nombre_usuario = usuario_sesion.get("nombre") if usuario_sesion else None
                saludo_prefijo = f"Hola, {nombre_usuario}." if nombre_usuario else "Hola."
                conteo_frase = salas.formato_conteo_materiales(libros, tesis, total)
                respuesta = (
                    f"{saludo_prefijo} Soy {bibliotecario}, de la {nombre_sala}. "
                    f"{conteo_frase} ¿Qué buscas?"
                )
                salas_opciones = None
                sugerencia_sala = None
            elif _es_saludo_puro(texto):
                intencion = "saludo (rápido)"
                if sala_actual_slug:
                    sala_info = salas.sala_por_slug(sala_actual_slug)
                    bibliotecario = sala_info["bibliotecario"]["nombre"]
                    nombre_sala = sala_info["nombre"]
                    respuesta = f"¡Hola! Soy {bibliotecario}, de la {nombre_sala}. ¿Qué buscas hoy?"
                else:
                    respuesta = (
                        "¡Hola! Puedo ayudarle a buscar libros y otros materiales, consultar "
                        "disponibilidad, revisar préstamos y multas, hacer reservas y responder "
                        "preguntas sobre el reglamento y la citación."
                    )
            elif _estudio_sin_tema(texto):
                estado["tema_estudio_pendiente"] = True
                intencion = "aclarar_tema_estudio (rápido)"
                respuesta = "¿De qué materia o tema es el parcial? Por ejemplo: redes, contabilidad o ecología. Así puedo recomendarte libros del catálogo para estudiar."

        if not respuesta and estado.get("tema_estudio_pendiente"):
            estado["tema_estudio_pendiente"] = False
            if _es_negativo(texto):
                intencion = "cancelar_accion (rápido)"
                respuesta = "De acuerdo. Cuando quieras, dime qué tema necesitas estudiar."
            elif _es_afirmativo(texto):
                estado["tema_estudio_pendiente"] = True
                intencion = "aclarar_tema_estudio (rápido)"
                respuesta = "Dime la materia o el tema del parcial para poder recomendarte un libro."
            elif intencion_por_palabras(texto) == "fuera_de_dominio" and re.match(r"^(?:¿|como\b|que\b|cual\b|cuando\b|donde\b|por que\b|a que\b)", _normalizar(texto).strip()):
                intencion = "aclarar_tema_estudio (rápido)"
                respuesta = "Podemos cambiar de consulta. Formula tu pregunta completa, o dime la materia del parcial."
                estado["tema_estudio_pendiente"] = True
            elif intencion_por_palabras(texto) in ("fuera_de_dominio", "buscar_semantico") and not _pregunta_fuera_de_dominio(texto):
                tema = re.sub(r"(?i)^(?:de|sobre)\s+", "", texto.strip())
                texto = f"Busco libros sobre {tema} para estudiar"

        if not respuesta and _pide_recomendacion_contextual(texto):
            respuesta, materiales = _recomendar_resultados(estado, identificador, usuario_id)
            intencion = "recomendar_contexto (rápido)" if materiales else "aclarar_recomendacion (rápido)"
            herramienta_usada = "recomendar_contexto" if materiales else None

        referencia = None
        if not respuesta:
            referencia = _referencia_propia(texto, estado, usuario_id)
            if referencia is None:
                referencia = _referencia_catalogo(texto, estado, identificador, usuario_id)
            if referencia and referencia[2]:
                intencion = "aclarar_material (rápido)"
                respuesta = referencia[2]

        if not respuesta:
            llamada_nombre: str | None = None
            argumentos: dict[str, Any] = {}
            origen_herramienta = "rápido"

            if referencia:
                llamada_nombre, argumentos, _ = referencia
                if "_propia_id" in argumentos:
                    estado.pop("seleccion_propia", None)
                origen_herramienta = "rápido"
                tiempos["t_llm_ms"] = 0
            else:
                estado.pop("catalogo_contexto", None)
                palabras = intencion_por_palabras(texto)
                es_fuera_dominio = _pregunta_fuera_de_dominio(texto)

                if es_fuera_dominio:
                    llamada_nombre = None
                    origen_herramienta = "rápido"
                    tiempos["t_llm_ms"] = 0
                elif palabras != "fuera_de_dominio":
                    # Enrutador rápido: intención identificada con confianza por reglas deterministas
                    llamada_nombre = palabras
                    origen_herramienta = "rápido"
                    tiempos["t_llm_ms"] = 0
                    argumentos = {}

                    if llamada_nombre == "presentacion":
                        argumentos = {}
                    elif llamada_nombre == "cortesia":
                        _, tipo_c = _es_cortesia(texto)
                        argumentos = {"tipo": tipo_c}
                    elif llamada_nombre == "panorama_catalogo":
                        argumentos = {}
                    elif llamada_nombre == "mas_prestados":
                        argumentos = {}
                    elif llamada_nombre == "ubicacion_material":
                        _, tit_ub = _extraer_peticion_ubicacion(texto)
                        argumentos = {"titulo": tit_ub or _titulo_material(texto)}
                    elif llamada_nombre == "recomendar":
                        _, tema_rec = _extraer_peticion_recomendacion(texto)
                        argumentos = {"tema": tema_rec}
                    elif llamada_nombre == "buscar_exacto":
                        argumentos = {"texto": _titulo_material(texto)}
                    elif llamada_nombre in ("consultar_disponibilidad", "reservar"):
                        argumentos = {"titulo": _titulo_material(texto)}
                    elif llamada_nombre == "cancelar_reserva":
                        argumentos = {"titulo": _titulo_cancelacion(texto)}
                    elif llamada_nombre == "renovar_prestamo":
                        argumentos = {"titulo": _titulo_renovacion(texto)}
                    elif llamada_nombre == "consultar_recogida":
                        argumentos = {"titulo": texto}
                    elif llamada_nombre == "consultar_prestamos_y_multas":
                        argumentos = {}
                    elif llamada_nombre == "responder_con_documentos":
                        argumentos = {"pregunta": texto}
                    elif llamada_nombre == "resumir_material":
                        argumentos = {
                            "titulo": _titulo_resumen_material(texto),
                            "pregunta": texto,
                        }
                    elif llamada_nombre == "generar_bibliografia":
                        argumentos = _extraer_peticion_bibliografia(texto) or {
                            "tema": texto,
                            "cantidad": 5,
                            "norma": "APA",
                        }
                    elif llamada_nombre == "buscar_semantico":
                        argumentos = {"consulta": texto}
                else:
                    # Frase ambigua: llamada de tool calling al LLM con historial acotado (2 turnos) y prompt breve (<600 chars)
                    sala_info_actual = salas.sala_por_slug(sala_actual_slug)
                    mensajes = [{"role": "system", "content": _prompt_sistema(sala_info_actual)}]
                    mensajes.extend(_mensaje_historial(identificador))
                    try:
                        salida_modelo, tiempo_llm = _llamar_modelo(
                            mensajes, con_herramientas=True, num_predict=NUM_PREDICT_TOOL_CALLING
                        )
                        tiempos["t_llm_ms"] = round(tiempo_llm)
                        llamada_nombre, argumentos = _llamada_herramienta(salida_modelo)
                        if llamada_nombre not in _HERRAMIENTAS:
                            llamada_nombre = None
                        origen_herramienta = "llm" if llamada_nombre else "rápido"
                    except Exception as error:
                        error_texto = str(error)
                        origen_herramienta = "rápido"

            # No aceptar IDs internos del modelo: solo los resueltos en este turno.
            argumentos.pop("_referencia_id", None)
            argumentos.pop("_propia_id", None)

            if llamada_nombre is None:
                intencion = f"fuera_de_dominio ({origen_herramienta})"
                respuesta = "Solo puedo ayudar con la biblioteca: buscar material, préstamos, reservas, reglamento y citación."
                if error_texto and "modelo de lenguaje no está disponible" in error_texto:
                    respuesta = "El modelo de lenguaje no está disponible; inicie Ollama. " + respuesta
            else:
                intencion = f"{llamada_nombre} ({origen_herramienta})"
                herramienta_usada = llamada_nombre
                requiere_login = (
                    usuario_sesion is None
                    and llamada_nombre in {
                        "consultar_recogida",
                        "reservar",
                        "renovar_prestamo",
                        "cancelar_reserva",
                        "consultar_prestamos_y_multas",
                    }
                )
                respuesta, herramienta_resultado, fuentes, error_herramienta, tiempo_redaccion = _ejecutar_herramienta(
                    llamada_nombre, argumentos, usuario_id, estado, sala_slug=sala_actual_slug
                )
                if herramienta_resultado and herramienta_resultado.get("sugerencia_sala"):
                    sugerencia_sala = herramienta_resultado["sugerencia_sala"]
                if (
                    llamada_nombre == "buscar_semantico"
                    and origen_herramienta == "llm"
                    and not (herramienta_resultado or {}).get("datos")
                    and not sugerencia_sala
                ):
                    intencion = "fuera_de_dominio (llm)"
                    herramienta_usada = None
                    respuesta = "Solo puedo ayudar con la biblioteca: buscar material, préstamos, reservas, reglamento y citación."
                if tiempo_redaccion:
                    tiempos["t_llm_ms"] = (tiempos.get("t_llm_ms") or 0) + round(tiempo_redaccion)
                if error_herramienta:
                    error_texto = error_texto or error_herramienta
                if herramienta_resultado:
                    error_texto = error_texto or _es_error_tecnico(herramienta_resultado)
                    tiempos_rag = herramienta_resultado.get("tiempos", {})
                    for llave in ("t_embedding_ms", "t_busqueda_ms"):
                        if tiempos_rag.get(llave) is not None:
                            tiempos[llave] = round(tiempos_rag[llave])

        if herramienta_usada == "generar_bibliografia":
            datos_bibliografia = (herramienta_resultado or {}).get("datos")
            mensaje_bibliografia = str((herramienta_resultado or {}).get("mensaje") or "")
            if isinstance(datos_bibliografia, dict) and (
                (herramienta_resultado or {}).get("ok")
                or "No encontré material del acervo" in mensaje_bibliografia
            ):
                bibliografia_datos = {
                    "norma": datos_bibliografia.get("norma", "APA"),
                    "tema": datos_bibliografia.get("tema", ""),
                    "referencias": datos_bibliografia.get("referencias", []),
                }

        if not sala_actual_slug and not salas_opciones and not sugerencia_sala and herramienta_usada in ("buscar_semantico", "buscar_exacto"):
            area_slug = _detectar_area_sala(texto)
            if area_slug:
                sala_prop = salas.sala_por_slug(area_slug)
                if sala_prop:
                    salas_opciones = [salas.opcion_sala(s) for s in salas.listar_salas()]
                    respuesta += (
                        f"\n\n¿Quieres ir a la {sala_prop['nombre']}? "
                        f"Ahí está todo lo de {sala_prop['descripcion']}."
                    )

        respuesta = _limpiar_respuesta(respuesta)
        if herramienta_usada in {
            "buscar_semantico",
            "buscar_exacto",
            "consultar_disponibilidad",
            "panorama_catalogo",
            "mas_prestados",
            "ubicacion_material",
            "recomendar",
        }:
            datos = (herramienta_resultado or {}).get("materiales") or (herramienta_resultado or {}).get("datos")
            candidatos = datos if isinstance(datos, list) else (
                [datos] if isinstance(datos, dict) and datos.get("material_id") else []
            )
            materiales = herramientas.enriquecer_materiales(candidatos)
            if herramienta_usada == "buscar_exacto":
                for material in materiales:
                    material["similitud"] = None
        elif herramienta_usada == "resumir_material":
            materiales = (herramienta_resultado or {}).get("materiales") or []
        if herramienta_usada in {
            "buscar_semantico",
            "buscar_exacto",
            "consultar_disponibilidad",
            "panorama_catalogo",
            "mas_prestados",
            "ubicacion_material",
            "recomendar",
        }:
            items = [{"material_id": int(m["material_id"]), "titulo": str(m["titulo"])[:300], "similitud": m.get("similitud")}
                     for m in materiales[:5] if m.get("material_id") and m.get("titulo")]
            estado["catalogo_contexto"] = {
                "conversacion_id": identificador, "usuario_id": usuario_id,
                "expira": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                "items": items,
                "origen": herramienta_usada,
            }
    except Exception as error:
        error_texto = error_texto or str(error)
        respuesta = _respuesta_error(error)
        intencion = "error"

    tiempos["t_total_ms"] = round((perf_counter() - inicio_total) * 1000)
    respuesta_voz = limpiar_para_voz(_pesos_en_voz(respuesta))
    if herramienta_usada == "responder_con_documentos" and re.search(r"(?m)^APA\n", respuesta) and re.search(r"(?m)^IEEE\n", respuesta):
        secciones = re.split(r"(?m)^(APA|IEEE)\s*\n", respuesta)
        resumenes = []
        for indice in range(1, len(secciones), 2):
            cuerpo = limpiar_para_voz(secciones[indice + 1])
            frases = re.split(r"(?<=[.!?])\s+", cuerpo)
            clave = r"autor.fecha" if secciones[indice] == "APA" else r"corchetes"
            resumen = next((f for f in frases if re.search(clave, _normalizar(f))), frases[0])
            resumenes.append(secciones[indice] + ": " + resumen)
        respuesta_voz = " ".join(resumenes)
    if bibliografia_datos:
        referencias_voz = bibliografia_datos.get("referencias") or []
        if referencias_voz:
            titulos = [
                re.sub(r"[\[\]_*#<>|]", "", str(ref.get("titulo", ""))).strip()
                for ref in referencias_voz[:5]
            ]
            cant_ref_voz = len(referencias_voz)
            texto_ref_voz = "1 referencia" if cant_ref_voz == 1 else f"{cant_ref_voz} referencias"
            respuesta_voz = (
                f"Encontré {texto_ref_voz} en formato "
                f"{bibliografia_datos.get('norma', 'APA')}. Los títulos son: "
                + "; ".join(titulo for titulo in titulos if titulo)
            )
        else:
            respuesta_voz = "No encontré material del acervo sobre ese tema para armar la bibliografía."
    sala_actual_slug = estado.get("sala")
    if sala_actual_slug and not intencion.endswith(f" · sala {sala_actual_slug}"):
        intencion = f"{intencion} · sala {sala_actual_slug}"

    sala_info_final = salas.sala_por_slug(sala_actual_slug)
    sala_serializada = (
        {
            "slug": sala_info_final["slug"],
            "nombre": sala_info_final["nombre"],
            "bibliotecario": sala_info_final["bibliotecario"],
        }
        if sala_info_final
        else None
    )

    resultado = {
        "conversacion_id": identificador or conversacion_id,
        "respuesta": respuesta,
        "respuesta_voz": respuesta_voz,
        "intencion": intencion,
        "herramienta": herramienta_usada,
        "fuentes": fuentes,
        "materiales": materiales,
        "bibliografia": bibliografia_datos,
        "avisos": avisos,
        "accion_pendiente": (
            {
                "tipo": estado["accion_pendiente"].get("tipo"),
                "descripcion": estado["accion_pendiente"].get("descripcion"),
                "aviso": estado["accion_pendiente"].get("aviso"),
            }
            if estado.get("accion_pendiente")
            else None
        ),
        "usuario": None,
        "tiempos": tiempos,
        "error": error_texto,
        "bitacora_id": None,
        "requiere_login": requiere_login,
        "esperando": estado.get("esperando"),
        "sesion_iniciada": sesion_iniciada,
        "entrada_oculta": entrada_oculta,
        "sala": sala_serializada,
        "salas_opciones": salas_opciones,
        "sugerencia_sala": sugerencia_sala,
    }
    try:
        if identificador:
            if usuario_id is not None:
                with conexion() as conn, conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT codigo, nombre, tipo, programa FROM public.usuarios WHERE id = %s",
                        (usuario_id,),
                    )
                    usuario = cursor.fetchone()
                if usuario:
                    resultado["usuario"] = {
                        "codigo": usuario[0],
                        "nombre": usuario[1],
                        "tipo": usuario[2],
                        "programa": usuario[3],
                    }
            resultado["bitacora_id"] = _guardar_turno(
                identificador,
                usuario_id,
                estado,
                entrada_segura,
                respuesta,
                error_texto,
                modo_voz,
                intencion,
                herramienta_usada,
                fuentes,
                herramienta_resultado,
                tiempos,
            )
    except Exception as error:
        resultado["error"] = resultado["error"] or _respuesta_error(error)
        resultado["respuesta"] = resultado["respuesta"] or _respuesta_error(error)
        resultado["respuesta_voz"] = limpiar_para_voz(resultado["respuesta"])
    if token_sesion:
        resultado["token_sesion"] = token_sesion
    return resultado
