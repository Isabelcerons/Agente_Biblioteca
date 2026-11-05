"""Formato común de fechas y dinero para respuestas en español."""

from datetime import date, datetime
from typing import Any


def fecha_es(valor: date | datetime | str) -> str:
    """Presenta fechas en español y convierte datetimes a la zona local."""
    mostrar_hora = isinstance(valor, datetime)
    if isinstance(valor, str):
        mostrar_hora = "T" in valor or " " in valor
        try:
            valor = datetime.fromisoformat(valor)
        except ValueError:
            try:
                valor = date.fromisoformat(valor)
            except ValueError:
                return valor
    meses = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    salida = f"{valor.day} de {meses[valor.month - 1]}"
    if isinstance(valor, datetime) and mostrar_hora:
        local = valor.astimezone() if valor.tzinfo else valor
        hora = local.hour % 12 or 12
        minuto = f":{local.minute:02d}" if local.minute else ""
        periodo = "a. m." if local.hour < 12 else "p. m."
        salida += f" a las {hora}{minuto} {periodo}"
    return salida


def pesos(valor: Any) -> str:
    """Formatea una cantidad en el estilo colombiano, sin decimales."""
    try:
        entero = round(float(valor or 0))
    except (TypeError, ValueError):
        entero = 0
    return "$" + f"{entero:,}".replace(",", ".")
