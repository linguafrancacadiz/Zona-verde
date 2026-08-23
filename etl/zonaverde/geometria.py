"""Operaciones geométricas sobre polilíneas. Sin dependencias externas.

Hacia fuera se trabaja siempre en grados WGS84 como tuplas ``(lon, lat)``.
Internamente se proyecta a metros con una proyección equirectangular local
anclada al centroide de la geometría. Para una ciudad del tamaño de Cádiz
(~6 km de extremo a extremo) el error de esa aproximación queda muy por debajo
del metro, holgadamente suficiente para las tolerancias de 15-25 m con las que
trabaja el clasificador.

Se evita deliberadamente shapely/pyproj: el dataset de zonas es el artefacto
crítico del proyecto y conviene que se pueda reconstruir y verificar en
cualquier máquina con un Python limpio.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, radians
from typing import Iterable, Sequence

Punto = tuple[float, float]  # (lon, lat)

METROS_POR_GRADO_LAT = 111_132.0


class ProyeccionLocal:
    """Proyección equirectangular anclada a un punto de referencia."""

    def __init__(self, lat0: float, lon0: float) -> None:
        self.lat0 = lat0
        self.lon0 = lon0
        self._m_por_grado_lon = METROS_POR_GRADO_LAT * cos(radians(lat0))
        if self._m_por_grado_lon == 0:
            raise ValueError("latitud de referencia degenerada (polo)")

    def a_metros(self, punto: Punto) -> tuple[float, float]:
        lon, lat = punto
        return (
            (lon - self.lon0) * self._m_por_grado_lon,
            (lat - self.lat0) * METROS_POR_GRADO_LAT,
        )

    def a_grados(self, xy: tuple[float, float]) -> Punto:
        x, y = xy
        return (
            self.lon0 + x / self._m_por_grado_lon,
            self.lat0 + y / METROS_POR_GRADO_LAT,
        )


@dataclass(frozen=True)
class Proyeccion:
    """Resultado de proyectar un punto sobre una polilínea."""

    distancia_m: float
    fraccion: float  # posición a lo largo de la línea, en [0, 1]
    punto: Punto  # punto más cercano sobre la línea


def distancia_m(a: Punto, b: Punto) -> float:
    """Distancia en metros entre dos puntos (lon, lat)."""
    proy = ProyeccionLocal((a[1] + b[1]) / 2, (a[0] + b[0]) / 2)
    ax, ay = proy.a_metros(a)
    bx, by = proy.a_metros(b)
    return hypot(bx - ax, by - ay)


class Polilinea:
    """Polilínea en coordenadas geográficas con operaciones métricas."""

    def __init__(self, coords: Sequence[Punto], proyeccion: ProyeccionLocal | None = None) -> None:
        limpias: list[Punto] = []
        for c in coords:
            punto = (float(c[0]), float(c[1]))
            # descartar vértices repetidos consecutivos, habituales en OSM/CDAU
            if not limpias or punto != limpias[-1]:
                limpias.append(punto)
        if len(limpias) < 2:
            raise ValueError("una polilínea necesita al menos dos vértices distintos")

        self.coords: list[Punto] = limpias
        if proyeccion is None:
            lat0 = sum(c[1] for c in limpias) / len(limpias)
            lon0 = sum(c[0] for c in limpias) / len(limpias)
            proyeccion = ProyeccionLocal(lat0, lon0)
        self.proyeccion = proyeccion

        self._xy = [proyeccion.a_metros(c) for c in limpias]
        acumulado = [0.0]
        for (x1, y1), (x2, y2) in zip(self._xy, self._xy[1:]):
            acumulado.append(acumulado[-1] + hypot(x2 - x1, y2 - y1))
        self._acumulado = acumulado
        self.longitud_m = acumulado[-1]

    def __repr__(self) -> str:  # pragma: no cover - ayuda en depuración
        return f"<Polilinea {len(self.coords)} vértices, {self.longitud_m:.1f} m>"

    @property
    def inicio(self) -> Punto:
        return self.coords[0]

    @property
    def fin(self) -> Punto:
        return self.coords[-1]

    def proyectar(self, punto: Punto) -> Proyeccion:
        """Punto más cercano de la línea al punto dado."""
        px, py = self.proyeccion.a_metros(punto)
        mejor_d = float("inf")
        mejor_recorrido = 0.0
        mejor_xy = self._xy[0]

        for i, ((x1, y1), (x2, y2)) in enumerate(zip(self._xy, self._xy[1:])):
            dx, dy = x2 - x1, y2 - y1
            largo2 = dx * dx + dy * dy
            if largo2 == 0:
                t = 0.0
            else:
                t = ((px - x1) * dx + (py - y1) * dy) / largo2
                t = max(0.0, min(1.0, t))
            cx, cy = x1 + t * dx, y1 + t * dy
            d = hypot(px - cx, py - cy)
            if d < mejor_d:
                mejor_d = d
                mejor_recorrido = self._acumulado[i] + t * hypot(dx, dy)
                mejor_xy = (cx, cy)

        fraccion = 0.0 if self.longitud_m == 0 else mejor_recorrido / self.longitud_m
        return Proyeccion(mejor_d, fraccion, self.proyeccion.a_grados(mejor_xy))

    def distancia_a(self, punto: Punto) -> float:
        return self.proyectar(punto).distancia_m

    def punto_en(self, fraccion: float) -> Punto:
        """Punto situado a una fracción dada del recorrido."""
        fraccion = max(0.0, min(1.0, float(fraccion)))
        objetivo = fraccion * self.longitud_m
        for i, (desde, hasta) in enumerate(zip(self._acumulado, self._acumulado[1:])):
            if objetivo <= hasta or i == len(self._xy) - 2:
                tramo = hasta - desde
                t = 0.0 if tramo == 0 else (objetivo - desde) / tramo
                (x1, y1), (x2, y2) = self._xy[i], self._xy[i + 1]
                return self.proyeccion.a_grados((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
        return self.coords[-1]

    def recortar(self, fraccion_ini: float, fraccion_fin: float) -> "Polilinea":
        """Sub-línea entre dos fracciones. Equivalente a ``ST_LineSubstring``."""
        f1 = max(0.0, min(1.0, float(fraccion_ini)))
        f2 = max(0.0, min(1.0, float(fraccion_fin)))
        if f1 > f2:
            f1, f2 = f2, f1
        if (f2 - f1) * self.longitud_m < 0.5:
            raise ValueError(
                f"el recorte resultante mide menos de 0,5 m (f1={f1:.4f}, f2={f2:.4f}); "
                "revisa los extremos del tramo"
            )

        inicio = self.punto_en(f1)
        fin = self.punto_en(f2)
        d_ini, d_fin = f1 * self.longitud_m, f2 * self.longitud_m
        intermedios = [
            self.coords[i]
            for i, acumulado in enumerate(self._acumulado)
            if d_ini < acumulado < d_fin
        ]
        return Polilinea([inicio, *intermedios, fin], self.proyeccion)

    def intersecciones(self, otra: "Polilinea") -> list[Punto]:
        """Puntos de cruce con otra polilínea (extremos incluidos)."""
        otra_xy = [self.proyeccion.a_metros(c) for c in otra.coords]
        encontrados: list[Punto] = []
        for (x1, y1), (x2, y2) in zip(self._xy, self._xy[1:]):
            for (x3, y3), (x4, y4) in zip(otra_xy, otra_xy[1:]):
                punto = _cruce_segmentos((x1, y1), (x2, y2), (x3, y3), (x4, y4))
                if punto is not None:
                    encontrados.append(self.proyeccion.a_grados(punto))
        return _sin_duplicados(encontrados)

    def punto_de_encuentro(self, otra: "Polilinea", tolerancia_m: float = 12.0) -> Punto | None:
        """Cruce con otra línea; si no se cruzan, punto medio del acercamiento máximo.

        Los ejes viales de CDAU y OSM vienen partidos en los cruces, de modo que
        dos calles que se encuentran suelen compartir vértice. Pero no siempre:
        hay huecos de pocos metros. La tolerancia cubre ese caso sin inventar
        cruces entre calles que realmente no se tocan.
        """
        cruces = self.intersecciones(otra)
        if cruces:
            return cruces[0]

        mejor: tuple[float, Punto] | None = None
        for candidato in (*self.coords, *(otra.punto_en(f / 20) for f in range(21))):
            d1 = self.distancia_a(candidato)
            d2 = otra.distancia_a(candidato)
            total = d1 + d2
            if mejor is None or total < mejor[0]:
                mejor = (total, candidato)

        if mejor is None or mejor[0] > tolerancia_m:
            return None
        punto = mejor[1]
        a = self.proyectar(punto).punto
        b = otra.proyectar(punto).punto
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _cruce_segmentos(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> tuple[float, float] | None:
    """Intersección de dos segmentos en coordenadas proyectadas, o ``None``."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denominador = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(denominador) < 1e-12:  # paralelos o colineales
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / denominador
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / denominador
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def _sin_duplicados(puntos: Iterable[Punto], tolerancia_m: float = 0.5) -> list[Punto]:
    unicos: list[Punto] = []
    for punto in puntos:
        if all(distancia_m(punto, otro) > tolerancia_m for otro in unicos):
            unicos.append(punto)
    return unicos
