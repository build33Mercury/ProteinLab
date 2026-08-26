from __future__ import annotations

import csv
import math
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .library import APP_DATA, CACHE_DIR, ensure_dirs, register_generated_structure
from .models import ProteinRecord
from .structure import pdb_path_for_vtk

SIMULATION_DIR = APP_DATA / "simulations"


@dataclass(slots=True)
class EnergyTerm:
    name: str
    force_class: str
    energy_kj_mol: float
    equation: str
    explanation: str


@dataclass(slots=True)
class EnergyResult:
    total_kj_mol: float
    terms: list[EnergyTerm]
    forcefield: str
    nonbonded_method: str
    atom_count: int
    rms_force_kj_mol_nm: float


@dataclass(slots=True)
class MinimizationOptions:
    tolerance_kj_mol_nm: float = 10.0
    max_iterations: int = 500


@dataclass(slots=True)
class MinimizationResult:
    record: ProteinRecord
    energy_before_kj_mol: float
    energy_after_kj_mol: float
    rms_force_before: float
    rms_force_after: float
    iterations_limit: int
    tolerance_kj_mol_nm: float


@dataclass(slots=True)
class MDOptions:
    temperature_k: float = 300.0
    friction_per_ps: float = 1.0
    timestep_fs: float = 2.0
    steps: int = 2500
    report_interval: int = 250
    random_seed: int = 20260814
    minimize_before: bool = True
    ensemble: str = "NVT"
    pressure_bar: float = 1.0
    barostat_interval: int = 25


@dataclass(slots=True)
class MDSample:
    step: int
    time_ps: float
    potential_kj_mol: float
    kinetic_kj_mol: float
    total_kj_mol: float


@dataclass(slots=True)
class MDResult:
    record: ProteinRecord
    samples: list[MDSample] = field(default_factory=list)
    log_path: str = ""
    trajectory_path: str = ""
    dcd_path: str = ""
    frame_count: int = 0
    platform: str = ""
    temperature_k: float = 0.0
    timestep_fs: float = 0.0
    steps: int = 0
    simulated_time_ps: float = 0.0
    ensemble: str = "NVT"
    pressure_bar: float | None = None


_FORCE_INFO = {
    "HarmonicBondForce": (
        "Bond stretching",
        "E_bond = 1/2 k_b (r - r0)^2",
        "Harmonic bond-stretching energy from the selected force field.",
    ),
    "HarmonicAngleForce": (
        "Angle bending",
        "E_angle = 1/2 k_theta (theta - theta0)^2",
        "Harmonic valence-angle energy from the selected force field.",
    ),
    "PeriodicTorsionForce": (
        "Torsions",
        "E_torsion = k [1 + cos(n*theta - theta0)]",
        "Periodic torsional potential over bonded dihedral angles.",
    ),
    "CMAPTorsionForce": (
        "CMAP torsion correction",
        "E_CMAP = F(phi, psi) from a periodic tabulated 2D torsion surface",
        "Coupled backbone-torsion correction evaluated from the force field's periodic two-dimensional energy map.",
    ),
    "NonbondedForce": (
        "Nonbonded",
        "E_nonbonded = k_e q_i q_j/r + 4 epsilon[(sigma/r)^12 - (sigma/r)^6]",
        "OpenMM NonbondedForce combines electrostatics and Lennard-Jones interactions; PME/cutoffs/exceptions are applied by the configured System.",
    ),
    "CMMotionRemover": (
        "Center-of-mass remover",
        "No potential-energy term",
        "Removes center-of-mass motion during dynamics; it does not contribute a conventional potential-energy term.",
    ),
}


def is_simulation_ready(record: ProteinRecord) -> bool:
    return record.origin in {"prepared", "minimized", "dynamics"} or record.metadata.get("simulation_ready", "").lower() == "true"


def _require_ready(record: ProteinRecord) -> None:
    if not is_simulation_ready(record):
        raise ValueError(
            "This structure is not force-field prepared yet. Use Prepare simulation first so hydrogens, solvent/ions, and force-field templates are explicit."
        )


def _openmm_modules():
    try:
        import openmm
        from openmm import LangevinMiddleIntegrator, VerletIntegrator
        from openmm.app import DCDReporter, ForceField, HBonds, NoCutoff, PDBFile, PME, Simulation
        from openmm.unit import bar, femtoseconds, kelvin, kilojoules_per_mole, nanometer, picosecond, picoseconds
    except Exception as exc:  # pragma: no cover - binary dependency
        raise RuntimeError("OpenMM is unavailable. Rerun the current Protein Lab installer to repair the scientific stack.") from exc
    return {
        "openmm": openmm,
        "LangevinMiddleIntegrator": LangevinMiddleIntegrator,
        "VerletIntegrator": VerletIntegrator,
        "DCDReporter": DCDReporter,
        "ForceField": ForceField,
        "HBonds": HBonds,
        "NoCutoff": NoCutoff,
        "PDBFile": PDBFile,
        "PME": PME,
        "Simulation": Simulation,
        "bar": bar,
        "femtoseconds": femtoseconds,
        "kelvin": kelvin,
        "kilojoules_per_mole": kilojoules_per_mole,
        "nanometer": nanometer,
        "picosecond": picosecond,
        "picoseconds": picoseconds,
    }


def _bool_meta(record: ProteinRecord, key: str) -> bool:
    return str(record.metadata.get(key, "false")).strip().lower() in {"1", "true", "yes", "on"}


def _build_simulation_objects(record: ProteinRecord, *, integrator, barostat: tuple[float, float, int, int] | None = None):
    _require_ready(record)
    m = _openmm_modules()
    pdb_path = pdb_path_for_vtk(record)
    pdb = m["PDBFile"](str(pdb_path))
    preset = record.metadata.get("forcefield_preset", "amber19").strip().lower()
    if preset == "amber14_lipid17":
        forcefield = m["ForceField"]("amber14-all.xml", "amber14/tip3p.xml")
    else:
        forcefield = m["ForceField"]("amber19-all.xml", "tip3p.xml")
    periodic = _bool_meta(record, "explicit_solvation")
    if periodic:
        system = forcefield.createSystem(
            pdb.topology,
            nonbondedMethod=m["PME"],
            nonbondedCutoff=1.0 * m["nanometer"],
            constraints=m["HBonds"],
            rigidWater=True,
        )
        nonbonded = "PME, 1.0 nm real-space cutoff"
    else:
        system = forcefield.createSystem(
            pdb.topology,
            nonbondedMethod=m["NoCutoff"],
            constraints=m["HBonds"],
        )
        nonbonded = "NoCutoff (nonperiodic/vacuum)"
    if barostat is not None:
        pressure_bar, temperature_k, frequency, barostat_seed = barostat
        if not periodic:
            raise ValueError("NPT dynamics requires an explicitly solvated periodic system. Re-run Prepare simulation with explicit solvent enabled.")
        if pressure_bar <= 0:
            raise ValueError("NPT pressure must be positive.")
        if frequency <= 0:
            raise ValueError("Barostat interval must be a positive number of integration steps.")
        mc_barostat = m["openmm"].MonteCarloBarostat(
            float(pressure_bar) * m["bar"],
            float(temperature_k) * m["kelvin"],
            int(frequency),
        )
        try:
            mc_barostat.setRandomNumberSeed(int(barostat_seed))
        except Exception:
            pass
        system.addForce(mc_barostat)
    simulation = m["Simulation"](pdb.topology, system, integrator)
    simulation.context.setPositions(pdb.positions)
    try:
        simulation.context.computeVirtualSites()
    except Exception:
        pass
    return m, pdb, system, simulation, nonbonded


def _rms_force(state, unit_force) -> float:
    forces = state.getForces(asNumpy=True).value_in_unit(unit_force)
    arr = np.asarray(forces, dtype=float)
    if arr.size == 0:
        return 0.0
    return float(math.sqrt(float(np.mean(np.sum(arr * arr, axis=1)))))


def _classify_force(force) -> tuple[str, str, str]:
    cls = force.__class__.__name__
    return _FORCE_INFO.get(cls, (force.getName() or cls, "OpenMM force term; see force class", f"Energy reported directly from OpenMM {cls}."))


def evaluate_energy(record: ProteinRecord) -> EnergyResult:
    """Evaluate the current OpenMM potential and decompose it by actual Force groups."""
    m = _openmm_modules()
    integrator = m["VerletIntegrator"](1.0 * m["femtoseconds"])
    m, pdb, system, simulation, nonbonded = _build_simulation_objects(record, integrator=integrator)

    forces = list(system.getForces())
    if len(forces) > 32:
        raise RuntimeError("Energy decomposition requires at most 32 OpenMM Force objects because Force groups are indexed 0-31.")
    for group, force in enumerate(forces):
        force.setForceGroup(group)
    simulation.context.reinitialize(preserveState=True)

    total_state = simulation.context.getState(getEnergy=True, getForces=True)
    unit_energy = m["kilojoules_per_mole"]
    unit_force = m["kilojoules_per_mole"] / m["nanometer"]
    total = float(total_state.getPotentialEnergy().value_in_unit(unit_energy))
    rms = _rms_force(total_state, unit_force)

    aggregated: dict[tuple[str, str, str, str], float] = {}
    for group, force in enumerate(forces):
        state = simulation.context.getState(getEnergy=True, groups={group})
        value = float(state.getPotentialEnergy().value_in_unit(unit_energy))
        display_name, equation, explanation = _classify_force(force)
        key = (display_name, force.__class__.__name__, equation, explanation)
        aggregated[key] = aggregated.get(key, 0.0) + value

    terms = [EnergyTerm(name=k[0], force_class=k[1], equation=k[2], explanation=k[3], energy_kj_mol=v) for k, v in aggregated.items()]
    terms.sort(key=lambda t: abs(t.energy_kj_mol), reverse=True)
    return EnergyResult(
        total_kj_mol=total,
        terms=terms,
        forcefield=record.metadata.get("force_field", "AMBER19 / ff19SB protein parameters"),
        nonbonded_method=nonbonded,
        atom_count=sum(1 for _ in pdb.topology.atoms()),
        rms_force_kj_mol_nm=rms,
    )


def minimize_structure(record: ProteinRecord, options: MinimizationOptions) -> MinimizationResult:
    m = _openmm_modules()
    integrator = m["VerletIntegrator"](1.0 * m["femtoseconds"])
    m, pdb, system, simulation, nonbonded = _build_simulation_objects(record, integrator=integrator)
    unit_energy = m["kilojoules_per_mole"]
    unit_force = unit_energy / m["nanometer"]

    before_state = simulation.context.getState(getEnergy=True, getForces=True)
    e0 = float(before_state.getPotentialEnergy().value_in_unit(unit_energy))
    f0 = _rms_force(before_state, unit_force)

    simulation.minimizeEnergy(
        tolerance=float(options.tolerance_kj_mol_nm) * unit_force,
        maxIterations=int(options.max_iterations),
    )
    after_state = simulation.context.getState(getEnergy=True, getForces=True, getPositions=True)
    e1 = float(after_state.getPotentialEnergy().value_in_unit(unit_energy))
    f1 = _rms_force(after_state, unit_force)

    ensure_dirs()
    temp = CACHE_DIR / f"minimized_{uuid.uuid4().hex[:12]}.pdb"
    with temp.open("w", encoding="utf-8") as handle:
        m["PDBFile"].writeFile(pdb.topology, after_state.getPositions(), handle)

    metadata = dict(record.metadata)
    metadata.update({
        "parent_protein": record.name,
        "parent_record_id": record.id,
        "simulation_ready": "true",
        "calculation": "OpenMM local energy minimization",
        "minimizer": "L-BFGS via OpenMM Simulation.minimizeEnergy",
        "minimization_tolerance_kJ_mol_nm": f"{options.tolerance_kj_mol_nm:.6g}",
        "minimization_max_iterations": str(options.max_iterations),
        "potential_energy_before_kJ_mol": f"{e0:.10g}",
        "potential_energy_after_kJ_mol": f"{e1:.10g}",
        "rms_force_before_kJ_mol_nm": f"{f0:.10g}",
        "rms_force_after_kJ_mol_nm": f"{f1:.10g}",
        "nonbonded_method": nonbonded,
    })
    minimized = register_generated_structure(
        temp,
        name=f"{record.name} — minimized",
        origin="minimized",
        description="OpenMM force-field structure after local L-BFGS energy minimization.",
        metadata=metadata,
    )
    temp.unlink(missing_ok=True)
    return MinimizationResult(minimized, e0, e1, f0, f1, options.max_iterations, options.tolerance_kj_mol_nm)


def run_molecular_dynamics(
    record: ProteinRecord,
    options: MDOptions,
    *,
    progress: Callable[[int, int, MDSample | None], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> MDResult:
    m = _openmm_modules()
    if options.steps <= 0 or options.report_interval <= 0:
        raise ValueError("MD steps and report interval must both be positive integers.")
    if options.timestep_fs <= 0 or options.timestep_fs > 4.0:
        raise ValueError("Timestep must be >0 and <=4 fs in this build. The default 2 fs is intended for HBond-constrained systems.")
    ensemble = options.ensemble.strip().upper()
    if ensemble not in {"NVT", "NPT"}:
        raise ValueError("Ensemble must be NVT or NPT.")

    integrator = m["LangevinMiddleIntegrator"](
        float(options.temperature_k) * m["kelvin"],
        float(options.friction_per_ps) / m["picosecond"],
        float(options.timestep_fs) * m["femtoseconds"],
    )
    try:
        integrator.setRandomNumberSeed(int(options.random_seed))
    except Exception:
        pass

    barostat = None
    if ensemble == "NPT":
        barostat = (float(options.pressure_bar), float(options.temperature_k), int(options.barostat_interval), int(options.random_seed))
    m, pdb, system, simulation, nonbonded = _build_simulation_objects(record, integrator=integrator, barostat=barostat)
    unit_energy = m["kilojoules_per_mole"]
    if options.minimize_before:
        simulation.minimizeEnergy(tolerance=10.0 * unit_energy / m["nanometer"], maxIterations=500)
    simulation.context.setVelocitiesToTemperature(float(options.temperature_k) * m["kelvin"], int(options.random_seed))

    ensure_dirs(); SIMULATION_DIR.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    dcd_path = SIMULATION_DIR / f"md_{token}.dcd"
    # DCD is the standards-friendly research trajectory. Protein Lab also records a compact NPZ cache
    # containing the exact displayed/report frames for native playback and RMSD/RMSF analysis.
    simulation.reporters.append(m["DCDReporter"](str(dcd_path), int(options.report_interval)))

    samples: list[MDSample] = []
    frames_angstrom: list[np.ndarray] = []

    def capture_sample(step: int) -> MDSample:
        state = simulation.context.getState(getEnergy=True, getPositions=True)
        potential = float(state.getPotentialEnergy().value_in_unit(unit_energy))
        kinetic = float(state.getKineticEnergy().value_in_unit(unit_energy))
        positions_nm = np.asarray(state.getPositions(asNumpy=True).value_in_unit(m["nanometer"]), dtype=float)
        frames_angstrom.append(positions_nm * 10.0)
        sample = MDSample(
            step=int(step),
            time_ps=float(step) * options.timestep_fs / 1000.0,
            potential_kj_mol=potential,
            kinetic_kj_mol=kinetic,
            total_kj_mol=potential + kinetic,
        )
        samples.append(sample)
        return sample

    initial = capture_sample(0)
    if progress:
        progress(0, options.steps, initial)

    completed = 0
    while completed < options.steps:
        if cancelled and cancelled():
            raise RuntimeError(f"Molecular dynamics cancelled after {completed} of {options.steps} steps.")
        chunk = min(options.report_interval, options.steps - completed)
        simulation.step(int(chunk))
        completed += int(chunk)
        sample = capture_sample(completed)
        if progress:
            progress(completed, options.steps, sample)

    final_state = simulation.context.getState(getEnergy=True, getPositions=True)
    temp = CACHE_DIR / f"md_final_{token}.pdb"
    with temp.open("w", encoding="utf-8") as handle:
        m["PDBFile"].writeFile(pdb.topology, final_state.getPositions(), handle)

    log_path = SIMULATION_DIR / f"md_{token}.csv"
    with log_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["step", "time_ps", "potential_kJ_mol", "kinetic_kJ_mol", "total_kJ_mol"])
        for s in samples:
            writer.writerow([s.step, f"{s.time_ps:.10g}", f"{s.potential_kj_mol:.12g}", f"{s.kinetic_kj_mol:.12g}", f"{s.total_kj_mol:.12g}"])

    trajectory_path = SIMULATION_DIR / f"md_{token}.npz"
    np.savez_compressed(
        trajectory_path,
        coordinates_angstrom=np.asarray(frames_angstrom, dtype=np.float32),
        steps=np.asarray([s.step for s in samples], dtype=np.int64),
        times_ps=np.asarray([s.time_ps for s in samples], dtype=np.float64),
        potential_kj_mol=np.asarray([s.potential_kj_mol for s in samples], dtype=np.float64),
        kinetic_kj_mol=np.asarray([s.kinetic_kj_mol for s in samples], dtype=np.float64),
        total_kj_mol=np.asarray([s.total_kj_mol for s in samples], dtype=np.float64),
        topology_pdb=np.asarray(str(pdb_path_for_vtk(record))),
    )

    platform_name = simulation.context.getPlatform().getName()
    metadata = dict(record.metadata)
    metadata.update({
        "parent_protein": record.name,
        "parent_record_id": record.id,
        "simulation_ready": "true",
        "calculation": f"OpenMM {ensemble} molecular dynamics",
        "integrator": "LangevinMiddleIntegrator (LFMiddle)",
        "ensemble": ensemble,
        "temperature_K": f"{options.temperature_k:.6g}",
        "friction_per_ps": f"{options.friction_per_ps:.6g}",
        "timestep_fs": f"{options.timestep_fs:.6g}",
        "steps": str(options.steps),
        "simulated_time_ps": f"{options.steps * options.timestep_fs / 1000.0:.10g}",
        "random_seed": str(options.random_seed),
        "minimized_before_md": str(bool(options.minimize_before)),
        "platform": platform_name,
        "nonbonded_method": nonbonded,
        "state_log_csv": str(log_path),
        "trajectory_npz": str(trajectory_path),
        "trajectory_dcd": str(dcd_path),
        "trajectory_frames": str(len(samples)),
    })
    if ensemble == "NPT":
        metadata.update({
            "pressure_bar": f"{options.pressure_bar:.6g}",
            "barostat": "OpenMM MonteCarloBarostat",
            "barostat_interval_steps": str(options.barostat_interval),
        })
    final_record = register_generated_structure(
        temp,
        name=f"{record.name} — {ensemble} MD {options.steps * options.timestep_fs / 1000.0:g} ps",
        origin="dynamics",
        description=f"Final coordinate snapshot from a real OpenMM {ensemble} Langevin-middle molecular-dynamics run; full trajectory retained.",
        metadata=metadata,
    )
    temp.unlink(missing_ok=True)
    return MDResult(
        record=final_record,
        samples=samples,
        log_path=str(log_path),
        trajectory_path=str(trajectory_path),
        dcd_path=str(dcd_path),
        frame_count=len(samples),
        platform=platform_name,
        temperature_k=options.temperature_k,
        timestep_fs=options.timestep_fs,
        steps=options.steps,
        simulated_time_ps=options.steps * options.timestep_fs / 1000.0,
        ensemble=ensemble,
        pressure_bar=options.pressure_bar if ensemble == "NPT" else None,
    )
