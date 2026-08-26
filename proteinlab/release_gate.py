from __future__ import annotations

from pathlib import Path
import json
from importlib.metadata import version as distribution_version

from . import __version__


def main() -> int:
    print(f"Protein Lab {__version__} native release-gate import check")

    import Bio  # noqa: F401
    import PySide6  # noqa: F401
    import certifi  # noqa: F401
    import gemmi  # noqa: F401
    import numpy  # noqa: F401
    import openmm  # noqa: F401
    import pdbfixer  # noqa: F401
    import PeptideBuilder  # noqa: F401
    import vtk  # noqa: F401

    from openmm.app import ForceField, Modeller
    from . import app as app_module  # noqa: F401
    from .tools import TOOLS

    if __version__ != "1.0.3":
        raise RuntimeError(f"Expected public release version 1.0.3, got {__version__}")
    unavailable = [tool.key for tool in TOOLS if not tool.available]
    if unavailable:
        raise RuntimeError(f"Public Toolbox contains unavailable tools: {', '.join(unavailable)}")

    ForceField("amber19-all.xml", "tip3p.xml")
    ForceField("amber14-all.xml", "amber14/tip3p.xml")
    if not hasattr(Modeller, "addMembrane"):
        raise RuntimeError("OpenMM Modeller.addMembrane is unavailable")

    root = Path(__file__).resolve().parents[1]
    lock_path = root / "RUNTIME_LOCK.json"
    if not lock_path.exists():
        raise RuntimeError("Required runtime lock is missing: RUNTIME_LOCK.json")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    for package, expected in lock.get("packages", {}).items():
        actual = distribution_version(package)
        if actual != expected:
            raise RuntimeError(f"Runtime dependency mismatch for {package}: expected {expected}, got {actual}")
    for rel in (
        "assets/ProteinLab.ico",
        "assets/ProteinLab_splash.png",
        "docs/USER_GUIDE.md",
        "docs/INSTALLATION.md",
        "RUNTIME_LOCK.json",
    ):
        if not (root / rel).exists():
            raise RuntimeError(f"Required public-release resource is missing: {rel}")

    print("[PASS] Native GUI/science imports")
    print("[PASS] Runtime dependency versions match RUNTIME_LOCK.json")
    print("[PASS] OpenMM protein and membrane force-field resources")
    print("[PASS] All public Toolbox tools enabled")
    print("[PASS] Public release assets/documentation present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
