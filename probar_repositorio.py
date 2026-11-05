"""Prueba de aceptación del flujo de carga de tesis al repositorio."""

import time
from typing import Any

from fastapi.testclient import TestClient

from app import mapa
from app.config import RAIZ
from app.db import conexion
from app.main import app

TITULO = (
    "Prototipo de riego inteligente con sensores de humedad para cultivos de cacao"
)
_resultados: list[tuple[str, bool, str]] = []
_creados: list[int] = []


def _registrar(nombre: str, cumple: bool, detalle: str = "") -> None:
    _resultados.append((nombre, cumple, detalle))


def _pdf_literal(texto: str) -> bytes:
    salida: list[str] = []
    for byte in texto.encode("cp1252", errors="replace"):
        if byte in (ord("("), ord(")"), ord("\\")):
            salida.append("\\" + chr(byte))
        elif byte < 32 or byte > 126:
            salida.append(f"\\{byte:03o}")
        else:
            salida.append(chr(byte))
    return "".join(salida).encode("ascii")


def _envolver(texto: str, ancho: int = 82) -> list[str]:
    lineas: list[str] = []
    for parrafo in texto.splitlines():
        palabras = parrafo.split()
        actual = ""
        for palabra in palabras:
            if actual and len(actual) + len(palabra) + 1 > ancho:
                lineas.append(actual)
                actual = palabra
            else:
                actual = f"{actual} {palabra}".strip()
        if actual:
            lineas.append(actual)
    return lineas


def _crear_pdf(paginas: list[str]) -> bytes:
    objetos: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # Se completa con las referencias de página.
    ]
    referencias: list[str] = []
    for indice, texto in enumerate(paginas):
        id_pagina = 3 + indice * 2
        id_contenido = id_pagina + 1
        referencias.append(f"{id_pagina} 0 R")
        lineas = _envolver(texto)
        operaciones = [b"BT\n/F1 11 Tf\n50 760 Td\n14 TL"]
        for linea in lineas:
            operaciones.append(b"(" + _pdf_literal(linea) + b") Tj\nT*")
        operaciones.append(b"ET")
        contenido = b"\n".join(operaciones)
        objetos.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 {3 + 2 * len(paginas)} 0 R >> >> "
                    f"/Contents {id_contenido} 0 R >>"
                ).encode("ascii"),
                (
                    f"<< /Length {len(contenido)} >>\nstream\n".encode("ascii")
                    + contenido
                    + b"\nendstream"
                ),
            ]
        )
    objetos[1] = (
        f"<< /Type /Pages /Kids [{' '.join(referencias)}] /Count {len(paginas)} >>"
    ).encode("ascii")
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    desplazamientos = [0]
    for numero, objeto in enumerate(objetos, start=1):
        desplazamientos.append(len(salida))
        salida.extend(f"{numero} 0 obj\n".encode("ascii"))
        salida.extend(objeto)
        salida.extend(b"\nendobj\n")
    inicio_xref = len(salida)
    salida.extend(f"xref\n0 {len(objetos) + 1}\n".encode("ascii"))
    salida.extend(b"0000000000 65535 f \n")
    for desplazamiento in desplazamientos[1:]:
        salida.extend(f"{desplazamiento:010d} 00000 n \n".encode("ascii"))
    salida.extend(
        (
            f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
            f"startxref\n{inicio_xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(salida)


def _pdf_tesis() -> bytes:
    resumen = (
        "RESUMEN\n"
        "Este trabajo desarrolla un prototipo de riego inteligente para cultivos de "
        "cacao en el Putumayo. El sistema utiliza sensores de humedad instalados en "
        "el suelo para conocer las necesidades de agua de cada parcela. Las mediciones "
        "se envían mediante una red de Internet de las cosas a una unidad de control "
        "que analiza los valores y activa una bomba cuando la humedad está por debajo "
        "del nivel establecido. La automatización busca reducir el desperdicio de "
        "agua, mejorar la estabilidad de las plantas y facilitar el seguimiento de "
        "las condiciones del cultivo. El prototipo registra datos periódicos y "
        "permite consultar el estado del sistema desde una interfaz sencilla. Las "
        "pruebas realizadas muestran que los sensores responden a los cambios de "
        "humedad y que el riego puede activarse de forma automática. La propuesta "
        "considera las condiciones de pequeños productores de cacao de la región, "
        "la disponibilidad de conectividad y la necesidad de mantener equipos de "
        "bajo costo. Se concluye que integrar sensores, comunicación IoT y control "
        "automatizado ofrece una alternativa para apoyar el manejo eficiente del "
        "agua, aunque se recomienda ampliar las pruebas en diferentes suelos y "
        "temporadas antes de una implementación productiva."
    )
    contenido_dos = (
        "INTRODUCCION\n"
        "La producción de cacao es una actividad importante para numerosas familias "
        "del Putumayo. La disponibilidad de agua y el seguimiento de la humedad "
        "influyen en el desarrollo de las plantas. Este proyecto plantea una solución "
        "de bajo costo con sensores, un microcontrolador y una bomba de agua. El "
        "diseño prioriza mediciones confiables, mantenimiento sencillo y operación "
        "adaptable a parcelas rurales. La arquitectura transmite las lecturas a una "
        "plataforma que conserva los valores y facilita su revisión por el productor. "
        "El sistema evita activar el riego cuando el suelo ya contiene suficiente "
        "humedad y registra cada decisión para comparar el funcionamiento."
    )
    contenido_tres = (
        "RESULTADOS Y CONCLUSIONES\n"
        "Las pruebas de laboratorio verificaron la lectura de los sensores en suelo "
        "seco y húmedo, la transmisión de información y la activación del sistema "
        "de riego. El prototipo respondió a los umbrales configurados y permitió "
        "consultar las mediciones de manera remota. La automatización puede ayudar "
        "a optimizar el uso del agua y apoyar decisiones oportunas en cultivos de "
        "cacao. Para trabajos posteriores se recomienda evaluar la precisión durante "
        "periodos prolongados, estudiar costos de conectividad y probar el diseño "
        "en parcelas con diferentes características del suelo en el Putumayo."
    )
    return _crear_pdf(
        [
            f"{TITULO}\n\n{resumen}",
            f"{TITULO}\n\n{contenido_dos}",
            f"{TITULO}\n\n{contenido_tres}",
        ]
    )


def _pdf_sin_texto() -> bytes:
    return _crear_pdf([""])


def _esperar_estado(
    cliente: TestClient, carga_id: str, limite_segundos: int = 180
) -> dict[str, Any] | None:
    inicio = time.monotonic()
    ultima_etapa = ""
    while time.monotonic() - inicio < limite_segundos:
        respuesta = cliente.get(f"/api/tesis/progreso/{carga_id}")
        if respuesta.status_code != 200:
            return None
        estado = respuesta.json()
        if estado.get("etapa") != ultima_etapa:
            ultima_etapa = str(estado.get("etapa"))
            print(
                f"  Etapa {ultima_etapa}: {estado.get('avance')}/"
                f"{estado.get('total')} — {estado.get('mensaje')}"
            )
        if estado.get("etapa") in {"lista", "error"}:
            return estado
        time.sleep(1)
    return None


def _limpiar() -> None:
    """Elimina exclusivamente los materiales registrados por esta prueba."""
    for material_id in _creados:
        try:
            with conexion() as conn, conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM conocimiento.documentos WHERE material_id = %s",
                    (material_id,),
                )
                cursor.execute(
                    "DELETE FROM public.cargas_tesis WHERE material_id = %s",
                    (material_id,),
                )
                cursor.execute(
                    "DELETE FROM public.ejemplares WHERE material_id = %s",
                    (material_id,),
                )
                cursor.execute("DELETE FROM public.material WHERE id = %s", (material_id,))
            archivo = RAIZ / "repositorio" / "tesis" / f"{material_id}.pdf"
            archivo.unlink(missing_ok=True)
        except Exception as error:
            print(f"FALLA limpieza del material {material_id}: {error}")
            _registrar("Limpieza", False, str(error))
    try:
        mapa.calcular_mapa()
    except Exception as error:
        print(f"FALLA recálculo del mapa tras la limpieza: {error}")
        _registrar("Limpieza del mapa", False, str(error))


def main() -> None:
    carga_id: str | None = None
    material_id: int | None = None
    try:
        with TestClient(app) as cliente:
            anonimo = cliente.post(
                "/api/tesis",
                data={
                    "titulo": TITULO,
                    "autor": "Equipo de prueba del repositorio",
                    "anio": "2026",
                    "programa": "Ingeniería Agroforestal",
                },
                files={"pdf": ("tesis.pdf", _pdf_tesis(), "application/pdf")},
            )
            _registrar(
                "Invitado recibe 401",
                anonimo.status_code == 401,
                str(anonimo.status_code),
            )

            login = cliente.post(
                "/api/login",
                json={"codigo": "101", "pin": "1234"},
            )
            _registrar("Inicio de sesión", login.status_code == 200 and login.json().get("ok") is True)
            if login.status_code != 200:
                raise RuntimeError("No fue posible iniciar sesión con el usuario de prueba.")

            invalido = cliente.post(
                "/api/tesis",
                data={
                    "titulo": TITULO,
                    "autor": "Equipo de prueba del repositorio",
                    "anio": "2026",
                    "programa": "Ingeniería Agroforestal",
                },
                files={"pdf": ("no-es-pdf.txt", b"texto plano", "application/pdf")},
            )
            _registrar(
                "Archivo no PDF recibe 422",
                invalido.status_code == 422
                and "PDF" in invalido.json().get("mensaje", ""),
                invalido.text,
            )

            mapa_inicial = cliente.get("/api/mapa")
            puntos_iniciales = len(mapa_inicial.json().get("puntos", [])) if mapa_inicial.is_success else -1
            carga = cliente.post(
                "/api/tesis",
                data={
                    "titulo": TITULO,
                    "autor": "Equipo de prueba del repositorio",
                    "anio": "2026",
                    "programa": "Ingeniería Agroforestal",
                },
                files={"pdf": ("tesis.pdf", _pdf_tesis(), "application/pdf")},
            )
            _registrar("Carga aceptada", carga.status_code == 202, carga.text)
            if carga.status_code == 202:
                carga_id = carga.json()["carga_id"]
                material_id = int(carga.json()["material_id"])
                _creados.append(material_id)

            estado: dict[str, Any] | None = None
            if carga_id:
                estado = _esperar_estado(cliente, carga_id)
            _registrar(
                "Procesamiento termina",
                bool(estado and estado.get("etapa") == "lista"),
                str((estado or {}).get("error") or (estado or {}).get("mensaje")),
            )

            if material_id is not None:
                with conexion() as conn, conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT tipo FROM public.material WHERE id = %s",
                        (material_id,),
                    )
                    material = cursor.fetchone()
                    cursor.execute(
                        """
                        SELECT d.tipo, count(f.id)
                        FROM conocimiento.documentos AS d
                        LEFT JOIN conocimiento.fragmentos AS f ON f.documento_id = d.id
                        WHERE d.material_id = %s
                        GROUP BY d.id, d.tipo
                        ORDER BY d.tipo
                        """,
                        (material_id,),
                    )
                    documentos = cursor.fetchall()
                _registrar(
                    "Material y dos documentos",
                    material == ("tesis",)
                    and len(documentos) == 2
                    and all(cantidad > 0 for _, cantidad in documentos),
                    f"material={material}, documentos={documentos}",
                )
            else:
                _registrar("Material y dos documentos", False, "No se creó el material.")

            catalogo = cliente.get("/api/catalogo", params={"q": "riego"})
            resultados = catalogo.json().get("resultados", []) if catalogo.is_success else []
            _registrar(
                "Catálogo encuentra la tesis",
                any(fila.get("titulo") == TITULO for fila in resultados),
                catalogo.text,
            )

            puntos = cliente.get("/api/mapa")
            puntos_finales = len(puntos.json().get("puntos", [])) if puntos.is_success else -1
            _registrar(
                "Mapa suma un punto",
                puntos_iniciales >= 0 and puntos_finales == puntos_iniciales + 1,
                f"{puntos_iniciales} -> {puntos_finales}",
            )

            busqueda = cliente.post(
                "/api/chat",
                json={"texto": "Busco tesis sobre riego automatizado de cacao"},
            )
            materiales_chat = busqueda.json().get("materiales", []) if busqueda.is_success else []
            _registrar(
                "Chat encuentra la tesis",
                any(fila.get("titulo") == TITULO for fila in materiales_chat),
                busqueda.text,
            )

            resumen = cliente.post(
                "/api/chat",
                json={"texto": "¿De qué trata la tesis Prototipo de riego inteligente?"},
            )
            datos_resumen = resumen.json() if resumen.is_success else {}
            _registrar(
                "Chat resume con fuente",
                datos_resumen.get("herramienta") == "resumir_material"
                and "Fuente:" in str(datos_resumen.get("respuesta", "")),
                str(datos_resumen.get("respuesta")),
            )

            pdf_vacio = cliente.post(
                "/api/tesis",
                data={
                    "titulo": "Prueba de PDF sin texto seleccionable",
                    "autor": "Equipo de prueba",
                    "anio": "2026",
                    "programa": "Ingeniería Agroforestal",
                },
                files={"pdf": ("vacio.pdf", _pdf_sin_texto(), "application/pdf")},
            )
            _registrar(
                "PDF sin texto aceptado para validación",
                pdf_vacio.status_code == 202,
                pdf_vacio.text,
            )
            if pdf_vacio.status_code == 202:
                _creados.append(int(pdf_vacio.json()["material_id"]))
                estado_vacio = _esperar_estado(
                    cliente, pdf_vacio.json()["carga_id"]
                )
                mensaje_error = str((estado_vacio or {}).get("error") or "")
                _registrar(
                    "PDF escaneado informa error claro",
                    bool(
                        estado_vacio
                        and estado_vacio.get("etapa") == "error"
                        and "no tiene texto seleccionable" in mensaje_error.lower()
                        and "no hace ocr" in mensaje_error.lower()
                    ),
                    mensaje_error,
                )
            else:
                _registrar(
                    "PDF escaneado informa error claro",
                    False,
                    pdf_vacio.text,
                )
    except Exception as error:
        _registrar("Ejecución de la prueba", False, str(error))
    finally:
        _limpiar()

    aprobados = sum(1 for _, cumple, _ in _resultados if cumple)
    for nombre, cumple, detalle in _resultados:
        print(f"{nombre}: {'PASA' if cumple else 'FALLA'} {detalle}")
    print(f"\n{aprobados}/{len(_resultados)} PASA")


if __name__ == "__main__":
    main()
