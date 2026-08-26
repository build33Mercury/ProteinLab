from __future__ import annotations

import json
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from .library import USER_STRUCTURES, ensure_dirs, save_user_library
from .models import ProteinRecord
from .notebook import ExperimentEntry

PROJECT_FORMAT_VERSION = 1


def save_project(path: Path, records: list[ProteinRecord], notebook: list[ExperimentEntry], *, current_id: str | None = None) -> None:
    path = path.with_suffix(".plab") if path.suffix.lower() != ".plab" else path
    manifest = {
        "format": "Protein Lab Project",
        "version": PROJECT_FORMAT_VERSION,
        "current_record_id": current_id,
        "records": [],
        "notebook": [e.to_dict() for e in notebook],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for record in records:
            if record.origin == "builtin" or not record.file_path.exists():
                continue
            arc = f"structures/{record.file_path.name}"
            z.write(record.file_path, arc)
            item = record.to_dict()
            item["path"] = arc
            manifest["records"].append(item)
        z.writestr("project.json", json.dumps(manifest, indent=2))


def load_project(path: Path, existing_records: list[ProteinRecord]) -> tuple[list[ProteinRecord], list[ExperimentEntry], str | None]:
    ensure_dirs()
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("project.json").decode("utf-8"))
        if manifest.get("format") != "Protein Lab Project":
            raise ValueError("This is not a Protein Lab project file.")
        token = uuid.uuid4().hex[:8]
        new_records: list[ProteinRecord] = []
        id_map: dict[str, str] = {}
        for item in manifest.get("records", []):
            arc = item["path"]
            suffix = Path(arc).suffix.lower()
            target = USER_STRUCTURES / f"project_{token}_{Path(arc).name}"
            with z.open(arc) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            old_id = item["id"]
            new_id = f"user:project:{uuid.uuid4().hex[:10]}"
            id_map[old_id] = new_id
            item = dict(item)
            item["id"] = new_id
            item["path"] = str(target)
            item["origin"] = "project"
            md = dict(item.get("metadata", {}))
            md["project_import_source"] = str(path)
            md["project_original_id"] = old_id
            item["metadata"] = md
            new_records.append(ProteinRecord.from_dict(item))
        merged = [*new_records, *existing_records]
        save_user_library(merged)
        notebook = []
        for raw in manifest.get("notebook", []):
            raw = dict(raw)
            if raw.get("protein_id") in id_map:
                raw["protein_id"] = id_map[raw["protein_id"]]
            notebook.append(ExperimentEntry(**raw))
        current = id_map.get(manifest.get("current_record_id"), None)
        return merged, notebook, current
