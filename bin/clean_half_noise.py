"""Robust noise for the half-ROCs that actually measured something.

Runs inside the client container.  Only half-ROCs with per-half corruption == 0
carry real data (HANDOVER §1); every per-chip number computed over a broken half
is meaningless, which is how the retracted "plate effect" arose.
"""
import glob
import os
import subprocess
import sys

import numpy as np
import uproot

d_glob = sys.argv[1]
dirs = sorted(d for d in glob.glob(d_glob) if os.path.isdir(d))
print(f"{len(dirs)} run(s) matching {d_glob}\n")
print(f"{'run':18s} {'totalcorrupt':>12s}  clean halves: robust sigma = adc_iqr/1.349")
print("-" * 96)

allsig = {}
for d in dirs:
    root = os.path.join(d, "pedestal_run0.root")
    if not os.path.exists(root):
        continue
    a = uproot.open(root)["runsummary/summary"].arrays(library="np")
    m = a["channeltype"] == 0
    log = os.path.join(d, "pedestal_run0.log")
    tot = subprocess.run(["grep", "-c", "was not 0x5", log],
                         capture_output=True, text=True).stdout.strip() or "-"
    parts = []
    for c in (0, 1, 2):
        for h in (0, 1):
            k = m & (a["chip"] == c) & (a["channel"] // 36 == h)
            if np.median(a["corruption"][k]) != 0:
                continue
            sig = np.median(a["adc_iqr"][k]) / 1.349
            # corruption == 0 is necessary but NOT sufficient.  Slot A's c2h0
            # (2026-08-27) has corruption 0 with adc_mean = adc_stdd = adc_iqr = 0
            # on every channel: it emits well-formed packets full of zeros, so it
            # passes the header check while measuring nothing.  A real pedestal
            # half sits near adc_mean ~94 with a non-zero width.
            if np.median(a["adc_mean"][k]) == 0 or sig == 0:
                parts.append(f"c{c}h{h}=DEAD")
                continue
            parts.append(f"c{c}h{h}={sig:5.2f}")
            allsig.setdefault(f"c{c}h{h}", []).append(sig)
    print(f"{os.path.basename(d)[4:]:18s} {tot:>12s}  " + "  ".join(parts))

print()
for k, v in sorted(allsig.items()):
    print(f"  {k}: robust sigma {np.mean(v):.3f} ADC "
          f"(n={len(v)}, spread {min(v):.3f}-{max(v):.3f})")
