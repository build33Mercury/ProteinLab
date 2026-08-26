from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from .library import CACHE_DIR, ensure_dirs, register_generated_structure
from .models import ProteinRecord
from .structure import pdb_path_for_vtk

STANDARD_AA3 = (
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
)


@dataclass(slots=True)
class MutationResult:
    record: ProteinRecord
    chain: str
    residue_number: str
    original_residue: str
    target_residue: str
    ph: float


def mutate_residue(record: ProteinRecord, *, chain_id: str, residue_number: str, target_residue: str, ph: float = 7.0) -> MutationResult:
    """Create a standard-amino-acid substitution with PDBFixer templates.

    This generates chemically complete starting coordinates for the mutation. It deliberately does not
    claim a stability effect or relaxed mutant structure; users should prepare/minimize/simulate afterward.
    """
    target_residue = target_residue.upper().strip()
    if target_residue not in STANDARD_AA3:
        raise ValueError("Mutation target must be one of the 20 standard amino acids.")
    try:
        from pdbfixer import PDBFixer
        from openmm.app import PDBFile
    except Exception as exc:  # pragma: no cover - native/install dependency
        raise RuntimeError("PDBFixer is unavailable. Rerun the current Protein Lab installer to repair the mutation stack.") from exc

    source = pdb_path_for_vtk(record)
    fixer = PDBFixer(filename=str(source))
    target_chain = next((c for c in fixer.topology.chains() if (c.id or "?") == chain_id), None)
    if target_chain is None:
        raise ValueError(f"Chain {chain_id!r} was not found in the current structure.")
    target = next((r for r in target_chain.residues() if str(r.id) == str(residue_number)), None)
    if target is None:
        raise ValueError(f"Residue {residue_number!r} was not found in chain {chain_id!r}.")
    original = target.name.upper()
    if original not in STANDARD_AA3:
        raise ValueError(f"Residue {chain_id}:{original}{residue_number} is not a standard amino acid and is not mutated by this phase.")
    if original == target_residue:
        raise ValueError("The target amino acid is identical to the current residue.")
    if not str(residue_number).lstrip("-").isdigit():
        raise ValueError("This mutation phase currently requires a numeric PDB residue identifier (no insertion code).")

    fixer.applyMutations([f"{original}-{residue_number}-{target_residue}"], chain_id)
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(float(ph))

    ensure_dirs()
    temp = CACHE_DIR / f"mutant_{uuid.uuid4().hex[:12]}.pdb"
    with temp.open("w", encoding="utf-8") as handle:
        PDBFile.writeFile(fixer.topology, fixer.positions, handle, keepIds=True)

    metadata = dict(record.metadata)
    metadata.update({
        "parent_protein": record.name,
        "parent_record_id": record.id,
        "mutation": f"{chain_id}:{original}{residue_number}{target_residue}",
        "mutation_chain": chain_id,
        "mutation_residue_number": str(residue_number),
        "mutation_original": original,
        "mutation_target": target_residue,
        "mutation_builder": "PDBFixer applyMutations + missing-atom/hydrogen completion",
        "mutation_pH": f"{float(ph):.4g}",
        "geometry_relaxed": "false",
        "simulation_ready": "false",
    })
    mutant = register_generated_structure(
        temp,
        name=f"{record.name} — {original}{residue_number}{target_residue}",
        origin="mutated",
        description="Template-built single-residue mutant. Geometry is not energy-relaxed until minimization/simulation is run.",
        metadata=metadata,
    )
    temp.unlink(missing_ok=True)
    return MutationResult(mutant, chain_id, str(residue_number), original, target_residue, float(ph))
