# Financial Risk Analysis System (FARE Architecture)

An agent-orchestrated financial intelligence and risk analysis system designed to analyze corporate financial data from SEC EDGAR filings and identify financial risks, trends, and performance insights.

Built on the **FARE (Financial Analysis & Retrieval-Augmented Execution)** framework, the system enforces **zero-hallucination** guarantees through deterministic financial math, strict fact-based SEC XBRL/EDGAR data grounding, and SEC accession audit trails.

---

## Key Capabilities

1. **Audited Statement Extraction**: Direct fact extraction from SEC Form 10-K/10-Q filings with accession number provenance, filing dates, and accounting balance checks ($Assets = Liabilities + Equity$).
2. **Deterministic Financial Analysis**: Growth rates, YoY margin trajectories, and profitability metrics computed via exact mathematical formulas rather than LLM generation.
3. **Cross-Company Comparison**: Side-by-side metric tables comparing revenues, net income, margins, and balance sheet strength across indexed SEC registrants.
4. **Distress & Solvency Risk Modeling**: Multi-factor risk signals evaluating liquidity (Current Ratio), solvency/leverage (Debt-to-Equity), operational burn, and margin decay.
5. **Tone Analysis & Scenario Stress-Testing**:
   - Quantitative tone scoring based on Loughran-McDonald financial sentiment lexicons.
   - Deterministic stress simulation simulating revenue and cost shocks with breakeven recalculation.
6. **Multi-Turn Conversational Memory**: Contextual dialogue pipeline resolving temporal ellipses (*"what about 2022?"*), metric ellipses (*"what about net income?"*), and comparative bridging (*"compare with AMD"*).
7. **Pre-Generation Validation Guardrails**: Automatic sanity checks verifying balance sheet equations, non-negative revenues, and unit consistencies before outputs are finalized.

---

## System Architecture

```text
                               +----------------------------+
                               |     User Input / Query     |
                               +--------------+-------------+
                                              |
                                              v
                               +----------------------------+
                               | Conversational Pipeline    |
                               | (Dialogue State & Memory)  |
                               +--------------+-------------+
                                              |
                                              v
                               +----------------------------+
                               |     Agent Orchestrator     |
                               +--------------+-------------+
                                              |
         +--------------------+---------------+--------------------+--------------------+
         |                    |               |                    |                    |
         v                    v               v                    v                    v
  +--------------+    +---------------+ +------------+    +-----------------+    +-----------------+
  | Statement    |    | Investment    | | Comparison |    | Risk Distress   |    | Tone & Scenario |
  | Extraction   |    | Analysis      | | Agent      |    | Agent           |    | Simulation      |
  +-------+------+    +-------+-------+ +-----+------+    +--------+--------+    +--------+--------+
          |                   |               |                    |                      |
          +-------------------+---------------+--------------------+----------------------+
                                              |
                                              v
                               +----------------------------+
                               | Metric Mapper & Retrieval  |
                               +--------------+-------------+
                                              |
                                              v
                               +----------------------------+
                               |   SEC EDGAR Data Store     |
                               |   (42+ Indexed Registrants)|
                               +--------------+-------------+
                                              |
                                              v
                               +----------------------------+
                               | Financial Calculator Tools |
                               | (Deterministic Arithmetic) |
                               +--------------+-------------+
                                              |
                                              v
                               +----------------------------+
                               | Validation & Guardrails    |
                               | (Accounting Invariants)    |
                               +--------------+-------------+
                                              |
                                              v
                               +----------------------------+
                               | Audited Response & Cards   |
                               | (SEC Accession Provenance) |
                               +----------------------------+
```

---

## Repository Structure

```text
BE_PROJECT/
├── Data/                             # SEC EDGAR company facts JSON repository (42+ registrants)
├── evaluation/                       # Ground-truth evaluation benchmark suite
│   ├── benchmark_dataset.py          # 60 ground-truth financial evaluation cases
│   ├── benchmark_runner.py           # Automated evaluation harness
│   ├── metrics.py                    # FARE Composite Score, Grounding, and Math accuracy metrics
│   └── __init__.py
├── src/                              # Core system source code
│   ├── agents/                       # Specialized domain agents
│   │   ├── comparison_agent.py       # Cross-company benchmarking
│   │   ├── investment_agent.py       # Multi-period trend and margin analysis
│   │   ├── orchestrator.py           # Query router and multi-agent dispatcher
│   │   ├── risk_extraction_agent.py  # Solvency, liquidity, and distress analysis
│   │   ├── statement_extraction_agent.py # Primary 10-K/10-Q statement retriever
│   │   ├── tone_simulation_agent.py  # Loughran-McDonald sentiment & stress simulator
│   │   └── __init__.py
│   ├── cli/                          # User interface
│   │   ├── interactive_cli.py        # Interactive terminal REPL with slash commands
│   │   └── __init__.py
│   ├── data/                         # Data ingestion and normalization
│   │   ├── company_registry.py       # Company metadata, ticker, and CIK lookup
│   │   ├── financial_normalizer.py   # Unit scaling ($B, $M, USD) and date formatting
│   │   ├── sec_loader.py             # SEC EDGAR JSON loader with caching
│   │   └── __init__.py
│   ├── explainability/               # Auditability and provenance
│   │   ├── provenance.py             # SEC accession number & filing citation cards
│   │   └── __init__.py
│   ├── memory/                       # Dialogue management
│   │   ├── conversation_state.py     # Multi-turn state, anaphora, and ellipsis tracking
│   │   └── __init__.py
│   ├── pipeline/                     # End-to-end integration
│   │   ├── conversational_pipeline.py # Full pipeline orchestrating memory + agents + validation
│   │   └── __init__.py
│   ├── retrieval/                    # Query routing and metric lookup
│   │   ├── financial_query.py        # Financial query engine and statement extraction
│   │   ├── metric_mapper.py          # US-GAAP taxonomy concept mapping
│   │   └── __init__.py
│   ├── tools/                        # Deterministic computational tools
│   │   ├── financial_calculator.py   # Exact financial arithmetic (growth, margins, ratios)
│   │   ├── scenario_simulator.py     # Deterministic sensitivity and stress testing
│   │   ├── tone_analyzer.py          # Loughran-McDonald financial tone analyzer
│   │   ├── validation.py             # Accounting invariant guardrails
│   │   └── __init__.py
│   └── __init__.py
├── tests/                            # Comprehensive test suite (166 unit and integration tests)
├── file_to_company.json              # SEC filename-to-entity mapping cache
├── requirements.txt                  # Python dependencies
├── Script.py                         # Unified system executable entry point
└── README.md                         # Project documentation
```

---

## Quickstart Guide

### 1. Requirements

- Python 3.10+ (tested on Python 3.11)
- Install test dependencies (optional, system core uses standard library only):
  ```bash
  pip install -r requirements.txt
  ```

### 2. Launch Interactive REPL

Start the interactive terminal session:
```bash
python Script.py
```

Available slash commands within the session:
- `/help` - Display available commands and sample queries
- `/companies` - List all indexed SEC companies, tickers, and CIKs
- `/audit` - Toggle display of SEC filing provenance audit cards
- `/validation` - Toggle display of pre-generation mathematical validation checks
- `/benchmark` - Run live 60-case FARE evaluation suite and render scorecard
- `/reset` - Clear current conversational dialogue memory
- `/exit` - Exit the interactive CLI

### 3. Single Query Execution

Run a single query from the command line and exit:
```bash
python Script.py --query "What was Abbott's revenue in 2024?"
```

### 4. Run Evaluation Benchmark

Run the automated 60-case ground-truth evaluation benchmark:
```bash
python Script.py --benchmark
```

### 5. Update Company Mapping

Re-scan `Data/` to update `file_to_company.json`:
```bash
python Script.py --map
```

---

## Testing

Run the full automated test suite (166 tests across 17 test modules):
```bash
pytest tests/ -v
```

---

## Evaluation Benchmark Performance

The system is evaluated against 60 ground-truth SEC EDGAR test cases covering all 5 specialized agents:

| Metric | Target | Result | Status |
|:---|:---:|:---:|:---:|
| **Grounding Precision** | $\ge 95\%$ | **100.00%** | PASS |
| **Mathematical Accuracy** | $\ge 98\%$ | **100.00%** | PASS |
| **SEC Accession Provenance** | $\ge 90\%$ | **100.00%** | PASS |
| **Routing Accuracy** | $\ge 95\%$ | **100.00%** | PASS |
| **Conversational Resolution** | $\ge 90\%$ | **100.00%** | PASS |
| **Validation Enforcement** | $\ge 98\%$ | **100.00%** | PASS |
| **Composite FARE Score** | $\ge 95\%$ | **100.00%** | **PASS** |

---

## License & Credits

Final Year Project — Developed using the FARE (Financial Analysis & Retrieval-Augmented Execution) framework with grounded data from SEC EDGAR.
