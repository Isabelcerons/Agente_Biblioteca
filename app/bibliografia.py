"""Construye referencias APA e IEEE con los metadatos del catálogo."""

import html
import re
import unicodedata
from time import perf_counter
from typing import Any

from app import rag
from app.db import conexion

_PARTICULAS = {"de", "del", "la", "van", "von"}

# Nombres de pila frecuentes (normalizados, sin tildes). Sirven para decidir, en nombres
# de 3 palabras, si la del medio es un segundo nombre ("Oscar Antonio López" → López, O. A.)
# o un primer apellido ("Roberto Hernández Sampieri" → Hernández Sampieri, R.).
_NOMBRES_DE_PILA = {
    "alberto", "alejandra", "alejandro", "alexander", "alfonso", "ana", "andrea", "andres",
    "angel", "antonio", "camila", "carlos", "carolina", "charles", "cristina", "daniel",
    "david", "diego", "eduardo", "elena", "enrique", "esteban", "felipe", "fernando",
    "francisco", "gabriel", "german", "gloria", "guillermo", "gustavo", "hector", "ignacio",
    "isabel", "jaime", "javier", "jesus", "john", "jorge", "jose", "juan", "julian", "lane", "laura",
    "lucia", "luis", "manuel", "marcela", "maria", "mario", "marta", "mauricio", "miguel",
    "monica", "nicolas", "pablo", "paola", "patricia", "pedro", "rafael", "ramon", "ricardo",
    "roberto", "rosa", "santiago", "sebastian", "sergio", "sofia", "teresa", "thomas", "victor",
    "william", "yolanda",
}


def _normalizar_alfabetico(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(
        caracter
        for caracter in descompuesto
        if unicodedata.category(caracter) != "Mn"
    )


def _nombres_autores(autor: str) -> list[str]:
    return [
        nombre.strip()
        for nombre in re.split(r",\s+|\s+y\s+", autor.strip())
        if nombre.strip()
    ]


def _inicial(token: str) -> str:
    partes = token.split("-")
    iniciales = [
        f"{parte.rstrip('.').strip()[0].upper()}."
        for parte in partes
        if parte.rstrip(".").strip()
    ]
    return "-".join(iniciales)


def _apellidos_e_iniciales(nombre: str) -> tuple[str, str]:
    tokens = nombre.split()
    if not tokens:
        raise ValueError("el autor no tiene un nombre válido")
    if len(tokens) == 1:
        return tokens[0], ""

    if len(tokens) == 2:
        inicio_apellido = len(tokens) - 1
    elif len(tokens) == 3 and (
        re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]\.", tokens[1])
        or _normalizar_alfabetico(tokens[1]) in _NOMBRES_DE_PILA
    ):
        # "Andrew S. Tanenbaum" o "Oscar Antonio López": el apellido es la última palabra
        inicio_apellido = len(tokens) - 1
    else:
        inicio_apellido = max(1, len(tokens) - 2)

    # Una inicial ("K.", "R.") nunca es apellido: "P. K. R. Nair" → Nair, P. K. R.
    ultima_inicial = max(
        (i for i, t in enumerate(tokens[:-1]) if t.endswith(".")), default=-1
    )
    inicio_apellido = max(inicio_apellido, ultima_inicial + 1)

    # "Nora E. Andrade de Guajardo": si el apellido empieza por partícula, incluye la palabra previa
    if tokens[inicio_apellido].casefold() in _PARTICULAS and inicio_apellido > 1:
        inicio_apellido -= 1

    while (
        inicio_apellido > 0
        and tokens[inicio_apellido - 1].casefold() in _PARTICULAS
    ):
        inicio_apellido -= 1

    apellidos = " ".join(tokens[inicio_apellido:])
    # Las partículas de los nombres ("María del Pilar") no generan inicial
    iniciales = " ".join(
        _inicial(token)
        for token in tokens[:inicio_apellido]
        if token.casefold() not in _PARTICULAS
    )
    return apellidos, iniciales


def _autores_apa(autor: str) -> tuple[str, str]:
    nombres = _nombres_autores(autor)
    if not nombres:
        raise ValueError("no hay autores registrados")
    formateados: list[str] = []
    apellidos: list[str] = []
    for nombre in nombres:
        apellido, iniciales = _apellidos_e_iniciales(nombre)
        apellidos.append(apellido)
        formateados.append(f"{apellido}, {iniciales}" if iniciales else apellido)
    if len(formateados) == 1:
        lista = formateados[0]
    elif len(formateados) == 2:
        lista = f"{formateados[0]}, & {formateados[1]}"
    else:
        lista = f"{', '.join(formateados[:-1])}, & {formateados[-1]}"
    return lista, apellidos[0]


def _autores_ieee(autor: str) -> tuple[str, str]:
    nombres = _nombres_autores(autor)
    if not nombres:
        raise ValueError("no hay autores registrados")
    apellidos: list[str] = []
    formateados: list[str] = []
    for nombre in nombres:
        apellido, iniciales = _apellidos_e_iniciales(nombre)
        apellidos.append(apellido)
        formateados.append(f"{iniciales} {apellido}".strip())
    if len(formateados) >= 7:
        lista = f"{', '.join(formateados[:6])}, et al."
    elif len(formateados) == 1:
        lista = formateados[0]
    elif len(formateados) == 2:
        lista = f"{formateados[0]} y {formateados[1]}"
    else:
        lista = f"{', '.join(formateados[:-1])} y {formateados[-1]}"
    return lista, apellidos[0]


def _cerrar(autores: str) -> str:
    """Añade el punto final a la lista de autores sin duplicarlo tras una inicial ("W." → "W.")."""
    return autores if autores.endswith(".") else f"{autores}."


def _texto_titulo(titulo: str) -> tuple[str, bool]:
    termina_especial = titulo.endswith(("?", "!"))
    return ("" if termina_especial else "."), termina_especial


def _escapar(texto: str) -> str:
    return html.escape(texto, quote=True)


def _verificar_referencia(ref: dict[str, Any], fila: dict[str, Any]) -> None:
    """Evita que el formateo introduzca metadatos ajenos a la fila."""
    texto = ref["texto"]
    titulo = str(fila.get("titulo") or "")
    if not titulo or titulo not in texto or ref.get("titulo") != titulo:
        raise ValueError("el título de la referencia no coincide con el catálogo")
    campos_origen = [str(valor) for valor in fila.values() if valor is not None]
    for anio in re.findall(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)", texto):
        if not any(anio in campo for campo in campos_origen):
            raise ValueError("el año de la referencia no proviene del catálogo")
    editorial = str(fila.get("editorial") or "")
    tipo = str(fila.get("tipo") or "").casefold()
    if editorial and tipo != "tesis" and editorial not in texto:
        raise ValueError("la editorial de la referencia no coincide con el catálogo")
    if tipo == "tesis":
        institucion = "Institución Universitaria del Putumayo"
        if institucion in texto and institucion not in editorial:
            raise ValueError("la institución de la tesis no coincide con la editorial")
    if not texto:
        raise ValueError("la referencia quedó vacía")


def _armar_apa(fila: dict[str, Any]) -> tuple[str, str, str]:
    autores, primer_apellido = _autores_apa(str(fila["autor"]))
    titulo = str(fila["titulo"]).strip()
    editorial = str(fila["editorial"]).strip()
    if not titulo or not editorial:
        raise ValueError("faltan el título o la editorial")
    anio = str(fila["anio"]) if fila.get("anio") is not None else "s. f."
    punto_titulo, _ = _texto_titulo(titulo)
    if str(fila.get("tipo") or "").casefold() == "tesis":
        institucion = (
            "Institución Universitaria del Putumayo"
            if "Institución Universitaria del Putumayo" in editorial
            else ""
        )
        etiqueta = (
            f"[Tesis de grado, {institucion}]"
            if institucion
            else "[Tesis de grado]"
        )
        referencia = (
            f"{_cerrar(autores)} ({anio}). {titulo} {etiqueta}. "
            "Repositorio institucional."
        )
        referencia_html = (
            f"{_escapar(_cerrar(autores))} ({_escapar(anio)}). "
            f"<i>{_escapar(titulo)}</i> "
            f"{_escapar(etiqueta)}. Repositorio institucional."
        )
    else:
        referencia = f"{_cerrar(autores)} ({anio}). {titulo}{punto_titulo} {editorial}."
        referencia_html = (
            f"{_escapar(_cerrar(autores))} ({_escapar(anio)}). "
            f"<i>{_escapar(titulo)}</i>{punto_titulo} {_escapar(editorial)}."
        )
    return referencia, referencia_html, primer_apellido


def _armar_ieee(fila: dict[str, Any], numero: int) -> tuple[str, str, str]:
    autores, primer_apellido = _autores_ieee(str(fila["autor"]))
    titulo = str(fila["titulo"]).strip()
    editorial = str(fila["editorial"]).strip()
    if not titulo or not editorial:
        raise ValueError("faltan el título o la editorial")
    anio = str(fila["anio"]) if fila.get("anio") is not None else ""
    prefijo = f"[{numero}] {autores}, "
    if str(fila.get("tipo") or "").casefold() == "tesis":
        institucion = (
            "Institución Universitaria del Putumayo"
            if "Institución Universitaria del Putumayo" in editorial
            else ""
        )
        if not institucion:
            raise ValueError("la editorial no identifica la institución de la tesis")
        referencia = f'{prefijo}"{titulo}," Tesis de grado, {institucion}'
        if anio:
            referencia += f", {anio}"
        referencia += "."
        referencia_html = (
            f'{_escapar(prefijo)}&quot;{_escapar(titulo)},&quot; '
            f"Tesis de grado, {_escapar(institucion)}"
        )
        if anio:
            referencia_html += f", {_escapar(anio)}"
        referencia_html += "."
    else:
        punto_titulo, _ = _texto_titulo(titulo)
        referencia = f"{prefijo}{titulo}{punto_titulo} {editorial}"
        if anio:
            referencia += f", {anio}"
        referencia += "."
        referencia_html = (
            f"{_escapar(prefijo)}<i>{_escapar(titulo)}</i>{punto_titulo} "
            f"{_escapar(editorial)}"
        )
        if anio:
            referencia_html += f", {_escapar(anio)}"
        referencia_html += "."
    return referencia, referencia_html, primer_apellido


def generar_bibliografia(
    tema: str, cantidad: int = 5, norma: str = "APA"
) -> dict[str, Any]:
    """Busca materiales del acervo y construye una lista sin inventar metadatos."""
    inicio = perf_counter()
    tema = tema.strip()
    norma_solicitada = norma
    aviso = ""
    if not isinstance(norma, str) or norma.strip().upper() not in {"APA", "IEEE"}:
        norma = "APA"
        aviso = f"La norma «{norma_solicitada}» no se reconoce; usé APA. "
    else:
        norma = norma.strip().upper()
    if not isinstance(cantidad, int) or isinstance(cantidad, bool) or not 1 <= cantidad <= 15:
        return {
            "ok": False,
            "mensaje": "La cantidad debe ser un entero entre 1 y 15.",
            "datos": {"norma": norma, "tema": tema, "referencias": [], "omitidos": []},
            "tiempos": {"t_total_ms": round((perf_counter() - inicio) * 1000)},
        }
    if not tema:
        return {
            "ok": False,
            "mensaje": "Indique un tema para buscar referencias.",
            "datos": {"norma": norma, "tema": tema, "referencias": [], "omitidos": []},
            "tiempos": {"t_total_ms": round((perf_counter() - inicio) * 1000)},
        }

    try:
        resultados, tiempos_rag = rag.buscar_materiales_semantico(tema, k=cantidad)
        candidatos = [
            material
            for material in resultados
            if float(material.get("similitud") or 0) >= 0.30
            and material.get("material_id") is not None
        ]
        ids = list(dict.fromkeys(int(material["material_id"]) for material in candidatos))
        filas_por_id: dict[int, dict[str, Any]] = {}
        t_consulta_ms = 0.0
        if ids:
            sql = """
                SELECT id AS material_id, autor, anio, titulo, editorial, tipo, programa
                FROM public.material
                WHERE id = ANY(%s)
            """
            inicio_consulta = perf_counter()
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(sql, (ids,))
                columnas = [columna.name for columna in cursor.description]
                filas_por_id = {
                    int(fila[0]): dict(zip(columnas, fila, strict=True))
                    for fila in cursor.fetchall()
                }
            t_consulta_ms = (perf_counter() - inicio_consulta) * 1000

        omitidos: list[dict[str, Any]] = []
        referencias_base: list[tuple[dict[str, Any], str]] = []
        for material in candidatos:
            material_id = int(material["material_id"])
            fila = filas_por_id.get(material_id)
            if fila is None:
                omitidos.append({"material_id": material_id, "motivo": "no existe en public.material"})
                continue
            try:
                for campo in ("autor", "titulo", "editorial"):
                    if not str(fila.get(campo) or "").strip():
                        raise ValueError(f"falta el campo {campo}")
                if norma == "APA":
                    texto, referencia_html, apellido = _armar_apa(fila)
                else:
                    texto, referencia_html, apellido = _armar_ieee(fila, 0)
                ref = {
                    "material_id": material_id,
                    "texto": texto,
                    "html": referencia_html,
                    "titulo": str(fila["titulo"]),
                }
                _verificar_referencia(ref, fila)
                referencias_base.append(
                    (
                        {
                            "material_id": material_id,
                            "similitud": material.get("similitud"),
                            "fila": fila,
                            "ref": ref,
                        },
                        apellido,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                omitidos.append({"material_id": material_id, "motivo": str(error)})

        referencias_base.sort(
            key=lambda elemento: (
                _normalizar_alfabetico(elemento[1]),
                (
                    0,
                    int(elemento[0]["fila"]["anio"]),
                )
                if elemento[0]["fila"].get("anio") is not None
                else (1, 0),
                _normalizar_alfabetico(str(elemento[0]["fila"]["titulo"])),
            )
        )
        referencias: list[dict[str, Any]] = []
        fuentes: list[dict[str, Any]] = []
        for indice, (elemento, _) in enumerate(referencias_base, start=1):
            ref = elemento["ref"]
            if norma == "IEEE":
                texto, referencia_html, _ = _armar_ieee(elemento["fila"], indice)
                ref = {
                    **ref,
                    "texto": texto,
                    "html": referencia_html,
                }
                _verificar_referencia(ref, elemento["fila"])
            referencias.append(ref)
            fuentes.append(
                {
                    "material_id": elemento["material_id"],
                    "titulo": ref["titulo"],
                    "similitud": elemento["similitud"],
                }
            )

        tiempos = {
            **tiempos_rag,
            "t_materiales_ms": t_consulta_ms,
            "t_total_ms": round((perf_counter() - inicio) * 1000),
        }
        datos = {
            "norma": norma,
            "tema": tema,
            "referencias": referencias,
            "omitidos": omitidos,
        }
        mensaje = (
            f"{aviso}Encontré {len(referencias)} referencias en formato {norma}."
            if referencias
            else f"{aviso}No encontré material del acervo sobre ese tema para armar la bibliografía."
        )
        return {
            "ok": bool(referencias),
            "mensaje": mensaje,
            "datos": datos,
            "tiempos": tiempos,
            "fuentes": fuentes,
        }
    except Exception as error:
        return {
            "ok": False,
            "mensaje": str(error),
            "datos": {"norma": norma, "tema": tema, "referencias": [], "omitidos": []},
            "tiempos": {"t_total_ms": round((perf_counter() - inicio) * 1000)},
            "fuentes": [],
        }
