import unittest

from zonaverde.clasificacion import Tramo, clasificar
from zonaverde.geometria import Polilinea

LAT_VERDE = 36.5300
LAT_AZUL = 36.5302  # ≈22 m al norte
LON_1, LON_2 = -6.3000, -6.2900


def tramo(tipo, lat, confianza=5, via=None, lon1=LON_1, lon2=LON_2):
    return Tramo(
        id=f"{tipo}-{lat}",
        tipo=tipo,
        via=via or f"Calle {tipo}",
        ambito="casco histórico",
        confianza=confianza,
        linea=Polilinea([(lon1, lat), (lon2, lat)]),
    )


class TestClasificar(unittest.TestCase):
    def setUp(self):
        self.tramos = [tramo("verde", LAT_VERDE), tramo("azul", LAT_AZUL)]

    def test_punto_claramente_en_verde(self):
        # ≈5,6 m del eje verde, ≈16,7 m del azul
        resultado = clasificar((-6.2950, LAT_VERDE + 0.00005), 5, self.tramos)
        self.assertTrue(resultado.reportable)
        self.assertEqual(resultado.motivo, "en_zona_verde")
        self.assertEqual(resultado.tipo, "verde")

    def test_punto_equidistante_es_ambiguo(self):
        # a medio camino entre ambas: la persona decide
        resultado = clasificar((-6.2950, (LAT_VERDE + LAT_AZUL) / 2), 5, self.tramos)
        self.assertFalse(resultado.reportable)
        self.assertTrue(resultado.ambiguo)
        self.assertEqual(len(resultado.para_app()["candidatos"]), 2)

    def test_punto_en_azul_no_es_reportable(self):
        resultado = clasificar((-6.2950, LAT_AZUL + 0.00005), 5, self.tramos)
        self.assertFalse(resultado.reportable)
        self.assertEqual(resultado.motivo, "no_es_zona_verde")

    def test_fuera_de_zona_regulada(self):
        resultado = clasificar((-6.2950, 36.5400), 5, self.tramos)
        self.assertFalse(resultado.reportable)
        self.assertEqual(resultado.motivo, "fuera_de_zona_regulada")

    def test_precision_insuficiente(self):
        resultado = clasificar((-6.2950, LAT_VERDE), 60, self.tramos)
        self.assertFalse(resultado.reportable)
        self.assertEqual(resultado.motivo, "precision_insuficiente")

    def test_tramo_sin_verificar_no_se_denuncia(self):
        tramos = [tramo("verde", LAT_VERDE, confianza=3)]
        resultado = clasificar((-6.2950, LAT_VERDE), 5, tramos)
        self.assertFalse(resultado.reportable)
        self.assertEqual(resultado.motivo, "tramo_sin_verificar")

    def test_exclusion_gana_al_tramo_verde_que_la_contiene(self):
        # un vado dentro del tramo verde, solapado a propósito
        vado = tramo("excluida", LAT_VERDE, via="Vado nº 12", lon1=-6.2960, lon2=-6.2940)
        resultado = clasificar((-6.2950, LAT_VERDE), 5, [*self.tramos, vado])
        self.assertFalse(resultado.reportable)
        self.assertEqual(resultado.motivo, "tramo_excluido")

    def test_exclusion_no_bloquea_el_resto_de_la_calle(self):
        vado = tramo("excluida", LAT_VERDE, via="Vado nº 12", lon1=-6.2960, lon2=-6.2940)
        # muy lejos del vado, en el mismo tramo verde
        resultado = clasificar((-6.2910, LAT_VERDE), 5, [*self.tramos, vado])
        self.assertTrue(resultado.reportable)

    def test_precision_pobre_amplia_el_radio_y_provoca_ambiguedad(self):
        # con 5 m de precisión el punto es claramente verde; con 30 m, no
        punto = (-6.2950, LAT_VERDE + 0.00005)
        self.assertTrue(clasificar(punto, 5, self.tramos).reportable)
        resultado = clasificar(punto, 30, self.tramos)
        self.assertTrue(resultado.reportable or resultado.ambiguo)


if __name__ == "__main__":
    unittest.main()
