"""Refresca los datos demo de la biblioteca para que sigan siendo válidos.

Este script reubica únicamente los registros operativos de los usuarios demo
(101–108) y mantiene el resto del sistema intacto: usuarios, PIN, sesiones,
material, conocimiento, conversaciones y bitácora.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.db import conexion

RAIZ = Path(__file__).resolve().parent
SQL_REFRESCO = RAIZ / "sql" / "refrescar_demo.sql"


def _estado_esperado() -> dict[str, str]:
    return {
        "101": "sin préstamos, sin multas y sin reservas activas",
        "102": "préstamo vencido de «Fundamentos de seguridad en redes» + multa pendiente de $5.000",
        "103": "préstamo activo de «Cálculo de una variable» con 3 renovaciones y vence en 6 días",
        "104": "préstamo activo de «Redes de computadoras» con 1 renovación y vence en 7 días",
        "105": "préstamo activo de «Ingeniería de software» con 0 renovaciones y vence en 5 días",
        "106": "préstamo activo regular de «Fundamentos de bases de datos» y vence en 8 días",
        "108": "reserva activa de «Redes de computadoras» en cola con expira_en = now() + 48h",
    }


def _sentencias_sql() -> list[str]:
    texto = SQL_REFRESCO.read_text(encoding="utf-8")
    sentencias: list[str] = []
    for bloque in texto.split(";"):
        limpio = []
        for linea in bloque.splitlines():
            stripped = linea.strip()
            if not stripped or stripped.startswith("--"):
                continue
            limpio.append(linea.rstrip())
        sentencia = "\n".join(limpio).strip()
        if sentencia:
            sentencias.append(sentencia)
    return sentencias


def _resumen_actual() -> list[dict[str, Any]]:
    with conexion() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                u.codigo,
                u.nombre,
                COALESCE(
                    (
                        SELECT m.titulo
                        FROM public.prestamos AS p
                        JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
                        JOIN public.material AS m ON m.id = e.material_id
                        WHERE p.usuario_id = u.id
                          AND p.estado IN ('activo', 'vencido')
                        ORDER BY p.fecha_vencimiento DESC, p.id DESC
                        LIMIT 1
                    ),
                    ''
                ) AS titulo_prestamo,
                COALESCE(
                    (
                        SELECT SUM(mv.valor)
                        FROM public.multas AS mv
                        WHERE mv.usuario_id = u.id
                          AND mv.estado = 'pendiente'
                    ),
                    0
                ) AS multa_pendiente,
                COALESCE(
                    (
                        SELECT COUNT(*)
                        FROM public.reservas AS r
                        WHERE r.usuario_id = u.id
                          AND r.estado = 'activa'
                    ),
                    0
                ) AS reservas_activas
            FROM public.usuarios AS u
            WHERE u.codigo BETWEEN '101' AND '108'
            ORDER BY u.codigo
            """
        )
        filas = []
        for codigo, nombre, titulo, multa, reservas in cursor.fetchall():
            codigo = str(codigo)
            if codigo == "102":
                situacion = (
                    f"préstamo vencido de «{titulo}» y multa pendiente de ${float(multa):,.0f}"
                    if titulo
                    else "sin préstamo activo ni reserva activa"
                )
            elif codigo == "103":
                situacion = (
                    f"préstamo activo de «{titulo}» con 3 renovaciones y vencimiento en 6 días"
                    if titulo
                    else "sin préstamo activo"
                )
            elif codigo == "104":
                situacion = (
                    f"préstamo activo de «{titulo}» con 1 renovación y vencimiento en 7 días"
                    if titulo
                    else "sin préstamo activo"
                )
            elif codigo == "105":
                situacion = (
                    f"préstamo activo de «{titulo}» con 0 renovaciones y vencimiento en 5 días"
                    if titulo
                    else "sin préstamo activo"
                )
            elif codigo == "106":
                situacion = (
                    f"préstamo activo regular de «{titulo}» y vencimiento en 8 días"
                    if titulo
                    else "sin préstamo activo"
                )
            elif codigo == "101":
                situacion = (
                    "sin préstamos, sin multas y sin reservas activas"
                    if int(reservas) == 0 and float(multa) == 0
                    else "hay pendientes que deben limpiarse"
                )
            elif codigo == "108":
                situacion = (
                    "reserva activa de «Redes de computadoras» en cola con expira_en = now() + 48h"
                    if int(reservas) > 0
                    else "sin reserva activa"
                )
            else:
                situacion = "estado demo"
            filas.append(
                {
                    "codigo": codigo,
                    "nombre": nombre,
                    "situacion": situacion,
                    "multa_pendiente": float(multa),
                    "reservas_activas": int(reservas),
                }
            )
    return filas


def _mostrar_estado_actual_vs_esperado() -> list[dict[str, Any]]:
    esperado = _estado_esperado()
    actual = _resumen_actual()
    for fila in actual:
        codigo = fila["codigo"]
        fila["esperado"] = esperado.get(codigo, "estado demo")
        fila["coincide"] = fila["situacion"].lower() == fila["esperado"].lower()
    return actual


def refrescar_demo() -> list[dict[str, Any]]:
    """Actualiza los datos demo y devuelve el resumen final."""
    with conexion() as conn:
        for sentencia in _sentencias_sql():
            conn.execute(sentencia)
    return _mostrar_estado_actual_vs_esperado()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresca los datos operativos demo para la biblioteca."
    )
    parser.add_argument(
        "--solo-mostrar",
        action="store_true",
        help="Muestra el estado actual y el esperado sin tocar la base de datos.",
    )
    argumentos = parser.parse_args()

    if argumentos.solo_mostrar:
        filas = _mostrar_estado_actual_vs_esperado()
        print("Estado actual vs esperado (sin cambios):")
        for fila in filas:
            print(
                f"- {fila['codigo']} {fila['nombre']}: "
                f"actual={fila['situacion']} | esperado={fila['esperado']}"
            )
        return

    filas = refrescar_demo()
    print("Demo actualizada:")
    for fila in filas:
        print(
            f"- {fila['codigo']} {fila['nombre']}: {fila['situacion']}"
        )


if __name__ == "__main__":
    main()
