#!/usr/bin/env python3
"""Program the DAQ link IDELAYs manually, to the eye centres from a delay scan.

WHY
---
daq-server leaves the DAQ links in automatic delay mode (delay.mode = 1) and the
aligner settles on very narrow eyes -- measured on slot B, 2026-08-25:

    link      0     1     4     5     8     9
    chosen    4     3   415   168    28     5
    eye(N)    8     8     8    40     8     8      <- delay_out_N, taps

while the delay scan of the same links measures eyes of 44-89 taps at completely
different positions (centres 153, 307, 173, 212, 49, 250).  Links 0/1/4/9 are
locked onto spurious narrow eyes far from the real one.  Sampling that close to
an edge produces occasional corrupted events, which is what inflates adc_stdd on
chips 0 and 2 in pedestal runs (robust width is ~3 ADC, adc_stdd 9.7 and 27.7).

This switches the links to manual mode and programs given delays.

ORDERING: daq-server re-runs its own alignment on every configure, so run this
AFTER the run's configure step and BEFORE the acquisition, or the writes are
overwritten.  Verify with trg_link_probe.py --delays: delay.mode must read 0 and
delay_out must match what was asked for.

Usage:
    python3 set_daq_delays.py TOP_B 0:153 1:307 4:173 5:212 8:49 9:250
    python3 set_daq_delays.py TOP_B --auto          # hand the links back to
                                                    # automatic mode
"""
import sys
import time

import uhal

CONN = ("file:///opt/cms-hgcal-firmware/hgc-test-systems/active/"
        "uHAL_xml/connections.xml")
BLOCK = "link_capture_daq"


def set_manual(device, delays):
    hw = uhal.ConnectionManager(CONN).getDevice(device)
    for l, d in delays.items():
        hw.getNode("%s.link%d.delay.mode" % (BLOCK, l)).write(0)
        hw.getNode("%s.link%d.delay.in" % (BLOCK, l)).write(d)
        hw.getNode("%s.link%d.delay.set" % (BLOCK, l)).write(1)
    hw.dispatch()

    # Changing the delay drops the current lock, and nothing re-issues a
    # linkReset between here and the acquisition, so force the word aligner to
    # re-lock at the new delay.  explicit_align is sufficient on DAQ links
    # (verified: a manual sweep using it aligns 6/6; it is NOT sufficient on
    # trigger links, which align on the linkReset_ROCt fast command).
    for l in delays:
        hw.getNode("%s.link%d.reset_counters" % (BLOCK, l)).write(1)
    hw.dispatch()
    for l in delays:
        hw.getNode("%s.link%d.explicit_align" % (BLOCK, l)).write(1)
    hw.dispatch()
    time.sleep(0.05)

    out = {l: hw.getNode("%s.link%d.delay_out" % (BLOCK, l)).read()
           for l in delays}
    mode = {l: hw.getNode("%s.link%d.delay.mode" % (BLOCK, l)).read()
            for l in delays}
    ali = {l: hw.getNode("%s.link%d.status.link_aligned" % (BLOCK, l)).read()
           for l in delays}
    hw.dispatch()

    print("%-6s %-10s %-10s %-8s %s" % ("link", "asked", "delay_out", "mode",
                                        "aligned"))
    ok = True
    for l in sorted(delays):
        got = int(out[l])
        if got != delays[l]:
            ok = False
        print("%-6d %-10d %-10d %-8d %d%s" % (l, delays[l], got, int(mode[l]),
                                              int(ali[l]),
                                              "" if got == delays[l] else "  <-- MISMATCH"))
    return ok


def realign(device, links):
    """Force a re-align without touching mode or delays.

    Use when daq-server refuses to START with 'elink link_capture_daq.linkN is
    not aligned' -- a link that failed to initialise.  Cheaper than a bring-up,
    and this bench drops a link this way roughly once a session.
    """
    hw = uhal.ConnectionManager(CONN).getDevice(device)
    for l in links:
        hw.getNode("%s.link%d.reset_counters" % (BLOCK, l)).write(1)
    hw.dispatch()
    for l in links:
        hw.getNode("%s.link%d.explicit_align" % (BLOCK, l)).write(1)
    hw.dispatch()
    time.sleep(0.1)
    ali = {l: hw.getNode("%s.link%d.status.link_aligned" % (BLOCK, l)).read()
           for l in links}
    out = {l: hw.getNode("%s.link%d.delay_out" % (BLOCK, l)).read()
           for l in links}
    wid = {l: hw.getNode("%s.link%d.delay_out_N" % (BLOCK, l)).read()
           for l in links}
    hw.dispatch()
    print("%-6s %-10s %-10s %s" % ("link", "aligned", "delay", "eye"))
    bad = []
    for l in sorted(links):
        if not int(ali[l]):
            bad.append(l)
        print("%-6d %-10d %-10d %d" % (l, int(ali[l]), int(out[l]), int(wid[l])))
    if bad:
        print("\nstill unaligned: %s -- re-run bring-up for this slot" % bad)
    else:
        print("\nall links aligned")
    return not bad


def set_auto(device, links):
    hw = uhal.ConnectionManager(CONN).getDevice(device)
    for l in links:
        hw.getNode("%s.link%d.delay.mode" % (BLOCK, l)).write(1)
    hw.dispatch()
    print("links %s handed back to automatic delay mode" % sorted(links))


if __name__ == "__main__":
    uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    dev = sys.argv[1] if len(sys.argv) > 1 else "TOP_B"
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    if "--realign" in sys.argv:
        sys.exit(0 if realign(dev, [0, 1, 4, 5, 8, 9]) else 1)
    elif "--auto" in sys.argv:
        set_auto(dev, [0, 1, 4, 5, 8, 9])
    else:
        delays = {int(a.split(":")[0]): int(a.split(":")[1]) for a in args}
        if not delays:
            delays = {0: 153, 1: 307, 4: 173, 5: 212, 8: 49, 9: 250}
        sys.exit(0 if set_manual(dev, delays) else 1)
