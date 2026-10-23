"""Chapter 5 figures (high-level design): use case, DFDs, sequence, class, activity,
deployment, collaboration and component diagrams. Black-and-white UML notation."""

from html import escape

from lib import (
    F, FS, INK, MUTED, OVERFLOW, actor, lines_block, arrow, box, circle_proc, datastore, diamond, ellipse,
    end_node, group, label_at, start_node, text, tw,
)

K = "#000"


def rect(x, y, w, h, dashed=False, rx=4, sw=1.5):
    d = ' stroke-dasharray="6 4"' if dashed else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#fff" stroke="{K}" stroke-width="{sw}"{d}/>'


def line(x1, y1, x2, y2, dashed=False, sw=1.4):
    d = ' stroke-dasharray="6 4"' if dashed else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{K}" stroke-width="{sw}"{d}/>'


# ------------------------------------------------------------------ 5.1 use case


def fig05_use_case():
    W, H = 1200, 990
    b = [rect(232, 20, 726, 950, rx=8), text(252, 50, "Loupe", F, "start", "bold")]
    left = [("Ask a question in chat", 110), ("Read cited answer and sources", 190),
            ("Compare companies", 270), ("View charts and forecasts", 350),
            ("Review 8-K risk events", 430), ("Run experiments", 570),
            ("Compare methods side by side", 650), ("View leaderboard and models", 730),
            ("Inspect runs and citations", 810), ("Audit gold dataset items", 890)]
    for t, y in left:
        b.append(ellipse(430, y, 172, 32, t, size=FS + 1))
    right = {"verify": ("Verify claims\nagainst evidence", 135), "llm": ("Query an LLM\nthrough the gateway", 285),
             "ingest": ("Ingest filings\nand XBRL facts", 470), "index": ("Build search\nindex", 570),
             "config": ("Configure models\nand API keys", 670), "score": ("Score answers", 860)}
    for t, y in right.values():
        b.append(ellipse(800, y, 140, 40, t, size=FS + 1))

    b.append(actor(115, 200, "Financial\nanalyst"))
    for _, y in left[:5]:
        b.append(line(140, 245, 258, y))
    b.append(actor(115, 650, "Researcher /\nexaminer"))
    for _, y in left[5:]:
        b.append(line(140, 695, 258, y))

    b.append(actor(1100, 470, "Data\nadministrator"))
    for key in ("ingest", "index", "config"):
        b.append(line(1072, 515, 940, right[key][1]))
    b.append(box(1005, 255, 180, 62, "«system»\nLLM provider", size=FS + 1))
    b.append(line(1005, 286, 940, 285))
    b.append(box(1005, 365, 180, 62, "«system»\nSEC EDGAR", size=FS + 1))
    b.append(line(1005, 396, 925, 452))

    inc = dict(dashed=True, head="open", label_size=FS - 1)
    b.append(arrow([(602, 112), (662, 130)], "«include»", at=(632, 102), **inc))
    b.append(arrow([(585, 125), (690, 262)], "«include»", at=(668, 222), **inc))
    b.append(arrow([(585, 585), (690, 838)], "«include»", at=(655, 765), **inc))
    b.append(arrow([(600, 575), (668, 300)], "«include»", at=(640, 505), **inc))
    return W, H, b


# ------------------------------------------------------------------ 5.2 DFD level 0


def fig06_dfd0():
    W, H = 1200, 690
    cx, cy, r = 600, 380, 140
    b = ['<g transform="translate(0 -70)">', circle_proc(cx, cy, r, "0", "Loupe financial\nrisk copilot")]
    ext = [(60, 120, "Financial analyst"), (60, 570, "Research team"), (910, 120, "SEC EDGAR"),
           (910, 570, "LLM providers"), (485, 662, "Public benchmarks")]
    for x, y, t in ext:
        b.append(box(x, y, 230, 70, t, sw=1.8))
    b.append(arrow([(290, 140), (520, 140), (520, 264)], "question", at=(405, 130)))
    b.append(arrow([(470, 328), (470, 175), (292, 175)], "cited answer, charts, events", at=(381, 214)))
    b.append(arrow([(910, 155), (680, 155), (680, 264)], "filings, XBRL facts,\n8-K item codes", at=(795, 186)))
    b.append(arrow([(290, 585), (470, 585), (470, 432)], "experiment config", at=(380, 575)))
    b.append(arrow([(500, 478), (500, 625), (292, 625)], "leaderboard, runs, traces", at=(395, 660)))
    b.append(arrow([(730, 432), (730, 585), (908, 585)], "prompts", at=(820, 575)))
    b.append(arrow([(910, 625), (700, 625), (700, 478)], "completions", at=(805, 652)))
    b.append(arrow([(600, 662), (600, 522)], "questions +\ngold answers", at=(600, 590)))
    b.append("</g>")
    return W, H, b


# ------------------------------------------------------------------ 5.3 DFD level 1


def fig07_dfd1():
    W, H = 1200, 1000
    R = 80
    b = []
    P = {"1": (330, 121, "Ingest\nfilings"), "2": (780, 121, "Build\nindex"),
         "3": (330, 451, "Route and\nplan"), "4": (620, 451, "Run tools"),
         "5": (910, 451, "Compose\nand verify"), "6": (330, 890, "Evaluate\nmethods")}
    for k, (x, y, t) in P.items():
        b.append(circle_proc(x, y, R, f"{k}.0", t))
    b.append(datastore(440, 97, 220, 48, "D1", "Parsed filings"))
    b.append(datastore(900, 97, 230, 48, "D2", "Search index"))
    b.append(datastore(520, 250, 260, 48, "D3", "Facts and events"))
    b.append(datastore(470, 840, 260, 48, "D4", "Evaluation sets"))
    b.append(datastore(470, 920, 260, 48, "D5", "Results"))
    for x, y, w, t in [(20, 85, 150, "SEC EDGAR"), (20, 415, 150, "Analyst"), (1060, 415, 120, "Analyst"),
                       (560, 600, 200, "LLM providers"), (20, 854, 150, "Researchers"),
                       (860, 828, 200, "Public benchmarks")]:
        b.append(box(x, y, w, 72, t, sw=1.8))
    # duplicate external entity mark (DFD convention)
    b.append(line(1070, 487, 1086, 471))

    b.append(arrow([(170, 121), (248, 121)], "filings,\nXBRL", at=(209, 82)))
    b.append(arrow([(410, 121), (438, 121)]))
    b.append(arrow([(660, 121), (698, 121)]))
    b.append(arrow([(860, 121), (898, 121)]))
    b.append(arrow([(330, 201), (330, 274), (518, 274)], "facts, 8-K items", at=(424, 263)))
    b.append(arrow([(1015, 145), (1015, 330), (650, 330), (650, 376)], "passages", at=(840, 320)))
    b.append(arrow([(600, 298), (600, 374)], "values,\nevents", at=(548, 328), label_anchor="middle"))
    b.append(arrow([(170, 451), (248, 451)], "question", at=(209, 440)))
    b.append(arrow([(410, 451), (538, 451)], "tool plan", at=(474, 440)))
    b.append(arrow([(700, 451), (828, 451)], "evidence [E#]", at=(764, 440)))
    b.append(arrow([(990, 451), (1058, 451)], "answer", at=(1024, 440)))
    b.append(arrow([(370, 520), (370, 636), (558, 636)], "prompts ⇄\ncompletions", at=(455, 600), start_head="arr"))
    b.append(arrow([(870, 520), (870, 636), (762, 636)], "prompts ⇄\ncompletions", at=(815, 690), start_head="arr"))
    b.append(arrow([(300, 812), (300, 528)], "benchmark\nquestions", at=(232, 690)))
    b.append(arrow([(910, 531), (910, 760), (380, 760), (380, 828)], "answers and traces", at=(640, 750)))
    b.append(arrow([(470, 864), (408, 864)]))
    b.append(arrow([(389, 944), (468, 944)]))
    b.append(arrow([(860, 864), (732, 864)], "questions,\ngold", at=(796, 820)))
    b.append(arrow([(170, 890), (248, 890)], "config ⇄\nscores", at=(209, 832), start_head="arr"))
    return W, H, b


# ------------------------------------------------------------------ 5.4 sequence


def fig08_sequence():
    names = ["Analyst", "Bench UI", "FastAPI", "Loupe-Orch", "LLM gateway", "Tool harness", "Data stores"]
    X = [70, 215, 365, 560, 765, 955, 1120]
    msgs = [
        (0, 1, "ask question", "call"), (1, 2, "POST /api/chat", "call"), (2, 3, "run(question)", "call"),
        (3, 4, "route question", "call"), (4, 3, "intents, company, year", "ret"),
        (3, 5, "get_financial_metric", "call"), (5, 6, "query XBRL facts", "call"),
        (6, 5, "value + accession", "ret"), (5, 3, "evidence [E1], [E2]", "ret"),
        (3, 5, "calculate(pct_change)", "call"), (5, 3, "result [E3]", "ret"),
        (3, 4, "compose, cite [E#]", "call"), (4, 3, "draft answer", "ret"),
        (3, 3, "verify numbers, quotes", "self"),
        (3, 4, "critique claims", "call"), (4, 3, "unsupported claims", "ret"),
        ("alt",),
        (3, 4, "revise once (hint: right [E#])", "call"), (4, 3, "revised answer", "ret"),
        (3, 3, "drop claims that still fail", "self"),
        ("end",),
        (3, 2, "Answer: claims, citations, trace", "ret"), (2, 1, "JSON", "ret"),
        (1, 0, "answer + sources", "ret"),
    ]
    y0, step = 150, 46
    ys, y = [], y0
    for m in msgs:
        ys.append(y)
        y += {"alt": 58, "end": 44}.get(m[0], 0) or (64 if m[-1] == "self" else step)
    W, H = 1200, y + 40
    b = []
    for i, (n, x) in enumerate(zip(names, X, strict=True)):
        if i == 0:
            b.append(actor(x, 8, ""))
            b.append(text(x, 122, n, F, "middle"))
        else:
            b.append(box(x - 68, 30, 136, 54, n, size=FS + 1))
        b.append(line(x, 132 if i == 0 else 84, x, H - 20, dashed=True, sw=1.1))
    # activation bars
    b.append(f'<rect x="{X[3] - 7}" y="{ys[2]}" width="14" height="{ys[-3] - ys[2]}" fill="#fff" stroke="{K}" stroke-width="1.3"/>')
    for i, m in enumerate(msgs):
        y = ys[i]
        if m[0] == "alt":
            top = y - 4
            bottom = ys[msgs.index(("end",))] + 4
            b.append(f'<rect x="{X[3] - 120}" y="{top}" width="{X[4] - X[3] + 190}" height="{bottom - top}" fill="none" stroke="{K}" stroke-width="1.2"/>')
            b.append(f'<path d="M {X[3] - 120} {top + 26} L {X[3] - 70} {top + 26} L {X[3] - 60} {top + 16} L {X[3] - 60} {top}" fill="#fff" stroke="{K}" stroke-width="1.2"/>')
            b.append(text(X[3] - 112, top + 19, "alt", FS - 1, "start", "bold"))
            b.append(label_at(X[3] - 52, top + 20, "[a claim is unsupported]", FS - 1, anchor="start"))
            continue
        if m[0] == "end":
            continue
        a, c, label, kind = m
        if kind == "self":
            x = X[a] + 7
            b.append(arrow([(x, y), (x + 40, y), (x + 40, y + 26), (x + 2, y + 26)]))
            b.append(text(x + 50, y + 18, label, FS, "start"))
            continue
        xa, xc = X[a], X[c]
        xa += 7 if (a == 3 and xc > xa) else (-7 if a == 3 else 0)
        xc += -9 if (c == 3 and xa > X[3]) else (9 if c == 3 else 0)
        b.append(arrow([(xa, y), (xc, y)], dashed=kind == "ret", head="open" if kind == "ret" else "arr"))
        b.append(label_at((xa + xc) / 2, y - 8, label, FS))
    return W, H, b


# ------------------------------------------------------------------ 5.5 class


def class_box(x, y, w, name, attrs, methods, stereo=None):
    lh = 23
    head = 38 + (22 if stereo else 0)
    h = head + 10 + len(attrs) * lh + 10 + len(methods) * lh + 8
    out = [rect(x, y, w, h, rx=0)]
    ty = y + 26
    if stereo:
        out.append(text(x + w / 2, ty, stereo, FS - 1, "middle", "normal", MUTED))
        ty += 22
    out.append(text(x + w / 2, ty, name, F, "middle", "bold", italic=bool(stereo)))
    yy = y + head
    out.append(line(x, yy, x + w, yy, sw=1.2))
    for i, a in enumerate(attrs):
        out.append(text(x + 10, yy + 26 + i * lh, a, FS, "start"))
        if tw(a, FS) > w - 16:
            OVERFLOW.append(f"{name}: {a}")
    yy += 10 + len(attrs) * lh + 6
    out.append(line(x, yy, x + w, yy, sw=1.2))
    for i, m in enumerate(methods):
        out.append(text(x + 10, yy + 24 + i * lh, m, FS, "start"))
        if tw(m, FS) > w - 16:
            OVERFLOW.append(f"{name}: {m}")
    return "".join(out), h


def fig09_class():
    W = 1200
    cols = [20, 430, 840]
    w = 340
    specs = {
        "Engine": (0, 20, None, ["gateway: Gateway", "facts: FactsStore", "companies: list[Company]"],
                   ["context(model): RunContext", "ask(question, arm): Answer"]),
        "Gateway": (0, 250, None, ["registry: ModelRegistry", "cache: DiskCache"],
                    ["complete(alias, messages)"]),
        "RunContext": (1, 20, None, ["model: str", "allowed_tools: list[str]", "trace: list[TraceStep]"],
                       ["llm(stage, messages)", "tool(name, args): str", "finish(text): Answer"]),
        "Ledger": (1, 290, None, ["items: dict[str, Evidence]"], ["add(kind, text, citation)", "get(id): Evidence"]),
        "Evidence": (1, 455, None, ["id: str", "kind: chunk | fact | calc", "text: str", "citation: Citation"], []),
        "ToolBox": (2, 20, None, ["retriever: Retriever", "facts: FactsStore"],
                    ["search_filings()", "get_financial_metric()", "compare_companies()", "calculate()",
                     "make_chart(), forecast_metric()", "distress_score(), list_events()"]),
        "Retriever": (2, 370, None, ["index: SearchIndex", "reranker: CrossEncoder"], ["retrieve(query, filter)"]),
        "FactsStore": (2, 520, None, ["metrics: dict"], ["get(company, metric, year)"]),
        "Runner": (0, 700, None, ["store: ResultStore"], ["run(spec): list[ResultRow]"]),
        "ResultStore": (0, 860, None, ["db: DuckDB"], ["add(row, answer)", "rows(where)"]),
        "Orchestrator": (1, 700, "«interface»", ["name, toolset: str"], ["run(question, ctx): Answer"]),
        "LoupeOrch": (1, 880, None, ["use_router, use_planner: bool", "use_verifier, use_critic: bool",
                                     "toolset = \"harness\""], ["run(question, ctx): Answer"]),
        "Baseline methods": (1, 1080, None, ["B0, RAG, ReAct, Plan-Execute,", "Router (FARE), Self-Refine",
                                             "toolset = \"none\" | \"generic\""], ["run(question, ctx): Answer"]),
        "Answer": (2, 700, None, ["text: str", "abstained: bool", "removed_claims: list[str]"], ["tokens(), latency_ms()"]),
        "Claim": (2, 900, None, ["text: str", "supported: bool"], []),
        "Citation": (2, 1040, None, ["doc_id | fact_id: str", "quote, url: str", "verified: bool"], []),
    }
    b, R = [], {}
    for name, (c, y, st, at, me) in specs.items():
        svg_, h = class_box(cols[c], y, w, name, at, me, st)
        b.append(svg_)
        R[name] = (cols[c], y, w, h)
    H = max(y + h for (_, y, _, h) in R.values()) + 20

    def mid(n, side):
        x, y, w_, h = R[n]
        return {"t": (x + w_ / 2, y), "b": (x + w_ / 2, y + h), "l": (x, y + h / 2), "r": (x + w_, y + h / 2)}[side]

    def comp(a, c, label=None, at=None):  # composition: filled diamond at the whole
        p, q = mid(a, "b"), mid(c, "t")
        b.append(arrow([p, q], head="open", start_head="dia", label=label, at=at, label_size=FS - 1))

    def compose(a, c, label=None):  # filled diamond at the whole, near its right side
        x, y, w_, h = R[a]
        _, cy_, _, _ = R[c]
        px = x + w_ - 40
        b.append(arrow([(px, y + h), (px, cy_ - 1)], head="open", start_head="dia"))
        if label:
            b.append(text(px + 12, cy_ - 10, label, FS - 1, "start"))

    compose("Engine", "Gateway")
    compose("RunContext", "Ledger")
    compose("Ledger", "Evidence", "1..*")
    compose("Answer", "Claim", "*")
    compose("Claim", "Citation", "*")
    b.append(arrow([mid("ToolBox", "b"), mid("Retriever", "t")], head="open"))
    tb, fs = R["ToolBox"], R["FactsStore"]
    b.append(arrow([(1180, tb[1] + tb[3] - 30), (1193, tb[1] + tb[3] - 30), (1193, fs[1] + 30), (1182, fs[1] + 30)], head="open"))
    b.append(arrow([mid("Runner", "b"), mid("ResultStore", "t")], head="open"))
    rc, gw, ev = R["RunContext"], R["Gateway"], R["Evidence"]
    ey = R["Engine"][1] + 40
    b.append(arrow([(cols[0] + w, ey), (cols[1] - 2, ey)], "creates", at=(cols[0] + w + 35, ey - 8), dashed=True, head="open"))
    b.append(arrow([(cols[1], rc[1] + 90), (375, rc[1] + 90), (375, gw[1] + 40), (cols[0] + w + 2, gw[1] + 40)], head="open"))
    b.append(arrow([(cols[1] + w, tb[1] + 50), (cols[2] - 2, tb[1] + 50)], head="open"))
    b.append(arrow([(cols[2], tb[1] + tb[3] - 20), (805, tb[1] + tb[3] - 20), (805, ev[1] + 40), (cols[1] + w + 2, ev[1] + 40)],
                   "adds", at=(805, ev[1] + 12), dashed=True, head="open"))
    ox, oy, ow, oh = R["Orchestrator"]
    lo, bl = R["LoupeOrch"], R["Baseline methods"]
    b.append(arrow([(lo[0] + 30, lo[1]), (lo[0] + 30, oy + oh + 1)], dashed=True, head="tri"))
    rx_ = ox + ow - 30
    b.append(arrow([(cols[1] + w, bl[1] + 30), (800, bl[1] + 30), (800, oy + oh + 22), (rx_, oy + oh + 22), (rx_, oy + oh + 1)],
                   dashed=True, head="tri"))
    ry = oy + 50
    b.append(arrow([(cols[0] + w, ry), (cols[1] - 2, ry)], "runs", at=(cols[0] + w + 35, ry - 8), head="open"))
    b.append(arrow([(cols[1] + w, ry), (cols[2] - 2, ry)], "returns", at=(cols[1] + w + 35, ry - 8), dashed=True, head="open"))
    b.append(arrow([(cols[1], oy + 20), (395, oy + 20), (395, rc[1] + 140), (cols[1] - 2, rc[1] + 140)],
                   "uses", at=(395, oy - 140), dashed=True, head="open"))
    return W, H, b


# ------------------------------------------------------------------ 5.6 activity


def fig10_activity():
    W, H = 1200, 1420
    cx, bw = 560, 520
    b = [start_node(cx, 34)]

    def act(y, t, h=58):
        b.append(box(cx - bw / 2, y, bw, h, t, rx=24, size=FS + 1))
        return y + h

    y = act(70, "Choose dataset, split, methods and models")
    b.append(arrow([(cx, 49), (cx, 68)]))
    b.append(arrow([(cx, y), (cx, y + 30)]))
    b.append(diamond(cx, y + 75, 230, 90, "test split?"))
    b.append(box(870, y + 47, 300, 58, "require --final and the\npre-registration tag", rx=24, size=FS))
    b.append(arrow([(cx + 115, y + 75), (868, y + 75)], "yes", at=(cx + 160, y + 66)))
    b.append(arrow([(1020, y + 105), (1020, y + 160), (cx + 6, y + 160)]))
    b.append(arrow([(cx, y + 120), (cx, y + 178)], "no", at=(cx - 22, y + 150)))
    y = act(y + 180, "Select items (seeded, stratified by company)")
    b.append(arrow([(cx, y), (cx, y + 28)]))
    loop_top = y + 30
    y = act(loop_top, "Take next (item, method, model)")
    b.append(arrow([(cx, y), (cx, y + 28)]))
    b.append(diamond(cx, y + 72, 250, 88, "already\nstored?"))
    skip_y = y + 72
    b.append(arrow([(cx, y + 116), (cx, y + 148)], "no", at=(cx - 22, y + 138)))
    y = act(y + 150, "Build run context: model, retriever, method's toolset")
    for t in ("Run the method on the question", "Verify every claim against cited evidence",
              "Score: numeric match, refusal, or LLM judge", "Store result row and full answer with citations"):
        b.append(arrow([(cx, y), (cx, y + 28)]))
        y = act(y + 30, t)
    b.append(box(850, y - 300, 270, 72, "on an API error: store\nthe error, continue", dashed=True, rx=2, size=FS))
    b.append(line(cx + bw / 2, y - 264, 850, y - 264, dashed=True, sw=1.1))
    b.append(arrow([(cx, y), (cx, y + 28)]))
    b.append(diamond(cx, y + 74, 280, 90, "more\ncombinations?"))
    more_y = y + 74
    b.append(arrow([(cx + 125, skip_y), (1170, skip_y), (1170, more_y), (cx + 142, more_y)], "yes (skip)", at=(1080, skip_y - 9)))
    b.append(arrow([(cx - 140, more_y), (130, more_y), (130, loop_top + 29), (cx - bw / 2 - 2, loop_top + 29)], "yes", at=(130, (more_y + loop_top) / 2)))
    b.append(arrow([(cx, more_y + 45), (cx, more_y + 88)], "no", at=(cx - 22, more_y + 72)))
    y = act(more_y + 90, "Compute metrics with company-cluster bootstrap 95% CIs")
    b.append(arrow([(cx, y), (cx, y + 28)]))
    y = act(y + 30, "Show on the Bench: leaderboard, models, runs")
    b.append(arrow([(cx, y), (cx, y + 24)]))
    b.append(end_node(cx, y + 42))
    return W, y + 70, b


# ------------------------------------------------------------------ 5.7 deployment


def node(x, y, w, h, title, d=14):
    return (
        f'<path d="M {x} {y} L {x + d} {y - d} L {x + w + d} {y - d} L {x + w + d} {y + h - d} L {x + w} {y + h}" '
        f'fill="#fff" stroke="{K}" stroke-width="1.5"/>'
        f'<line x1="{x + w}" y1="{y}" x2="{x + w + d}" y2="{y - d}" stroke="{K}" stroke-width="1.5"/>'
        + rect(x, y, w, h, rx=0) + text(x + 14, y + 28, title, F, "start", "bold")
    )


def fig11_deployment():
    W, H = 1200, 860
    b = [node(20, 40, 700, 600, "«device» Developer laptop (macOS, Apple M1)")]
    b.append(group(45, 85, 650, 245, "«execution environment» Python 3.12 (uv)", dashed=False, label_size=FS + 1))
    for i, (t, s) in enumerate([("FastAPI", "uvicorn :8000"), ("Loupe-Orch + tools", "in process"),
                                ("Experiment runner", "loupe eval run"), ("Loupe CLI", "ingest, index, ask")]):
        b.append(box(70 + (i % 2) * 315, 135 + (i // 2) * 92, 290, 74, t, [s]))
    b.append(group(45, 350, 650, 100, "«execution environment» Node.js", dashed=False, label_size=FS + 1))
    b.append(box(70, 390, 290, 48, "Vite dev server :5173", size=FS + 1))
    b.append(group(45, 470, 650, 150, "«artifacts» data/", dashed=False, label_size=FS + 1))
    for i, t in enumerate(["loupe.duckdb", "results.duckdb + runs/", "search index (vectors, BM25)", "LLM cache (diskcache)"]):
        b.append(box(70 + (i % 2) * 315, 512 + (i // 2) * 52, 290, 42, t, size=FS))

    b.append(node(20, 715, 330, 120, "«device» Web browser"))
    b.append(box(45, 760, 280, 52, "React Bench (SPA)", size=FS + 1))
    b.append(arrow([(185, 715), (185, 640)], "HTTP :5173 (/api → :8000)", at=(330, 682), start_head="arr"))

    rights = [(70, 120, "«device» GPU workstation (RTX 4050)", ["TorchEmbedder (CUDA)", "builds the chunk index in ~16 min"]),
              (290, 130, "«server» SEC EDGAR (sec.gov)", ["filings and XBRL company facts", "≤ 8 requests/s, contact header"]),
              (480, 150, "«cloud» LLM providers", ["NVIDIA NIM, Ollama Cloud,", "Mistral, Groq, OpenRouter"]),
              (690, 130, "«server» GitHub repository", ["code, configs, gold sets,", "experiment exports"])]
    for y, h, t, subs in rights:
        b.append(node(790, y, 380, h, t))
        for j, s in enumerate(subs):
            b.append(text(808, y + 62 + j * 26, s, FS, "start", "normal", MUTED))
    b.append(arrow([(788, 140), (736, 140)], "index files", at=(762, 128)))
    b.append(arrow([(736, 355), (788, 355)], "HTTPS", at=(762, 343)))
    b.append(arrow([(736, 555), (788, 555)], "HTTPS", at=(762, 543)))
    b.append(arrow([(736, 620), (760, 620), (760, 755), (788, 755)], "git", at=(760, 690), start_head="arr"))
    return W, H, b


# ------------------------------------------------------------------ 5.8 collaboration


def obj(x, y, w, name):
    return (rect(x, y, w, 56, rx=0) +
            f'<text x="{x + w / 2}" y="{y + 35}" font-size="{F}" text-anchor="middle" fill="{INK}" '
            f'text-decoration="underline">{escape(name)}</text>')


def fig12_collaboration():
    W, H = 1200, 800
    b = [actor(60, 40, ":Analyst")]
    O = {"ui": (240, 60, ":BenchUI"), "api": (640, 60, ":FastAPI"), "ver": (980, 200, ":Verifier"),
         "ledger": (240, 400, ":Ledger"), "orch": (640, 400, ":LoupeOrch"), "llm": (980, 400, ":LLMGateway"),
         "ret": (240, 700, ":Retriever"), "tools": (640, 700, ":ToolBox"), "facts": (980, 700, ":FactsStore")}
    for x, y, n in O.values():
        b.append(obj(x, y, 200, n))

    def msgs(x, y, items, anchor="start"):
        for i, m in enumerate(items):
            b.append(text(x, y + i * 24, m, FS, anchor))

    b.append(line(90, 88, 240, 88))
    msgs(96, 76, ["1: question →"])
    msgs(96, 112, ["← 12: answer"])
    b.append(line(440, 88, 640, 88))
    msgs(452, 76, ["2: POST /api/chat →"])
    msgs(452, 112, ["← 11: JSON"])
    b.append(line(740, 116, 740, 400))
    msgs(752, 250, ["3: run(question) ↓", "10: Answer ↑"])
    b.append(line(840, 404, 980, 256))
    msgs(990, 292, ["8: verify(claims) ↗"])
    b.append(line(840, 428, 980, 428))
    msgs(850, 486, ["4: route() →", "7: compose() →", "9: critique() →"])
    b.append(line(440, 428, 640, 428))
    msgs(452, 416, ["← 6: read [E#]"])
    b.append(line(740, 456, 740, 700))
    msgs(752, 580, ["5: call tools ↓"])
    b.append(line(440, 728, 640, 728))
    msgs(452, 770, ["← 5.1: search()"])
    b.append(line(840, 728, 980, 728))
    msgs(850, 770, ["5.2: get facts →"])
    b.append(line(660, 700, 440, 456))
    msgs(545, 615, ["5.3: add evidence ↖"], "end")
    return W, H, b


# ------------------------------------------------------------------ 5.9 component


def comp(x, y, w, h, title, sub=()):
    icon = (f'<rect x="{x + w - 34}" y="{y + 10}" width="22" height="26" fill="#fff" stroke="{K}" stroke-width="1.2"/>'
            f'<rect x="{x + w - 40}" y="{y + 15}" width="12" height="6" fill="#fff" stroke="{K}" stroke-width="1.2"/>'
            f'<rect x="{x + w - 40}" y="{y + 25}" width="12" height="6" fill="#fff" stroke="{K}" stroke-width="1.2"/>')
    rows = [(title, F, "normal", INK)] + [(t, FS, "normal", MUTED) for t in sub]
    return box(x, y, w, h, rx=0) + lines_block(x + (w - 44) / 2 + 4, y + h / 2, rows, w - 56, title) + icon


def fig13_component():
    W, H = 1200, 1000
    b = []
    b.append(group(20, 20, 340, 150, "Web client", dashed=True, label_size=FS + 1))
    b.append(comp(45, 65, 290, 80, "Bench UI", ["React + TypeScript"]))
    b.append(group(440, 20, 340, 150, "API", dashed=True, label_size=FS + 1))
    b.append(comp(465, 65, 290, 80, "REST API", ["FastAPI"]))
    b.append(arrow([(335, 105), (463, 105)], "REST /api", at=(400, 95), dashed=True, head="open"))

    b.append(group(20, 210, 760, 330, "Core engine", dashed=True, label_size=FS + 1))
    core = [("Orchestrators", ["Loupe-Orch + baselines"]), ("Tool harness", ["9 financial tools"]),
            ("Retrieval", ["hybrid search, rerank"]), ("Evidence + verifier", ["ledger, code check"]),
            ("LLM gateway", ["LiteLLM, cache, limits"]), ("Facts store", ["XBRL, fiscal calendars"])]
    for i, (t, s_) in enumerate(core):
        x, y = 45 + (i % 3) * 245, 260 + (i // 3) * 140
        b.append(comp(x, y, 225, 95, t, s_))
    b.append(arrow([(610, 145), (610, 190), (157, 190), (157, 258)], "run(question)", at=(380, 197), dashed=True, head="open"))
    b.append(arrow([(270, 307), (288, 307)], dashed=True, head="open"))
    b.append(arrow([(515, 307), (533, 307)], dashed=True, head="open"))
    b.append(arrow([(110, 355), (110, 398)], dashed=True, head="open"))
    b.append(arrow([(220, 355), (220, 375), (402, 375), (402, 398)], dashed=True, head="open"))
    b.append(arrow([(500, 355), (500, 385), (647, 385), (647, 398)], dashed=True, head="open"))

    b.append(group(820, 210, 360, 330, "Evaluation", dashed=True, label_size=FS + 1))
    for i, (t, s_) in enumerate([("Dataset loaders", "public + Loupe-Gold"), ("Experiment runner", "methods × models"),
                                 ("Metrics and stats", "judge, bootstrap CIs")]):
        b.append(comp(845, 255 + i * 92, 310, 78, t, [s_]))
    b.append(arrow([(845, 386), (782, 386)], "runs", at=(813, 376), dashed=True, head="open"))
    b.append(arrow([(755, 120), (1000, 120), (1000, 208)], "results", at=(880, 110), dashed=True, head="open"))

    b.append(group(20, 580, 760, 230, "Data pipeline (offline)", dashed=True, label_size=FS + 1))
    for i, item in enumerate([("Ingest", "parse, sections"), ("Index builder", "chunk, embed, BM25"),
                              ("Event extractor", "8-K events (LLM)"), ("XBRL loader", "facts table"),
                              None, ("SEC client", "polite, cached")]):
        if item is None:
            continue
        t, s_ = item
        x, y = 45 + (i % 3) * 245, 625 + (i // 3) * 92
        b.append(comp(x, y, 225, 78, t, [s_]))

    b.append(group(820, 580, 360, 230, "External systems", dashed=True, label_size=FS + 1))
    b.append(comp(845, 625, 310, 70, "LLM providers", ["HTTPS + API keys"]))
    b.append(comp(845, 717, 310, 70, "SEC EDGAR", ["HTTPS"]))
    b.append(arrow([(402, 495), (402, 560), (800, 560), (800, 660), (843, 660)], dashed=True, head="open"))
    b.append(arrow([(760, 756), (843, 756)], dashed=True, head="open"))

    b.append(group(20, 850, 1160, 130, "Storage («artifact»)", dashed=True, label_size=FS + 1))
    for i, t in enumerate(["search index files", "loupe.duckdb", "results.duckdb + runs/", "LLM cache"]):
        b.append(box(45 + i * 285, 895, 255, 60, t, size=FS + 1, rx=0))
    return W, H, b


FIGURES = {
    "fig05_use_case": fig05_use_case,
    "fig06_dfd_level0": fig06_dfd0,
    "fig07_dfd_level1": fig07_dfd1,
    "fig08_sequence": fig08_sequence,
    "fig09_class": fig09_class,
    "fig10_activity": fig10_activity,
    "fig11_deployment": fig11_deployment,
    "fig12_collaboration": fig12_collaboration,
    "fig13_component": fig13_component,
}
