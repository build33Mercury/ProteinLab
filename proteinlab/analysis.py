from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gemmi
import numpy as np

from .library import CACHE_DIR, ensure_dirs
from .models import ProteinRecord
from .structure import inspect_structure, pdb_path_for_vtk


@dataclass(slots=True)
class TrajectoryData:
    coordinates_angstrom: np.ndarray
    steps: np.ndarray
    times_ps: np.ndarray
    potential_kj_mol: np.ndarray
    kinetic_kj_mol: np.ndarray
    total_kj_mol: np.ndarray
    topology_pdb: Path

    @property
    def frame_count(self) -> int:
        return int(self.coordinates_angstrom.shape[0])

    @property
    def atom_count(self) -> int:
        return int(self.coordinates_angstrom.shape[1])


@dataclass(slots=True)
class RMSDSeries:
    values_angstrom: np.ndarray
    atom_indices: np.ndarray
    atom_selection: str
    reference_frame: int


@dataclass(slots=True)
class RMSFSeries:
    values_angstrom: np.ndarray
    labels: list[str]
    atom_indices: np.ndarray
    atom_selection: str


def trajectory_path_for_record(record: ProteinRecord) -> Path | None:
    value = record.metadata.get("trajectory_npz", "").strip()
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def load_trajectory(record: ProteinRecord) -> TrajectoryData:
    path = trajectory_path_for_record(record)
    if path is None:
        raise ValueError("This protein record does not contain an available Protein Lab trajectory.")
    with np.load(path, allow_pickle=False) as data:
        coords = np.asarray(data["coordinates_angstrom"], dtype=float)
        steps = np.asarray(data["steps"], dtype=int)
        times = np.asarray(data["times_ps"], dtype=float)
        potential = np.asarray(data["potential_kj_mol"], dtype=float)
        kinetic = np.asarray(data["kinetic_kj_mol"], dtype=float)
        total = np.asarray(data["total_kj_mol"], dtype=float)
        topology_pdb_text = str(data["topology_pdb"].item()) if "topology_pdb" in data else str(pdb_path_for_vtk(record))
    if coords.ndim != 3 or coords.shape[2] != 3:
        raise ValueError("Trajectory coordinates have an invalid shape; expected frames × atoms × 3.")
    n = coords.shape[0]
    if not all(len(arr) == n for arr in (steps, times, potential, kinetic, total)):
        raise ValueError("Trajectory metadata arrays do not have the same number of frames as the coordinates.")
    return TrajectoryData(coords, steps, times, potential, kinetic, total, Path(topology_pdb_text))


def _kabsch_align(mobile: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Return mobile coordinates least-squares aligned to reference using the Kabsch rotation."""
    mobile = np.asarray(mobile, dtype=float)
    reference = np.asarray(reference, dtype=float)
    if mobile.shape != reference.shape or mobile.ndim != 2 or mobile.shape[1] != 3:
        raise ValueError("Kabsch alignment needs equally shaped N×3 coordinate arrays.")
    mob_center = mobile.mean(axis=0)
    ref_center = reference.mean(axis=0)
    x = mobile - mob_center
    y = reference - ref_center
    covariance = x.T @ y
    u, _s, vt = np.linalg.svd(covariance)
    d = np.sign(np.linalg.det(u @ vt))
    correction = np.eye(3)
    correction[-1, -1] = d
    rotation = u @ correction @ vt
    return x @ rotation + ref_center


def selection_indices(record: ProteinRecord, selection: str = "Cα atoms") -> tuple[np.ndarray, list[str]]:
    info = inspect_structure(record)
    atoms = info.atom_records
    normalized = selection.strip().lower()
    if normalized in {"cα atoms", "ca atoms", "c-alpha", "alpha carbons"}:
        indices = [a.index for a in atoms if a.atom_name.upper() == "CA" and a.residue_name.upper() in {
            "ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL","SEC","PYL"
        }]
        labels = [a.label for a in atoms if a.index in set(indices)]
        if indices:
            return np.asarray(indices, dtype=int), labels
    indices = [a.index for a in atoms]
    labels = [a.label for a in atoms]
    return np.asarray(indices, dtype=int), labels


def compute_rmsd(record: ProteinRecord, trajectory: TrajectoryData, *, selection: str = "Cα atoms", reference_frame: int = 0) -> RMSDSeries:
    indices, _labels = selection_indices(record, selection)
    if len(indices) == 0:
        raise ValueError("No atoms are available for RMSD analysis.")
    if trajectory.atom_count <= int(indices.max()):
        raise ValueError("Trajectory atom count does not match the structure used for analysis.")
    if not 0 <= reference_frame < trajectory.frame_count:
        raise ValueError("RMSD reference frame is out of range.")
    reference = trajectory.coordinates_angstrom[reference_frame, indices, :]
    values = np.zeros(trajectory.frame_count, dtype=float)
    for i in range(trajectory.frame_count):
        mobile = trajectory.coordinates_angstrom[i, indices, :]
        aligned = _kabsch_align(mobile, reference)
        delta = aligned - reference
        values[i] = np.sqrt(np.mean(np.sum(delta * delta, axis=1)))
    return RMSDSeries(values, indices, selection, reference_frame)


def compute_rmsf(record: ProteinRecord, trajectory: TrajectoryData, *, selection: str = "Cα atoms", reference_frame: int = 0) -> RMSFSeries:
    indices, labels = selection_indices(record, selection)
    if len(indices) == 0:
        raise ValueError("No atoms are available for RMSF analysis.")
    if trajectory.atom_count <= int(indices.max()):
        raise ValueError("Trajectory atom count does not match the structure used for analysis.")
    reference = trajectory.coordinates_angstrom[reference_frame, indices, :]
    aligned_frames = np.empty((trajectory.frame_count, len(indices), 3), dtype=float)
    for i in range(trajectory.frame_count):
        mobile = trajectory.coordinates_angstrom[i, indices, :]
        aligned_frames[i] = _kabsch_align(mobile, reference)
    mean_positions = aligned_frames.mean(axis=0)
    displacements = aligned_frames - mean_positions[None, :, :]
    values = np.sqrt(np.mean(np.sum(displacements * displacements, axis=2), axis=0))
    return RMSFSeries(values, labels, indices, selection)


def write_trajectory_frame(record: ProteinRecord, trajectory: TrajectoryData, frame_index: int) -> Path:
    """Write one trajectory frame to a cache PDB for VTK ribbon rendering."""
    if not 0 <= frame_index < trajectory.frame_count:
        raise IndexError("Trajectory frame is out of range.")
    topology_path = trajectory.topology_pdb if trajectory.topology_pdb.exists() else pdb_path_for_vtk(record)
    st = gemmi.read_structure(str(topology_path))
    atoms = []
    if len(st):
        for chain in st[0]:
            for residue in chain:
                for atom in residue:
                    atoms.append(atom)
    coords = trajectory.coordinates_angstrom[frame_index]
    if len(atoms) != coords.shape[0]:
        raise ValueError(f"Trajectory has {coords.shape[0]} atoms but topology contains {len(atoms)} atoms.")
    for atom, xyz in zip(atoms, coords, strict=True):
        atom.pos = gemmi.Position(float(xyz[0]), float(xyz[1]), float(xyz[2]))
    ensure_dirs()
    safe_id = record.id.replace(":", "_").replace("/", "_")
    target = CACHE_DIR / f"trajectory_{safe_id}_frame_{frame_index:06d}.pdb"
    st.write_pdb(str(target))
    return target
