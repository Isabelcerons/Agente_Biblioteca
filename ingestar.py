"""Carga idempotente de documentos demostrativos a PostgreSQL y pgvector."""

import argparse
import re
import sys
import time
from pathlib import Path

from app.config import RAIZ
from app.db import conexion
from app.ingesta import (
    Documento,
    fragmentar as _fragmentar,
    fragmentos_documento as _fragmentos_documento,
    persistir_documento as _persistir_documento,
)
from app.rag import embed_documentos

DIRECTORIO_CONOCIMIENTO = RAIZ / "conocimiento"
TIPOS_POR_ARCHIVO = {
    "reglamento_biblioteca": "reglamento",
    "guia_apa7": "apa",
    "guia_ieee": "ieee",
    "guia_bases_datos": "guia_bd",
    "preguntas_frecuentes": "faq",
    "resumenes_tesis": "resumen_tesis",
    "resenas_libros": "resena_libro",
}
def _secciones(texto: str) -> tuple[str, list[tuple[str, str]]]:
    """Separa encabezados de segundo nivel sin perder el contenido previo."""
    coincidencias = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", texto))
    if not coincidencias:
        return texto.strip(), [(None, texto.strip())]
    preambulo = texto[: coincidencias[0].start()].strip()
    secciones: list[tuple[str, str]] = []
    for indice, coincidencia in enumerate(coincidencias):
        fin = (
            coincidencias[indice + 1].start()
            if indice + 1 < len(coincidencias)
            else len(texto)
        )
        encabezado = coincidencia.group(1).strip()
        cuerpo = texto[coincidencia.end() : fin].strip()
        if indice == 0 and preambulo:
            cuerpo = f"{preambulo}\n\n{cuerpo}".strip()
        secciones.append((encabezado, cuerpo))
    return preambulo, secciones


def _cargar_documentos() -> list[Documento]:
    """Lee los siete archivos y crea documentos generales o uno por título."""
    documentos: list[Documento] = []
    for base, tipo in TIPOS_POR_ARCHIVO.items():
        ruta = DIRECTORIO_CONOCIMIENTO / f"{base}.md"
        if not ruta.is_file():
            raise FileNotFoundError(f"No existe el archivo de conocimiento: {ruta}")
        texto = ruta.read_text(encoding="utf-8")
        preambulo, secciones = _secciones(texto)
        if tipo in ("resumen_tesis", "resena_libro"):
            for titulo, cuerpo in secciones:
                if titulo is None:
                    continue
                contenido = f"## {titulo}\n{cuerpo}".strip()
                fuente = f"{ruta.name}#{titulo}"
                documentos.append(
                    Documento(
                        titulo=titulo,
                        tipo=tipo,
                        fuente=fuente,
                        contenido=contenido,
                        secciones=[(titulo, cuerpo)],
                    )
                )
        else:
            titulo = next(
                (
                    linea.removeprefix("#").strip()
                    for linea in preambulo.splitlines()
                    if linea.startswith("# ")
                ),
                ruta.stem.replace("_", " "),
            )
            documentos.append(
                Documento(
                    titulo=titulo,
                    tipo=tipo,
                    fuente=ruta.name,
                    contenido=texto,
                    secciones=[
                        (seccion, cuerpo) for seccion, cuerpo in secciones
                    ],
                )
            )
    return documentos


def _material_id(titulo: str, tipo: str) -> int | None:
    """Resuelve el título exacto en el catálogo, restringiendo libro o tesis."""
    tipo_material = "tesis" if tipo == "resumen_tesis" else "libro"
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM public.material
            WHERE titulo = %s AND tipo = %s
            ORDER BY id
            LIMIT 1
            """,
            (titulo, tipo_material),
        )
        fila = cursor.fetchone()
    if fila is None:
        print(
            f"AVISO: no se encontró {tipo_material} con título exacto "
            f"{titulo!r}; material_id quedará NULL.",
            file=sys.stderr,
        )
        return None
    return fila[0]


def _buscar_documento(fuente: str) -> tuple[int, str] | None:
    """Consulta el documento actual para decidir si se omite o actualiza."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, hash_contenido FROM conocimiento.documentos WHERE fuente = %s",
            (fuente,),
        )
        fila = cursor.fetchone()
    return (fila[0], fila[1]) if fila else None


def _mostrar_huerfanos(fuentes_esperadas: set[str], limpiar: bool) -> None:
    """Lista documentos sin archivo y solo los borra si se solicitó limpiar."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT id, fuente FROM conocimiento.documentos ORDER BY fuente")
        registrados = cursor.fetchall()
    huerfanos = [
        (documento_id, fuente)
        for documento_id, fuente in registrados
        if fuente not in fuentes_esperadas
    ]
    if not huerfanos:
        print("Documentos huérfanos: ninguno.")
        return
    print("Documentos huérfanos:")
    for documento_id, fuente in huerfanos:
        print(f"  - {fuente}")
        if limpiar:
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM conocimiento.documentos WHERE id = %s",
                    (documento_id,),
                )
    if limpiar:
        print(f"Se eliminaron {len(huerfanos)} documentos huérfanos (--limpiar).")
    else:
        print("No se borraron; use --limpiar para eliminarlos.")


def main() -> int:
    """Ejecuta la ingesta y presenta un resumen de sus resultados."""
    parser = argparse.ArgumentParser(
        description="Fragmenta e indexa los documentos de conocimiento de la biblioteca."
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="recalcula e inserta nuevamente todos los embeddings",
    )
    parser.add_argument(
        "--limpiar",
        action="store_true",
        help="elimina documentos huérfanos después de listarlos",
    )
    argumentos = parser.parse_args()
    inicio_total = time.perf_counter()
    contadores = {"nuevo": 0, "actualizado": 0, "omitido": 0}
    errores: list[str] = []

    try:
        documentos = _cargar_documentos()
        fuentes_esperadas = {documento.fuente for documento in documentos}
        _mostrar_huerfanos(fuentes_esperadas, argumentos.limpiar)

        for numero, documento in enumerate(documentos, start=1):
            try:
                print(
                    f"[{numero}/{len(documentos)}] {documento.fuente}",
                    flush=True,
                )
                if documento.tipo in ("resumen_tesis", "resena_libro"):
                    documento.material_id = _material_id(
                        documento.titulo, documento.tipo
                    )

                existente = _buscar_documento(documento.fuente)
                if (
                    existente
                    and existente[1] == documento.hash_contenido
                    and not argumentos.forzar
                ):
                    contadores["omitido"] += 1
                    print("  Sin cambios; se omite.")
                    continue

                trozos = _fragmentos_documento(documento)
                if not trozos:
                    raise ValueError("El documento no contiene texto fragmentable.")
                vectores = embed_documentos(
                    [texto for _, texto in trozos],
                    [documento.titulo] * len(trozos),
                )
                estado = _persistir_documento(
                    documento, trozos, vectores, argumentos.forzar
                )
                contadores[estado] += 1
                print(f"  {estado.capitalize()}: {len(trozos)} fragmentos.")
            except Exception as error:
                mensaje = f"{documento.fuente}: {error}"
                errores.append(mensaje)
                print(f"  ERROR: {mensaje}", file=sys.stderr)

        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM conocimiento.fragmentos")
            total_fragmentos = cursor.fetchone()[0]
        duracion = time.perf_counter() - inicio_total
        print("\nResumen de ingesta")
        print(f"  Documentos nuevos:       {contadores['nuevo']}")
        print(f"  Documentos actualizados: {contadores['actualizado']}")
        print(f"  Documentos omitidos:     {contadores['omitido']}")
        print(f"  Fragmentos totales en BD: {total_fragmentos}")
        print(f"  Tiempo total:            {duracion:.2f} s")
        if errores:
            print(f"  Errores:                 {len(errores)}", file=sys.stderr)
            return 1
        try:
            from app.mapa import calcular_mapa

            resultado_mapa = calcular_mapa()
            print(
                f"Mapa del conocimiento: {resultado_mapa['n']} materiales "
                f"({('actualizado' if resultado_mapa['recalculado'] else 'sin cambios')})."
            )
        except Exception as error:
            print(
                f"AVISO: no se pudo actualizar el mapa del conocimiento: {error}",
                file=sys.stderr,
            )
        return 0
    except Exception as error:
        print(f"Error de ingesta: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
