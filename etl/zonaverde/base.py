"""Carga del callejero base (ejes de vial) desde GeoJSON.

Fuentes admitidas, en orden de preferencia:

1. CDAU — Callejero Digital de Andalucía Unificado (autoridad para Andalucía).
   Convertir a GeoJSON con:
       ogr2ogr -f GeoJSON -t_srs EPSG:4326 data/fuentes/cdau.geojson <shp>
2. OSM vía Overpass — ``tools/overpass_calles.sh``.

Ambas fuentes parten cada calle en múltiples tramos (uno por manzana). Para
poder recortar «desde X hasta Y» hay que reconstruir el eje completo, de ahí
``encadenar``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from .geometria import Polilinea, Punto, distancia_m
from .normalizar import clave_via, normalizar_via

# Campos donde cada fuente guarda el nombre de la vía.
CAMPOS_NOMBRE = ("name", "NOMBRE", "nombre", "NOMBRE_VIA", "nombre_via", "TIP_NOM", "rotulo")


@dataclass
class Via:
    """Una vía del callejero, con sus ejes ya encadenados."""

    nombre: str
    clave: str
    ejes: list[Polilinea] = field(default_factory=list)

    @property
    def eje_principal(self) -> Polilinea:
        return max(self.ejes, key=lambda e: e.longitud_m)


def _nombre_de(propiedades: dict) -> str | None:
    for campo in CAMPOS_NOMBRE:
        valor = propiedades.get(campo)
        if valor:
            return str(valor)
    return None


def _lineas_de_geometria(geom: dict) -> list[list[Punto]]:
    if not geom:
        return []
    tipo = geom.get("type")
    if tipo == "LineString":
        return [[(c[0], c[1]) for c in geom["coordinates"]]]
    if tipo == "MultiLineString":
        return [[(c[0], c[1]) for c in parte] for parte in geom["coordinates"]]
    return []


def encadenar(lineas: Sequence[Sequence[Punto]], tolerancia_m: float = 1.5) -> list[Polilinea]:
    """Une tramos sueltos que comparten extremo en polilíneas continuas.

    Una calle puede quedar en varias piezas si está realmente discontinua
    (interrumpida por una plaza, por ejemplo); por eso devuelve una lista.
    """
    pendientes = [list(l) for l in lineas if len(l) >= 2]
    resultado: list[Polilinea] = []

    while pendientes:
        actual = pendientes.pop(0)
        cambiado = True
        while cambiado:
            cambiado = False
            for i, candidato in enumerate(pendientes):
                if distancia_m(actual[-1], candidato[0]) <= tolerancia_m:
                    actual = actual + candidato[1:]
                elif distancia_m(actual[-1], candidato[-1]) <= tolerancia_m:
                    actual = actual + list(reversed(candidato))[1:]
                elif distancia_m(actual[0], candidato[-1]) <= tolerancia_m:
                    actual = candidato + actual[1:]
                elif distancia_m(actual[0], candidato[0]) <= tolerancia_m:
                    actual = list(reversed(candidato)) + actual[1:]
                else:
                    continue
                pendientes.pop(i)
                cambiado = True
                break
        try:
            resultado.append(Polilinea(actual))
        except ValueError:
            continue

    return resultado


def cargar_callejero(ruta: Path | str) -> dict[str, Via]:
    """Lee un GeoJSON de ejes viales y devuelve las vías indexadas por clave."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    agrupadas: dict[str, tuple[str, list[list[Punto]]]] = {}

    for elemento in datos.get("features", []):
        nombre = _nombre_de(elemento.get("properties") or {})
        if not nombre:
            continue
        clave = clave_via(nombre)
        if not clave:
            continue
        nombre_legible, lineas = agrupadas.setdefault(clave, (normalizar_via(nombre), []))
        lineas.extend(_lineas_de_geometria(elemento.get("geometry") or {}))

    vias: dict[str, Via] = {}
    for clave, (nombre, lineas) in agrupadas.items():
        ejes = encadenar(lineas)
        if ejes:
            vias[clave] = Via(nombre=nombre, clave=clave, ejes=ejes)
    return vias


def buscar_via(vias: dict[str, Via], nombre: str) -> Via | None:
    """Busca por clave exacta y, si falla, por contención de clave.

    La contención resuelve casos como «Sagasta» en el anexo frente a
    «Calle Práxedes Mateo Sagasta» en el callejero, pero es ambigua por
    naturaleza: sólo se acepta cuando hay un único candidato.
    """
    clave = clave_via(nombre)
    if not clave:
        return None
    if clave in vias:
        return vias[clave]

    candidatos = [v for k, v in vias.items() if clave in k or k in clave]
    return candidatos[0] if len(candidatos) == 1 else None
