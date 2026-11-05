"""CLI para calcular o actualizar el mapa del conocimiento."""

import argparse

from app.mapa import calcular_mapa


def main() -> int:
    """Calcula el mapa e imprime su tamaño y varianza explicada."""
    parser = argparse.ArgumentParser(
        description="Calcula la proyección PCA del mapa del conocimiento."
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="recalcula el mapa aunque los documentos no hayan cambiado",
    )
    argumentos = parser.parse_args()
    resultado = calcular_mapa(forzar=argumentos.forzar)
    varianzas = resultado["varianza_explicada"]
    if resultado["recalculado"]:
        print(f"Mapa calculado: {resultado['n']} materiales.")
    else:
        print(f"Mapa sin cambios: {resultado['n']} materiales.")
    if varianzas:
        print(
            "Varianza explicada: "
            + ", ".join(
                f"componente {indice + 1}: {valor * 100:.2f}%"
                for indice, valor in enumerate(varianzas)
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
