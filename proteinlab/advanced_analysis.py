from __future__ import annotations

import csv
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .analysis import TrajectoryData, compute_rmsd
from .library import APP_DATA
from .models import ProteinRecord
from .structure import AA3, AtomRecord, inspect_structure

ANALYSIS_DIR = APP_DATA / "analyses"
R_KJ_MOL_K = 0.00831446261815324

# Standard atomic masses (Da) for the common biomolecular elements used here.
_MASS = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998403163,
    "NA": 22.98976928, "MG": 24.305, "P": 30.973761998, "S": 32.06, "CL": 35.45,
    "K": 39.0983, "CA": 40.078, "MN": 54.938044, "FE": 55.845, "CO": 58.933194,
    "NI": 58.6934, "CU": 63.546, "ZN": 65.38, "SE": 78.971, "BR": 79.904,
    "I": 126.90447,
}


@dataclass(slots=True)
class RadiusOfGyrationSeries:
    values_angstrom: np.ndarray
    atom_indices: np.ndarray
    atom_selection: str


@dataclass(slots=True)
class FreeEnergyLandscape:
    rmsd_centers_angstrom: np.ndarray
    rg_centers_angstrom: np.ndarray
    free_energy_kj_mol: np.ndarray
    counts: np.ndarray
    temperature_k: float
    bins: int
    output_npz: str


@dataclass(slots=True)
class ContactEdge:
    residue_a: str
    residue_b: str
    occupancy: float
    mean_distance_angstrom: float
    minimum_distance_angstrom: float


@dataclass(slots=True)
class ContactNetworkResult:
    threshold_angstrom: float
    minimum_occupancy: float
    frames: int
    node_count: int
    edges: list[ContactEdge] = field(default_factory=list)
    degree: dict[str, int] = field(default_factory=dict)
    weighted_degree: dict[str, float] = field(default_factory=dict)
    output_csv: str = ""


def _protein_heavy_atom_indices(record: ProteinRecord) -> tuple[np.ndarray, np.ndarray]:
    atoms = inspect_structure(record).atom_records
    indices: list[int] = []
    masses: list[float] = []
    for atom in atoms:
        if atom.residue_name not in AA3:
            continue
        symbol = atom.element.strip().upper()
        if symbol == "H" or atom.atom_name.upper().startswith("H"):
            continue
        mass = _MASS.get(symbol)
        if mass is None:
            raise ValueError(f"No atomic mass is registered for element '{atom.element}' in the radius-of-gyration analysis.")
        indices.append(atom.index)
        masses.append(mass)
    if not indices:
        raise ValueError("No protein heavy atoms were found for radius-of-gyration analysis.")
    return np.asarray(indices, dtype=int), np.asarray(masses, dtype=float)


def compute_radius_of_gyration(record: ProteinRecord, trajectory: TrajectoryData) -> RadiusOfGyrationSeries:
    indices, masses = _protein_heavy_atom_indices(record)
    if trajectory.atom_count <= int(indices.max()):
        raise ValueError("Trajectory atom count does not match the structure used for radius-of-gyration analysis.")
    coords = trajectory.coordinates_angstrom[:, indices, :]
    total_mass = float(masses.sum())
    centers = np.sum(coords * masses[None, :, None], axis=1) / total_mass
    delta = coords - centers[:, None, :]
    rg2 = np.sum(masses[None, :] * np.sum(delta * delta, axis=2), axis=1) / total_mass
    return RadiusOfGyrationSeries(np.sqrt(np.maximum(rg2, 0.0)), indices, "protein heavy atoms")


def compute_free_energy_landscape(
    record: ProteinRecord,
    trajectory: TrajectoryData,
    *,
    temperature_k: float,
    bins: int = 24,
) -> FreeEnergyLandscape:
    if temperature_k <= 0:
        raise ValueError("Free-energy landscape temperature must be positive.")
    if bins < 6 or bins > 100:
        raise ValueError("Histogram bins must be between 6 and 100.")
    if trajectory.frame_count < 4:
        raise ValueError("At least four stored trajectory frames are required for a 2D occupancy landscape.")

    rmsd = compute_rmsd(record, trajectory, selection="Cα atoms", reference_frame=0).values_angstrom
    rg = compute_radius_of_gyration(record, trajectory).values_angstrom
    counts, x_edges, y_edges = np.histogram2d(rmsd, rg, bins=int(bins))
    probability = counts / float(np.sum(counts))
    occupied = probability > 0
    free = np.full_like(probability, np.nan, dtype=float)
    pmax = float(probability[occupied].max())
    free[occupied] = -R_KJ_MOL_K * float(temperature_k) * np.log(probability[occupied] / pmax)
    x_centers = 0.5 * (x_edges[:-1] + x_edges[1:])
    y_centers = 0.5 * (y_edges[:-1] + y_edges[1:])

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    target = ANALYSIS_DIR / f"free_energy_landscape_{uuid.uuid4().hex[:12]}.npz"
    np.savez_compressed(
        target,
        rmsd_centers_angstrom=x_centers,
        rg_centers_angstrom=y_centers,
        free_energy_kj_mol=free,
        counts=counts,
        temperature_k=np.asarray(float(temperature_k)),
        bins=np.asarray(int(bins)),
    )
    return FreeEnergyLandscape(x_centers, y_centers, free, counts, float(temperature_k), int(bins), str(target))


def _residue_representatives(atoms: list[AtomRecord]) -> list[tuple[str, str, int, int]]:
    """Return (label, chain, order-within-chain, atom-index), using CB or CA for glycine/fallback."""
    by_residue: dict[tuple[str, str, str], dict[str, AtomRecord]] = {}
    order: list[tuple[str, str, str]] = []
    for atom in atoms:
        if atom.residue_name not in AA3:
            continue
        key = (atom.chain, atom.residue_number, atom.residue_name)
        if key not in by_residue:
            by_residue[key] = {}
            order.append(key)
        by_residue[key][atom.atom_name.upper()] = atom
    chain_order: dict[str, int] = {}
    out: list[tuple[str, str, int, int]] = []
    for chain, number, name in order:
        chain_order[chain] = chain_order.get(chain, 0) + 1
        atom_map = by_residue[(chain, number, name)]
        representative = atom_map.get("CB") or atom_map.get("CA")
        if representative is None:
            continue
        label = f"{chain}:{name}{number}"
        out.append((label, chain, chain_order[chain], representative.index))
    return out


def compute_residue_contact_network(
    record: ProteinRecord,
    trajectory: TrajectoryData | None = None,
    *,
    threshold_angstrom: float = 8.0,
    minimum_occupancy: float = 0.25,
    exclude_adjacent: bool = True,
) -> ContactNetworkResult:
    if threshold_angstrom <= 0:
        raise ValueError("Contact-distance threshold must be positive.")
    if not 0.0 <= minimum_occupancy <= 1.0:
        raise ValueError("Minimum occupancy must be between 0 and 1.")
    atoms = inspect_structure(record).atom_records
    reps = _residue_representatives(atoms)
    if len(reps) < 2:
        raise ValueError("At least two standard amino-acid residues with Cα/Cβ atoms are required.")

    atom_indices = np.asarray([r[3] for r in reps], dtype=int)
    if trajectory is None:
        base = np.asarray([[atoms[i].x, atoms[i].y, atoms[i].z] for i in atom_indices], dtype=float)
        frames = base[None, :, :]
    else:
        if trajectory.atom_count <= int(atom_indices.max()):
            raise ValueError("Trajectory atom count does not match the structure used for contact analysis.")
        frames = trajectory.coordinates_angstrom[:, atom_indices, :]

    edge_rows: list[ContactEdge] = []
    degree = {r[0]: 0 for r in reps}
    weighted = {r[0]: 0.0 for r in reps}
    n_frames = int(frames.shape[0])
    for i in range(len(reps)):
        label_i, chain_i, order_i, _idx_i = reps[i]
        for j in range(i + 1, len(reps)):
            label_j, chain_j, order_j, _idx_j = reps[j]
            if exclude_adjacent and chain_i == chain_j and abs(order_i - order_j) <= 1:
                continue
            d = np.linalg.norm(frames[:, i, :] - frames[:, j, :], axis=1)
            occupancy = float(np.mean(d <= float(threshold_angstrom)))
            if occupancy + 1e-12 < minimum_occupancy:
                continue
            edge = ContactEdge(
                residue_a=label_i,
                residue_b=label_j,
                occupancy=occupancy,
                mean_distance_angstrom=float(np.mean(d)),
                minimum_distance_angstrom=float(np.min(d)),
            )
            edge_rows.append(edge)
            degree[label_i] += 1; degree[label_j] += 1
            weighted[label_i] += occupancy; weighted[label_j] += occupancy
    edge_rows.sort(key=lambda e: (-e.occupancy, e.mean_distance_angstrom, e.residue_a, e.residue_b))

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    target = ANALYSIS_DIR / f"residue_contact_network_{uuid.uuid4().hex[:12]}.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["residue_a", "residue_b", "occupancy", "mean_distance_A", "minimum_distance_A"])
        for e in edge_rows:
            writer.writerow([e.residue_a, e.residue_b, f"{e.occupancy:.12g}", f"{e.mean_distance_angstrom:.12g}", f"{e.minimum_distance_angstrom:.12g}"])

    return ContactNetworkResult(
        threshold_angstrom=float(threshold_angstrom),
        minimum_occupancy=float(minimum_occupancy),
        frames=n_frames,
        node_count=len(reps),
        edges=edge_rows,
        degree=degree,
        weighted_degree=weighted,
        output_csv=str(target),
    )
