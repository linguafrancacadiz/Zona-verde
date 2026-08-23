# M0 — Obtención y verificación de la geometría

## Por qué tramos y no polígonos

El estacionamiento es **lineal**, pegado al bordillo, no una superficie. Un
polígono dibujado sobre una calle de seis metros del casco antiguo se solapa con
los edificios, con la calle paralela y a menudo con la zona azul del cruce.

Cada tramo es una `LineString` y la clasificación se hace por **cercanía**, no
por contención:

```sql
SELECT id, tipo, via, ST_Distance(geom, $punto) AS dist_m
FROM   zonas
WHERE  version_id = $version
  AND  ST_DWithin(geom, $punto, $precision_gps + 15)
ORDER  BY dist_m LIMIT 3;
```

Consecuencias de diseño:

- **El GPS del casco antiguo es malo.** Calles estrechas, edificios altos,
  multitrayecto: entre 10 y 30 m de error. Una consulta por contención convierte
  ese error en una clasificación silenciosamente equivocada; la cercanía más el
  radio de precisión declarado lo convierte en una ambigüedad explícita.
- **Ambigüedad → decide la persona.** Si los dos primeros candidatos son de tipo
  distinto y la diferencia de distancia es menor que el margen, la app pregunta
  «¿en qué calle está el vehículo?» con dos o tres botones.
- **Las exclusiones son una capa por encima.** Vados, carga y descarga, plazas
  PMR, reservas de obra, motos y contenedores se solapan a propósito con el
  tramo verde que los contiene, y ganan siempre.

## Las cinco vías de obtención

### S1 · Solicitud de acceso a la información pública — lanzar primero
Ver [`docs/s1/`](s1/). No cuesta nada, corre en paralelo durante un mes y tiene
tres desenlaces, los tres útiles: llega la capa y M0 se reduce a importarla;
llega un PDF y estamos en S5; o no llega nada, y eso mismo es un dato del
proyecto y deja constancia de que se pidió por el cauce correcto.

### S2 · Anexo de la ordenanza + CDAU — la de mayor fidelidad bajo nuestro control
El anexo de la Ordenanza de Estacionamiento Regulado lista los viales por
ámbito. Se emparejan contra el **Callejero Digital de Andalucía Unificado**,
autoridad para Andalucía, que publica los ejes de vial con códigos estables.

```
anexo PDF ──python -m zonaverde.anexo extraer──▶ CSV  (SE REVISA A MANO)
CDAU (SHP) ──ogr2ogr -f GeoJSON -t_srs EPSG:4326──▶ callejero.geojson
                              │
                    make construir
                              │
              data/zonas/<ambito>.geojson  +  <ambito>.pendientes.csv
```

Los extremos «desde X hasta Y» se resuelven por **cruce con la calle
transversal**. Cuando el callejero no lo resuelve, se puede forzar el extremo
escribiendo `lon,lat` directamente en la columna `desde` o `hasta` del CSV.

Espera entre un 70 y un 85 % de emparejamiento automático. El resto sale en
`pendientes.csv`: esa es la cola de trabajo manual.

### S3 · OSM como geometría base
`./tools/overpass_calles.sh`. Sirve de respaldo mientras no esté el CDAU, y
devolver a OSM los tramos verificados es un bien público — pero OSM no puede ser
la fuente única de un tramo que genere denuncias: cualquiera puede editarlo.
El esquema `parking:condition:*` está obsoleto; el vigente es
`parking:right:restriction=residents`.

### S4 · Trabajo de campo — «modo cartógrafo»
Una segunda pantalla en la app: recorrer la calle, marcar inicio y fin de tramo,
fotografiar la señal vertical y la marca vial. Es la **única** fuente que
produce confianza 5 y la única que captura las exclusiones. Dos personas cubren
el casco histórico en unas cuantas tardes.

### S5 · Georreferenciar el plano publicado de Emasa
QGIS → Georreferenciador → EPSG:25830 → digitalizar encima. Vale para un primer
vistazo, no para denunciar. Su uso correcto es de **capa de contraste**: donde
S2 y S5 discrepen, ese tramo encabeza la cola de verificación en campo.

**Combinación:** S1 desde el día uno · v0 con S2 (S3 de respaldo) · verificación
con S4 · S5 como contraste. Y **por ámbito**: cerrar el casco histórico entero
antes de tocar el Paseo Marítimo.

## Criterio de aceptación

```bash
make validar
```

Sobre unos 60 puntos de control tomados en campo con tipo conocido:

- **Cero falsos positivos.** Un solo punto fuera de zona verde clasificado como
  reportable tumba el dataset. No es negociable.
- Hasta un 15 % de falsos negativos, que sólo cuestan reportes perdidos.

Devuelve código de salida 1 si no se cumple, de modo que se puede enganchar en
integración continua.

## Mantenimiento

Las zonas cambian. Un repaso trimestral sobre el 10 % de tramos con
`fecha_verificacion` más antigua evita que el dataset se pudra en silencio.
Las versiones no se modifican en sitio: se publica una nueva y cada reporte
guarda contra qué versión se validó.
