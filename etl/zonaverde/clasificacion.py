"""Clasificación de un punto GPS contra el dataset de tramos.

Regla de diseño: el error es asimétrico. Clasificar como «verde» un tramo que
no lo es produce una denuncia injusta; clasificar como «no verde» un tramo
verde sólo produce un reporte perdido. Ante cualquier duda —precisión pobre,
dos candidatos de tipo distinto igual de cerca, tramo sin verificar— la
respuesta correcta es NO reportable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .geometria import Polilinea, Punto

# Un punto con peor precisión que esto no se clasifica: el radio de búsqueda
# barrería media manzana del casco antiguo.
PRECISION_MAXIMA_M = 40.0

# Margen sobre la precisión declarada, para cubrir el ancho de calzada y acera.
TOLERANCIA_M = 15.0

# Si el segundo candidato es de otro tipo y está a menos de esto del primero,
# la clasificación es ambigua y decide la persona.
MARGEN_AMBIGUEDAD_M = 8.0

# Un tramo por debajo de esta confianza no genera denuncias.
CONFIANZA_MINIMA = 4


@dataclass
class Tramo:
    id: str
    tipo: str  # verde | naranja | azul | excluida
    via: str
    ambito: str
    confianza: int
    linea: Polilinea
    propiedades: dict = field(default_factory=dict)

    @classmethod
    def desde_feature(cls, elemento: dict) -> "Tramo":
        props = elemento.get("properties") or {}
        geom = elemento.get("geometry") or {}
        if geom.get("type") != "LineString":
            raise ValueError(f"se esperaba LineString, llegó {geom.get('type')!r}")
        return cls(
            id=str(props.get("id") or props.get("tramo_id") or ""),
            tipo=str(props.get("tipo") or ""),
            via=str(props.get("via") or ""),
            ambito=str(props.get("ambito") or ""),
            confianza=int(props.get("confianza") or 0),
            linea=Polilinea([(c[0], c[1]) for c in geom["coordinates"]]),
            propiedades=props,
        )


@dataclass
class Candidato:
    tramo: Tramo
    distancia_m: float


@dataclass
class Resultado:
    reportable: bool
    motivo: str
    tipo: str | None = None
    via: str | None = None
    distancia_m: float | None = None
    candidatos: list[Candidato] = field(default_factory=list)

    @property
    def ambiguo(self) -> bool:
        return self.motivo == "ambiguo"

    def para_app(self) -> dict:
        """Forma serializable que consume la pantalla de revisión."""
        return {
            "reportable": self.reportable,
            "motivo": self.motivo,
            "tipo": self.tipo,
            "via": self.via,
            "distancia_m": round(self.distancia_m, 1) if self.distancia_m is not None else None,
            "candidatos": [
                {
                    "via": c.tramo.via,
                    "tipo": c.tramo.tipo,
                    "distancia_m": round(c.distancia_m, 1),
                }
                for c in self.candidatos[:3]
            ],
        }


def cargar_tramos(ruta: Path | str) -> list[Tramo]:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    tramos = []
    for elemento in datos.get("features", []):
        try:
            tramos.append(Tramo.desde_feature(elemento))
        except ValueError:
            continue
    return tramos


def clasificar(
    punto: Punto,
    precision_m: float,
    tramos: list[Tramo],
    tolerancia_m: float = TOLERANCIA_M,
    margen_ambiguedad_m: float = MARGEN_AMBIGUEDAD_M,
    confianza_minima: int = CONFIANZA_MINIMA,
) -> Resultado:
    """Decide si un punto es reportable como estacionamiento en zona verde."""
    if precision_m > PRECISION_MAXIMA_M:
        return Resultado(False, "precision_insuficiente")

    radio = tolerancia_m + min(precision_m, PRECISION_MAXIMA_M)
    candidatos = sorted(
        (
            Candidato(t, d)
            for t in tramos
            if (d := t.linea.distancia_a(punto)) <= radio
        ),
        key=lambda c: c.distancia_m,
    )

    if not candidatos:
        return Resultado(False, "fuera_de_zona_regulada")

    # Las exclusiones (vado, carga y descarga, PMR, obras) se solapan a propósito
    # con el tramo verde que las contiene: son una capa por encima, no un
    # candidato que compita en distancia. Si hay una cerca, no se denuncia.
    exclusiones = [c for c in candidatos if c.tramo.tipo == "excluida"]
    if exclusiones and exclusiones[0].distancia_m <= tolerancia_m:
        mejor = exclusiones[0]
        return Resultado(
            False,
            "tramo_excluido",
            tipo=mejor.tramo.tipo,
            via=mejor.tramo.via,
            distancia_m=mejor.distancia_m,
            candidatos=candidatos,
        )

    regulados = [c for c in candidatos if c.tramo.tipo != "excluida"]
    if not regulados:
        return Resultado(False, "fuera_de_zona_regulada", candidatos=candidatos)

    mejor = regulados[0]
    base = dict(
        tipo=mejor.tramo.tipo,
        via=mejor.tramo.via,
        distancia_m=mejor.distancia_m,
        candidatos=regulados,
    )

    # Un candidato de otro tipo prácticamente a la misma distancia: decide la persona.
    for otro in regulados[1:]:
        if otro.tramo.tipo != mejor.tramo.tipo:
            if otro.distancia_m - mejor.distancia_m < margen_ambiguedad_m:
                return Resultado(False, "ambiguo", **base)
            break

    if mejor.tramo.tipo != "verde":
        return Resultado(False, "no_es_zona_verde", **base)

    if mejor.tramo.confianza < confianza_minima:
        return Resultado(False, "tramo_sin_verificar", **base)

    return Resultado(True, "en_zona_verde", **base)


MOTIVOS_ES = {
    "en_zona_verde": "El vehículo está en zona verde.",
    "precision_insuficiente": "La precisión del GPS es insuficiente. Acércate y repite la toma.",
    "fuera_de_zona_regulada": "Este punto no consta como zona de estacionamiento regulado.",
    "ambiguo": "No se puede determinar la calle con seguridad. Confírmala.",
    "tramo_excluido": "Este tramo está excluido (vado, carga y descarga, PMR u obras).",
    "no_es_zona_verde": "El tramo no es zona verde.",
    "tramo_sin_verificar": "El tramo aún no está verificado en campo. No se puede denunciar.",
}
