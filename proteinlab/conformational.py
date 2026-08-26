from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .library import APP_DATA, CACHE_DIR, ensure_dirs, register_generated_structure
from .models import ProteinRecord
from .physics import _build_simulation_objects, _openmm_modules, is_simulation_ready
from .structure import pdb_path_for_vtk

EXPLORATION_DIR = APP_DATA / "conformational_exploration"


@dataclass(slots=True)
class ConformationalOptions:
    target_temperature_k: float = 300.0
    high_temperature_k: float = 450.0
    replicas: int = 2
    cycles: int = 2
    temperature_points_per_leg: int = 5
    steps_per_temperature: int = 100
    timestep_fs: float = 2.0
    friction_per_ps: float = 1.0
    random_seed: int = 20260814
    minimize_before: bool = True


@dataclass(slots=True)
class ConformationalSample:
    replica: int
    cycle: int
    stage: int
    temperature_k: float
    potential_kj_mol: float
    coordinates_angstrom: np.ndarray


@dataclass(slots=True)
class ConformationalResult:
    record: ProteinRecord
    samples: list[ConformationalSample] = field(default_factory=list)
    sample_path: str = ""
    lowest_energy_kj_mol: float = 0.0
    total_steps: int = 0
    platform: str = ""


def _temperature_schedule(target: float, high: float, points_per_leg: int) -> np.ndarray:
    if target <= 0 or high <= 0:
        raise ValueError("Temperatures must be positive Kelvin values.")
    if high < target:
        raise ValueError("High temperature must be greater than or equal to the target temperature.")
    if points_per_leg < 2:
        raise ValueError("Temperature points per leg must be at least 2.")
    up = np.linspace(target, high, points_per_leg, dtype=float)
    down = np.linspace(high, target, points_per_leg, dtype=float)[1:]
    return np.concatenate([up, down])


def run_conformational_exploration(
    record: ProteinRecord,
    options: ConformationalOptions,
    *,
    progress: Callable[[int, int, ConformationalSample | None], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> ConformationalResult:
    """Run explicit OpenMM heating/cooling replicas for conformational exploration.

    This is a physics-based sampling protocol, not a native-structure predictor. The temperature
    schedule is intentionally recorded because the resulting samples are non-equilibrium and must
    not be interpreted as a Boltzmann free-energy distribution.
    """
    if not is_simulation_ready(record):
        raise ValueError("Conformational exploration requires a force-field-prepared structure. Use Prepare Simulation first.")
    if options.replicas < 1 or options.cycles < 1:
        raise ValueError("Replicas and cycles must each be at least 1.")
    if options.steps_per_temperature < 1:
        raise ValueError("Steps per temperature must be positive.")
    if options.timestep_fs <= 0 or options.timestep_fs > 4.0:
        raise ValueError("Timestep must be >0 and <=4 fs in this build.")

    m = _openmm_modules()
    schedule = _temperature_schedule(
        float(options.target_temperature_k),
        float(options.high_temperature_k),
        int(options.temperature_points_per_leg),
    )
    total_stages = int(options.replicas) * int(options.cycles) * len(schedule)
    total_steps = total_stages * int(options.steps_per_temperature)
    completed_stages = 0
    all_samples: list[ConformationalSample] = []
    lowest_energy = float("inf")
    lowest_positions_nm: np.ndarray | None = None
    lowest_topology = None
    platform_name = ""

    ensure_dirs()
    EXPLORATION_DIR.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]

    for replica in range(int(options.replicas)):
        seed = int(options.random_seed) + replica * 100003
        integrator = m["LangevinMiddleIntegrator"](
            float(options.target_temperature_k) * m["kelvin"],
            float(options.friction_per_ps) / m["picosecond"],
            float(options.timestep_fs) * m["femtoseconds"],
        )
        try:
            integrator.setRandomNumberSeed(seed)
        except Exception:
            pass
        m2, pdb, _system, simulation, _nonbonded = _build_simulation_objects(record, integrator=integrator)
        platform_name = simulation.context.getPlatform().getName()
        lowest_topology = pdb.topology
        if options.minimize_before:
            simulation.minimizeEnergy(
                tolerance=10.0 * m2["kilojoules_per_mole"] / m2["nanometer"],
                maxIterations=500,
            )
        simulation.context.setVelocitiesToTemperature(
            float(options.target_temperature_k) * m2["kelvin"], seed
        )

        for cycle in range(int(options.cycles)):
            for stage, temperature in enumerate(schedule):
                if cancelled and cancelled():
                    raise RuntimeError(
                        f"Conformational exploration cancelled after {completed_stages} of {total_stages} temperature stages."
                    )
                # OpenMM explicitly allows updating the Langevin heat-bath temperature.
                integrator.setTemperature(float(temperature) * m2["kelvin"])
                simulation.step(int(options.steps_per_temperature))
                state = simulation.context.getState(getEnergy=True, getPositions=True)
                energy = float(
                    state.getPotentialEnergy().value_in_unit(m2["kilojoules_per_mole"])
                )
                positions_nm = np.asarray(
                    state.getPositions(asNumpy=True).value_in_unit(m2["nanometer"]), dtype=float
                )
                sample = ConformationalSample(
                    replica=replica + 1,
                    cycle=cycle + 1,
                    stage=stage + 1,
                    temperature_k=float(temperature),
                    potential_kj_mol=energy,
                    coordinates_angstrom=positions_nm * 10.0,
                )
                all_samples.append(sample)
                if energy < lowest_energy:
                    lowest_energy = energy
                    lowest_positions_nm = positions_nm.copy()
                completed_stages += 1
                if progress:
                    progress(completed_stages, total_stages, sample)

    if not all_samples or lowest_positions_nm is None or lowest_topology is None:
        raise RuntimeError("Conformational exploration produced no samples.")

    sample_path = EXPLORATION_DIR / f"exploration_{token}.npz"
    np.savez_compressed(
        sample_path,
        coordinates_angstrom=np.asarray([s.coordinates_angstrom for s in all_samples], dtype=np.float32),
        replica=np.asarray([s.replica for s in all_samples], dtype=np.int16),
        cycle=np.asarray([s.cycle for s in all_samples], dtype=np.int16),
        stage=np.asarray([s.stage for s in all_samples], dtype=np.int16),
        temperature_k=np.asarray([s.temperature_k for s in all_samples], dtype=np.float64),
        potential_kj_mol=np.asarray([s.potential_kj_mol for s in all_samples], dtype=np.float64),
        topology_pdb=np.asarray(str(pdb_path_for_vtk(record))),
    )

    temp = CACHE_DIR / f"exploration_lowest_{token}.pdb"
    with temp.open("w", encoding="utf-8") as handle:
        m["PDBFile"].writeFile(lowest_topology, lowest_positions_nm * m["nanometer"], handle)

    metadata = dict(record.metadata)
    metadata.update({
        "parent_protein": record.name,
        "parent_record_id": record.id,
        "calculation": "OpenMM non-equilibrium heating/cooling conformational exploration",
        "conformational_exploration": "true",
        "native_fold_prediction": "false",
        "equilibrium_distribution": "false",
        "target_temperature_K": f"{options.target_temperature_k:.8g}",
        "high_temperature_K": f"{options.high_temperature_k:.8g}",
        "replicas": str(options.replicas),
        "cycles": str(options.cycles),
        "temperature_points_per_leg": str(options.temperature_points_per_leg),
        "steps_per_temperature": str(options.steps_per_temperature),
        "total_steps": str(total_steps),
        "timestep_fs": f"{options.timestep_fs:.8g}",
        "friction_per_ps": f"{options.friction_per_ps:.8g}",
        "random_seed": str(options.random_seed),
        "lowest_sampled_potential_kJ_mol": f"{lowest_energy:.12g}",
        "exploration_npz": str(sample_path),
        "platform": platform_name,
        "simulation_ready": "true",
    })
    lowest_record = register_generated_structure(
        temp,
        name=f"{record.name} — lowest sampled conformer",
        origin="conformer",
        description=(
            "Lowest potential-energy coordinate snapshot encountered during a non-equilibrium OpenMM heating/cooling "
            "conformational exploration. It is not identified as the native fold."
        ),
        metadata=metadata,
    )
    temp.unlink(missing_ok=True)
    return ConformationalResult(
        record=lowest_record,
        samples=all_samples,
        sample_path=str(sample_path),
        lowest_energy_kj_mol=float(lowest_energy),
        total_steps=total_steps,
        platform=platform_name,
    )
