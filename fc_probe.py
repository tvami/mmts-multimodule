#!/usr/bin/env python3
"""Read the fastcontrol block: are L1As actually being sent?

WHY
---
Pedestal runs on this bench produce ~100 % header corruption ("the head and/or
tail of the header packet was not 0x5"), 60192 rejected packets out of 60000,
*with perfect links* -- 18/18, full-width eyes, zero bit errors. Link delay,
fifo_latency, L1A_offset and ROC configuration have all been eliminated, so the
data is malformed before it reaches the link.

The surviving hypothesis: **no L1A reaches the ROCs**, so the readout captures
idle patterns where event headers should be. That explains every symptom --
all packets failing the header check, ADC values meaningless, channels reading
either a constant or noise, and the pattern changing run to run.

`fastcontrol.counters.l1a` counts L1As sent since the last counter reset, so
this settles it. Run before and after a pedestal run and compare:

    counters.l1a jumps by ~NEvents  -> L1As ARE sent; hypothesis dead, look
                                       downstream (ROC not responding to L1A,
                                       or a readout-format mismatch)
    counters.l1a stays 0            -> hypothesis CONFIRMED; no L1As are issued

Also worth watching: `l1a_suppressed` (backpressure eating them) and
`link_reset_rocd` (the fast command that aligns the DAQ links).

READ-ONLY.  Usage: python3 fc_probe.py [TOP_A|TOP_B|TOP_C]
"""
import sys

import uhal

CONN = ("file:///opt/cms-hgcal-firmware/hgc-test-systems/active/"
        "uHAL_xml/connections.xml")

COUNTERS = ["l1a", "l1a_suppressed", "bx_suppressed", "l1a_nzs", "orbit_sync",
            "chipsync", "ecr", "ebr", "link_reset_roct", "link_reset_rocd"]

FLAGS = ["global_l1a_enable", "enable_random_l1a", "enable_external_l1as",
         "random_trigger_log2_period", "minimum_trigger_period"]


def probe(device):
    hw = uhal.ConnectionManager(CONN).getDevice(device)

    c = {}
    for n in COUNTERS:
        try:
            c[n] = hw.getNode("fastcontrol.counters.%s" % n).read()
        except Exception:
            c[n] = None
    f = {}
    for n in FLAGS:
        try:
            f[n] = hw.getNode("fastcontrol.%s" % n).read()
        except Exception:
            f[n] = None
    try:
        sup = hw.getNode("fastcontrol.l1a_suppress").read()
    except Exception:
        sup = None
    hw.dispatch()

    print("=== %s / fastcontrol ===" % device)
    print("counters:")
    for n in COUNTERS:
        v = "n/a" if c[n] is None else int(c[n])
        print("  %-22s %s" % (n, v))
    print("flags:")
    for n in FLAGS:
        v = "n/a" if f[n] is None else int(f[n])
        print("  %-22s %s" % (n, v))
    print("  %-22s %s" % ("l1a_suppress (live)",
                          "n/a" if sup is None else int(sup)))


if __name__ == "__main__":
    uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    probe(sys.argv[1] if len(sys.argv) > 1 else "TOP_A")
