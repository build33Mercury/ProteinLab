from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

StructureFormat = Literal["pdb", "mmcif"]
ProteinOrigin = Literal["builtin", "imported", "generated", "predicted", "prepared", "minimized", "dynamics", "mutated", "conformer", "project"]


@dataclass(slots=True)
class ProteinRecord:
    id: str
    name: str
    path: str
    format: StructureFormat
    origin: ProteinOrigin
    pdb_id: str | None = None
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def file_path(self) -> Path:
        return Path(self.path)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProteinRecord":
        # Backward compatible with alpha.2/alpha.3 library.json records.
        return cls(
            id=data["id"],
            name=data["name"],
            path=data["path"],
            format=data["format"],
            origin=data.get("origin", "imported"),
            pdb_id=data.get("pdb_id"),
            description=data.get("description", ""),
            metadata=dict(data.get("metadata", {})),
        )
