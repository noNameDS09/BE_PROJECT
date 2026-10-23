"""Chapter 6 figures: algorithm flowchart, flow of the system, evaluation methodology."""

from lib import F, FS, MUTED, arrow, box, bullets, cylinder, diamond, text

K = "#000"


def pill(cx, y, w, label, h=48):
    return box(cx - w / 2, y, w, h, label, rx=h / 2, size=FS + 1)


def fig14_algorithm():
    """Section 6.2: Loupe-Orch v1 for one question."""
    W, cx, bw = 1200, 600, 500
    b = [pill(cx, 20, 260, "Start: question q")]

    def step(y, t, h=58):
        b.append(box(cx - bw / 2, y, bw, h, t, size=FS + 1))
        return y + h

    def down(y0, y1, label=None):
        b.append(arrow([(cx, y0), (cx, y1)], label, at=(cx - 24, (y0 + y1) / 2 + 6) if label else None))

    down(68, 98)
    y = step(100, "Router (LLM): intents, companies, fiscal years")
    down(y, y + 32)
    d1 = y + 82
    b.append(diamond(cx, d1, 250, 96, "company in\nthe corpus?"))
    b.append(box(880, d1 - 30, 280, 60, "Reply: company not\ncovered by the corpus", size=FS))
    b.append(arrow([(cx + 125, d1), (878, d1)], "no", at=(cx + 160, d1 - 9)))
    b.append(pill(1020, d1 + 62, 120, "End", h=40))
    b.append(arrow([(1020, d1 + 30), (1020, d1 + 60)]))
    down(d1 + 48, d1 + 98, "yes")
    d2 = d1 + 148
    b.append(diamond(cx, d2, 270, 96, "multi-step\nintent?"))
    b.append(box(40, d2 - 30, 300, 60, "Planner writes a typed\nplan (ReWOO style)", size=FS))
    b.append(box(40, d2 + 60, 300, 60, "Execute the plan with\nharness tools", size=FS))
    b.append(arrow([(190, d2 + 30), (190, d2 + 58)]))
    b.append(box(860, d2 - 30, 300, 60, "Short tool loop with\nthe intents' tools", size=FS))
    b.append(arrow([(cx - 135, d2), (342, d2)], "yes", at=(cx - 170, d2 - 9)))
    b.append(arrow([(cx + 135, d2), (858, d2)], "no", at=(cx + 170, d2 - 9)))
    ly = d2 + 170
    b.append(arrow([(190, d2 + 120), (190, ly + 29), (cx - bw / 2 - 2, ly + 29)]))
    b.append(arrow([(1010, d2 + 30), (1010, ly + 29), (cx + bw / 2 + 2, ly + 29)]))
    y = step(ly, "Evidence ledger [E1 … En], each with its citation")
    down(y, y + 30)
    y = step(y + 32, "Composer writes claims, each citing [E#]")
    down(y, y + 30)
    y = step(y + 32, "Code verifier checks numbers and quotes;\nLLM critic flags unsupported claims", h=72)
    down(y, y + 32)
    d3 = y + 82
    b.append(diamond(cx, d3, 270, 96, "any claim\nunsupported?"))
    b.append(box(870, d3 - 30, 290, 60, "Return the cited answer", size=FS + 1))
    b.append(arrow([(cx + 135, d3), (868, d3)], "no", at=(cx + 170, d3 - 9)))
    down(d3 + 48, d3 + 96, "yes")
    y = step(d3 + 98, "Revise once: feedback names the evidence\nthat holds each number", h=72)
    down(y, y + 30)
    y = step(y + 32, "Re-verify; remove claims that still fail")
    down(y, y + 32)
    d4 = y + 82
    b.append(diamond(cx, d4, 250, 96, "anything\nleft?"))
    b.append(box(40, d4 - 30, 300, 60, "Abstain: say what\nis missing", size=FS))
    b.append(arrow([(cx - 125, d4), (342, d4)], "no", at=(cx - 160, d4 - 9)))
    down(d4 + 48, d4 + 96, "yes")
    y = step(d4 + 98, "Return cited answer + removed claims")
    end_y = y + 40
    down(y, end_y)
    b.append(pill(cx, end_y, 160, "End"))
    b.append(arrow([(190, d4 + 30), (190, end_y + 24), (cx - 82, end_y + 24)]))
    b.append(arrow([(1015, d3 + 30), (1015, end_y + 24), (cx + 82, end_y + 24)]))
    return W, end_y + 70, b


def lane(y, h, title):
    return (f'<rect x="20" y="{y}" width="1160" height="{h}" fill="none" stroke="{K}" stroke-width="1.4"/>'
            f'<line x1="62" y1="{y}" x2="62" y2="{y + h}" stroke="{K}" stroke-width="1.4"/>'
            f'<text transform="translate(47 {y + h / 2}) rotate(-90)" font-size="{FS + 1}" '
            f'text-anchor="middle" font-weight="bold">{title}</text>')


def fig15_system_flow():
    """Section 6.3: offline data preparation, online answering, evaluation loop."""
    W = 1200
    X = [80 + i * 184 for i in range(6)]  # six columns, boxes 160 wide
    bw = 160
    b = []

    def chain(y, items, h=74):
        for i, it in enumerate(items):
            if it is None:
                continue
            kind, t = it
            if kind == "cyl":
                b.append(cylinder(X[i], y - 6, bw, h + 12, t))
            else:
                b.append(box(X[i], y, bw, h, t, size=FS, dashed=kind == "ext", rx=0 if kind == "ext" else 4))
        for i in range(len(items) - 1):
            if items[i] is not None and items[i + 1] is not None:
                b.append(arrow([(X[i] + bw, y + h / 2), (X[i + 1] - 2, y + h / 2)]))

    b.append(lane(20, 380, "Offline: data preparation"))
    chain(45, [("ext", "SEC EDGAR\nfilings"), ("p", "Download\n10-K, 10-Q, 8-K"), ("p", "Parse HTML,\nsplit Items"),
               ("p", "Chunk\n1,200 / 150"), ("p", "Embed (GPU)\n+ BM25"), ("cyl", "Search\nindex")])
    chain(170, [("ext", "XBRL company\nfacts"), ("p", "Fiscal calendars,\nmetric map"), ("cyl", "Facts\ntable"),
                ("ext", "8-K item\ncodes"), ("p", "Label events\nby item"), ("cyl", "Events\ntable")])
    chain(295, [("ext", "Public\nbenchmarks"), ("p", "Convert to\none schema"), ("cyl", "Evaluation\nsets"),
                ("p", "Facts + item\ncodes"), ("p", "Loupe-Gold +\ncode check"), ("cyl", "Gold\nsets")])

    b.append(lane(420, 150, "Answering"))
    chain(458, [("ext", "Analyst\nquestion"), ("p", "Route and\nplan"), ("p", "Run harness\ntools"),
                ("p", "Compose with\n[E#] citations"), ("p", "Verify: code\n+ critic"), ("ext", "Cited answer\nin the Bench")])
    b.append(arrow([(X[2] + 80, 456), (X[2] + 80, 402)], "reads index, facts, events", at=(X[2] + 92, 444), dashed=True, label_anchor="start"))

    b.append(lane(590, 150, "Evaluation"))
    chain(628, [("cyl", "Evaluation +\ngold sets"), ("p", "Runner:\nmethods × models"), ("p", "Same answering\npipeline"),
                ("p", "Score each\nanswer"), ("cyl", "Results\nstore"), ("ext", "Leaderboard,\nModels, Runs")])
    return W, 760, b


def column(x, y, w, h, title, sections):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" stroke="{K}" stroke-width="1.5"/>',
           f'<line x1="{x}" y1="{y + 46}" x2="{x + w}" y2="{y + 46}" stroke="{K}" stroke-width="1.2"/>',
           text(x + w / 2, y + 30, title, F, "middle", "bold")]
    yy = y + 80
    for head, items in sections:
        if head:
            out.append(text(x + 16, yy, head, FS, "start", "bold"))
            yy += 28
        out.append(bullets(x + 16, yy, items, size=FS, gap=1.42, max_w=w - 24, where=title))
        yy += len(items) * FS * 1.42 + 14
    return "".join(out)


def fig16_evaluation():
    """Section 6.4: what is compared, on what, and how it is scored."""
    W, H = 1200, 900
    top, h = 20, 480
    b = [
        column(20, top, 275, h, "Question sets", [
            ("Public benchmarks", ["FinanceBench", "FinDER", "DocFinQA", "ConvFinQA", "FinQA, TAT-QA",
                                   "FailSafeQA", "SECQUE", "Finance Agent"]),
            ("Loupe-Gold (ours)", ["Numbers: 300", "Calculations: 150", "Trick questions: 125",
                                   "Event labels: 555", "Plans: 199"])]),
        column(330, top, 275, h, "Methods", [
            ("Baselines (generic tools)", ["B0: closed book", "O1: single-shot RAG", "O2: ReAct",
                                           "O3: Plan-and-Execute", "O4: FARE-style router", "O5: Self-Refine"]),
            ("Ours (financial harness)", ["Loupe-Orch v1"]),
            ("Ablations of Loupe", ["minus router, planner,", "verifier, critic, abstain,", "minus harness"])]),
        column(640, top, 255, h, "Models", [
            ("Generators (free tiers)", ["Gemma 4 31B", "GPT-OSS 120B", "GPT-OSS 20B", "Nemotron 3 Super"]),
            ("Judge (different family)", ["Ministral 14B"]),
            ("Fixed for every run", ["temperature 0", "same retriever, top-k", "same token cap"])]),
        column(930, top, 250, h, "Metrics", [
            ("Quality", ["numeric accuracy", "hallucination rate", "supported-claim rate", "refusal accuracy",
                         "abstain rate"]),
            ("Retrieval", ["recall@k, MRR"]),
            ("Cost", ["tokens", "latency", "cost (USD)"])]),
    ]
    for x in (295, 605):
        b.append(text(x + 17, top + h / 2 + 10, "×", F + 8, "middle", "bold"))
    b.append(arrow([(897, top + h / 2), (928, top + h / 2)]))

    y = top + h + 30
    b.append(f'<rect x="20" y="{y}" width="760" height="165" fill="#fff" stroke="{K}" stroke-width="1.5"/>')
    b.append(text(36, y + 32, "Controls", F, "start", "bold"))
    b.append(bullets(36, y + 68, ["every LLM call cached; a config hash on every result row",
                                  "dev / test split by company (8 / 17); test split used once",
                                  "hypotheses written down before the test run",
                                  "same number of prompt-tuning rounds for every method"], size=FS, gap=1.45, max_w=730))
    b.append(f'<rect x="810" y="{y}" width="370" height="165" fill="#fff" stroke="{K}" stroke-width="1.5"/>')
    b.append(text(826, y + 32, "Statistics and output", F, "start", "bold"))
    b.append(bullets(826, y + 68, ["company-cluster bootstrap 95% CI", "paired tests, Holm correction",
                                   "Bench: Leaderboard, Models,", "Stages, Runs with citations"], size=FS, gap=1.45, max_w=350))
    return W, y + 185, b


FIGURES = {
    "fig14_algorithm": fig14_algorithm,
    "fig15_system_flow": fig15_system_flow,
    "fig16_evaluation_method": fig16_evaluation,
}
