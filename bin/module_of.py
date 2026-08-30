#!/usr/bin/env python3
"""Serial of the board in a slot at a given time, from the module registry.

    module_of.py B                  -> serial for slot B now
    module_of.py B 20260829_223154  -> serial for slot B at that UTC run stamp

Prints nothing (exit 1) when no window matches, so callers can fall back.
Registry: Results/alabama/module_ids.json, windows keyed by slot and UTC.
"""
import json
import os
import sys
from datetime import datetime, timezone

REG = "/Users/blackmac/Docs/1Research/MMTS/Results/alabama/module_ids.json"


def module_of(slot, stamp=None):
    if not os.path.exists(REG):
        return None
    t = (datetime.strptime(stamp, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
         if stamp else datetime.now(timezone.utc))
    for w in json.load(open(REG))["windows"]:
        f = datetime.fromisoformat(w["from"].replace("Z", "+00:00"))
        to = datetime.fromisoformat(w["to"].replace("Z", "+00:00"))
        if w["slot"] == slot.upper() and f <= t < to:
            return w["module"]
    return None


if __name__ == "__main__":
    m = module_of(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    if not m:
        sys.exit(1)
    print(m)
