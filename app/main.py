"""API HTTP del agente de biblioteca."""

import base64
import hashlib
import json
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import re
from time import perf_counter
from typing import Any
from uuid import UUID

import ollama
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app import agente, auth, herramientas, mapa, rag, repositorio, stt, tts
from app.config import KEEP_ALIVE, LLM_MODEL, LLM_MODEL_REDACCION, NUM_CTX, OLLAMA_HOST
from app.db import conexion
from app.formatos import fecha_es
from app.numeros import pin_explicito

_RAIZ = Path(__file__).resolve().parent.parent
_STATIC = _RAIZ / "static"
_CLIENTE_OLLAMA = ollama.Client(host=OLLAMA_HOST)
_ERRORES_VOZ: dict[str, str] = {}
_LOGGER = logging.getLogger(__name__)


class SolicitudChat(BaseModel):
    texto: str
    conversacion_id: str | None = None
    con_audio: bool = False


class SolicitudTTS(BaseModel):
    texto: str


class SolicitudCerrarSesion(BaseModel):
    conversacion_id: str


class SolicitudLogin(BaseModel):
    codigo: str
    pin: str


def _serializar(valor: Any) -> Any:
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {llave: _serializar(elemento) for llave, elemento in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_serializar(elemento) for elemento in valor]
    return valor


def _estado_postgres() -> None:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _precalentar_llm() -> None:
    # Misma num_ctx que las consultas reales: si cambia, Ollama recargaría el modelo
    # Modo híbrido: se precalientan el modelo que decide (3b) y el que redacta (1.5b)
    for modelo in dict.fromkeys((LLM_MODEL, LLM_MODEL_REDACCION)):
        _CLIENTE_OLLAMA.chat(
            model=modelo,
            messages=[{"role": "user", "content": "Responde solo: listo"}],
            options={"temperature": 0, "num_ctx": NUM_CTX, "num_predict": 1},
            keep_alive=KEEP_ALIVE,
        )


def _precalentar_embeddings() -> None:
    # Deja embeddinggemma cargado junto al LLM (keep_alive largo)
    rag.embed_consulta("precalentamiento")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Carga y precalienta los modelos UNA vez; el chat de texto funciona aunque falle la voz."""
    for nombre, precalentar in (("llm", _precalentar_llm), ("embeddings", _precalentar_embeddings)):
        try:
            inicio = perf_counter()
            await run_in_threadpool(precalentar)
            print(f"[inicio] {nombre} precalentado en {round((perf_counter() - inicio) * 1000)} ms.")
        except Exception as error:
            print(f"[inicio] No se pudo precalentar {nombre}: {error}")
    for nombre, cargar in (("whisper", stt.cargar_modelo), ("piper", tts.cargar_voz)):
        try:
            await run_in_threadpool(cargar)
            _ERRORES_VOZ.pop(nombre, None)
            print(f"[voz] {nombre} cargado correctamente.")
        except Exception as error:
            _ERRORES_VOZ[nombre] = str(error)
            print(f"[voz] No se pudo cargar {nombre}: {error}")
    # Primera síntesis y transcripción en vacío: la primera consulta real no paga la inicialización
    try:
        inicio = perf_counter()
        audio = await run_in_threadpool(tts.sintetizar, "Hola, buenas tardes.")
        await run_in_threadpool(stt.transcribir, audio["wav_bytes"])
        print(f"[inicio] voz precalentada en {round((perf_counter() - inicio) * 1000)} ms.")
    except Exception as error:
        print(f"[inicio] No se pudo precalentar la voz: {error}")
    yield


app = FastAPI(title="Biblioteca UniPutumayo — Agente", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.middleware("http")
async def revalidar_interfaz(request: Request, call_next):
    respuesta = await call_next(request)
    if request.url.path == "/":
        respuesta.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/static/") and request.url.path.endswith((".js", ".css", ".html")):
        respuesta.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    return respuesta


def _html_interfaz() -> str:
    """Versiona el conjunto de módulos para no mezclar pantallas nuevas con JS antiguo."""
    modulos = sorted((_STATIC / "js").rglob("*.js"))
    estilos = sorted((_STATIC / "css").rglob("*.css"))
    huella = hashlib.sha256()
    for archivo in [*modulos, *estilos, _STATIC / "index.html"]:
        huella.update(archivo.relative_to(_STATIC).as_posix().encode())
        huella.update(archivo.read_bytes())
    version = huella.hexdigest()[:16]
    rutas = ["/static/" + archivo.relative_to(_STATIC).as_posix() for archivo in modulos]
    mapa = json.dumps({"imports": {ruta: f"{ruta}?v={version}" for ruta in rutas}})
    html = (_STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace('<script type="module"', f'<script type="importmap">{mapa}</script>\n  <script type="module"', 1)
    html = html.replace('src="/static/js/app.js"', f'src="/static/js/app.js?v={version}"')
    for archivo in estilos:
        ruta = "/static/" + archivo.relative_to(_STATIC).as_posix()
        html = html.replace(f'href="{ruta}"', f'href="{ruta}?v={version}"')
    return html


@app.exception_handler(HTTPException)
async def manejar_http_error(_: Request, error: HTTPException) -> JSONResponse:
    detalle = error.detail
    return JSONResponse(
        status_code=error.status_code,
        content={"mensaje": detalle if isinstance(detalle, str) else str(detalle)},
    )


@app.exception_handler(RequestValidationError)
async def manejar_validacion(request: Request, error: RequestValidationError) -> JSONResponse:
    if request.url.path == "/api/login":
        return JSONResponse(
            status_code=422,
            content={"ok": False, "mensaje": "La solicitud no tiene el formato esperado."},
        )
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {"mensaje": "La solicitud no tiene el formato esperado.", "detalle": error.errors()}
        ),
    )


@app.exception_handler(Exception)
async def manejar_error(_: Request, error: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"mensaje": f"No fue posible completar la solicitud: {error}"},
    )


@app.get("/", include_in_schema=False)
async def inicio() -> HTMLResponse:
    return HTMLResponse(await run_in_threadpool(_html_interfaz))


@app.post("/api/chat")
async def chat(solicitud: SolicitudChat, request: Request, response: Response) -> dict[str, Any]:
    try:
        usuario_sesion = await run_in_threadpool(
            auth.usuario_de_token, request.cookies.get(auth.COOKIE)
        )
        resultado = await run_in_threadpool(
            agente.procesar_mensaje,
            solicitud.texto,
            solicitud.conversacion_id,
            usuario_sesion=usuario_sesion,
        )
    except Exception as error:
        resultado = {
            "conversacion_id": solicitud.conversacion_id,
            "respuesta": f"No fue posible procesar el mensaje: {error}",
            "respuesta_voz": f"No fue posible procesar el mensaje: {error}",
            "intencion": "error",
            "herramienta": None,
            "fuentes": [],
            "materiales": [],
            "accion_pendiente": None,
            "bibliografia": None,
            "usuario": None,
            "tiempos": {},
            "error": str(error),
            "requiere_login": False,
        }
    if solicitud.con_audio:
        inicio_total = perf_counter()
        try:
            sintetizado = await run_in_threadpool(
                tts.sintetizar,
                resultado.get("respuesta_voz") or "",
            )
            resultado["audio_wav_base64"] = base64.b64encode(
                sintetizado["wav_bytes"]
            ).decode("ascii")
            t_tts_ms: int | None = sintetizado["t_tts_ms"]
            resultado["t_tts_ms"] = t_tts_ms
        except Exception as error:
            _LOGGER.exception("No se pudo sintetizar la respuesta de /api/chat.")
            resultado["audio_wav_base64"] = None
            resultado["aviso"] = "No se pudo generar la voz"
            t_tts_ms = None
        tiempos = resultado.setdefault("tiempos", {})
        tiempos["t_tts_ms"] = t_tts_ms
        tiempos["t_total_ms"] = round(
            (perf_counter() - inicio_total) * 1000
            + (tiempos.get("t_total_ms") or 0)
        )
        await _actualizar_bitacora(
            resultado.get("bitacora_id"),
            tiempos.get("t_stt_ms"),
            t_tts_ms,
            tiempos["t_total_ms"],
            False,
        )
    _sesion_del_chat(resultado, response)
    return resultado


async def _actualizar_bitacora(
    bitacora_id: int | None,
    t_stt_ms: int | None,
    t_tts_ms: int | None,
    t_total_ms: int,
    es_voz: bool,
) -> None:
    """Actualiza los tiempos finales del turno después del procesamiento de voz."""
    if bitacora_id is None:
        return

    def actualizar() -> None:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.bitacora_agente
                SET t_stt_ms = %s, t_tts_ms = %s, t_total_ms = %s, es_voz = %s
                WHERE id = %s
                """,
                (t_stt_ms, t_tts_ms, t_total_ms, es_voz, bitacora_id),
            )

    try:
        await run_in_threadpool(actualizar)
    except Exception:
        _LOGGER.exception("No se pudo actualizar la bitácora del turno %s.", bitacora_id)


@app.get("/api/salud")
async def salud() -> dict[str, Any]:
    estado: dict[str, Any] = {
        "postgresql": False,
        "ollama": False,
        "whisper": stt.esta_listo(),
        "piper": tts.esta_listo(),
    }
    errores: dict[str, str] = {}
    errores.update(_ERRORES_VOZ)
    try:
        await run_in_threadpool(_estado_postgres)
        estado["postgresql"] = True
    except Exception as error:
        errores["postgresql"] = str(error)
    try:
        await run_in_threadpool(_CLIENTE_OLLAMA.list)
        estado["ollama"] = True
    except Exception as error:
        errores["ollama"] = str(error)
    return {"ok": all(estado.values()), "servicios": estado, "errores": errores}


def _formatear_cuenta(resultado: dict[str, Any]) -> dict[str, Any]:
    if not resultado.get("ok"):
        raise HTTPException(
            status_code=503,
            detail=resultado.get("mensaje", "No fue posible consultar la cuenta."),
        )
    datos = resultado["datos"]
    for prestamo in datos.get("prestamos", []):
        prestamo["fecha_vencimiento"] = fecha_es(prestamo["fecha_vencimiento"])
    for reserva in datos.get("reservas", []):
        reserva["expira_en"] = fecha_es(reserva["expira_en"])
    return datos


@app.get("/api/cuenta")
async def cuenta_sesion(request: Request) -> dict[str, Any]:
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    try:
        resultado = await run_in_threadpool(
            herramientas.consultar_prestamos_y_multas, int(usuario["id"])
        )
        return _formatear_cuenta(resultado)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar la cuenta: {error}",
        ) from error


@app.get("/api/mis-reservas", response_model=None)
async def mis_reservas(request: Request) -> dict[str, Any]:
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    try:
        return await run_in_threadpool(
            herramientas.historial_reservas, int(usuario["id"])
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar tus reservas: {error}",
        ) from error


@app.get("/api/avisos")
async def avisos_disponibilidad(request: Request) -> dict[str, Any]:
    usuario = await run_in_threadpool(auth.usuario_de_token, request.cookies.get(auth.COOKIE))
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    return await run_in_threadpool(herramientas.avisos_disponibilidad, int(usuario["id"]))


@app.post("/api/reservas/{reserva_id}/cancelar", response_model=None)
async def cancelar_reserva_interfaz(
    reserva_id: int, request: Request
) -> dict[str, Any]:
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")

    def registrar_interaccion() -> None:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.bitacora_agente
                    (entrada, es_voz, intencion, herramienta)
                VALUES (%s, FALSE, %s, %s)
                """,
                (
                    "[Mis reservas] cancelar",
                    "cancelar_reserva (interfaz)",
                    "cancelar_reserva",
                ),
            )

    try:
        await run_in_threadpool(registrar_interaccion)
        resultado = await run_in_threadpool(
            herramientas.cancelar_reserva, int(usuario["id"]), reserva_id
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible cancelar la reserva: {error}",
        ) from error

    if not resultado.get("ok"):
        mensaje = resultado.get("mensaje", "")
        if mensaje == "No encontré esa reserva a su nombre.":
            raise HTTPException(status_code=404, detail=mensaje)
        if mensaje == "Esa reserva ya no está activa.":
            raise HTTPException(status_code=409, detail=mensaje)
        raise HTTPException(status_code=503, detail="No fue posible cancelar la reserva.")
    return {"ok": True, "mensaje": resultado["mensaje"]}


@app.get("/api/cuenta/{conversacion_id}")
async def cuenta(conversacion_id: str, request: Request) -> dict[str, Any]:
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    try:
        identificador = UUID(conversacion_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="El identificador de conversación no es válido.") from error
    try:
        def consultar() -> tuple[bool, int | None]:
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    "SELECT usuario_id FROM public.conversaciones WHERE id = %s",
                    (identificador,),
                )
                fila = cursor.fetchone()
            return (True, fila[0]) if fila else (False, None)

        existe, usuario_conversacion = await run_in_threadpool(consultar)
        if not existe:
            raise HTTPException(status_code=404, detail="No encontré esa conversación.")
        if usuario_conversacion is None or int(usuario_conversacion) != int(usuario["id"]):
            raise HTTPException(status_code=403, detail="La conversación no pertenece a esta sesión.")
        resultado = await run_in_threadpool(
            herramientas.consultar_prestamos_y_multas, int(usuario["id"])
        )
        return _formatear_cuenta(resultado)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar la cuenta: {error}",
        ) from error


def _poner_cookie(response: Response, token: str) -> None:
    """Comparte la cookie de sesión entre login, chat y voz."""
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="lax",
                        path="/", max_age=auth.DURACION_SESION * 3600, secure=False)


def _sesion_del_chat(resultado: dict[str, Any], response: Response) -> None:
    token = resultado.pop("token_sesion", None)
    if token:
        _poner_cookie(response, token)


@app.post("/api/login")
async def login(solicitud: SolicitudLogin, request: Request, response: Response) -> Any:
    resultado = await run_in_threadpool(
        auth.iniciar_sesion,
        solicitud.codigo,
        solicitud.pin,
        request.headers.get("user-agent"),
    )
    if not resultado["ok"]:
        contenido: dict[str, Any] = {
            "ok": False,
            "mensaje": resultado["mensaje"],
        }
        if "intentos_restantes" in resultado:
            contenido["intentos_restantes"] = resultado["intentos_restantes"]
        if "bloqueado_hasta" in resultado:
            contenido["bloqueado_hasta"] = _serializar(resultado["bloqueado_hasta"])
        return JSONResponse(status_code=resultado["status"], content=contenido)

    usuario = resultado["usuario"]
    _poner_cookie(response, resultado["token"])
    return {
        "ok": True,
        "usuario": usuario,
        "avisos": resultado["avisos"],
        "mensaje_bienvenida": resultado["mensaje_bienvenida"],
    }


@app.post("/api/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    await run_in_threadpool(auth.cerrar_sesion, request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE, path="/", httponly=True, samesite="lax")
    return {"ok": True}


@app.get("/api/sesion")
async def estado_sesion(request: Request) -> dict[str, Any]:
    token = request.cookies.get(auth.COOKIE)
    usuario = await run_in_threadpool(auth.usuario_de_token, token)
    expira = (
        await run_in_threadpool(auth.expira_de_token, token)
        if usuario is not None
        else None
    )
    return {
        "autenticado": usuario is not None,
        "usuario": usuario,
        "expira": _serializar(expira),
    }


@app.get("/api/conversacion/actual")
async def conversacion_actual(request: Request) -> dict[str, Any]:
    """Devuelve el chat más reciente del perfil autenticado, sin estado operativo."""
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")

    def consultar() -> dict[str, Any] | None:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                WITH reciente AS (
                    SELECT c.id
                    FROM public.conversaciones c
                    WHERE c.usuario_id = %s
                      AND EXISTS (
                          SELECT 1 FROM public.mensajes m
                          WHERE m.conversacion_id = c.id
                            AND m.rol IN ('user', 'assistant')
                      )
                    ORDER BY c.actualizada DESC, c.id
                    LIMIT 1
                )
                SELECT reciente.id, m.rol, m.contenido, m.creado
                FROM reciente
                JOIN public.mensajes m ON m.conversacion_id = reciente.id
                WHERE m.rol IN ('user', 'assistant')
                ORDER BY m.creado, m.id
                """,
                (int(usuario["id"]),),
            )
            filas = cursor.fetchall()
        if not filas:
            return None
        mensajes = []
        for _, rol, contenido, creado in filas:
            texto = contenido or ""
            if rol == "user" and ("[PIN oculto]" in texto or pin_explicito(texto)):
                texto = "[Dato de acceso omitido]"
            mensajes.append({"rol": rol, "contenido": texto, "creado": creado.isoformat()})
        return {"conversacion_id": str(filas[0][0]), "mensajes": mensajes}

    try:
        return await run_in_threadpool(consultar) or {"conversacion_id": None, "mensajes": []}
    except Exception as error:
        raise HTTPException(
            status_code=503, detail=f"No fue posible recuperar el chat: {error}"
        ) from error


@app.delete("/api/conversacion/{conversacion_id}")
async def borrar_conversacion(conversacion_id: str, request: Request) -> dict[str, bool]:
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    try:
        identificador = UUID(conversacion_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="El identificador no es válido.") from error

    def eliminar() -> bool:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM public.conversaciones
                WHERE id = %s AND usuario_id = %s
                """,
                (identificador, int(usuario["id"])),
            )
            if cursor.fetchone() is None:
                return False
            cursor.execute(
                """
                DELETE FROM public.bitacora_agente
                WHERE conversacion_id IN (
                    SELECT id FROM public.conversaciones WHERE usuario_id = %s
                )
                """,
                (int(usuario["id"]),),
            )
            cursor.execute(
                "DELETE FROM public.conversaciones WHERE usuario_id = %s",
                (int(usuario["id"]),),
            )
            return cursor.rowcount > 0

    try:
        if not await run_in_threadpool(eliminar):
            raise HTTPException(status_code=404, detail="No encontré ese chat en tu perfil.")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=503, detail=f"No fue posible borrar el chat: {error}"
        ) from error


@app.get("/api/bitacora")
async def bitacora(limite: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    def consultar() -> list[dict[str, Any]]:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, conversacion_id, entrada, es_voz, intencion, herramienta,
                       fragmentos, respuesta, error, t_stt_ms, t_embedding_ms,
                       t_busqueda_ms, t_llm_ms, t_tts_ms, t_total_ms, creado
                FROM public.bitacora_agente
                ORDER BY creado DESC, id DESC
                LIMIT %s
                """,
                (limite,),
            )
            columnas = [columna.name for columna in cursor.description]
            return [
                dict(zip(columnas, fila, strict=True))
                for fila in cursor.fetchall()
            ]

    try:
        filas = await run_in_threadpool(consultar)
        return {"resultados": _serializar(filas)}
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar la bitácora: {error}",
        ) from error


@app.get("/api/demo")
async def demo(q: str = Query(min_length=1, max_length=500)) -> dict[str, Any]:
    try:
        def buscar() -> dict[str, Any]:
            inicio_sql = perf_counter()
            resultados_sql = rag.buscar_exacto_sql(q)
            t_sql = (perf_counter() - inicio_sql) * 1000
            resultados_vector, tiempos_vector = rag.buscar_materiales_semantico(q)
            return {
                "sql": resultados_sql,
                "pgvector": resultados_vector,
                "tiempos": {
                    "t_sql_ms": t_sql,
                    "t_embedding_ms": tiempos_vector.get("t_embedding_ms"),
                    "t_busqueda_ms": tiempos_vector.get("t_busqueda_ms"),
                },
            }

        return _serializar(await run_in_threadpool(buscar))
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible ejecutar la demostración: {error}",
        ) from error


@app.get("/api/mapa", response_model=None)
async def mapa_conocimiento() -> dict[str, Any] | JSONResponse:
    try:
        puntos = await run_in_threadpool(mapa.obtener_puntos)
        resumen = await run_in_threadpool(mapa.obtener_resumen)
        if not puntos or resumen is None:
            await run_in_threadpool(mapa.calcular_mapa)
            puntos = await run_in_threadpool(mapa.obtener_puntos)
            resumen = await run_in_threadpool(mapa.obtener_resumen)
        xs = [float(punto["x"]) for punto in puntos]
        ys = [float(punto["y"]) for punto in puntos]
        limites = (
            {
                "min_x": min(xs),
                "max_x": max(xs),
                "min_y": min(ys),
                "max_y": max(ys),
            }
            if puntos
            else {"min_x": None, "max_x": None, "min_y": None, "max_y": None}
        )
        return _serializar(
            {
                "puntos": puntos,
                "limites": limites,
                "varianza_explicada": (resumen or {}).get(
                    "varianza_explicada", []
                ),
                "calculado": (resumen or {}).get("calculado"),
            }
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar el mapa del conocimiento: {error}",
        ) from error


@app.get("/api/mapa/proyectar", response_model=None)
async def proyectar_mapa(
    q: str = Query(min_length=1, max_length=500),
    k: int = Query(default=5, ge=1, le=50),
) -> dict[str, Any] | JSONResponse:
    try:
        resultado = await run_in_threadpool(mapa.proyectar_consulta, q, k)
        return _serializar(resultado)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible proyectar la consulta: {error}",
        ) from error


@app.get("/api/catalogo")
async def catalogo(
    q: str = Query(default="", max_length=500),
    tipo: str | None = Query(default=None, max_length=30),
    programa: str | None = Query(default=None, max_length=160),
    disponible: bool | None = None,
    limite: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    patron = f"%{q}%"
    filtros = """
        (%s = '' OR m.titulo ILIKE %s OR m.autor ILIKE %s OR m.tema ILIKE %s)
        AND (%s::varchar IS NULL OR m.tipo = %s)
        AND (%s::varchar IS NULL OR m.programa = %s)
        AND (%s::boolean IS NULL OR %s = false OR
             EXISTS (SELECT 1 FROM public.ejemplares ed
                     WHERE ed.material_id = m.id AND ed.estado = 'disponible'))
    """
    parametros_filtro = (
        q, patron, patron, patron,
        tipo, tipo,
        programa, programa,
        disponible, disponible,
    )
    try:
        def consultar() -> dict[str, Any]:
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT count(*) FROM public.material AS m WHERE {filtros}",
                    parametros_filtro,
                )
                total = cursor.fetchone()[0]
                cursor.execute(
                    f"""
                    SELECT m.id AS material_id, m.titulo, m.autor, m.anio, m.tipo,
                           m.programa,
                           COALESCE(array_agg(DISTINCT e.estante ORDER BY e.estante)
                               FILTER (WHERE e.estante IS NOT NULL),
                               ARRAY[]::varchar[]) AS estantes,
                           count(e.id) FILTER (WHERE e.estado = 'disponible') AS disponibles,
                           count(e.id) AS total,
                           count(e.id) FILTER (WHERE e.estado = 'prestado') AS prestados,
                           count(e.id) FILTER (WHERE e.estado = 'reservado') AS reservados
                    FROM public.material AS m
                    LEFT JOIN public.ejemplares AS e ON e.material_id = m.id
                    WHERE {filtros}
                    GROUP BY m.id
                    ORDER BY m.titulo, m.id
                    LIMIT %s OFFSET %s
                    """,
                    (*parametros_filtro, limite, offset),
                )
                resultados = [
                    dict(zip((columna.name for columna in cursor.description), fila, strict=True))
                    for fila in cursor.fetchall()
                ]
                cursor.execute(
                    "SELECT DISTINCT programa FROM public.material "
                    "WHERE programa IS NOT NULL ORDER BY programa"
                )
                programas = [fila[0] for fila in cursor.fetchall()]
                cursor.execute("SELECT DISTINCT tipo FROM public.material ORDER BY tipo")
                tipos = [fila[0] for fila in cursor.fetchall()]
                cursor.execute("""
                    SELECT count(DISTINCT m.id) AS materiales,
                           count(DISTINCT m.id) FILTER (WHERE m.tipo='libro') AS libros,
                           count(DISTINCT m.id) FILTER (WHERE m.tipo='tesis') AS tesis,
                           count(e.id) AS ejemplares,
                           count(e.id) FILTER (WHERE e.estado='disponible') AS disponibles
                    FROM public.material m LEFT JOIN public.ejemplares e ON e.material_id=m.id
                """)
                estadisticas = dict(zip((c.name for c in cursor.description), cursor.fetchone(), strict=True))
            return {
                "total": total,
                "resultados": _serializar(resultados),
                "programas": programas,
                "tipos": tipos,
                "estadisticas": estadisticas,
            }

        return await run_in_threadpool(consultar)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar el catálogo: {error}",
        ) from error


@app.get("/api/programas")
async def programas() -> dict[str, list[str]]:
    try:
        return {"programas": await run_in_threadpool(repositorio.programas)}
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar los programas: {error}",
        ) from error


@app.post("/api/tesis", status_code=202)
async def registrar_tesis(
    request: Request,
    pdf: UploadFile = File(...),
    titulo: str = Form(...),
    autor: str = Form(...),
    anio: str = Form(...),
    programa: str = Form(...),
) -> dict[str, Any]:
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    try:
        anio_numero = int(anio)
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail="El año debe ser un número entre 1990 y el año actual.",
        ) from error
    pdf_bytes = await pdf.read(repositorio.MAX_BYTES + 1)
    try:
        carga_id = await run_in_threadpool(
            repositorio.registrar_tesis,
            int(usuario["id"]),
            titulo,
            autor,
            anio_numero,
            programa,
            pdf_bytes,
        )
    except repositorio.CargaEnCursoError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    estado = await run_in_threadpool(
        repositorio.progreso, carga_id, int(usuario["id"])
    )
    if estado is None:
        raise HTTPException(
            status_code=500,
            detail="La carga se registró, pero no fue posible consultar su estado.",
        )
    return {"carga_id": str(carga_id), "material_id": estado["material_id"]}


@app.get("/api/tesis/progreso/{carga_id}")
async def progreso_tesis(carga_id: UUID, request: Request) -> dict[str, Any]:
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    estado = await run_in_threadpool(
        repositorio.progreso, carga_id, int(usuario["id"])
    )
    if estado is None:
        raise HTTPException(status_code=404, detail="No encontré esa carga de tesis.")
    return estado


@app.get("/api/tesis/{material_id}/pdf")
async def descargar_pdf_tesis(material_id: int, request: Request) -> FileResponse:
    usuario = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")

    def consultar_ruta() -> Path | None:
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT archivo_pdf FROM public.material WHERE id = %s",
                (material_id,),
            )
            fila = cursor.fetchone()
        if fila is None or not fila[0]:
            return None
        ruta = (_RAIZ / fila[0]).resolve()
        if not ruta.is_relative_to(_RAIZ.resolve()):
            return None
        return ruta

    try:
        ruta = await run_in_threadpool(consultar_ruta)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar el PDF: {error}",
        ) from error
    if ruta is None or not ruta.is_file():
        raise HTTPException(status_code=404, detail="No encontré el PDF de esa tesis.")
    return FileResponse(ruta, media_type="application/pdf")


def _unir_fragmentos(fragmentos: list[str]) -> str:
    """Une fragmentos ordenados sin repetir el solapamiento entre ellos."""
    palabras: list[str] = []
    for fragmento in fragmentos:
        siguientes = fragmento.split()
        solapamiento = 0
        limite = min(len(palabras), len(siguientes), 120)
        for cantidad in range(limite, 0, -1):
            if palabras[-cantidad:] == siguientes[:cantidad]:
                solapamiento = cantidad
                break
        palabras.extend(siguientes[solapamiento:])
    texto = " ".join(palabras)
    texto = texto.replace("**", "").replace("Documento de demostración para el taller", "")
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


@app.get("/api/material/{material_id}", response_model=None)
async def detalle_material(material_id: int) -> dict[str, Any] | JSONResponse:
    try:
        def consultar() -> dict[str, Any] | None:
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT m.id AS material_id, m.titulo, m.autor, m.anio, m.tipo,
                           m.programa, m.tema, m.editorial, m.isbn, m.descripcion_corta,
                           COALESCE(array_agg(DISTINCT e.estante ORDER BY e.estante)
                               FILTER (WHERE e.estante IS NOT NULL),
                               ARRAY[]::varchar[]) AS estantes,
                           count(e.id) FILTER (WHERE e.estado = 'disponible') AS disponibles,
                           count(e.id) AS total,
                           count(e.id) FILTER (WHERE e.estado = 'prestado') AS prestados,
                           count(e.id) FILTER (WHERE e.estado = 'reservado') AS reservados
                    FROM public.material AS m
                    LEFT JOIN public.ejemplares AS e ON e.material_id = m.id
                    WHERE m.id = %s
                    GROUP BY m.id
                    """,
                    (material_id,),
                )
                fila = cursor.fetchone()
                if fila is None:
                    return None
                material = dict(zip((columna.name for columna in cursor.description), fila, strict=True))
                cursor.execute(
                    """
                    SELECT codigo_barras, estante, estado
                    FROM public.ejemplares
                    WHERE material_id = %s
                    ORDER BY codigo_barras
                    """,
                    (material_id,),
                )
                ejemplares = [
                    dict(zip((columna.name for columna in cursor.description), ejemplar, strict=True))
                    for ejemplar in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT d.tipo, f.texto
                    FROM conocimiento.documentos AS d
                    LEFT JOIN conocimiento.fragmentos AS f ON f.documento_id = d.id
                    WHERE d.material_id = %s
                    ORDER BY d.fuente, f.orden
                    """,
                    (material_id,),
                )
                documentos = cursor.fetchall()
            tipos_resumen = {documento[0] for documento in documentos}
            tipo_resumen = next(
                (tipo for tipo in ("resena_libro", "resumen_tesis") if tipo in tipos_resumen),
                None,
            )
            textos = [documento[1] for documento in documentos if documento[1] is not None]
            resumen = _unir_fragmentos(textos)
            return {
                **material,
                "ejemplares": ejemplares,
                "resumen": resumen,
                "tipo_resumen": tipo_resumen,
            }

        resultado = await run_in_threadpool(consultar)
        if resultado is None:
            return JSONResponse(status_code=404, content={"mensaje": "No encontré ese material en el acervo."})
        return _serializar(resultado)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar el material: {error}",
        ) from error


@app.post("/api/sesion/cerrar")
async def cerrar_sesion(
    solicitud: SolicitudCerrarSesion, request: Request, response: Response
) -> dict[str, bool]:
    try:
        identificador = UUID(solicitud.conversacion_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="El identificador de conversación no es válido.",
        ) from error
    try:
        token = request.cookies.get(auth.COOKIE)
        usuario = await run_in_threadpool(auth.usuario_de_token, token)

        def cerrar() -> bool:
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public.conversaciones
                    SET usuario_id = NULL,
                        estado = jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    jsonb_set(COALESCE(estado, '{}'::jsonb),
                                              '{usuario_id}', 'null'::jsonb, true),
                                    '{accion_pendiente}', 'null'::jsonb, true),
                                '{accion_tras_codigo}', 'null'::jsonb, true),
                            '{esperando}', 'null'::jsonb, true),
                        actualizada = now()
                    WHERE id = %s AND (usuario_id IS NULL OR usuario_id = %s)
                    RETURNING id
                    """,
                    (identificador, int(usuario["id"]) if usuario else None),
                )
                return cursor.fetchone() is not None

        if not await run_in_threadpool(cerrar):
            raise HTTPException(
                status_code=404,
                detail="No encontré una conversación disponible para esta sesión.",
            )
        await run_in_threadpool(auth.cerrar_sesion, token)
        response.delete_cookie(auth.COOKIE, path="/", httponly=True, samesite="lax")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible cerrar la sesión: {error}",
        ) from error


def _validar_conversacion_transcripcion(
    conversacion_id: str | None, usuario_sesion: dict[str, Any] | None,
) -> bool:
    """Consulta sin crear ni modificar conversaciones; no devuelve datos privados."""
    if not conversacion_id:
        return False
    try:
        identificador = UUID(conversacion_id)
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(400, "El identificador de conversación no es válido.") from error
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT usuario_id, estado FROM public.conversaciones WHERE id = %s",
            (identificador,),
        )
        fila = cursor.fetchone()
    if fila is None:
        raise HTTPException(404, "No encontré esa conversación.")
    esperado = int(usuario_sesion["id"]) if usuario_sesion else None
    estado = fila[1] if isinstance(fila[1], dict) else {}
    if fila[0] != esperado or estado.get("usuario_id") not in (None, esperado):
        raise HTTPException(403, "La conversación no pertenece a esta sesión.")
    return estado.get("esperando") == "pin"


@app.post("/api/transcribir")
async def transcribir_audio(
    request: Request,
    audio: UploadFile = File(...),
    conversacion_id: str | None = Form(default=None),
) -> dict[str, Any]:
    async def validar() -> bool:
        try:
            usuario = await run_in_threadpool(
                auth.usuario_de_token, request.cookies.get(auth.COOKIE)
            )
            return await run_in_threadpool(
                _validar_conversacion_transcripcion, conversacion_id, usuario
            )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "No fue posible validar la sesión de voz.") from None

    pin_antes = await validar()
    audio_bytes = await audio.read(10 * 1024 * 1024 + 1)
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(422, "El audio supera el límite de 10 MB.")
    try:
        resultado = await run_in_threadpool(stt.transcribir, audio_bytes)
    except Exception:
        raise HTTPException(422, "No pude transcribir el audio. Grábelo de nuevo, por favor.") from None
    # Revalidar impide exponer un PIN si el estado o la sesión cambió durante STT.
    pin_despues = await validar()
    from app.numeros import pin_explicito

    seguro = pin_antes or pin_despues or pin_explicito(resultado["texto"])
    return {
        "transcripcion": "[PIN oculto]" if seguro else resultado["texto"],
        "t_stt_ms": resultado["t_stt_ms"],
        "requiere_envio_seguro": seguro,
    }


@app.post("/api/voz", response_model=None)  # devuelve dict o JSONResponse de error
async def voz(
    request: Request,
    response: Response,
    audio: UploadFile = File(...),
    conversacion_id: str | None = Form(default=None),
) -> dict[str, Any] | JSONResponse:
    inicio_total = perf_counter()
    audio_bytes = await audio.read()
    try:
        transcripcion = await run_in_threadpool(stt.transcribir, audio_bytes)
    except Exception as error:
        mensaje = str(error)
        try:
            await run_in_threadpool(_registrar_error_voz, conversacion_id, mensaje)
        except Exception:
            _LOGGER.exception("No se pudo registrar el error de reconocimiento de voz.")
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "etapa": "stt",
                "mensaje": mensaje,
                "bibliografia": None,
            },
        )

    texto = transcripcion["texto"]
    usuario_sesion = await run_in_threadpool(
        auth.usuario_de_token, request.cookies.get(auth.COOKIE)
    )
    resultado = await run_in_threadpool(
        agente.procesar_mensaje,
        texto,
        conversacion_id,
        True,
        transcripcion["t_stt_ms"],
        usuario_sesion=usuario_sesion,
    )
    t_tts_ms: int | None = None
    try:
        sintetizado = await run_in_threadpool(
            tts.sintetizar,
            resultado.get("respuesta_voz") or "",
        )
        audio_base64: str | None = base64.b64encode(
            sintetizado["wav_bytes"]
        ).decode("ascii")
        t_tts_ms = sintetizado["t_tts_ms"]
    except Exception:
        _LOGGER.exception("No se pudo sintetizar la respuesta de /api/voz.")
        audio_base64 = None
        resultado["aviso"] = "No se pudo generar la voz"

    tiempos = resultado.setdefault("tiempos", {})
    tiempos["t_stt_ms"] = transcripcion["t_stt_ms"]
    tiempos["t_tts_ms"] = t_tts_ms
    tiempos["t_total_ms"] = round((perf_counter() - inicio_total) * 1000)
    resultado["transcripcion"] = "[PIN oculto]" if resultado.get("entrada_oculta") else texto
    resultado["audio_wav_base64"] = audio_base64
    resultado["t_tts_ms"] = t_tts_ms
    await _actualizar_bitacora(
        resultado.get("bitacora_id"),
        transcripcion["t_stt_ms"],
        t_tts_ms,
        tiempos["t_total_ms"],
        True,
    )
    _sesion_del_chat(resultado, response)
    return resultado


def _registrar_error_voz(conversacion_id: str | None, mensaje: str) -> None:
    """Registra una entrada de audio que no pudo transcribirse."""
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.bitacora_agente
                (conversacion_id, entrada, es_voz, intencion, error)
            VALUES (%s, '[audio]', TRUE, 'error_stt', %s)
            """,
            (conversacion_id, mensaje),
        )


@app.post("/api/tts")
async def sintetizar_texto(solicitud: SolicitudTTS) -> dict[str, Any]:
    try:
        sintetizado = await run_in_threadpool(tts.sintetizar, solicitud.texto)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible generar la voz: {error}",
        ) from error
    return {
        "audio_wav_base64": base64.b64encode(sintetizado["wav_bytes"]).decode("ascii"),
        "t_tts_ms": sintetizado["t_tts_ms"],
    }
