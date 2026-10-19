# Building the search index on an NVIDIA GPU

**Who this is for:** a teammate with an NVIDIA GPU (written for an RTX 4050 laptop, 6 GB).

**Why:** Loupe's search index has 123,889 text chunks from SEC filings, and each one must be turned into a vector by the `BAAI/bge-small-en-v1.5` model. On an Apple M1 CPU that takes about 5–6 hours: we measured 5.4 chunks/s with all 8 cores. A mid-range NVIDIA GPU should take roughly 10–20 minutes.

**What you produce:** one folder, `data/processed/index/c1200o150-bge-small/`, which you send back. Searches still run on the other machine's CPU; only this one-time bulk embedding needs the GPU.

---

## 1. What you need

- Git, and [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python is installed by uv).
- An NVIDIA driver recent enough for CUDA 12. Check with `nvidia-smi`.
- About 2 GB free disk space.
- **From Ayush:** `chunks.jsonl` (174 MB). It is already chunked, so you do **not** need to download any SEC data.
  - Lines: **123,889**
  - SHA-256: `2616c725bfcb1011a2c86309c3b91b4ffcd000cb7191619886cb01907bf10b8d`

## 2. Get the code

```bash
git clone https://github.com/noNameDS09/BE_PROJECT.git
cd BE_PROJECT
git checkout gpu-embedding-index
uv sync --extra gpu
```

## 3. Install a CUDA build of PyTorch

`uv sync` may install a CPU-only PyTorch, the default on Windows. Replace it with the CUDA 12.4 build:

```bash
uv pip install --reinstall torch --index-url https://download.pytorch.org/whl/cu124
uv run --no-sync python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

The last line must print `True` and your GPU name. From now on, always use `uv run --no-sync …` so uv doesn't put the CPU build back.

## 4. Put the chunks file in place and check it

**macOS / Linux:**
```bash
mkdir -p data/processed/index/c1200o150-bge-small
# copy the received chunks.jsonl into that folder, then:
shasum -a 256 data/processed/index/c1200o150-bge-small/chunks.jsonl
```

**Windows PowerShell:**
```powershell
New-Item -ItemType Directory -Force data\processed\index\c1200o150-bge-small
Get-FileHash data\processed\index\c1200o150-bge-small\chunks.jsonl -Algorithm SHA256
```

The hash must equal `2616c725…0b8d` (full value in section 1).

## 5. Build the index on the GPU

```bash
uv run --no-sync loupe index build --device cuda --from-chunks data/processed/index/c1200o150-bge-small/chunks.jsonl
```

- Progress is logged after each batch of 512 chunks, with elapsed seconds.
- When it finishes, the folder contains:

| File | What it is | Approx. size |
|---|---|---|
| `chunks.jsonl` | the input, rewritten unchanged | 174 MB |
| `dense.npy` | 123,889 × 384 float32 vectors | 190 MB |
| `bm25/` | keyword index | ~100 MB |
| `INFO.json` | `{"chunks": 123889, "embedder": "bge-small", ...}` | tiny |

**If you run out of GPU memory** (an "out of memory" error), lower the batch size: open `src/loupe/index/embed.py` and change `TorchEmbedder(..., batch_size=128)` to `64`.

## 6. Sanity-check before sending

```bash
uv run --no-sync python -c "import numpy as np, json; d=np.load('data/processed/index/c1200o150-bge-small/dense.npy'); print(d.shape, d.dtype, float(np.linalg.norm(d[0]))); print(json.load(open('data/processed/index/c1200o150-bge-small/INFO.json')))"
```

Expected: `(123889, 384) float32 1.0` (the norm may print as 0.99999…), then the INFO dictionary.

## 7. Send it back

Zip the whole `c1200o150-bge-small` folder (`dense.npy`, `bm25/`, `chunks.jsonl`, `INFO.json`) and share it the same way you received the chunks file. Tell Ayush the build time, so it can go in the report.

---

## For Ayush: after receiving the folder

```bash
# unzip into data/processed/index/c1200o150-bge-small/ (replace the folder), then:
echo c1200o150-bge-small > data/processed/index/DEFAULT
uv run loupe index check
uv run loupe search "cybersecurity incident" --company UNH --form 8-K
```

`loupe index check` confirms two things:
- the three files agree on the chunk count;
- a fixed sample of 64 chunks re-embedded locally (ONNX on CPU) has **cosine ≥ 0.99** with the GPU vectors.

That proves the GPU (PyTorch) and CPU (ONNX) versions of the model give the same vectors, so local query embeddings match the stored passage vectors.

## Why this is safe for the research

- **Same model weights:** `BAAI/bge-small-en-v1.5`, the same 512-token limit and the same normalised CLS embeddings. Only the runtime differs (PyTorch CUDA vs ONNX CPU), and `index check` measures the agreement.
- **Unchanged pipeline:** chunking happened once, on the original machine. The GPU step only computes vectors, so chunk ids and character offsets, which citations depend on, stay identical.
- **Recorded:** decision D17 in `docs/decisions.md`.
