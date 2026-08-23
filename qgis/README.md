# Revisión visual en QGIS

Sirve para subir tramos de confianza 3 (recorte automático) a 4 (contrastado).
Nunca a 5: eso exige ir a la calle y fotografiar la señal.

1. Abrir QGIS 3.28 o posterior.
2. Consola de Python → `exec(open('.../tools/cargar_qgis.py').read())`.
3. Contrastar cada tramo contra la ortofoto del PNOA y contra el plano
   publicado por Emasa.
4. Corregir la geometría o el CSV del anexo, según de dónde venga el error.
5. Regenerar con `make construir` y commitear el GeoJSON, con el motivo del
   cambio en el mensaje del commit.

La simbología de `zonas.qml` etiqueta cada tramo con `vía (confianza)`, de modo
que los tramos que aún no denuncian se distinguen de un vistazo.
