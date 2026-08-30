#!/usr/bin/env python3
"""Common-mode decomposition of a pedestal run.

Nothing in hexactrl-sw subtracts common mode.  `pedestal_run_analysis.py` only
PLOTS the CM pads (channeltype 100) and flags dead ones, so the `adc_stdd` it
reports still contains the CM.  Trimming does not do it either: trims are one
static number per channel, while the CM is a coherent fluctuation that changes
event to event across all 36 channels of a half.

For every (chip, half) this reports, over CRC-good events only:

  total     std of (adc - per-channel pedestal), i.e. what adc_stdd measures
  CM        std of the per-event common mode
  resid     std after subtracting it, the noise that is actually per channel
  frac      CM^2 / total^2, how much of the variance is common mode
  ACF 1/5   autocorrelation of the CM at lags 1 and 5 events.  A damped
            oscillation (+0.6 / -0.4) is the periodic bench pickup of
            RESULTS 4j/4k; ~0 means the CM is just white noise

Two estimators of the CM, selectable with --cm:
  mean  (default)  per-event mean of the 36 normal channels.  Always available,
                   but it also absorbs real signal, so it is right for pedestals
                   and wrong for physics data.
  pads             per-event mean of that half's CM pads (channeltype 100),
                   which see the common mode without seeing the pad signal.
                   This is what the pads are for; falls back to `mean` per half
                   if the pads are dead or absent.

usage (inside the daq container, needs uproot):
  python3 debug/cm_analysis.py <run-dir> [<run-dir> ...] [--cm pads] [--csv out.csv]
"""
import argparse
import glob
import os
import sys

import numpy as np
import uproot


def decompose(root, cm_source="mean", max_events=900000):
    """Per (chip, half): total / CM / residual noise and the CM autocorrelation."""
    t = uproot.open(root)["unpacker_data/hgcroc"]
    a = t.arrays(["event", "chip", "half", "channel", "adc", "corruption"],
                 library="np", entry_stop=max_events)
    # In unpacker_data/hgcroc a half is channels 0-38: 0-35 normal, 36 calib,
    # 37-38 the two CM pads.  There is no channeltype branch here; that lives in
    # runsummary/summary.
    good = (a["corruption"] & 2) == 0          # CRC-valid frames only
    rows = []
    for c in sorted(set(a["chip"].tolist())):
        for h in sorted(set(a["half"].tolist())):
            base = good & (a["chip"] == c) & (a["half"] == h)
            m = base & (a["channel"] < 36)
            if m.sum() < 1000:
                continue
            ev, ch = a["event"][m], a["channel"][m]
            adc = a["adc"][m].astype(float)
            uev, inv = np.unique(ev, return_inverse=True)
            n = np.bincount(inv)
            # per-channel pedestal, then residual about it
            chans = np.unique(ch)
            ped = {x: adc[ch == x].mean() for x in chans}
            res = adc - np.array([ped[x] for x in ch])

            used = cm_source
            if cm_source == "pads":
                p = base & (a["channel"] >= 37)
                pev, padc = a["event"][p], a["adc"][p].astype(float)
                # CM pads must cover the same events to be usable
                if p.sum() < 100 or padc.std() < 1e-6:
                    used = "mean (pads dead/absent)"
                else:
                    pidx = np.searchsorted(uev, pev)
                    ok = (pidx < len(uev)) & (uev[np.clip(pidx, 0, len(uev) - 1)] == pev)
                    pidx, padc = pidx[ok], padc[ok]
                    cnt = np.bincount(pidx, minlength=len(uev))
                    z = np.zeros(len(uev))
                    np.add.at(z, pidx, padc)
                    z = np.where(cnt > 0, z / np.maximum(cnt, 1), np.nan)
                    if np.isnan(z).mean() > 0.1:
                        used = "mean (pads sparse)"
                    else:
                        z = np.where(np.isnan(z), np.nanmean(z), z)
                        z -= z.mean()
            if used.startswith("mean"):
                z = np.bincount(inv, res) / n
                z = z - z.mean()

            # The CM pads are a different circuit with their own gain, so the
            # raw pad value must be SCALED before subtraction: least squares
            # slope of the channel residual on the pad common mode.  (Subtracting
            # it raw makes the noise worse: pad CM 8.85 against a total of 3.61.)
            # For the `mean` estimator the slope comes out ~1 by construction.
            zev = z[inv]
            denom = float((zev * zev).sum())
            slope = float((res * zev).sum() / denom) if denom > 0 else 0.0
            z = z * slope
            resid = (res - z[inv]).std()
            tot = res.std()
            zz = z - z.mean()
            acf = [float(np.corrcoef(zz[:-L], zz[L:])[0, 1]) if len(zz) > L + 10 else float("nan")
                   for L in (1, 5)]
            rows.append(dict(chip=c, half=h, nev=len(uev), total=tot, cm=z.std(),
                             resid=resid, frac=(z.std() ** 2 / tot ** 2) if tot else float("nan"),
                             acf1=acf[0], acf5=acf[1], cm_from=used, slope=slope))
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rundirs", nargs="+", help="run directory, or a glob of them")
    p.add_argument("--cm", choices=["mean", "pads"], default="mean",
                   help="CM estimator: per-event mean of normal channels (default), "
                        "or the CM pads (channeltype 100)")
    p.add_argument("--csv", default=None, help="also write the table here")
    a = p.parse_args()

    dirs = []
    for d in a.rundirs:
        dirs += sorted(glob.glob(d)) if any(ch in d for ch in "*?[") else [d]

    print(f"{'run':<22}{'ch/h':>5}{'nev':>8}{'total':>8}{'CM':>7}{'resid':>8}"
          f"{'CMfrac':>8}{'ACF1':>7}{'ACF5':>7}{'k':>7}  cm_from")
    out = []
    for d in dirs:
        root = os.path.join(d.rstrip("/"), "pedestal_run0.root")
        if not os.path.exists(root):
            continue
        for r in decompose(root, a.cm):
            r["run"] = os.path.basename(d.rstrip("/"))
            out.append(r)
            print(f"{r['run']:<22}{r['chip']}/{r['half']:<3}{r['nev']:>8}"
                  f"{r['total']:>8.2f}{r['cm']:>7.2f}{r['resid']:>8.2f}"
                  f"{r['frac']:>8.2f}{r['acf1']:>+7.2f}{r['acf5']:>+7.2f}"
                  f"{r['slope']:>7.2f}  {r['cm_from']}")
    if not out:
        sys.exit("no runs with pedestal_run0.root found")
    if a.csv:
        import csv
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print("wrote", a.csv)

    med = lambda k: float(np.median([r[k] for r in out]))
    print(f"\nmedian over {len(out)} halves: total {med('total'):.2f} -> resid "
          f"{med('resid'):.2f}  (CM is {100*med('frac'):.0f} % of the variance), "
          f"ACF1 {med('acf1'):+.2f}")


if __name__ == "__main__":
    main()
