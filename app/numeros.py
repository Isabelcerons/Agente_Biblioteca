"""Interpreta códigos y PIN dictados en español, sin buscar números en frases libres."""
import re
import unicodedata

_UNIDADES = dict(zip("cero uno dos tres cuatro cinco seis siete ocho nueve".split(), range(10)))
_NUMEROS = {**_UNIDADES, **dict(zip("diez once doce trece catorce quince dieciseis diecisiete dieciocho diecinueve veinte veintiuno veintidos veintitres veinticuatro veinticinco veintiseis veintisiete veintiocho veintinueve".split(), range(10, 30))), **dict(zip("treinta cuarenta cincuenta sesenta setenta ochenta noventa".split(), range(30, 100, 10))), **dict(zip("cien ciento doscientos trescientos cuatrocientos quinientos seiscientos setecientos ochocientos novecientos".split(), [100,100,200,300,400,500,600,700,800,900]))}

def _normalizar(texto):
    texto = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()

def _digitos(texto):
    palabras = _normalizar(texto).split()
    if not palabras:
        return None
    if all(p.isdigit() or p in _UNIDADES for p in palabras):
        return "".join(p if p.isdigit() else str(_UNIDADES[p]) for p in palabras)
    # El STT también agrupa el PIN en pares: doce treinta y cuatro.
    if len(palabras) >= 2 and palabras[0] in _NUMEROS and 10 <= _NUMEROS[palabras[0]] <= 29:
        resto = palabras_a_numero(" ".join(palabras[1:]))
        if resto is not None and 10 <= resto <= 99:
            return str(_NUMEROS[palabras[0]]) + str(resto)
    numero = palabras_a_numero(" ".join(palabras))
    return str(numero) if numero is not None else None

def palabras_a_numero(texto: str) -> int | None:
    """Convierte un cardinal o una secuencia de dígitos; rechaza frases ajenas."""
    palabras = _normalizar(texto).split()
    if not palabras:
        return None
    if all(p.isdigit() or p in _UNIDADES for p in palabras):
        return int("".join(p if p.isdigit() else str(_UNIDADES[p]) for p in palabras))
    total = parcial = 0
    for i, palabra in enumerate(palabras):
        if palabra == "y":
            if i == 0 or i == len(palabras)-1:
                return None
        elif palabra == "mil":
            total += (parcial or 1) * 1000
            parcial = 0
        elif palabra in _NUMEROS:
            parcial += _NUMEROS[palabra]
        else:
            return None
    return total + parcial

def extraer_codigo(texto: str) -> str | None:
    """Interpreta un código de 3 a 10 dígitos, conservando ceros iniciales."""
    texto = _normalizar(texto)
    texto = re.sub(r"^(?:mi codigo(?: es| les)?|codigo(?: es| les)?|soy el)\s+", "", texto)
    numero = _digitos(texto)
    return numero if numero and re.fullmatch(r"[0-9]{3,10}", numero) else None

def pin_explicito(texto: str) -> bool:
    """Solo prefijos completos al inicio; incluye colas inválidas para ocultarlas."""
    return bool(re.match(r"^(?:(?:mi|el)\s+pin\s+es|pin)\b", _normalizar(texto)))


def extraer_pin(texto: str) -> str | None:
    """Interpreta exactamente cuatro dígitos sin conservar el PIN en estado."""
    # Whisper intercala a veces «el» entre dígitos dictados; no cambia sus valores.
    texto = re.sub(r"^(?:(?:mi|el)\s+pin\s+es|pin)\b\s*", "", _normalizar(texto))
    texto = re.sub(r"\bel\b", " ", texto)
    numero = _digitos(texto)
    return numero if numero and re.fullmatch(r"[0-9]{4}", numero) else None

def _probar():
    casos = {"ciento uno": "101", "ciento dos": "102", "uno cero uno": "101", "mil doscientos treinta y cuatro": "1234", "uno dos tres cuatro": "1234", "doce treinta y cuatro": "1234", "101.": "101", "dos mil veinte": "2020", "1-0-1": "101", "Ciento ocho.": "108", "código 101": "101", "mi código es ciento dos": "102", "soy el 103": "103", "ciento cuatro": "104", "ciento cinco": "105", "ciento seis": "106", "ciento siete": "107"}
    for texto, esperado in casos.items():
        assert extraer_codigo(texto) == esperado, texto
    assert palabras_a_numero("veintiuno") == 21
    assert extraer_pin("cero uno dos tres") == "0123"
    assert extraer_pin("123") is None
    assert extraer_codigo("dame 5 referencias de 2020") is None
    assert extraer_codigo("veintiuno") is None
    print("22 comprobaciones de números: PASA")

if __name__ == "__main__":
    _probar()
