"""Normalización acotada de nombres de normas, sin cambiar números ni credenciales."""
import re


def normalizar_consulta(texto: str) -> str:
    texto = re.sub(r"\b(?:i\s*[,;]?\s*)?triple\s+e\b", "IEEE", texto, flags=re.I)
    texto = re.sub(r"\bi[\s,.-]+e[\s,.-]+e[\s,.-]+e\b", "IEEE", texto, flags=re.I)
    texto = re.sub(r"\benormes\s+(?=(?:APA|IEEE)\b)", "normas ", texto, flags=re.I)
    return texto
