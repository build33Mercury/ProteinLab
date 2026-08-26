from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees, sqrt
from pathlib import Path

from Bio.PDB import PDBParser
from Bio.PDB.SASA import ShrakeRupley

from .models import ProteinRecord
from .structure import AtomRecord, inspect_structure, pdb_path_for_vtk


@dataclass(slots=True)
class SASAResidue:
    chain: str
    residue_name: str
    residue_number: str
    sasa_angstrom2: float


@dataclass(slots=True)
class SASAResult:
    total_sasa_angstrom2: float
    residues: list[SASAResidue]
    probe_radius_angstrom: float
    n_points: int


@dataclass(slots=True)
class HydrogenBond:
    donor: str
    hydrogen: str
    acceptor: str
    donor_acceptor_angstrom: float
    hydrogen_acceptor_angstrom: float
    angle_deg: float


@dataclass(slots=True)
class HydrogenBondResult:
    bonds: list[HydrogenBond]
    donor_acceptor_cutoff_angstrom: float
    hydrogen_acceptor_cutoff_angstrom: float
    minimum_angle_deg: float
    note: str


def compute_sasa(record: ProteinRecord, *, probe_radius_angstrom: float = 1.4, n_points: int = 100) -> SASAResult:
    """Calculate solvent-accessible surface area with Biopython's Shrake-Rupley implementation.

    The result is geometric SASA for the stored coordinates and chosen probe/sampling parameters; it is not a
    solvation free energy.
    """
    path = pdb_path_for_vtk(record)
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("proteinlab", str(path))
    sr = ShrakeRupley(probe_radius=float(probe_radius_angstrom), n_points=int(n_points))
    sr.compute(structure, level="R")
    rows: list[SASAResidue] = []
    total = 0.0
    model = next(structure.get_models())
    for chain in model:
        chain_id = str(chain.id).strip() or "?"
        for residue in chain:
            hetflag, seqnum, icode = residue.id
            # Keep standard and modified residues but skip waters.
            if str(residue.get_resname()).strip().upper() in {"HOH", "WAT"}:
                continue
            sasa = float(getattr(residue, "sasa", 0.0))
            total += sasa
            number = f"{seqnum}{str(icode).strip()}" if str(icode).strip() else str(seqnum)
            rows.append(SASAResidue(chain_id, residue.get_resname().strip(), number, sasa))
    return SASAResult(total, rows, float(probe_radius_angstrom), int(n_points))


def _dist(a: AtomRecord, b: AtomRecord) -> float:
    dx, dy, dz = a.x-b.x, a.y-b.y, a.z-b.z
    return sqrt(dx*dx + dy*dy + dz*dz)


def _angle_dha(donor: AtomRecord, hydrogen: AtomRecord, acceptor: AtomRecord) -> float:
    # D-H-A, vertex at hydrogen.
    v1 = (donor.x-hydrogen.x, donor.y-hydrogen.y, donor.z-hydrogen.z)
    v2 = (acceptor.x-hydrogen.x, acceptor.y-hydrogen.y, acceptor.z-hydrogen.z)
    n1 = sqrt(sum(x*x for x in v1)); n2 = sqrt(sum(x*x for x in v2))
    if n1 <= 1e-12 or n2 <= 1e-12:
        return 0.0
    c = max(-1.0, min(1.0, sum(a*b for a,b in zip(v1,v2))/(n1*n2)))
    return degrees(acos(c))


def detect_hydrogen_bonds(
    record: ProteinRecord,
    *,
    donor_acceptor_cutoff_angstrom: float = 3.5,
    hydrogen_acceptor_cutoff_angstrom: float = 2.5,
    minimum_angle_deg: float = 120.0,
) -> HydrogenBondResult:
    """Detect explicit-hydrogen D-H...A contacts from stored coordinates.

    Donors are N/O/S atoms with an explicit H within 1.30 Å. Candidate acceptors are N/O/S atoms. This deliberately
    uses a transparent geometric screen rather than pretending to assign full quantum/chemical H-bond energetics.
    """
    atoms = inspect_structure(record).atom_records
    heavy = [a for a in atoms if a.element.upper() in {"N", "O", "S"}]
    hydrogens = [a for a in atoms if a.element.upper() in {"H", "D"} or a.atom_name.upper().startswith("H")]
    donor_h: list[tuple[AtomRecord, AtomRecord]] = []
    for donor in heavy:
        for h in hydrogens:
            if donor.model != h.model or donor.chain != h.chain or donor.residue_number != h.residue_number:
                continue
            if _dist(donor, h) <= 1.30:
                donor_h.append((donor, h))
    bonds: list[HydrogenBond] = []
    for donor, h in donor_h:
        for acceptor in heavy:
            if acceptor.index == donor.index:
                continue
            # Avoid treating atoms in the same residue as intermolecular H-bonds in this simple screen.
            if acceptor.chain == donor.chain and acceptor.residue_number == donor.residue_number:
                continue
            da = _dist(donor, acceptor)
            if da > donor_acceptor_cutoff_angstrom:
                continue
            ha = _dist(h, acceptor)
            if ha > hydrogen_acceptor_cutoff_angstrom:
                continue
            theta = _angle_dha(donor, h, acceptor)
            if theta < minimum_angle_deg:
                continue
            bonds.append(HydrogenBond(donor.label, h.label, acceptor.label, da, ha, theta))
    note = (
        "Geometric explicit-hydrogen screen: donors are N/O/S atoms with an H/D within 1.30 Å; candidate acceptors are N/O/S. "
        "This does not assign protonation chemistry or hydrogen-bond energies. Prepare/add hydrogens first for meaningful use."
    )
    return HydrogenBondResult(bonds, float(donor_acceptor_cutoff_angstrom), float(hydrogen_acceptor_cutoff_angstrom), float(minimum_angle_deg), note)
