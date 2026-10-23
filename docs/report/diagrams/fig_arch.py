"""Chapter 3-4 figures: SDLC, implementation plan, existing and proposed architecture."""

from lib import (
    FS, F, INK, KINDS, MUTED, actor, arrow, box, bullets, cylinder, group, text, tw,
)


def fig01_sdlc():
    """Section 3.6: iterative and incremental model with a research loop."""
    W, H = 1200, 700
    b = []
    b.append(box(20, 30, 240, 105, "Requirements", ["problem statement,", "data, users"], "ext"))
    b.append(box(310, 30, 240, 105, "Design", ["architecture, HLD,", "hypotheses fixed"], "core"))
    b.append(arrow([(260, 82), (308, 82)]))

    b.append(group(600, 20, 580, 470, "Iterative build (one increment per phase)", "core"))
    cyc = [(640, 95, "Implement", ["code + unit tests"]), (920, 95, "Pilot on dev split", ["8 dev companies"]),
           (920, 330, "Analyse errors", ["miss analysis, logs"]), (640, 330, "Tune once", ["same effort per method"])]
    for x, y, t, sub in cyc:
        b.append(box(x, y, 230, 100, t, sub, "core"))
    b.append(arrow([(870, 145), (918, 145)]))
    b.append(arrow([(1035, 195), (1035, 328)]))
    b.append(arrow([(920, 380), (872, 380)]))
    b.append(arrow([(755, 330), (755, 197)]))
    b.append(text(895, 255, "repeat until the", FS, "middle", "normal", MUTED))
    b.append(text(895, 280, "phase's “done when”", FS, "middle", "normal", MUTED))
    b.append(text(895, 305, "check passes", FS, "middle", "normal", MUTED))
    b.append(arrow([(550, 82), (575, 82), (575, 145), (638, 145)]))

    # increments panel
    fill, stroke = KINDS["neutral"]
    b.append(f'<rect x="20" y="180" width="530" height="310" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    b.append(text(42, 220, "Increments", F, "start", "bold"))
    b.append(bullets(42, 258, [
        "P0  Setup, model check, pre-registration",
        "P1  US data layer: EDGAR, XBRL, search index",
        "P2  Thin end-to-end answer + Bench skeleton",
        "P3  All methods, full toolset, event extraction",
        "P4  Datasets: public benchmarks + Loupe-Gold",
        "P5  Experiments, ablations, model sweep",
        "P6  India data swap with the same harness",
    ], size=FS + 1, gap=1.68, max_w=500))

    b.append(box(640, 560, 250, 110, "Final evaluation", ["test split, used once,", "95% confidence intervals"], "eval"))
    b.append(box(930, 560, 250, 110, "Report and demo", ["Bench, results,", "viva"], "ext"))
    b.append(arrow([(765, 490), (765, 558)]))
    b.append(arrow([(890, 615), (928, 615)]))
    b.append(box(20, 540, 530, 130, "", [], "white", dashed=True))
    b.append(text(42, 578, "Why this model", F, "start", "bold"))
    b.append(text(42, 612, "Each phase ships a working increment. Prompts are tuned", FS, "start", "normal", MUTED))
    b.append(text(42, 640, "on dev companies only; test companies stay unseen.", FS, "start", "normal", MUTED))
    return W, H, b


def fig02_implementation_plan():
    """Section 3.7: phases, what each delivers, and status today."""
    rows = [
        ("P0", "Setup and pre-registration", "Repo, LLM gateway, live model check, 25-company universe, hypotheses draft", "done"),
        ("P1", "US data layer", "1,409 filings, 488,147 XBRL facts, 123,889-chunk search index (GPU build)", "done"),
        ("P2", "Thin end-to-end + Bench", "A question becomes a cited answer in the web Bench (FastAPI + React)", "done"),
        ("P3", "Methods, tools, events", "6 baseline methods + Loupe-Orch v1, 9 harness tools, 8-K event extraction", "done"),
        ("P4", "Evaluation datasets", "11 public benchmarks converted; Loupe-Gold 1,329 items; human audit", "progress"),
        ("P5", "Experiments", "Dev pilots, then the test-split matrix, ablations and model sweep", "progress"),
        ("P6", "India swap", "NSE / BSE adapters for 10–20 companies, same harness and Bench", "planned"),
    ]
    status = {"done": ("Done", "data"), "progress": ("In progress", "ext"), "planned": ("Planned", "neutral")}
    W, rh, gap = 1200, 104, 18
    H = 30 + len(rows) * (rh + gap) + 30
    b = [f'<line x1="62" y1="40" x2="62" y2="{H - 50}" stroke="#000" stroke-width="1.5"/>']
    for i, (pid, title, deliver, st) in enumerate(rows):
        y = 30 + i * (rh + gap)
        label, kind = status[st]
        fill, stroke = KINDS[kind]
        b.append(f'<circle cx="62" cy="{y + rh / 2}" r="26" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        b.append(text(62, y + rh / 2 + 7, pid, F - 1, "middle", "bold", stroke))
        b.append(f'<rect x="110" y="{y}" width="1070" height="{rh}" rx="4" fill="#fff" stroke="{stroke}" stroke-width="1.5"/>')
        b.append(text(134, y + 42, title, F, "start", "bold"))
        b.append(text(134, y + 78, deliver, FS + 1, "start", "normal", MUTED))
        pw = tw(label, FS, True) + 34
        b.append(f'<rect x="{1160 - pw}" y="{y + 18}" width="{pw}" height="34" rx="17" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        b.append(text(1160 - pw / 2, y + 41, label, FS, "middle", "normal", stroke))
    return W, H, b


def fig03_existing_architecture():
    """Section 4.1: FARE (Chakraborty et al., IEEE Access 2026), as described in the paper."""
    W, H = 1200, 915
    b = []
    # offline dataset construction
    b.append(group(20, 20, 370, 640, "Dataset construction", "data"))
    b.append(box(50, 80, 310, 80, "168 earnings-call\ntranscripts", kind="ext"))
    b.append(box(50, 205, 310, 95, "Chunking + metadata", ["chunk_id, company,", "quarter, year"], "data"))
    b.append(box(50, 345, 310, 95, "Sentence embeddings", ["all-MiniLM-L6-v2, 384-d"], "data"))
    b.append(cylinder(50, 485, 310, 140, "FAISS vector store", ["IndexFlatL2 (exact L2)"]))
    for y0, y1 in ((160, 205), (300, 345), (440, 485)):
        b.append(arrow([(205, y0), (205, y1)]))

    # online agent workflow
    b.append(group(410, 20, 770, 640, "Agent workflow (LangGraph)", "core"))
    b.append(actor(475, 72, "User"))
    b.append(box(560, 80, 590, 95, "Orchestrator Agent",
                 ["single-intent LLM routing: exactly one agent per query"]))
    b.append(arrow([(503, 120), (558, 120)]))
    b.append(group(430, 215, 730, 225, "Six specialist agents (one is chosen)", "core", dashed=False,
                   label_size=FS + 2, fill="#ffffff"))
    names = ["Tone", "Tone Shift", "Investment", "Simulation", "Comparison", "Statement\nExtraction"]
    for i, n in enumerate(names):
        x, y = 450 + (i % 3) * 235, 262 + (i // 3) * 88
        b.append(box(x, y, 215, 72, n, kind="core", size=F - 1))
    b.append(arrow([(855, 175), (855, 215)]))
    b.append(box(430, 478, 730, 85, "LLM generation backbone",
                 ["Gemini 2.5 Flash · Gemini 2.5 Flash-Lite · Qwen2.5-7B · Llama-3.2-3B"], "neutral"))
    b.append(arrow([(795, 440), (795, 478)]))
    b.append(box(430, 588, 450, 62, "Answer to the user", ["narrative, with hold / re-evaluate / sell advice"],
                 "ext", size=F - 1, sub_size=FS - 1))
    b.append(box(900, 588, 260, 62, "LLM-as-a-judge", ["one evaluator per agent"], "eval",
                 size=F - 1, sub_size=FS - 1))
    b.append(arrow([(655, 563), (655, 588)]))
    b.append(arrow([(1030, 563), (1030, 588)]))
    # retrieval from every agent
    b.append(arrow([(430, 400), (400, 400), (400, 555), (362, 555)], dashed=True))
    b.append(text(205, 648, "each agent retrieves top-k = 10", FS, "middle", "normal", MUTED))

    # limitations
    b.append(f'<rect x="20" y="690" width="1160" height="205" rx="6" fill="none" '
             f'stroke="#000" stroke-width="1.5"/>')
    b.append(text(44, 728, "Limitations relevant to this project", F, "start", "bold"))
    b.append(bullets(44, 768, [
        "Earnings-call transcripts only: no 10-K / 10-Q filings, 8-K events or exact XBRL numbers",
        "Single-intent routing: a question needing lookup + comparison still goes to one agent",
        "No numeric tools: the LLM reads the text and computes every number itself",
        "No code check that each claim matches its source; quality is judged by LLMs only",
        "Produces hold / sell style recommendations rather than verifiable, cited analysis",
    ], size=F - 2, max_w=1120))
    return W, H, b


def fig04_proposed_architecture():
    """Section 4.2: Loupe, layer by layer."""
    W, H = 1200, 1475
    b = []
    # users
    b.append(box(150, 20, 380, 80, "Financial analyst", ["asks questions, reads cited answers"], "ext"))
    b.append(box(670, 20, 380, 80, "Research team / examiners", ["compare methods and models"], "ext"))
    b.append(arrow([(340, 100), (340, 140)]))
    b.append(arrow([(860, 100), (860, 140)]))

    # interface
    b.append(group(20, 140, 1160, 150, "Interface", "neutral"))
    b.append(box(50, 185, 640, 90, "React Bench (web app)",
                 ["Chat · Compare · Leaderboard · Models · Runs · Datasets"], "core"))
    b.append(box(760, 185, 390, 90, "FastAPI service", ["REST: chat, compare, results"], "core"))
    b.append(arrow([(690, 230), (758, 230)], start_head="arr"))
    b.append(arrow([(955, 275), (955, 330)]))

    # orchestration
    b.append(group(20, 330, 1160, 248, "Loupe-Orch v1: our orchestration", "core"))
    steps = [("Router", ["intents,", "company, year"]), ("Planner", ["typed plan", "(ReWOO style)"]),
             ("Executors", ["call tools,", "fill ledger"]), ("Composer", ["claims that", "cite [E#]"]),
             ("Verifier", ["code check +", "LLM critic"]), ("Abstain", ["say what is", "missing"])]
    xs = [40 + i * 191.6 for i in range(6)]
    for x, (t, s) in zip(xs, steps, strict=True):
        b.append(box(x, 385, 162, 105, t, s, "warn" if t == "Verifier" else "core"))
    for x in xs[:-1]:
        b.append(arrow([(x + 162, 437), (x + 191.6, 437)]))
    cx_comp, cx_ver = xs[3] + 81, xs[4] + 81
    b.append(arrow([(cx_ver, 385), (cx_ver, 366), (cx_comp, 366), (cx_comp, 383)],
                   label="revise once", at=((cx_comp + cx_ver) / 2, 372)))
    b.append(box(xs[2], 510, xs[4] + 162 - xs[2], 50, "Evidence ledger [E1] … [En], each with its citation",
                 kind="data", size=FS + 1))
    b.append(arrow([(xs[2] + 81, 490), (xs[2] + 81, 508)]))
    b.append(arrow([(cx_ver, 510), (cx_ver, 492)]))

    # harness, evaluation, gateway
    b.append(group(20, 618, 560, 250, "Financial tool harness (built by us)", "core"))
    tools = ["Filing search (hybrid)", "Exact XBRL facts", "Company comparison", "Calculator",
             "Charts", "Forecasts", "Distress (Altman Z″)", "8-K risk events"]
    for i, t in enumerate(tools):
        x, y = 40 + (i % 2) * 270, 672 + (i // 2) * 47
        b.append(box(x, y, 250, 38, t, kind="white", size=FS + 1, bold=False, rx=6, sw=1.6))
    b.append(group(600, 618, 280, 250, "Evaluation", "eval"))
    for i, t in enumerate(["Experiment runner", "Metrics + LLM judge", "Bootstrap 95% CIs"]):
        b.append(box(620, 668 + i * 64, 240, 50, t, kind="eval", size=FS + 2))
    b.append(group(900, 618, 280, 250, "LLM gateway", "core"))
    b.append(box(920, 668, 240, 80, "LiteLLM", ["cache · rate limits"], "core"))
    b.append(box(920, 765, 240, 85, "Free-tier models", ["Gemma 4, GPT-OSS,", "Nemotron, Ministral"], "ext"))
    b.append(arrow([(300, 578), (300, 616)]))
    b.append(arrow([(1040, 578), (1040, 616)]))
    b.append(arrow([(740, 616), (740, 580)], label="runs every method", at=(740, 603)))

    # storage
    b.append(group(20, 905, 1160, 182, "Data and storage", "data"))
    cyl = [("Search index", ["123,889 chunks", "dense + BM25"]),
           ("Facts and events", ["488,147 XBRL facts", "2,326 8-K events"]),
           ("Evaluation sets", ["11 public benchmarks", "Loupe-Gold, 1,329 items"]),
           ("Results store", ["scores + answers", "with citations"])]
    for i, (t, s) in enumerate(cyl):
        b.append(cylinder(40 + i * 285, 952, 255, 120, t, s))
    b.append(arrow([(275, 868), (275, 950)]))
    b.append(arrow([(452, 868), (452, 950)]))
    b.append(arrow([(700, 868), (700, 950)]))
    b.append(arrow([(850, 868), (850, 890), (1022, 890), (1022, 950)]))

    # ingestion
    b.append(group(20, 1125, 1160, 158, "Ingestion pipeline (offline)", "data"))
    ing = [("Load facts", ["XBRL facts,", "8-K item codes"]), ("SEC client", ["filings + XBRL,", "≤ 8 req/s"]),
           ("Parse", ["HTML → text,", "Items, exhibits"]), ("Chunk", ["1,200 chars,", "150 overlap"]),
           ("Embed + BM25", ["bge-small", "(GPU build)"])]
    ixs = [40 + i * 230 for i in range(5)]
    for x, (t, s) in zip(ixs, ing, strict=True):
        b.append(box(x, 1172, 200, 95, t, s, "data"))
    b.append(arrow([(ixs[1], 1219), (ixs[0] + 202, 1219)]))
    for x in ixs[1:-1]:
        b.append(arrow([(x + 200, 1219), (x + 228, 1219)]))
    b.append(arrow([(600, 1125), (600, 1089)], label="builds", at=(655, 1113)))

    # external
    b.append(group(20, 1320, 1160, 142, "External sources", "ext"))
    ext = [("SEC EDGAR", ["1,409 filings, FY2023–25"], False), ("XBRL company facts", ["SEC API"], False),
           ("Public benchmarks", ["FinanceBench, FinDER, …"], False), ("India: NSE / BSE", ["planned"], True)]
    for i, (t, s, d) in enumerate(ext):
        b.append(box(40 + i * 286, 1366, 262, 80, t, s, "ext", dashed=d))
    b.append(arrow([(600, 1320), (600, 1285)]))

    return W, H, b


FIGURES = {
    "fig01_sdlc": fig01_sdlc,
    "fig02_implementation_plan": fig02_implementation_plan,
    "fig03_existing_architecture": fig03_existing_architecture,
    "fig04_proposed_architecture": fig04_proposed_architecture,
}
