#!/usr/bin/env bash
# Descarga los ejes viales de Cádiz desde OpenStreetMap vía Overpass.
#
# Fuente de RESPALDO: la autoridad para Andalucía es el CDAU
# (https://www.callejerodeandalucia.es/descargas/). Usar OSM sólo mientras
# no se disponga del CDAU, y nunca como única fuente de un tramo que vaya a
# generar denuncias.
#
#   ./tools/overpass_calles.sh [salida.geojson]

set -euo pipefail

SALIDA="${1:-data/fuentes/callejero-osm.geojson}"
ENDPOINT="${OVERPASS_URL:-https://overpass-api.de/api/interpreter}"

CONSULTA='
[out:json][timeout:180];
area["name"="Cádiz"]["admin_level"="8"]->.ciudad;
way(area.ciudad)["highway"~"^(residential|living_street|unclassified|tertiary|tertiary_link|secondary|secondary_link|primary|primary_link|pedestrian|service)$"]["name"];
out geom;
'

echo "Consultando ${ENDPOINT}…" >&2
mkdir -p "$(dirname "$SALIDA")"
RESPUESTA="$(mktemp)"
trap 'rm -f "$RESPUESTA"' EXIT

curl -sS --fail --max-time 240 -G "$ENDPOINT" --data-urlencode "data=${CONSULTA}" > "$RESPUESTA"

python3 - "$RESPUESTA" "$SALIDA" <<'PYEOF'
import json
import sys

crudo = json.load(open(sys.argv[1], encoding="utf-8"))
features = []
for elemento in crudo.get("elements", []):
    geometria = elemento.get("geometry") or []
    if elemento.get("type") != "way" or len(geometria) < 2:
        continue
    etiquetas = elemento.get("tags") or {}
    features.append({
        "type": "Feature",
        "id": elemento["id"],
        "properties": {
            "name": etiquetas.get("name"),
            "highway": etiquetas.get("highway"),
            "osm_id": elemento["id"],
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [[p["lon"], p["lat"]] for p in geometria],
        },
    })

coleccion = {"type": "FeatureCollection", "features": features}
with open(sys.argv[2], "w", encoding="utf-8") as fichero:
    json.dump(coleccion, fichero, ensure_ascii=False)
print(f"{len(features)} ejes viales → {sys.argv[2]}", file=sys.stderr)
PYEOF
