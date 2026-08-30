#!/usr/bin/env python3
"""Compare corruption against pedestal across Inv_vref settings.

The mechanism (RESULTS §4c/§4f) says the links drop `1` bits, worst for an
isolated `1` in a run of zeros, and that in a pedestal run every `1` lives in the
`adcm` field.  So the pedestal -- set by `Inv_vref` -- controls how many
droppable ones the frame contains.  This tabulates, per half and per setting:

    CRC pass, mean adcm, 1-bits/word, and how much of the corruption is
    explained by a single flipped bit

usage: vref_compare.py LABEL=/path/to/run_dir [LABEL=... ...]
       (run dirs must already have pedestal_run0.raw; roc2root is made here)
"""
import os
import subprocess
import sys

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

print(f'{"setting":<10}{"half":<11}{"CRC ok":>9}{"1-bit expl":>12}'
      f'{"mean adcm":>11}{"1-bits/wd":>11}')
for arg in sys.argv[1:]:
    label, d = arg.split('=', 1)
    root = f'/tmp/r2_{label}.root'
    if not os.path.exists(root):
        subprocess.run(['unpack', '-i', f'{d}/pedestal_run0.raw', '-o', root,
                        '-t', 'roc2root'], capture_output=True)
    t = uproot.open(root)['hgcroc_rawdata/eventdata']
    a = t.arrays(['chip', 'half', 'daqdata'], library='np')
    chip, half, daq = a['chip'], a['half'], a['daqdata']
    for c in (0, 1, 2):
        for h in (0, 1):
            m = np.where((chip == c) & (half == h))[0][:300]
            if not len(m):
                continue
            W = np.array([np.asarray(daq[i], dtype=np.uint32)[:41] for i in m])
            ok = one = 0
            for row in W:
                delta = crc(row[:NW].astype('>u4').tobytes()) ^ int(row[39])
                if delta == 0:
                    ok += 1
                elif delta in inv:
                    one += 1
            ch = W[:, 2:38]
            adcm = ((ch >> 20) & 0x3FF).mean()
            pops = np.mean([bin(int(x)).count('1') for x in ch.ravel()])
            print(f'{label:<10}chip{c}half{h}  {100*ok/len(m):>8.1f}%'
                  f'{100*one/len(m):>11.1f}%{adcm:>11.1f}{pops:>11.2f}')
    print()
