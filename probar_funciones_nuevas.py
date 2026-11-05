"""
probar_funciones_nuevas.py — Ejecuta los casos BIB-* y MAPA-* de evaluacion/casos_prueba.json.

Uso:  python probar_funciones_nuevas.py
Comprueba la bibliografía APA/IEEE (incluido que cada dato salga de la tabla material)
y el mapa del conocimiento (puntos, proyección de consultas y que no recalcule sin cambios).
"""
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from app.agente import procesar_mensaje  # noqa: E402
from app import auth  # noqa: E402
from app.db import conexion  # noqa: E402
from app import mapa  # noqa: E402

CASOS = json.loads((RAIZ / "evaluacion" / "casos_prueba.json").read_text(encoding="utf-8"))["casos"]
resultados: list[tuple[str, bool, str]] = []


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar y ordenar."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def registrar(caso_id: str, ok: bool, detalle: str) -> None:
    resultados.append((caso_id, ok, detalle))
    print(f"[{'PASA' if ok else 'FALLA'}] {caso_id}: {detalle}")


def filas_material(ids: list[int]) -> dict[int, dict]:
    with conexion() as c, c.cursor() as cur:
        cur.execute("SELECT id, titulo, autor, anio, editorial, tipo FROM material WHERE id = ANY(%s)", (ids,))
        return {r[0]: dict(zip(("id", "titulo", "autor", "anio", "editorial", "tipo"), r)) for r in cur.fetchall()}


def verificar_datos(ref: dict, fila: dict) -> str | None:
    """Devuelve un motivo si la referencia contiene datos que no vienen de la tabla material."""
    texto = ref.get("texto", "")
    if fila["titulo"] and normalizar(fila["titulo"].rstrip(".?!")) not in normalizar(texto):
        return "el título no coincide con la tabla"
    anios = re.findall(r"\b(1[89]\d\d|20\d\d)\b", texto)
    for a in anios:
        if fila["anio"] is None or int(a) != int(fila["anio"]):
            return f"año {a} no está en la tabla"
    if re.search(r"doi|https?://|pp\.|vol\.", texto, re.I):
        return "contiene DOI/URL/páginas/volumen inventados"
    # El primer apellido citado debe estar en el campo autor
    primer = re.split(r"[,\[]", texto.split("] ", 1)[-1])[0].strip()
    primer_apellido = primer.split()[-1] if primer else ""
    if primer_apellido and normalizar(primer_apellido.strip(".")) not in normalizar(fila["autor"] or ""):
        return f"autor «{primer}» no aparece en la tabla"
    return None


def clave_orden(ref: dict) -> str:
    texto = re.sub(r"^\[\d+\]\s*", "", ref.get("texto", ""))
    if re.match(r"^[A-ZÁÉÍÓÚÑ]\. ", texto):
        # IEEE: "N. F. Coral Burbano, ..." → se saltan las iniciales y se ordena por los apellidos
        primero = texto.split(",")[0]
        return normalizar(re.sub(r"^(?:[A-ZÁÉÍÓÚÑ]\.(?:-[A-ZÁÉÍÓÚÑ]\.)?\s+)+", "", primero))
    return normalizar(texto)


def caso_bibliografia(caso: dict) -> None:
    cid = None
    r = None
    codigo_sesion = caso.get("sesion")
    usuario_sesion = auth.usuario_por_codigo(str(codigo_sesion)) if codigo_sesion else None
    if codigo_sesion and usuario_sesion is None:
        raise RuntimeError(f"No existe la cuenta de prueba {codigo_sesion}.")
    for turno in caso["conversacion"]:
        r = procesar_mensaje(
            turno,
            cid,
            modo_voz=bool(caso.get("modo_voz")),
            usuario_sesion=usuario_sesion,
        )
        cid = r["conversacion_id"]
    esp = caso["esperado"]
    herr_ok = r["herramienta"] == caso["herramienta_esperada"]
    registrar(caso["id"], herr_ok, f"herramienta={r['herramienta']} (esperada {caso['herramienta_esperada']})")
    if caso["herramienta_esperada"] != "generar_bibliografia":
        for frag in esp.get("contiene", []):
            registrar(caso["id"], frag in r["respuesta"], f"respuesta contiene «{frag}»")
        return
    bib = r.get("bibliografia") or {"referencias": [], "norma": None}
    refs = bib.get("referencias") or []
    n = len(refs)
    if "norma" in esp:
        registrar(caso["id"], (bib.get("norma") or "").upper() == esp["norma"], f"norma={bib.get('norma')}")
    if "min_referencias" in esp:
        registrar(caso["id"], n >= esp["min_referencias"], f"{n} referencias (mínimo {esp['min_referencias']})")
    if "num_referencias" in esp:
        registrar(caso["id"], n == esp["num_referencias"], f"{n} referencias (esperadas {esp['num_referencias']})")
    if "max_referencias" in esp:
        registrar(caso["id"], n <= esp["max_referencias"], f"{n} referencias (máximo {esp['max_referencias']}) · «{r['respuesta'][:80]}»")
    if esp.get("numeradas"):
        registrar(caso["id"], all(re.match(rf"^\[{i + 1}\]", x["texto"]) for i, x in enumerate(refs)), "numeración [1], [2]…")
    if esp.get("orden_alfabetico") and n > 1:
        claves = [clave_orden(x) for x in refs]
        registrar(caso["id"], claves == sorted(claves), "orden alfabético")
    if esp.get("datos_solo_de_tabla_material") and refs:
        filas = filas_material([x["material_id"] for x in refs])
        problemas = [f"{x['material_id']}: {m}" for x in refs if (m := verificar_datos(x, filas[x["material_id"]]))]
        registrar(caso["id"], not problemas, "datos solo de la tabla material" + (f" → {problemas}" if problemas else ""))
    for frag in esp.get("contiene_alguno", []) and [esp["contiene_alguno"]]:
        registrar(caso["id"], any(f in r["respuesta"] for f in frag), f"contiene alguno de {frag}")
    for frag in esp.get("voz_contiene", []):
        registrar(caso["id"], frag in r["respuesta_voz"], f"voz contiene «{frag}»")
    if esp.get("voz_no_contiene"):
        malos = [s for s in esp["voz_no_contiene"] if s in r["respuesta_voz"]]
        registrar(caso["id"], not malos, f"voz sin símbolos ni años · «{r['respuesta_voz'][:120]}»")
    for x in refs[:3]:
        print("     ", x["texto"])


def caso_mapa(caso: dict) -> None:
    esp = caso["esperado"]
    ep = caso["endpoint"]
    if ep == "GET /api/mapa":
        datos = mapa.obtener_puntos()
        puntos = datos["puntos"] if isinstance(datos, dict) else datos
        registrar(caso["id"], len(puntos) == esp["num_puntos"], f"{len(puntos)} puntos")
        finitos = all(math.isfinite(p["x"]) and math.isfinite(p["y"]) for p in puntos)
        registrar(caso["id"], finitos, "coordenadas finitas")
        faltan = [c for c in esp["campos"] if puntos and c not in puntos[0]]
        registrar(caso["id"], not faltan, f"campos completos {faltan or ''}")
    elif ep.startswith("GET /api/mapa/proyectar"):
        q = re.search(r"q=([^&]+)", ep).group(1)
        res = mapa.proyectar_consulta(q, k=5)
        registrar(caso["id"], all(math.isfinite(res[c]) for c in ("x", "y")), f"consulta proyectada en ({res['x']:.3f}, {res['y']:.3f})")
        titulos = [c["titulo"] for c in res["cercanos"]]
        if "min_cercanos_relevantes" in esp:
            n = sum(t in caso["relevantes_top3"] for t in titulos)
            registrar(caso["id"], n >= esp["min_cercanos_relevantes"], f"{n} relevantes entre {titulos}")
        if "min_cercanos_programa" in esp:
            ids = [c["material_id"] for c in res["cercanos"]]
            with conexion() as c, c.cursor() as cur:
                cur.execute("SELECT programa FROM material WHERE id = ANY(%s)", (ids,))
                progs = [p[0] or "" for p in cur.fetchall()]
            regla = esp["min_cercanos_programa"]
            n = sum(regla["programa_contiene"] in p for p in progs)
            registrar(caso["id"], n >= regla["minimo"], f"{n} de programa {regla['programa_contiene']} · {titulos}")
    elif "calcular_mapa" in ep:
        mapa.calcular_mapa()
        segunda = mapa.calcular_mapa()
        registrar(caso["id"], segunda.get("recalculado") is False, f"segunda ejecución: {segunda}")


for caso in CASOS:
    print(f"\n=== {caso['id']} ({caso['categoria']}) ===")
    try:
        if caso["categoria"] == "mapa":
            caso_mapa(caso)
        elif caso["id"].startswith("BIB"):
            caso_bibliografia(caso)
    except Exception as error:  # una falla no detiene el resto
        registrar(caso["id"], False, f"excepción: {error!r}")

ok = sum(1 for _, b, _ in resultados if b)
print(f"\n{ok}/{len(resultados)} comprobaciones PASA")
sys.exit(0 if ok == len(resultados) else 1)
