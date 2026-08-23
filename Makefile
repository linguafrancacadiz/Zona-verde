# Zona Verde Cádiz — M0: construcción del dataset de tramos.
#
# El núcleo no necesita dependencias externas: basta Python 3.11+.

PY      ?= python3
AMBITO  ?= casco-historico
CALLEJERO ?= data/fuentes/callejero-osm.geojson
ANEXO     ?= data/anexo/$(AMBITO).csv
ZONAS     ?= data/zonas/$(AMBITO).geojson
PUNTOS    ?= data/verificacion/puntos-control.csv
PSQL_URL  ?= postgres://localhost/zonaverde

.PHONY: ayuda test callejero construir validar db importar limpiar

ayuda:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

test: ## Ejecuta la batería de pruebas del ETL
	cd etl && $(PY) -m unittest discover -s tests -t . -v

callejero: ## Descarga los ejes viales de OSM (respaldo del CDAU)
	./tools/overpass_calles.sh $(CALLEJERO)

construir: ## Anexo + callejero -> GeoJSON de tramos
	cd etl && $(PY) -m zonaverde.construir \
	    --callejero ../$(CALLEJERO) \
	    --anexo ../$(ANEXO) \
	    --salida ../$(ZONAS) \
	    --pendientes ../data/zonas/$(AMBITO).pendientes.csv

validar: ## Criterio de aceptación: cero falsos positivos
	cd etl && $(PY) -m zonaverde.validar --zonas ../$(ZONAS) --puntos ../$(PUNTOS)

db: ## Aplica las migraciones de PostGIS
	for m in db/migrations/*.sql; do echo "-- $$m"; psql "$(PSQL_URL)" -v ON_ERROR_STOP=1 -f "$$m"; done

importar: ## Carga el GeoJSON vigente en PostGIS (requiere GDAL)
	ogr2ogr -f PostgreSQL "PG:$(PSQL_URL)" $(ZONAS) \
	    -nln zonas_import -overwrite -lco GEOMETRY_NAME=geom -t_srs EPSG:4326

limpiar:
	rm -rf etl/**/__pycache__ etl/.pytest_cache data/tmp
