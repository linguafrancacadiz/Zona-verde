# Zona Verde Cádiz

Herramienta vecinal para documentar y comunicar posibles estacionamientos
indebidos en las zonas verdes —de uso exclusivo para residentes— de Cádiz.

> **La app no determina infracciones.** En Cádiz el título habilitante del
> residente es un **distintivo digital, no físico**, asociado a la matrícula en
> los sistemas de Emasa. Ninguna fotografía puede acreditar si un vehículo está
> autorizado. Lo único que este proyecto hace es levantar evidencia verificable
> —fotografía, ubicación, hora, cadena de custodia— y encauzarla hacia quien sí
> puede comprobarlo. Todos los textos dicen «posible infracción».

Estado actual: **M0 — construcción del dataset de tramos de zona verde.**
El resto de la aplicación (captura, ANPR, entrega) depende de que esta capa sea
correcta, así que es lo primero.

## Puesta en marcha

```bash
make test          # 48 pruebas, sin dependencias externas
make callejero     # descarga los ejes viales de OSM (respaldo del CDAU)
make construir     # anexo + callejero → data/zonas/<ambito>.geojson
make validar       # criterio de aceptación: cero falsos positivos
```

El núcleo del ETL funciona con la biblioteca estándar de Python 3.11+.
`pdfplumber` sólo hace falta para extraer el anexo directamente de un PDF.

## Estructura

```
data/anexo/         listados del anexo de la ordenanza, en CSV — se revisan a mano
data/fuentes/       descargas voluminosas (CDAU, OSM). Fuera de git.
data/zonas/         EL DATASET. GeoJSON versionado en git, revisado por PR.
data/verificacion/  puntos de control con tipo conocido, para el criterio de aceptación
db/migrations/      esquema PostGIS y función de clasificación en tiempo de ejecución
etl/zonaverde/      pipeline de construcción y clasificador de referencia
qgis/, tools/       revisión visual y descarga de fuentes
docs/               método de M0 y solicitud de transparencia
```

## Por qué el dataset vive en git

Toda la credibilidad del proyecto descansa en no acusar a nadie por error. Con
el GeoJSON versionado, cada cambio en lo que se considera zona verde es un diff
auditable con su motivo en el mensaje del commit, y cualquier vecino puede abrir
una incidencia señalando un tramo mal clasificado.

## Escala de confianza

La app **sólo denuncia a partir de 4**. El pipeline nunca emite por encima de 3:
subir un tramo a 4 o a 5 es una decisión humana que queda registrada.

| | Significado |
|---|---|
| 1 | Emparejamiento fallido — no se emite |
| 2 | Calle completa, sin recortar, fuente única |
| 3 | Tramo recortado automáticamente (anexo + callejero) |
| 4 | Contrastado con una segunda fuente o revisado en QGIS |
| 5 | Verificado en campo, con fotografía de la señal |

## El error es asimétrico

Clasificar como verde un tramo que no lo es produce una denuncia injusta.
Clasificar como no verde un tramo verde sólo produce un reporte perdido. No son
equivalentes. Ante la duda —precisión de GPS pobre, dos candidatos de tipo
distinto igual de cerca, tramo sin verificar— la respuesta correcta siempre es
**no reportable**, y así está escrito tanto en `etl/zonaverde/clasificacion.py`
como en `db/migrations/003_clasificar.sql`.

`make validar` falla si un solo punto de control fuera de zona verde se
clasifica como reportable. Tolera hasta un 15 % de reportes perdidos.

## Documentación

- [`docs/M0-metodo.md`](docs/M0-metodo.md) — de dónde sale la geometría y cómo se verifica
- [`docs/s1/`](docs/s1/) — solicitud de acceso a la información pública y correo a Emasa
