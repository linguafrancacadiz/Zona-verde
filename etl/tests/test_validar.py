import json
import tempfile
import unittest
from pathlib import Path

from zonaverde.validar import validar

LAT_VERDE = 36.5300
LAT_AZUL = 36.5302


def tramo(tipo, lat, confianza=5, fecha="2026-03-14"):
    return {
        "type": "Feature",
        "properties": {
            "id": f"{tipo}-1",
            "tipo": tipo,
            "via": f"Calle {tipo}",
            "ambito": "casco histórico",
            "confianza": confianza,
            "fecha_verificacion": fecha,
        },
        "geometry": {"type": "LineString", "coordinates": [[-6.3000, lat], [-6.2900, lat]]},
    }


ZONAS = {
    "type": "FeatureCollection",
    "features": [tramo("verde", LAT_VERDE), tramo("azul", LAT_AZUL)],
}


class TestValidar(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.zonas = Path(self.carpeta.name) / "zonas.geojson"
        self.zonas.write_text(json.dumps(ZONAS), encoding="utf-8")
        self.puntos = Path(self.carpeta.name) / "puntos.csv"

    def tearDown(self):
        self.carpeta.cleanup()

    def escribir_puntos(self, filas):
        contenido = "lon,lat,precision_m,tipo_esperado,nota\n" + "\n".join(filas)
        self.puntos.write_text(contenido, encoding="utf-8")

    def test_dataset_correcto_es_apto(self):
        self.escribir_puntos([
            f"-6.2950,{LAT_VERDE + 0.00005},5,verde,en verde",
            f"-6.2950,{LAT_AZUL + 0.00005},5,azul,en azul",
            "-6.2950,36.5400,5,ninguna,sin regular",
        ])
        correcto, informe = validar(self.zonas, self.puntos)
        self.assertTrue(correcto, informe)
        self.assertIn("APTO", informe)

    def test_un_solo_falso_positivo_tumba_el_dataset(self):
        # se etiqueta como azul un punto que cae sobre el eje verde:
        # el dataset está mal y la validación tiene que detectarlo
        self.escribir_puntos([
            f"-6.2950,{LAT_VERDE},5,azul,mal clasificado a propósito",
            f"-6.2950,{LAT_VERDE + 0.00005},5,verde,en verde",
        ])
        correcto, informe = validar(self.zonas, self.puntos)
        self.assertFalse(correcto)
        self.assertIn("NO APTO", informe)
        self.assertIn("falsos POSITIVOS       : 1", informe)

    def test_sin_puntos_de_control_no_hay_validacion(self):
        self.escribir_puntos([])
        correcto, informe = validar(self.zonas, self.puntos)
        self.assertFalse(correcto)
        self.assertIn("no está validado", informe)

    def test_falsos_negativos_toleran_hasta_el_umbral(self):
        # 8 puntos verdes, uno de ellos fuera del alcance del dataset → 12,5 %
        filas = [f"-6.29{50 + i},{LAT_VERDE + 0.00005},5,verde,ok" for i in range(7)]
        filas.append(f"-6.2950,{LAT_VERDE + 0.0010},5,verde,demasiado lejos del eje")
        self.escribir_puntos(filas)
        correcto, informe = validar(self.zonas, self.puntos)
        self.assertTrue(correcto, informe)
        self.assertIn("falsos NEGATIVOS       : 1", informe)


if __name__ == "__main__":
    unittest.main()
