from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import gemmi

from .library import CACHE_DIR, ensure_dirs
from .models import ProteinRecord

AA3 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "SEC": "U", "PYL": "O",
}


@dataclass(slots=True, frozen=True)
class AtomRecord:
    index: int
    model: int
    chain: str
    residue_name: str
    residue_number: str
    atom_name: str
    element: str
    x: float
    y: float
    z: float
    occupancy: float
    b_factor: float
    altloc: str = ""

    @property
    def coord(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def label(self) -> str:
        chain = self.chain or "?"
        return f"{chain}:{self.residue_name}{self.residue_number}:{self.atom_name}"


@dataclass(slots=True)
class StructureInfo:
    models: int
    chains: int
    residues: int
    atoms: int
    sequence_length: int
    sequences: dict[str, str]
    atom_records: list[AtomRecord]


def read_structure(record: ProteinRecord) -> gemmi.Structure:
    path = record.file_path
    if not path.exists():
        raise FileNotFoundError(f"Structure file not found: {path}")
    return gemmi.read_structure(str(path))


def _seqid_text(residue: gemmi.Residue) -> str:
    try:
        number = str(residue.seqid.num)
        icode = str(residue.seqid.icode).strip()
        return f"{number}{icode}" if icode else number
    except Exception:
        return "?"


def inspect_structure(record: ProteinRecord) -> StructureInfo:
    st = read_structure(record)
    model_count = len(st)
    chain_count = residue_count = atom_count = 0
    sequences: dict[str, str] = {}
    atom_records: list[AtomRecord] = []
    if model_count:
        model = st[0]
        for chain in model:
            chain_count += 1
            seq: list[str] = []
            for residue in chain:
                residue_count += 1
                aa = AA3.get(residue.name.upper())
                if aa:
                    seq.append(aa)
                for atom in residue:
                    # Only the first model is rendered/inspected in this phase.
                    pos = atom.pos
                    atom_records.append(
                        AtomRecord(
                            index=atom_count,
                            model=0,
                            chain=chain.name or "?",
                            residue_name=residue.name.upper(),
                            residue_number=_seqid_text(residue),
                            atom_name=atom.name.strip(),
                            element=atom.element.name if atom.element else "?",
                            x=float(pos.x),
                            y=float(pos.y),
                            z=float(pos.z),
                            occupancy=float(atom.occ),
                            b_factor=float(atom.b_iso),
                            altloc=str(atom.altloc).strip(),
                        )
                    )
                    atom_count += 1
            if seq:
                sequences[chain.name or "?"] = "".join(seq)
    if model_count == 0 or atom_count == 0:
        raise ValueError("The structure contains no readable atomic coordinates.")
    return StructureInfo(
        models=model_count,
        chains=chain_count,
        residues=residue_count,
        atoms=atom_count,
        sequence_length=sum(len(s) for s in sequences.values()),
        sequences=sequences,
        atom_records=atom_records,
    )


def pdb_path_for_vtk(record: ProteinRecord) -> Path:
    """Return a PDB file because vtkPDBReader is the ribbon-rendering input."""
    if record.format == "pdb":
        return record.file_path
    ensure_dirs()
    digest = hashlib.sha256(record.file_path.read_bytes()).hexdigest()[:16]
    target = CACHE_DIR / f"{record.file_path.stem}_{digest}.pdb"
    if not target.exists():
        st = read_structure(record)
        st.write_pdb(str(target))
    return target
