"""JSON Lines reading that is safe for real-world text.

`str.splitlines()` also splits on Unicode separators (U+2028, U+2029, U+0085, form
feed...) that may appear raw inside JSON strings, cutting records in half. JSONL
records are separated by "\\n" only.
"""

from pathlib import Path


def jsonl_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]
