#!/usr/bin/env python3
"""Read/set bytes_little_endian and words_little_endian on the link-capture blocks.

WHY
---
Pedestal runs on this bench reject essentially every half-ROC packet -- "the head
and/or tail of the header packet was not 0x5", **60192 failures out of 60000
packets, identical across two runs whose L1A rates differed by 50x**. That
determinism rules out overrun/timing and points at a format mismatch.

Every link here reads `words_little_endian = 1`, and the firmware's own address
table says of that bit:

    "reverse 32-bit words; 0: for use with most things;
     1: for use with ECON-T-P1 only; default is 0"

Reversing 32-bit words puts the header nibbles in the wrong place in every
packet, which is exactly a systematic, rate-independent, 100 %-of-packets header
failure -- while leaving link ALIGNMENT untouched, since that matches the idle
pattern before this reordering matters.

ORDERING: daq-server reprograms the link-capture blocks on every configure, so
set this AFTER the run's configure and BEFORE the acquisition --
`pedestal_run_fixdelay.py` provides exactly that pause. Verify with
`trg_link_probe.py <dev> --delays`.

Usage:
    python3 set_link_endian.py TOP_A --show
    python3 set_link_endian.py TOP_A --words 0            # the suspected fix
    python3 set_link_endian.py TOP_A --words 0 --bytes 1  # both to documented defaults
    python3 set_link_endian.py TOP_A --words 0 --trg      # trigger links too
"""
import sys

import uhal

CONN = ("file:///opt/cms-hgcal-firmware/hgc-test-systems/active/"
        "uHAL_xml/connections.xml")
DAQ_LINKS = [0, 1, 4, 5, 8, 9]
TRG_LINKS = list(range(12))


def run(device, blocks, words, bytes_):
    hw = uhal.ConnectionManager(CONN).getDevice(device)

    for block, links in blocks:
        for l in links:
            if words is not None:
                hw.getNode("%s.link%d.delay.words_little_endian"
                           % (block, l)).write(words)
            if bytes_ is not None:
                hw.getNode("%s.link%d.delay.bytes_little_endian"
                           % (block, l)).write(bytes_)
    if words is not None or bytes_ is not None:
        hw.dispatch()

    for block, links in blocks:
        w = {l: hw.getNode("%s.link%d.delay.words_little_endian" % (block, l)).read()
             for l in links}
        b = {l: hw.getNode("%s.link%d.delay.bytes_little_endian" % (block, l)).read()
             for l in links}
        hw.dispatch()
        print("%s / %s" % (device, block))
        print("  %-6s %-22s %s" % ("link", "words_little_endian", "bytes_little_endian"))
        for l in links:
            print("  %-6d %-22d %d" % (l, int(w[l]), int(b[l])))


if __name__ == "__main__":
    uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    args = sys.argv[1:]
    dev = args[0] if args and not args[0].startswith("--") else "TOP_A"

    def opt(name):
        return int(args[args.index(name) + 1]) if name in args else None

    blocks = [("link_capture_daq", DAQ_LINKS)]
    if "--trg" in args:
        blocks.append(("link_capture_trg", TRG_LINKS))

    run(dev, blocks, opt("--words"), opt("--bytes"))
