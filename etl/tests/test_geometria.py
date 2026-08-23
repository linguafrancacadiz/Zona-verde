import unittest

from zonaverde.geometria import Polilinea, ProyeccionLocal, distancia_m

# Referencia: casco antiguo de Cádiz.
LAT = 36.5300
LON_OESTE, LON_ESTE = -6.3000, -6.2900


def horizontal(lat=LAT, lon1=LON_OESTE, lon2=LON_ESTE):
    return Polilinea([(lon1, lat), (lon2, lat)])


class TestProyeccionLocal(unittest.TestCase):
    def test_ida_y_vuelta(self):
        proyeccion = ProyeccionLocal(LAT, LON_OESTE)
        punto = (-6.2955, 36.5312)
        recuperado = proyeccion.a_grados(proyeccion.a_metros(punto))
        self.assertAlmostEqual(punto[0], recuperado[0], places=9)
        self.assertAlmostEqual(punto[1], recuperado[1], places=9)

    def test_un_grado_de_latitud(self):
        self.assertAlmostEqual(distancia_m((LON_OESTE, 36.53), (LON_OESTE, 36.54)), 1111.32, delta=1)


class TestPolilinea(unittest.TestCase):
    def test_longitud(self):
        # 0,01° de longitud a 36,53° de latitud ≈ 893 m
        self.assertAlmostEqual(horizontal().longitud_m, 893.1, delta=2)

    def test_descarta_vertices_repetidos(self):
        linea = Polilinea([(LON_OESTE, LAT), (LON_OESTE, LAT), (LON_ESTE, LAT)])
        self.assertEqual(len(linea.coords), 2)

    def test_exige_dos_vertices_distintos(self):
        with self.assertRaises(ValueError):
            Polilinea([(LON_OESTE, LAT), (LON_OESTE, LAT)])

    def test_proyectar_punto_desplazado(self):
        # 0,001° de latitud por encima del centro de la línea ≈ 111 m
        proyeccion = horizontal().proyectar((-6.2950, LAT + 0.001))
        self.assertAlmostEqual(proyeccion.distancia_m, 111.1, delta=1)
        self.assertAlmostEqual(proyeccion.fraccion, 0.5, places=3)
        self.assertAlmostEqual(proyeccion.punto[1], LAT, places=6)

    def test_proyectar_mas_alla_del_extremo_se_ancla(self):
        proyeccion = horizontal().proyectar((-6.3100, LAT))
        self.assertEqual(proyeccion.fraccion, 0.0)

    def test_punto_en_fraccion(self):
        punto = horizontal().punto_en(0.25)
        self.assertAlmostEqual(punto[0], -6.2975, places=6)

    def test_recortar(self):
        recorte = horizontal().recortar(0.25, 0.75)
        self.assertAlmostEqual(recorte.longitud_m, 893.1 / 2, delta=2)
        self.assertAlmostEqual(recorte.inicio[0], -6.2975, places=6)
        self.assertAlmostEqual(recorte.fin[0], -6.2925, places=6)

    def test_recortar_conserva_vertices_intermedios(self):
        linea = Polilinea([(LON_OESTE, LAT), (-6.2950, LAT + 0.0005), (LON_ESTE, LAT)])
        self.assertEqual(len(linea.recortar(0.1, 0.9).coords), 3)

    def test_recortar_degenerado_falla(self):
        with self.assertRaises(ValueError):
            horizontal().recortar(0.5, 0.5000001)

    def test_recortar_invierte_fracciones(self):
        recorte = horizontal().recortar(0.75, 0.25)
        self.assertAlmostEqual(recorte.inicio[0], -6.2975, places=6)


class TestCruces(unittest.TestCase):
    def test_interseccion_en_cruz(self):
        vertical = Polilinea([(-6.2950, LAT - 0.002), (-6.2950, LAT + 0.002)])
        cruces = horizontal().intersecciones(vertical)
        self.assertEqual(len(cruces), 1)
        self.assertAlmostEqual(cruces[0][0], -6.2950, places=6)
        self.assertAlmostEqual(cruces[0][1], LAT, places=6)

    def test_paralelas_no_se_cruzan(self):
        self.assertEqual(horizontal().intersecciones(horizontal(lat=LAT + 0.001)), [])

    def test_encuentro_con_hueco_pequeno(self):
        # arranca 0,00005° (≈5,5 m) por encima: dentro de tolerancia
        casi = Polilinea([(-6.2950, LAT + 0.00005), (-6.2950, LAT + 0.002)])
        encuentro = horizontal().punto_de_encuentro(casi, tolerancia_m=12)
        self.assertIsNotNone(encuentro)
        self.assertAlmostEqual(encuentro[0], -6.2950, places=5)

    def test_encuentro_con_hueco_grande_es_none(self):
        # arranca 0,0005° (≈55 m) por encima: calles que no se tocan
        lejos = Polilinea([(-6.2950, LAT + 0.0005), (-6.2950, LAT + 0.002)])
        self.assertIsNone(horizontal().punto_de_encuentro(lejos, tolerancia_m=12))


if __name__ == "__main__":
    unittest.main()
