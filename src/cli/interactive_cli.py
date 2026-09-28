"""
Interactive Command-Line Interface (REPL) for the FARE Financial Intelligence System.

Features:
- Multi-turn conversational memory with session isolation
- Full FARE multi-agent routing (Extraction, Analysis, Comparison, Risk, Tone, Simulation)
- Pre-generation validation reporting (bounds checking, arithmetic integrity)
- Provenance audit cards (SEC accession number, form, filing date, taxonomy concept)
- Slash commands: /help, /companies, /audit, /validation, /benchmark, /reset, /exit
"""

from __future__ import annotations

import sys
from typing import Optional

from evaluation.benchmark_runner import run_benchmark
from src.data.company_registry import CompanyRegistry, get_registry
from src.pipeline.conversational_pipeline import (
    FinancialIntelligencePipeline,
    PipelineResponse,
    get_default_pipeline,
)


class InteractiveCLI:
    """
    Terminal REPL interface for the financial intelligence system.
    """

    def __init__(
        self,
        pipeline: Optional[FinancialIntelligencePipeline] = None,
        registry: Optional[CompanyRegistry] = None,
        session_id: str = "interactive_session",
    ):
        self.pipeline = pipeline or get_default_pipeline()
        self.registry = registry or get_registry()
        self.session_id = session_id
        self.show_audit = True
        self.show_validation = True

    def print_banner(self) -> None:
        """Displays the startup banner."""
        companies = self.registry.list_companies(include_empty=False)
        banner = [
            "=" * 80,
            "  SEC EDGAR Agent-Orchestrated Financial Intelligence (FARE Architecture)",
            "  Grounding SEC EDGAR Corporate Facts | Deterministic Math | Zero Hallucination",
            "=" * 80,
            f"Loaded {len(companies)} SEC registrants from Data/ (Abbott, AMD, AAR Corp, Aflac, etc.)",
            "Specialized Agents: Statement Extraction | Investment Analysis | Comparison |",
            "                    Risk Distress | Loughran-McDonald Tone | Scenario Simulation",
            "",
            "Type your financial query below, or use slash commands:",
            "  /help       - View detailed usage examples and commands",
            "  /companies  - List indexed SEC companies and CIKs",
            "  /audit      - Toggle SEC provenance audit card display",
            "  /validation - Toggle pre-generation validation check display",
            "  /benchmark  - Run live FARE evaluation suite and display scorecard",
            "  /reset      - Reset dialogue context memory for this session",
            "  /exit       - Quit the application",
            "=" * 80,
        ]
        print("\n".join(banner))

    def print_help(self) -> None:
        """Displays comprehensive query guidance."""
        help_text = [
            "\n" + "=" * 80,
            "  SAMPLE QUERIES BY CAPABILITY",
            "=" * 80,
            "1. Statement Line Item Extraction (Audited Facts):",
            "   - 'What was Abbott\\'s revenue in 2024?'",
            "   - 'How much cash did AMD have in 2023?'",
            "   - 'What was AAR Corp\\'s operating income in 2023?'",
            "",
            "2. Multi-Period Performance Analysis (Trend Evaluation):",
            "   - 'Analyze Abbott\\'s financial performance from 2022 to 2024'",
            "   - 'Evaluate AMD financial trends over time'",
            "",
            "3. Cross-Company Comparison (Multi-Entity Benchmarking):",
            "   - 'Compare Abbott and AMD in 2023'",
            "   - 'Abbott vs AMD margin benchmarking'",
            "",
            "4. Financial Risk Assessment (Distress Signals):",
            "   - 'What financial risks does Abbott face?'",
            "   - 'Assess solvency and leverage risks for AMD'",
            "",
            "5. Managerial Tone & Sentiment Analysis (Loughran-McDonald):",
            "   - 'Analyze management tone for Abbott in 2023'",
            "   - 'Did the tone shift between 2022 and 2023 for Abbott?'",
            "",
            "6. Financial Scenario & Stress Simulation (What-If Sensitivities):",
            "   - 'Simulate a 10% revenue drop for Abbott in 2024'",
            "   - 'Stress test AMD with a 5% inflation shock'",
            "   - 'Calculate operating breakeven for Abbott in 2024'",
            "",
            "7. Conversational Memory (Follow-up Ellipses & Pronouns):",
            "   - 'What was Abbott\\'s revenue in 2023?' -> 'What about 2022?' -> 'What was its net income?'",
            "=" * 80 + "\n",
        ]
        print("\n".join(help_text))

    def list_companies(self) -> None:
        """Prints indexed SEC companies."""
        companies = self.registry.list_companies(include_empty=False)
        print(f"\nIndexed SEC Companies ({len(companies)} filers):")
        print("-" * 70)
        print(f"{'CIK':<12} | {'Entity Name':<45} | {'File'}")
        print("-" * 70)
        for c in companies[:25]:
            print(f"{c.cik:<12} | {c.entity_name[:45]:<45} | {c.filename}")
        if len(companies) > 25:
            print(f"... and {len(companies) - 25} more companies.")
        print("-" * 70 + "\n")

    def handle_command(self, cmd: str) -> bool:
        """
        Executes a slash command. Returns True if command was handled, False otherwise.
        """
        c_clean = cmd.strip().lower()
        if c_clean in ("/help", "/h"):
            self.print_help()
            return True
        elif c_clean in ("/companies", "/list"):
            self.list_companies()
            return True
        elif c_clean == "/audit":
            self.show_audit = not self.show_audit
            status = "ENABLED" if self.show_audit else "DISABLED"
            print(f"\n[Config] SEC Provenance Audit Cards: {status}\n")
            return True
        elif c_clean == "/validation":
            self.show_validation = not self.show_validation
            status = "ENABLED" if self.show_validation else "DISABLED"
            print(f"\n[Config] Pre-generation Validation Checks: {status}\n")
            return True
        elif c_clean == "/benchmark":
            print("\nRunning FARE Benchmark Suite against SEC filings... Please wait.")
            report = run_benchmark()
            print("\n" + report.generate_markdown_scorecard() + "\n")
            return True
        elif c_clean in ("/reset", "/clear"):
            self.pipeline.conversation_manager.reset_session(self.session_id)
            print(f"\n[Memory] Conversational context reset for session '{self.session_id}'.\n")
            return True
        elif c_clean in ("/exit", "/quit", "exit", "quit"):
            print("\nThank you for using the SEC Financial Intelligence System. Goodbye!\n")
            sys.exit(0)
        return False

    def process_input(self, user_query: str) -> str:
        """Processes a single query or command string and returns output text."""
        if not user_query.strip():
            return ""

        if user_query.strip().startswith("/"):
            self.handle_command(user_query)
            return ""

        resp: PipelineResponse = self.pipeline.process_query(
            query=user_query,
            session_id=self.session_id,
            validate=True,
            include_audit=True,
        )

        display_text = resp.format_display(
            include_audit=self.show_audit,
            include_validation=self.show_validation,
        )
        return display_text

    def run_repl(self) -> None:
        """Starts the interactive read-eval-print loop."""
        self.print_banner()

        while True:
            try:
                user_input = input(f"[{self.session_id}] You: ")
                if not user_input.strip():
                    continue

                if user_input.strip().startswith("/") or user_input.strip().lower() in ("exit", "quit"):
                    if self.handle_command(user_input):
                        continue

                print("\nAssistant:")
                output = self.process_input(user_input)
                print(output)
                print()

            except (KeyboardInterrupt, EOFError):
                print("\n\nSession terminated. Goodbye!")
                break
            except Exception as e:
                print(f"\n[Error processing query]: {e}\n")


def main() -> None:
    """Entry point for the interactive CLI."""
    cli = InteractiveCLI()
    cli.run_repl()


if __name__ == "__main__":
    main()
