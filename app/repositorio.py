"""Registro y procesamiento de tesis PDF del repositorio institucional."""

from collections import Counter
from datetime import date
import io
import logging
import math
from pathlib import Path
import re
import threading
from typing import Callable
from uuid import UUID

from pypdf import PdfReader

from app.config import RAIZ
from app.db import conexion
from app.ingesta import Documento, fragmentos_documento, persistir_documentos

CARPETA = RAIZ / "repositorio" / "tesis"
CARPETA.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 25 * 1024 * 1024
_LOGGER = logging.getLogger(__name__)


class CargaEnCursoError(ValueError):
    """Indica que el usuario ya tiene una tesis en procesamiento."""


def validar_pdf(pdf_bytes: bytes) -> None:
    """Valida tamaño, firma, estructura, cifrado y cantidad de páginas."""
    if len(pdf_bytes) > MAX_BYTES:
        raise ValueError("El PDF supera el tamaño máximo de 25 MB.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("El archivo no tiene una firma PDF válida.")
    try:
        lector = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        if lector.is_encrypted and lector.decrypt("") == 0:
            raise ValueError("El PDF está cifrado y no se puede abrir.")
        if len(lector.pages) > 300:
            raise ValueError("El PDF supera el máximo permitido de 300 páginas.")
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"No fue posible leer el PDF: {error}") from error


def _limpiar_texto(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r" *\n *", "\n", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def _extraer_texto(
    ruta: Path, al_leer: Callable[[int, int], None] | None = None
) -> list[tuple[int, str]]:
    try:
        lector = PdfReader(str(ruta), strict=False)
        if lector.is_encrypted and lector.decrypt("") == 0:
            raise ValueError("El PDF está cifrado y no se puede abrir.")
        total = len(lector.pages)
        paginas: list[tuple[int, str]] = []
        lineas_por_pagina: list[list[str]] = []
        for numero, pagina in enumerate(lector.pages, start=1):
            try:
                texto = _limpiar_texto(pagina.extract_text() or "")
            except Exception as error:
                raise ValueError(
                    f"No fue posible extraer el texto de la página {numero}: {error}"
                ) from error
            lineas = texto.splitlines()
            paginas.append((numero, texto))
            lineas_por_pagina.append(lineas)
            if al_leer:
                al_leer(numero, total)
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"No fue posible leer el PDF: {error}") from error

    umbral = max(2, math.ceil(len(paginas) * 0.5))
    apariciones: Counter[str] = Counter()
    for lineas in lineas_por_pagina:
        candidatas = set(lineas[:2] + lineas[-2:])
        apariciones.update(
            re.sub(r"\s+", " ", linea).strip().casefold()
            for linea in candidatas
            if linea.strip()
        )
    repetidas = {linea for linea, cantidad in apariciones.items() if cantidad >= umbral}

    salida: list[tuple[int, str]] = []
    for numero, lineas in enumerate(lineas_por_pagina, start=1):
        limpias = [
            linea
            for linea in lineas
            if re.sub(r"\s+", " ", linea).strip().casefold() not in repetidas
        ]
        salida.append((numero, _limpiar_texto("\n".join(limpias))))
    if sum(len(texto) for _, texto in salida) < 500:
        raise ValueError(
            "El PDF no tiene texto seleccionable (¿es escaneado?). "
            "Esta versión no hace OCR."
        )
    return salida


def extraer_texto(ruta: Path) -> list[tuple[int, str]]:
    """Extrae texto por página y elimina encabezados o pies repetidos."""
    return _extraer_texto(Path(ruta))


def _es_encabezado(linea: str) -> bool:
    texto = linea.strip().strip(":.- ")
    if not texto or len(texto) > 100:
        return False
    normalizado = texto.casefold()
    secciones = (
        "resumen", "abstract", "introduccion", "introducción", "marco teorico",
        "marco teórico", "metodologia", "metodología", "resultados", "discusion",
        "discusión", "conclusiones", "referencias", "bibliografia", "bibliografía",
        "objetivos", "planteamiento del problema", "justificacion", "justificación",
        "materiales y metodos", "materiales y métodos", "anexos", "capitulo",
        "capítulo",
    )
    if any(normalizado.startswith(nombre) for nombre in secciones):
        return True
    return bool(
        re.fullmatch(
            r"(?:\d+(?:\.\d+)*\s+)?[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9\s:().,-]{2,80}",
            texto,
        )
    )


def _detectar_resumen(texto: str) -> str:
    lineas = texto.splitlines()
    for indice, linea in enumerate(lineas):
        coincidencia = re.match(
            r"^\s*(?:\d+(?:\.\d+)*\s*)?(?:RESUMEN|ABSTRACT)\b\s*[:.-]?\s*(.*)$",
            linea,
            re.IGNORECASE,
        )
        if not coincidencia:
            continue
        contenido = [coincidencia.group(1).strip()] if coincidencia.group(1).strip() else []
        for siguiente in lineas[indice + 1 :]:
            if _es_encabezado(siguiente):
                break
            contenido.append(siguiente)
            if sum(len(parte) for parte in contenido) >= 2500:
                break
        resumen = _limpiar_texto("\n".join(contenido))[:2500]
        if resumen:
            return resumen
    return _limpiar_texto(texto)[:2500]


def _secciones_paginas(
    paginas: list[tuple[int, str]],
) -> list[tuple[str, str]]:
    salida: list[tuple[str, str]] = []
    for numero, texto in paginas:
        seccion = f"Página {numero}"
        contenido: list[str] = []
        for linea in texto.splitlines():
            if _es_encabezado(linea):
                if contenido:
                    salida.append((seccion, "\n".join(contenido).strip()))
                    contenido = []
                seccion = linea.strip().strip(":.- ")
            contenido.append(linea)
        if contenido:
            salida.append((seccion, "\n".join(contenido).strip()))
    return [(seccion, texto) for seccion, texto in salida if texto]


def _actualizar_carga(
    carga_id: UUID,
    etapa: str,
    avance: int,
    total: int,
    mensaje: str,
    error: str | None = None,
) -> None:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.cargas_tesis
            SET etapa = %s, avance = %s, total = %s, mensaje = %s,
                error = %s, actualizada = now()
            WHERE id = %s
            """,
            (etapa, avance, total, mensaje, error, carga_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("No encontré la carga de tesis que se está procesando.")


def _cargar_datos(carga_id: UUID) -> tuple[int, str, Path]:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.material_id, m.titulo, m.archivo_pdf
            FROM public.cargas_tesis AS c
            JOIN public.material AS m ON m.id = c.material_id
            WHERE c.id = %s
            """,
            (carga_id,),
        )
        fila = cursor.fetchone()
    if fila is None or fila[0] is None or not fila[2]:
        raise ValueError("No encontré el PDF asociado con esta carga.")
    ruta = (RAIZ / fila[2]).resolve()
    if not ruta.is_relative_to(RAIZ.resolve()):
        raise ValueError("La ruta del PDF del repositorio no es válida.")
    return int(fila[0]), str(fila[1]), ruta


def procesar_carga(carga_id: UUID | str) -> None:
    """Indexa en una transacción los dos documentos del PDF.

    Si el procesamiento falla, conserva el material y su carga en estado de error
    para permitir un reintento; nunca deja solo uno de los documentos indexado.
    """
    identificador = UUID(str(carga_id))
    try:
        material_id, titulo, ruta = _cargar_datos(identificador)
        if not ruta.is_file():
            raise ValueError("No se encontró el archivo PDF de la tesis.")
        _actualizar_carga(identificador, "leyendo", 0, 0, "Leyendo PDF…")

        def informar_lectura(avance: int, total: int) -> None:
            _actualizar_carga(
                identificador,
                "leyendo",
                avance,
                total,
                f"Leyendo PDF… ({avance}/{total})",
            )

        paginas = _extraer_texto(ruta, informar_lectura)
        texto_completo = _limpiar_texto("\n\n".join(texto for _, texto in paginas))
        resumen = _detectar_resumen(texto_completo)
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                "UPDATE public.material SET descripcion_corta = %s WHERE id = %s",
                (resumen[:250], material_id),
            )
        documentos = [
            Documento(
                titulo=titulo,
                tipo="resumen_tesis",
                fuente=f"repositorio#{material_id}#resumen",
                contenido=resumen,
                secciones=[("Resumen", resumen)],
                material_id=material_id,
            ),
            Documento(
                titulo=titulo,
                tipo="tesis_completa",
                fuente=f"repositorio#{material_id}#completa",
                contenido=texto_completo,
                secciones=_secciones_paginas(paginas),
                material_id=material_id,
            ),
        ]
        trozos_por_documento = [
            fragmentos_documento(documento) for documento in documentos
        ]
        total_fragmentos = sum(map(len, trozos_por_documento))
        if total_fragmentos == 0:
            raise ValueError("El PDF no contiene texto fragmentable.")
        _actualizar_carga(
            identificador,
            "fragmentando",
            0,
            total_fragmentos,
            "Fragmentando el texto de la tesis…",
        )

        from app import rag

        _actualizar_carga(
            identificador,
            "embeddings",
            0,
            total_fragmentos,
            f"Generando embeddings (0/{total_fragmentos})…",
        )
        vectores_por_documento: list[list[list[float]]] = []
        avance = 0
        for documento, trozos in zip(
            documentos, trozos_por_documento, strict=True
        ):
            vectores: list[list[float]] = []
            textos = [texto for _, texto in trozos]
            for inicio in range(0, len(textos), 16):
                lote = textos[inicio : inicio + 16]
                vectores.extend(rag.embed_documentos(lote, [titulo] * len(lote)))
                avance += len(lote)
                _actualizar_carga(
                    identificador,
                    "embeddings",
                    avance,
                    total_fragmentos,
                    f"Generando embeddings ({avance}/{total_fragmentos})…",
                )
            vectores_por_documento.append(vectores)

        persistir_documentos(
            documentos,
            trozos_por_documento,
            vectores_por_documento,
            forzar=True,
        )
        _actualizar_carga(
            identificador,
            "mapa",
            0,
            1,
            "Actualizando el mapa del conocimiento…",
        )
        try:
            from app.mapa import calcular_mapa

            calcular_mapa()
        except Exception as error:
            _LOGGER.exception(
                "No se pudo recalcular el mapa para la carga %s.", identificador
            )
            mensaje_final = (
                f"Tesis indexada; no se pudo actualizar el mapa: {error}"
            )
        else:
            mensaje_final = "Tesis indexada y disponible en el repositorio."
        _actualizar_carga(identificador, "lista", 1, 1, mensaje_final)
    except Exception as error:
        mensaje = str(error) or "No fue posible procesar el PDF de la tesis."
        _LOGGER.exception("Falló el procesamiento de la carga de tesis %s.", identificador)
        try:
            _actualizar_carga(identificador, "error", 0, 0, mensaje, error=mensaje)
        except Exception:
            _LOGGER.exception(
                "No se pudo registrar el error de la carga de tesis %s.",
                identificador,
            )


def registrar_tesis(
    usuario_id: int,
    titulo: str,
    autor: str,
    anio: int,
    programa: str,
    pdf_bytes: bytes,
) -> UUID:
    """Registra material, ejemplar y carga; el procesamiento no bloquea la petición."""
    titulo = titulo.strip() if isinstance(titulo, str) else ""
    autor = autor.strip() if isinstance(autor, str) else ""
    programa = programa.strip() if isinstance(programa, str) else ""
    if not 5 <= len(titulo) <= 300:
        raise ValueError("El título debe tener entre 5 y 300 caracteres.")
    if not 3 <= len(autor) <= 200:
        raise ValueError("El autor debe tener entre 3 y 200 caracteres.")
    if isinstance(anio, bool) or not isinstance(anio, int) or not 1990 <= anio <= 9999:
        raise ValueError("El año debe ser un número entre 1990 y el año actual.")
    if anio > date.today().year:
        raise ValueError("El año debe estar entre 1990 y el año actual.")
    if not 3 <= len(programa) <= 120:
        raise ValueError("El programa debe tener entre 3 y 120 caracteres.")
    validar_pdf(pdf_bytes)

    CARPETA.mkdir(parents=True, exist_ok=True)
    archivo: Path | None = None
    archivo_creado = False
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", (713022, usuario_id))
            cursor.execute(
                """
                SELECT 1
                FROM public.cargas_tesis
                WHERE usuario_id = %s AND etapa NOT IN ('lista', 'error')
                LIMIT 1
                """,
                (usuario_id,),
            )
            if cursor.fetchone():
                raise CargaEnCursoError("Ya tiene una tesis procesándose.")
            from app.salas import sala_de_programa
            sala_info = sala_de_programa(programa)
            sala_id = (
                sala_info.get("id")
                if isinstance(sala_info, dict)
                else (sala_info if isinstance(sala_info, int) else None)
            )
            cursor.execute(
                """
                INSERT INTO public.material
                    (titulo, autor, anio, tipo, tema, programa, editorial,
                     descripcion_corta, es_demo, subido_por, subido_en, sala_id)
                VALUES (%s, %s, %s, 'tesis', %s, %s,
                        'Institución Universitaria del Putumayo (repositorio)',
                        %s, false, %s, now(), %s)
                RETURNING id
                """,
                (titulo, autor, anio, programa, programa, "", usuario_id, sala_id),
            )
            material_id = int(cursor.fetchone()[0])
            cursor.execute(
                """
                INSERT INTO public.ejemplares
                    (material_id, codigo_barras, estante, estado)
                VALUES (%s, 'REP-' || lpad(%s::text, 6, '0'),
                        'Repositorio digital', 'disponible')
                """,
                (material_id, material_id),
            )
            cursor.execute(
                """
                INSERT INTO public.cargas_tesis
                    (usuario_id, material_id, etapa, avance, total, mensaje)
                VALUES (%s, %s, 'recibida', 0, 0, 'Tesis recibida.')
                RETURNING id
                """,
                (usuario_id, material_id),
            )
            carga_id = cursor.fetchone()[0]
            archivo = CARPETA / f"{material_id}.pdf"
            archivo.touch(exist_ok=False)
            archivo_creado = True
            archivo.write_bytes(pdf_bytes)
            ruta_relativa = archivo.relative_to(RAIZ).as_posix()
            cursor.execute(
                "UPDATE public.material SET archivo_pdf = %s WHERE id = %s",
                (ruta_relativa, material_id),
            )
    except Exception:
        if archivo_creado and archivo is not None and archivo.exists():
            archivo.unlink()
        raise

    hilo = threading.Thread(
        target=procesar_carga,
        args=(carga_id,),
        name=f"procesar-tesis-{material_id}",
        daemon=True,
    )
    try:
        hilo.start()
    except Exception as error:
        mensaje = f"No fue posible iniciar el procesamiento de la tesis: {error}"
        try:
            _actualizar_carga(
                carga_id, "error", 0, 0, mensaje, error=mensaje
            )
        except Exception:
            _LOGGER.exception("No se pudo marcar la carga %s como fallida.", carga_id)
        raise RuntimeError(mensaje) from error
    return carga_id


def progreso(carga_id: UUID | str, usuario_id: int) -> dict[str, object] | None:
    """Devuelve el avance únicamente al usuario propietario de la carga."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.etapa, c.avance, c.total, c.mensaje, c.error,
                   c.material_id, m.titulo
            FROM public.cargas_tesis AS c
            LEFT JOIN public.material AS m ON m.id = c.material_id
            WHERE c.id = %s AND c.usuario_id = %s
            """,
            (UUID(str(carga_id)), usuario_id),
        )
        fila = cursor.fetchone()
    if fila is None:
        return None
    etapa, avance, total, mensaje, error, material_id, titulo = fila
    porcentaje = min(100, round(avance * 100 / total)) if total else 0
    return {
        "etapa": etapa,
        "avance": avance,
        "total": total,
        "porcentaje": porcentaje,
        "mensaje": mensaje,
        "error": error,
        "material_id": material_id,
        "titulo": titulo,
    }


def programas() -> list[str]:
    """Lista los programas no vacíos que aparecen en el catálogo."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT programa
            FROM public.material
            WHERE programa IS NOT NULL AND btrim(programa) <> ''
            ORDER BY programa
            """
        )
        return [fila[0] for fila in cursor.fetchall()]
