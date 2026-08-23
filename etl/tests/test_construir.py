import json
import tempfile
import unittest
from pathlib import Path

from zonaverde.anexo import RegistroTramo, escribir_csv, leer_csv
from zonaverde.base import cargar_callejero, encadenar
from zonaverde.construir import construir, construir_tramo
from zonaverde.geometria import Polilinea

LAT = 36.5300


def feature(nombre, coords):
    return {
        "type": "Feature",
        "properties": {"name": nombre},
        "geometry": {"type": "LineString", "coordinates": [list(c) for c in coords]},
    }


CALLEJERO = {
    "type": "FeatureCollection",
    "features": [
        # Calle Ancha, partida en dos piezas como en OSM/CDAU
        feature("Calle Ancha", [(-6.3000, LAT), (-6.2950, LAT)]),
        feature("Calle Ancha", [(-6.2950, LAT), (-6.2900, LAT)]),
        feature("Calle San José", [(-6.2970, LAT - 0.002), (-6.2970, LAT + 0.002)]),
        feature("Calle Sagasta", [(-6.2930, LAT - 0.002), (-6.2930, LAT + 0.002)]),
    ],
}


class TestEncadenar(unittest.TestCase):
    def test_une_piezas_contiguas(self):
        piezas = [[(-6.3000, LAT), (-6.2950, LAT)], [(-6.2950, LAT), (-6.2900, LAT)]]
        unidas = encadenar(piezas)
        self.assertEqual(len(unidas), 1)
        self.assertAlmostEqual(unidas[0].longitud_m, 893.1, delta=2)

    def test_une_piezas_invertidas(self):
        piezas = [[(-6.2950, LAT), (-6.3000, LAT)], [(-6.2950, LAT), (-6.2900, LAT)]]
        self.assertEqual(len(encadenar(piezas)), 1)

    def test_no_une_piezas_separadas(self):
        piezas = [[(-6.3000, LAT), (-6.2950, LAT)], [(-6.2800, LAT), (-6.2700, LAT)]]
        self.assertEqual(len(encadenar(piezas)), 2)


class TestConstruirTramo(unittest.TestCase):
    def setUp(self):
        self.directorio = tempfile.TemporaryDirectory()
        self.ruta = Path(self.directorio.name) / "callejero.geojson"
        self.ruta.write_text(json.dumps(CALLEJERO), encoding="utf-8")
        self.vias = cargar_callejero(self.ruta)

    def tearDown(self):
        self.directorio.cleanup()

    def test_callejero_encadena_la_calle_partida(self):
        self.assertIn("ancha", self.vias)
        self.assertAlmostEqual(self.vias["ancha"].eje_principal.longitud_m, 893.1, delta=2)

    def test_recorta_entre_dos_transversales(self):
        registro = RegistroTramo(
            via="Calle Ancha", tipo="verde", desde="Calle San José", hasta="Sagasta"
        )
        linea, confianza, metodo = construir_tramo(registro, self.vias)
        self.assertIsInstance(linea, Polilinea)
        self.assertEqual(metodo, "recorte_por_cruces")
        self.assertEqual(confianza, 3)
        # de -6,2970 a -6,2930 ≈ 357 m
        self.assertAlmostEqual(linea.longitud_m, 357.2, delta=3)

    def test_calle_completa_sin_tramo(self):
        registro = RegistroTramo(via="Calle Ancha", tipo="verde")
        linea, confianza, metodo = construir_tramo(registro, self.vias)
        self.assertEqual(metodo, "calle_completa")
        self.assertEqual(confianza, 2)

    def test_via_desconocida_queda_pendiente(self):
        registro = RegistroTramo(via="Calle Inexistente", tipo="verde")
        resultado = construir_tramo(registro, self.vias)
        self.assertEqual(resultado.motivo, "via_no_encontrada_en_callejero")

    def test_extremos_por_coordenadas(self):
        registro = RegistroTramo(
            via="Calle Ancha", tipo="verde", desde="-6.2970,36.53", hasta="-6.2930,36.53"
        )
        linea, _, metodo = construir_tramo(registro, self.vias)
        self.assertEqual(metodo, "recorte_por_cruces")
        self.assertAlmostEqual(linea.longitud_m, 357.2, delta=3)

    def test_pipeline_completo(self):
        anexo = Path(self.directorio.name) / "anexo.csv"
        escribir_csv(
            [
                RegistroTramo(via="Calle Ancha", tipo="verde", desde="San José", hasta="Sagasta"),
                RegistroTramo(via="Calle Fantasma", tipo="verde"),
            ],
            anexo,
        )
        coleccion, pendientes = construir(self.ruta, anexo)
        self.assertEqual(len(coleccion["features"]), 1)
        self.assertEqual(len(pendientes), 1)
        props = coleccion["features"][0]["properties"]
        self.assertEqual(props["tipo"], "verde")
        self.assertEqual(props["confianza"], 3)
        self.assertIsNone(props["fecha_verificacion"])


class TestAnexoCsv(unittest.TestCase):
    def test_ida_y_vuelta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "a.csv"
            original = [RegistroTramo(via="C/ Ancha", tipo="verde", ambito="casco")]
            escribir_csv(original, ruta)
            self.assertEqual(leer_csv(ruta)[0].via, "C/ Ancha")

    def test_tipo_invalido(self):
        with self.assertRaises(ValueError):
            RegistroTramo(via="X", tipo="morada")


if __name__ == "__main__":
    unittest.main()
