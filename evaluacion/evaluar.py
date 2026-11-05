"""Ejecuta los casos declarativos y genera resultados y reporte en español."""

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from app import auth, mapa, rag
from app.agente import procesar_mensaje
from app.config import EMBED_MODEL, LLM_MODEL, LLM_MODEL_RESPALDO
from app.db import conectar, conexion

CARPETA_EVALUACION = RAIZ / "evaluacion"
RUTA_CASOS = CARPETA_EVALUACION / "casos_prueba.json"
RUTA_REPORTE = CARPETA_EVALUACION / "reporte.md"
RUTA_RESULTADOS = CARPETA_EVALUACION / "resultados.json"
TABLAS = ("prestamos", "reservas", "ejemplares", "multas", "devoluciones")
CAMPOS_RESTAURACION = {
    "prestamos": ("fecha_vencimiento", "renovaciones", "estado"),
    "reservas": ("estado", "expira_en", "ejemplar_id"),
    "ejemplares": ("estado",),
}


def normalizar(texto: Any) -> str:
    """Compara texto ignorando mayúsculas y tildes."""
    descompuesto = unicodedata.normalize("NFD", str(texto or "").casefold())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def quitar_sufijo_intencion(intencion: Any) -> str | None:
    """Quita los calificadores que añade el agente a la intención."""
    if intencion is None:
        return None
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(intencion)).strip()


def comprobar(registro: dict[str, Any], nombre: str, ok: bool, detalle: str) -> None:
    registro["comprobaciones"].append(
        {"nombre": nombre, "pasa": bool(ok), "detalle": str(detalle)}
    )


def filas_material(ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, titulo, autor, anio, editorial, tipo "
            "FROM public.material WHERE id = ANY(%s)",
            (ids,),
        )
        return {
            fila[0]: dict(
                zip(("id", "titulo", "autor", "anio", "editorial", "tipo"), fila)
            )
            for fila in cursor.fetchall()
        }


def verificar_datos_referencia(
    referencia: dict[str, Any], fila: dict[str, Any]
) -> str | None:
    """Comprueba que los datos bibliográficos correspondan al catálogo."""
    texto = referencia.get("texto", "")
    titulo = fila.get("titulo")
    if titulo and normalizar(str(titulo).rstrip(".?!")) not in normalizar(texto):
        return "el título no coincide con la tabla material"
    anios = re.findall(r"\b(1[89]\d\d|20\d\d)\b", texto)
    for anio in anios:
        if fila.get("anio") is None or int(anio) != int(fila["anio"]):
            return f"el año {anio} no está en la tabla material"
    if re.search(r"doi|https?://|pp\.|vol\.", texto, re.I):
        return "incluye DOI, URL, páginas o volumen no registrados"
    primer_autor = re.split(r"[,\[]", texto.split("] ", 1)[-1])[0].strip()
    apellido = primer_autor.split()[-1].strip(".") if primer_autor else ""
    if apellido and normalizar(apellido) not in normalizar(fila.get("autor")):
        return f"el autor «{primer_autor}» no aparece en la tabla"
    return None


def clave_orden_referencia(referencia: dict[str, Any]) -> str:
    texto = re.sub(r"^\[\d+\]\s*", "", referencia.get("texto", ""))
    if re.match(r"^[A-ZÁÉÍÓÚÑ]\. ", texto):
        primer_autor = texto.split(",")[0]
        texto = re.sub(
            r"^(?:[A-ZÁÉÍÓÚÑ]\.(?:-[A-ZÁÉÍÓÚÑ]\.)?\s+)+",
            "",
            primer_autor,
        )
    return normalizar(texto)


def evaluar_comprobaciones_declarativas(
    caso: dict[str, Any], registro: dict[str, Any]
) -> None:
    esperado = caso.get("esperado") or {}
    respuesta = str(registro.get("respuesta") or "")
    avisos = registro.get("avisos")
    if avisos:
        respuesta += " " + json.dumps(avisos, ensure_ascii=False, default=str)
    respuesta_norm = normalizar(respuesta)

    for fragmento in esperado.get("contiene", []):
        comprobar(
            registro,
            f"contiene: {fragmento}",
            normalizar(fragmento) in respuesta_norm,
            f"se esperaba «{fragmento}» en la respuesta",
        )
    for fragmento in esperado.get("no_contiene", []):
        comprobar(
            registro,
            f"no_contiene: {fragmento}",
            normalizar(fragmento) not in respuesta_norm,
            f"no debía aparecer «{fragmento}» en la respuesta",
        )
    alternativas = esperado.get("contiene_alguno", [])
    if alternativas:
        encontrado = next(
            (fragmento for fragmento in alternativas if normalizar(fragmento) in respuesta_norm),
            None,
        )
        comprobar(
            registro,
            "contiene_alguno",
            encontrado is not None,
            f"se esperaba alguna de {alternativas}; coincidencia: {encontrado!r}",
        )
    if "accion_pendiente_tipo" in esperado:
        pendiente = registro.get("accion_pendiente")
        tipo_obtenido = pendiente.get("tipo") if isinstance(pendiente, dict) else None
        tipo_esperado = esperado.get("accion_pendiente_tipo")
        comprobar(
            registro,
            "accion_pendiente_tipo",
            tipo_obtenido == tipo_esperado,
            f"esperado {tipo_esperado!r}, obtenido {tipo_obtenido!r}",
        )
    if "requiere_login" in esperado:
        obtenido = registro.get("requiere_login")
        comprobar(
            registro,
            "requiere_login",
            obtenido is esperado["requiere_login"],
            f"esperado {esperado['requiere_login']!r}, obtenido {obtenido!r}",
        )
    for campo in ("esperando", "sesion_iniciada", "entrada_oculta"):
        if campo in esperado:
            obtenido = registro.get(campo)
            comprobar(
                registro,
                campo,
                obtenido == esperado[campo],
                f"esperado {esperado[campo]!r}, obtenido {obtenido!r}",
            )
    if "avisos_contienen" in esperado:
        from app.agente import _resumir_avisos
        avisos_texto = normalizar(_resumir_avisos(registro.get("avisos") or {}))
        faltantes = [
            fragmento
            for fragmento in esperado["avisos_contienen"]
            if normalizar(fragmento) not in avisos_texto
        ]
        comprobar(
            registro,
            "avisos_contienen",
            not faltantes,
            f"faltan {faltantes}; avisos: {registro.get('avisos')!r}",
        )
    if "transcripcion_ultima" in esperado:
        obtenida = registro.get("transcripcion_ultima", registro.get("transcripcion"))
        comprobar(
            registro,
            "transcripcion_ultima",
            obtenida == esperado["transcripcion_ultima"],
            f"esperada {esperado['transcripcion_ultima']!r}, obtenida {obtenida!r}",
        )
    for indice, expectativas_turno in enumerate(esperado.get("turnos", [])):
        turnos = registro.get("resultados_turno", [])
        obtenido = turnos[indice] if indice < len(turnos) else {}
        for campo, valor in expectativas_turno.items():
            comprobar(
                registro,
                f"turno_{indice + 1}_{campo}",
                obtenido.get(campo) == valor,
                f"esperado {valor!r}, obtenido {obtenido.get(campo)!r}",
            )
    palabras_transcripcion = esperado.get("transcripcion_contiene", [])
    if palabras_transcripcion:
        transcripcion = normalizar(registro.get("transcripcion", ""))
        encontrado = next(
            (p for p in palabras_transcripcion if normalizar(p) in transcripcion),
            None,
        )
        comprobar(
            registro,
            "transcripcion_contiene",
            encontrado is not None,
            f"se esperaba alguna de {palabras_transcripcion}; transcripción: "
            f"«{registro.get('transcripcion', '')}»",
        )


def registrar_intencion_y_herramienta(
    caso: dict[str, Any], registro: dict[str, Any]
) -> None:
    esperada = caso.get("intencion_esperada")
    aceptadas = caso.get("intenciones_aceptadas", [])
    if esperada is not None or aceptadas:
        opciones = set(aceptadas)
        if esperada is not None:
            opciones.add(esperada)
        obtenida = quitar_sufijo_intencion(registro.get("intencion"))
        comprobar(
            registro,
            "intención",
            obtenida in opciones,
            f"esperada {sorted(opciones)!r}, obtenida {obtenida!r}",
        )
    herramienta_esperada = caso.get("herramienta_esperada")
    herramientas_aceptadas = caso.get("herramientas_aceptadas", [])
    if "herramienta_esperada" in caso or herramientas_aceptadas:
        opciones_herramienta = set(herramientas_aceptadas)
        if "herramienta_esperada" in caso:
            opciones_herramienta.add(herramienta_esperada)
        obtenida = registro.get("herramienta")
        comprobar(
            registro,
            "herramienta",
            obtenida in opciones_herramienta,
            f"esperada {sorted(map(str, opciones_herramienta))!r}, "
            f"obtenida {obtenida!r}",
        )


def ejecutar_conversacion(caso: dict[str, Any]) -> dict[str, Any]:
    conversacion_id = None
    resultado: dict[str, Any] = {}
    codigo_sesion = caso.get("sesion")
    usuario_sesion = auth.usuario_por_codigo(str(codigo_sesion)) if codigo_sesion else None
    if codigo_sesion and usuario_sesion is None:
        raise RuntimeError(f"No existe una cuenta activa para la sesión de prueba {codigo_sesion}.")
    for turno in caso.get("conversacion", []):
        resultado = procesar_mensaje(
            turno,
            conversacion_id,
            modo_voz=bool(caso.get("modo_voz")),
            usuario_sesion=usuario_sesion,
        )
        conversacion_id = resultado.get("conversacion_id")
    return resultado


def evaluar_bibliografia(caso: dict[str, Any], registro: dict[str, Any]) -> None:
    esperado = caso.get("esperado") or {}
    datos_bib = registro.get("bibliografia") or {"referencias": [], "norma": None}
    referencias = datos_bib.get("referencias") or []
    cantidad = len(referencias)
    if "norma" in esperado:
        comprobar(
            registro,
            "norma",
            (datos_bib.get("norma") or "").upper() == esperado["norma"],
            f"norma obtenida: {datos_bib.get('norma')!r}",
        )
    if "min_referencias" in esperado:
        comprobar(
            registro,
            "min_referencias",
            cantidad >= esperado["min_referencias"],
            f"{cantidad} referencias; mínimo {esperado['min_referencias']}",
        )
    if "num_referencias" in esperado:
        comprobar(
            registro,
            "num_referencias",
            cantidad == esperado["num_referencias"],
            f"{cantidad} referencias; esperadas {esperado['num_referencias']}",
        )
    if "max_referencias" in esperado:
        comprobar(
            registro,
            "max_referencias",
            cantidad <= esperado["max_referencias"],
            f"{cantidad} referencias; máximo {esperado['max_referencias']}",
        )
    if esperado.get("numeradas"):
        numeradas = all(
            re.match(rf"^\[{indice}\]", referencia.get("texto", ""))
            for indice, referencia in enumerate(referencias, start=1)
        )
        comprobar(registro, "numeradas", numeradas, "numeración IEEE consecutiva")
    if esperado.get("orden_alfabetico") and cantidad > 1:
        claves = [clave_orden_referencia(referencia) for referencia in referencias]
        comprobar(
            registro,
            "orden_alfabetico",
            claves == sorted(claves),
            "orden alfabético de las referencias",
        )
    if esperado.get("datos_solo_de_tabla_material") and referencias:
        ids = [int(ref["material_id"]) for ref in referencias]
        filas = filas_material(ids)
        problemas = []
        for referencia in referencias:
            material_id = int(referencia["material_id"])
            fila = filas.get(material_id)
            problema = (
                verificar_datos_referencia(referencia, fila)
                if fila is not None
                else "material inexistente en el catálogo"
            )
            if problema:
                problemas.append(f"{material_id}: {problema}")
        comprobar(
            registro,
            "datos_solo_de_tabla_material",
            not problemas,
            "datos cotejados con el catálogo"
            + (f"; problemas: {problemas}" if problemas else ""),
        )
    fragmentos = esperado.get("contiene_alguno", [])
    if fragmentos:
        respuesta = normalizar(registro.get("respuesta", ""))
        coincidencia = next((f for f in fragmentos if normalizar(f) in respuesta), None)
        comprobar(
            registro,
            "contiene_alguno",
            coincidencia is not None,
            f"alternativas {fragmentos}; coincidencia {coincidencia!r}",
        )
    respuesta_voz = normalizar(registro.get("respuesta_voz", ""))
    for fragmento in esperado.get("voz_contiene", []):
        comprobar(
            registro,
            f"voz_contiene: {fragmento}",
            normalizar(fragmento) in respuesta_voz,
            f"respuesta de voz: «{registro.get('respuesta_voz', '')[:120]}»",
        )
    prohibidos = esperado.get("voz_no_contiene", [])
    if prohibidos:
        malos = [s for s in prohibidos if s in str(registro.get("respuesta_voz", ""))]
        comprobar(
            registro,
            "voz_no_contiene",
            not malos,
            f"símbolos prohibidos encontrados: {malos}",
        )


def evaluar_mapa(caso: dict[str, Any], registro: dict[str, Any]) -> None:
    esperado = caso.get("esperado") or {}
    endpoint = caso.get("endpoint", "")
    if endpoint == "GET /api/mapa":
        datos = mapa.obtener_puntos()
        puntos = datos["puntos"] if isinstance(datos, dict) else datos
        comprobar(
            registro,
            "num_puntos",
            len(puntos) == esperado["num_puntos"],
            f"{len(puntos)} puntos; esperados {esperado['num_puntos']}",
        )
        finitos = all(
            math.isfinite(float(punto["x"])) and math.isfinite(float(punto["y"]))
            for punto in puntos
        )
        comprobar(registro, "coordenadas_finitas", finitos, "coordenadas x/y finitas")
        faltantes = [
            campo
            for campo in esperado.get("campos", [])
            if puntos and campo not in puntos[0]
        ]
        comprobar(
            registro,
            "campos",
            not faltantes,
            f"campos faltantes: {faltantes}",
        )
        registro["recuperados"] = [punto.get("titulo", "") for punto in puntos[:3]]
        return
    if endpoint.startswith("GET /api/mapa/proyectar"):
        consulta = parse_qs(urlparse(endpoint.replace("GET ", "")).query).get("q", [""])[0]
        resultado = mapa.proyectar_consulta(consulta, k=5)
        comprobar(
            registro,
            "tiene_xy",
            all(math.isfinite(float(resultado[c])) for c in ("x", "y")),
            f"punto proyectado ({resultado['x']:.3f}, {resultado['y']:.3f})",
        )
        cercanos = resultado.get("cercanos", [])
        titulos = [cercano.get("titulo", "") for cercano in cercanos]
        registro["recuperados"] = titulos[:3]
        if "min_cercanos_relevantes" in esperado:
            relevantes = caso.get("relevantes_top3", [])
            cantidad = sum(
                any(normalizar(titulo) == normalizar(relevante) for relevante in relevantes)
                for titulo in titulos
            )
            comprobar(
                registro,
                "min_cercanos_relevantes",
                cantidad >= esperado["min_cercanos_relevantes"],
                f"{cantidad} relevantes entre los cercanos: {titulos}",
            )
        if "min_cercanos_programa" in esperado:
            ids = [cercano["material_id"] for cercano in cercanos]
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    "SELECT programa FROM public.material WHERE id = ANY(%s)",
                    (ids,),
                )
                programas = [fila[0] or "" for fila in cursor.fetchall()]
            regla = esperado["min_cercanos_programa"]
            cantidad = sum(regla["programa_contiene"] in programa for programa in programas)
            comprobar(
                registro,
                "min_cercanos_programa",
                cantidad >= regla["minimo"],
                f"{cantidad} materiales del programa «{regla['programa_contiene']}»",
            )
        return
    if "calcular_mapa" in endpoint:
        mapa.calcular_mapa()
        segunda = mapa.calcular_mapa()
        comprobar(
            registro,
            "recalculado",
            segunda.get("recalculado") is esperado.get("recalculado"),
            f"segunda ejecución: {segunda}",
        )


def preparar_caso(caso: dict[str, Any]) -> None:
    sentencias = caso.get("preparacion", [])
    if not sentencias:
        return
    with conexion() as conn, conn.cursor() as cursor:
        for sentencia in sentencias:
            cursor.execute(sentencia)


def recuperar_top3(
    caso: dict[str, Any], registro: dict[str, Any]
) -> list[str]:
    if registro.get("recuperados") is not None:
        return list(registro["recuperados"])[:3]
    materiales = registro.get("materiales") or []
    if materiales:
        return [str(item.get("titulo", "")) for item in materiales[:3]]
    bibliografia = registro.get("bibliografia") or {}
    referencias = bibliografia.get("referencias") or []
    if caso.get("categoria") == "bibliografia" and referencias:
        filas = filas_material(
            [int(ref["material_id"]) for ref in referencias if ref.get("material_id") is not None]
        )
        return [
            str(filas[int(ref["material_id"])]["titulo"])
            for ref in referencias[:3]
            if int(ref["material_id"]) in filas
        ]
    fuentes = registro.get("fuentes") or []
    etiquetas = [
        f"{etiqueta_documento(fuente.get('documento', ''), caso.get('categoria'))} "
        f"› {fuente.get('seccion', '')}"
        for fuente in fuentes
    ]
    if len(etiquetas) < 3 and caso.get("relevantes_top3") and caso.get("conversacion"):
        pregunta = str(caso["conversacion"][-1])
        categoria = caso.get("categoria")
        tipos = (
            ["reglamento", "faq"]
            if categoria == "reglamento"
            else ["apa", "ieee"]
        )
        fragmentos, _ = rag.buscar_fragmentos(pregunta, k=3, tipos=tipos)
        etiquetas = [
            f"{etiqueta_documento(fragmento.get('documento', ''), categoria)} "
            f"› {fragmento.get('seccion', '')}"
            for fragmento in fragmentos
        ]
    if etiquetas:
        return etiquetas[:3]
    if referencias:
        filas = filas_material(
            [int(ref["material_id"]) for ref in referencias if ref.get("material_id") is not None]
        )
        return [
            str(filas[int(ref["material_id"])]["titulo"])
            for ref in referencias[:3]
            if int(ref["material_id"]) in filas
        ]
    return []


def etiqueta_documento(documento: Any, categoria: str | None) -> str:
    """Usa nombres breves para los documentos de reglamento en el reporte."""
    titulo = str(documento or "")
    if categoria == "reglamento":
        if "reglamento de la biblioteca" in normalizar(titulo):
            return "Reglamento"
        if "preguntas frecuentes" in normalizar(titulo):
            return "Preguntas frecuentes"
    return titulo


def precision_top3(caso: dict[str, Any], recuperados: list[str]) -> float | None:
    relevantes = caso.get("relevantes_top3") or []
    if not relevantes:
        return None
    primeros = recuperados[:3]
    denominador = min(3, len(primeros))
    if not denominador:
        return 0.0
    aciertos = sum(
        any(normalizar(relevante) in normalizar(resultado) for relevante in relevantes)
        for resultado in primeros
    )
    return aciertos / denominador


def nueva_ficha(caso: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": caso.get("id"),
        "categoria": caso.get("categoria"),
        "tipo": caso.get("tipo"),
        "entrada": (
            caso.get("conversacion")
            or caso.get("audios")
            or [caso.get("audio", caso.get("endpoint", ""))]
        ),
        "esperado": caso.get("esperado", {}),
        "relevantes_top3": caso.get("relevantes_top3", []),
        "intencion_esperada": caso.get("intencion_esperada"),
        "herramienta_esperada": caso.get("herramienta_esperada"),
        "endpoint": caso.get("endpoint"),
        "audio": caso.get("audio"),
        "intenciones_aceptadas": caso.get("intenciones_aceptadas", []),
        "herramientas_aceptadas": caso.get("herramientas_aceptadas", []),
        "intencion_evaluable": (
            caso.get("intencion_esperada") is not None
            or bool(caso.get("intenciones_aceptadas"))
        ),
        "herramienta_evaluable": (
            "herramienta_esperada" in caso or bool(caso.get("herramientas_aceptadas"))
        ),
        "intencion": None,
        "herramienta": None,
        "respuesta": "",
        "respuesta_voz": "",
        "avisos": None,
        "fuentes": [],
        "materiales": [],
        "accion_pendiente": None,
        "tiempos": {},
        "comprobaciones": [],
        "error": None,
        "requiere_login": False,
        "duracion_ms": None,
        "precision_top3": None,
        "recuperados": None,
        "omitido": False,
    }


def evaluar_caso_texto(caso: dict[str, Any], registro: dict[str, Any]) -> None:
    preparar_caso(caso)
    resultado = ejecutar_conversacion(caso)
    for campo in (
        "intencion", "herramienta", "respuesta", "respuesta_voz", "fuentes",
        "materiales", "accion_pendiente", "tiempos", "bibliografia",
        "esperando", "sesion_iniciada", "entrada_oculta", "usuario",
    ):
        registro[campo] = resultado.get(campo)
    registro["avisos"] = resultado.get("avisos")
    registro["requiere_login"] = resultado.get("requiere_login", False)
    evaluar_comprobaciones_declarativas(caso, registro)
    registrar_intencion_y_herramienta(caso, registro)
    if caso.get("id", "").startswith("BIB-"):
        evaluar_bibliografia(caso, registro)
    registro["recuperados"] = recuperar_top3(caso, registro)


def evaluar_caso_login(caso: dict[str, Any], registro: dict[str, Any]) -> None:
    preparar_caso(caso)
    if caso.get("login"):
        credenciales = caso["login"]
        resultado = auth.iniciar_sesion(
            credenciales["codigo"], credenciales["pin"], "evaluacion"
        )
        registro["respuesta"] = (
            resultado.get("mensaje_bienvenida")
            if resultado["ok"]
            else resultado["mensaje"]
        )
        registro["avisos"] = resultado.get("avisos")
        registro["http_status"] = resultado["status"]
        registro["intentos_restantes"] = resultado.get("intentos_restantes")
        registro["usuario"] = resultado.get("usuario")
        registro["avisos"] = resultado.get("avisos")
        if resultado.get("token"):
            auth.cerrar_sesion(resultado["token"])
    else:
        resultado = ejecutar_conversacion(caso)
        registro["respuesta"] = resultado.get("respuesta", "")
        registro["respuesta_voz"] = resultado.get("respuesta_voz", "")
        registro["intencion"] = resultado.get("intencion")
        registro["herramienta"] = resultado.get("herramienta")
        registro["accion_pendiente"] = resultado.get("accion_pendiente")
        registro["requiere_login"] = resultado.get("requiere_login", False)
        registro["esperando"] = resultado.get("esperando")
        registro["sesion_iniciada"] = resultado.get("sesion_iniciada", False)
        registro["entrada_oculta"] = resultado.get("entrada_oculta", False)
        registro["tiempos"] = resultado.get("tiempos") or {}
    esperado = caso.get("esperado") or {}
    evaluar_comprobaciones_declarativas(caso, registro)
    for campo, valor in (
        ("status", registro.get("http_status")),
        ("intentos_restantes", registro.get("intentos_restantes")),
    ):
        if campo in esperado:
            comprobar(
                registro,
                campo,
                valor == esperado[campo],
                f"esperado {esperado[campo]!r}, obtenido {valor!r}",
            )


def evaluar_caso_login_voz(caso: dict[str, Any], registro: dict[str, Any]) -> None:
    conversacion_id = None
    resultados_turno = []
    resultado: dict[str, Any] = {}
    for texto in caso.get("conversacion", []):
        resultado = procesar_mensaje(texto, conversacion_id)
        conversacion_id = resultado.get("conversacion_id")
        resultados_turno.append(
            {
                campo: resultado.get(campo)
                for campo in (
                    "intencion", "herramienta", "respuesta", "respuesta_voz",
                    "avisos", "esperando", "sesion_iniciada", "entrada_oculta",
                    "usuario", "requiere_login", "accion_pendiente", "tiempos",
                )
                if campo in resultado
            }
        )
    for campo in (
        "intencion", "herramienta", "respuesta", "respuesta_voz", "fuentes",
        "materiales", "accion_pendiente", "tiempos", "bibliografia", "avisos",
        "esperando", "sesion_iniciada", "entrada_oculta", "usuario",
        "requiere_login",
    ):
        registro[campo] = resultado.get(campo)
    registro["resultados_turno"] = resultados_turno
    evaluar_comprobaciones_declarativas(caso, registro)
    registrar_intencion_y_herramienta(caso, registro)
    if caso.get("id", "").startswith("BIB-"):
        evaluar_bibliografia(caso, registro)
    registro["recuperados"] = recuperar_top3(caso, registro)


def evaluar_caso_mapa(caso: dict[str, Any], registro: dict[str, Any]) -> None:
    evaluar_mapa(caso, registro)
    registro["herramienta"] = "mapa"
    registro["recuperados"] = recuperar_top3(caso, registro)


def evaluar_caso_audio(
    caso: dict[str, Any], registro: dict[str, Any], cliente: Any
) -> None:
    inicio = perf_counter()
    cliente.post("/api/logout")
    rutas = caso.get("audios") or [caso["audio"]]
    datos: dict[str, Any] = {}
    transcripciones = []
    resultados_turno = []
    conversacion_id = None
    tiempos_turno: list[dict[str, Any]] = []
    for ruta_relativa in rutas:
        ruta = RAIZ / ruta_relativa
        audio = ruta.read_bytes()
        argumentos_peticion: dict[str, Any] = {
            "files": {"audio": (ruta.name, audio, "audio/wav")}
        }
        if conversacion_id:
            argumentos_peticion["data"] = {"conversacion_id": conversacion_id}
        respuesta_http = cliente.post("/api/voz", **argumentos_peticion)
        datos = respuesta_http.json()
        conversacion_id = datos.get("conversacion_id", conversacion_id)
        transcripciones.append(datos.get("transcripcion", ""))
        tiempos_turno.append(datos.get("tiempos") or {})
        resultados_turno.append(
            {
                campo: datos.get(campo)
                for campo in (
                    "intencion", "herramienta", "respuesta", "respuesta_voz",
                    "avisos", "esperando", "sesion_iniciada", "entrada_oculta",
                    "usuario", "requiere_login",
                )
                if campo in datos
            }
        )
        registro["http_status"] = respuesta_http.status_code
        if respuesta_http.status_code != 200:
            comprobar(
                registro,
                "respuesta HTTP",
                False,
                f"HTTP {respuesta_http.status_code}: {datos}",
            )
    registro["duracion_ms"] = round((perf_counter() - inicio) * 1000)
    registro["transcripcion"] = " ".join(transcripciones)
    registro["transcripcion_ultima"] = transcripciones[-1] if transcripciones else ""
    registro["resultados_turno"] = resultados_turno
    registro["intencion"] = datos.get("intencion")
    registro["herramienta"] = datos.get("herramienta")
    registro["respuesta"] = datos.get("respuesta", datos.get("mensaje", ""))
    registro["respuesta_voz"] = datos.get("respuesta_voz", "")
    registro["avisos"] = datos.get("avisos")
    registro["fuentes"] = datos.get("fuentes") or []
    registro["materiales"] = datos.get("materiales") or []
    registro["accion_pendiente"] = datos.get("accion_pendiente")
    registro["tiempos"] = {}
    for etapa in {etapa for tiempos in tiempos_turno for etapa in tiempos}:
        muestras = [
            float(tiempos[etapa])
            for tiempos in tiempos_turno
            if tiempos.get(etapa) is not None
        ]
        registro["tiempos"][etapa] = sum(muestras) if muestras else None
    for campo in ("esperando", "sesion_iniciada", "entrada_oculta", "usuario", "requiere_login"):
        registro[campo] = datos.get(campo)
    evaluar_comprobaciones_declarativas(caso, registro)
    registrar_intencion_y_herramienta(caso, registro)
    registro["recuperados"] = recuperar_top3(caso, registro)


_materiales_creados: set[int] = set()


def evaluar_caso_subir_tesis(
    caso: dict[str, Any], registro: dict[str, Any], cliente: Any
) -> None:
    import probar_repositorio

    login = cliente.post("/api/login", json={"codigo": "101", "pin": "1234"})
    comprobar(
        registro,
        "login_http",
        login.status_code == 200 and login.json().get("ok") is True,
        f"HTTP {login.status_code}: {login.text}",
    )
    if login.status_code != 200:
        return

    tesis = caso["tesis"]
    pdf_vacio = caso["esperado"].get("etapa") == "error"
    contenido = (
        probar_repositorio._pdf_sin_texto()
        if pdf_vacio
        else probar_repositorio._pdf_tesis()
    )
    nombre_archivo = "sin_texto.pdf" if pdf_vacio else "tesis_evaluacion.pdf"
    carga = cliente.post(
        "/api/tesis",
        data={
            "titulo": tesis["titulo"],
            "autor": tesis["autor"],
            "anio": tesis["anio"],
            "programa": tesis["programa"],
        },
        files={"pdf": (nombre_archivo, contenido, "application/pdf")},
    )
    comprobar(
        registro,
        "carga_aceptada",
        carga.status_code == 202,
        f"HTTP {carga.status_code}: {carga.text}",
    )
    if carga.status_code != 202:
        return

    datos_carga = carga.json()
    material_id = int(datos_carga["material_id"])
    _materiales_creados.add(material_id)
    estado = probar_repositorio._esperar_estado(cliente, datos_carga["carga_id"])
    registro["etapa"] = (estado or {}).get("etapa")
    registro["error_procesamiento"] = str((estado or {}).get("error") or "")
    if pdf_vacio:
        texto_error = normalizar(registro["error_procesamiento"])
        esperados = caso["esperado"].get("error_contiene", [])
        cumple_error = bool(registro["etapa"] == "error") and all(
            normalizar(fragmento) in texto_error for fragmento in esperados
        )
        comprobar(
            registro,
            "error_pdf_sin_texto",
            cumple_error,
            f"etapa={registro['etapa']!r}; error={registro['error_procesamiento']!r}",
        )
        registro["respuesta"] = registro["error_procesamiento"]
        return

    comprobar(
        registro,
        "procesamiento_lista",
        registro["etapa"] == caso["esperado"]["etapa"],
        f"etapa obtenida: {registro['etapa']!r}",
    )
    consulta = tesis.get("busqueda", "riego")
    catalogo = cliente.get("/api/catalogo", params={"q": consulta})
    filas = catalogo.json().get("resultados", []) if catalogo.is_success else []
    catalogo_ok = any(fila.get("titulo") == tesis["titulo"] for fila in filas)
    comprobar(
        registro,
        "catalogo_contiene_tesis",
        catalogo_ok,
        f"HTTP {catalogo.status_code}; título encontrado: {catalogo_ok}",
    )
    chat = cliente.post(
        "/api/chat",
        json={"texto": f"Busco tesis sobre {consulta} de cacao"},
    )
    datos_chat = chat.json() if chat.is_success else {}
    materiales = datos_chat.get("materiales", [])
    chat_ok = any(fila.get("titulo") == tesis["titulo"] for fila in materiales)
    comprobar(
        registro,
        "chat_contiene_tesis",
        chat_ok,
        f"HTTP {chat.status_code}; título encontrado: {chat_ok}",
    )
    registro["intencion"] = datos_chat.get("intencion")
    registro["herramienta"] = datos_chat.get("herramienta")
    registro["respuesta"] = datos_chat.get("respuesta", "")
    registro["materiales"] = materiales
    registro["fuentes"] = datos_chat.get("fuentes") or []
    registro["tiempos"] = datos_chat.get("tiempos") or {}
    registro["recuperados"] = [fila.get("titulo", "") for fila in materiales[:3]]


def capturar_base() -> dict[str, dict[str, Any]]:
    """Copia las filas operativas antes de ejecutar cualquier escenario."""
    from psycopg import sql

    guardado: dict[str, dict[str, Any]] = {}
    with conexion() as conn, conn.cursor() as cursor:
        for tabla in TABLAS:
            cursor.execute(
                sql.SQL("SELECT * FROM {}").format(sql.Identifier("public", tabla))
            )
            columnas = [columna.name for columna in cursor.description]
            guardado[tabla] = {
                "columnas": columnas,
                "filas": [
                    dict(zip(columnas, fila, strict=True))
                    for fila in cursor.fetchall()
                ],
            }
    return guardado


def capturar_estado_autenticacion() -> list[tuple[int, int, Any]]:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, intentos_fallidos, bloqueado_hasta
            FROM public.usuarios
            """
        )
        return [(int(fila[0]), int(fila[1]), fila[2]) for fila in cursor.fetchall()]


def capturar_ids_sesiones() -> set[str]:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT token_hash FROM public.sesiones")
        return {fila[0] for fila in cursor.fetchall()}


def cerrar_sesiones_nuevas(ids_iniciales: set[str]) -> int:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.sesiones
            SET cerrada = now()
            WHERE NOT (token_hash = ANY(%s)) AND cerrada IS NULL
            """,
            (list(ids_iniciales),),
        )
        return cursor.rowcount


def limpiar_materiales_tesis() -> list[str]:
    errores = []
    for material_id in sorted(_materiales_creados):
        try:
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM conocimiento.fragmentos AS f
                    USING conocimiento.documentos AS d
                    WHERE f.documento_id = d.id AND d.material_id = %s
                    """,
                    (material_id,),
                )
                cursor.execute(
                    "DELETE FROM conocimiento.documentos WHERE material_id = %s",
                    (material_id,),
                )
                cursor.execute(
                    "DELETE FROM public.cargas_tesis WHERE material_id = %s",
                    (material_id,),
                )
                cursor.execute(
                    "DELETE FROM public.ejemplares WHERE material_id = %s",
                    (material_id,),
                )
                cursor.execute("DELETE FROM public.material WHERE id = %s", (material_id,))
            (RAIZ / "repositorio" / "tesis" / f"{material_id}.pdf").unlink(
                missing_ok=True
            )
        except Exception as error:
            errores.append(f"material {material_id}: {type(error).__name__}: {error}")
    if _materiales_creados:
        try:
            mapa.calcular_mapa()
        except Exception as error:
            errores.append(f"recalcular mapa: {type(error).__name__}: {error}")
    return errores


def restaurar_estado_autenticacion(guardado: list[tuple[int, int, Any]]) -> int:
    cambios = 0
    with conexion() as conn, conn.cursor() as cursor:
        for usuario_id, intentos, bloqueado_hasta in guardado:
            cursor.execute(
                """
                UPDATE public.usuarios
                SET intentos_fallidos = %s, bloqueado_hasta = %s
                WHERE id = %s
                  AND (intentos_fallidos <> %s OR bloqueado_hasta IS DISTINCT FROM %s)
                """,
                (
                    intentos,
                    bloqueado_hasta,
                    usuario_id,
                    intentos,
                    bloqueado_hasta,
                ),
            )
            cambios += cursor.rowcount
    return cambios


def restaurar_base(guardado: dict[str, dict[str, Any]]) -> int:
    """Restaura filas operativas en una sola transacción."""
    from psycopg import sql

    cambios = 0
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            actuales_por_tabla: dict[str, dict[Any, dict[str, Any]]] = {}
            for tabla in TABLAS:
                columnas = guardado[tabla]["columnas"]
                cursor.execute(
                    sql.SQL("SELECT * FROM {}").format(
                        sql.Identifier("public", tabla)
                    )
                )
                actuales_por_tabla[tabla] = {
                    fila[columnas.index("id")]: dict(zip(columnas, fila, strict=True))
                    for fila in cursor.fetchall()
                }

            for tabla in ("devoluciones", "multas", "reservas", "prestamos", "ejemplares"):
                originales = {
                    fila["id"] for fila in guardado[tabla]["filas"]
                }
                nuevos = [
                    identificador
                    for identificador in actuales_por_tabla[tabla]
                    if identificador not in originales
                ]
                if nuevos:
                    cursor.execute(
                        sql.SQL("DELETE FROM {} WHERE id = ANY(%s)").format(
                            sql.Identifier("public", tabla)
                        ),
                        (nuevos,),
                    )
                    cambios += len(nuevos)

            for tabla in ("ejemplares", "prestamos", "reservas", "multas", "devoluciones"):
                columnas = guardado[tabla]["columnas"]
                originales = {
                    fila["id"]: fila for fila in guardado[tabla]["filas"]
                }
                por_id = actuales_por_tabla[tabla]
                columnas_insertar = sql.SQL(", ").join(
                    sql.Identifier(columna) for columna in columnas
                )
                marcadores = sql.SQL(", ").join(sql.Placeholder() for _ in columnas)
                for identificador, original in originales.items():
                    actual = por_id.get(identificador)
                    if actual is None:
                        cursor.execute(
                            sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                                sql.Identifier("public", tabla),
                                columnas_insertar,
                                marcadores,
                            ),
                            tuple(original[columna] for columna in columnas),
                        )
                        cambios += 1
                        continue
                    campos = CAMPOS_RESTAURACION.get(tabla, tuple(
                        columna for columna in columnas if columna != "id"
                    ))
                    modificados = [
                        campo
                        for campo in campos
                        if campo in original and actual.get(campo) != original[campo]
                    ]
                    if modificados:
                        asignaciones = sql.SQL(", ").join(
                            sql.SQL("{} = {}").format(
                                sql.Identifier(campo), sql.Placeholder()
                            )
                            for campo in modificados
                        )
                        cursor.execute(
                            sql.SQL("UPDATE {} SET {} WHERE id = {}").format(
                                sql.Identifier("public", tabla),
                                asignaciones,
                                sql.Placeholder(),
                            ),
                            tuple(original[campo] for campo in modificados)
                            + (identificador,),
                        )
                        cambios += 1
        conn.commit()
        return cambios
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def resumir_metricas(registros: list[dict[str, Any]]) -> dict[str, Any]:
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for registro in registros:
        grupos[registro.get("categoria") or "sin_categoria"].append(registro)
    globales: dict[str, Any] = {}
    por_categoria: dict[str, Any] = {}
    for categoria, elementos in {**grupos, "global": registros}.items():
        evaluables = [r for r in elementos if not r.get("omitido")]
        intenciones = [
            r for r in evaluables if r.get("intencion_evaluable")
        ]
        herramientas = [r for r in evaluables if r.get("herramienta_evaluable")]
        top3 = [r["precision_top3"] for r in evaluables if r.get("precision_top3") is not None]
        comprobaciones = [c for r in evaluables for c in r.get("comprobaciones", [])]
        resumen = {
            "casos": len(elementos),
            "casos_omitidos": sum(r.get("omitido", False) for r in elementos),
            "intenciones": (
                sum(
                    quitar_sufijo_intencion(r.get("intencion"))
                    in (
                        set(r.get("intenciones_aceptadas", []))
                        | (
                            {r["intencion_esperada"]}
                            if r.get("intencion_esperada") is not None
                            else set()
                        )
                    )
                    for r in intenciones
                )
                / len(intenciones)
                if intenciones
                else None
            ),
            "muestras_intencion": len(intenciones),
            "herramientas": (
                sum(
                    r.get("herramienta") in (
                        set(r.get("herramientas_aceptadas", []))
                        | (
                            {r["herramienta_esperada"]}
                            if r.get("herramienta_evaluable")
                            and "herramienta_esperada" in r
                            else set()
                        )
                    )
                    for r in herramientas
                )
                / len(herramientas)
                if herramientas
                else None
            ),
            "muestras_herramienta": len(herramientas),
            "precision_top3": sum(top3) / len(top3) if top3 else None,
            "muestras_top3": len(top3),
            "comprobaciones": sum(c["pasa"] for c in comprobaciones),
            "comprobaciones_total": len(comprobaciones),
            "casos_pasa": sum(r.get("pasa", False) for r in evaluables),
        }
        if categoria == "global":
            globales = resumen
        else:
            por_categoria[categoria] = resumen
    return {"global": globales, "por_categoria": por_categoria}


def resumen_tiempos(registros: list[dict[str, Any]]) -> dict[str, Any]:
    etapas = (
        "t_stt_ms", "t_embedding_ms", "t_busqueda_ms", "t_llm_ms",
        "t_tts_ms", "t_total_ms",
    )
    salida: dict[str, Any] = {}
    agrupaciones = {
        "global": registros,
        "texto": [r for r in registros if r.get("tipo") == "texto"],
        "audio": [r for r in registros if r.get("tipo") == "audio"],
    }
    for grupo, elementos in agrupaciones.items():
        salida[grupo] = {}
        for etapa in etapas:
            muestras = [
                float((r.get("tiempos") or {}).get(etapa))
                for r in elementos
                if (r.get("tiempos") or {}).get(etapa) is not None
            ]
            salida[grupo][etapa] = {
                "promedio_ms": sum(muestras) / len(muestras) if muestras else None,
                "muestras": len(muestras),
            }
    return salida


def porcentaje(valor: float | None) -> str:
    return "N/D" if valor is None else f"{valor * 100:.1f}%"


def generar_reporte(
    registros: list[dict[str, Any]],
    metricas: dict[str, Any],
    tiempos: dict[str, Any],
    interrupcion: bool,
    error_restauracion: str | None,
) -> str:
    ahora = datetime.now().astimezone().isoformat(timespec="seconds")
    resumen = metricas["global"]
    lineas = [
        "# Reporte de evaluación",
        "",
        f"- **Fecha y hora:** {ahora}",
        f"- **Modelo LLM:** {LLM_MODEL} (respaldo: {LLM_MODEL_RESPALDO})",
        f"- **Modelo de embeddings:** {EMBED_MODEL}",
        f"- **Casos ejecutados:** {resumen['casos']}"
        + (" (ejecución interrumpida)" if interrupcion else ""),
        f"- **Casos omitidos por recursos faltantes:** {resumen['casos_omitidos']}",
        "",
        "## Resumen",
        "",
        "| Casos | Acierto de intención | Acierto de herramienta | Precisión top-3 | Comprobaciones |",
        "|---:|---:|---:|---:|---:|",
        f"| {resumen['casos']} | {porcentaje(resumen['intenciones'])} "
        f"({resumen['muestras_intencion']}) | {porcentaje(resumen['herramientas'])} "
        f"({resumen['muestras_herramienta']}) | {porcentaje(resumen['precision_top3'])} "
        f"({resumen['muestras_top3']}) | {resumen['comprobaciones']}/"
        f"{resumen['comprobaciones_total']} |",
        "",
        "## Resultados por categoría",
        "",
        "| Categoría | Pasa/total | Omitidos | Intención | Herramienta | Precisión top-3 | Comprobaciones |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for categoria, datos in sorted(metricas["por_categoria"].items()):
        lineas.append(
            f"| {categoria} | {datos['casos_pasa']}/{datos['casos']} "
            f"| {datos['casos_omitidos']} | {porcentaje(datos['intenciones'])} | {porcentaje(datos['herramientas'])} "
            f"| {porcentaje(datos['precision_top3'])} "
            f"| {datos['comprobaciones']}/{datos['comprobaciones_total']} |"
        )
    lineas.extend(
        [
            "",
            "## Tiempos promedio por etapa",
            "",
            "| Tipo | Etapa | Promedio (ms) | Muestras |",
            "|---|---|---:|---:|",
        ]
    )
    nombres_etapas = {
        "t_stt_ms": "STT",
        "t_embedding_ms": "Embeddings",
        "t_busqueda_ms": "Búsqueda",
        "t_llm_ms": "LLM",
        "t_tts_ms": "TTS",
        "t_total_ms": "Total",
    }
    for grupo in ("global", "texto", "audio"):
        for etapa, datos in tiempos[grupo].items():
            promedio = datos["promedio_ms"]
            valor = "N/D" if promedio is None else f"{promedio:.1f}"
            lineas.append(
                f"| {grupo} | {nombres_etapas[etapa]} | {valor} | {datos['muestras']} |"
            )
    lineas.extend(
        [
            "",
            "## Casos",
            "",
            "| ID | Categoría | Entrada | Intención esperada/obtenida | Herramienta esperada/obtenida | Total (ms) | Resultado |",
            "|---|---|---|---|---|---:|:---:|",
        ]
    )
    for registro in registros:
        entrada = registro.get("entrada", "")
        if isinstance(entrada, list):
            entrada = " → ".join(str(item) for item in entrada)
        entrada = str(entrada).replace("|", "\\|").replace("\n", " ")[:100]
        intenciones = (
            f"{registro.get('intencion_esperada')} / "
            f"{quitar_sufijo_intencion(registro.get('intencion'))}"
        )
        herramientas = (
            f"{registro.get('herramienta_esperada')} / {registro.get('herramienta')}"
        )
        total = (registro.get("tiempos") or {}).get("t_total_ms")
        lineas.append(
            f"| {registro.get('id')} | {registro.get('categoria')} | {entrada} "
            f"| {intenciones} | {herramientas} | {total if total is not None else 'N/D'} "
            f"| {'⏭️' if registro.get('omitido') else '✅' if registro.get('pasa') else '❌'} |"
        )
    lineas.extend(["", "## Fallos", ""])
    fallidos = [r for r in registros if not r.get("pasa") and not r.get("omitido")]
    if not fallidos:
        lineas.append("No se registraron fallos.")
    for registro in fallidos:
        detalle = [
            f"{comprobacion['nombre']}: {comprobacion['detalle']}"
            for comprobacion in registro.get("comprobaciones", [])
            if not comprobacion["pasa"]
        ]
        if registro.get("error"):
            detalle.append(f"Excepción: {registro['error']}")
        lineas.extend(
            [
                f"### {registro.get('id')} — {registro.get('categoria')}",
                "",
                f"- **Esperado:** intención {registro.get('intencion_esperada')!r}, "
                f"herramienta {registro.get('herramienta_esperada')!r}; "
                + ("; ".join(detalle) or "caso no superado"),
                f"- **Obtenido:** intención {registro.get('intencion')!r}, "
                f"herramienta {registro.get('herramienta')!r}.",
                f"- **Respuesta:** {(registro.get('respuesta') or '')[:500]}",
                "",
            ]
        )
    lineas.extend(
        [
            "## Reproducción",
            "",
            "Desde cualquier carpeta, ejecute `python ruta/al/proyecto/evaluacion/evaluar.py`. "
            "Use `--solo TXT`, `--solo AUD`, `--solo BIB` o `--solo MAPA` para limitar "
            "la ejecución; `--sin-audio` omite los casos de audio.",
            "",
        ]
    )
    if error_restauracion:
        lineas.extend(
            ["> **Error al restaurar la base de datos:** " + error_restauracion, ""]
        )
    return "\n".join(lineas)


def cargar_casos() -> list[dict[str, Any]]:
    return json.loads(RUTA_CASOS.read_text(encoding="utf-8"))["casos"]


def seleccionar_casos(casos: list[dict[str, Any]], solo: str | None, sin_audio: bool) -> list[dict[str, Any]]:
    prefijos = {"TXT": "TXT-", "AUD": "AUD-", "BIB": "BIB-", "MAPA": "MAPA-"}
    seleccionados = casos
    if solo:
        prefijo = prefijos[solo]
        seleccionados = [caso for caso in seleccionados if caso["id"].startswith(prefijo)]
    if sin_audio:
        seleccionados = [caso for caso in seleccionados if caso.get("tipo") != "audio"]
    return seleccionados


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa el agente de biblioteca.")
    parser.add_argument("--solo", choices=("TXT", "AUD", "BIB", "MAPA"))
    parser.add_argument("--sin-audio", action="store_true")
    argumentos = parser.parse_args()
    casos = seleccionar_casos(cargar_casos(), argumentos.solo, argumentos.sin_audio)
    registros: list[dict[str, Any]] = []
    guardado = None
    estado_autenticacion = None
    ids_sesiones_iniciales = None
    interrumpido = False
    error_general = None
    error_restauracion = None
    cambios_revertidos = 0
    try:
        guardado = capturar_base()
        estado_autenticacion = capturar_estado_autenticacion()
        ids_sesiones_iniciales = capturar_ids_sesiones()
        casos_audio = [caso for caso in casos if caso.get("tipo") == "audio"]
        casos_api = [caso for caso in casos if caso.get("categoria") == "subir_tesis"]
        if casos_audio or casos_api:
            from fastapi.testclient import TestClient
            from app.main import app

            cliente_contexto = TestClient(app)
        else:
            cliente_contexto = None

        def ejecutar(caso: dict[str, Any], indice: int) -> None:
            registro = nueva_ficha(caso)
            registros.append(registro)
            inicio = perf_counter()
            try:
                recursos = caso.get("audios") or (
                    [caso["audio"]] if caso.get("audio") else []
                )
                faltantes = [
                    ruta for ruta in recursos if not (RAIZ / ruta).is_file()
                ]
                if faltantes:
                    registro["omitido"] = True
                    registro["motivo_omitido"] = f"Faltan recursos: {', '.join(faltantes)}"
                else:
                    if caso.get("tipo") == "audio":
                        evaluar_caso_audio(caso, registro, cliente)
                    elif caso.get("id", "").startswith("MAPA-"):
                        evaluar_caso_mapa(caso, registro)
                    elif caso.get("categoria") == "login":
                        evaluar_caso_login(caso, registro)
                    elif caso.get("categoria") == "login_voz":
                        evaluar_caso_login_voz(caso, registro)
                    elif caso.get("categoria") == "subir_tesis":
                        evaluar_caso_subir_tesis(caso, registro, cliente)
                    else:
                        evaluar_caso_texto(caso, registro)
                    if caso.get("relevantes_top3"):
                        registro["precision_top3"] = precision_top3(
                            caso, registro.get("recuperados") or []
                        )
            except Exception as error:
                registro["error"] = f"{type(error).__name__}: {error}"
                comprobar(
                    registro,
                    "excepción",
                    False,
                    registro["error"],
                )
            finally:
                if registro["duracion_ms"] is None:
                    registro["duracion_ms"] = round((perf_counter() - inicio) * 1000)
                if caso.get("relevantes_top3") and registro["precision_top3"] is None:
                    registro["precision_top3"] = 0.0
                registro["pasa"] = None if registro["omitido"] else (
                    not registro.get("error")
                    and all(c["pasa"] for c in registro["comprobaciones"])
                )
                duracion = registro["duracion_ms"] / 1000
                print(
                    f"[{indice}/{len(casos)}] {caso['id']} "
                    f"{'⏭️ omitido' if registro['omitido'] else '✅' if registro['pasa'] else '❌'} "
                    f"{duracion:.1f} s"
                )

        if cliente_contexto is not None:
            with cliente_contexto as cliente:
                for indice, caso in enumerate(casos, start=1):
                    ejecutar(caso, indice)
        else:
            cliente = None
            for indice, caso in enumerate(casos, start=1):
                ejecutar(caso, indice)
    except KeyboardInterrupt:
        interrumpido = True
        print("\nEvaluación interrumpida; se restaurará la base de datos.")
    except Exception as error:
        error_general = f"{type(error).__name__}: {error}"
        print(f"Error al iniciar la evaluación: {error_general}")
    finally:
        errores_limpieza = limpiar_materiales_tesis()
        if errores_limpieza:
            error_restauracion = "; ".join(errores_limpieza)
        if ids_sesiones_iniciales is not None:
            try:
                sesiones_cerradas = cerrar_sesiones_nuevas(ids_sesiones_iniciales)
                cambios_revertidos += sesiones_cerradas
            except Exception as error:
                detalle = f"{type(error).__name__}: {error}"
                error_restauracion = "; ".join(
                    parte for parte in (error_restauracion, detalle) if parte
                )
        if guardado is not None:
            try:
                cambios_revertidos += restaurar_base(guardado)
            except Exception as error:
                detalle = f"{type(error).__name__}: {error}"
                error_restauracion = "; ".join(
                    parte for parte in (error_restauracion, detalle) if parte
                )
                print(f"No fue posible restaurar la base de datos: {error_restauracion}")
        if estado_autenticacion is not None:
            try:
                cambios_revertidos += restaurar_estado_autenticacion(
                    estado_autenticacion
                )
            except Exception as error:
                detalle = f"{type(error).__name__}: {error}"
                error_restauracion = "; ".join(
                    parte for parte in (error_restauracion, detalle) if parte
                )
                print(f"No fue posible restaurar la autenticación: {error_restauracion}")
        if guardado is not None and not error_restauracion:
            print(
                f"Base de datos restaurada ({cambios_revertidos} cambios revertidos)"
            )
        metricas = resumir_metricas(registros)
        tiempos = resumen_tiempos(registros)
        resultado = {
            "fecha_hora": datetime.now().astimezone().isoformat(),
            "modelos": {
                "llm": LLM_MODEL,
                "llm_respaldo": LLM_MODEL_RESPALDO,
                "embeddings": EMBED_MODEL,
            },
            "interrumpido": interrumpido,
            "error_general": error_general,
            "restauracion": {
                "cambios_revertidos": cambios_revertidos,
                "error": error_restauracion,
            },
            "metricas": metricas,
            "tiempos": tiempos,
            "casos": registros,
        }
        CARPETA_EVALUACION.mkdir(parents=True, exist_ok=True)
        RUTA_RESULTADOS.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        RUTA_REPORTE.write_text(
            generar_reporte(
                registros, metricas, tiempos, interrumpido, error_restauracion
            ),
            encoding="utf-8",
        )
        print(
            "Archivos: evaluacion/casos_prueba.json, evaluacion/evaluar.py, "
            "evaluacion/resultados.json, evaluacion/reporte.md"
        )
    fallos = sum(
        not registro.get("pasa", False) and not registro.get("omitido", False)
        for registro in registros
    )
    if error_general or error_restauracion or interrumpido or fallos:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
