#!/usr/bin/env python3
"""Set the safe's two codes: the real one and the duress one.

    python FingerLock/set_codes.py

Asks for each code without showing what you type, checks it (3 different
digits, each 1-5, as the brief asks; the two codes different) and writes unoq/finger-lock/python/codes.json.
That file is gitignored, so the codes never reach GitHub, and deploy.py copies
it to the board with the rest of the app. It also picks a random MQTT topic,
so nobody else on the public broker can read the safe's alerts by guessing it.
Run it again any time to change the codes (the topic stays unless you pass
--new-topic).
"""
import argparse
import getpass
import json
import secrets

from common import CODES_PATH
from lock_policy import CODE_LEN, check_code


def ask(name):
    while True:
        raw = getpass.getpass(f"{name} ({CODE_LEN} different digits, each 1-5, e.g. 241): ").strip()
        try:
            return list(check_code([int(c) for c in raw if c.isdigit()], name, CODE_LEN, low=1, distinct=True))
        except ValueError as e:
            print(f"  {e}. Try again.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new-topic", action="store_true", help="pick a new random MQTT topic")
    args = ap.parse_args()

    old = json.loads(CODES_PATH.read_text()) if CODES_PATH.exists() else {}
    code = ask("Real code")
    while True:
        duress = ask("Duress code")
        if duress != code:
            break
        print("  The duress code must differ from the real code. Try again.")
    topic = old.get("topic") if old.get("topic") and not args.new_topic else \
        f"ME193/Sam/safe-{secrets.token_hex(4)}"
    CODES_PATH.write_text(json.dumps({"code": code, "duress": duress, "topic": topic}, indent=2) + "\n")
    print(f"Saved {CODES_PATH.relative_to(CODES_PATH.parents[4])} (gitignored).")
    print(f"MQTT topic: {topic}")
    print(f"Dashboard:  open FingerLock/dashboard.html#{topic}")
    print("Redeploy the board app so it gets the new codes.")


if __name__ == "__main__":
    main()
