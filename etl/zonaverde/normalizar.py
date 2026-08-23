"""Normalización de nombres de vía para emparejar el anexo con el callejero.

El anexo de la ordenanza escribe «C/ Sagasta», el CDAU «CALLE SAGASTA» y OSM
«Calle de Sagasta». Se generan dos formas:

- ``normalizado``: legible, sin tipo de vía ni acentos. Para mostrar y depurar.
- ``clave``: agresiva, sin partículas ni espacios. Para emparejar.
"""

from __future__ import annotations

import re
import unicodedata

TIPOS_VIA = (
    "calle", "c", "cl", "avenida", "avda", "avd", "av", "plaza", "pza", "plz", "pl",
    "paseo", "po", "pso", "glorieta", "gta", "ronda", "rda", "camino", "cmno", "cno",
    "carretera", "ctra", "cuesta", "callejon", "callejuela", "travesia", "trva",
    "alameda", "barriada", "bda", "urbanizacion", "urb", "poligono", "pol",
    "muelle", "parque", "pje", "pasaje", "via", "cortadura", "puerta", "campo",
    "jardines", "rincon", "explanada", "bulevar", "sector", "residencial",
)

PARTICULAS = ("de", "del", "de la", "de los", "de las", "la", "el", "los", "las", "y", "d")

ABREVIATURAS = {
    "sta": "santa", "sto": "santo", "sn": "san", "s": "san",
    "dr": "doctor", "dra": "doctora", "gral": "general", "cap": "capitan",
    "ntra": "nuestra", "sra": "senora", "sr": "senor", "hnos": "hermanos",
    "pdte": "presidente", "marq": "marques", "cnel": "coronel", "tte": "teniente",
    "arz": "arzobispo", "obpo": "obispo", "prof": "profesor", "ing": "ingeniero",
    "fco": "francisco", "mª": "maria", "jose_mª": "josemaria",
}


def _sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _limpiar(nombre: str) -> list[str]:
    texto = _sin_acentos(str(nombre)).lower()
    texto = texto.replace("/", " ").replace(".", " ").replace("-", " ")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return [ABREVIATURAS.get(p, p) for p in texto.split(" ") if p]


def normalizar_via(nombre: str) -> str:
    """Nombre de vía sin tipo, sin acentos y en minúsculas.

    >>> normalizar_via("C/ Sagasta")
    'sagasta'
    >>> normalizar_via("Plaza de la Catedral")
    'catedral'
    """
    palabras = _limpiar(nombre)
    if not palabras:
        return ""

    # eliminar el tipo de vía inicial (una sola vez)
    if palabras[0] in TIPOS_VIA and len(palabras) > 1:
        palabras = palabras[1:]

    # eliminar partículas iniciales que quedan colgando tras quitar el tipo
    while len(palabras) > 1 and palabras[0] in PARTICULAS:
        palabras = palabras[1:]

    return " ".join(palabras)


def clave_via(nombre: str) -> str:
    """Forma canónica para emparejar. Sin partículas ni espacios.

    >>> clave_via("Cuesta de las Calesas") == clave_via("CUESTA CALESAS")
    True
    >>> clave_via("Avda. Ana de Viya") == clave_via("Avenida Ana de Viya")
    True
    """
    palabras = normalizar_via(nombre).split(" ")
    utiles = [p for p in palabras if p and p not in PARTICULAS]
    return "".join(utiles or palabras)
