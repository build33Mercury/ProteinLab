from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from .library import CACHE_DIR, ensure_dirs, register_generated_structure
from .models import ProteinRecord
from .structure import pdb_path_for_vtk

STANDARD_PROTEIN_RESIDUES = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
}


@dataclass(slots=True)
class PreparationOptions:
    ph: float = 7.0
    remove_heterogens: bool = True
    solvate: bool = False
    padding_nm: float = 1.0
    ionic_strength_m: float = 0.15
    forcefield_key: str = "amber19"


@dataclass(slots=True)
class PreparationResult:
    record: ProteinRecord
    original_atoms: int
    prepared_atoms: int
    particles: int
    residues: int
    removed_residues: int


def prepare_simulation_system(record: ProteinRecord, options: PreparationOptions) -> PreparationResult:
    """Create a force-field-validatable OpenMM preparation and save its coordinates.

    This phase prepares coordinates/topology only. It does not run minimization or MD.
    Unsupported or incomplete chemistry raises an error instead of receiving invented parameters.
    """
    try:
        from openmm.app import ForceField, HBonds, Modeller, NoCutoff, PDBFile, PME
        from openmm.unit import molar, nanometer
    except Exception as exc:  # pragma: no cover - depends on installed binary wheel
        raise RuntimeError(
            "OpenMM is not available in this Protein Lab installation. Rerun the current installer to repair dependencies."
        ) from exc

    ensure_dirs()
    pdb_path = pdb_path_for_vtk(record)
    pdb = PDBFile(str(pdb_path))
    original_atoms = sum(1 for _ in pdb.topology.atoms())
    modeller = Modeller(pdb.topology, pdb.positions)

    removed = 0
    if options.remove_heterogens:
        to_delete = []
        for residue in modeller.topology.residues():
            if residue.name.upper() not in STANDARD_PROTEIN_RESIDUES:
                to_delete.append(residue)
        removed = len(to_delete)
        if to_delete:
            modeller.delete(to_delete)

    if not any(True for _ in modeller.topology.residues()):
        raise ValueError("No standard protein residues remain after cleanup.")

    if options.forcefield_key != "amber19":
        raise ValueError(f"Unsupported force-field preset: {options.forcefield_key}")

    # AMBER ff19SB is included through amber19-all.xml; tip3p.xml supplies water/ion templates.
    forcefield = ForceField("amber19-all.xml", "tip3p.xml")

    # OpenMM chooses standard protonation variants consistent with the requested pH where possible.
    modeller.addHydrogens(forcefield, pH=float(options.ph))

    if options.solvate:
        modeller.addSolvent(
            forcefield,
            model="tip3p",
            padding=float(options.padding_nm) * nanometer,
            ionicStrength=float(options.ionic_strength_m) * molar,
            neutralize=True,
        )
        system = forcefield.createSystem(
            modeller.topology,
            nonbondedMethod=PME,
            nonbondedCutoff=1.0 * nanometer,
            constraints=HBonds,
        )
    else:
        system = forcefield.createSystem(
            modeller.topology,
            nonbondedMethod=NoCutoff,
            constraints=HBonds,
        )

    prepared_atoms = sum(1 for _ in modeller.topology.atoms())
    residues = sum(1 for _ in modeller.topology.residues())
    particles = int(system.getNumParticles())
    if particles != prepared_atoms:
        raise RuntimeError(
            f"OpenMM topology/system mismatch: {prepared_atoms} atoms but {particles} force-field particles."
        )

    temp = CACHE_DIR / f"prepared_{uuid.uuid4().hex[:12]}.pdb"
    with temp.open("w", encoding="utf-8") as handle:
        PDBFile.writeFile(modeller.topology, modeller.positions, handle)

    source_label = record.pdb_id or record.name
    metadata = {
        "parent_protein": record.name,
        "parent_record_id": record.id,
        "source_structure": source_label,
        "preparation_engine": "OpenMM 8.4.0",
        "force_field": "AMBER19 / ff19SB protein parameters",
        "water_model": "TIP3P" if options.solvate else "none (vacuum preparation)",
        "hydrogen_pH": f"{options.ph:.2f}",
        "removed_nonstandard_residues": str(removed),
        "explicit_solvation": str(bool(options.solvate)),
        "water_padding_nm": f"{options.padding_nm:.3f}" if options.solvate else "n/a",
        "ionic_strength_M": f"{options.ionic_strength_m:.3f}" if options.solvate else "n/a",
        "validated_forcefield_particles": str(particles),
        "calculation_status": "Topology/parameterization validated; no minimization or MD performed",
        "simulation_ready": "true",
    }

    prepared = register_generated_structure(
        temp,
        name=f"{record.name} — prepared",
        origin="prepared",
        description=(
            "OpenMM-prepared protein system with hydrogens"
            + (", explicit TIP3P solvent and ions" if options.solvate else "")
            + ". Parameterization was validated; dynamics have not been run."
        ),
        metadata=metadata,
    )
    try:
        temp.unlink(missing_ok=True)
    except OSError:
        pass

    return PreparationResult(
        record=prepared,
        original_atoms=original_atoms,
        prepared_atoms=prepared_atoms,
        particles=particles,
        residues=residues,
        removed_residues=removed,
    )
