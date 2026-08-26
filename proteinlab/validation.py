from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import platform
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from . import __version__
from .analysis import _kabsch_align
from .builder import normalize_amino_sequence, translate_coding_dna
from .geometry import angle, dihedral, distance
from .library import BUILTINS


@dataclass(slots=True)
class CheckResult:
    group: str
    name: str
    status: str
    detail: str
    elapsed_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass(slots=True)
class ValidationReport:
    protein_lab_version: str
    python_version: str
    platform: str
    checks: list[CheckResult]

    @property
    def pass_count(self) -> int:
        return sum(c.status == "PASS" for c in self.checks)

    @property
    def fail_count(self) -> int:
        return sum(c.status == "FAIL" for c in self.checks)

    @property
    def warn_count(self) -> int:
        return sum(c.status == "WARN" for c in self.checks)

    @property
    def all_required_passed(self) -> bool:
        return self.fail_count == 0

    def to_dict(self) -> dict:
        return {
            "protein_lab_version": self.protein_lab_version,
            "python_version": self.python_version,
            "platform": self.platform,
            "summary": {"pass": self.pass_count, "warn": self.warn_count, "fail": self.fail_count},
            "checks": [asdict(c) for c in self.checks],
        }

    def to_text(self) -> str:
        lines = [
            f"Protein Lab validation report — {self.protein_lab_version}",
            f"Python: {self.python_version}",
            f"Platform: {self.platform}",
            f"Summary: {self.pass_count} PASS / {self.warn_count} WARN / {self.fail_count} FAIL",
            "",
        ]
        current = None
        for c in self.checks:
            if c.group != current:
                current = c.group
                lines += [current, "-" * len(current)]
            lines.append(f"[{c.status}] {c.name} — {c.detail} ({c.elapsed_ms:.2f} ms)")
        lines += [
            "",
            "Interpretation",
            "--------------",
            "PASS means that this specific deterministic check behaved as expected. It does not prove biological truth, force-field exactness, or convergence of a particular research simulation.",
        ]
        return "\n".join(lines)


def _run(group: str, name: str, fn) -> CheckResult:  # noqa: ANN001
    start = time.perf_counter()
    try:
        detail = fn()
        status = "PASS"
        if isinstance(detail, tuple):
            status, detail = detail
        detail = str(detail or "OK")
    except Exception as exc:
        status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
    return CheckResult(group, name, status, detail, (time.perf_counter() - start) * 1000.0)


def _benchmark_distance() -> str:
    value = distance((0.0, 0.0, 0.0), (3.0, 4.0, 0.0))
    if abs(value - 5.0) > 1e-12:
        raise AssertionError(f"expected 5.0 Å, got {value}")
    return "3-4-5 Euclidean case = 5.000000 Å"


def _benchmark_angle() -> str:
    value = angle((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    if abs(value - 90.0) > 1e-10:
        raise AssertionError(f"expected 90°, got {value}")
    return "orthogonal-vector case = 90.000000°"


def _benchmark_dihedral() -> str:
    value = dihedral((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0, 1.0))
    if abs(value + 90.0) > 1e-10:
        raise AssertionError(f"expected -90°, got {value}")
    return "signed torsion case = -90.000000°"


def _benchmark_kabsch() -> str:
    reference = np.array([[0., 0., 0.], [2., 0., 0.], [0., 1., 0.], [0., 0., 3.]])
    rot = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    mobile = reference @ rot.T + np.array([4.2, -2.1, 7.0])
    aligned = _kabsch_align(mobile, reference)
    rmsd = float(np.sqrt(np.mean(np.sum((aligned - reference) ** 2, axis=1))))
    if rmsd > 1e-10:
        raise AssertionError(f"expected ~0 Å after rigid transform, got {rmsd}")
    return f"rigid rotation+translation recovered; RMSD={rmsd:.3e} Å"


def _benchmark_translation() -> str:
    dna, aa = translate_coding_dna("ATGGCTTAA")
    if dna != "ATGGCTTAA" or aa != "MA":
        raise AssertionError(f"expected MA, got {aa}")
    return "ATG-GCT-TAA translated to MA with terminal stop removed"


def _qa_invalid_amino_acid() -> str:
    try:
        normalize_amino_sequence("ACDZ")
    except ValueError:
        return "unsupported amino-acid code rejected"
    raise AssertionError("invalid sequence was accepted")


def _qa_internal_stop() -> str:
    try:
        translate_coding_dna("ATGTAAGCT")
    except ValueError:
        return "internal stop codon rejected"
    raise AssertionError("internal stop codon was accepted")


def _qa_zero_angle() -> str:
    try:
        angle((0, 0, 0), (0, 0, 0), (1, 0, 0))
    except ValueError:
        return "coincident-point angle rejected"
    raise AssertionError("undefined angle was accepted")


def _dependency_check(label: str, module: str, distribution: str | None = None):
    def check() -> str:
        m = importlib.import_module(module)
        version = getattr(m, "__version__", None)
        if distribution:
            try:
                version = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                pass
        if module == "vtk":
            version = m.vtkVersion().GetVTKVersion()
        return f"imported{f' — version {version}' if version else ''}"
    return _run("Runtime dependencies", label, check)


def _openmm_forcefields() -> str:
    from openmm.app import ForceField, Modeller
    ForceField("amber19-all.xml", "tip3p.xml")
    ForceField("amber14-all.xml", "amber14/tip3p.xml")
    if not hasattr(Modeller, "addMembrane"):
        raise RuntimeError("OpenMM Modeller.addMembrane is unavailable")
    return "AMBER19/TIP3P and membrane-compatible AMBER14 resources loaded"


def _builtin_check(project_root: Path, pdb_id: str, name: str):
    def check():
        path = project_root / "data" / "builtins" / f"{pdb_id}.pdb"
        if not path.exists():
            return "WARN", "not cached locally yet; installer/download can populate it"
        if path.stat().st_size < 100:
            raise ValueError("file is unexpectedly small")
        import gemmi
        st = gemmi.read_structure(str(path))
        atom_count = sum(1 for model in st for chain in model for residue in chain for _atom in residue)
        if atom_count == 0:
            raise ValueError("parsed structure contains no atoms")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        return f"{name}: {atom_count} atoms; SHA256 {digest}…"
    return _run("Built-in structure integrity", pdb_id, check)


def run_validation_suite(project_root: Path, *, include_runtime: bool = True, include_builtins: bool = True) -> ValidationReport:
    checks: list[CheckResult] = []
    checks.extend([
        _run("Deterministic numerical benchmarks", "Euclidean distance", _benchmark_distance),
        _run("Deterministic numerical benchmarks", "Vector angle", _benchmark_angle),
        _run("Deterministic numerical benchmarks", "Signed dihedral", _benchmark_dihedral),
        _run("Deterministic numerical benchmarks", "Kabsch alignment", _benchmark_kabsch),
        _run("Deterministic numerical benchmarks", "Coding-DNA translation", _benchmark_translation),
        _run("Defensive QA", "Invalid amino-acid code", _qa_invalid_amino_acid),
        _run("Defensive QA", "Internal stop codon", _qa_internal_stop),
        _run("Defensive QA", "Undefined angle", _qa_zero_angle),
    ])

    if include_runtime:
        for label, module, dist in (
            ("NumPy", "numpy", "numpy"), ("Biopython", "Bio", "biopython"), ("Gemmi", "gemmi", "gemmi"),
            ("PySide6", "PySide6", "PySide6"), ("VTK", "vtk", "vtk"), ("OpenMM", "openmm", "openmm"),
            ("PDBFixer", "pdbfixer", "pdbfixer"), ("PeptideBuilder", "PeptideBuilder", None), ("Certifi", "certifi", "certifi"),
        ):
            checks.append(_dependency_check(label, module, dist))
        checks.append(_run("Runtime dependencies", "OpenMM force-field resources", _openmm_forcefields))

    if include_builtins:
        for pdb_id, name, _description in BUILTINS:
            checks.append(_builtin_check(project_root, pdb_id, name))

    return ValidationReport(
        protein_lab_version=__version__,
        python_version=sys.version.replace("\n", " "),
        platform=f"{platform.system()} {platform.release()} ({platform.machine()})",
        checks=checks,
    )


def write_validation_report(path: Path, report: ValidationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    else:
        path.write_text(report.to_text(), encoding="utf-8")
