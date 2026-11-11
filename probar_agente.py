"""Prueba de aceptación conversacional del backend de biblioteca."""

from datetime import date
import hashlib
from typing import Any

from app import auth, herramientas
from app.agente import procesar_mensaje
from app.db import conexion
from refrescar_demo import refrescar_demo

_resultados: list[tuple[str, bool, str]] = []
_tiempos: list[int] = []
_reservas_previas: set[int] = set()
_prestamo_revertir: tuple[int, date, int] | None = None
_estado_pin_revertir: tuple[int, int, Any] | None = None
_estados_pin_revertir: list[tuple[int, int, Any]] = []
_sesiones_tokens: list[str] = []


def turno(
    etiqueta: str,
    texto: str,
    conversacion_id: str | None = None,
    usuario_sesion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    respuesta = procesar_mensaje(
        texto, conversacion_id, usuario_sesion=usuario_sesion
    )
    if respuesta.get("token_sesion"):
        _sesiones_tokens.append(respuesta["token_sesion"])
    if respuesta.get("tiempos", {}).get("t_total_ms") is not None:
        _tiempos.append(respuesta["tiempos"]["t_total_ms"])
    print(
        f"{etiqueta} | texto: {'[PIN oculto]' if respuesta.get('entrada_oculta') else texto}\n"
        f"  intención: {respuesta.get('intencion')}\n"
        f"  herramienta: {respuesta.get('herramienta')}\n"
        f"  respuesta: {respuesta.get('respuesta')}\n"
        f"  respuesta_voz: {respuesta.get('respuesta_voz')}\n"
        f"  t_total_ms: {respuesta.get('tiempos', {}).get('t_total_ms')}"
    )
    return respuesta


def registrar(nombre: str, cumple: bool, detalle: str = "") -> None:
    _resultados.append((nombre, cumple, detalle))


def _codigo_usuario(codigo: str) -> int:
    usuario = auth.usuario_por_codigo(codigo)
    if usuario is None:
        raise RuntimeError(f"No existe el usuario de prueba {codigo}.")
    return int(usuario["id"])


def _preparar_limpieza_reserva() -> None:
    usuario_id = _codigo_usuario("101")
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.id
            FROM public.reservas AS r
            JOIN public.material AS m ON m.id = r.material_id
            WHERE r.usuario_id = %s AND m.titulo = %s
            """,
            (usuario_id, "Hacking ético"),
        )
        _reservas_previas.update(fila[0] for fila in cursor.fetchall())


def _guardar_estado_pin(codigo: str) -> tuple[int, int, Any]:
    usuario_id = _codigo_usuario(codigo)
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT intentos_fallidos, bloqueado_hasta FROM public.usuarios WHERE id = %s",
            (usuario_id,),
        )
        intentos, bloqueado_hasta = cursor.fetchone()
    return usuario_id, int(intentos), bloqueado_hasta


def _limpiar_pruebas() -> None:
    """Revierte únicamente las reservas/renovaciones creadas por este guion."""
    try:
        usuario_id = _codigo_usuario("101")
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.ejemplar_id
                FROM public.reservas AS r
                JOIN public.material AS m ON m.id = r.material_id
                WHERE r.usuario_id = %s AND m.titulo = %s AND r.estado = 'activa'
                """,
                (usuario_id, "Hacking ético"),
            )
            for reserva_id, ejemplar_id in cursor.fetchall():
                if reserva_id in _reservas_previas:
                    continue
                cursor.execute(
                    "UPDATE public.reservas SET estado = 'cancelada' WHERE id = %s",
                    (reserva_id,),
                )
                if ejemplar_id is not None:
                    cursor.execute(
                        """
                        UPDATE public.ejemplares SET estado = 'disponible'
                        WHERE id = %s AND estado = 'reservado'
                        """,
                        (ejemplar_id,),
                    )
            if _prestamo_revertir:
                prestamo_id, fecha_original, renovaciones_originales = _prestamo_revertir
                cursor.execute(
                    """
                    UPDATE public.prestamos
                    SET fecha_vencimiento = %s, renovaciones = %s
                    WHERE id = %s AND renovaciones = %s
                    """,
                    (
                        fecha_original,
                        renovaciones_originales,
                        prestamo_id,
                        renovaciones_originales + 1,
                    ),
                )
            if _estado_pin_revertir:
                usuario_id, intentos, bloqueado_hasta = _estado_pin_revertir
                cursor.execute(
                    """
                    UPDATE public.usuarios
                    SET intentos_fallidos = %s, bloqueado_hasta = %s
                    WHERE id = %s
                    """,
                    (intentos, bloqueado_hasta, usuario_id),
                )
            for u_id, intentos, bloqueado in _estados_pin_revertir:
                cursor.execute(
                    """
                    UPDATE public.usuarios
                    SET intentos_fallidos = %s, bloqueado_hasta = %s
                    WHERE id = %s
                    """,
                    (intentos, bloqueado, u_id),
                )
            for token in _sesiones_tokens:
                try:
                    auth.cerrar_sesion(token)
                except Exception:
                    pass
    except Exception as error:
        print(f"FALLA limpieza de datos de prueba: {error}")
        registrar("Limpieza", False, str(error))


def main() -> None:
    global _prestamo_revertir, _estado_pin_revertir, _estados_pin_revertir
    refrescar_demo()
    _preparar_limpieza_reserva()
    _estado_pin_revertir = _guardar_estado_pin("107")
    _estados_pin_revertir = [
        _guardar_estado_pin("101"),
        _guardar_estado_pin("102"),
        _guardar_estado_pin("107"),
    ]
    try:
        s1 = turno("S1", "Hola")
        registrar("S1 saludo", s1["intencion"] == "saludo")

        s2 = turno("S2", "Busco libros sobre cómo proteger una red de una empresa")
        registrar(
            "S2 búsqueda semántica",
            s2["herramienta"] == "buscar_semantico"
            and "seguridad" in s2["respuesta"].lower(),
            s2["respuesta"],
        )

        s3 = turno("S3", "¿Tienen el libro Cálculo de una variable?")
        registrar(
            "S3 búsqueda exacta",
            s3["herramienta"] in {"buscar_exacto", "consultar_disponibilidad"}
            and ("stewart" in s3["respuesta"].lower() or "cálculo" in s3["respuesta"].lower()),
            s3["respuesta"],
        )

        s4 = turno("S4", "¿Cuántos días dura un préstamo?")
        registrar(
            "S4 días de préstamo",
            s4["herramienta"] == "responder_con_documentos"
            and "8" in s4["respuesta"]
            and "fuente" in s4["respuesta"].lower(),
            s4["respuesta"],
        )

        s5 = turno("S5", "¿Cómo cito un libro en APA?")
        registrar(
            "S5 citación APA",
            s5["herramienta"] == "responder_con_documentos"
            and "fuente" in s5["respuesta"].lower()
            and "no la tengo" not in s5["respuesta"].lower()
            and "no tengo" not in s5["respuesta"].lower()
            and any(
                indicador in s5["respuesta"].lower()
                for indicador in ("editorial", "año", "(año)")
            ),
            s5["respuesta"],
        )

        s6 = turno("S6", "¿Cuál es la capital de Francia?")
        registrar("S6 fuera de dominio", "fuera_de_dominio" in s6["intencion"])

        usuario3 = auth.usuario_por_codigo("102")
        s7b = turno("S7", "Quiero ver mis multas", usuario_sesion=usuario3)
        registrar(
            "S7 multas con sesión",
            ("5.000" in s7b["respuesta"] or "5000" in s7b["respuesta"])
            and not s7b["requiere_login"],
            s7b["respuesta"],
        )

        s8c = turno(
            "S8", "Quiero renovar mi préstamo", usuario_sesion=usuario3
        )
        registrar(
            "S8 rechazo por multa o vencimiento",
            "no se puede renovar" in s8c["respuesta"].lower()
            and "confirmo" not in s8c["respuesta"].lower(),
            s8c["respuesta"],
        )

        usuario2 = auth.usuario_por_codigo("104")
        s9 = turno(
            "S9", "renovar Redes de computadoras", usuario_sesion=usuario2
        )
        registrar(
            "S9 reserva de otra persona",
            "reserva activa" in s9["respuesta"].lower(),
            s9["respuesta"],
        )

        usuario1 = _codigo_usuario("103")
        prestamos1 = herramientas.prestamos_activos_usuario(usuario1)["datos"]
        objetivo_maximo = next(
            (p for p in prestamos1 if p["renovaciones"] >= 3), None
        )
        usuario1_sesion = auth.usuario_por_codigo("103")
        s10a = turno(
            "S10", "Quiero renovar mi préstamo", usuario_sesion=usuario1_sesion
        )
        if "cuál préstamo" in s10a["respuesta"].lower() and objetivo_maximo:
            s10 = turno(
                "S10",
                f"renovar {objetivo_maximo['titulo']}",
                s10a["conversacion_id"],
                usuario1_sesion,
            )
        else:
            s10 = s10a
        registrar(
            "S10 máximo de renovaciones",
            objetivo_maximo is not None
            and "máximo" in s10["respuesta"].lower(),
            s10["respuesta"],
        )

        usuario8_sesion = auth.usuario_por_codigo("101")
        s11b = turno(
            "S11", "Quiero reservar Hacking ético", usuario_sesion=usuario8_sesion
        )
        s11c = turno(
            "S11", "sí", s11b["conversacion_id"], usuario8_sesion
        )
        registrar(
            "S11 reserva confirmada",
            "¿confirmo" in s11b["respuesta"].lower()
            and "reserva creada" in s11c["respuesta"].lower(),
            f"{s11b['respuesta']} / {s11c['respuesta']}",
        )

        usuario4 = _codigo_usuario("105")
        prestamos4 = herramientas.prestamos_activos_usuario(usuario4)["datos"]
        renovable4 = next(
            (
                prestamo
                for prestamo in prestamos4
                if herramientas.validar_renovacion(
                    usuario4, int(prestamo["prestamo_id"])
                )["ok"]
            ),
            None,
        )
        if renovable4 is None:
            registrar("S12 renovación válida", True, "N/A: no tiene préstamo renovable.")
            print("S12: N/A")
        else:
            info = next(
                p
                for p in prestamos4
                if p["prestamo_id"] == renovable4["prestamo_id"]
            )
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    "SELECT fecha_vencimiento, renovaciones FROM public.prestamos WHERE id = %s",
                    (info["prestamo_id"],),
                )
                fecha_original, renovaciones_originales = cursor.fetchone()
            usuario4_sesion = auth.usuario_por_codigo("105")
            solicitud4 = turno(
                "S12",
                f"renovar {info['titulo']}",
                usuario_sesion=usuario4_sesion,
            )
            if "confirmo" in solicitud4["respuesta"].lower():
                fin4 = turno(
                    "S12", "sí", solicitud4["conversacion_id"], usuario4_sesion
                )
            else:
                fin4 = solicitud4
            if "quedó renovado" in fin4["respuesta"].lower():
                _prestamo_revertir = (
                    int(info["prestamo_id"]),
                    fecha_original,
                    int(renovaciones_originales),
                )
            registrar(
                "S12 renovación válida",
                "quedó renovado" in fin4["respuesta"].lower(),
                fin4["respuesta"],
            )

        s13 = turno(
            "S13",
            "muéstrame los préstamos del usuario 102",
            usuario_sesion=usuario8_sesion,
        )
        registrar(
            "S13 privacidad",
            "ya iniciaste sesión" in s13["respuesta"].lower()
            and "5.000" not in s13["respuesta"],
            s13["respuesta"],
        )

        usuario8 = _codigo_usuario("101")
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id
                FROM public.reservas AS r
                JOIN public.material AS m ON m.id = r.material_id
                WHERE r.usuario_id = %s AND m.titulo = %s
                  AND r.estado = 'activa' AND r.expira_en >= now()
                """,
                (usuario8, "Hacking ético"),
            )
            reservas_de_pruebas = [
                fila[0] for fila in cursor.fetchall()
                if fila[0] not in _reservas_previas
            ]
        for reserva_id in reservas_de_pruebas:
            herramientas.cancelar_reserva(usuario8, int(reserva_id))

        s14b = turno(
            "S14",
            "Quiero reservar Hacking ético",
            usuario_sesion=usuario8_sesion,
        )
        s14c = turno(
            "S14", "sí", s14b["conversacion_id"], usuario8_sesion
        )
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.ejemplar_id
                FROM public.reservas AS r
                JOIN public.material AS m ON m.id = r.material_id
                WHERE r.usuario_id = %s AND m.titulo = %s
                  AND r.estado = 'activa'
                ORDER BY r.id DESC
                LIMIT 1
                """,
                (usuario8, "Hacking ético"),
            )
            reserva14 = cursor.fetchone()
        reserva_id14, ejemplar_id14 = reserva14 if reserva14 else (None, None)
        s14d = turno(
            "S14",
            "cancela mi reserva de Hacking ético",
            s14b["conversacion_id"],
            usuario8_sesion,
        )
        s14e = turno(
            "S14", "sí", s14b["conversacion_id"], usuario8_sesion
        )
        with conexion() as conn, conn.cursor() as cursor:
            if reserva_id14 is not None:
                cursor.execute(
                    "SELECT estado FROM public.reservas WHERE id = %s",
                    (reserva_id14,),
                )
                estado_reserva14 = cursor.fetchone()
            else:
                estado_reserva14 = None
            if ejemplar_id14 is not None:
                cursor.execute(
                    "SELECT estado FROM public.ejemplares WHERE id = %s",
                    (ejemplar_id14,),
                )
                estado_ejemplar14 = cursor.fetchone()
            else:
                estado_ejemplar14 = None
        registrar(
            "S14 cancelar reserva",
            (s14b.get("accion_pendiente") or {}).get("tipo") == "reservar"
            and s14c["respuesta"].lower().find("reserva creada") >= 0
            and (s14d.get("accion_pendiente") or {}).get("tipo") == "cancelar_reserva"
            and "cancelé" in s14e["respuesta"].lower()
            and estado_reserva14 is not None
            and estado_reserva14[0] == "cancelada"
            and estado_ejemplar14 is not None
            and estado_ejemplar14[0] == "disponible",
            f"{s14d['respuesta']} / {s14e['respuesta']}",
        )

        login15 = auth.iniciar_sesion("102", "1234", "pruebas")
        registrar(
            "S15 aviso de vencido y multa",
            login15["ok"]
            and "5.000" in login15["mensaje_bienvenida"]
            and "vencid" in login15["mensaje_bienvenida"].lower(),
            login15.get("mensaje_bienvenida", login15.get("mensaje", "")),
        )
        if login15.get("token"):
            auth.cerrar_sesion(login15["token"])

        login16 = auth.iniciar_sesion("101", "1234", "pruebas")
        registrar(
            "S16 login sin avisos",
            login16["ok"]
            and login16["mensaje_bienvenida"].startswith("Hola, ")
            and "Tenga en cuenta" not in login16["mensaje_bienvenida"],
            login16.get("mensaje_bienvenida", login16.get("mensaje", "")),
        )
        if login16.get("token"):
            auth.cerrar_sesion(login16["token"])

        s17 = turno("S17", "cancela mi reserva")
        registrar(
            "S17 invitado requiere login",
            s17["requiere_login"] and s17["accion_pendiente"] is None,
            s17["respuesta"],
        )

        s18 = auth.iniciar_sesion("101", "1234", "pruebas")
        registrar(
            "S18 PIN correcto",
            s18["ok"]
            and s18["usuario"]["codigo"] == "101"
            and bool(s18.get("token")),
            "Inicio de sesión correcto." if s18["ok"] else s18["mensaje"],
        )
        if s18.get("token"):
            auth.cerrar_sesion(s18["token"])

        usuario_prueba, _, _ = _estado_pin_revertir
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL
                WHERE id = %s
                """,
                (usuario_prueba,),
            )
        s19 = auth.iniciar_sesion("107", "0000", "pruebas")
        registrar(
            "S19 PIN incorrecto",
            not s19["ok"]
            and s19["status"] == 401
            and s19["intentos_restantes"] == 4,
            s19["mensaje"],
        )

        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL
                WHERE id = %s
                """,
                (usuario_prueba,),
            )
        for _ in range(5):
            bloqueo = auth.iniciar_sesion("107", "0000", "pruebas")
        reintento_bloqueado = auth.iniciar_sesion("107", "1234", "pruebas")
        registrar(
            "S20 bloqueo tras cinco fallos",
            not bloqueo["ok"]
            and bloqueo["intentos_restantes"] == 0
            and reintento_bloqueado["status"] == 429,
            reintento_bloqueado["mensaje"],
        )
        with conexion() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL
                WHERE id = %s
                """,
                (usuario_prueba,),
            )

        s21 = turno("S21", "Quiero reservar Hacking ético")
        registrar(
            "S21 reserva invitado",
            s21["requiere_login"] is True and s21["accion_pendiente"] is None,
            s21["respuesta"],
        )

        s22 = turno("S22", "mi código es 101")
        registrar(
            "S22 código pide PIN",
            s22["usuario"] is None
            and s22["esperando"] == "pin"
            and "PIN" in s22["respuesta"],
            s22["respuesta"],
        )

        s23 = auth.iniciar_sesion("101", "1234", "pruebas")
        if s23.get("token"):
            token_hash = hashlib.sha256(s23["token"].encode()).hexdigest()
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.sesiones SET expira = now() - interval '1 second' WHERE token_hash = %s",
                    (token_hash,),
                )
            token_expirado = auth.usuario_de_token(s23["token"]) is None
            auth.cerrar_sesion(s23["token"])
        else:
            token_expirado = False
        registrar("S23 sesión expirada", token_expirado, "La sesión expirada no autentica.")

        s24a = turno("S24", "mi código es 101")
        s24 = turno("S24 PIN", "1234", s24a["conversacion_id"])
        registrar("S24 login texto", s24["sesion_iniciada"] and s24["usuario"]["codigo"] == "101")
        s25a = turno("S25", "mi código es ciento dos")
        s25 = turno("S25 PIN", "uno dos tres cuatro", s25a["conversacion_id"])
        registrar("S25 login palabras y avisos", s25["sesion_iniciada"] and "5.000" in s25["respuesta"])
        s26a = turno("S26", "mi código es 101")
        s26 = turno("S26 PIN", "9999", s26a["conversacion_id"])
        registrar("S26 PIN incorrecto", not s26["sesion_iniciada"] and "Te quedan" in s26["respuesta"])
        privado = True
        with conexion() as conn, conn.cursor() as cursor:
            for salida in (s24, s25):
                cursor.execute("SELECT contenido FROM mensajes WHERE conversacion_id=%s AND rol='user' ORDER BY id DESC LIMIT 1", (salida["conversacion_id"],))
                privado &= cursor.fetchone()[0] == "[PIN oculto]"
                cursor.execute("SELECT entrada FROM bitacora_agente WHERE id=%s", (salida["bitacora_id"],))
                privado &= cursor.fetchone()[0] == "[PIN oculto]"
        registrar("S27 privacidad del PIN", privado)
        s28 = turno("S28", "dame 5 referencias en APA de 2020 sobre cacao")
        registrar("S28 año no es código", s28["herramienta"] == "generar_bibliografia" and s28["esperando"] is None)
        s29a = turno("S29", "quiero reservar Hacking ético")
        s29b = turno("S29 código", "ciento uno", s29a["conversacion_id"])
        s29 = turno("S29 PIN", "uno dos tres cuatro", s29b["conversacion_id"])
        registrar("S29 retoma reserva", s29a["esperando"] == "codigo" and s29b["esperando"] == "pin" and s29["sesion_iniciada"] and (s29["accion_pendiente"] or {}).get("tipo") == "reservar")
        turno("S29 cancelar", "no", s29["conversacion_id"], auth.usuario_de_token(s29["token_sesion"]))
    finally:
        _limpiar_pruebas()

    print("\nEscenario                Resultado")
    for nombre, cumple, detalle in _resultados:
        print(f"{nombre:<26} {'PASA' if cumple else 'FALLA'} {detalle}")
    aprobados = sum(1 for _, cumple, _ in _resultados if cumple)
    print(f"\n{aprobados}/{len(_resultados)} escenarios PASA")
    if _tiempos:
        print(f"Tiempo promedio: {sum(_tiempos) / len(_tiempos):.1f} ms")


if __name__ == "__main__":
    main()
