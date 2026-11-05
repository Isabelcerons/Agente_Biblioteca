"""Regresión de resúmenes con dobles; --real añade una lectura del acervo.

No usa endpoints ni procesa mensajes; no crea conversaciones ni trámites.
"""
import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import herramientas


LIBRO = {"material_id": 10, "tipo": "libro", "titulo": "Redes", "autor": "Autor libro"}
TESIS = {"material_id": 20, "tipo": "tesis", "titulo": "Redes", "autor": "Autor tesis"}


def fragmento(material, tipo, seccion="", texto="Texto real del documento", **extras):
    return {
        "material_id": material["material_id"], "tipo": tipo, "seccion": seccion,
        "texto": texto, "documento": material["titulo"], "fuente": "documento_de_prueba.md",
        **extras,
    }


class ResumenMaterial(unittest.TestCase):
    def consultar(self, candidatos, fragmentos, pregunta="¿De qué trata «Redes»?"):
        with (
            patch.object(herramientas, "resolver_material", return_value={"ok": True, "datos": candidatos}),
            patch.object(herramientas, "enriquecer_materiales", side_effect=lambda filas: filas),
            patch.object(herramientas.rag, "buscar_fragmentos_material", return_value=(fragmentos, {"t_busqueda_ms": 2})) as buscar,
        ):
            resultado = herramientas.resumir_material("Redes", pregunta)
        return resultado, buscar

    def test_libro_con_resena_y_fuente_real(self):
        original = fragmento(LIBRO, "resena_libro", "Contenido y alcance")
        resultado, buscar = self.consultar([LIBRO], [original])
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["datos"], [original])
        self.assertEqual(resultado["materiales"], [LIBRO])
        self.assertEqual(resultado["fuentes"][0]["seccion"], "Contenido y alcance")
        self.assertEqual(resultado["fuentes"][0]["fuente"], original["fuente"])
        buscar.assert_called_once_with(10, "¿De qué trata «Redes»?", limite_completa=3)

    def test_tesis_con_resumen_y_paginas_pdf(self):
        fuentes = [fragmento(TESIS, "resumen_tesis"), fragmento(TESIS, "tesis_completa", "Página 8")]
        resultado, _ = self.consultar([TESIS], fuentes, "Resume la tesis «Redes»")
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["datos"], fuentes)
        self.assertEqual([f["seccion"] for f in resultado["fuentes"]], ["Resumen", "Página 8"])

    def test_tesis_explicita_no_se_sustituye_por_libro(self):
        resultado, buscar = self.consultar([LIBRO], [], "¿De qué trata la tesis «Redes»?")
        self.assertFalse(resultado["ok"])
        self.assertIn("esa tesis", resultado["mensaje"])
        buscar.assert_not_called()

    def test_tipo_explicito_desambigua(self):
        for material, tipo, pregunta in (
            (LIBRO, "resena_libro", "Resume el libro «Redes»"),
            (TESIS, "resumen_tesis", "Resume la tesis «Redes»"),
        ):
            with self.subTest(tipo=tipo):
                resultado, buscar = self.consultar([LIBRO, TESIS], [fragmento(material, tipo)], pregunta)
                self.assertTrue(resultado["ok"])
                self.assertEqual(buscar.call_args.args[0], material["material_id"])

    def test_varios_materiales_piden_seleccion_sin_buscar_fragmentos(self):
        resultado, buscar = self.consultar([LIBRO, TESIS], [])
        self.assertFalse(resultado["ok"])
        self.assertIn("¿Cuál material", resultado["mensaje"])
        self.assertIn("Autor libro", resultado["mensaje"])
        self.assertIn("Autor tesis", resultado["mensaje"])
        self.assertEqual(resultado["datos"], [])
        self.assertEqual(resultado["materiales"], [LIBRO, TESIS])
        buscar.assert_not_called()

    def test_candidato_duplicado_no_crea_ambiguedad(self):
        resultado, buscar = self.consultar([LIBRO, dict(LIBRO)], [fragmento(LIBRO, "resena_libro")])
        self.assertTrue(resultado["ok"])
        buscar.assert_called_once()

    def test_sin_fragmentos_no_inventa_resumen(self):
        for material in (LIBRO, TESIS):
            with self.subTest(tipo=material["tipo"]):
                resultado, _ = self.consultar([material], [])
                self.assertFalse(resultado["ok"])
                self.assertIn("indexado disponible", resultado["mensaje"])
                self.assertIn("tesis" if material is TESIS else "libro", resultado["mensaje"])
                self.assertEqual(resultado["datos"], [])
                self.assertEqual(resultado["fuentes"], [])

    def test_no_mezcla_obras_ni_fuentes_de_otro_tipo(self):
        propio = fragmento(LIBRO, "resena_libro")
        ajenos = [fragmento(TESIS, "resumen_tesis"), fragmento(TESIS, "resena_libro"), fragmento(LIBRO, "tesis_completa")]
        resultado, _ = self.consultar([LIBRO], [propio, *ajenos])
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["datos"], [propio])
        self.assertEqual({f["material_id"] for f in resultado["fuentes"]}, {10})

    def test_textos_vacios_o_sin_procedencia_no_son_resumen(self):
        resultado, _ = self.consultar([LIBRO], [fragmento(LIBRO, "resena_libro", texto="  "), fragmento(LIBRO, "resena_libro", material_id=None)])
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["datos"], [])

    def test_ausencia_del_material_usa_tipo_correcto(self):
        for pregunta, etiqueta in (("Resume la tesis Redes", "esa tesis"), ("Resume el libro Redes", "ese libro"), ("Resume Redes", "ese material")):
            with self.subTest(pregunta=pregunta):
                resultado, buscar = self.consultar([], [], pregunta)
                self.assertFalse(resultado["ok"])
                self.assertIn(etiqueta, resultado["mensaje"])
                buscar.assert_not_called()

    def test_palabra_tesis_en_titulo_citado_no_impone_tipo(self):
        resultado, _ = self.consultar([LIBRO], [fragmento(LIBRO, "resena_libro")], "¿De qué trata «Cómo escribir una tesis»?")
        self.assertTrue(resultado["ok"])

    def test_error_tecnico_no_se_disfraza_de_material_ausente(self):
        with patch.object(herramientas, "resolver_material", return_value={"ok": False, "mensaje": "No fue posible consultar PostgreSQL", "datos": []}):
            resultado = herramientas.resumir_material("Redes", "Resume Redes")
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["mensaje"], "No fue posible consultar PostgreSQL")

    def test_error_de_fragmentos_nombra_el_tipo_consultado(self):
        for material in (LIBRO, TESIS):
            with (
                self.subTest(tipo=material["tipo"]),
                patch.object(herramientas, "resolver_material", return_value={"ok": True, "datos": [material]}),
                patch.object(herramientas.rag, "buscar_fragmentos_material", side_effect=RuntimeError("No fue posible consultar los fragmentos de la tesis en PostgreSQL.")),
            ):
                resultado = herramientas.resumir_material("Redes", "Resume «Redes»")
                self.assertFalse(resultado["ok"])
                self.assertIn("tesis" if material is TESIS else "libro", resultado["mensaje"])
                if material is LIBRO:
                    self.assertNotIn("tesis", resultado["mensaje"])


def verificar_lectura_real():
    """Solo SELECT de catálogo/reseñas y embeddings; ninguna herramienta de trámite."""
    with herramientas.conexion() as conn, conn.cursor() as cursor:
        cursor.execute("""
            SELECT m.id, m.titulo FROM public.material m
            WHERE m.tipo = 'libro' AND EXISTS (
                SELECT 1 FROM conocimiento.documentos d
                JOIN conocimiento.fragmentos f ON f.documento_id = d.id
                WHERE d.material_id = m.id AND d.tipo = 'resena_libro'
                  AND length(trim(f.texto)) > 0
            ) ORDER BY length(m.titulo) DESC, m.id LIMIT 1
        """)
        libro = cursor.fetchone()
    if libro is None:
        raise AssertionError("No hay un libro con reseña indexada para la lectura real")
    material_id, titulo = libro
    resultado = herramientas.resumir_material(titulo, f"¿De qué trata el libro «{titulo}»?")
    assert resultado["ok"], resultado["mensaje"]
    assert resultado["datos"] and resultado["fuentes"]
    assert all(f["material_id"] == material_id and f["tipo"] == "resena_libro" for f in resultado["datos"])
    assert all(f["fuente"] for f in resultado["fuentes"])
    print(f"LECTURA REAL PASA: libro {material_id}, «{titulo}»; {len(resultado['datos'])} fragmentos y {len(resultado['fuentes'])} fuentes reales")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true", help="Añade lectura del catálogo y reseña indexada; requiere PostgreSQL y embeddings")
    opciones = parser.parse_args()
    resultado = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ResumenMaterial))
    if not resultado.wasSuccessful():
        sys.exit(1)
    if opciones.real:
        verificar_lectura_real()
