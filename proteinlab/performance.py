from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PerformanceAdvice:
    level: str
    message: str


# Conservative UI guardrails. These do not change physics; they only advise how to render/analyze large data.
LARGE_STRUCTURE_ATOMS = 100_000
VERY_LARGE_STRUCTURE_ATOMS = 300_000
LARGE_TRAJECTORY_COORDINATES = 50_000_000  # frames × atoms


def structure_advice(atom_count: int) -> PerformanceAdvice | None:
    if atom_count >= VERY_LARGE_STRUCTURE_ATOMS:
        return PerformanceAdvice("high", "Very large structure: Ribbon or Sticks is recommended. Space-filling rendering can be expensive.")
    if atom_count >= LARGE_STRUCTURE_ATOMS:
        return PerformanceAdvice("moderate", "Large structure: Ribbon is recommended for responsive navigation.")
    return None


def trajectory_advice(frame_count: int, atom_count: int) -> PerformanceAdvice | None:
    total = int(frame_count) * int(atom_count)
    if total >= LARGE_TRAJECTORY_COORDINATES:
        return PerformanceAdvice("high", "Large trajectory: playback is available, but full-frame analyses may consume substantial memory/time. Consider a smaller reporting frequency or external trajectory tooling for production-scale runs.")
    return None
