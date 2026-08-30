#!/usr/bin/env python3
"""Hexmap plots with ROBUST noise and a CLIPPED colour scale.

Two problems with `hexmap/plot_summary.py` output on a corrupt partial:

1. It plots `adc_stdd`, but this bench's runbook says to trust the robust width
   `adc_iqr / 1.349` -- not a column in the tree. Corruption inflates `adc_stdd`
   via outliers while barely moving the IQR, so the ratio of the two is
   effectively a corruption map.

2. The colour scale is set by the data range, so ONE bad channel hides everything
   else. Measured 2026-08-27 on run_20260827_235446: a single channel at 115 ADC
   stretched the scale to 0-110, rendering 68 of 108 channels that sit at 20-30
   ADC as dark blue -- indistinguishable from the genuinely clean half at 0.7.
   The plot read as "one bad cell" when in fact all of chip0 was bad.

Adds, and plots on a clipped scale:
  adc_robust_noise   = adc_iqr / 1.349          (Gaussian-equivalent sigma)
  adc_stdd_over_rob  = adc_stdd / robust        (>> 1 = outlier-driven)
  *_clipped          = the above and adc_stdd, capped at --clip

Healthy reference on this bench: robust sigma ~= 0.74 ADC.

Run inside the daq container (needs uproot3):
  docker exec daq bash -lc "python3 .../debug/hexmap_robust.py <run-dir> [-t LF] [-l LABEL] [--clip 5]"

⚠️ 2026-08-29: this pointed at hgcal-daq-sw/hexmap, which is DEPRECATED and has
been deleted. It now uses acrobert/hgcal-module-testing-gui (worktree
multimodule/gui-hexmap), whose "LF" type loads
channel_maps/ld_pad_to_channel_mapping_V3.csv -- the LD Full V3 map the old repo
never shipped. Maps made before this date have the right outline and the WRONG
channel positions; board types are now LF/LR/LL/L5/LT/LB + HF/HB/HL/HT/HR.
"""
import sys
import os
import re as _re0
from argparse import ArgumentParser

HEXMAP = "/Users/blackmac/Docs/1Research/MMTS/multimodule/gui-hexmap/hexmap"
sys.path.insert(0, HEXMAP)
os.chdir(HEXMAP)          # add_mapping() keys its paths off a cwd ending in "hexmap"

import numpy as np
import uproot3 as uproot
import matplotlib as mpl
import plot_summary as ps

mpl.rcParams["text.usetex"] = False   # no LaTeX in the container

p = ArgumentParser()
p.add_argument("rundir")
p.add_argument("-l", "--label", default=None)
p.add_argument("-t", "--hb_type", default=None,
               choices=["LF", "LR", "LL", "L5", "LT", "LB",
                        "HF", "HB", "HL", "HT", "HR"],
               help="board type in the GUI repo's naming, not LD/HD. Default: taken "
                    "from characters 5-6 of the serial (320X**LF**4CQH00443 = LD Full, "
                    "320X**LR**4DQE00020 = LD Right); falls back to LF")
p.add_argument("--clip", type=float, default=5.0,
               help="cap the noise colour scale at this many ADC (default 5; "
                    "healthy is ~0.74, so anything above saturates)")
p.add_argument("--keep-toa-tot", action="store_true",
               help="also plot the toa/tot maps (default: adc only, for speed)")
p.add_argument("-m", "--module", default=None,
               help="hexaboard serial (e.g. 320TSYMM1030078) for the title and file "
                    "names; default: looked up in Results/alabama/module_ids.json by "
                    "slot and run time")
a = p.parse_args()

rundir = a.rundir.rstrip("/")


def module_for_run(rundir):
    """Serial of the board in this run's slot at this run's time, from the registry.

    Slot comes from the DUT directory (Mux<S>_...), time from run_YYYYMMDD_HHMMSS
    (UTC).  Returns None if either cannot be resolved or no window matches.
    """
    import json
    import re
    from datetime import datetime, timezone
    reg = "/Users/blackmac/Docs/1Research/MMTS/Results/alabama/module_ids.json"
    # Directory is "MuxB_rxeq4" in the old flat layout and plain "MuxB" in the
    # by-board layout, so the slot letter may be followed by "_" or "/".
    mslot = re.search(r"/Mux([ABC])[_/]", rundir + "/")
    mts = re.search(r"run_(\d{8})_(\d{6})", rundir)
    if not (mslot and mts and os.path.exists(reg)):
        return None
    t = datetime.strptime(mts.group(1) + mts.group(2), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    for w in json.load(open(reg))["windows"]:
        f = datetime.fromisoformat(w["from"].replace("Z", "+00:00"))
        to = datetime.fromisoformat(w["to"].replace("Z", "+00:00"))
        if w["slot"] == mslot.group(1) and f <= t < to:
            return w["module"]
    return None


# A run already stored under its board carries the serial in its path; trust
# that over the registry, which cannot be wrong about a directory it named.
_inpath = _re0.search(r"/(3\d{2}[A-Z]{4}\w+)/Mux[ABC]/", rundir + "/")
module = a.module or (_inpath.group(1) if _inpath else None) or module_for_run(rundir)
# Label = slot + firmware variant + serial, e.g. "MuxB_rxeq4_320TSYMM1030078".
# Run tags in the DUT name ("swap", "crc", ...) and the timestamp are left out:
# the run directory already carries both.  No 'run_' token either, since the
# plotter would print that UTC timestamp as local time.
import re as _re
_dut = os.path.basename(os.path.dirname(os.path.dirname(rundir)))
_slot = _re.match(r"Mux[ABC]", _dut)
_slot = _slot.group(0) if _slot else _dut
_variant = next((v for v in ("uaf2stock", "rxeq2", "rxeq4", "rxlp", "stock")
                 if v in _dut.split("_")), "")
label = a.label or "_".join(x for x in (_slot, _variant) if x)

# The serial goes in the OUTPUT DIRECTORY name, not in every file name, so the
# png names stay short and comparable across boards.  plot_summary derives the
# file name from `label`, so the title is decorated separately.
if module:
    _plain = ps._label_for_title
    ps._label_for_title = lambda lab: f"{_plain(lab)} {module}".strip()

# The serial encodes the board type: 320X<TT>..., TT = LF, LR, LL, HF, ...
_types = {"LF", "LR", "LL", "L5", "LT", "LB", "HF", "HB", "HL", "HT", "HR"}
if a.hb_type is None:
    _from_serial = (module or "")[4:6].upper()
    a.hb_type = _from_serial if _from_serial in _types else "LF"
print(f"module: {module or 'UNKNOWN (not in module_ids.json; pass -m)'}   "
      f"type: {a.hb_type}   label: {label}")
df = uproot.open(f"{rundir}/pedestal_run0.root")["runsummary"]["summary"].pandas.df()

if "adc_iqr" not in df.columns:
    sys.exit("no adc_iqr column -- cannot form the robust width")

rob = df["adc_iqr"] / 1.349
df["adc_robust_noise"] = rob
df["adc_stdd_over_rob"] = np.where(rob > 0.01, df["adc_stdd"] / rob, -1)

# Clipped copies. plot_summary colours by data range, so capping the VALUES is
# what caps the scale. Named _clipped so the plot cannot be mistaken for raw.
c = a.clip
df["adc_stdd_clipped"] = df["adc_stdd"].clip(upper=c)
df["adc_robust_noise_clipped"] = rob.clip(upper=c)
df["adc_stdd_over_rob_clipped"] = df["adc_stdd_over_rob"].clip(upper=10)

if not a.keep_toa_tot:
    drop = [x for x in df.columns if ("toa" in x or "tot" in x)]
    df = df.drop(columns=drop)

norm = df["channeltype"] == 0
live = df[norm & (df["adc_mean"] > 1)]
print(f"{label}: {len(live)} live normal channels (clip = {c} ADC)")
print(f"  adc_stdd     median {live['adc_stdd'].median():7.2f}   max {live['adc_stdd'].max():7.2f}")
print(f"  robust sigma median {live['adc_robust_noise'].median():7.2f}   "
      f"(healthy on this bench ~0.74)")
print(f"  stdd/robust  median {live['adc_stdd_over_rob'].median():7.2f}   "
      f"(>>1 = outlier-driven, i.e. corruption)")
print(f"  channels above {c} ADC robust: {int((live['adc_robust_noise'] > c).sum())} of {len(live)}")

# The GUI repo's plot_adc_hexmaps hardcodes `for column in ['adc_mean','adc_stdd']`,
# so extra columns are silently ignored (the old deprecated repo plotted every
# adc* column).  Feed each quantity through the adc_stdd slot instead, one call
# per quantity, and name the output for what it actually holds.
df = ps.add_mapping(df, hb_type=a.hb_type)
# Maps are collected per BOARD: Results/alabama/<serial>/<YYYYMMDD_HHMMSS>/,
# so one module's whole history sits together no matter which slot it was in.
# The run directory itself is left alone; RESULTS_*.md cites those names.
# If the run already lives under its board (Results/alabama/<serial>/Mux<slot>/...,
# the layout ped_run.sh and delay_scan.sh now use) the maps go beside the data.
# Older flat runs are collected into Results/alabama/<serial>/<slot>/<stamp>/.
_stamp = _re.search(r"run_(\d{8}_\d{6})", rundir)
if module and f"/{module}/" in rundir:
    figdir = rundir + "/"
elif module and _stamp:
    _res = os.path.dirname(os.path.dirname(os.path.dirname(rundir)))
    figdir = f"{_res}/{module}/{_slot}/{_stamp.group(1)}/"
else:
    figdir = rundir + "/"
os.makedirs(figdir, exist_ok=True)

# raw adc_mean/adc_stdd, plus the 1D channel/pad plots -- once, unmodified
ps.plot_adc_hexmaps(df, figdir, a.hb_type, label)
ps.plot_channels(df, figdir, a.hb_type, label)
ps.plot_pads(df, figdir, a.hb_type, label)

for suffix, col in (("robust", "adc_robust_noise_clipped"),
                    ("stddOverRob", "adc_stdd_over_rob_clipped"),
                    ("stddClipped", "adc_stdd_clipped")):
    d = df.copy()
    d["adc_stdd"] = d[col]
    ps.plot_adc_hexmaps(d, figdir, a.hb_type, f"{label}_{suffix}")

print(f"wrote maps to {rundir}/  "
      f"(*_robust = adc_iqr/1.349, *_stddOverRob = corruption map)")
