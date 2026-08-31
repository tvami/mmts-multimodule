#!/usr/bin/env python3
"""gate.py <dut-dir> -- read the newest delay scan and say whether to proceed.

PASS means every DAQ and trigger link listed in the config found a good delay.
Anything less and daq-server refuses START, so the pedestal would burn its full
timeout. A FAIL is a retry, not a result: re-run the bring-up and scan again.
"""
import glob
import json
import os
import sys

paths = sorted(glob.glob(sys.argv[1] + "/delay_scan/*/summary.json"))
if not paths:
    sys.exit("no summary.json -- the scan did not produce output")
d = paths[-1]
s = json.load(open(d))
print(os.path.dirname(d))
bad = 0
for kind in ("daq", "trg"):
    ks = [k for k in s if kind in k]
    ok = sum(1 for k in ks if s[k]["ngood"] > 0)
    bad += len(ks) - ok
    print(f"  {kind}: {ok}/{len(ks)}  " +
          " ".join(f"{k.split('.')[-1]}={s[k]['ngood']}" for k in ks))
print("GATE: PASS -- safe to run pedestals" if bad == 0 else
      f"GATE: FAIL -- {bad} link(s) at ngood 0; daq-server will refuse START")
sys.exit(0 if bad == 0 else 1)
