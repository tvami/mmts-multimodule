#!/usr/bin/env python3
"""Per-link raw statistics from a delay-scan ROOT tree.

The summary.json trio (ngood/nbad/nturnon) collapses two physically different
cases into `nturnon`: a link that is QUIET (nothing arriving, errorCount==0) and
a link that is RECEIVING but never locks (errorCount high).  The raw tree keeps
errorCount / alignedCount / nIdles per delay setting, which separates them.

Usage: python3 link_raw_stats.py <run_dir> [<run_dir> ...]
"""
import sys
import uproot
import numpy as np

HDR = "{:<26}{:>8}{:>8}{:>9}{:>8}{:>9}{:>10}".format(
    "link", "n(err=0)", "errMax", "errMean", "aliMax", "idleMax", "idleMean")


def stats(path, tag):
    t = uproot.open(path + "/delayScan0.root")["delayScanTree"]
    a = t.arrays(["link", "idelay", "alignedCount", "errorCount", "nIdles"],
                 library="np")
    links = a["link"]
    print("\n===== %s =====" % tag)
    print(HDR)

    def key(s):
        s = s.decode() if isinstance(s, bytes) else str(s)
        return ("trg" in s, len(s), s)

    for L in sorted(set(links), key=key):
        m = links == L
        e = a["errorCount"][m]
        al = a["alignedCount"][m]
        idl = a["nIdles"][m]
        name = L.decode() if isinstance(L, bytes) else str(L)
        print("{:<26}{:>8}{:>8}{:>9.1f}{:>8}{:>9}{:>10.1f}".format(
            name, int((e == 0).sum()), int(e.max()), float(e.mean()),
            int(al.max()), int(idl.max()), float(idl.mean())))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        stats(p, p.rstrip("/").split("/")[-1])
