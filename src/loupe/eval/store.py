"""Results store: one row per (item, arm, model, config) in DuckDB, full answers as JSON files.

Kept in its own database (data/processed/results.duckdb) so experiment writes never
lock the facts database the tools read.
"""

import json
from pathlib import Path

import duckdb

from loupe.core.schemas import Answer
from loupe.eval.schema import ResultRow

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    run_id VARCHAR PRIMARY KEY, item_id VARCHAR, dataset VARCHAR, arm VARCHAR, model VARCHAR,
    config_hash VARCHAR, answer VARCHAR, correct DOUBLE, supported_rate DOUBLE,
    hallucinated BOOLEAN, abstained BOOLEAN, retrieval_recall DOUBLE, tokens INTEGER,
    latency_ms INTEGER, cost_usd DOUBLE, error VARCHAR, created_at TIMESTAMP, meta JSON
)
"""
COLUMNS = list(ResultRow.model_fields)


class ResultStore:
    def __init__(self, db_path: Path, runs_dir: Path):
        self.db_path = db_path
        self.runs_dir = runs_dir
        db_path.parent.mkdir(parents=True, exist_ok=True)
        runs_dir.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(db_path)) as con:
            con.execute(SCHEMA)

    def done(self, config_hash: str) -> set[str]:
        with duckdb.connect(str(self.db_path), read_only=True) as con:
            rows = con.execute(
                "SELECT item_id FROM results WHERE config_hash = ? AND error IS NULL", [config_hash]
            ).fetchall()
        return {r[0] for r in rows}

    def add(self, row: ResultRow, answer: Answer | None) -> None:
        values = [json.dumps(row.meta) if c == "meta" else getattr(row, c) for c in COLUMNS]
        with duckdb.connect(str(self.db_path)) as con:
            con.execute(
                f"INSERT OR REPLACE INTO results ({', '.join(COLUMNS)}) "
                f"VALUES ({', '.join('?' * len(COLUMNS))})",
                values,
            )
        if answer is not None:
            (self.runs_dir / f"{row.run_id}.json").write_text(answer.model_dump_json())

    def answer(self, run_id: str) -> Answer | None:
        path = self.runs_dir / f"{run_id}.json"
        return Answer.model_validate_json(path.read_text()) if path.exists() else None

    def rows(self, where: str = "", params: list | None = None) -> list[dict]:
        with duckdb.connect(str(self.db_path), read_only=True) as con:
            cur = con.execute(f"SELECT * FROM results {where}", params or [])
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
