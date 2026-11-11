"""Asistencia extractiva basada exclusivamente en el acervo ya indexado.

Las citas [material ID] remiten a materiales y fuentes de la misma respuesta.
No se solicita al modelo que complete información ausente de los documentos.
"""

from typing import Any

from pgvector import Vector

from app import bibliografia, rag
from app.db import conexion

UMBRAL_SIMILITUD = 0.35
MAX_MATERIALES = 5


def resultado_vacio(
    tema: str, respuesta: str, sugerencia_sala: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "ok": False, "tema": tema, "respuesta": respuesta,
        "subtemas": [], "materiales": [], "fuentes": [], "bibliografia": [],
        "sugerencia_sala": sugerencia_sala,
    }


def investigar(
    tema: str, programa: str | None = None, sala_slug: str | None = None
) -> dict[str, Any]:
    """Busca hasta cinco materiales y dos fragmentos literales por material.

    Programa es un filtro exacto del catálogo, sin distinguir mayúsculas.
    Se calcula un único embedding; el resumen, las reseñas y las tesis
    completas participan en la búsqueda. Solo se ejecutan consultas SELECT.
    """
    tema = tema.strip()
    programa = programa.strip() if programa else None
    sala_slug = (
        sala_slug.strip().lower()
        if sala_slug and sala_slug.strip().lower() not in ("", "todas", "toda", "general", "null", "none")
        else None
    )
    if not tema or len(tema) > 500:
        raise ValueError("El tema debe tener entre 1 y 500 caracteres.")
    if programa is not None and not 1 <= len(programa) <= 160:
        raise ValueError("El programa debe tener entre 1 y 160 caracteres.")
    vector = Vector(rag.embed_consulta(tema))
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            WITH evidencia AS (
                SELECT d.material_id, d.titulo AS documento, f.seccion, f.texto,
                       f.id, 1 - (f.embedding <=> %s::vector) AS similitud
                FROM conocimiento.fragmentos AS f
                JOIN conocimiento.documentos AS d ON d.id = f.documento_id
                JOIN public.material AS m ON m.id = d.material_id
                WHERE d.tipo = ANY(%s) AND m.tipo IN ('libro', 'tesis')
                  AND f.embedding IS NOT NULL AND btrim(f.texto) <> ''
                  AND (%s::text IS NULL OR lower(btrim(m.programa)) = lower(%s))
                  AND (%s::text IS NULL OR m.sala_id = (
                      SELECT s.id FROM public.salas AS s WHERE lower(btrim(s.slug)) = lower(btrim(%s))
                  ))
            ), ordenados AS (
                SELECT *, row_number() OVER (
                    PARTITION BY material_id ORDER BY similitud DESC, id
                ) AS posicion
                FROM evidencia WHERE similitud >= %s
            ), mejores AS (
                SELECT material_id, similitud FROM ordenados
                WHERE posicion = 1
                ORDER BY similitud DESC, material_id LIMIT %s
            )
            SELECT v.material_id, v.titulo, v.autor, v.tipo, m.anio,
                   v.disponibles, v.total, m.editorial, m.tema AS tema_catalogo,
                   mejores.similitud, o.documento, o.seccion, o.texto,
                   o.similitud AS similitud_fuente
            FROM mejores
            JOIN public.material AS m ON m.id = mejores.material_id
            JOIN public.v_disponibilidad AS v ON v.material_id = m.id
            JOIN ordenados AS o ON o.material_id = m.id AND o.posicion <= 2
            ORDER BY mejores.similitud DESC, m.id, o.posicion
            """,
            (
                vector, ["resena_libro", "resumen_tesis", "tesis_completa"],
                programa, programa, sala_slug, sala_slug,
                UMBRAL_SIMILITUD, MAX_MATERIALES,
            ),
        )
        columnas = [columna.name for columna in cursor.description]
        filas = [dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()]

    if not filas:
        if sala_slug:
            # Comprobar si hay evidencia en otra sala
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    """
                    WITH evidencia_global AS (
                        SELECT d.material_id, 1 - (f.embedding <=> %s::vector) AS similitud
                        FROM conocimiento.fragmentos AS f
                        JOIN conocimiento.documentos AS d ON d.id = f.documento_id
                        JOIN public.material AS m ON m.id = d.material_id
                        WHERE d.tipo = ANY(%s) AND m.tipo IN ('libro', 'tesis')
                          AND f.embedding IS NOT NULL AND btrim(f.texto) <> ''
                    )
                    SELECT s.slug, s.nombre, count(DISTINCT eg.material_id) as cantidad
                    FROM evidencia_global eg
                    JOIN public.material m ON m.id = eg.material_id
                    JOIN public.salas s ON s.id = m.sala_id
                    WHERE eg.similitud >= %s AND lower(btrim(s.slug)) <> lower(btrim(%s))
                    GROUP BY s.slug, s.nombre
                    ORDER BY cantidad DESC
                    LIMIT 1
                    """,
                    (vector, ["resena_libro", "resumen_tesis", "tesis_completa"], UMBRAL_SIMILITUD, sala_slug),
                )
                fila_otra = cursor.fetchone()
            if fila_otra:
                sugerencia = {
                    "slug": fila_otra[0],
                    "nombre": fila_otra[1],
                    "motivo": f"Hay {fila_otra[2]} resultados en {fila_otra[1]}.",
                }
                mensaje = (
                    f"En esta sala no tengo material sobre eso, pero en la {fila_otra[1]} "
                    f"hay {fila_otra[2]} resultados. ¿Quieres que te lleve?"
                )
                return resultado_vacio(tema, mensaje, sugerencia_sala=sugerencia)
        return resultado_vacio(
            tema,
            "No encontré evidencia indexada suficientemente cercana al tema con esos filtros.",
        )

    materiales: dict[int, dict[str, Any]] = {}
    fuentes: list[dict[str, Any]] = []
    referencias: list[str] = []
    subtemas: list[str] = []
    parrafos: list[str] = []
    campos = ("material_id", "titulo", "autor", "tipo", "anio", "disponibles", "total", "similitud")
    for fila in filas:
        material_id = fila["material_id"]
        fuentes.append({
            "material_id": material_id, "documento": fila["documento"],
            "seccion": fila["seccion"], "texto": fila["texto"],
            "similitud": float(fila["similitud_fuente"]),
        })
        if material_id in materiales:
            continue
        materiales[material_id] = {campo: fila[campo] for campo in campos}
        # El extracto es un prefijo literal; la fuente conserva el fragmento entero.
        texto = fila["texto"]
        extracto = texto[:280]
        sufijo = "…" if len(texto) > len(extracto) else ""
        parrafos.append(f'«{fila["titulo"]}»: «{extracto}»{sufijo} [material {material_id}].')
        subtema = str(fila.get("tema_catalogo") or "").strip()
        if subtema and subtema not in subtemas:
            subtemas.append(subtema)
        referencia = bibliografia.referencia_apa_catalogo(fila)
        if referencia:
            referencias.append(referencia)
    return {
        "ok": True, "tema": tema,
        "respuesta": "Evidencia del acervo para orientar tu investigación:\n\n" + "\n\n".join(parrafos),
        "subtemas": subtemas, "materiales": list(materiales.values()),
        "fuentes": fuentes, "bibliografia": sorted(set(referencias)),
        "sugerencia_sala": None,
    }
