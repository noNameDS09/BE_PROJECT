"""Build every report figure: svg/<name>.svg and png/<name>.png (2x, for Word).

    uv run python docs/report/diagrams/build.py            # all figures
    uv run python docs/report/diagrams/build.py fig04      # names starting with fig04

PNGs are rendered with headless Google Chrome so text looks exactly like the SVG.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fig_arch  # noqa: E402
import fig_flow  # noqa: E402
import fig_uml  # noqa: E402
import lib  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FIGURES = {**fig_arch.FIGURES, **fig_uml.FIGURES, **fig_flow.FIGURES}


def render(name: str, svg_text: str, w: int, h: int) -> None:
    (HERE / "svg").mkdir(exist_ok=True)
    (HERE / "png").mkdir(exist_ok=True)
    svg_path = HERE / "svg" / f"{name}.svg"
    svg_path.write_text(svg_text)
    png = HERE / "png" / f"{name}.png"
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=2", f"--window-size={w},{h}",
         f"--screenshot={png}", svg_path.as_uri()],
        check=True, capture_output=True,
    )  # fmt: skip


def main() -> None:
    prefix = sys.argv[1] if len(sys.argv) > 1 else ""
    for name, fn in FIGURES.items():
        if not name.startswith(prefix):
            continue
        lib.OVERFLOW.clear()
        w, h, body = fn()
        render(name, lib.svg(w, h, body), w, h)
        print(f"{name}: {w}x{h}")
        for o in lib.OVERFLOW:
            print(f"   overflow? {o}")


if __name__ == "__main__":
    main()
