"""Evidence ledger for one run: every tool result gets an id ([E1], [E2], ...) the answer cites."""

from typing import Literal

from pydantic import BaseModel, Field

from loupe.core.schemas import Citation


class Evidence(BaseModel):
    id: str
    kind: Literal["chunk", "fact", "calc"]
    text: str  # what the model saw
    citation: Citation
    value: float | None = None  # facts and calculations: the exact number


class Ledger(BaseModel):
    items: dict[str, Evidence] = Field(default_factory=dict)
    charts: list[dict] = Field(default_factory=list)  # {title, figure, evidence_ids}

    def add(self, kind: str, text: str, citation: Citation, value: float | None = None) -> Evidence:
        eid = f"E{len(self.items) + 1}"
        ev = Evidence(id=eid, kind=kind, text=text, citation=citation, value=value)  # type: ignore[arg-type]
        self.items[eid] = ev
        return ev

    def get(self, eid: str) -> Evidence | None:
        return self.items.get(eid)
