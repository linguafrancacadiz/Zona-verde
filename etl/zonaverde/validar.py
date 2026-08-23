"""Criterio de aceptación de M0.

Clasifica una lista de puntos de control con tipo conocido y comprueba la
única condición que no admite negociación: **ningún punto que no esté en zona
verde puede clasificarse como reportable**. Los falsos negativos (zona verde
que no se detecta) sólo cuestan reportes perdidos y se toleran hasta un umbral.

    python -m zonaverde.validar \
        --zonas data/zonas/casco-historico.geojson \
        --puntos data/verificacion/puntos-control.csv

Sale con código 1 si el dataset no supera el criterio: se puede enganchar en CI.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from .clasificacion import cargar_tramos, clasificar

FALSOS_NEGATIVOS_ADMISIBLES = 0.15


@dataclass
class PuntoControl:
    lon: float
    lat: float
    precision_m: float
    tipo_esperado: str
    nota: str = ""


def leer_puntos(ruta: Path | str) -> list[PuntoControl]:
    puntos = []
    with Path(ruta).open(encoding="utf-8-sig", newline="") as fichero:
        for fila in csv.DictReader(fichero):
            if not (fila.get("lon") or "").strip():
                continue
            puntos.append(
                PuntoControl(
                    lon=float(fila["lon"]),
                    lat=float(fila["lat"]),
                    precision_m=float(fila.get("precision_m") or 10),
                    tipo_esperado=(fila.get("tipo_esperado") or "").strip().lower(),
                    nota=(fila.get("nota") or "").strip(),
                )
            )
    return puntos


def validar(ruta_zonas: Path, ruta_puntos: Path) -> tuple[bool, str]:
    tramos = cargar_tramos(ruta_zonas)
    puntos = leer_puntos(ruta_puntos)
    if not puntos:
        return False, "no hay puntos de control: el dataset no está validado"

    falsos_positivos: list[tuple[PuntoControl, str]] = []
    falsos_negativos: list[PuntoControl] = []
    aciertos = 0
    verdes = 0

    for punto in puntos:
        resultado = clasificar((punto.lon, punto.lat), punto.precision_m, tramos)
        esperaba_verde = punto.tipo_esperado == "verde"
        verdes += esperaba_verde

        if resultado.reportable and not esperaba_verde:
            falsos_positivos.append((punto, resultado.via or "?"))
        elif not resultado.reportable and esperaba_verde:
            falsos_negativos.append(punto)
        else:
            aciertos += 1

    lineas = [
        f"puntos de control      : {len(puntos)} ({verdes} en zona verde)",
        f"aciertos               : {aciertos}",
        f"falsos NEGATIVOS       : {len(falsos_negativos)}  (reportes perdidos, tolerables)",
        f"falsos POSITIVOS       : {len(falsos_positivos)}  (denuncias injustas, inadmisibles)",
    ]

    for punto, via in falsos_positivos:
        lineas.append(f"  ✗ ({punto.lon}, {punto.lat}) esperado={punto.tipo_esperado} "
                      f"→ reportado como verde en «{via}» — {punto.nota}")

    tasa_fn = len(falsos_negativos) / verdes if verdes else 0.0
    lineas.append(f"tasa de falsos negativos: {tasa_fn:.0%} (máximo {FALSOS_NEGATIVOS_ADMISIBLES:.0%})")

    correcto = not falsos_positivos and tasa_fn <= FALSOS_NEGATIVOS_ADMISIBLES
    lineas.append("RESULTADO: " + ("APTO" if correcto else "NO APTO"))
    return correcto, "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida el dataset de zonas.")
    parser.add_argument("--zonas", type=Path, required=True)
    parser.add_argument("--puntos", type=Path, required=True)
    args = parser.parse_args(argv)

    correcto, informe = validar(args.zonas, args.puntos)
    print(informe)
    return 0 if correcto else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
