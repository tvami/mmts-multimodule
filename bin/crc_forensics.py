#!/usr/bin/env python3
"""Mode A forensics: why does link4 (chip1half0) never match its CRC?

chip1half0 delivers 100 % correct headers, 94 % intact tails and valid
bxcounter, yet fails CRC32 on every one of 391 248 events.  That is not a
bit-error signature -- it is a systematic payload/CRC mismatch.  So: recompute
the CRC over a family of plausible windows/orderings and find which one DOES
match.  Whatever variant matches names the bug.

Reference implementation (`ntupler.cc`):
    crcvec = [byteswap32(w) for w in data]        # all 41 words
    crc32  = boost::crc<32, 0x4c11db7, 0, 0, false, false>(bytes, 39*4)
    target = data[39]                             # NOT byteswapped
i.e. MSB-first CRC-32, poly 0x04C11DB7, init 0, no reflection, no final xor,
over words 0..38 after a per-word byte swap.

Input: the roc2root ntuple, which carries the raw 41-word frame per half:
    unpack -i pedestal_run0.raw -o roc2.root -t roc2root     (no -M !)
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


def crc32_msb(buf, init=0):
    """boost::crc<32, 0x4c11db7, init, 0, false, false>."""
    c = init
    for byte in buf:
        c = ((c << 8) & 0xFFFFFFFF) ^ TABLE[((c >> 24) ^ byte) & 0xFF]
    return c


def words_to_bytes(words, swap):
    a = np.asarray(words, dtype='>u4' if not swap else '<u4')
    return np.frombuffer(np.asarray(words, dtype=np.uint32).astype('<u4' if swap else '>u4').tobytes(), dtype=np.uint8)


path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/roc2.root'
t = uproot.open(path)['hgcroc_rawdata/eventdata']
a = t.arrays(['chip', 'half', 'daqdata'], library='np')
chip, half, daq = a['chip'], a['half'], a['daqdata']

# Variants: (label, first word, last word inclusive, byteswap?, target index, swap target?)
VARIANTS = [
    ('ntupler reference  w0-38 swap, tgt[39]', 0, 38, True,  39, False),
    ('no byteswap        w0-38     , tgt[39]', 0, 38, False, 39, False),
    ('swap, target swapped                  ', 0, 38, True,  39, True),
    ('skip header        w1-38 swap, tgt[39]', 1, 38, True,  39, False),
    ('include crc word   w0-39 swap, tgt[40]', 0, 39, True,  40, False),
    ('shift by one       w1-39 swap, tgt[40]', 1, 39, True,  40, False),
    ('40 words           w0-39 swap, tgt[39]', 0, 39, True,  39, False),
    ('38 words           w0-37 swap, tgt[39]', 0, 37, True,  39, False),
]

print(f'{"chip/half":<11}{"rows":>8}   ' + '  '.join(f'{i}' for i in range(len(VARIANTS))))
print('variants:')
for i, v in enumerate(VARIANTS):
    print(f'  {i}: {v[0]}')
print()

NSAMP = 300     # enough to separate 0 % from 100 %; these rates are not marginal
for c in sorted(set(chip.tolist())):
    for h in sorted(set(half.tolist())):
        m = np.where((chip == c) & (half == h))[0]
        if not len(m):
            continue
        idx = m[:NSAMP]
        hits = [0] * len(VARIANTS)
        for i in idx:
            d = np.asarray(daq[i], dtype=np.uint32)
            if len(d) < 41:
                continue
            for vi, (_, lo, hi, swap, ti, tswap) in enumerate(VARIANTS):
                buf = words_to_bytes(d[lo:hi + 1], swap)
                tgt = int(d[ti])
                if tswap:
                    tgt = int(np.asarray([tgt], dtype='<u4').astype('>u4')[0])
                if crc32_msb(buf) == tgt:
                    hits[vi] += 1
        n = len(idx)
        print(f'chip{c}half{h}  {n:>8}   ' +
              '  '.join(f'{100*x/n:>4.0f}%' for x in hits))
