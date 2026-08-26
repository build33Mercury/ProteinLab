from __future__ import annotations

import math
from dataclasses import dataclass

from .structure import AtomRecord

Vec3 = tuple[float, float, float]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _scale(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def _normalize(a: Vec3) -> Vec3:
    n = _norm(a)
    if n <= 1e-15:
        raise ValueError("Cannot normalize a zero-length vector.")
    return _scale(a, 1.0 / n)


def distance(a: Vec3, b: Vec3) -> float:
    """Euclidean distance in the same units as the input coordinates (Å in PDB/mmCIF)."""
    d = _sub(b, a)
    return _norm(d)


def angle(a: Vec3, b: Vec3, c: Vec3) -> float:
    """Angle ABC in degrees, using the dot-product definition."""
    ba = _sub(a, b)
    bc = _sub(c, b)
    denom = _norm(ba) * _norm(bc)
    if denom <= 1e-15:
        raise ValueError("Angle is undefined because two selected points coincide.")
    cosine = max(-1.0, min(1.0, _dot(ba, bc) / denom))
    return math.degrees(math.acos(cosine))


def dihedral(a: Vec3, b: Vec3, c: Vec3, d: Vec3) -> float:
    """Signed torsion angle A-B-C-D in degrees, range [-180, 180].

    The implementation projects the terminal bond vectors onto the plane normal
    to the central bond and uses atan2, avoiding the sign ambiguity of acos.
    """
    b0 = _sub(a, b)
    b1 = _sub(c, b)
    b2 = _sub(d, c)
    b1n = _normalize(b1)

    v = _sub(b0, _scale(b1n, _dot(b0, b1n)))
    w = _sub(b2, _scale(b1n, _dot(b2, b1n)))
    if _norm(v) <= 1e-15 or _norm(w) <= 1e-15:
        raise ValueError("Dihedral is undefined for collinear selected points.")
    x = _dot(v, w)
    y = _dot(_cross(b1n, v), w)
    return math.degrees(math.atan2(y, x))


@dataclass(slots=True)
class MeasurementResult:
    kind: str
    value: float
    unit: str
    atoms: tuple[AtomRecord, ...]
    equation: str
    calculation: str

    @property
    def display_value(self) -> str:
        precision = 4 if self.kind == "Distance" else 3
        return f"{self.value:.{precision}f} {self.unit}"


def measure(kind: str, atoms: list[AtomRecord]) -> MeasurementResult:
    if kind == "Distance":
        if len(atoms) != 2:
            raise ValueError("Distance requires exactly two atoms.")
        p1, p2 = atoms[0].coord, atoms[1].coord
        value = distance(p1, p2)
        dx, dy, dz = p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]
        equation = "d = √[(x₂−x₁)² + (y₂−y₁)² + (z₂−z₁)²]"
        calculation = (
            f"Δx = {dx:.6f} Å\nΔy = {dy:.6f} Å\nΔz = {dz:.6f} Å\n\n"
            f"d = √[({dx:.6f})² + ({dy:.6f})² + ({dz:.6f})²]\n"
            f"d = {value:.6f} Å"
        )
        return MeasurementResult(kind, value, "Å", tuple(atoms), equation, calculation)

    if kind == "Angle":
        if len(atoms) != 3:
            raise ValueError("Angle requires exactly three atoms.")
        a, b, c = [x.coord for x in atoms]
        ba = _sub(a, b)
        bc = _sub(c, b)
        dot = _dot(ba, bc)
        nba, nbc = _norm(ba), _norm(bc)
        cosine = max(-1.0, min(1.0, dot / (nba * nbc)))
        value = angle(a, b, c)
        equation = "θ = arccos[(BA·BC)/(|BA||BC|)]"
        calculation = (
            f"BA·BC = {dot:.6f} Å²\n|BA| = {nba:.6f} Å\n|BC| = {nbc:.6f} Å\n"
            f"cos θ = {cosine:.9f}\nθ = {value:.6f}°"
        )
        return MeasurementResult(kind, value, "°", tuple(atoms), equation, calculation)

    if kind == "Dihedral":
        if len(atoms) != 4:
            raise ValueError("Dihedral requires exactly four atoms.")
        a, b, c, d = [x.coord for x in atoms]
        value = dihedral(a, b, c, d)
        equation = "φ = atan2[(b̂₁×v)·w, v·w]"
        calculation = (
            "b̂₁ is the normalized central bond B→C.\n"
            "v and w are the terminal bond vectors projected onto the plane perpendicular to b̂₁.\n\n"
            f"Signed torsion φ = {value:.6f}°"
        )
        return MeasurementResult(kind, value, "°", tuple(atoms), equation, calculation)

    raise ValueError(f"Unknown measurement type: {kind}")
