#!/usr/bin/env python3
"""Hexmap plots for LD PARTIAL boards, on their TRUE geometry.

`hexmap` master only ships LD-Full (198ch) and HD-Full (432ch) geometries, so a
partial gets drawn as a full hexagon with its channels at full-board positions --
the outline is then NOT the module's shape.

Use acrobert/hgcal-module-testing-gui master (worktree: multimodule/gui-master),
whose hexmap/ is the maintained one -- 11 board types (LF LR LL L5 LT LB, HF HB
HL HT HR), each with its own geometry AND pad->channel map.

⚠️ NOT hgcal-daq-sw/hexmap. Its `cmumac` branch has the same LR *geometry* but an
OLDER LR *channel map*: it loads the undated lr_pad_to_channel_mapping.csv while
the GUI repo loads lr_pad_to_channel_mapping_Nov2024.csv -- 182 differing lines
out of ~120 rows, i.e. almost every channel lands on a different pad. A plot made
with the old map has the right outline and the wrong channel positions.
The GUI repo also keeps lb_..._Feb2025.csv for LD Bottom, and an explicitly
_BAD.csv, so mapping VERSION matters -- always check which file gets loaded.

Two gotchas this wrapper handles:
  * add_mapping() picks its file prefix with `os.getcwd().endswith('hexmap')`, so
    the working directory must END in "hexmap" -- hence the worktree name.
  * the branch sets matplotlib text.usetex=True at import; the daq container has
    no LaTeX, so it is switched off after import.

Run in a container with uproot3 (the daq/hexplot image):
  docker exec hexplot bash -lc "python3 .../debug/hexmap_partial.py <run-dir> -t LR -l LABEL"
"""
import os
import sys
from argparse import ArgumentParser

HEXMAP = "/Users/blackmac/Docs/1Research/MMTS/multimodule/gui-hexmap/hexmap"

p = ArgumentParser()
p.add_argument("rundir")
p.add_argument("-t", "--hb_type", default="LR",
               choices=["LF", "LR", "LL", "L5", "LT", "LB", "HF", "HB", "HL", "HT", "HR"],
               help="LR = LD Right (default), LB = LD Bottom, LT = LD Top, L5 = LD Five, "
                    "LL = LD Left, LF = LD Full; HD equivalents HF/HB/HL/HT/HR")
p.add_argument("-l", "--label", default=None)
a = p.parse_args()

if not os.path.isdir(HEXMAP):
    sys.exit(f"missing {HEXMAP} -- create it with:\n"
             f"  git -C multimodule/hexmap worktree add ../cmumac-hexmap origin/cmumac")

sys.path.insert(0, HEXMAP)
os.chdir(HEXMAP)                      # add_mapping() keys its paths off cwd

import matplotlib as mpl
import plot_summary as ps
mpl.rcParams["text.usetex"] = False   # no LaTeX in the container

rundir = a.rundir.rstrip("/")
label = a.label or f"{os.path.basename(rundir)}_{a.hb_type}"
# is_live=False is required: the GUI version derives a module serial from a
# "320M..." path segment and our run paths have none, leaving moduleserial
# unbound. Passing is_live explicitly skips both branches that reference it.
ps.make_hexmap_plots_from_file(f"{rundir}/pedestal_run0.root",
                               figdir=rundir + "/", hb_type=a.hb_type,
                               label=label, is_live=False)
print(f"wrote {a.hb_type} maps to {rundir}/")
