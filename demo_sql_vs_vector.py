"""Compara una búsqueda literal con la recuperación semántica de pgvector."""

import sys
import time

from app.rag import buscar_exacto_sql, buscar_materiales_semantico

CONSULTA_PREDETERMINADA = "cómo proteger una red de una empresa"


def _tabla_sql(filas: list[dict]) -> None:
    """Imprime resultados de la búsqueda literal en columnas sencillas."""
    print("SQL (ILIKE)")
    if not filas:
        print("  Sin coincidencias literales.")
        return
    print(f"  {'Título':58} {'Tipo':8} {'Disp./total':12}")
    for fila in filas:
        disponibilidad = f"{fila['disponibles']}/{fila['total']}"
        print(
            f"  {str(fila['titulo'])[:58]:58} "
            f"{str(fila['tipo'])[:8]:8} {disponibilidad:12}"
        )


def _tabla_vectorial(filas: list[dict]) -> None:
    """Imprime título, categoría, disponibilidad y similitud."""
    print("pgvector (búsqueda semántica)")
    if not filas:
        print("  Sin resultados semánticos.")
        return
    print(f"  {'Título':58} {'Tipo':8} {'Disp./total':12} {'Similitud':9}")
    for fila in filas:
        disponibilidad = f"{fila['disponibles']}/{fila['total']}"
        print(
            f"  {str(fila['titulo'])[:58]:58} "
            f"{str(fila['tipo'])[:8]:8} {disponibilidad:12} "
            f"{float(fila['similitud']):.3f}"
        )


def main() -> int:
    """Ejecuta las dos búsquedas usando exactamente la misma consulta."""
    consulta = " ".join(sys.argv[1:]).strip() or CONSULTA_PREDETERMINADA
    print(f'Consulta: "{consulta}"\n')
    try:
        inicio = time.perf_counter()
        resultados_sql = buscar_exacto_sql(consulta)
        tiempo_sql = (time.perf_counter() - inicio) * 1000
        resultados_vector, tiempos = buscar_materiales_semantico(consulta, k=5)

        _tabla_sql(resultados_sql)
        print(f"  Tiempo de búsqueda SQL: {tiempo_sql:.2f} ms\n")
        _tabla_vectorial(resultados_vector)
        print(
            "  Tiempos pgvector: "
            f"embedding {tiempos['t_embedding_ms']:.2f} ms, "
            f"consulta {tiempos['t_busqueda_ms']:.2f} ms"
        )
        print(
            "\nSQL encuentra coincidencias de texto en títulos/autores; "
            "pgvector compara significado y puede recuperar materiales "
            "pertinentes aunque no repitan las palabras de la consulta."
        )
        return 0
    except Exception as error:
        print(f"Error en la demostración: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
