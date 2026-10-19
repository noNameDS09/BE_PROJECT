"""Download public evaluation datasets with provenance.

Each dataset lands in data/raw/public/<name>/ next to a MANIFEST.json that records
where every file came from, its size and sha256, and the licence, so any result
can be traced back to the exact bytes it was computed on.
"""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel

from loupe.core.jsonl import jsonl_lines


class DatasetSpec(BaseModel):
    name: str
    licence: str
    homepage: str
    role: str
    base: str
    files: list[str]
    paper: str | None = None
    defer: bool = False
    extra: str | None = None


def load_specs(path: Path) -> dict[str, DatasetSpec]:
    raw = yaml.safe_load(path.read_text())["datasets"]
    return {name: DatasetSpec(name=name, **cfg) for name, cfg in raw.items()}


def financebench_pdfs(root: Path) -> list[str]:
    """PDF paths for every document referenced by the open-sample questions."""
    questions = root / "data" / "financebench_open_source.jsonl"
    docs = sorted({json.loads(line)["doc_name"] for line in jsonl_lines(questions)})
    return [f"pdfs/{doc}.pdf" for doc in docs]


EXTRAS: dict[str, Callable[[Path], list[str]]] = {"financebench_pdfs": financebench_pdfs}


def _download(http: httpx.Client, url: str, target: Path) -> tuple[int, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    tmp = target.with_suffix(target.suffix + ".part")
    with http.stream("GET", url) as resp, tmp.open("wb") as f:
        resp.raise_for_status()
        for block in resp.iter_bytes(1 << 20):
            f.write(block)
            digest.update(block)
            size += len(block)
    tmp.replace(target)
    return size, digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(
    spec: DatasetSpec,
    root: Path,
    http: httpx.Client,
    refresh: bool = False,
    progress: Callable[[str], None] = lambda _: None,
) -> dict:
    """Fetch every file of `spec` into root/<name>/ and write its MANIFEST.json."""
    out = root / spec.name
    entries = []

    def fetch(rel: str) -> None:
        url = f"{spec.base}/{rel}"
        target = out / rel
        if target.exists() and not refresh:
            size, sha = target.stat().st_size, _sha256(target)
        else:
            progress(rel)
            size, sha = _download(http, url, target)
        entries.append({"path": rel, "url": url, "bytes": size, "sha256": sha})

    for rel in spec.files:
        fetch(rel)
    if spec.extra:
        for rel in EXTRAS[spec.extra](out):
            fetch(rel)

    manifest = {
        "name": spec.name,
        "licence": spec.licence,
        "homepage": spec.homepage,
        "paper": spec.paper,
        "role": spec.role,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": entries,
        "total_bytes": sum(e["bytes"] for e in entries),
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    return manifest
