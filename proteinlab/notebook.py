from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".proteinlab")) / "ProteinLab"
NOTEBOOK_JSON = APP_DATA / "experiment_notebook.json"


@dataclass(slots=True)
class ExperimentEntry:
    id: str
    timestamp_utc: str
    action: str
    protein_id: str
    protein_name: str
    method: str
    parameters: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_entries() -> list[ExperimentEntry]:
    if not NOTEBOOK_JSON.exists():
        return []
    try:
        raw = json.loads(NOTEBOOK_JSON.read_text(encoding="utf-8"))
        return [ExperimentEntry(**item) for item in raw]
    except Exception:
        return []


def save_entries(entries: list[ExperimentEntry]) -> None:
    APP_DATA.mkdir(parents=True, exist_ok=True)
    tmp = NOTEBOOK_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps([e.to_dict() for e in entries], indent=2, default=str), encoding="utf-8")
    tmp.replace(NOTEBOOK_JSON)


def append_entry(*, action: str, protein_id: str, protein_name: str, method: str, parameters: dict | None = None, results: dict | None = None, notes: str = "") -> ExperimentEntry:
    entries = load_entries()
    entry = ExperimentEntry(
        id=uuid.uuid4().hex[:12],
        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        action=action,
        protein_id=protein_id,
        protein_name=protein_name,
        method=method,
        parameters=dict(parameters or {}),
        results=dict(results or {}),
        notes=notes,
    )
    entries.append(entry)
    save_entries(entries)
    return entry


def methods_text(entries: list[ExperimentEntry], *, protein_id: str | None = None) -> str:
    selected = [e for e in entries if protein_id is None or e.protein_id == protein_id]
    if not selected:
        return "No recorded computational operations are available for this selection."
    lines = ["Protein Lab computational methods", "", "Automatically generated from recorded settings; verify before publication.", ""]
    for e in selected:
        params = ", ".join(f"{k}={v}" for k, v in e.parameters.items()) or "default/recorded settings"
        result = ", ".join(f"{k}={v}" for k, v in e.results.items())
        sentence = f"{e.action}: {e.method} was applied to {e.protein_name} with {params}."
        if result:
            sentence += f" Recorded outputs: {result}."
        lines.append(sentence)
    return "\n".join(lines)
