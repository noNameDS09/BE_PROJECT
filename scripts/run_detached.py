"""Start a long command in its own session, so closing the terminal or the Claude app does
not stop it, and keep the Mac awake while it runs (caffeinate).

    uv run python scripts/run_detached.py data/logs/run.txt -- uv run loupe eval run gold_calc ...

Prints the process id; follow progress with `tail -f <log>`.
"""

import subprocess
import sys

if __name__ == "__main__":
    if "--" not in sys.argv or len(sys.argv) < 4:
        sys.exit(__doc__)
    log, cmd = sys.argv[1], sys.argv[sys.argv.index("--") + 1 :]
    with open(log, "a") as out:
        proc = subprocess.Popen(
            ["caffeinate", "-i", *cmd],
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    print(proc.pid)
