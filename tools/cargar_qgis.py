"""Carga las capas del proyecto en QGIS con su simbología.

En QGIS: Complementos → Consola de Python → ejecutar este fichero, o bien
    exec(open('/ruta/a/Zona-verde/tools/cargar_qgis.py').read())

Pensado para la revisión visual de M0: contrastar los tramos generados contra
una ortofoto y el plano de Emasa antes de subir ningún tramo a confianza 4.
"""

from pathlib import Path

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer  # type: ignore

RAIZ = Path(__file__).resolve().parent.parent
ESTILO = RAIZ / "qgis" / "zonas.qml"

ORTOFOTO_PNOA = (
    "type=xyz&url=https://www.ign.es/wmts/pnoa-ma?"
    "service%3DWMTS%26request%3DGetTile%26version%3D1.0.0%26layer%3DOI.OrthoimageCoverage"
    "%26style%3Ddefault%26tilematrixset%3DGoogleMapsCompatible%26format%3Dimage/jpeg"
    "%26tilematrix%3D{z}%26tilerow%3D{y}%26tilecol%3D{x}&zmax=19&zmin=0"
)


def cargar() -> None:
    proyecto = QgsProject.instance()

    orto = QgsRasterLayer(ORTOFOTO_PNOA, "PNOA máxima actualidad", "wms")
    if orto.isValid():
        proyecto.addMapLayer(orto)

    for ruta in sorted((RAIZ / "data" / "zonas").glob("*.geojson")):
        capa = QgsVectorLayer(str(ruta), f"zonas · {ruta.stem}", "ogr")
        if not capa.isValid():
            print(f"no se pudo cargar {ruta}")
            continue
        if ESTILO.exists():
            capa.loadNamedStyle(str(ESTILO))
        proyecto.addMapLayer(capa)

    for ruta in sorted((RAIZ / "data" / "fuentes").glob("callejero*.geojson")):
        capa = QgsVectorLayer(str(ruta), f"callejero · {ruta.stem}", "ogr")
        if capa.isValid():
            proyecto.addMapLayer(capa)

    print("capas cargadas")


cargar()
