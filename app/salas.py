"""Catálogo y métricas por sala."""

from __future__ import annotations

from typing import Any

from app.db import conexion


SALAS_BASE = [
    {
        "slug": "ingenieria",
        "nombre": "Sala de Ingeniería y Tecnología",
        "descripcion": "Ingeniería de Sistemas",
        "icono": "💻",
        "bibliotecario": {"nombre": "Andrés", "saludo": "Bienvenido a la Sala de Ingeniería. Aquí están los libros de programación, redes, bases de datos e inteligencia artificial. ¿Qué buscas?"},
        "programas": ["Ingeniería de Sistemas"],
    },
    {
        "slug": "agro-ambiental",
        "nombre": "Sala de Ciencias Agrarias y Ambientales",
        "descripcion": "Ingeniería Agroforestal, Ingeniería Ambiental",
        "icono": "🌱",
        "bibliotecario": {"nombre": "Rosa", "saludo": "Bienvenida a la Sala Agroambiental. Aquí están los materiales sobre suelo, cultivos, ecología y sostenibilidad. ¿Qué buscas?"},
        "programas": ["Ingeniería Agroforestal", "Ingeniería Ambiental"],
    },
    {
        "slug": "administracion",
        "nombre": "Sala de Administración y Negocios",
        "descripcion": "Administración de Empresas",
        "icono": "📈",
        "bibliotecario": {"nombre": "Camilo", "saludo": "Bienvenido a la Sala de Administración. Aquí están los libros de gestión, marketing y negocios. ¿Qué buscas?"},
        "programas": ["Administración de Empresas"],
    },
    {
        "slug": "contaduria",
        "nombre": "Sala de Contaduría y Finanzas",
        "descripcion": "Contaduría Pública",
        "icono": "🧾",
        "bibliotecario": {"nombre": "Lucía", "saludo": "Bienvenida a la Sala de Contaduría. Aquí están los materiales de costos, finanzas y contabilidad. ¿Qué buscas?"},
        "programas": ["Contaduría Pública"],
    },
    {
        "slug": "investigacion",
        "nombre": "Sala de Investigación y Escritura",
        "descripcion": "Transversal (metodología, redacción)",
        "icono": "✍️",
        "bibliotecario": {"nombre": "Elena", "saludo": "Bienvenida a la Sala de Investigación. Aquí están los materiales de metodología, redacción y tesis. ¿Qué buscas?"},
        "programas": ["Transversal"],
    },
]


def _serializar_sala(fila: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fila.get("id"),
        "slug": fila["slug"],
        "nombre": fila["nombre"],
        "descripcion": fila["descripcion"],
        "icono": fila["icono"],
        "bibliotecario": {
            "nombre": fila["bibliotecario_nombre"],
            "saludo": fila["bibliotecario_saludo"],
        },
        "programas": fila.get("programas") or [],
        "libros": int(fila.get("libros") or 0),
        "tesis": int(fila.get("tesis") or 0),
        "total": int(fila.get("total") or 0),
    }


def opcion_sala(sala: dict[str, Any]) -> dict[str, Any]:
    """Serializa la sala como opción compacta para el chat."""
    return {
        "slug": sala["slug"],
        "nombre": sala["nombre"],
        "descripcion": sala.get("descripcion"),
        "icono": sala.get("icono"),
        "bibliotecario": sala.get("bibliotecario"),
        "libros": int(sala.get("libros") or 0),
        "tesis": int(sala.get("tesis") or 0),
        "total": int(sala.get("total") or 0),
    }


def formato_conteo_materiales(libros: int, tesis: int, total: int = 0) -> str:
    """Devuelve la frase con concordancia gramatical para el acervo de una sala."""
    partes: list[str] = []
    if libros == 1:
        partes.append("1 libro")
    elif libros > 1:
        partes.append(f"{libros} libros")

    if tesis == 1:
        partes.append("1 tesis")
    elif tesis > 1:
        partes.append(f"{tesis} tesis")

    if partes:
        return f"Aquí hay {' y '.join(partes)}."

    if total == 1:
        return "Aquí hay 1 material."
    if total > 1:
        return f"Aquí hay {total} materiales."
    return "Aquí no hay materiales."


def listar_salas() -> list[dict[str, Any]]:
    """Lista salas con conteos reales del catálogo y programas asociados."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT s.id, s.slug, s.nombre, s.descripcion, s.icono,
                   s.bibliotecario_nombre, s.bibliotecario_saludo,
                   COALESCE((SELECT array_agg(sp.programa ORDER BY sp.programa)
                             FROM public.salas_programas AS sp
                             WHERE sp.sala_id = s.id), ARRAY[]::text[]) AS programas,
                   COUNT(m.id) FILTER (WHERE m.tipo = 'libro') AS libros,
                   COUNT(m.id) FILTER (WHERE m.tipo = 'tesis') AS tesis,
                   COUNT(m.id) AS total
            FROM public.salas AS s
            LEFT JOIN public.material AS m ON m.sala_id = s.id
            GROUP BY s.id, s.slug, s.nombre, s.descripcion, s.icono,
                     s.bibliotecario_nombre, s.bibliotecario_saludo
            ORDER BY s.orden
            """
        )
        columnas = [columna.name for columna in cursor.description]
        filas = cursor.fetchall()
    salas = []
    for fila in filas:
        datos = dict(zip(columnas, fila, strict=True))
        programas = datos.get("programas") or []
        if isinstance(programas, list):
            datos["programas"] = [str(programa) for programa in programas]
        salas.append(_serializar_sala(datos))
    return salas


def sala_por_slug(slug: str | None) -> dict[str, Any] | None:
    """Recupera una sala por su slug, o None si no existe."""
    if slug is None:
        return None
    clave = str(slug).strip().lower()
    if not clave:
        return None
    salas = listar_salas()
    for sala in salas:
        if sala["slug"] == clave:
            return sala
    return None


def sala_de_programa(programa: str | None) -> dict[str, Any] | None:
    """Devuelve la sala a la que pertenece un programa, si existe."""
    if programa is None:
        return None
    texto = str(programa).strip()
    if not texto:
        return None
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT s.id, s.slug, s.nombre, s.descripcion, s.icono,
                   s.bibliotecario_nombre, s.bibliotecario_saludo
            FROM public.salas AS s
            JOIN public.salas_programas AS sp ON sp.sala_id = s.id
            WHERE lower(btrim(sp.programa)) = lower(btrim(%s))
            LIMIT 1
            """,
            (texto,),
        )
        fila = cursor.fetchone()
        columnas = [columna.name for columna in cursor.description] if cursor.description else []
        if not fila and "transversal" in texto.lower():
            cursor.execute(
                """
                SELECT s.id, s.slug, s.nombre, s.descripcion, s.icono,
                       s.bibliotecario_nombre, s.bibliotecario_saludo
                FROM public.salas AS s
                WHERE s.slug = 'investigacion'
                LIMIT 1
                """
            )
            fila = cursor.fetchone()
            columnas = [columna.name for columna in cursor.description] if cursor.description else []
    if not fila or not columnas:
        return None
    datos = dict(zip(columnas, fila, strict=True))
    sala = sala_por_slug(datos["slug"])
    return sala
