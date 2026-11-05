"""Cálculo y consulta de la proyección bidimensional del conocimiento."""

import hashlib
from time import perf_counter
from typing import Any

import numpy as np
from pgvector import Vector

from app.db import conexion


def _a_numpy(valor) -> np.ndarray:
    """Convierte lo que devuelve psycopg para una columna vector (pgvector.Vector,
    numpy, lista o texto '[..]') en un arreglo float64."""
    if hasattr(valor, "to_numpy"):
        valor = valor.to_numpy()
    elif isinstance(valor, str):
        valor = [float(x) for x in valor.strip("[]").split(",")]
    return np.asarray(valor, dtype=np.float64)


_DIMENSIONES = 768
_TIPOS = ("resumen_tesis", "resena_libro")


def _firma_documentos(cursor: Any) -> str:
    """Genera una firma estable con los materiales y sus versiones de contenido."""
    cursor.execute(
        """
        SELECT material_id, hash_contenido
        FROM conocimiento.documentos
        WHERE material_id IS NOT NULL AND tipo = ANY(%s)
        ORDER BY material_id, hash_contenido
        """,
        (list(_TIPOS),),
    )
    firma = hashlib.sha256()
    for material_id, hash_contenido in cursor.fetchall():
        firma.update(f"{material_id}:{hash_contenido}\n".encode("utf-8"))
    return firma.hexdigest()


def calcular_mapa(forzar: bool = False) -> dict[str, Any]:
    """Calcula el PCA y persiste coordenadas y componentes reutilizables."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT d.material_id, AVG(f.embedding) AS embedding_medio
            FROM conocimiento.fragmentos AS f
            JOIN conocimiento.documentos AS d ON d.id = f.documento_id
            WHERE d.material_id IS NOT NULL
              AND d.tipo = ANY(%s)
            GROUP BY d.material_id
            ORDER BY d.material_id
            """,
            (list(_TIPOS),),
        )
        filas = cursor.fetchall()
        firma = _firma_documentos(cursor)
        if not filas:
            cursor.execute("DELETE FROM conocimiento.mapa_materiales")
            cursor.execute("DELETE FROM conocimiento.mapa_pca WHERE id = 1")
            return {"n": 0, "varianza_explicada": [], "recalculado": True}

        cursor.execute("SELECT firma FROM conocimiento.mapa_pca WHERE id = 1")
        firma_guardada = cursor.fetchone()
        if firma_guardada and firma_guardada[0] == firma and not forzar:
            cursor.execute("SELECT count(*) FROM conocimiento.mapa_materiales")
            if cursor.fetchone()[0] == len(filas):
                cursor.execute(
                    """
                    SELECT varianza_explicada
                    FROM conocimiento.mapa_pca
                    WHERE id = 1
                    """
                )
                varianza_guardada = cursor.fetchone()[0]
                return {
                    "n": len(filas),
                    "varianza_explicada": list(varianza_guardada or []),
                    "recalculado": False,
                }

        ids = [fila[0] for fila in filas]
        embeddings = np.asarray(
            [_a_numpy(fila[1]) for fila in filas],
            dtype=np.float64,
        )
        normas = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = np.divide(
            embeddings,
            normas,
            out=np.zeros_like(embeddings),
            where=normas != 0,
        )

        media = embeddings.mean(axis=0)
        centrados = embeddings - media
        _, valores_singulares, vt = np.linalg.svd(
            centrados, full_matrices=False
        )
        componentes = np.zeros((2, _DIMENSIONES), dtype=np.float64)
        componentes[: min(2, len(vt))] = vt[:2]
        for indice in range(2):
            mayor = int(np.argmax(np.abs(componentes[indice])))
            if componentes[indice, mayor] < 0:
                componentes[indice] *= -1

        coordenadas = centrados @ componentes.T
        varianzas = valores_singulares**2
        varianza_total = float(varianzas.sum())
        varianza_explicada = [
            float(valor / varianza_total) if varianza_total else 0.0
            for valor in varianzas[:2]
        ]
        while len(varianza_explicada) < 2:
            varianza_explicada.append(0.0)
        vectores_normalizados = embeddings.tolist()

        cursor.execute(
            """
            INSERT INTO conocimiento.mapa_pca
                (id, media, comp1, comp2, varianza_explicada,
                 n_materiales, firma, calculado)
            VALUES (1, %s, %s, %s, %s::real[], %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET
                media = EXCLUDED.media,
                comp1 = EXCLUDED.comp1,
                comp2 = EXCLUDED.comp2,
                varianza_explicada = EXCLUDED.varianza_explicada,
                n_materiales = EXCLUDED.n_materiales,
                firma = EXCLUDED.firma,
                calculado = now()
            """,
            (
                Vector(media.tolist()),
                Vector(componentes[0].tolist()),
                Vector(componentes[1].tolist()),
                varianza_explicada,
                len(ids),
                firma,
            ),
        )
        cursor.executemany(
            """
            INSERT INTO conocimiento.mapa_materiales
                (material_id, x, y, embedding_medio, calculado)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (material_id) DO UPDATE SET
                x = EXCLUDED.x,
                y = EXCLUDED.y,
                embedding_medio = EXCLUDED.embedding_medio,
                calculado = now()
            """,
            [
                (
                    material_id,
                    float(coordenadas[indice, 0]),
                    float(coordenadas[indice, 1]),
                    Vector(vectores_normalizados[indice]),
                )
                for indice, material_id in enumerate(ids)
            ],
        )
        cursor.execute(
            """
            DELETE FROM conocimiento.mapa_materiales
            WHERE material_id <> ALL(%s)
            """,
            (ids,),
        )

    return {
        "n": len(ids),
        "varianza_explicada": varianza_explicada,
        "recalculado": True,
    }


def obtener_puntos() -> list[dict[str, Any]]:
    """Devuelve materiales proyectados con su programa y disponibilidad."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT mm.material_id, m.titulo, m.autor, m.anio, m.tipo,
                   m.programa, m.tema, mm.x, mm.y,
                   v.disponibles, v.total
            FROM conocimiento.mapa_materiales AS mm
            JOIN public.material AS m ON m.id = mm.material_id
            JOIN public.v_disponibilidad AS v ON v.material_id = m.id
            ORDER BY mm.material_id
            """
        )
        columnas = [columna.name for columna in cursor.description]
        return [
            dict(zip(columnas, fila, strict=True))
            for fila in cursor.fetchall()
        ]


def obtener_resumen() -> dict[str, Any] | None:
    """Lee la varianza y la fecha de cálculo del PCA almacenado."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT varianza_explicada, calculado
            FROM conocimiento.mapa_pca
            WHERE id = 1
            """
        )
        fila = cursor.fetchone()
    if fila is None:
        return None
    return {
        "varianza_explicada": list(fila[0] or []),
        "calculado": fila[1],
    }


def proyectar_consulta(texto: str, k: int = 5) -> dict[str, Any]:
    """Proyecta una consulta; la proximidad visual en 2D es aproximada porque PCA
    conserva solo parte de la varianza. Los vecinos se buscan en 768 dimensiones,
    que es lo que hace pgvector.
    """
    from app.rag import embed_consulta

    inicio = perf_counter()
    consulta = np.asarray(embed_consulta(texto), dtype=np.float64)
    t_embedding_ms = (perf_counter() - inicio) * 1000
    norma = float(np.linalg.norm(consulta))
    if norma:
        consulta /= norma

    inicio = perf_counter()
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT media, comp1, comp2
            FROM conocimiento.mapa_pca
            WHERE id = 1
            """
        )
        pca = cursor.fetchone()
        if pca is None:
            raise RuntimeError("No hay mapa calculado. Ejecute python calcular_mapa.py")
        media = _a_numpy(pca[0])
        componentes = np.vstack(
            (_a_numpy(pca[1]), _a_numpy(pca[2]))
        )
        coordenadas = (consulta - media) @ componentes.T

        cursor.execute("SELECT count(*) FROM conocimiento.mapa_materiales")
        if cursor.fetchone()[0] == 0:
            raise RuntimeError("No hay mapa calculado. Ejecute python calcular_mapa.py")
        cursor.execute(
            """
            SELECT mm.material_id, m.titulo,
                   1 - (mm.embedding_medio <=> %s::vector) AS similitud
            FROM conocimiento.mapa_materiales AS mm
            JOIN public.material AS m ON m.id = mm.material_id
            ORDER BY mm.embedding_medio <=> %s::vector
            LIMIT %s
            """,
            (Vector(consulta.tolist()), Vector(consulta.tolist()), k),
        )
        cercanos = [
            {
                "material_id": fila[0],
                "titulo": fila[1],
                "similitud": float(fila[2]),
            }
            for fila in cursor.fetchall()
        ]

    return {
        "x": float(coordenadas[0]),
        "y": float(coordenadas[1]),
        "cercanos": cercanos,
        "tiempos": {
            "t_embedding_ms": t_embedding_ms,
            "t_busqueda_ms": (perf_counter() - inicio) * 1000,
        },
    }
