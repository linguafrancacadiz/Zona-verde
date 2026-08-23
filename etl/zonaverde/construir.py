"""Pipeline M0: anexo + callejero → GeoJSON de tramos.

    python -m zonaverde.construir \
        --callejero data/fuentes/callejero.geojson \
        --anexo     data/anexo/casco-historico.csv \
        --salida    data/zonas/casco-historico.geojson \
        --pendientes data/zonas/casco-historico.pendientes.csv

Escala de confianza (la app sólo denuncia a partir de 4):

    1  emparejamiento fallido — no se emite
    2  calle completa, sin recortar, fuente única
    3  tramo recortado automáticamente (anexo + callejero)
    4  contrastado con una segunda fuente o revisado en QGIS
    5  verificado en campo, con foto de la señal

El pipeline nunca emite por encima de 3: subir a 4 o 5 es una decisión humana
que se registra en el commit correspondiente.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .anexo import RegistroTramo, escribir_csv, leer_csv
from .base import Via, buscar_via, cargar_callejero
from .geometria import Polilinea, Punto

VERSION_DATASET = "0.1.0"


@dataclass
class Pendiente:
    registro: RegistroTramo
    motivo: str


def _extremo_a_punto(texto: str, via: Via, vias: dict[str, Via]) -> Punto | None:
    """Resuelve «desde X» a un punto sobre el eje de la vía.

    Admite coordenadas explícitas ``lon,lat`` —útiles para forzar a mano un
    extremo que el callejero no resuelve— y, si no, el cruce con la calle
    transversal nombrada.
    """
    texto = texto.strip()
    if not texto:
        return None

    if "," in texto:
        partes = texto.split(",")
        if len(partes) == 2:
            try:
                return (float(partes[0]), float(partes[1]))
            except ValueError:
                pass

    transversal = buscar_via(vias, texto)
    if transversal is None:
        return None

    mejor: tuple[float, Punto] | None = None
    for eje_via in via.ejes:
        for eje_transversal in transversal.ejes:
            encuentro = eje_via.punto_de_encuentro(eje_transversal)
            if encuentro is None:
                continue
            distancia = eje_via.distancia_a(encuentro)
            if mejor is None or distancia < mejor[0]:
                mejor = (distancia, encuentro)
    return mejor[1] if mejor else None


def construir_tramo(
    registro: RegistroTramo, vias: dict[str, Via]
) -> tuple[Polilinea, int, str] | Pendiente:
    """Devuelve (geometría, confianza, método) o un Pendiente con el motivo."""
    via = buscar_via(vias, registro.via)
    if via is None:
        return Pendiente(registro, "via_no_encontrada_en_callejero")

    eje = via.eje_principal

    if not registro.tiene_tramo:
        return (eje, 2, "calle_completa")

    punto_desde = _extremo_a_punto(registro.desde, via, vias)
    punto_hasta = _extremo_a_punto(registro.hasta, via, vias)

    if punto_desde is None and punto_hasta is None:
        return Pendiente(registro, "extremos_no_resueltos")
    if punto_desde is None or punto_hasta is None:
        return (eje, 2, "un_extremo_sin_resolver")

    fraccion_desde = eje.proyectar(punto_desde).fraccion
    fraccion_hasta = eje.proyectar(punto_hasta).fraccion
    try:
        return (eje.recortar(fraccion_desde, fraccion_hasta), 3, "recorte_por_cruces")
    except ValueError as error:
        return Pendiente(registro, f"recorte_invalido: {error}")


def a_feature(
    registro: RegistroTramo, linea: Polilinea, confianza: int, metodo: str, indice: int
) -> dict:
    identificador = f"{registro.tipo}-{indice:04d}"
    return {
        "type": "Feature",
        "id": identificador,
        "properties": {
            "id": identificador,
            "tipo": registro.tipo,
            "via": registro.via,
            "ambito": registro.ambito,
            "lado": registro.lado,
            "confianza": confianza,
            "metodo": metodo,
            "fuente": registro.fuente,
            "fecha_verificacion": None,
            "foto_senal": None,
            "observaciones": registro.observaciones,
            "longitud_m": round(linea.longitud_m, 1),
            "version_dataset": VERSION_DATASET,
            "generado": date.today().isoformat(),
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [[round(x, 7), round(y, 7)] for x, y in linea.coords],
        },
    }


def construir(ruta_callejero: Path, ruta_anexo: Path) -> tuple[dict, list[Pendiente]]:
    vias = cargar_callejero(ruta_callejero)
    registros = leer_csv(ruta_anexo)

    features: list[dict] = []
    pendientes: list[Pendiente] = []

    for indice, registro in enumerate(registros, start=1):
        resultado = construir_tramo(registro, vias)
        if isinstance(resultado, Pendiente):
            pendientes.append(resultado)
            continue
        linea, confianza, metodo = resultado
        features.append(a_feature(registro, linea, confianza, metodo, indice))

    coleccion = {
        "type": "FeatureCollection",
        "name": ruta_anexo.stem,
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    return coleccion, pendientes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construye el GeoJSON de tramos de zona.")
    parser.add_argument("--callejero", type=Path, required=True)
    parser.add_argument("--anexo", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--pendientes", type=Path, default=None)
    args = parser.parse_args(argv)

    coleccion, pendientes = construir(args.callejero, args.anexo)

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(
        json.dumps(coleccion, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    total = len(coleccion["features"]) + len(pendientes)
    print(f"{len(coleccion['features'])}/{total} tramos construidos → {args.salida}")

    if pendientes:
        destino = args.pendientes or args.salida.with_suffix(".pendientes.csv")
        escribir_csv([p.registro for p in pendientes], destino)
        print(f"{len(pendientes)} pendientes de resolver a mano → {destino}", file=sys.stderr)
        for pendiente in pendientes[:10]:
            print(f"  · {pendiente.registro.via}: {pendiente.motivo}", file=sys.stderr)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
