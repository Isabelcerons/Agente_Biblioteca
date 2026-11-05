"""Búsqueda semántica y exacta sobre el conocimiento de la biblioteca."""

from time import perf_counter
from typing import Any

import ollama
from pgvector import Vector
from psycopg import Error as PsycopgError

from app.config import EMBED_MODEL, KEEP_ALIVE, OLLAMA_HOST, TOP_K
from app.db import conexion

PREFIJO_CONSULTA = "task: search result | query: {texto}"
PREFIJO_DOCUMENTO = "title: {titulo} | text: {texto}"
_CLIENTE = ollama.Client(host=OLLAMA_HOST)
_DIMENSIONES = 768


def _crear_embeddings(textos: list[str]) -> list[list[float]]:
    """Solicita embeddings al servicio local y comprueba su dimensión."""
    try:
        # keep_alive largo: el modelo de embeddings queda en memoria junto al LLM
        respuesta = _CLIENTE.embed(model=EMBED_MODEL, input=textos, keep_alive=KEEP_ALIVE)
    except Exception as error:
        detalle = str(error).lower()
        if any(marca in detalle for marca in ("not found", "model not found", "404")):
            raise RuntimeError(
                f"No está disponible el modelo de embeddings {EMBED_MODEL!r}; "
                f"descárguelo con «ollama pull {EMBED_MODEL}»."
            ) from error
        raise RuntimeError(
            "No fue posible solicitar embeddings a Ollama. Verifique el "
            "servicio con «ollama serve» y la variable OLLAMA_HOST."
        ) from error

    vectores = respuesta.embeddings
    if len(vectores) != len(textos):
        raise RuntimeError("Ollama devolvió una cantidad inesperada de embeddings.")
    if any(len(vector) != _DIMENSIONES for vector in vectores):
        raise RuntimeError(
            f"Se esperaban embeddings de {_DIMENSIONES} dimensiones; "
            "revise que EMBED_MODEL sea compatible con pgvector."
        )
    return [list(vector) for vector in vectores]


def embed_documentos(
    lista_textos: list[str], lista_titulos: list[str | None]
) -> list[list[float]]:
    """Genera embeddings de documentos en lotes de hasta dieciséis textos."""
    if len(lista_textos) != len(lista_titulos):
        raise ValueError("Cada texto debe tener un título correspondiente.")
    entradas = [
        PREFIJO_DOCUMENTO.format(titulo=titulo or "none", texto=texto)
        for texto, titulo in zip(lista_textos, lista_titulos, strict=True)
    ]
    vectores: list[list[float]] = []
    for inicio in range(0, len(entradas), 16):
        vectores.extend(_crear_embeddings(entradas[inicio : inicio + 16]))
    return vectores


def embed_consulta(texto: str) -> list[float]:
    """Genera el vector de una consulta de búsqueda."""
    return _crear_embeddings([PREFIJO_CONSULTA.format(texto=texto)])[0]


def buscar_fragmentos(
    consulta: str, k: int = TOP_K, tipos: list[str] | None = None,
    secciones: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Recupera los fragmentos más cercanos y mide embedding y consulta SQL."""
    inicio = perf_counter()
    vector = Vector(embed_consulta(consulta))
    t_embedding_ms = (perf_counter() - inicio) * 1000

    sql = """
        SELECT f.id, f.texto, f.seccion, f.orden, d.titulo AS documento, d.tipo,
               d.fuente, d.material_id,
               1 - (f.embedding <=> %s::vector) AS similitud
        FROM conocimiento.fragmentos AS f
        JOIN conocimiento.documentos AS d ON d.id = f.documento_id
    """
    parametros: list[Any] = [vector]
    if tipos:
        sql += " WHERE d.tipo = ANY(%s)"
        parametros.append(tipos)
    if secciones:
        sql += (" AND " if tipos else " WHERE ") + "f.seccion = ANY(%s)"
        parametros.append(secciones)
    sql += " ORDER BY f.embedding <=> %s::vector LIMIT %s"
    parametros.extend((vector, k))

    inicio = perf_counter()
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(sql, parametros)
            columnas = [columna.name for columna in cursor.description]
            resultados = [dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()]
    except PsycopgError as error:
        raise RuntimeError(
            "No fue posible consultar los fragmentos en PostgreSQL; "
            "verifique el esquema conocimiento y la extensión pgvector."
        ) from error
    tiempos = {
        "t_embedding_ms": t_embedding_ms,
        "t_busqueda_ms": (perf_counter() - inicio) * 1000,
    }
    return resultados, tiempos


def buscar_materiales_semantico(
    consulta: str, k: int = TOP_K
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Agrupa los mejores resúmenes o reseñas y añade disponibilidad real."""
    inicio = perf_counter()
    vector = Vector(embed_consulta(consulta))
    t_embedding_ms = (perf_counter() - inicio) * 1000
    sql = """
        WITH mejores AS (
            SELECT DISTINCT ON (d.material_id)
                   d.material_id, 1 - (f.embedding <=> %s::vector) AS similitud
            FROM conocimiento.fragmentos AS f
            JOIN conocimiento.documentos AS d ON d.id = f.documento_id
            WHERE d.tipo = ANY(%s) AND d.material_id IS NOT NULL
            ORDER BY d.material_id, f.embedding <=> %s::vector
        )
        SELECT v.material_id, v.titulo, v.autor, v.tipo, catalogo.anio,
               v.disponibles, v.total, mejores.similitud
        FROM mejores
        JOIN public.v_disponibilidad AS v
          ON v.material_id = mejores.material_id
        JOIN public.material AS catalogo
          ON catalogo.id = mejores.material_id
        ORDER BY mejores.similitud DESC
        LIMIT %s
    """
    inicio = perf_counter()
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(sql, (vector, ["resumen_tesis", "resena_libro"], vector, k))
            columnas = [columna.name for columna in cursor.description]
            resultados = [dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()]
    except PsycopgError as error:
        raise RuntimeError(
            "No fue posible consultar los materiales semánticos en PostgreSQL; "
            "verifique conocimiento y public.v_disponibilidad."
        ) from error
    tiempos = {
        "t_embedding_ms": t_embedding_ms,
        "t_busqueda_ms": (perf_counter() - inicio) * 1000,
    }
    return resultados, tiempos


def buscar_fragmentos_material(
    material_id: int, consulta: str, limite_completa: int = 3
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Recupera el resumen completo del material y sus páginas más relevantes."""
    inicio = perf_counter()
    vector = Vector(embed_consulta(consulta))
    t_embedding_ms = (perf_counter() - inicio) * 1000
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.texto, f.seccion, d.titulo AS documento,
                       d.tipo, d.fuente, d.material_id, f.orden,
                       NULL::real AS similitud
                FROM conocimiento.fragmentos AS f
                JOIN conocimiento.documentos AS d ON d.id = f.documento_id
                WHERE d.material_id = %s
                  AND d.tipo = ANY(%s)
                ORDER BY d.fuente, f.orden
                """,
                (material_id, ["resumen_tesis", "resena_libro"]),
            )
            columnas = [columna.name for columna in cursor.description]
            resultados = [
                dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT f.texto, f.seccion, d.titulo AS documento,
                       d.tipo, d.fuente, d.material_id, f.orden,
                       1 - (f.embedding <=> %s::vector) AS similitud
                FROM conocimiento.fragmentos AS f
                JOIN conocimiento.documentos AS d ON d.id = f.documento_id
                WHERE d.material_id = %s AND d.tipo = 'tesis_completa'
                ORDER BY f.embedding <=> %s::vector
                LIMIT %s
                """,
                (vector, material_id, vector, limite_completa),
            )
            columnas = [columna.name for columna in cursor.description]
            resultados.extend(
                dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()
            )
    except PsycopgError as error:
        raise RuntimeError(
            "No fue posible consultar los fragmentos de la tesis en PostgreSQL."
        ) from error
    return resultados, {
        "t_embedding_ms": t_embedding_ms,
        "t_busqueda_ms": (perf_counter() - inicio) * 1000 - t_embedding_ms,
    }


def buscar_exacto_sql(texto: str, limite: int = 10) -> list[dict[str, Any]]:
    """Busca la cadena literal en títulos o autores, sin interpolar SQL."""
    patron = f"%{texto}%"
    sql = """
        SELECT v.material_id, v.titulo, v.autor, v.tipo, m.anio,
               v.disponibles, v.total
        FROM public.v_disponibilidad AS v
        JOIN public.material AS m ON m.id = v.material_id
        WHERE v.titulo ILIKE %s OR v.autor ILIKE %s
        ORDER BY v.titulo
        LIMIT %s
    """
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(sql, (patron, patron, limite))
            columnas = [columna.name for columna in cursor.description]
            return [
                dict(zip(columnas, fila, strict=True))
                for fila in cursor.fetchall()
            ]
    except PsycopgError as error:
        raise RuntimeError(
            "No fue posible realizar la búsqueda exacta en PostgreSQL; "
            "verifique public.v_disponibilidad."
        ) from error
