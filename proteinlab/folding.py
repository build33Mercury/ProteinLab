from __future__ import annotations

import ssl
import urllib.error
import urllib.request

import certifi
from dataclasses import dataclass
from pathlib import Path

import gemmi
from PySide6.QtCore import QThread, Signal

from .builder import normalize_amino_sequence
from .library import CACHE_DIR, ensure_dirs, register_generated_structure
from .models import ProteinRecord

ESMFOLD_ENDPOINT = "https://api.esmatlas.com/foldSequence/v1/pdb/"
MAX_AUTO_SEQUENCE_LENGTH = 400


@dataclass(slots=True)
class FoldPredictionResult:
    record: ProteinRecord
    sequence_length: int
    mean_plddt: float | None
    method: str


def _mean_bfactor_as_plddt(path: Path) -> float | None:
    try:
        st = gemmi.read_structure(str(path))
        values: list[float] = []
        if len(st):
            for chain in st[0]:
                for residue in chain:
                    for atom in residue:
                        value = float(atom.b_iso)
                        if 0.0 <= value <= 100.0:
                            values.append(value)
        if not values:
            return None
        return sum(values) / len(values)
    except Exception:
        return None


def predict_esmfold(
    sequence: str,
    *,
    name: str,
    source_record: ProteinRecord | None = None,
    timeout_s: int = 90,
) -> FoldPredictionResult:
    """Predict an all-atom structure from one amino-acid sequence using the public ESM Atlas ESMFold service.

    This is a structure prediction, not a time-resolved folding trajectory. The returned coordinates are
    validated as a PDB before being registered in My Proteins.
    """
    sequence = normalize_amino_sequence(sequence)
    if len(sequence) < 4:
        raise ValueError("Automatic fold prediction requires at least 4 residues.")
    if len(sequence) > MAX_AUTO_SEQUENCE_LENGTH:
        raise ValueError(
            f"Automatic ESMFold prediction is limited to {MAX_AUTO_SEQUENCE_LENGTH} residues in Protein Lab's "
            "rapid workflow. Keep the created chain and use an external/local prediction workflow for longer proteins."
        )

    ensure_dirs()
    request = urllib.request.Request(
        ESMFOLD_ENDPOINT,
        data=sequence.encode("ascii"),
        method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Accept": "text/plain, chemical/x-pdb, */*",
            "User-Agent": "ProteinLab/1.0.3",
        },
    )
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(request, timeout=timeout_s, context=context) as response:
            payload = response.read()
            status = getattr(response, "status", 200)
            if status >= 400:
                raise RuntimeError(f"ESMFold service returned HTTP {status}.")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"ESMFold service returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach the ESMFold prediction service: {exc.reason}") from exc

    text = payload.decode("utf-8", errors="replace")
    if "ATOM" not in text and "HETATM" not in text:
        raise RuntimeError("The ESMFold service did not return a PDB structure.")

    temp = CACHE_DIR / f"esmfold_{source_record.id.replace(':','_') if source_record else 'sequence'}_{len(sequence)}.pdb"
    temp.write_text(text, encoding="utf-8")
    try:
        st = gemmi.read_structure(str(temp))
        if not len(st) or not any(True for _ in st[0]):
            raise RuntimeError("The returned PDB could not be parsed as a protein structure.")
    except Exception as exc:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"The ESMFold response was not a valid PDB: {exc}") from exc

    mean_plddt = _mean_bfactor_as_plddt(temp)
    record = register_generated_structure(
        temp,
        name=f"{name} — predicted fold",
        origin="predicted",
        description=(
            f"ESMFold single-sequence structure prediction for a {len(sequence)}-residue protein. "
            "This is a predicted structure, not an experimentally measured structure and not a molecular-dynamics folding trajectory."
        ),
        metadata={
            "created_from": "amino-acid sequence",
            "amino_acid_sequence": sequence,
            "prediction_method": "ESMFold",
            "prediction_service": "ESM Metagenomic Atlas public fold-sequence service",
            "prediction_endpoint": ESMFOLD_ENDPOINT,
            "source_record_id": source_record.id if source_record else "",
            "source_record_name": source_record.name if source_record else name,
            "mean_plddt_bfactor": f"{mean_plddt:.3f}" if mean_plddt is not None else "not available",
            "scientific_status": "predicted coordinates; not folding trajectory",
        },
    )
    temp.unlink(missing_ok=True)
    return FoldPredictionResult(record=record, sequence_length=len(sequence), mean_plddt=mean_plddt, method="ESMFold")


class FoldPredictionThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, sequence: str, name: str, source_record: ProteinRecord | None, parent=None) -> None:
        super().__init__(parent)
        self.sequence = sequence
        self.name = name
        self.source_record = source_record

    def run(self) -> None:
        try:
            result = predict_esmfold(self.sequence, name=self.name, source_record=self.source_record)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)
