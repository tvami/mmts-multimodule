#!/usr/bin/env python3
"""Per-half pedestal quality, scored by CRC.

🔑 THE SUMMARY `corruption` BRANCH IS BLIND TO CRC. `runanalyzer.cc` sets its flag
from head / tail / Hamming only:

    if ((head != 0x5 && head != 0xF) || (tail != 0x5 && tail != 0x2)
        || (header>>4)&0x1 || (header>>5)&0x1 || (header>>6)&0x1) corruption = 1;

There is no CRC term. `ntupler.cc` computes a richer additive code, stored in
`unpacker_data/hgcroc.corruption`:

    +1  head  != 0x5/0xF        +2  CRC32 mismatch
    +4/+8/+16  Hamming bits     +32 tail != 0x5/0x2

Decoding it (2026-08-27) showed halves reading summary corruption 0.058-0.073 --
described all day as "clean" -- failing CRC on 100% of events, and an LD Right
partial producing ZERO CRC-valid events on every half. Judge data by CRC.

Reference: LD Full slot C `chip1half1` reaches 99.2% CRC pass. That is the bar.

Two other traps this avoids:
  * event yield: dividing entries by ALL summary rows counts empty halves and calib
    channels, pinning a partial at ~75% regardless. Divide by channels with signal.
  * per-chip medians: a chip with one live half and one empty half medians to ~0 and
    looks dead. Always split by half.

usage: half_analysis.py <run-directory> [--summary-too]
"""
import sys
import numpy as np
import uproot3 as uproot

CRC_BIT = 2          # ntupler.cc: corruption += 2 on CRC32 mismatch
BITS = [(1, 'head'), (2, 'CRC32'), (4, 'Ham4'), (8, 'Ham8'), (16, 'Ham16'), (32, 'tail')]

d = sys.argv[1].rstrip('/')
show_summary = '--summary-too' in sys.argv
f = uproot.open(f'{d}/pedestal_run0.root')

# ---- per-half CRC, from the unpacker tree (the meaningful metric) -------------
t = f['unpacker_data']['hgcroc']
a = t.arrays(['chip', 'half', 'corruption'], namedecode='utf-8')
chip, half, code = a['chip'], a['half'], a['corruption'].astype(np.int64)

print(f'{"chip/half":<11}{"rows":>10}{"CRC pass":>10}{"CRC ok%":>9}'
      f'{"all-checks ok%":>16}   failing checks')
any_pass = False
for c in sorted(set(chip.tolist())):
    for h in sorted(set(half.tolist())):
        m = (chip == c) & (half == h)
        n = int(m.sum())
        if not n:
            continue
        v = code[m]
        crc_ok = int(((v & CRC_BIT) == 0).sum())
        clean = int((v == 0).sum())
        fails = ', '.join(nm for b, nm in BITS if ((v & b) != 0).mean() > 0.01)
        print(f'chip{c}half{h}  {n:>10,}{crc_ok:>10,}{100*crc_ok/n:>8.1f}%'
              f'{100*clean/n:>15.1f}%   {fails or "-"}')
        if crc_ok / n > 0.5:
            any_pass = True
print(f'\n   CRC pass is the metric. Reference: 99.2% on LD Full slot C chip1half1.')
if not any_pass:
    print('   ⚠️  NO half exceeds 50% CRC pass — this run contains essentially no valid data.')

# ---- bxcounter sanity: >3563 is physically impossible (3564 BX per orbit) -----
bx = t.arrays(['bxcounter'], namedecode='utf-8')['bxcounter']
bad_bx = int((bx > 3563).sum())
print(f'   bxcounter > 3563 (impossible): {bad_bx:,} of {len(bx):,} rows'
      f' — independent corruption indicator')

# ---- yield, divided by channels that actually carry signal --------------------
sdf = f['runsummary']['summary'].pandas.df()
normal = sdf['channeltype'] == 0
live = normal & (sdf['adc_mean'] > 1)
nlive = int(live.sum())
entries = t.numentries
print(f'\n   entries {entries:,} / {nlive} live channels -> events {entries/nlive:,.0f}'
      if nlive else '   no live channels')

# ---- optional: the old (CRC-blind) per-half summary numbers -------------------
if show_summary:
    print('\n   --- summary-tree corruption (CRC-BLIND, for comparison only) ---')
    sdf['half_'] = sdf['channel'] // 36
    for c in sorted(sdf.loc[normal, 'chip'].unique()):
        for h in (0, 1):
            m = normal & (sdf['chip'] == c) & (sdf['half_'] == h)
            if not m.sum():
                continue
            sig = int((sdf.loc[m, 'adc_mean'] > 1).sum())
            if sig == 0:
                print(f'   chip{c}half{h}: NO SOURCE (no DAQ elink)')
                continue
            print(f'   chip{c}half{h}: summary corruption {sdf.loc[m,"corruption"].mean():.3f}'
                  f'  adc_mean {np.median(sdf.loc[m,"adc_mean"]):7.2f}'
                  f'  robust sigma {np.median(sdf.loc[m,"adc_iqr"])/1.349:6.2f}')
