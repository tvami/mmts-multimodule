#!/usr/bin/env python3
"""Summarise a set of pedestal runs per half: CRC pass and adc_mean, with spread.

For before/after comparisons (e.g. a trophy swap) a single run is not enough to
read a change -- but it is also not necessary to look at ten tables. This gives
median and min-max per half across a glob of run directories.

BOTH metrics are printed on purpose. CRC pass alone is not sufficient: a half
whose pedestal has railed reads adc_mean 0 and then scores a HEALTHY CRC rate,
because an all-zero frame has no `1` bits for the link to drop. `dead` marks any
half at adc_mean < 1 -- such a half is silenced, not working.

usage: summarise_runs.py 'Results/alabama/MuxC_preswap/pedestal_run/run_*'
"""
import glob
import sys

import numpy as np
import uproot

dirs = sorted(d for d in glob.glob(sys.argv[1]) if glob.glob(d + '/pedestal_run0.root'))
if not dirs:
    raise SystemExit(f'no runs with a .root under {sys.argv[1]}')

crc = {}
ped = {}
for d in dirs:
    f = uproot.open(d + '/pedestal_run0.root')
    t = f['unpacker_data/hgcroc']
    a = t.arrays(['chip', 'half', 'corruption'], library='np')
    chip, half, code = a['chip'], a['half'], a['corruption'].astype('int64')
    s = f['runsummary/summary'].arrays(library='np')
    norm = s['channeltype'] == 0
    for c in (0, 1, 2):
        for h in (0, 1):
            m = (chip == c) & (half == h)
            if not m.sum():
                continue
            crc.setdefault((c, h), []).append(((code[m] & 2) == 0).mean())
            sm = norm & (s['chip'] == c) & (s['channel'] // 36 == h)
            ped.setdefault((c, h), []).append(
                float(np.median(s['adc_mean'][sm])) if sm.sum() else -1)

print(f'{len(dirs)} runs: {dirs[0].split("_")[-1]} .. {dirs[-1].split("_")[-1]}\n')
print(f'{"half":<11}{"CRC median":>12}{"CRC min-max":>20}'
      f'{"adc_mean median":>18}{"verdict":>12}')
for k in sorted(crc):
    c, h = k
    v = np.array(crc[k])
    p = np.array(ped[k])
    pm = np.median(p)
    verdict = 'DEAD' if pm < 1 else ('good' if np.median(v) > 0.5 else 'FAIL')
    print(f'chip{c}half{h}  {np.median(v):>12.3f}'
          f'{f"{v.min():.3f} - {v.max():.3f}":>20}{pm:>18.1f}{verdict:>12}')

print('\n  CRC pass is the data-integrity metric; adc_mean guards against a half'
      '\n  whose pedestal has railed (adc_mean 0 scores a healthy CRC rate because'
      '\n  an all-zero frame has no ones to drop).')
