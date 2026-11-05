"""Autenticación por PIN y administración de sesiones de biblioteca."""

import hashlib
import hmac
import math
import re
import secrets
from datetime import datetime, timedelta
from time import monotonic
from typing import Any

from app.db import conexion

DURACION_SESION = 2
MAX_INTENTOS = 5
BLOQUEO = 5
COOKIE = "sesion_biblioteca"
_ITERACIONES = 200_000
_VENTANA_LIMITADOR = 5 * 60
_MAX_INTENTOS_CODIGO_INEXISTENTE = 5
_intentos_codigos_inexistentes: dict[str, tuple[int, float]] = {}


def hash_pin(pin: str) -> str:
    """Genera un hash PBKDF2 con una sal aleatoria por PIN."""
    sal = secrets.token_bytes(16)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", pin.encode(), sal, _ITERACIONES
    )
    return f"pbkdf2_sha256${_ITERACIONES}${sal.hex()}${derivado.hex()}"


def verificar_pin(pin: str, guardado: str) -> bool:
    """Compara un PIN con su hash almacenado en tiempo constante."""
    try:
        algoritmo, iteraciones_texto, sal_hex, hash_hex = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        iteraciones = int(iteraciones_texto)
        if iteraciones < 1:
            return False
        esperado = bytes.fromhex(hash_hex)
        calculado = hashlib.pbkdf2_hmac(
            "sha256", pin.encode(), bytes.fromhex(sal_hex), iteraciones
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return hmac.compare_digest(calculado, esperado)


def _usuario(fila: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": fila[0],
        "codigo": fila[1],
        "nombre": fila[2],
        "tipo": fila[3],
        "programa": fila[4],
    }


def usuario_por_codigo(codigo: str) -> dict[str, Any] | None:
    """Devuelve los datos de una cuenta activa sin abrir una sesión."""
    if not re.fullmatch(r"[0-9]{3,10}", codigo or ""):
        return None
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, codigo, nombre, tipo, programa
            FROM public.usuarios
            WHERE codigo = %s AND activo = true
            """,
            (codigo,),
        )
        fila = cursor.fetchone()
    return _usuario(fila) if fila else None


def _limitar_codigo_inexistente(codigo: str) -> bool:
    """Limita consultas repetidas para códigos inexistentes sin conservarlos en BD."""
    ahora = monotonic()
    intentos, inicio = _intentos_codigos_inexistentes.get(codigo, (0, ahora))
    if ahora - inicio >= _VENTANA_LIMITADOR:
        intentos, inicio = 0, ahora
    if intentos >= _MAX_INTENTOS_CODIGO_INEXISTENTE:
        return True
    _intentos_codigos_inexistentes[codigo] = (intentos + 1, inicio)
    if len(_intentos_codigos_inexistentes) > 10_000:
        _intentos_codigos_inexistentes.clear()
        _intentos_codigos_inexistentes[codigo] = (1, ahora)
    return False


def _respuesta_codigo_inexistente_limitado(codigo: str) -> dict[str, Any] | None:
    ahora = monotonic()
    intentos, inicio = _intentos_codigos_inexistentes.get(codigo, (0, ahora))
    if ahora - inicio >= _VENTANA_LIMITADOR:
        _intentos_codigos_inexistentes.pop(codigo, None)
        return None
    if intentos < _MAX_INTENTOS_CODIGO_INEXISTENTE:
        return None
    restante = max(0, _VENTANA_LIMITADOR - (ahora - inicio))
    bloqueado_hasta = datetime.now().astimezone() + timedelta(seconds=restante)
    minutos = max(1, math.ceil(restante / 60))
    return {
        "ok": False,
        "status": 429,
        "mensaje": f"Demasiados intentos. Intente de nuevo en {minutos} minutos.",
        "bloqueado_hasta": bloqueado_hasta,
    }


def _fallo_codigo_inexistente(codigo: str) -> dict[str, Any]:
    _limitar_codigo_inexistente(codigo)
    intentos = _intentos_codigos_inexistentes[codigo][0]
    return {
        "ok": False,
        "status": 401,
        "mensaje": f"Código o PIN incorrectos. Te quedan {max(0, MAX_INTENTOS - intentos)} intentos.",
        "intentos_restantes": max(0, MAX_INTENTOS - intentos),
    }


def iniciar_sesion(codigo: str, pin: str, user_agent: str | None) -> dict[str, Any]:
    """Valida PIN, aplica bloqueo temporal y crea una sesión opaca."""
    if not re.fullmatch(r"[0-9]{3,10}", codigo or "") or not re.fullmatch(r"[0-9]{4}", pin or ""):
        return {
            "ok": False,
            "status": 422,
            "mensaje": "Código o PIN incorrectos.",
            "intentos_restantes": None,
        }
    respuesta_limitador = _respuesta_codigo_inexistente_limitado(codigo)
    if respuesta_limitador is not None:
        return respuesta_limitador

    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, codigo, nombre, tipo, programa, activo, pin_hash,
                   intentos_fallidos, bloqueado_hasta
            FROM public.usuarios
            WHERE codigo = %s
            FOR UPDATE
            """,
            (codigo,),
        )
        fila = cursor.fetchone()
        if fila is None or not fila[5]:
            return _fallo_codigo_inexistente(codigo)

        usuario = _usuario(fila)
        bloqueado_hasta = fila[8]
        cursor.execute("SELECT now()")
        ahora = cursor.fetchone()[0]
        if bloqueado_hasta is not None and bloqueado_hasta > ahora:
            minutos = max(1, math.ceil((bloqueado_hasta - ahora).total_seconds() / 60))
            return {
                "ok": False,
                "status": 429,
                "mensaje": f"Demasiados intentos. Intente de nuevo en {minutos} minutos.",
                "bloqueado_hasta": bloqueado_hasta,
            }

        if not fila[6] or not verificar_pin(pin, fila[6]):
            fallidos = int(fila[7]) + 1
            if fallidos >= MAX_INTENTOS:
                cursor.execute(
                    """
                    UPDATE public.usuarios
                    SET intentos_fallidos = 0,
                        bloqueado_hasta = now() + (%s * interval '1 minute')
                    WHERE id = %s
                    RETURNING bloqueado_hasta
                    """,
                    (BLOQUEO, usuario["id"]),
                )
                return {
                    "ok": False,
                    "status": 401,
                    "mensaje": "Código o PIN incorrectos. Te quedan 0 intentos.",
                    "intentos_restantes": 0,
                    "bloqueado_hasta": cursor.fetchone()[0],
                }
            cursor.execute(
                "UPDATE public.usuarios SET intentos_fallidos = %s WHERE id = %s",
                (fallidos, usuario["id"]),
            )
            return {
                "ok": False,
                "status": 401,
                "mensaje": f"Código o PIN incorrectos. Te quedan {MAX_INTENTOS - fallidos} intentos.",
                "intentos_restantes": MAX_INTENTOS - fallidos,
            }

        cursor.execute(
            """
            UPDATE public.usuarios
            SET intentos_fallidos = 0, bloqueado_hasta = NULL
            WHERE id = %s
            """,
            (usuario["id"],),
        )
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        cursor.execute(
            """
            INSERT INTO public.sesiones
                (token_hash, usuario_id, expira, user_agent)
            VALUES (%s, %s, now() + (%s * interval '1 hour'), %s)
            RETURNING expira
            """,
            (token_hash, usuario["id"], DURACION_SESION, user_agent),
        )
        expira = cursor.fetchone()[0]
    avisos = _avisos(usuario["id"])
    return {
        "ok": True,
        "status": 200,
        "token": token,
        "usuario": usuario,
        "avisos": avisos,
        "mensaje_bienvenida": _mensaje_bienvenida(usuario, avisos),
        "expira": expira,
    }


def _avisos(usuario_id: int) -> dict[str, Any]:
    from app import herramientas

    return herramientas.avisos_cuenta(usuario_id)


def _mensaje_bienvenida(usuario: dict[str, Any], avisos: dict[str, Any]) -> str:
    from app.agente import _resumir_avisos

    frase = _resumir_avisos(avisos)
    return " ".join(
        parte for parte in (f"Hola, {usuario['nombre']}.", frase) if parte
    )


def _hash_token(token: str | None) -> str | None:
    return hashlib.sha256(token.encode()).hexdigest() if token else None


def usuario_de_token(token: str | None) -> dict[str, Any] | None:
    """Resuelve un token vigente cuyo hash corresponde a una sesión abierta."""
    token_hash = _hash_token(token)
    if token_hash is None:
        return None
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT u.id, u.codigo, u.nombre, u.tipo, u.programa
            FROM public.sesiones AS s
            JOIN public.usuarios AS u ON u.id = s.usuario_id
            WHERE s.token_hash = %s AND s.cerrada IS NULL
              AND s.expira > now() AND u.activo = true
            """,
            (token_hash,),
        )
        fila = cursor.fetchone()
    return _usuario(fila) if fila else None


def expira_de_token(token: str | None) -> Any:
    """Devuelve la expiración de una sesión vigente, sin exponer su token."""
    token_hash = _hash_token(token)
    if token_hash is None:
        return None
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT expira FROM public.sesiones
            WHERE token_hash = %s AND cerrada IS NULL AND expira > now()
            """,
            (token_hash,),
        )
        fila = cursor.fetchone()
    return fila[0] if fila else None


def cerrar_sesion(token: str | None) -> None:
    """Cierra la sesión asociada al token sin almacenarlo."""
    token_hash = _hash_token(token)
    if token_hash is None:
        return
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE public.sesiones SET cerrada = now()
            WHERE token_hash = %s AND cerrada IS NULL
            """,
            (token_hash,),
        )
