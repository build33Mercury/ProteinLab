from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from Bio.PDB import PDBIO
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import PeptideBuilder

from .library import CACHE_DIR, ensure_dirs, register_generated_structure
from .models import ProteinRecord

STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

CODON_TABLE = {
    "TTT":"F","TTC":"F","TTA":"L","TTG":"L",
    "TCT":"S","TCC":"S","TCA":"S","TCG":"S",
    "TAT":"Y","TAC":"Y","TAA":"*","TAG":"*",
    "TGT":"C","TGC":"C","TGA":"*","TGG":"W",
    "CTT":"L","CTC":"L","CTA":"L","CTG":"L",
    "CCT":"P","CCC":"P","CCA":"P","CCG":"P",
    "CAT":"H","CAC":"H","CAA":"Q","CAG":"Q",
    "CGT":"R","CGC":"R","CGA":"R","CGG":"R",
    "ATT":"I","ATC":"I","ATA":"I","ATG":"M",
    "ACT":"T","ACC":"T","ACA":"T","ACG":"T",
    "AAT":"N","AAC":"N","AAA":"K","AAG":"K",
    "AGT":"S","AGC":"S","AGA":"R","AGG":"R",
    "GTT":"V","GTC":"V","GTA":"V","GTG":"V",
    "GCT":"A","GCC":"A","GCA":"A","GCG":"A",
    "GAT":"D","GAC":"D","GAA":"E","GAG":"E",
    "GGT":"G","GGC":"G","GGA":"G","GGG":"G",
}


@dataclass(slots=True)
class SequenceAnalysis:
    length: int
    molecular_weight_da: float
    isoelectric_point: float
    aromaticity: float
    gravy: float
    instability_index: float


def _strip_fasta(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(">"):
            continue
        lines.append(line)
    return "".join(lines)


def normalize_amino_sequence(text: str) -> str:
    raw = re.sub(r"[^A-Za-z]", "", _strip_fasta(text)).upper()
    if not raw:
        raise ValueError("Enter an amino-acid sequence.")
    invalid = sorted(set(raw) - STANDARD_AA)
    if invalid:
        raise ValueError(
            "This builder currently supports the 20 standard amino acids only. "
            f"Unsupported code(s): {', '.join(invalid)}"
        )
    return raw


def normalize_coding_dna(text: str) -> str:
    raw = re.sub(r"[^A-Za-z]", "", _strip_fasta(text)).upper()
    if not raw:
        raise ValueError("Enter a coding DNA sequence.")
    invalid = sorted(set(raw) - set("ACGT"))
    if invalid:
        raise ValueError(f"Coding DNA may contain only A, C, G, and T. Invalid: {', '.join(invalid)}")
    if len(raw) % 3:
        raise ValueError(
            f"Coding DNA length is {len(raw)} nt, which is not divisible by 3. "
            "Provide a complete coding sequence in reading frame 0."
        )
    return raw


def translate_coding_dna(text: str) -> tuple[str, str]:
    dna = normalize_coding_dna(text)
    aa: list[str] = []
    codons = [dna[i:i+3] for i in range(0, len(dna), 3)]
    for index, codon in enumerate(codons):
        residue = CODON_TABLE[codon]
        if residue == "*":
            if index != len(codons) - 1:
                raise ValueError(
                    f"Internal stop codon {codon} occurs at codon {index + 1}. "
                    "The input is not a continuous protein-coding sequence in this frame."
                )
            break
        aa.append(residue)
    sequence = "".join(aa)
    if not sequence:
        raise ValueError("The coding DNA does not encode any amino-acid residues before the stop codon.")
    return dna, sequence


def analyze_sequence(sequence: str) -> SequenceAnalysis:
    analysis = ProteinAnalysis(sequence)
    return SequenceAnalysis(
        length=len(sequence),
        molecular_weight_da=float(analysis.molecular_weight()),
        isoelectric_point=float(analysis.isoelectric_point()),
        aromaticity=float(analysis.aromaticity()),
        gravy=float(analysis.gravy()),
        instability_index=float(analysis.instability_index()),
    )


def build_peptide_structure(
    sequence: str,
    *,
    name: str,
    source_kind: str,
    starting_conformation: str = "Extended",
) -> ProteinRecord:
    """Build an idealized heavy-atom peptide model and persist it in My Proteins.

    This is geometry construction, not a folding prediction. PeptideBuilder uses
    amino-acid-specific bond lengths/angles and requested backbone torsions.
    """
    sequence = normalize_amino_sequence(sequence)
    ensure_dirs()

    if starting_conformation == "Alpha helix":
        phi = [-60.0] * max(0, len(sequence) - 1)
        psi = [-45.0] * max(0, len(sequence) - 1)
        structure = PeptideBuilder.make_structure(sequence, phi, psi) if len(sequence) > 1 else PeptideBuilder.initialize_res(sequence[0])
        torsion_note = "Ideal alpha-helical start (phi=-60°, psi=-45°)"
    elif starting_conformation == "Beta strand":
        phi = [-135.0] * max(0, len(sequence) - 1)
        psi = [135.0] * max(0, len(sequence) - 1)
        structure = PeptideBuilder.make_structure(sequence, phi, psi) if len(sequence) > 1 else PeptideBuilder.initialize_res(sequence[0])
        torsion_note = "Ideal beta-strand start (phi=-135°, psi=135°)"
    else:
        structure = PeptideBuilder.make_extended_structure(sequence)
        torsion_note = "Extended start (PeptideBuilder default phi=-120°, psi=140°)"

    PeptideBuilder.add_terminal_OXT(structure)

    temp = CACHE_DIR / f"generated_{uuid.uuid4().hex[:12]}.pdb"
    io = PDBIO()
    io.set_structure(structure)
    io.save(str(temp))

    props = analyze_sequence(sequence)
    record = register_generated_structure(
        temp,
        name=name.strip() or "Custom protein",
        origin="generated",
        description=(
            f"Custom {len(sequence)}-residue peptide/protein model built from {source_kind}. "
            "Initial geometry only; this is not a folding prediction or an energy-minimized structure."
        ),
        metadata={
            "created_from": source_kind,
            "amino_acid_sequence": sequence,
            "builder": "PeptideBuilder 1.1.0",
            "starting_conformation": starting_conformation,
            "geometry_note": torsion_note,
            "hydrogens": "not added yet",
            "molecular_weight_Da_sequence": f"{props.molecular_weight_da:.4f}",
            "isoelectric_point_sequence": f"{props.isoelectric_point:.4f}",
        },
    )
    try:
        temp.unlink(missing_ok=True)
    except OSError:
        pass
    return record
