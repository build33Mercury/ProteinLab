from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from proteinlab import __version__
from proteinlab.analysis import _kabsch_align
from proteinlab.builder import normalize_amino_sequence, translate_coding_dna
from proteinlab.geometry import angle, dihedral, distance
from proteinlab.help_content import TOPICS
from proteinlab.library import BUILTINS, import_structure
from proteinlab.models import ProteinRecord
from proteinlab.projects import save_project
from proteinlab.structure import inspect_structure
from proteinlab.tools import TOOLS
from proteinlab.validation import run_validation_suite


class GeometryTests(unittest.TestCase):
    def test_distance_345(self):
        self.assertAlmostEqual(distance((0, 0, 0), (3, 4, 0)), 5.0, places=12)

    def test_right_angle(self):
        self.assertAlmostEqual(angle((1, 0, 0), (0, 0, 0), (0, 1, 0)), 90.0, places=10)

    def test_signed_dihedral(self):
        self.assertAlmostEqual(dihedral((1, 0, 0), (0, 0, 0), (0, 1, 0), (0, 1, 1)), -90.0, places=10)

    def test_undefined_angle_rejected(self):
        with self.assertRaises(ValueError):
            angle((0, 0, 0), (0, 0, 0), (1, 0, 0))


class SequenceTests(unittest.TestCase):
    def test_translation_terminal_stop(self):
        dna, aa = translate_coding_dna("ATGGCTTAA")
        self.assertEqual(dna, "ATGGCTTAA")
        self.assertEqual(aa, "MA")

    def test_internal_stop_rejected(self):
        with self.assertRaises(ValueError):
            translate_coding_dna("ATGTAAGCT")

    def test_nonstandard_amino_acid_rejected(self):
        with self.assertRaises(ValueError):
            normalize_amino_sequence("ACDZ")


class AlignmentTests(unittest.TestCase):
    def test_kabsch_removes_rigid_transform(self):
        reference = np.array([[0.,0.,0.],[2.,0.,0.],[0.,1.,0.],[0.,0.,3.]])
        rot = np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
        mobile = reference @ rot.T + np.array([4.2,-2.1,7.0])
        aligned = _kabsch_align(mobile, reference)
        rmsd = np.sqrt(np.mean(np.sum((aligned-reference)**2, axis=1)))
        self.assertLess(rmsd, 1e-10)


class ProductIntegrityTests(unittest.TestCase):
    def test_builtin_ids_unique(self):
        ids = [row[0] for row in BUILTINS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_tool_keys_unique(self):
        keys = [tool.key for tool in TOOLS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_help_topic_keys_unique(self):
        keys = [topic.key for topic in TOPICS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_help_has_core_workflows(self):
        keys = {topic.key for topic in TOPICS}
        required = {"quick-start","toolbox","import","create","fold","prepare","energy","minimize","md","trajectory","rmsd","rmsf","mutation","validation-center","tool-reference","troubleshooting"}
        self.assertTrue(required <= keys)

    def test_empty_structure_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "empty.pdb"
            path.write_text("HEADER EMPTY\nEND\n", encoding="ascii")
            record = ProteinRecord(id="user:empty", name="Empty", path=str(path), format="pdb", origin="imported")
            with self.assertRaises(ValueError):
                inspect_structure(record)

    def test_unsupported_import_extension_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "not_a_structure.txt"
            p.write_text("hello", encoding="utf-8")
            with self.assertRaises(ValueError):
                import_structure(p)

    def test_project_archive_contains_manifest_and_structure(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            structure = td / "tiny.pdb"
            structure.write_text("ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n", encoding="ascii")
            record = ProteinRecord(id="user:test", name="Tiny", path=str(structure), format="pdb", origin="imported")
            out = td / "test.plab"
            save_project(out, [record], [], current_id=record.id)
            import zipfile
            with zipfile.ZipFile(out) as z:
                self.assertIn("project.json", z.namelist())
                self.assertTrue(any(name.startswith("structures/") for name in z.namelist()))

    def test_core_validation_suite_passes_without_runtime(self):
        root = Path(__file__).resolve().parents[1]
        report = run_validation_suite(root, include_runtime=False, include_builtins=False)
        self.assertEqual(report.fail_count, 0, report.to_text())

    def test_public_version_is_stable(self):
        self.assertEqual(__version__, "1.0.3")
        self.assertNotIn("alpha", __version__.lower())
        self.assertNotIn("rc", __version__.lower())


    def test_public_requirements_are_pinned(self):
        root = Path(__file__).resolve().parents[1]
        lines = [line.strip() for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertTrue(lines)
        self.assertTrue(all("==" in line and not any(op in line for op in (">=", "<=", "~=", ">", "<")) for line in lines), lines)

    def test_runtime_lock_present(self):
        import json
        root = Path(__file__).resolve().parents[1]
        lock = json.loads((root / "RUNTIME_LOCK.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["python"]["version"], "3.13.15")
        self.assertEqual(lock["packages"]["openmm"], "8.4.0")

    def test_all_public_tools_are_available(self):
        unavailable = [tool.key for tool in TOOLS if not tool.available]
        self.assertEqual(unavailable, [])

    def test_release_assets_present(self):
        root = Path(__file__).resolve().parents[1]
        for rel in (
            "assets/ProteinLab.ico",
            "assets/ProteinLab_splash.png",
            "proteinlab/startup.py",
            "docs/INSTALLATION.md",
            "LICENSE",
        ):
            self.assertTrue((root / rel).exists(), rel)


if __name__ == "__main__":
    unittest.main()
