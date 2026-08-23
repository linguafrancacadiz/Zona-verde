"""Lectura del anexo de la Ordenanza de Estacionamiento Regulado.

Dos entradas posibles:

- **CSV** (``leer_csv``): formato canónico del proyecto. Es lo que se versiona
  en git y lo que se corrige a mano.
- **PDF** (``leer_pdf``): extracción del anexo publicado en el BOP. Requiere
  ``pdfplumber``.

  ⚠️ El patrón de ``PATRON_TRAMO`` está escrito a ciegas: no se ha calibrado
  todavía contra el anexo real. Antes de fiarse de la extracción, ejecutar
  ``python -m zonaverde.anexo volcar <pdf>`` para ver el texto tal cual sale y
  ajustar el patrón. El CSV resultante SIEMPRE se revisa a mano.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

TIPOS_VALIDOS = ("verde", "naranja", "azul", "excluida")

PATRON_TRAMO = re.compile(
    r"^(?P<via>.+?)\s+(?:desde|entre)\s+(?P<desde>.+?)\s+(?:hasta|y)\s+(?P<hasta>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass
class RegistroTramo:
    """Una fila del anexo: un tramo de vía con un tipo de zona."""

    via: str
    tipo: str
    ambito: str = ""
    desde: str = ""
    hasta: str = ""
    lado: str = "ambos"  # ambos | pares | impares
    observaciones: str = ""
    fuente: str = "ordenanza"

    def __post_init__(self) -> None:
        self.tipo = self.tipo.strip().lower()
        if self.tipo not in TIPOS_VALIDOS:
            raise ValueError(f"tipo de zona no válido: {self.tipo!r} (vía {self.via!r})")
        self.lado = (self.lado or "ambos").strip().lower()
        if self.lado not in ("ambos", "pares", "impares"):
            raise ValueError(f"lado no válido: {self.lado!r} (vía {self.via!r})")

    @property
    def tiene_tramo(self) -> bool:
        return bool(self.desde.strip() and self.hasta.strip())


CAMPOS_CSV = [f.name for f in fields(RegistroTramo)]


def leer_csv(ruta: Path | str) -> list[RegistroTramo]:
    registros: list[RegistroTramo] = []
    with Path(ruta).open(encoding="utf-8-sig", newline="") as fichero:
        for numero, fila in enumerate(csv.DictReader(fichero), start=2):
            datos = {k: (fila.get(k) or "").strip() for k in CAMPOS_CSV if k in fila}
            if not datos.get("via"):
                continue
            try:
                registros.append(RegistroTramo(**datos))
            except (TypeError, ValueError) as error:
                raise ValueError(f"{ruta}:{numero}: {error}") from error
    return registros


def escribir_csv(registros: list[RegistroTramo], ruta: Path | str) -> None:
    with Path(ruta).open("w", encoding="utf-8", newline="") as fichero:
        escritor = csv.DictWriter(fichero, fieldnames=CAMPOS_CSV)
        escritor.writeheader()
        for registro in registros:
            escritor.writerow(asdict(registro))


def volcar_texto(ruta_pdf: Path | str) -> str:
    """Texto plano del PDF, para calibrar el patrón de extracción."""
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError as error:  # pragma: no cover
        raise SystemExit(
            "Falta pdfplumber. Instalar con: pip install -r etl/requirements.txt"
        ) from error

    partes = []
    with pdfplumber.open(str(ruta_pdf)) as pdf:
        for numero, pagina in enumerate(pdf.pages, start=1):
            partes.append(f"\n===== página {numero} =====\n")
            partes.append(pagina.extract_text() or "")
    return "".join(partes)


def leer_pdf(ruta_pdf: Path | str, tipo_por_defecto: str = "verde") -> list[RegistroTramo]:
    """Extracción tentativa del anexo. Revisar SIEMPRE el CSV resultante."""
    registros: list[RegistroTramo] = []
    ambito = ""
    tipo = tipo_por_defecto

    for linea in volcar_texto(ruta_pdf).splitlines():
        texto = " ".join(linea.split())
        if not texto or texto.startswith("====="):
            continue

        minuscula = texto.lower()
        if "ámbito" in minuscula or "ambito" in minuscula or "distrito" in minuscula:
            ambito = texto
            continue
        for candidato in TIPOS_VALIDOS:
            if f"zona {candidato}" in minuscula and len(texto) < 60:
                tipo = candidato
                break

        coincidencia = PATRON_TRAMO.match(texto)
        if coincidencia:
            registros.append(
                RegistroTramo(
                    via=coincidencia.group("via").strip(),
                    tipo=tipo,
                    ambito=ambito,
                    desde=coincidencia.group("desde").strip(),
                    hasta=coincidencia.group("hasta").strip(),
                )
            )
        elif 4 < len(texto) < 60 and not any(c.isdigit() for c in texto[:3]):
            registros.append(RegistroTramo(via=texto, tipo=tipo, ambito=ambito))

    return registros


def _cli(argumentos: list[str]) -> int:
    if len(argumentos) < 2 or argumentos[0] not in ("volcar", "extraer"):
        print(
            "uso:\n"
            "  python -m zonaverde.anexo volcar  <anexo.pdf>\n"
            "  python -m zonaverde.anexo extraer <anexo.pdf> <salida.csv>",
            file=sys.stderr,
        )
        return 2

    if argumentos[0] == "volcar":
        print(volcar_texto(argumentos[1]))
        return 0

    if len(argumentos) < 3:
        print("falta la ruta del CSV de salida", file=sys.stderr)
        return 2
    registros = leer_pdf(argumentos[1])
    escribir_csv(registros, argumentos[2])
    print(f"{len(registros)} registros extraídos → {argumentos[2]}")
    print("REVISAR A MANO antes de construir la geometría.", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli(sys.argv[1:]))
