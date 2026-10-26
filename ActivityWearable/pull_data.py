#!/usr/bin/env python3
"""Copy recorded sessions from the board into ActivityWearable/data/.

Skips sessions already copied. Uses the same connection as tools/deploy.py:
USB (adb) first, then Wi-Fi (UNOQ_HOST=<ip>, then HOSTS in board_secrets.py).

    python ActivityWearable/pull_data.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import deploy  # noqa: E402

from common import BOARD_DATA_DIR, DATA_DIR  # noqa: E402


def main():
    board = deploy.find_board()
    r = deploy.remote(board, f"ls {BOARD_DATA_DIR} 2>/dev/null", check=False, quiet=True, timeout=20)
    names = sorted(n for n in r.stdout.decode().split() if n.endswith(".csv")) if r else []
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    new = [n for n in names if not (DATA_DIR / n).exists()]
    print(f"{len(names)} sessions on the board, {len(new)} new")
    kind, target = board
    for n in new:
        src, dst = f"{BOARD_DATA_DIR}/{n}", str(DATA_DIR / n)
        if kind == "adb":
            deploy.run([deploy.ADB, "pull", src, dst], quiet=True)
        else:
            deploy.run(["scp", *deploy.SSH_OPTS, "-q", f"{target}:{src}", dst], quiet=True)
        print("  copied", n)


if __name__ == "__main__":
    main()
