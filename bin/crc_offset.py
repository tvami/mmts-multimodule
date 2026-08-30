#!/usr/bin/env python3
"""Mode A, part 2: is link4's CRC word simply from the WRONG FRAME?

crc_forensics.py showed no window/byte-order variant rescues chip1half0, and
validated the CRC implementation against the two known-good halves.  So the
frame is well-formed and the CRC is computed correctly -- but never matches.

A pipeline/FIFO offset would do exactly that: frame N carries frame N±k's CRC
word.  Test it directly by cross-matching computed CRCs against targets from
neighbouring frames of the same half, and against the same frame of OTHER halves
(which would indicate a mux/routing crossover instead).

Also reports whether the payload itself looks like sane pedestal data, which
separates "payload corrupted" from "only the CRC word is wrong".
"""
import sys
import numpy as np
import uproot

TABLE = []
for b in range(256):
    c = b << 24
    for _ in range(8):
        c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
    TABLE.append(c)


def crc32_msb(buf):
    c = 0
    for byte in buf:
        c = ((c << 8) & 0xFFFFFFFF) ^ TABLE[((c >> 24) ^ byte) & 0xFF]
    return c


def frame_crc(d):
    """The ntupler's calculation: big-endian bytes of words 0..38."""
    return crc32_msb(np.asarray(d[:39], dtype=np.uint32).astype('>u4').tobytes())


t = uproot.open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/roc2.root')['hgcroc_rawdata/eventdata']
a = t.arrays(['event', 'chip', 'half', 'daqdata'], library='np')
ev, chip, half, daq = a['event'], a['chip'], a['half'], a['daqdata']

N = 200
halves = sorted({(int(c), int(h)) for c, h in zip(chip, half)})

# ---- per half: computed CRC and stored target, in event order -----------------
store = {}
for (c, h) in halves:
    m = np.where((chip == c) & (half == h))[0][:N]
    comp = np.array([frame_crc(np.asarray(daq[i], dtype=np.uint32)) for i in m], dtype=np.uint64)
    targ = np.array([int(np.asarray(daq[i], dtype=np.uint32)[39]) for i in m], dtype=np.uint64)
    store[(c, h)] = (comp, targ, m)

print('=== does frame N\'s computed CRC match target of frame N+k (same half)? ===')
print(f'{"half":<11}' + ''.join(f'{k:>7}' for k in range(-3, 4)))
for (c, h), (comp, targ, _) in store.items():
    row = []
    for k in range(-3, 4):
        if k >= 0:
            hit = (comp[:len(comp) - k] == targ[k:]).mean() if len(comp) > k else 0
        else:
            hit = (comp[-k:] == targ[:len(targ) + k]).mean() if len(comp) > -k else 0
        row.append(hit)
    print(f'chip{c}half{h}  ' + ''.join(f'{100*x:>6.0f}%' for x in row))

print('\n=== does frame N\'s computed CRC match ANOTHER half\'s target (same index)? ===')
print(f'{"computed":<11}' + ''.join(f'  tgt c{c}h{h}' for (c, h) in halves))
for (c, h), (comp, _, _) in store.items():
    row = []
    for (c2, h2) in halves:
        targ2 = store[(c2, h2)][1]
        n = min(len(comp), len(targ2))
        row.append((comp[:n] == targ2[:n]).mean())
    print(f'chip{c}half{h}  ' + ''.join(f'{100*x:>8.0f}%' for x in row))

print('\n=== payload sanity: ADC field (word>>10 & 0x3ff) over channel words 2..37 ===')
print(f'{"half":<11}{"adc median":>12}{"adc IQR":>10}{"words==0":>10}{"CRC word varies":>17}')
for (c, h), (comp, targ, m) in store.items():
    adcs, zeros = [], 0
    for i in m[:50]:
        d = np.asarray(daq[i], dtype=np.uint32)
        ch = d[2:38]
        zeros += int((ch == 0).sum())
        adcs.extend(((ch >> 10) & 0x3FF).tolist())
    adcs = np.array(adcs)
    print(f'chip{c}half{h}  {np.median(adcs):>12.1f}'
          f'{np.subtract(*np.percentile(adcs, [75, 25])):>10.1f}'
          f'{zeros/(50*36):>10.2f}'
          f'{len(set(targ.tolist()))/len(targ):>16.2f}')
