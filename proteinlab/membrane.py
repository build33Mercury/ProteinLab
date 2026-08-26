from __future__ import annotations

import uuid
from dataclasses import dataclass

from .library import CACHE_DIR, ensure_dirs, register_generated_structure
from .models import ProteinRecord
from .preparation import STANDARD_PROTEIN_RESIDUES
from .structure import pdb_path_for_vtk


@dataclass(slots=True)
class MembranePreparationOptions:
    lipid_type: str = "POPC"
    minimum_padding_nm: float = 1.0
    ionic_strength_m: float = 0.15
    ph: float = 7.0
    positive_ion: str = "Na+"
    negative_ion: str = "Cl-"
    remove_heterogens: bool = True


@dataclass(slots=True)
class MembranePreparationResult:
    record: ProteinRecord
    atoms: int
    residues: int
    lipid_residues: int
    water_residues: int
    particles: int


def prepare_membrane_system(record: ProteinRecord, options: MembranePreparationOptions) -> MembranePreparationResult:
    """Embed an already oriented protein in an explicit lipid membrane using OpenMM Modeller.addMembrane.

    The protein is assumed to already be oriented with the membrane normal along Z. Protein Lab does not
    infer transmembrane orientation in this phase; that assumption is surfaced in the UI and provenance.
    """
    if options.lipid_type not in {"POPC", "POPE", "DLPC", "DLPE", "DMPC", "DOPC", "DPPC"}:
        raise ValueError("Unsupported built-in lipid type.")
    if options.minimum_padding_nm <= 0:
        raise ValueError("Minimum membrane padding must be positive.")
    if options.ionic_strength_m < 0:
        raise ValueError("Ionic strength cannot be negative.")
    try:
        from openmm.app import ForceField, HBonds, Modeller, PDBFile, PME
        from openmm.unit import molar, nanometer
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("OpenMM membrane-building support is unavailable. Rerun the current Protein Lab installer.") from exc

    ensure_dirs()
    pdb = PDBFile(str(pdb_path_for_vtk(record)))
    modeller = Modeller(pdb.topology, pdb.positions)

    if options.remove_heterogens:
        delete = [r for r in modeller.topology.residues() if r.name.upper() not in STANDARD_PROTEIN_RESIDUES]
        if delete:
            modeller.delete(delete)
    if not any(r.name.upper() in STANDARD_PROTEIN_RESIDUES for r in modeller.topology.residues()):
        raise ValueError("No standard protein residues remain for membrane preparation.")

    # amber14-all includes protein/nucleic-acid/Lipid17 parameters; amber14/tip3p includes compatible water/ions.
    forcefield = ForceField("amber14-all.xml", "amber14/tip3p.xml")
    modeller.addHydrogens(forcefield, pH=float(options.ph))
    modeller.addMembrane(
        forcefield,
        lipidType=options.lipid_type,
        minimumPadding=float(options.minimum_padding_nm) * nanometer,
        positiveIon=options.positive_ion,
        negativeIon=options.negative_ion,
        ionicStrength=float(options.ionic_strength_m) * molar,
        neutralize=True,
    )
    system = forcefield.createSystem(
        modeller.topology,
        nonbondedMethod=PME,
        nonbondedCutoff=1.0 * nanometer,
        constraints=HBonds,
        rigidWater=True,
    )

    atoms = sum(1 for _ in modeller.topology.atoms())
    residues_list = list(modeller.topology.residues())
    residues = len(residues_list)
    lipid_residues = sum(1 for r in residues_list if r.name.upper() == options.lipid_type)
    water_residues = sum(1 for r in residues_list if r.name.upper() in {"HOH", "WAT"})
    particles = int(system.getNumParticles())
    if particles != atoms:
        raise RuntimeError(f"OpenMM topology/system mismatch after membrane construction: {atoms} atoms vs {particles} particles.")

    temp = CACHE_DIR / f"membrane_{uuid.uuid4().hex[:12]}.pdb"
    with temp.open("w", encoding="utf-8") as handle:
        PDBFile.writeFile(modeller.topology, modeller.positions, handle)

    metadata = dict(record.metadata)
    metadata.update({
        "parent_protein": record.name,
        "parent_record_id": record.id,
        "simulation_ready": "true",
        "explicit_solvation": "true",
        "periodic_system": "true",
        "membrane_system": "true",
        "membrane_lipid": options.lipid_type,
        "membrane_minimum_padding_nm": f"{options.minimum_padding_nm:.4g}",
        "ionic_strength_M": f"{options.ionic_strength_m:.4g}",
        "hydrogen_pH": f"{options.ph:.3g}",
        "positive_ion": options.positive_ion,
        "negative_ion": options.negative_ion,
        "forcefield_preset": "amber14_lipid17",
        "force_field": "AMBER14 protein + Lipid17 (amber14-all.xml)",
        "water_model": "AMBER14-compatible TIP3P",
        "membrane_orientation_assumption": "Input protein pre-oriented; membrane plane XY, normal Z",
        "membrane_builder": "OpenMM Modeller.addMembrane",
        "validated_forcefield_particles": str(particles),
    })
    out = register_generated_structure(
        temp,
        name=f"{record.name} — {options.lipid_type} membrane",
        origin="prepared",
        description=f"OpenMM-prepared {options.lipid_type} membrane system with explicit water and ions; input orientation was preserved.",
        metadata=metadata,
    )
    temp.unlink(missing_ok=True)
    return MembranePreparationResult(out, atoms, residues, lipid_residues, water_residues, particles)
