#!/usr/bin/env python3
"""Cross-half coherence of the common mode and per-channel gain to it."""
import sys, glob
import numpy as np
import uproot

def run(root, max_events=600000):
    t = uproot.open(root)["unpacker_data/hgcroc"]
    a = t.arrays(["event", "chip", "half", "channel", "adc", "corruption"],
                 library="np", entry_stop=max_events)
    good = (a["corruption"] & 2) == 0
    cms = {}
    for c in sorted(set(a["chip"].tolist())):
        for h in sorted(set(a["half"].tolist())):
            m = good & (a["chip"] == c) & (a["half"] == h) & (a["channel"] < 36)
            if m.sum() < 1000:
                continue
            ev, ch, adc = a["event"][m], a["channel"][m], a["adc"][m].astype(float)
            uev, inv = np.unique(ev, return_inverse=True)
            chans = np.unique(ch)
            ped = {x: adc[ch == x].mean() for x in chans}
            res = adc - np.array([ped[x] for x in ch])
            cm = np.bincount(inv, weights=res) / np.bincount(inv)
            cms[(c, h)] = dict(zip(uev.tolist(), cm.tolist()))
            # per-channel slope against the CM
            slopes = []
            for x in chans:
                sel = ch == x
                y = res[sel]; xx = cm[inv[sel]]
                slopes.append((int(x), float(np.dot(xx, y) / np.dot(xx, xx))))
            s = np.array([v for _, v in slopes])
            order = sorted(slopes, key=lambda p: p[1])
            print(f"chip{c} h{h}: CM std {cm.std():.2f}  channel slope min {s.min():+.2f} "
                  f"median {np.median(s):+.2f} max {s.max():+.2f} spread(std) {s.std():.2f}")
            print("   lowest :", " ".join(f"ch{k}:{v:+.2f}" for k, v in order[:6]))
            print("   highest:", " ".join(f"ch{k}:{v:+.2f}" for k, v in order[-6:]))
    keys = list(cms)
    print("cross-half correlation of the per-event CM:")
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            common = sorted(set(cms[keys[i]]) & set(cms[keys[j]]))
            if len(common) < 500:
                continue
            x = np.array([cms[keys[i]][e] for e in common])
            y = np.array([cms[keys[j]][e] for e in common])
            r = np.corrcoef(x, y)[0, 1]
            print(f"   {keys[i]} vs {keys[j]}: r = {r:+.2f}  (n={len(common)})")

for d in sys.argv[1:]:
    for f in sorted(glob.glob(d + "/*.root")):
        print(f)
        run(f)
