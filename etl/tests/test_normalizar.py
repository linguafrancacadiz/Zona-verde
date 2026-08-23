import unittest

from zonaverde.normalizar import clave_via, normalizar_via


class TestNormalizarVia(unittest.TestCase):
    def test_quita_tipo_de_via(self):
        self.assertEqual(normalizar_via("C/ Sagasta"), "sagasta")
        self.assertEqual(normalizar_via("CALLE SAGASTA"), "sagasta")
        self.assertEqual(normalizar_via("Calle de Sagasta"), "sagasta")

    def test_quita_articulos_colgantes(self):
        self.assertEqual(normalizar_via("Plaza de la Catedral"), "catedral")
        self.assertEqual(normalizar_via("Cuesta de las Calesas"), "calesas")

    def test_quita_acentos(self):
        self.assertEqual(normalizar_via("Avenida Andalucía"), "andalucia")

    def test_no_vacia_una_via_que_es_su_propio_tipo(self):
        # «Cortadura» es un nombre de vía en Cádiz, no un tipo suelto
        self.assertEqual(normalizar_via("Cortadura"), "cortadura")

    def test_expande_abreviaturas(self):
        self.assertEqual(normalizar_via("Plaza de Sta. María"), "santa maria")


class TestClaveVia(unittest.TestCase):
    def test_equivalencias(self):
        parejas = [
            ("Cuesta de las Calesas", "CUESTA CALESAS"),
            ("Avda. Ana de Viya", "Avenida Ana de Viya"),
            ("C/ San José", "Calle de San Jose"),
            ("Pza. de España", "PLAZA ESPAÑA"),
        ]
        for a, b in parejas:
            with self.subTest(a=a, b=b):
                self.assertEqual(clave_via(a), clave_via(b))

    def test_distingue_vias_distintas(self):
        self.assertNotEqual(clave_via("Calle Ancha"), clave_via("Calle Nueva"))

    def test_cadena_vacia(self):
        self.assertEqual(clave_via(""), "")


if __name__ == "__main__":
    unittest.main()
