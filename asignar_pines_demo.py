"""Asigna PIN de demostración a cuentas demo sin credencial."""

import argparse

from app.auth import hash_pin
from app.db import conexion


def main() -> None:
    parser = argparse.ArgumentParser(description="Configura los PIN de cuentas demo.")
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Reasigna el PIN de todas las cuentas demo.",
    )
    argumentos = parser.parse_args()
    with conexion() as conn, conn.cursor() as cursor:
        condicion = "" if argumentos.forzar else "AND pin_hash IS NULL"
        cursor.execute(
            f"""
            SELECT id
            FROM public.usuarios
            WHERE es_demo = true {condicion}
            ORDER BY id
            FOR UPDATE
            """
        )
        ids = [fila[0] for fila in cursor.fetchall()]
        for usuario_id in ids:
            cursor.execute(
                "UPDATE public.usuarios SET pin_hash = %s WHERE id = %s",
                (hash_pin("1234"), usuario_id),
            )
    print(f"Se actualizaron {len(ids)} usuarios demo.")


if __name__ == "__main__":
    main()
