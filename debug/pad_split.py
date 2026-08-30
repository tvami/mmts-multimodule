#!/usr/bin/env python3
"""Per-pad common-mode test.

For each (chip, half): the per-event mean of the 36 normal channels (CM) and,
separately, the two CM pads (unpacker channels 37 and 38).  Reports the fitted
slope of each pad against CM and the correlation.  If the pickup enters through
the half's reference (made from the CM<1>/CM<3> preamp output), one pad should
follow the channels (slope ~ +1) and the other should read ~0; if the whole
front end moves together (rail ripple), both pads follow with the same slope.
"""
import sys, glob
import numpy as np
import uproot

def run(root, max_events=600000):
    t = uproot.open(root)["unpacker_data/hgcroc"]
    a = t.arrays(["event", "chip", "half", "channel", "adc", "corruption"],
                 library="np", entry_stop=max_events)
    good = (a["corruption"] & 2) == 0
    for c in sorted(set(a["chip"].tolist())):
        for h in sorted(set(a["half"].tolist())):
            base = good & (a["chip"] == c) & (a["half"] == h)
            m = base & (a["channel"] < 36)
            if m.sum() < 1000:
                continue
            ev, ch, adc = a["event"][m], a["channel"][m], a["adc"][m].astype(float)
            uev, inv = np.unique(ev, return_inverse=True)
            chans = np.unique(ch)
            ped = {x: adc[ch == x].mean() for x in chans}
            res = adc - np.array([ped[x] for x in ch])
            cm = np.bincount(inv, weights=res) / np.bincount(inv)
            out = [f"chip{c} h{h}  CM std {cm.std():5.2f}"]
            for pad in (36, 37, 38):
                p = base & (a["channel"] == pad)
                pev, padc = a["event"][p], a["adc"][p].astype(float)
                if p.sum() < 100:
                    out.append(f"  ch{pad}: absent")
                    continue
                padc = padc - padc.mean()
                idx = np.searchsorted(uev, pev)
                ok = (idx < len(uev)) & (uev[np.clip(idx, 0, len(uev) - 1)] == pev)
                x, y = cm[idx[ok]], padc[ok]
                slope = np.dot(x, y) / np.dot(x, x)
                r = np.corrcoef(x, y)[0, 1]
                lag = 1
                acf = np.corrcoef(y[:-lag], y[lag:])[0, 1]
                out.append(f"  ch{pad}: std {y.std():5.2f} slope {slope:+5.2f} r {r:+5.2f} acf1 {acf:+5.2f}")
            print("  ".join(out))

for d in sys.argv[1:]:
    for f in sorted(glob.glob(d + "/*.root")):
        print(f)
        run(f)
