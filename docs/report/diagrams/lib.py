"""Tiny SVG toolkit for the report figures: one style for every diagram.

Sizing rule: figures are drawn on a canvas about 1200 px wide and placed at full text
width (about 6.3 in) in the report, so 23 px text prints at about 9 pt and 19 px at about
7 pt. Nothing smaller than 18 px is used.
"""

from html import escape

FONT = "Arial, Helvetica, sans-serif"
F = 20  # primary text
FS = 17  # secondary text
FH = 20  # group headings

INK = "#000000"
LINE = "#000000"
MUTED = "#333333"

# black-and-white line drawings: every kind is an outline on white (kinds kept for structure)
KINDS = {k: ("#ffffff", "#000000") for k in ("core", "data", "ext", "eval", "warn", "neutral", "white")}

OVERFLOW: list[str] = []  # text that probably does not fit its box (checked by build.py)


def tw(s: str, size: float, bold: bool = False) -> float:
    """Rough rendered width of a string in Helvetica."""
    narrow = sum(c in "ijlI.,:;|!'()[] " for c in s)
    wide = sum(c in "MWmw@%" for c in s)
    caps = sum(c.isupper() for c in s)
    w = (len(s) - narrow - wide) * 0.53 + narrow * 0.3 + wide * 0.82 + caps * 0.1
    return w * size * (1.06 if bold else 1.0)


def text(x, y, s, size=F, anchor="middle", weight="normal", fill=INK, italic=False, cls=""):
    style = ' font-style="italic"' if italic else ""
    c = f' class="{cls}"' if cls else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" fill="{fill}"{style}{c}>{escape(s)}</text>'
    )


def lines_block(cx, cy, rows, max_w=None, where=""):
    """rows: list of (text, size, weight, fill). Centred vertically on cy."""
    heights = [r[1] * 1.28 for r in rows]
    total = sum(heights)
    y = cy - total / 2
    out = []
    for (s, size, weight, fill), h in zip(rows, heights, strict=True):
        y += h
        out.append(text(cx, y - h * 0.27, s, size, "middle", weight, fill))
        if max_w and tw(s, size, weight == "bold") > max_w:
            OVERFLOW.append(f"{where}: '{s}' ({tw(s, size, weight == 'bold'):.0f} > {max_w:.0f})")
    return "".join(out)


def box(x, y, w, h, title="", sub=(), kind="core", rx=4, size=F, sub_size=FS, bold=False,
        dashed=False, sw=1.5, title_fill=INK):
    fill, stroke = KINDS[kind]
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
           f'stroke="{stroke}" stroke-width="{sw}"{dash}/>']
    rows = []
    if title:
        for t in title.split("\n"):
            rows.append((t, size, "bold" if bold else "normal", title_fill))
    for s in sub:
        rows.append((s, sub_size, "normal", MUTED))
    out.append(lines_block(x + w / 2, y + h / 2, rows, w - 16, title or "box"))
    return "".join(out)


def group(x, y, w, h, label, kind="neutral", dashed=True, label_size=FH, fill=None):
    gfill, stroke = KINDS[kind]
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="none" '
        f'stroke="{stroke}" stroke-width="1.2"{dash}/>'
        + text(x + 14, y + label_size + 8, label, label_size, "start", "bold", stroke)
    )


def label_at(x, y, s, size=FS, fill=INK, bg="#ffffff", anchor="middle", weight="normal"):
    """Text with a white backing so it stays legible on top of lines."""
    w = tw(s, size, weight == "bold") + 10
    h = size * 1.3
    bx = x - w / 2 if anchor == "middle" else (x - 5 if anchor == "start" else x - w + 5)
    return (
        f'<rect x="{bx:.1f}" y="{y - h * 0.78:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{bg}" opacity="0.95" rx="3"/>' + text(x, y, s, size, anchor, weight, fill)
    )


def arrow(points, label=None, at=None, dashed=False, head="arr", color=LINE, sw=1.4,
          label_size=FS, start_head=None, label_anchor="middle"):
    """Polyline through points with an arrowhead at the end.

    head: arr (filled), open (open V), tri (hollow triangle), none.
    label: drawn at `at` (x, y) or the middle of the longest segment.
    """
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    end = f' marker-end="url(#{head})"' if head != "none" else ""
    start = f' marker-start="url(#{start_head}-s)"' if start_head else ""
    out = [f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{dash}{end}{start}/>']
    if label:
        if at is None:
            segs = list(zip(points, points[1:], strict=False))
            (x0, y0), (x1, y1) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            at = ((x0 + x1) / 2, (y0 + y1) / 2 + label_size * 0.35)
        for i, part in enumerate(label.split("\n")):
            out.append(label_at(at[0], at[1] + i * label_size * 1.25, part, label_size,
                                anchor=label_anchor))
    return "".join(out)


def actor(cx, top, name, size=F):
    """UML stick figure; returns svg. Figure is ~95 px tall, name below."""
    s = LINE
    return (
        f'<circle cx="{cx}" cy="{top + 14}" r="13" fill="#fff" stroke="{s}" stroke-width="1.5"/>'
        f'<line x1="{cx}" y1="{top + 27}" x2="{cx}" y2="{top + 62}" stroke="{s}" stroke-width="1.5"/>'
        f'<line x1="{cx - 24}" y1="{top + 40}" x2="{cx + 24}" y2="{top + 40}" stroke="{s}" stroke-width="1.5"/>'
        f'<line x1="{cx}" y1="{top + 62}" x2="{cx - 20}" y2="{top + 92}" stroke="{s}" stroke-width="1.5"/>'
        f'<line x1="{cx}" y1="{top + 62}" x2="{cx + 20}" y2="{top + 92}" stroke="{s}" stroke-width="1.5"/>'
        + "".join(text(cx, top + 116 + i * size * 1.2, part, size, "middle")
                  for i, part in enumerate(name.split("\n")))
    )


def ellipse(cx, cy, rx, ry, label, kind="core", size=F - 1):
    fill, stroke = KINDS[kind]
    rows = [(t, size, "normal", INK) for t in label.split("\n")]
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.5"/>' + lines_block(cx, cy, rows, rx * 1.8, label))


def circle_proc(cx, cy, r, number, label, kind="core"):
    """DFD process (Yourdon): numbered circle."""
    fill, stroke = KINDS[kind]
    rows = [(number, FS, "bold", stroke)] + [(t, F - 1, "normal", INK) for t in label.split("\n")]
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            + lines_block(cx, cy, rows, r * 1.85, label))


def datastore(x, y, w, h, ident, label, kind="data"):
    """DFD data store: open-ended box with an id cell."""
    fill, stroke = KINDS[kind]
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="none"/>'
        f'<path d="M {x + w} {y} L {x} {y} L {x} {y + h} L {x + w} {y + h}" fill="none" '
        f'stroke="{stroke}" stroke-width="1.5"/>'
        f'<line x1="{x + 62}" y1="{y}" x2="{x + 62}" y2="{y + h}" stroke="{stroke}" stroke-width="1.5"/>'
        + text(x + 31, y + h / 2 + 7, ident, FS + 1, "middle", "bold", stroke)
        + text(x + 76, y + h / 2 + 7, label, F - 1, "start")
    )


def cylinder(x, y, w, h, title, sub=(), kind="data"):
    fill, stroke = KINDS[kind]
    e = 12
    rows = [(t, F - 1, "normal", INK) for t in title.split("\n")] + [(s, FS, "normal", MUTED) for s in sub]
    return (
        f'<path d="M {x} {y + e} L {x} {y + h - e} A {w / 2} {e} 0 0 0 {x + w} {y + h - e} '
        f'L {x + w} {y + e}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<ellipse cx="{x + w / 2}" cy="{y + e}" rx="{w / 2}" ry="{e}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        + lines_block(x + w / 2, y + h / 2 + e / 2, rows, w - 14, title)
    )


def diamond(cx, cy, w, h, label, kind="neutral", size=FS + 1):
    fill, stroke = KINDS[kind]
    pts = f"{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}"
    rows = [(t, size, "normal", INK) for t in label.split("\n")]
    return (f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            + lines_block(cx, cy, rows, w * 0.72, label))


def start_node(cx, cy, r=15):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{INK}"/>'


def end_node(cx, cy, r=17):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="{INK}" stroke-width="1.5"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r - 6}" fill="{INK}"/>')


def legend(x, y, items, size=FS):
    """items: list of (kind, label). Horizontal legend row."""
    out, cx = [], x
    for kind, label in items:
        fill, stroke = KINDS[kind]
        out.append(f'<rect x="{cx}" y="{y - 15}" width="26" height="18" rx="4" fill="{fill}" '
                   f'stroke="{stroke}" stroke-width="1.5"/>')
        out.append(text(cx + 34, y, label, size, "start", "normal", MUTED))
        cx += 34 + tw(label, size) + 30
    return "".join(out)


DEFS = f"""<defs>
<marker id="arr" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,1 L12,6 L0,11 z" fill="{LINE}"/></marker>
<marker id="arr-s" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,1 L12,6 L0,11 z" fill="{LINE}"/></marker>
<marker id="open" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="11" markerHeight="11" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M1,1 L13,7 L1,13" fill="none" stroke="{LINE}" stroke-width="1.5"/></marker>
<marker id="tri" viewBox="0 0 18 18" refX="17" refY="9" markerWidth="14" markerHeight="14" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M1,1 L17,9 L1,17 z" fill="#fff" stroke="{LINE}" stroke-width="1.5"/></marker>
<marker id="dia-s" viewBox="0 0 22 12" refX="1" refY="6" markerWidth="22" markerHeight="12" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M1,6 L11,1 L21,6 L11,11 z" fill="{LINE}" stroke="{LINE}" stroke-width="1.5"/></marker>
<marker id="odia-s" viewBox="0 0 22 12" refX="1" refY="6" markerWidth="22" markerHeight="12" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M1,6 L11,1 L21,6 L11,11 z" fill="#fff" stroke="{LINE}" stroke-width="1.8"/></marker>
</defs>"""


def svg(w, h, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'font-family="{FONT}">{DEFS}<rect width="{w}" height="{h}" fill="#ffffff"/>'
        + "".join(body) + "</svg>"
    )


def bullets(x, y, items, size=FS + 1, gap=1.45, fill=INK, max_w=None, where="bullets"):
    """Left-aligned bullet list starting at baseline y."""
    out = []
    for i, s in enumerate(items):
        yy = y + i * size * gap
        out.append(f'<circle cx="{x + 5}" cy="{yy - size * 0.33:.1f}" r="3.6" fill="{fill}"/>')
        out.append(text(x + 18, yy, s, size, "start", "normal", fill))
        if max_w and tw(s, size) + 18 > max_w:
            OVERFLOW.append(f"{where}: '{s}'")
    return "".join(out)
