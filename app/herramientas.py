"""Herramientas de negocio de la biblioteca, sin dependencia de un LLM."""

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _sin_tildes(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar títulos y autores."""
    descompuesto = unicodedata.normalize("NFD", (texto or "").casefold())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn").strip()

from app.config import (
    DIAS_PRESTAMO,
    HORAS_RESERVA,
    MAX_RENOVACIONES,
    MULTA_POR_DIA,
    TOP_K,
    UMBRAL_RELEVANCIA_SALA,
)
from app.db import conexion
from app import rag, salas
from app import bibliografia as constructor_bibliografia
from app.formatos import fecha_es, pesos
from app.consultas import normalizar_consulta


def _resultado(ok: bool, mensaje: str, datos: Any, **extras: Any) -> dict[str, Any]:
    """Construye resultados fáciles de serializar y deja visibles los tiempos."""
    return {"ok": ok, "mensaje": mensaje, "datos": datos, **extras}


def _filas(cursor: Any) -> list[dict[str, Any]]:
    nombres = [columna.name for columna in cursor.description]
    return [dict(zip(nombres, fila, strict=True)) for fila in cursor.fetchall()]


def _serializar(valor: Any) -> Any:
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, dict):
        return {llave: _serializar(elemento) for llave, elemento in valor.items()}
    if isinstance(valor, list):
        return [_serializar(elemento) for elemento in valor]
    return valor


_STOPWORDS_BUSQUEDA = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "a", "al",
    "en", "sobre", "para", "por", "con", "sin", "y", "o", "u", "e", "que", "es",
    "son", "libro", "libros", "tesis", "material", "materiales", "texto", "textos",
    "obra", "obras", "tema", "temas", "quiero", "quisiera", "busco", "buscar",
    "necesito", "tienen", "hay", "algun", "alguno", "alguna", "algunos", "algunas",
    "buen", "bueno", "buena", "buenos", "buenas", "mejor", "mejores", "favor",
    "porfa", "dame", "muestra", "muestrame", "ver", "recomienda", "recomiendame",
    "sugiere", "sugiereme", "informacion", "estudiar", "leer", "acervo", "biblioteca",
    "sala", "seccion", "donde", "esta", "estan", "cual", "cuales", "como", "mas",
}


def _raiz_palabra(palabra: str) -> str:
    """Calcula la raíz léxica aproximada de un término en español para filtrado temático."""
    norm = _sin_tildes(palabra.lower())
    if len(norm) <= 3:
        return norm
    if norm.startswith("contab"):  # contabilidad, contable, contador
        return "contab"
    if norm.startswith("market"):  # marketing, mercadeo
        return "market"
    if norm.startswith("progra"):  # programacion, programar
        return "progra"
    if norm.startswith("financ"):  # finanzas, financiero
        return "financ"
    if norm.startswith("admin"):  # administracion, administrativo
        return "admin"
    if norm.startswith("invest"):  # investigacion
        return "invest"
    if norm.startswith("comput"):  # computacion, computadoras
        return "comput"
    if norm.startswith("ambient"): # ambiental, ambiente, medioambiente
        return "ambient"
    if norm.startswith("contamin"):# contaminacion, contaminante, contaminantes
        return "contamin"
    if norm.startswith("ecolog"):  # ecologia, ecologico
        return "ecolog"
    if norm.startswith("forest"):  # forestal, agroforestal
        return "forest"
    if norm.startswith("agronom"): # agronomia
        return "agronom"
    if norm.startswith("residu"):  # residuos
        return "residu"
    if norm.startswith("sostenib"):# sostenibilidad, sostenible
        return "sostenib"
    sufijos = (
        "idades", "idad", "aciones", "acion", "adoras", "adores", "adora", "ador",
        "mientos", "miento", "encias", "encia", "ancias", "ancia", "amientos", "amiento",
        "erias", "eria", "ismos", "ismo", "istas", "ista", "antes", "ante",
        "ientes", "iente", "ables", "able", "ibles", "ible", "arios", "ario", "arias", "aria",
        "ando", "iendo", "ados", "adas", "ado", "ada", "idos", "idas", "ido", "ida",
        "eros", "eras", "ero", "era", "ores", "oras", "es", "os", "as", "s",
    )
    for sufijo in sufijos:
        if norm.endswith(sufijo) and len(norm) - len(sufijo) >= 3:
            return norm[:-len(sufijo)]
    return norm


def _extraer_terminos_tematicos(consulta: str) -> list[str]:
    """Extrae términos temáticos relevantes descartando palabras funcionales y de parada."""
    palabras = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", _sin_tildes(consulta))
    return [p for p in palabras if len(p) >= 3 and p not in _STOPWORDS_BUSQUEDA]


def _extraer_tema_consulta(consulta: str) -> str:
    """Extrae el término o frase temática central de una consulta de búsqueda."""
    texto = (consulta or "").strip()
    texto = re.sub(r'^[¿?¡!.,;:\"«“”»\'\s]+|[¿?¡!.,;:\"«“”»\'\s]+$', '', texto)
    m = re.search(
        r"(?i)\b(?:sobre|de|acerca\s+de|en\s+torno\s+a)\s+([a-zA-ZáéíóúñÁÉÍÓÚÑ0-9\s]{2,})$",
        texto,
    )
    if m:
        candidato = m.group(1).strip()
        candidato_norm = _sin_tildes(candidato)
        if candidato_norm not in ("la biblioteca", "el catalogo", "esta sala", "la sala", "leer", "estudiar", "un libro", "libros"):
            return candidato
    limpio = re.sub(
        r"(?i)^(?:quiero|quisiera|busco|buscar|necesito|tienen|dame|mu[eé]strame|hay)\s+",
        "",
        texto,
    )
    limpio = re.sub(
        r"(?i)^(?:un|una|unos|unas|el|la|los|las|alg[uú]n|algunos|algunas)\s+",
        "",
        limpio,
    )
    limpio = re.sub(
        r"(?i)^(?:libros?|tesis|material(?:es)?|textos?|art[ií]culos?|publicaci[oó]n|publicaciones|informaci[oó]n)\s+(?:de|sobre)?\s*",
        "",
        limpio,
    )
    limpio = limpio.strip()
    return limpio if limpio else texto


def _coincide_termino_tematico(terminos: list[str], material: dict[str, Any]) -> bool:
    """Verifica si el material contiene al menos uno de los términos temáticos o su raíz en metadatos."""
    if not terminos:
        return True
    campos = [
        str(material.get("titulo") or ""),
        str(material.get("tema") or ""),
        str(material.get("programa") or ""),
        str(material.get("descripcion_corta") or ""),
        str(material.get("descripcion") or ""),
        str(material.get("resena") or ""),
        str(material.get("materia") or ""),
        str(material.get("palabras_clave") or ""),
        str(material.get("autor") or ""),
    ]
    texto_mat = _sin_tildes(" ".join(campos))
    for t in terminos:
        raiz = _raiz_palabra(t)
        if re.search(rf"\b{re.escape(raiz)}", texto_mat) or (len(raiz) >= 4 and raiz in texto_mat):
            return True
        if raiz == "market" and ("mercadeo" in texto_mat or "mercadotecnia" in texto_mat or "marketing" in texto_mat):
            return True
        if raiz == "contab" and ("contabilidad" in texto_mat or "contable" in texto_mat or "costos" in texto_mat or "tributaria" in texto_mat):
            return True
        if raiz == "ambient" and ("ambiente" in texto_mat or "ambiental" in texto_mat or "agroambiental" in texto_mat):
            return True
        if raiz == "contamin" and ("contaminacion" in texto_mat or "contaminante" in texto_mat or "contaminantes" in texto_mat):
            return True
        if t in ("red", "redes") and re.search(r"\bred(?:es)?\b", texto_mat):
            return True
    return False


def _obtener_sugerencia_otra_sala(
    materiales: list[dict[str, Any]], sala_actual_slug: str | None
) -> dict[str, Any] | None:
    """Identifica qué otra sala contiene materiales relevantes cuando la actual no tiene."""
    ids = [int(m["material_id"]) for m in materiales if m.get("material_id")]
    if not ids:
        return None
    slug_actual = (sala_actual_slug or "").strip().lower()
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT s.slug, s.nombre, count(m.id) AS cantidad
            FROM public.material AS m
            JOIN public.salas AS s ON s.id = m.sala_id
            WHERE m.id = ANY(%s) AND lower(btrim(s.slug)) <> lower(btrim(%s))
            GROUP BY s.slug, s.nombre
            ORDER BY cantidad DESC, s.slug
            LIMIT 1
            """,
            (ids, slug_actual),
        )
        fila = cursor.fetchone()
    if fila:
        return {"slug": fila[0], "nombre": fila[1], "cantidad": fila[2]}
    return None


def buscar_semantico(consulta: str, k: int = TOP_K, sala_slug: str | None = None) -> dict[str, Any]:
    """Busca materiales relacionados por sus reseñas o resúmenes vectoriales con filtrado temático y sugerencia de sala."""
    try:
        sala_norm = (
            sala_slug.strip().lower()
            if sala_slug and sala_slug.strip().lower() not in ("", "todas", "toda", "general", "null", "none")
            else None
        )
        sala_info = salas.sala_por_slug(sala_norm) if sala_norm else None
        sala_actual_nombre = sala_info["nombre"] if sala_info else "esta sala"

        terminos_tematicos = _extraer_terminos_tematicos(consulta)
        tema_extraido = _extraer_tema_consulta(consulta)

        materiales_raw, tiempos = rag.buscar_materiales_semantico(consulta, k=k, sala_slug=sala_norm)
        materiales = [
            _serializar(m)
            for m in materiales_raw
            if float(m.get("similitud") or 0) >= UMBRAL_RELEVANCIA_SALA
            and (not terminos_tematicos or _coincide_termino_tematico(terminos_tematicos, _serializar(m)))
        ]

        # Caso 1: Dentro de la sala no hay nada relevante pero se especificó sala
        if not materiales and sala_norm:
            globales_raw, tiempos_glob = rag.buscar_materiales_semantico(consulta, k=max(k, 6), sala_slug=None)
            for tk, tv in (tiempos_glob or {}).items():
                tiempos[tk] = tiempos.get(tk, 0) + tv
            validos_glob = [
                _serializar(m)
                for m in globales_raw
                if float(m.get("similitud") or 0) >= UMBRAL_RELEVANCIA_SALA
                and (not terminos_tematicos or _coincide_termino_tematico(terminos_tematicos, _serializar(m)))
            ]
            if validos_glob:
                sug = _obtener_sugerencia_otra_sala(validos_glob, sala_norm)
                if sug:
                    mats_enriquecidos = enriquecer_materiales(validos_glob)
                    mats_otra = [m for m in mats_enriquecidos if m.get("sala_slug") == sug["slug"]]
                    if not mats_otra:
                        mats_otra = mats_enriquecidos
                    cant = int(sug["cantidad"])
                    texto_res = "1 resultado" if cant == 1 else f"{cant} resultados"
                    titulos = [m["titulo"] for m in mats_otra if m.get("titulo")]
                    titulos_ejemplos = ", ".join(f"«{t}»" for t in titulos[:2]) if titulos else "material especializado"
                    mensaje = (
                        f"En la {sala_actual_nombre} no tengo material sobre {tema_extraido}, "
                        f"pero en la {sug['nombre']} hay {texto_res}: {titulos_ejemplos}. "
                        "¿Quieres que te lleve?"
                    )
                    return _resultado(
                        True,
                        mensaje,
                        mats_otra,
                        materiales=mats_otra,
                        tiempos=tiempos,
                        sugerencia_sala={
                            "slug": sug["slug"],
                            "nombre": sug["nombre"],
                            "motivo": f"Hay {texto_res} en {sug['nombre']}.",
                        },
                    )
            msg_no_hallado = (
                f"No encontré material sobre {tema_extraido} en la biblioteca."
                if tema_extraido and tema_extraido.lower() not in ("eso", "el tema", "nada")
                else "No encontré material sobre eso en la biblioteca."
            )
            return _resultado(
                False,
                msg_no_hallado,
                [],
                materiales=[],
                tiempos=tiempos,
            )

        # Caso 2: Dentro de la sala hay algo relevante, verificar si otra sala tiene más del doble
        if materiales and sala_norm:
            globales_raw, _ = rag.buscar_materiales_semantico(consulta, k=10, sala_slug=None)
            validos_glob = [
                _serializar(m)
                for m in globales_raw
                if float(m.get("similitud") or 0) >= UMBRAL_RELEVANCIA_SALA
                and (not terminos_tematicos or _coincide_termino_tematico(terminos_tematicos, _serializar(m)))
            ]
            if validos_glob:
                sug = _obtener_sugerencia_otra_sala(validos_glob, sala_norm)
                if sug and int(sug["cantidad"]) > 2 * len(materiales):
                    cant = int(sug["cantidad"])
                    texto_res = "1 resultado" if cant == 1 else f"{cant} resultados"
                    mats_actuales = enriquecer_materiales(materiales)
                    prefijo = f"En la {sala_actual_nombre} encontré:\n"
                    lineas = []
                    for m in mats_actuales:
                        disp = int(m.get("disponibles") or 0)
                        tot = int(m.get("total") or 0)
                        disp_txt = f"{disp} de {tot} disponibles" if disp > 0 else "sin ejemplares disponibles"
                        lineas.append(
                            f"«{m.get('titulo', 'Sin título')}», de {m.get('autor', 'autor no registrado')} "
                            f"({m.get('tipo', 'material')}); {disp_txt}."
                        )
                    mensaje = prefijo + "\n".join(lineas) + f"\n\nTambién hay {texto_res} en la {sug['nombre']}."
                    return _resultado(
                        True,
                        mensaje,
                        mats_actuales,
                        materiales=mats_actuales,
                        tiempos=tiempos,
                        sugerencia_sala={
                            "slug": sug["slug"],
                            "nombre": sug["nombre"],
                            "motivo": f"Hay {texto_res} en {sug['nombre']}.",
                        },
                    )

        # Caso 3: Sin sala elegida o sin sugerencia especial
        if not materiales:
            msg_no_hallado = (
                f"No encontré material sobre {tema_extraido} en la biblioteca."
                if tema_extraido and tema_extraido.lower() not in ("eso", "el tema", "nada")
                else "No encontré material sobre eso en la biblioteca."
            )
            return _resultado(
                False,
                msg_no_hallado,
                [],
                materiales=[],
                tiempos=tiempos,
            )

        mats_ret = enriquecer_materiales(materiales)
        return _resultado(
            True,
            "Encontré materiales relacionados.",
            mats_ret,
            materiales=mats_ret,
            tiempos=tiempos,
        )
    except Exception as error:
        return _resultado(False, str(error), [], materiales=[], tiempos={})


def resumir_material(titulo: str, pregunta: str, sala_slug: str | None = None) -> dict[str, Any]:
    """Recupera la reseña de un libro o el resumen y páginas de una tesis."""
    consulta_tipo = _sin_tildes(re.sub(r'[«“\"][^»”\"]*[»”\"]', '', pregunta))
    tipo_pedido = (
        "tesis" if re.search(r"\btesis\b", consulta_tipo)
        else "libro" if re.search(r"\blibro\b", consulta_tipo)
        else None
    )
    etiqueta = {"tesis": "esa tesis", "libro": "ese libro"}.get(tipo_pedido, "ese material")
    try:
        candidato = resolver_material(titulo, sala_slug=None)
        materiales = list({
            int(material["material_id"]): material
            for material in candidato.get("datos") or []
            if material.get("tipo") in ("libro", "tesis")
            and (tipo_pedido is None or material.get("tipo") == tipo_pedido)
        }.values())
        if not candidato.get("ok") or not materiales:
            if not candidato.get("ok") and str(candidato.get("mensaje", "")).lower().startswith(
                ("no fue posible", "no está disponible", "no esta disponible")
            ):
                return _resultado(False, candidato["mensaje"], [], materiales=[])
            return _resultado(
                False, f"No encontré {etiqueta} en el catálogo.", [], materiales=[]
            )
        if len(materiales) > 1:
            opciones = "; ".join(
                f"«{material['titulo']}» ({material['tipo']}, {material.get('autor') or 'autor no indicado'})"
                for material in materiales
            )
            return _resultado(
                False, f"Encontré varias coincidencias. ¿Cuál material quieres consultar? {opciones}.",
                [], materiales=enriquecer_materiales(materiales), fuentes=[],
            )
        material = materiales[0]
        etiqueta = "esa tesis" if material["tipo"] == "tesis" else "ese libro"
        fragmentos, tiempos = rag.buscar_fragmentos_material(
            int(material["material_id"]), pregunta, limite_completa=3
        )
        tipos_fuente = (
            {"resumen_tesis", "tesis_completa"}
            if material["tipo"] == "tesis" else {"resena_libro"}
        )
        fragmentos = [
            fragmento for fragmento in fragmentos
            if fragmento.get("material_id") == int(material["material_id"])
            and fragmento.get("tipo") in tipos_fuente
            and str(fragmento.get("texto") or "").strip()
        ]
        if not fragmentos:
            return _resultado(
                False, f"No hay una reseña o resumen indexado disponible para {etiqueta}.",
                [], materiales=enriquecer_materiales([material]), tiempos=tiempos, fuentes=[],
            )
        tarjetas = enriquecer_materiales([material])
        fuentes = [
            {
                "titulo": material.get("titulo"),
                "seccion": fragmento.get("seccion") or {
                    "resumen_tesis": "Resumen", "resena_libro": "Reseña",
                }.get(fragmento.get("tipo"), "Texto indexado"),
                "tipo": fragmento.get("tipo"),
                "fuente": fragmento.get("fuente"),
                "material_id": int(material["material_id"]),
            }
            for fragmento in fragmentos
        ]
        return _resultado(
            True,
            "Encontré el material y sus fragmentos de conocimiento.",
            fragmentos,
            tiempos=tiempos,
            materiales=tarjetas,
            fuentes=fuentes,
        )
    except Exception as error:
        mensaje = str(error)
        if etiqueta != "esa tesis":
            mensaje = mensaje.replace(
                "de la tesis", "del libro" if etiqueta == "ese libro" else "del material"
            )
        return _resultado(False, mensaje, [], materiales=[], tiempos={})


def generar_bibliografia(
    tema: str, cantidad: int = 5, norma: str = "APA", sala_slug: str | None = None
) -> dict[str, Any]:
    """Construye referencias APA o IEEE exclusivamente con datos del catálogo."""
    return constructor_bibliografia.generar_bibliografia(tema, cantidad, norma, sala_slug=sala_slug)


def buscar_exacto(texto: str, sala_slug: str | None = None) -> dict[str, Any]:
    """Busca un título o autor usando la consulta SQL parametrizada de RAG."""
    try:
        sala_norm = (
            sala_slug.strip().lower()
            if sala_slug and sala_slug.strip().lower() not in ("", "todas", "toda", "general", "null", "none")
            else None
        )
        materiales = rag.buscar_exacto_sql(texto, sala_slug=sala_norm)
        if not materiales and sala_norm:
            globales = rag.buscar_exacto_sql(texto, sala_slug=None)
            if globales:
                sug = _obtener_sugerencia_otra_sala([_serializar(m) for m in globales], sala_norm)
                if sug:
                    cant = int(sug["cantidad"])
                    texto_res = "1 resultado" if cant == 1 else f"{cant} resultados"
                    mensaje = (
                        f"En esta sala no tengo material sobre eso, pero en la {sug['nombre']} "
                        f"hay {texto_res}. ¿Quieres que te lleve?"
                    )
                    return _resultado(
                        False,
                        mensaje,
                        [],
                        sugerencia_sala={
                            "slug": sug["slug"],
                            "nombre": sug["nombre"],
                            "motivo": f"Hay {texto_res} en {sug['nombre']}.",
                        },
                    )
        return _resultado(
            bool(materiales),
            "Encontré coincidencias." if materiales else "No encontré coincidencias en el acervo.",
            _serializar(materiales),
        )
    except Exception as error:
        return _resultado(False, str(error), [])


def enriquecer_materiales(materiales: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Completa en una sola consulta los datos de catálogo y ejemplares."""
    ids = list(dict.fromkeys(
        int(material["material_id"])
        for material in materiales
        if material.get("material_id") is not None
    ))
    if not ids:
        return []

    sql = """
        SELECT m.id AS material_id, m.titulo, m.autor, m.anio, m.tipo,
               m.tema, m.programa, m.descripcion_corta,
               COALESCE(array_agg(DISTINCT e.estante ORDER BY e.estante)
                   FILTER (WHERE e.estante IS NOT NULL), ARRAY[]::varchar[]) AS estantes,
               count(e.id) FILTER (WHERE e.estado = 'disponible') AS disponibles,
               count(e.id) AS total,
               count(e.id) FILTER (WHERE e.estado = 'prestado') AS prestados,
               count(e.id) FILTER (WHERE e.estado = 'reservado') AS reservados,
               s.nombre AS sala_nombre, s.slug AS sala_slug
        FROM public.material AS m
        LEFT JOIN public.salas AS s ON s.id = m.sala_id
        LEFT JOIN public.ejemplares AS e ON e.material_id = m.id
        WHERE m.id = ANY(%s)
        GROUP BY m.id, s.nombre, s.slug
    """
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(sql, (ids,))
        filas = _filas(cursor)
    por_id = {int(fila["material_id"]): _serializar(fila) for fila in filas}
    resultado = []
    for material in materiales:
        enriquecido = por_id.get(int(material["material_id"]))
        if enriquecido is None:
            continue
        enriquecido["similitud"] = material.get("similitud")
        resultado.append(enriquecido)
    return resultado


def _obtener_resena_material(material_id: int) -> str | None:
    """Obtiene el primer fragmento de reseña o resumen de un material."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.texto
                FROM conocimiento.fragmentos AS f
                JOIN conocimiento.documentos AS d ON d.id = f.documento_id
                WHERE d.material_id = %s AND d.tipo = ANY(%s)
                ORDER BY f.orden
                LIMIT 1
                """,
                (material_id, ["resena_libro", "resumen_tesis"]),
            )
            fila = cursor.fetchone()
            if fila and fila[0]:
                return str(fila[0])
    except Exception:
        pass
    return None


def panorama_catalogo(sala_slug: str | None = None) -> dict[str, Any]:
    """Genera un panorama real del acervo con totales por sala y títulos destacados."""
    try:
        todas_salas = salas.listar_salas()
        sala_actual = salas.sala_por_slug(sala_slug) if sala_slug else None

        with conexion() as conn, conn.cursor() as cursor:
            if sala_actual:
                cursor.execute(
                    """
                    SELECT m.id AS material_id, m.titulo, m.autor, m.tipo, m.anio,
                           count(e.id) FILTER (WHERE e.estado = 'disponible') AS disponibles,
                           count(e.id) AS total
                    FROM public.material AS m
                    LEFT JOIN public.ejemplares AS e ON e.material_id = m.id
                    WHERE m.sala_id = (SELECT s.id FROM public.salas s WHERE lower(btrim(s.slug)) = lower(btrim(%s)))
                    GROUP BY m.id
                    ORDER BY count(e.id) FILTER (WHERE e.estado = 'disponible') DESC, m.anio DESC NULLS LAST, m.id
                    LIMIT 4
                    """,
                    (sala_slug,),
                )
                destacados_raw = _filas(cursor)
            else:
                cursor.execute(
                    """
                    SELECT m.id AS material_id, m.titulo, m.autor, m.tipo, m.anio,
                           count(e.id) FILTER (WHERE e.estado = 'disponible') AS disponibles,
                           count(e.id) AS total
                    FROM public.material AS m
                    LEFT JOIN public.ejemplares AS e ON e.material_id = m.id
                    GROUP BY m.id
                    ORDER BY count(e.id) FILTER (WHERE e.estado = 'disponible') DESC, m.anio DESC NULLS LAST, m.id
                    LIMIT 4
                    """
                )
                destacados_raw = _filas(cursor)

        destacados = _serializar(destacados_raw)
        materiales = enriquecer_materiales(destacados)

        lineas: list[str] = []
        if sala_actual:
            libros = sala_actual.get("libros", 0)
            tesis = sala_actual.get("tesis", 0)
            total = sala_actual.get("total", libros + tesis)
            lineas.append(
                f"En la {sala_actual['nombre']} contamos con {libros} libros y {tesis} tesis ({total} en total)."
            )
        else:
            total_libros = sum(s.get("libros", 0) for s in todas_salas)
            total_tesis = sum(s.get("tesis", 0) for s in todas_salas)
            total_general = sum(s.get("total", 0) for s in todas_salas)
            lineas.append(
                f"La biblioteca cuenta con {total_general} materiales en total ({total_libros} libros y {total_tesis} tesis) distribuidos en 5 salas temáticas:"
            )
            for s in todas_salas:
                lineas.append(f"- {s['nombre']}: {s.get('libros', 0)} libros y {s.get('tesis', 0)} tesis.")

        if materiales:
            lineas.append("\nAlgunos títulos destacados del acervo son:")
            for m in materiales[:4]:
                disp = int(m.get("disponibles") or 0)
                tot = int(m.get("total") or 0)
                texto_disp = f"{disp} de {tot} disponibles" if disp > 0 else "sin ejemplares disponibles"
                lineas.append(f"• «{m.get('titulo')}», de {m.get('autor', 'autor no registrado')} ({texto_disp}).")

        lineas.append("\n¿Sobre qué tema buscas?")
        mensaje = "\n".join(lineas)
        return _resultado(True, mensaje, materiales, materiales=materiales)
    except Exception as error:
        return _resultado(False, str(error), [], materiales=[])


def mas_prestados(sala_slug: str | None = None) -> dict[str, Any]:
    """Consulta los materiales más prestados agrupando por material en la BD."""
    try:
        sala_norm = (
            sala_slug.strip().lower()
            if sala_slug and sala_slug.strip().lower() not in ("", "todas", "toda", "general", "null", "none")
            else None
        )
        sql = """
            SELECT m.id AS material_id, m.titulo, m.autor, m.tipo, m.anio,
                   count(p.id) AS total_prestamos
            FROM public.material AS m
            JOIN public.ejemplares AS e ON e.material_id = m.id
            JOIN public.prestamos AS p ON p.ejemplar_id = e.id
            WHERE (%s::text IS NULL OR m.sala_id = (
                SELECT s.id FROM public.salas AS s WHERE lower(btrim(s.slug)) = lower(btrim(%s))
            ))
            GROUP BY m.id, m.titulo, m.autor, m.tipo, m.anio
            ORDER BY total_prestamos DESC, m.titulo
            LIMIT 5
        """
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(sql, (sala_norm, sala_norm))
            filas = _serializar(_filas(cursor))

        if not filas:
            msg = "Aún no se registran suficientes préstamos en el sistema para determinar los más prestados. Te sugiero explorar el catálogo general."
            return _resultado(True, msg, [], materiales=[])

        top3 = filas[:3]
        materiales = enriquecer_materiales(top3)
        prestamos_map = {int(f["material_id"]): int(f["total_prestamos"]) for f in top3}
        for m in materiales:
            m["total_prestamos"] = prestamos_map.get(int(m["material_id"]), 0)

        conteos = [m["total_prestamos"] for m in materiales]
        hay_empate = len(conteos) > 1 and len(set(conteos)) < len(conteos)

        sala_info = salas.sala_por_slug(sala_norm)
        prefijo = f"En la {sala_info['nombre']}, los materiales más prestados son:\n" if sala_info else "Los materiales más prestados de la biblioteca son:\n"

        lineas = [prefijo.strip()]
        for idx, m in enumerate(materiales, start=1):
            disp = int(m.get("disponibles") or 0)
            tot = int(m.get("total") or 0)
            disp_txt = f"{disp} de {tot} disponibles" if disp > 0 else "sin ejemplares disponibles"
            cants = m["total_prestamos"]
            vez_txt = "préstamo" if cants == 1 else "préstamos"
            lineas.append(f"{idx}. «{m['titulo']}», de {m.get('autor', 'autor no registrado')} ({cants} {vez_txt}; {disp_txt}).")

        if hay_empate:
            lineas.append("\n(Nota: existe un empate en el número de préstamos entre algunos de estos títulos).")

        return _resultado(True, "\n".join(lineas), materiales, materiales=materiales)
    except Exception as error:
        return _resultado(False, str(error), [], materiales=[])


def ubicacion_material(texto: str, sala_slug: str | None = None) -> dict[str, Any]:
    """Ubica un material en el catálogo y devuelve sus estantes y disponibilidad física."""
    try:
        # La ubicación de un título concreto busca en todo el catálogo
        candidato = resolver_material(texto, sala_slug=None)
        if not candidato.get("ok") or not candidato.get("datos"):
            # Reintentar limpiando prefijos de petición
            limpio = re.sub(
                r"(?i)^(?:el\s+libro\s+|la\s+tesis\s+|el\s+material\s+|el\s+ejemplar\s+|el\s+|la\s+)",
                "",
                texto.strip(" ¿?!¡.,:;\"'“”«»"),
            ).strip()
            candidato = resolver_material(limpio, sala_slug=None)
            if not candidato.get("ok") or not candidato.get("datos"):
                return _resultado(False, "No encontré ese material en el catálogo para indicarte su estante.", [], materiales=[])

        datos = candidato["datos"]
        texto_norm = _sin_tildes(texto).strip(" ¿?!¡.,:;\"'“”«»")
        texto_sin_prefijo = re.sub(
            r"^(?:el\s+libro|la\s+tesis|el\s+material|el\s+ejemplar|el|la)\s+",
            "",
            texto_norm,
        ).strip()

        # Si un título coincide exactamente (normalizado), usarlo directamente
        exactos = [
            d for d in datos
            if _sin_tildes(str(d.get("titulo") or "")).strip() in (texto_norm, texto_sin_prefijo)
        ]
        if exactos:
            datos = [exactos[0]]

        if len(datos) > 1:
            materiales = enriquecer_materiales(datos[:5])
            lineas = ["Encontré varias coincidencias. ¿A cuál te refieres?"]
            for m in materiales:
                lineas.append(f"• «{m['titulo']}», de {m.get('autor', 'autor no registrado')}.")
            return _resultado(True, "\n".join(lineas), materiales, materiales=materiales)

        material_id = int(datos[0]["material_id"])
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.id, m.titulo, m.autor,
                       COALESCE(array_agg(DISTINCT e.estante ORDER BY e.estante)
                           FILTER (WHERE e.estante IS NOT NULL), ARRAY[]::varchar[]) AS estantes,
                       count(e.id) FILTER (WHERE e.estado = 'disponible') AS disponibles,
                       count(e.id) AS total,
                       s.nombre AS sala_nombre
                FROM public.material AS m
                LEFT JOIN public.salas AS s ON s.id = m.sala_id
                LEFT JOIN public.ejemplares AS e ON e.material_id = m.id
                WHERE m.id = %s
                GROUP BY m.id, s.nombre
                """,
                (material_id,),
            )
            fila = cursor.fetchone()
            if not fila:
                return _resultado(False, "No encontré información de ejemplares para ese material.", [], materiales=[])

        col_nombres = ["material_id", "titulo", "autor", "estantes", "disponibles", "total", "sala_nombre"]
        info = dict(zip(col_nombres, fila, strict=True))
        info = _serializar(info)
        materiales = enriquecer_materiales([info])

        estantes = info.get("estantes") or []
        disp = int(info.get("disponibles") or 0)
        tot = int(info.get("total") or 0)
        disp_txt = f"hay {disp} de {tot} disponibles" if disp > 0 else f"no hay ejemplares disponibles de {tot} registrados"
        sala_nombre = info.get("sala_nombre")
        sala_extra = f" Está en la {sala_nombre}." if sala_nombre else ""

        if estantes:
            if len(estantes) == 1:
                estantes_txt = f"el estante {estantes[0]}"
            elif len(estantes) == 2:
                estantes_txt = f"los estantes {estantes[0]} y {estantes[1]}"
            else:
                estantes_txt = f"los estantes {', '.join(estantes[:-1])} y {estantes[-1]}"
            mensaje = f"«{info['titulo']}» está en {estantes_txt}; {disp_txt}.{sala_extra}"
        else:
            mensaje = f"«{info['titulo']}» está en la colección general; {disp_txt}.{sala_extra}"

        return _resultado(True, mensaje, materiales, materiales=materiales)
    except Exception as error:
        return _resultado(False, str(error), [], materiales=[])


def recomendar(tema: str | None = None, sala_slug: str | None = None) -> dict[str, Any]:
    """Recomienda títulos destacados si no hay tema, o por afinidad y disponibilidad si hay tema."""
    try:
        sala_norm = (
            sala_slug.strip().lower()
            if sala_slug and sala_slug.strip().lower() not in ("", "todas", "toda", "general", "null", "none")
            else None
        )
        sala_info = salas.sala_por_slug(sala_norm)

        # Caso 1: Sin tema específico
        if not tema or not str(tema).strip():
            sql = """
                SELECT m.id AS material_id, m.titulo, m.autor, m.tipo, m.anio,
                       count(p.id) AS total_prestamos
                FROM public.material AS m
                LEFT JOIN public.ejemplares AS e ON e.material_id = m.id
                LEFT JOIN public.prestamos AS p ON p.ejemplar_id = e.id
                WHERE (%s::text IS NULL OR m.sala_id = (
                    SELECT s.id FROM public.salas AS s WHERE lower(btrim(s.slug)) = lower(btrim(%s))
                ))
                GROUP BY m.id, m.titulo, m.autor, m.tipo, m.anio
                ORDER BY count(p.id) DESC, m.anio DESC NULLS LAST, m.id
                LIMIT 3
            """
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(sql, (sala_norm, sala_norm))
                filas = _serializar(_filas(cursor))
            materiales = enriquecer_materiales(filas)

            lugar = f"de la {sala_info['nombre']}" if sala_info else "del acervo"
            lineas = [
                "¿Sobre qué tema o programa académico buscas? Dime qué materia te interesa para afinar la recomendación.",
                f"\nMientras tanto, te sugiero estos 3 títulos destacados {lugar} (los más solicitados y consultados):",
            ]
            for idx, m in enumerate(materiales[:3], start=1):
                disp = int(m.get("disponibles") or 0)
                tot = int(m.get("total") or 0)
                disp_txt = f"{disp} de {tot} disponibles" if disp > 0 else "sin ejemplares disponibles"
                lineas.append(f"{idx}. «{m['titulo']}», de {m.get('autor', 'autor no registrado')} ({disp_txt}).")

            lineas.append("\n¿Te interesa alguno de estos títulos o buscas otro tema?")
            return _resultado(True, "\n".join(lineas), materiales, materiales=materiales)

        # Caso 2: Con tema específico
        tema_limpio = str(tema).strip()
        busqueda = buscar_semantico(tema_limpio, k=3, sala_slug=sala_norm)
        if busqueda.get("sugerencia_sala"):
            return busqueda
        candidatos = busqueda.get("datos") or []
        if not candidatos and sala_norm:
            busqueda = buscar_semantico(tema_limpio, k=3, sala_slug=None)
            if busqueda.get("sugerencia_sala"):
                return busqueda
            candidatos = busqueda.get("datos") or []

        if not candidatos:
            exacto = buscar_exacto(tema_limpio, sala_slug=sala_norm)
            candidatos = exacto.get("datos") or []

        if not candidatos:
            return _resultado(
                False,
                f"No encontré materiales en el acervo directamente relacionados con «{tema_limpio}» para recomendarte. ¿Quieres probar con otro tema o sala?",
                [],
                materiales=[],
            )

        top3 = candidatos[:3]
        materiales = enriquecer_materiales(top3)

        lineas = [
            f"Te recomiendo estos materiales según su relevancia temática con «{tema_limpio}» y su disponibilidad en el acervo (no como un juicio de valor absoluto):"
        ]
        for idx, m in enumerate(materiales, start=1):
            disp = int(m.get("disponibles") or 0)
            tot = int(m.get("total") or 0)
            disp_txt = f"{disp} de {tot} disponibles" if disp > 0 else "sin ejemplares disponibles"

            resena = _obtener_resena_material(int(m["material_id"]))
            if resena:
                frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", resena) if f.strip()]
                razon = frases[0] if frases else "Contenido especializado en el área."
            else:
                prog = m.get("programa") or "formación universitaria"
                razon = f"Material de referencia para {prog}."

            lineas.append(f"{idx}. «{m['titulo']}», de {m.get('autor', 'autor no registrado')} ({disp_txt}). {razon}")

        return _resultado(True, "\n".join(lineas), materiales, materiales=materiales)
    except Exception as error:
        return _resultado(False, str(error), [], materiales=[])


def _disponibilidad(cursor: Any, material_id: int) -> dict[str, Any] | None:
    """Lee existencias y fechas sin revelar quién tiene un préstamo o reserva."""
    cursor.execute("""
        SELECT v.material_id, v.titulo, v.autor, v.tipo, v.total, v.disponibles,
               v.reservados, v.prestados,
               (SELECT min(p.fecha_vencimiento)
                FROM public.prestamos AS p
                JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
                WHERE e.material_id = v.material_id AND p.estado = 'activo'
                  AND p.fecha_vencimiento >= current_date) AS proximo_vencimiento,
               (SELECT min(r.expira_en) FROM public.reservas r
                WHERE r.material_id = v.material_id AND r.estado = 'activa'
                  AND r.ejemplar_id IS NOT NULL AND r.expira_en >= now()) AS proxima_liberacion_reserva,
               (SELECT count(*) FROM public.reservas r
                WHERE r.material_id = v.material_id AND r.estado = 'activa'
                  AND r.ejemplar_id IS NULL AND r.expira_en >= now()) AS reservas_en_espera,
               EXISTS (
                   SELECT 1 FROM public.reservas AS r
                   WHERE r.material_id = v.material_id AND r.estado = 'activa'
                     AND r.expira_en >= now()
               ) AS tiene_reservas
        FROM public.v_disponibilidad AS v
        WHERE v.material_id = %s
    """, (material_id,))
    fila = cursor.fetchone()
    return _serializar(dict(zip((c.name for c in cursor.description), fila, strict=True))) if fila else None


def mensaje_disponibilidad(datos: dict[str, Any]) -> str:
    """Explica la diferencia entre copias libres, apartadas y solicitudes en espera."""
    libres = int(datos.get("disponibles") or 0)
    total = int(datos.get("total") or 0)
    reservados = int(datos.get("reservados") or 0)
    prestados = int(datos.get("prestados") or 0)
    if libres:
        mensaje = f"Quedan {libres} de {total} ejemplares disponibles."
        if reservados:
            mensaje += f" Ejemplares ya reservados: {reservados}; se puede apartar otra copia."
        return mensaje
    mensaje = f"No hay ejemplares disponibles. Ejemplares reservados: {reservados}; prestados: {prestados}."
    if datos.get("proxima_liberacion_reserva"):
        mensaje += f" El próximo apartado vence el {fecha_es(datos['proxima_liberacion_reserva'])}; esa copia podría liberarse si no se retira."
    if datos.get("proximo_vencimiento"):
        mensaje += f" Próxima devolución prevista: {fecha_es(datos['proximo_vencimiento'])}; depende de que se devuelva a tiempo."
    if not datos.get("proxima_liberacion_reserva") and not datos.get("proximo_vencimiento"):
        mensaje += " No hay una fecha de disponibilidad confirmada."
    if datos.get("reservas_en_espera"):
        mensaje += f" Solicitudes en espera: {datos['reservas_en_espera']}."
    return mensaje + " La disponibilidad en esas fechas no está garantizada."


def consultar_disponibilidad(material_id: int) -> dict[str, Any]:
    """Consulta disponibilidad y fechas estimadas de liberación o devolución."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            _vencer_reservas(cursor)
            datos = _disponibilidad(cursor, material_id)
            if datos is None:
                return _resultado(False, "No encontré ese material en el acervo.", None)
        return _resultado(True, "Consulté la disponibilidad del material.", datos)
    except Exception as error:
        return _resultado(False, str(error), None)


def identificar_usuario(codigo: str) -> dict[str, Any] | None:
    """Devuelve solo los datos básicos de una cuenta activa."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, codigo, nombre
                FROM public.usuarios
                WHERE codigo = %s AND activo = true
                """,
                (codigo,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            return {"id": fila[0], "codigo": fila[1], "nombre": fila[2]}
    except Exception:
        raise


def prestamos_activos_usuario(usuario_id: int) -> dict[str, Any]:
    """Lista préstamos activos del usuario sin consultar cuentas ajenas."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id AS prestamo_id, p.fecha_vencimiento, p.renovaciones,
                       m.id AS material_id, m.titulo
                FROM public.prestamos AS p
                JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
                JOIN public.material AS m ON m.id = e.material_id
                WHERE p.usuario_id = %s AND p.estado IN ('activo', 'vencido')
                ORDER BY p.fecha_vencimiento, p.id
                """,
                (usuario_id,),
            )
            filas = _serializar(_filas(cursor))
        return _resultado(True, "Préstamos del usuario.", filas)
    except Exception as error:
        return _resultado(False, str(error), [])


def _asignar_espera(cursor: Any, material_id: int) -> None:
    """Con el material bloqueado, aparta copias libres por orden de solicitud."""
    cursor.execute("SELECT id FROM reservas WHERE material_id=%s AND estado='activa' AND ejemplar_id IS NULL AND expira_en>=now() ORDER BY fecha_reserva,id FOR UPDATE", (material_id,))
    pendientes = [r[0] for r in cursor.fetchall()]
    for reserva_id in pendientes:
        cursor.execute("SELECT id FROM ejemplares WHERE material_id=%s AND estado='disponible' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED", (material_id,))
        ejemplar = cursor.fetchone()
        if not ejemplar:
            break
        cursor.execute("UPDATE ejemplares SET estado='reservado' WHERE id=%s", (ejemplar[0],))
        cursor.execute("UPDATE reservas SET ejemplar_id=%s, expira_en=now()+(%s * interval '1 hour') WHERE id=%s", (ejemplar[0], HORAS_RESERVA, reserva_id))


def sincronizar_espera() -> None:
    """Actualiza solicitudes al consultar la aplicación; no necesita un servicio externo."""
    with conexion() as conn, conn.cursor() as cursor:
        _vencer_reservas(cursor)
        cursor.execute("SELECT m.id FROM material m WHERE EXISTS (SELECT 1 FROM reservas r WHERE r.material_id=m.id AND r.estado='activa' AND r.ejemplar_id IS NULL AND r.expira_en>=now()) ORDER BY m.id FOR UPDATE OF m")
        for (material_id,) in cursor.fetchall():
            _asignar_espera(cursor, material_id)


def avisos_disponibilidad(usuario_id: int) -> dict[str, Any]:
    """Devuelve únicamente los apartados propios que ya se pueden recoger."""
    reservas = historial_reservas(usuario_id)["activas"]
    listas = [r for r in reservas if r["ejemplar_id"] is not None]
    return {"listas_recoger": listas}


def consultar_recogida(usuario_id: int, pregunta: str = "") -> dict[str, Any]:
    """Resuelve una pregunta de recogida usando las reservas propias, nunca el catálogo."""
    reservas = historial_reservas(usuario_id)["activas"]
    comillas = re.search(r'[«“"]([^»”"]+)[»”"]', pregunta)
    titulo = comillas.group(1) if comillas else re.sub(r"^.*?(?:recoger|retirar)\s*", "", _sin_tildes(pregunta))
    titulo = re.sub(r"^(?:(?:mi|la|el|una)\s+)?(?:reserva|libro|ejemplar)\s*(?:de\s+)?", "", titulo).strip(' ¿?¡!.,')
    if titulo and _sin_tildes(titulo) not in ("mis reservas", "reservas"):
        reservas = [r for r in reservas if _sin_tildes(titulo) in _sin_tildes(r["titulo"])]
    if not reservas:
        return _resultado(True, "No encontré una reserva activa a su nombre para esa consulta. Puede revisar Mis reservas.", [])
    frases = []
    for reserva in reservas:
        if reserva["ejemplar_id"] is not None:
            frases.append(f"Puede recoger «{reserva['titulo']}» en el mostrador de la biblioteca durante su horario de atención, con su carné. Su ejemplar está apartado hasta el {fecha_es(reserva['expira_en'])}.")
        else:
            datos = consultar_disponibilidad(reserva["material_id"])
            detalle = mensaje_disponibilidad(datos["datos"]) if datos["ok"] else "No hay una fecha confirmada."
            frases.append(f"Su reserva de «{reserva['titulo']}» sigue en espera; todavía no puede recogerla. {detalle} Verá un aviso en la aplicación cuando tenga un ejemplar apartado.")
    return _resultado(True, "\n\n".join(frases), reservas)


def reservas_activas_usuario(usuario_id: int) -> list[dict[str, Any]]:
    """Lista las reservas vigentes de una cuenta sin consultar a otros usuarios."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.id AS reserva_id, r.material_id, m.titulo, r.expira_en
            FROM public.reservas AS r
            JOIN public.material AS m ON m.id = r.material_id
            WHERE r.usuario_id = %s AND r.estado = 'activa' AND r.expira_en >= now()
            ORDER BY r.expira_en, r.id
            """,
            (usuario_id,),
        )
        return _serializar(_filas(cursor))


def historial_reservas(usuario_id: int) -> dict[str, list[dict[str, Any]]]:
    """Consulta reservas activas e historial después de vencer las expiradas."""
    sincronizar_espera()
    with conexion() as conn, conn.cursor() as cursor:
        _vencer_reservas(cursor)
        cursor.execute(
            """
            SELECT r.id AS reserva_id, r.material_id, m.titulo, m.autor, m.tipo,
                   r.estado, r.fecha_reserva, r.expira_en, r.ejemplar_id, e.estante,
                   d.disponibles, d.total
            FROM public.reservas AS r
            JOIN public.material AS m ON m.id = r.material_id
            LEFT JOIN public.ejemplares AS e ON e.id = r.ejemplar_id
            JOIN public.v_disponibilidad AS d ON d.material_id = r.material_id
            WHERE r.usuario_id = %s
            ORDER BY
                CASE WHEN r.estado = 'activa' THEN 0 ELSE 1 END,
                CASE WHEN r.estado = 'activa' THEN r.expira_en END ASC NULLS LAST,
                r.fecha_reserva DESC, r.id DESC
            """,
            (usuario_id,),
        )
        reservas = _serializar(_filas(cursor))

    activas = [reserva for reserva in reservas if reserva["estado"] == "activa"]
    historial = [reserva for reserva in reservas if reserva["estado"] != "activa"][:30]
    return {"activas": activas, "historial": historial}


def cancelar_reserva(usuario_id: int, reserva_id: int) -> dict[str, Any]:
    """Cancela una reserva propia y libera su ejemplar reservado, si lo tiene."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.usuario_id, r.estado, r.ejemplar_id, m.titulo
                FROM public.reservas AS r
                JOIN public.material AS m ON m.id = r.material_id
                WHERE r.id = %s
                FOR UPDATE OF r
                """,
                (reserva_id,),
            )
            reserva = cursor.fetchone()
            if reserva is None or int(reserva[0]) != usuario_id:
                return _resultado(False, "No encontré esa reserva a su nombre.", None)
            _, estado, ejemplar_id, titulo = reserva
            if estado != "activa":
                return _resultado(False, "Esa reserva ya no está activa.", None)
            cursor.execute(
                "UPDATE public.reservas SET estado = 'cancelada' WHERE id = %s",
                (reserva_id,),
            )
            if ejemplar_id is not None:
                cursor.execute(
                    """
                    SELECT estado FROM public.ejemplares
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (ejemplar_id,),
                )
                ejemplar = cursor.fetchone()
                if ejemplar and ejemplar[0] == "reservado":
                    cursor.execute(
                        "UPDATE public.ejemplares SET estado = 'disponible' WHERE id = %s",
                        (ejemplar_id,),
                    )
        datos = {"reserva_id": reserva_id, "titulo": titulo}
        return _resultado(True, f"Cancelé su reserva de «{titulo}».", datos)
    except Exception as error:
        return _resultado(False, str(error), None)


def avisos_cuenta(usuario_id: int) -> dict[str, Any]:
    """Resume vencimientos, multas pendientes y reservas próximas a expirar."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT m.titulo, p.fecha_vencimiento,
                   p.fecha_vencimiento - current_date AS dias_restantes
            FROM public.prestamos AS p
            JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
            JOIN public.material AS m ON m.id = e.material_id
            WHERE p.usuario_id = %s AND p.estado = 'activo'
              AND p.fecha_vencimiento BETWEEN current_date AND current_date + 2
            ORDER BY p.fecha_vencimiento, p.id
            """,
            (usuario_id,),
        )
        por_vencer = _serializar(_filas(cursor))
        cursor.execute(
            """
            SELECT m.titulo, current_date - p.fecha_vencimiento AS dias_retraso
            FROM public.prestamos AS p
            JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
            JOIN public.material AS m ON m.id = e.material_id
            WHERE p.usuario_id = %s AND p.estado IN ('activo', 'vencido')
              AND p.fecha_vencimiento < current_date
            ORDER BY p.fecha_vencimiento, p.id
            """,
            (usuario_id,),
        )
        vencidos = _serializar(_filas(cursor))
        cursor.execute(
            """
            SELECT COALESCE(sum(valor), 0) AS total, count(*) AS cantidad
            FROM public.multas
            WHERE usuario_id = %s AND estado = 'pendiente'
            """,
            (usuario_id,),
        )
        multa = _filas(cursor)[0]
        cursor.execute(
            """
            SELECT m.titulo, r.expira_en
            FROM public.reservas AS r
            JOIN public.material AS m ON m.id = r.material_id
            WHERE r.usuario_id = %s AND r.estado = 'activa'
              AND r.expira_en >= now() AND r.expira_en < now() + interval '24 hours'
            ORDER BY r.expira_en, r.id
            """,
            (usuario_id,),
        )
        reservas_por_expirar = _serializar(_filas(cursor))
    return {
        "por_vencer": por_vencer,
        "vencidos": vencidos,
        "multas": {
            "total": float(multa["total"] or 0),
            "cantidad": int(multa["cantidad"] or 0),
        },
        "reservas_por_expirar": reservas_por_expirar,
    }


def resolver_material(texto: str, sala_slug: str | None = None) -> dict[str, Any]:
    """Intenta título/autor exacto y luego usa el candidato semántico más cercano."""
    patron = re.match(r"^(?P<titulo>.+?)\s+(?:de|del)\s+(?P<autor>[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'-]+)\s*$", texto.strip())
    if patron:
        por_titulo = buscar_exacto(patron.group("titulo"), sala_slug=sala_slug)
        apellido = _sin_tildes(patron.group("autor"))
        con_autor = [
            m for m in (por_titulo.get("datos") or [])
            if apellido in _sin_tildes(str(m.get("autor") or ""))
        ]
        if con_autor:
            exacto = [m for m in con_autor if _sin_tildes(str(m.get("titulo"))) == _sin_tildes(patron.group("titulo"))]
            return _resultado(True, "Material identificado por título y autor.", exacto or con_autor)

    exactos = buscar_exacto(texto, sala_slug=sala_slug)
    if exactos["ok"] and exactos["datos"]:
        return _resultado(True, exactos["mensaje"], exactos["datos"])
    if exactos.get("sugerencia_sala"):
        return exactos
    if str(exactos["mensaje"]).lower().startswith("no fue posible"):
        return exactos
    semanticos = buscar_semantico(texto, k=1, sala_slug=sala_slug)
    candidatos = semanticos["datos"]
    if candidatos and float(candidatos[0].get("similitud", 0)) >= 0.40:
        return _resultado(True, semanticos["mensaje"], candidatos, tiempos=semanticos.get("tiempos", {}))
    if semanticos.get("sugerencia_sala"):
        return semanticos
    if not semanticos["ok"] and str(semanticos["mensaje"]).lower().startswith(
        ("no fue posible", "no está disponible", "no esta disponible")
    ):
        return semanticos
    return _resultado(False, "No pude identificar con seguridad el material.", [])


def _vencer_reservas(cursor: Any) -> None:
    """Expira reservas vencidas y libera únicamente ejemplares aún reservados."""
    cursor.execute(
        """
        SELECT id, ejemplar_id
        FROM public.reservas
        WHERE estado = 'activa' AND expira_en < now()
        FOR UPDATE
        """
    )
    vencidas = cursor.fetchall()
    for reserva_id, ejemplar_id in vencidas:
        cursor.execute(
            "UPDATE public.reservas SET estado = 'vencida' WHERE id = %s",
            (reserva_id,),
        )
        if ejemplar_id is not None:
            cursor.execute(
                """
                UPDATE public.ejemplares
                SET estado = 'disponible'
                WHERE id = %s AND estado = 'reservado'
                """,
                (ejemplar_id,),
            )


def _usuario_activo(cursor: Any, usuario_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM public.usuarios WHERE id = %s AND activo = true FOR UPDATE",
        (usuario_id,),
    )
    return cursor.fetchone() is not None


def reservar(usuario_id: int, material_id: int) -> dict[str, Any]:
    """Crea una reserva transaccional, bloqueando un ejemplar disponible si existe."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            _vencer_reservas(cursor)
            if not _usuario_activo(cursor, usuario_id):
                return _resultado(False, "No se puede reservar: el usuario no está activo.", None)
            cursor.execute(
                "SELECT titulo FROM public.material WHERE id = %s FOR UPDATE",
                (material_id,),
            )
            material = cursor.fetchone()
            if material is None:
                return _resultado(False, "No encontré ese material en el acervo.", None)
            _asignar_espera(cursor, material_id)
            cursor.execute(
                """
                SELECT 1 FROM public.reservas
                WHERE usuario_id = %s AND material_id = %s AND estado = 'activa'
                  AND expira_en >= now()
                """,
                (usuario_id, material_id),
            )
            if cursor.fetchone():
                return _resultado(False, "Ya tiene una reserva activa de ese material.", None)
            cursor.execute(
                """
                SELECT 1
                FROM public.prestamos AS p
                JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
                WHERE p.usuario_id = %s AND e.material_id = %s
                  AND p.estado IN ('activo', 'vencido')
                """,
                (usuario_id, material_id),
            )
            if cursor.fetchone():
                return _resultado(False, "Ya tiene ese material en préstamo.", None)

            cursor.execute(
                """
                SELECT id FROM public.ejemplares
                WHERE material_id = %s AND estado = 'disponible'
                ORDER BY id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """,
                (material_id,),
            )
            ejemplar = cursor.fetchone()
            ejemplar_id = ejemplar[0] if ejemplar else None
            if ejemplar_id is not None:
                cursor.execute(
                    "UPDATE public.ejemplares SET estado = 'reservado' WHERE id = %s",
                    (ejemplar_id,),
                )
            cursor.execute(
                """
                INSERT INTO public.reservas
                    (usuario_id, material_id, ejemplar_id, expira_en, estado)
                VALUES (%s, %s, %s, now() + (%s * interval '1 hour'), 'activa')
                RETURNING id, expira_en
                """,
                (usuario_id, material_id, ejemplar_id, HORAS_RESERVA),
            )
            reserva_id, expira_en = cursor.fetchone()
            datos = {
                "reserva_id": reserva_id,
                "titulo": material[0],
                "ejemplar_asignado": ejemplar_id is not None,
                "expira_en": _serializar(expira_en),
            }
            disponibilidad = _disponibilidad(cursor, material_id)
            datos["disponibilidad"] = disponibilidad
        mensaje = (
            f"Reserva creada para «{datos['titulo']}». Vence el {fecha_es(datos['expira_en'])}."
            if ejemplar_id is not None
            else f"Reserva en cola creada para «{datos['titulo']}». Vence el {fecha_es(datos['expira_en'])}."
        )
        if ejemplar_id is None:
            mensaje += " No se ha apartado un ejemplar para usted; su solicitud queda en espera."
        if disponibilidad:
            mensaje += " " + mensaje_disponibilidad(disponibilidad)
        return _resultado(True, mensaje, datos)
    except Exception as error:
        return _resultado(False, str(error), None)


def validar_renovacion(usuario_id: int, prestamo_id: int) -> dict[str, Any]:
    """Prevalida la renovación para evitar pedir una confirmación que será rechazada."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.estado, p.fecha_vencimiento, p.renovaciones,
                       m.id AS material_id, m.titulo
                FROM public.prestamos AS p
                JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
                JOIN public.material AS m ON m.id = e.material_id
                WHERE p.id = %s AND p.usuario_id = %s
                """,
                (prestamo_id, usuario_id),
            )
            fila = cursor.fetchone()
            if fila is None:
                return _resultado(False, "No encontré ese préstamo a su nombre.", None)
            _, estado, vencimiento, renovaciones, material_id, titulo = fila
            if estado != "activo" or vencimiento < date.today():
                dias = max(0, (date.today() - vencimiento).days)
                return _resultado(
                    False,
                    f"No se puede renovar porque el préstamo está vencido; la multa estimada es de {pesos(dias * MULTA_POR_DIA)}.",
                    {"titulo": titulo, "dias_retraso": dias},
                )
            if renovaciones >= MAX_RENOVACIONES:
                return _resultado(False, f"No se puede renovar: ya alcanzó el máximo de {MAX_RENOVACIONES} renovaciones.", {"titulo": titulo})
            cursor.execute(
                "SELECT 1 FROM public.multas WHERE usuario_id = %s AND estado = 'pendiente' LIMIT 1",
                (usuario_id,),
            )
            if cursor.fetchone():
                return _resultado(False, "No se puede renovar porque tiene multas pendientes.", {"titulo": titulo})
            cursor.execute(
                """
                SELECT 1 FROM public.reservas
                WHERE material_id = %s AND usuario_id <> %s AND estado = 'activa'
                  AND expira_en >= now()
                LIMIT 1
                """,
                (material_id, usuario_id),
            )
            if cursor.fetchone():
                return _resultado(False, "No se puede renovar porque otra persona tiene una reserva activa de ese material.", {"titulo": titulo})
        return _resultado(True, "La renovación está disponible.", {"titulo": titulo, "prestamo_id": prestamo_id})
    except Exception as error:
        return _resultado(False, str(error), None)


def renovar_prestamo(usuario_id: int, prestamo_id: int) -> dict[str, Any]:
    """Renueva el préstamo con bloqueo de fila y validación transaccional completa."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.estado, p.fecha_vencimiento, p.renovaciones,
                       m.id AS material_id, m.titulo
                FROM public.prestamos AS p
                JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
                JOIN public.material AS m ON m.id = e.material_id
                WHERE p.id = %s AND p.usuario_id = %s
                FOR UPDATE OF p
                """,
                (prestamo_id, usuario_id),
            )
            fila = cursor.fetchone()
            if fila is None:
                return _resultado(False, "No encontré ese préstamo a su nombre.", None)
            _, estado, vencimiento, renovaciones, material_id, titulo = fila
            if estado != "activo" or vencimiento < date.today():
                dias = max(0, (date.today() - vencimiento).days)
                return _resultado(
                    False,
                    f"No se puede renovar porque el préstamo está vencido; la multa estimada es de {pesos(dias * MULTA_POR_DIA)}.",
                    {"titulo": titulo, "dias_retraso": dias},
                )
            if renovaciones >= MAX_RENOVACIONES:
                return _resultado(False, f"No se puede renovar: ya alcanzó el máximo de {MAX_RENOVACIONES} renovaciones.", {"titulo": titulo})
            cursor.execute(
                "SELECT 1 FROM public.multas WHERE usuario_id = %s AND estado = 'pendiente' LIMIT 1",
                (usuario_id,),
            )
            if cursor.fetchone():
                return _resultado(False, "No se puede renovar porque tiene multas pendientes.", {"titulo": titulo})
            cursor.execute(
                "SELECT id FROM public.material WHERE id = %s FOR UPDATE",
                (material_id,),
            )
            cursor.fetchone()
            cursor.execute(
                """
                SELECT 1 FROM public.reservas
                WHERE material_id = %s AND usuario_id <> %s AND estado = 'activa'
                  AND expira_en >= now()
                LIMIT 1
                """,
                (material_id, usuario_id),
            )
            if cursor.fetchone():
                return _resultado(False, "No se puede renovar porque otra persona tiene una reserva activa de ese material.", {"titulo": titulo})
            cursor.execute(
                """
                UPDATE public.prestamos
                SET fecha_vencimiento =
                        GREATEST(fecha_vencimiento, current_date) + %s,
                    renovaciones = renovaciones + 1
                WHERE id = %s
                RETURNING fecha_vencimiento, renovaciones
                """,
                (DIAS_PRESTAMO, prestamo_id),
            )
            nueva_fecha, nuevas_renovaciones = cursor.fetchone()
        restantes = MAX_RENOVACIONES - nuevas_renovaciones
        datos = {
            "titulo": titulo,
            "fecha_vencimiento": _serializar(nueva_fecha),
            "renovaciones": nuevas_renovaciones,
            "renovaciones_restantes": restantes,
        }
        return _resultado(
            True,
            f"«{titulo}» quedó renovado hasta {fecha_es(datos['fecha_vencimiento'])}. Le quedan {restantes} renovaciones.",
            datos,
        )
    except Exception as error:
        return _resultado(False, str(error), None)


def consultar_prestamos_y_multas(usuario_id: int) -> dict[str, Any]:
    """Consulta préstamos, multas y reservas exclusivamente de un usuario."""
    try:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id AS prestamo_id, m.titulo, p.fecha_vencimiento,
                       p.renovaciones,
                       GREATEST(current_date - p.fecha_vencimiento, 0) AS dias_retraso
                FROM public.prestamos AS p
                JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
                JOIN public.material AS m ON m.id = e.material_id
                WHERE p.usuario_id = %s AND p.estado IN ('activo', 'vencido')
                ORDER BY p.fecha_vencimiento
                """,
                (usuario_id,),
            )
            prestamos = _serializar(_filas(cursor))
            cursor.execute(
                """
                SELECT valor, dias
                FROM public.multas
                WHERE usuario_id = %s AND estado = 'pendiente'
                ORDER BY fecha, id
                """,
                (usuario_id,),
            )
            multas = _serializar(_filas(cursor))
            total_multas = sum(float(multa["valor"] or 0) for multa in multas)
            cursor.execute(
                """
                SELECT r.id AS reserva_id, m.titulo, r.expira_en
                FROM public.reservas AS r
                JOIN public.material AS m ON m.id = r.material_id
                WHERE r.usuario_id = %s AND r.estado = 'activa' AND r.expira_en >= now()
                ORDER BY r.expira_en
                """,
                (usuario_id,),
            )
            reservas = _serializar(_filas(cursor))
        datos = {
            "prestamos": prestamos,
            "multas": multas,
            "total_multas": total_multas,
            "reservas": reservas,
        }
        return _resultado(True, "Consulté su cuenta.", datos)
    except Exception as error:
        return _resultado(False, str(error), None)


def responder_con_documentos(pregunta: str) -> dict[str, Any]:
    """Recupera fragmentos autorizados sobre reglamento, citación y preguntas frecuentes."""
    try:
        pregunta = normalizar_consulta(pregunta)
        normas = [n for n in ("apa", "ieee") if re.search(rf"\b{n}\b", pregunta, re.I)]
        general = bool(normas and re.search(r"\b(normas?|reglas?|gu[ií]as?|diferencias?)\b", pregunta, re.I) and not re.search(r"\b(libro|tesis|revista|cap[ií]tulo|sangr[ií]a|margen|interlineado|autores|cita textual)\b", pregunta, re.I))
        if normas:
            fragmentos, tiempos = [], {"t_embedding_ms": 0, "t_busqueda_ms": 0}
            for norma in normas:
                consulta = f"{norma.upper()} citas en el texto y lista de referencias" if general else re.sub(r"\b(?:APA|IEEE)\b", "", pregunta, flags=re.I) + " " + norma.upper()
                if general:
                    secciones = {"apa": ["Principios de citación en el texto", "Lista de referencias"], "ieee": ["Citas numéricas en el texto", "Abreviaturas y presentación bibliográfica"]}
                    encontrados, mediciones = rag.buscar_fragmentos(consulta, k=12, tipos=[norma], secciones=secciones[norma])
                else:
                    encontrados, mediciones = rag.buscar_fragmentos(consulta, k=TOP_K, tipos=[norma])
                for f in encontrados:
                    f["resumen_norma"] = general
                fragmentos.extend(encontrados)
                for clave in tiempos:
                    tiempos[clave] += mediciones.get(clave, 0)
        else:
            fragmentos, tiempos = rag.buscar_fragmentos(pregunta, k=TOP_K, tipos=["reglamento", "faq", "apa", "ieee", "guia_bd"])
        fragmentos = [
            _serializar(fragmento)
            for fragmento in fragmentos
            if float(fragmento["similitud"]) >= 0.35
        ]
        return _resultado(
            bool(fragmentos),
            "Encontré información en los documentos." if fragmentos else "No tengo esa información en los documentos de la biblioteca.",
            fragmentos,
            tiempos=tiempos,
        )
    except Exception as error:
        return _resultado(False, str(error), [], tiempos={})
