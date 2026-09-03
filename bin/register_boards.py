#!/usr/bin/env python3
"""register_boards.py A=SERIAL B=SERIAL C=SERIAL [--at UTC] -- record a board swap.

Closes every currently-open window at the swap time and opens one per slot given.
Run it the moment the boards are in, BEFORE any bring-up: partial_slot.sh names
its result directories from this registry, so a stale entry files a whole
campaign under the previous module's serial.

    register_boards.py A=320XLB4DMR00159 B=320XLB4DMR00160 C=320XLB4DMR00090

A slot left out is treated as empty from now on.  --at accepts 'YYYY-mm-ddTHH:MM:SSZ'
for a swap that happened earlier; default is now.
"""
import datetime
import json
import sys

REG = "/Users/blackmac/Docs/1Research/MMTS/Results/alabama/module_ids.json"
FOREVER = "2099-01-01T00:00:00Z"

argv = sys.argv[1:]
at = None
if "--at" in argv:
    i = argv.index("--at")
    at = argv[i + 1]
    del argv[i:i + 2]          # drop BOTH, or the timestamp is parsed as a SLOT=SERIAL
args = [a for a in argv if not a.startswith("--")]
now = at or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z")

new = {}
for a in args:
    if "=" not in a:
        sys.exit("expected SLOT=SERIAL, got %r" % a)
    s, m = a.split("=", 1)
    if s.upper() not in "ABC" or len(s) != 1:
        sys.exit("slot must be A, B or C, got %r" % s)
    new[s.upper()] = m
if not new:
    sys.exit(__doc__)

d = json.load(open(REG))
closed = [w for w in d["windows"] if w["to"] == FOREVER]
for w in closed:
    w["to"] = now
for s, m in sorted(new.items()):
    d["windows"].append({"slot": s, "from": now, "to": FOREVER, "module": m})
json.dump(d, open(REG, "w"), indent=2)

print("swap recorded at %s" % now)
for w in closed:
    print("  closed  slot %s  %s" % (w["slot"], w["module"]))
for s, m in sorted(new.items()):
    print("  open    slot %s  %s" % (s, m))
for s in "ABC":
    if s not in new:
        print("  EMPTY   slot %s" % s)
