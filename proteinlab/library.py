from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path

from .models import ProteinRecord

APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".proteinlab")) / "ProteinLab"
USER_STRUCTURES = APP_DATA / "structures"
CACHE_DIR = APP_DATA / "cache"
LIBRARY_JSON = APP_DATA / "library.json"

BUILTINS = [
    ("1CRN", "Crambin", "Small 46-residue protein; useful for geometry and viewport tests."),
    ("1UBQ", "Ubiquitin", "Compact protein with alpha-helical and beta-sheet secondary structure."),
    ("1MBN", "Myoglobin", "Classic alpha-helical globular protein with a heme cofactor."),
    ("4HHB", "Hemoglobin", "Tetrameric hemoglobin; useful for multi-chain structure viewing."),
    ("1LYZ", "Lysozyme", "Enzyme containing alpha helices, beta structure, and disulfide bonds."),
    ("1L2Y", "Trp-cage", "20-residue NMR miniprotein; useful for small-protein structure and sampling exercises."),
    ("1VII", "Villin headpiece", "Small helical villin headpiece subdomain; useful for compact-fold examples."),
    ("1AKE", "Adenylate kinase", "Enzyme complex containing a nucleotide-like inhibitor; useful for ligand-pocket analysis."),
    ("1BRS", "Barnase–barstar", "Protein-protein complex for chain-interface and recognition exercises."),
    ("2PTC", "Trypsin–BPTI", "Protease-inhibitor complex for active-site and protein-interface analysis."),
    ("1ATP", "Protein kinase complex", "cAMP-dependent protein kinase complex with nucleotide and peptide inhibitor."),
    ("1F88", "Rhodopsin", "Membrane GPCR structure for transmembrane-protein viewing and membrane workflows."),
    ("1TIM", "Triosephosphate isomerase", "Classic enzyme fold useful for secondary-structure and multimer analysis."),
]



def ensure_dirs() -> None:
    USER_STRUCTURES.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip()).strip("._")
    return stem or "protein"


def builtins_from_project(project_root: Path) -> list[ProteinRecord]:
    records: list[ProteinRecord] = []
    for pdb_id, name, description in BUILTINS:
        path = project_root / "data" / "builtins" / f"{pdb_id}.pdb"
        records.append(
            ProteinRecord(
                id=f"builtin:{pdb_id}",
                name=name,
                path=str(path),
                format="pdb",
                origin="builtin",
                pdb_id=pdb_id,
                description=description,
                metadata={"source": "RCSB PDB", "accession": pdb_id},
            )
        )
    return records


def load_user_library() -> list[ProteinRecord]:
    ensure_dirs()
    if not LIBRARY_JSON.exists():
        return []
    try:
        data = json.loads(LIBRARY_JSON.read_text(encoding="utf-8"))
        records = [ProteinRecord.from_dict(item) for item in data]
        return [r for r in records if r.file_path.exists()]
    except Exception:
        return []


def save_user_library(records: list[ProteinRecord]) -> None:
    ensure_dirs()
    tmp = LIBRARY_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps([r.to_dict() for r in records], indent=2), encoding="utf-8")
    tmp.replace(LIBRARY_JSON)


def import_structure(source: Path) -> ProteinRecord:
    ensure_dirs()
    suffix = source.suffix.lower()
    if suffix not in {".pdb", ".cif", ".mmcif"}:
        raise ValueError("Supported structure files are PDB, CIF, and mmCIF.")
    fmt = "pdb" if suffix == ".pdb" else "mmcif"
    token = uuid.uuid4().hex[:10]
    target = USER_STRUCTURES / f"{_safe_stem(source.stem)}_{token}{suffix}"
    shutil.copy2(source, target)
    return ProteinRecord(
        id=f"user:{token}",
        name=source.stem.replace("_", " "),
        path=str(target),
        format=fmt,
        origin="imported",
        description=f"Imported from {source.name}",
        metadata={"imported_from": source.name},
    )


def register_generated_structure(
    source: Path,
    *,
    name: str,
    origin: str = "generated",
    description: str = "",
    metadata: dict[str, str] | None = None,
) -> ProteinRecord:
    """Copy a generated PDB into persistent My Proteins storage and return its record."""
    ensure_dirs()
    if source.suffix.lower() != ".pdb":
        raise ValueError("Generated structures must currently be PDB files.")
    token = uuid.uuid4().hex[:10]
    target = USER_STRUCTURES / f"{_safe_stem(name)}_{token}.pdb"
    shutil.copy2(source, target)
    return ProteinRecord(
        id=f"user:{token}",
        name=name.strip() or "Custom protein",
        path=str(target),
        format="pdb",
        origin=origin,  # type: ignore[arg-type]
        description=description,
        metadata=dict(metadata or {}),
    )


def remove_user_record(record: ProteinRecord, records: list[ProteinRecord]) -> list[ProteinRecord]:
    if record.origin == "builtin":
        return records
    try:
        record.file_path.unlink(missing_ok=True)
    except OSError:
        pass
    updated = [r for r in records if r.id != record.id]
    save_user_library(updated)
    return updated
