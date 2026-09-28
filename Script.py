"""
SEC EDGAR Financial Intelligence System (FARE Architecture Adaptation).

Executable entry point supporting:
1. Interactive conversational terminal REPL: python Script.py
2. Single-shot query execution: python Script.py --query "What was Abbott's revenue in 2024?"
3. Automated benchmark evaluation: python Script.py --benchmark
4. Legacy filename-to-company mapping: python Script.py --map
"""

import argparse
import json
import os
import sys
from pathlib import Path


def create_filename_to_company_mapping(
    data_dir: str = "Data",
    output_file: str = "file_to_company.json",
    indent: int = 4
) -> dict:
    """
    Scans a directory containing SEC fact JSON files and maps each filename
    to its corresponding company name ('entityName').

    :param data_dir: Directory where the JSON files are stored.
    :param output_file: Output JSON file path where the mapping dictionary will be saved.
    :param indent: Indentation level for the output JSON file.
    :return: Dictionary mapping filename to company name.
    """
    data_path = Path(data_dir)
    if not data_path.exists() or not data_path.is_dir():
        raise FileNotFoundError(f"Directory '{data_dir}' not found.")

    mapping = {}
    json_files = sorted([f for f in data_path.iterdir() if f.suffix.lower() == ".json"])

    print(f"Found {len(json_files)} JSON files in '{data_dir}'. Processing...")

    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extract company name (entityName)
            company_name = data.get("entityName")

            # Map filename -> company name
            mapping[file_path.name] = company_name if company_name else "Unknown"

        except Exception as e:
            print(f"Warning: Could not process {file_path.name}: {e}")
            mapping[file_path.name] = None

    # Save mapping to the output JSON file
    output_path = Path(output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=indent, ensure_ascii=False)

    print(f"Mapping successfully saved to '{output_file}' ({len(mapping)} entries).")
    return mapping


def main():
    parser = argparse.ArgumentParser(
        description="SEC EDGAR Financial Intelligence System (FARE Architecture)"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Run a single financial query through the pipeline and print the response.",
    )
    parser.add_argument(
        "--benchmark", "-b",
        action="store_true",
        help="Execute the full FARE benchmark evaluation suite and print the scorecard.",
    )
    parser.add_argument(
        "--map", "-m",
        action="store_true",
        help="Rebuild file_to_company.json mapping from Data/ directory.",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        default=True,
        help="Include full SEC provenance audit card with query output.",
    )
    parser.add_argument(
        "--validation",
        action="store_true",
        default=True,
        help="Include pre-generation validation report with query output.",
    )

    args = parser.parse_args()

    # Mode 1: Rebuild mapping
    if args.map:
        create_filename_to_company_mapping()
        return

    # Mode 2: Run benchmark
    if args.benchmark:
        from evaluation.benchmark_runner import run_benchmark
        print("\nExecuting FARE Benchmark Suite against SEC filings... Please wait.\n")
        report = run_benchmark()
        print(report.generate_markdown_scorecard())
        return

    # Mode 3: Single query
    if args.query:
        from src.pipeline.conversational_pipeline import process_financial_query
        resp = process_financial_query(args.query, validate=args.validation, include_audit=args.audit)
        print(resp.format_display(include_audit=args.audit, include_validation=args.validation))
        return

    # Mode 4: Default interactive terminal REPL
    from src.cli.interactive_cli import InteractiveCLI
    cli = InteractiveCLI()
    cli.run_repl()


if __name__ == "__main__":
    main()
