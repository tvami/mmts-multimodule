"""Per-link eye width and centre from delay scans already on disk.

E1 of PLAN_slotA_wandering_trigger_link.md -- costs no bench time.

"18/18" only says every link produced a branch.  What matters for whether a link
will still be aligned at START is the PHASE MARGIN: how many contiguous idelay
taps are error-free, and where the centre of that window sits.  A link with a
narrow eye passes an 18/18 gate and then falls over.

  width  -> narrow on slot A vs B/C  => marginal hardware / phase margin (H1/H4)
  centre -> moves between bring-ups on A but stable on B/C => phase lottery (H2)

delayScanTree is long-format: one row per (link, idelay) with alignedCount,
errorCount, nIdles.

Usage (inside the client container):
    python3 eye_stats.py 'Results/alabama/MuxA/delay_scan/*'
"""
import glob
import os
import sys

import numpy as np
import uproot


def widest_run(mask):
    """(width, centre_index) of the widest contiguous True run."""
    best_len = best_start = cur_len = cur_start = 0
    for i, g in enumerate(mask):
        if g:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
        else:
            cur_len = 0
    if best_len == 0:
        return 0, -1
    return best_len, best_start + best_len // 2


def main():
    dirs = sorted(d for d in glob.glob(sys.argv[1]) if os.path.isdir(d))
    for d in dirs:
        f = os.path.join(d, "delayScan0.root")
        if not os.path.exists(f):
            continue
        a = uproot.open(f)["delayScanTree"].arrays(library="np")
        links = [l for l in np.unique(a["link"]) if "trg" in str(l)]
        links.sort(key=lambda s: int(str(s).split("link")[-1]))
        print(f"\n{os.path.basename(d)}   ({len(links)} trigger links)")
        parts = []
        for l in links:
            k = a["link"] == l
            order = np.argsort(a["idelay"][k])
            err = a["errorCount"][k][order]
            aligned = a["alignedCount"][k][order]
            taps = a["idelay"][k][order]
            good = (err == 0) & (aligned > 0)
            w, ci = widest_run(good)
            centre = int(taps[ci]) if ci >= 0 else -1
            parts.append(f"{str(l).split('.')[-1]:>7}: w={w:3d} c={centre:3d}")
        for i in range(0, len(parts), 3):
            print("   " + "   ".join(parts[i:i + 3]))
        widths = []
        for l in links:
            k = a["link"] == l
            order = np.argsort(a["idelay"][k])
            good = (a["errorCount"][k][order] == 0) & (a["alignedCount"][k][order] > 0)
            widths.append(widest_run(good)[0])
        widths = np.array(widths)
        print(f"   -> width median {np.median(widths):.0f}, min {widths.min()}, "
              f"links with width 0: {(widths == 0).sum()}")


if __name__ == "__main__":
    main()
