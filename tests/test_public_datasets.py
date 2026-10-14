import hashlib
import json
from pathlib import Path

import httpx

from loupe.datasets.public import DatasetSpec, download, load_specs

QUESTION = b'{"doc_name": "ACME_2023_10K"}\n'
FILES = {
    "https://example.org/ds/data/financebench_open_source.jsonl": QUESTION * 2,
    "https://example.org/ds/pdfs/ACME_2023_10K.pdf": b"%PDF-1.4",
}


def client(calls):
    def handler(request):
        calls.append(str(request.url))
        body = FILES.get(str(request.url))
        return httpx.Response(200, content=body) if body else httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def spec(**kw):
    base = dict(
        name="ds",
        licence="MIT",
        homepage="h",
        role="r",
        base="https://example.org/ds",
        files=["data/financebench_open_source.jsonl"],
    )
    return DatasetSpec(**{**base, **kw})  # fmt: skip


def test_download_writes_files_and_manifest_with_hashes(tmp_path):
    calls = []
    manifest = download(spec(), tmp_path, client(calls))

    body = FILES["https://example.org/ds/data/financebench_open_source.jsonl"]
    assert (tmp_path / "ds" / "data" / "financebench_open_source.jsonl").read_bytes() == body
    entry = manifest["files"][0]
    assert entry["sha256"] == hashlib.sha256(body).hexdigest() and entry["bytes"] == len(body)
    on_disk = json.loads((tmp_path / "ds" / "MANIFEST.json").read_text())
    assert on_disk["licence"] == "MIT" and on_disk["total_bytes"] == len(body)


def test_existing_files_are_not_downloaded_again(tmp_path):
    calls = []
    download(spec(), tmp_path, client(calls))
    download(spec(), tmp_path, client(calls))
    assert len(calls) == 1


def test_financebench_extra_fetches_each_referenced_pdf_once(tmp_path):
    calls = []
    manifest = download(spec(extra="financebench_pdfs"), tmp_path, client(calls))
    assert [f["path"] for f in manifest["files"]] == [
        "data/financebench_open_source.jsonl",
        "pdfs/ACME_2023_10K.pdf",
    ]


def test_repo_dataset_config_is_valid():
    specs = load_specs(Path("configs/datasets.yaml"))
    assert "financebench" in specs and specs["docfinqa"].defer
