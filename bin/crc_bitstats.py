#!/usr/bin/env python3
"""Mode A, part 5: is the corruption frame-synchronous?

crc_bitlocate.py's top-6 lists hinted that every slot's dominant stuck bit sits
at **bit 27**, at word 19 (slot C), 28 (slot B) and 37 (slot A) -- positions
exactly 9 words apart. That would mean the corruption is not random but lands at
a fixed bit phase, i.e. it is synchronous with something.

Eyeballing a top-6 list is not evidence, so histogram the bit index and the word
index over EVERY single-bit-explained frame, per slot and per half.

usage: crc_bitstats.py /tmp/roc2_A.root /tmp/roc2_B.root /tmp/roc2_C.root
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
inv = {}
for w in range(NW):
    for b in range(32):
        e = np.zeros(NW, dtype=np.uint32)
        e[w] = np.uint32(1) << b
        inv[crc(e.astype('>u4').tobytes())] = (w, b)

NFRAME = 1500
allbits, allwords = Counter(), Counter()

for path in sys.argv[1:]:
    tag = path.split('_')[-1].split('.')[0]
    t = uproot.open(path)['hgcroc_rawdata/eventdata']
    a = t.arrays(['chip', 'half', 'daqdata'], library='np')
    chip, half, daq = a['chip'], a['half'], a['daqdata']
    print(f'\n===== {path} =====')
    for c in (0, 1, 2):
        for h in (0, 1):
            m = np.where((chip == c) & (half == h))[0][:NFRAME]
            if not len(m):
                continue
            bits, words, n1 = Counter(), Counter(), 0
            for i in m:
                d = np.asarray(daq[i], dtype=np.uint32)
                delta = crc(d[:NW].astype('>u4').tobytes()) ^ int(d[39])
                if delta and delta in inv:
                    w, b = inv[delta]
                    bits[b] += 1
                    words[w] += 1
                    n1 += 1
                    allbits[b] += 1
                    allwords[w] += 1
            if n1 < 5:
                continue
            tb = bits.most_common(3)
            tw = words.most_common(3)
            print(f'  chip{c}half{h}: {n1:4d} one-bit errors in {len(m)} frames')
            print(f'      bit index : ' + ', '.join(f'bit{b}={100*k/n1:.0f}%' for b, k in tb))
            print(f'      word index: ' + ', '.join(f'w{w}={100*k/n1:.0f}%' for w, k in tw))

tot = sum(allbits.values())
print(f'\n===== pooled over all slots/halves ({tot} single-bit errors) =====')
print('bit index distribution (expect ~3.1% each if uniform over 32):')
for b, k in allbits.most_common(8):
    print(f'   bit {b:>2}: {100*k/tot:5.1f}%   {"#"*int(60*k/tot)}')
print('\nword index distribution (expect ~2.6% each if uniform over 39):')
for w, k in allwords.most_common(8):
    print(f'   word {w:>2}: {100*k/tot:5.1f}%   {"#"*int(60*k/tot)}')
