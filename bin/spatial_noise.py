#!/usr/bin/env python3
"""Is the LD Left noise localised in space, and where?

Joins per-channel robust noise (adc_iqr/1.349) to pad positions via the GUI
repo's LL map + geometry, then reports the noise centroid and a y/x profile.
"""
import sys, csv, numpy as np, uproot

run = sys.argv[1]
bt = (sys.argv[2] if len(sys.argv) > 2 else 'll').lower()
H = '/Users/blackmac/Docs/1Research/MMTS/multimodule/gui-hexmap/hexmap'

pad2ch = {}
for r in csv.DictReader(open(f'{H}/channel_maps/{bt}_pad_to_channel_mapping_Nov2024.csv')):
    if int(r['Channeltype']) == 0:
        pad2ch[int(r['PAD'])] = (int(r['ASIC']), int(r['Channel']))

pos = {}
for line in open(f'{H}/geometries/hex_positions_HPK_{bt.upper()}_8inch_edge_ring_testcap.txt'):
    if line.startswith('#') or not line.strip():
        continue
    f = line.split()
    pos[int(f[0])] = (float(f[1]), float(f[2]))

s = uproot.open(run + '/pedestal_run0.root')['runsummary/summary'].arrays(library='np')
key = {(int(c), int(ch)): i for i, (c, ch) in enumerate(zip(s['chip'], s['channel']))}
# adc_stdd, not adc_iqr/1.349: the robust sigma is quantised near 1 ADC
# (only 0.74 or 1.48) and cannot resolve a gradient on a quiet board.
noise = s['adc_stdd']

rows = []
for pad, (asic, ch) in pad2ch.items():
    i = key.get((asic, ch))
    if i is None or pad not in pos:
        continue
    rows.append((pos[pad][0], pos[pad][1], float(noise[i])))
x, y, n = (np.array(v) for v in zip(*rows))
print(f'{len(n)} pads matched   noise median {np.median(n):.2f}  max {n.max():.2f}')

w = n - n.min()
print(f'noise-weighted centroid : x {np.average(x, weights=w):+.2f}  y {np.average(y, weights=w):+.2f}')
print(f'geometric centroid      : x {x.mean():+.2f}  y {y.mean():+.2f}')

top = n >= np.quantile(n, 0.9)
print(f'top-decile centroid     : x {x[top].mean():+.2f}  y {y[top].mean():+.2f}  (n={top.sum()})')
bot = n <= np.quantile(n, 0.1)
print(f'bottom-decile centroid  : x {x[bot].mean():+.2f}  y {y[bot].mean():+.2f}  (n={bot.sum()})')

print(f'\ncorrelation noise vs y : {np.corrcoef(y, n)[0,1]:+.3f}')
print(f'correlation noise vs x : {np.corrcoef(x, n)[0,1]:+.3f}')

print('\n y band      npads  median noise')
for lo, hi in [(-6,-4),(-4,-2),(-2,0),(0,2),(2,4),(4,6)]:
    m = (y >= lo) & (y < hi)
    if m.sum():
        print(f'  {lo:+3.0f} to {hi:+3.0f}   {m.sum():4d}   {np.median(n[m]):.2f}')
