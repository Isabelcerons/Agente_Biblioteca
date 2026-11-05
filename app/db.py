"""Conexión transaccional a PostgreSQL y registro de tipos pgvector."""

from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg import Connection

from app.config import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def conectar() -> Connection:
    """Abre una conexión con soporte para valores vectoriales."""
    try:
        conexion = psycopg.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
            autocommit=False,
        )
        register_vector(conexion)
        return conexion
    except psycopg.OperationalError as error:
        raise RuntimeError(
            "No fue posible conectar con PostgreSQL. Verifique que el servicio "
            "esté iniciado (Start-Service postgresql-x64-17) y que PG_HOST, "
            "PG_PORT, PG_DB y las credenciales de .env sean correctos."
        ) from error


@contextmanager
def conexion() -> Iterator[Connection]:
    """Confirma al terminar o revierte ante un error, y siempre cierra."""
    conn = conectar()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
