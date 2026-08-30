#!/usr/bin/env python3
"""Mode A, part 3: locate the corrupted bit(s) exactly, using CRC linearity.

CRC-32 with init 0 and no final XOR is linear over GF(2):
    CRC(A) xor CRC(B) = CRC(A xor B)
so for a frame D whose stored target is T,
    delta = CRC(D) xor T = CRC(E),  where E = D xor D_true
is the CRC *of the error pattern alone*.

There are only 39*32 = 1248 single-bit error patterns, so their deltas can be
tabulated exhaustively.  Any frame whose delta appears in that table is
explained by exactly ONE flipped bit, and the table says WHICH word and WHICH
bit.  That converts "the CRC never matches" into a physical statement about
where in the frame the corruption lands.

Run after:
    unpack -i pedestal_run0.raw -o /tmp/roc2.root -t roc2root     (no -M !)
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


NW = 39   # words covered by the CRC

# delta of a single flipped bit: word w, bit b (bit 0 = LSB of the 32-bit word)
single = {}
for w in range(NW):
    for b in range(32):
        e = np.zeros(NW, dtype=np.uint32)
        e[w] = np.uint32(1) << b
        single[crc(e.astype('>u4').tobytes())] = (w, b)
print(f'tabulated {len(single)} single-bit error signatures '
      f'({NW}*32 = {NW*32} possible)\n')

t = uproot.open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/roc2.root')['hgcroc_rawdata/eventdata']
a = t.arrays(['chip', 'half', 'daqdata'], library='np')
chip, half, daq = a['chip'], a['half'], a['daqdata']

NFRAME = 400
for c in (0, 1, 2):
    for h in (0, 1):
        m = np.where((chip == c) & (half == h))[0][:NFRAME]
        if not len(m):
            continue
        hits, zero, other = Counter(), 0, 0
        for i in m:
            d = np.asarray(daq[i], dtype=np.uint32)
            delta = crc(d[:NW].astype('>u4').tobytes()) ^ int(d[39])
            if delta == 0:
                zero += 1
            elif delta in single:
                hits[single[delta]] += 1
            else:
                other += 1
        n = len(m)
        print(f'chip{c}half{h}  frames {n}   CRC-ok {100*zero/n:5.1f}%   '
              f'explained by ONE bit flip {100*sum(hits.values())/n:5.1f}%   '
              f'unexplained {100*other/n:5.1f}%')
        for (w, b), k in hits.most_common(6):
            print(f'      word {w:>2}  bit {b:>2}   {100*k/n:5.1f}% of frames')
