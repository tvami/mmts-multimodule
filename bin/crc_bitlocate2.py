#!/usr/bin/env python3
"""Mode A, part 4: two-bit errors, and 'one entirely wrong word'.

crc_bitlocate.py explained chip0half1 (24 % of frames = one flipped bit at word
19 bit 27) but 0 % of chip1half0, whose deltas nonetheless repeat exactly (202
distinct in 400 frames, one at 16.5 %).  So its error is multi-bit but recurring.

Two tests here:

1. TWO-bit errors.  delta(w1,b1,w2,b2) = single(w1,b1) xor single(w2,b2), so a
   frame is a two-bit error iff `delta xor single_i` is itself a single-bit
   signature for some i -- an O(1248) lookup per frame, no 778k table needed.

2. ONE ENTIRELY WRONG WORD.  The 32 single-bit deltas of word p are the columns
   of an invertible GF(2) matrix M_p, so for ANY p there is a correction e_p with
   M_p e_p = delta.  Solvability discriminates nothing; plausibility does.  For
   the true p the corrected word D[p] xor e_p must look like real data, so report
   the spread of the corrected ADC field per candidate p -- the true position
   should stand out as narrow.
"""
import sys
from collections import Counter

import numpy as np
import uproot

TABLE = []
for b in range(256):
    c = b << 24
    for _ in range(8):
        c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
    TABLE.append(c)


def crc(buf):
    c = 0
    for by in buf:
        c = ((c << 8) & 0xFFFFFFFF) ^ TABLE[((c >> 24) ^ by) & 0xFF]
    return c


NW = 39
sig = {}                      # (w,b) -> delta
for w in range(NW):
    for b in range(32):
        e = np.zeros(NW, dtype=np.uint32)
        e[w] = np.uint32(1) << b
        sig[(w, b)] = crc(e.astype('>u4').tobytes())
inv = {v: k for k, v in sig.items()}
sig_list = list(sig.items())


def solve(p, delta):
    """Return e with M_p e = delta, i.e. the correction confined to word p."""
    cols = [sig[(p, b)] for b in range(32)]
    # Gaussian elimination over GF(2) on the 32x32 system
    rows = [(cols[b], 1 << b) for b in range(32)]
    acc, sol = [], []
    for val, tag in rows:
        v, t = val, tag
        for pv, pt in zip(acc, sol):
            if v ^ pv < v:
                v, t = v ^ pv, t ^ pt
        if v:
            acc.append(v); sol.append(t)
            order = sorted(range(len(acc)), key=lambda i: -acc[i])
            acc = [acc[i] for i in order]; sol = [sol[i] for i in order]
    v, t = delta, 0
    for pv, pt in zip(acc, sol):
        if v ^ pv < v:
            v, t = v ^ pv, t ^ pt
    return t if v == 0 else None


t = uproot.open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/roc2.root')['hgcroc_rawdata/eventdata']
a = t.arrays(['chip', 'half', 'daqdata'], library='np')
chip, half, daq = a['chip'], a['half'], a['daqdata']

TARGETS = [(0, 0), (0, 1), (1, 0), (2, 1)]      # the four failing halves
NFRAME = 200

for (c, h) in TARGETS:
    m = np.where((chip == c) & (half == h))[0][:NFRAME]
    deltas, frames = [], []
    for i in m:
        d = np.asarray(daq[i], dtype=np.uint32)
        deltas.append(crc(d[:NW].astype('>u4').tobytes()) ^ int(d[39]))
        frames.append(d)
    n = len(deltas)

    one = two = 0
    pos2 = Counter()
    for delta in deltas:
        if delta in inv:
            one += 1
            continue
        found = None
        for (wb, s) in sig_list:
            r = delta ^ s
            if r in inv:
                found = tuple(sorted([wb, inv[r]]))
                break
        if found:
            two += 1
            pos2[found] += 1
    print(f'\n=== chip{c}half{h}  ({n} frames) ===')
    print(f'  one-bit {100*one/n:5.1f}%   two-bit {100*two/n:5.1f}%   '
          f'neither {100*(n-one-two)/n:5.1f}%')
    for k, v in pos2.most_common(5):
        print(f'      bits {k}   {100*v/n:5.1f}%')

    # test 2: confine the error to a single word, see which position is plausible
    best = []
    for p in range(NW):
        corr = []
        for d, delta in zip(frames, deltas):
            e = solve(p, delta)
            if e is None:
                break
            corr.append(int(d[p]) ^ e)
        if len(corr) != len(frames):
            continue
        adc = np.array([(x >> 10) & 0x3FF for x in corr])
        best.append((float(np.std(adc)), p, float(np.median(adc))))
    best.sort()
    print('  most plausible single wrong-word positions (narrow corrected ADC):')
    for s, p, med in best[:4]:
        print(f'      word {p:>2}  corrected ADC median {med:7.1f}  std {s:7.1f}')
