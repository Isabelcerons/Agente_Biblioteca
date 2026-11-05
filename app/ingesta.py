"""Utilidades compartidas para fragmentar y persistir documentos de conocimiento."""

import hashlib
import re
from dataclasses import dataclass

from app.db import conexion


@dataclass
class Documento:
    """Documento lógico a persistir y sus fragmentos ordenados."""

    titulo: str
    tipo: str
    fuente: str
    contenido: str
    secciones: list[tuple[str | None, str]]
    material_id: int | None = None

    @property
    def hash_contenido(self) -> str:
        return hashlib.sha256(self.contenido.encode("utf-8")).hexdigest()


def fragmentar(texto: str, maximo: int = 500, solapamiento: int = 80) -> list[str]:
    """Corta en límites de frase o palabra y conserva un solapamiento breve."""
    texto = re.sub(r"\s+", " ", texto).strip()
    if not texto:
        return []
    fragmentos: list[str] = []
    inicio = 0
    while inicio < len(texto):
        limite = min(inicio + maximo, len(texto))
        fin = limite
        if limite < len(texto):
            candidatos = [
                match.end()
                for match in re.finditer(r"[.!?;:](?:\s+|$)", texto[inicio:limite])
            ]
            if candidatos and candidatos[-1] >= maximo // 2:
                fin = inicio + candidatos[-1]
            else:
                espacio = texto.rfind(" ", inicio, limite)
                if espacio <= inicio:
                    espacio = texto.find(" ", limite)
                    fin = len(texto) if espacio == -1 else espacio
                else:
                    fin = espacio
        fragmento = texto[inicio:fin].strip()
        if fragmento:
            fragmentos.append(fragmento)
        if fin >= len(texto):
            break
        siguiente = max(inicio + 1, fin - solapamiento)
        espacio = texto.rfind(" ", inicio, siguiente)
        if espacio >= inicio:
            siguiente = espacio + 1
        while siguiente < len(texto) and texto[siguiente].isspace():
            siguiente += 1
        inicio = siguiente
    return fragmentos


def fragmentos_documento(
    documento: Documento,
) -> list[tuple[str | None, str]]:
    """Fragmenta cada sección de forma independiente y conserva su encabezado."""
    salida: list[tuple[str | None, str]] = []
    for seccion, cuerpo in documento.secciones:
        salida.extend((seccion, texto) for texto in fragmentar(cuerpo))
    return salida


def persistir_documentos(
    documentos: list[Documento],
    trozos_por_documento: list[list[tuple[str | None, str]]],
    vectores_por_documento: list[list[list[float]]],
    forzar: bool = False,
) -> list[str]:
    """Inserta o reemplaza atómicamente varios documentos y sus vectores."""
    if not (
        len(documentos) == len(trozos_por_documento) == len(vectores_por_documento)
    ):
        raise ValueError("La cantidad de documentos, fragmentos y vectores no coincide.")
    for trozos, vectores in zip(
        trozos_por_documento, vectores_por_documento, strict=True
    ):
        if len(trozos) != len(vectores):
            raise RuntimeError(
                "La cantidad de vectores no coincide con los fragmentos."
            )

    estados: list[str] = []
    with conexion() as conn, conn.cursor() as cursor:
        for documento, trozos, vectores in zip(
            documentos,
            trozos_por_documento,
            vectores_por_documento,
            strict=True,
        ):
            cursor.execute(
                """
                SELECT id, hash_contenido
                FROM conocimiento.documentos
                WHERE fuente = %s
                FOR UPDATE
                """,
                (documento.fuente,),
            )
            existente = cursor.fetchone()
            if existente and existente[1] == documento.hash_contenido and not forzar:
                estados.append("omitido")
                continue
            if existente:
                documento_id = existente[0]
                cursor.execute(
                    "DELETE FROM conocimiento.fragmentos WHERE documento_id = %s",
                    (documento_id,),
                )
                cursor.execute(
                    """
                    UPDATE conocimiento.documentos
                    SET titulo = %s, tipo = %s, material_id = %s, hash_contenido = %s
                    WHERE id = %s
                    """,
                    (
                        documento.titulo,
                        documento.tipo,
                        documento.material_id,
                        documento.hash_contenido,
                        documento_id,
                    ),
                )
                estado = "actualizado"
            else:
                cursor.execute(
                    """
                    INSERT INTO conocimiento.documentos
                        (titulo, tipo, fuente, material_id, hash_contenido)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        documento.titulo,
                        documento.tipo,
                        documento.fuente,
                        documento.material_id,
                        documento.hash_contenido,
                    ),
                )
                documento_id = cursor.fetchone()[0]
                estado = "nuevo"

            cursor.executemany(
                """
                INSERT INTO conocimiento.fragmentos
                    (documento_id, orden, seccion, texto, embedding)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (documento_id, orden, seccion, texto, vector)
                    for orden, ((seccion, texto), vector) in enumerate(
                        zip(trozos, vectores, strict=True), start=1
                    )
                ],
            )
            estados.append(estado)
    return estados


def persistir_documento(
    documento: Documento,
    trozos: list[tuple[str | None, str]],
    vectores: list[list[float]],
    forzar: bool,
) -> str:
    """Conserva la interfaz de persistencia usada por la ingesta de conocimiento."""
    return persistir_documentos(
        [documento], [trozos], [vectores], forzar=forzar
    )[0]
