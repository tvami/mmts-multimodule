#!/usr/bin/env python3
"""Manual trigger-link delay sweep straight through uHAL.

Bypasses daq-server's delayScan menu entirely.  Written because on slot A the
daq-server sweep leaves link_capture_trg delay_out at 0 (while the DAQ links of
the same sweep end at 511, and slot B's trigger links end at 511) -- i.e. the
trigger IDELAY programming does not appear to take effect for that block, which
would make all 512 "steps" sample the same physical delay and produce the flat
ngood=0 that has been read as a dead link.

Per delay setting, for every enabled link:
    delay.in = d ; delay.set = 1     program the IDELAY
    reset_counters = 1               clear aligned/error counters
    explicit_align = 1               force the word aligner to try
    (settle)
    read link_aligned_count / link_error_count / status.link_aligned

"good" uses the delay-scan analyser's own criterion: aligned==128 and err<=1.

WRITES: only to the link-capture block (FPGA registers).  No I2C, so no risk to
the bus.  Re-running the server's configure restores normal state.

Usage: python3 manual_trg_scan.py [TOP_A|TOP_B|TOP_C] [step] [--daq]
"""
import sys
import time

import uhal

CONN = ("file:///opt/cms-hgcal-firmware/hgc-test-systems/active/"
        "uHAL_xml/connections.xml")
SETTLE = 0.02


def sweep(device, block, links, step):
    hw = uhal.ConnectionManager(CONN).getDevice(device)

    # confirm the delay programming actually lands before sweeping
    probe_d = 137
    for l in links:
        hw.getNode("%s.link%d.delay.in" % (block, l)).write(probe_d)
        hw.getNode("%s.link%d.delay.set" % (block, l)).write(1)
    hw.dispatch()
    time.sleep(SETTLE)
    rb = {l: hw.getNode("%s.link%d.delay_out" % (block, l)).read()
          for l in links}
    hw.dispatch()
    bad = [l for l in links if int(rb[l]) != probe_d]
    print("delay programming check: wrote %d -> read back %s" %
          (probe_d, {l: int(rb[l]) for l in links}))
    if bad:
        print("  !! delay_out did NOT follow the write on links %s" % bad)
        print("  !! the IDELAY programming path is broken for this block --")
        print("  !! every delay step would sample the same physical delay.")
    else:
        print("  delay programming works on every link.")

    good = {l: 0 for l in links}
    best = {l: (0, -1) for l in links}   # (aligned, delay)
    seen = {l: 0 for l in links}

    for d in range(0, 512, step):
        for l in links:
            hw.getNode("%s.link%d.delay.in" % (block, l)).write(d)
            hw.getNode("%s.link%d.delay.set" % (block, l)).write(1)
        hw.dispatch()
        for l in links:
            hw.getNode("%s.link%d.reset_counters" % (block, l)).write(1)
        hw.dispatch()
        for l in links:
            hw.getNode("%s.link%d.explicit_align" % (block, l)).write(1)
        hw.dispatch()
        time.sleep(SETTLE)

        a = {l: hw.getNode("%s.link%d.link_aligned_count" % (block, l)).read()
             for l in links}
        e = {l: hw.getNode("%s.link%d.link_error_count" % (block, l)).read()
             for l in links}
        hw.dispatch()

        for l in links:
            ac, ec = int(a[l]), int(e[l])
            if ac > 0:
                seen[l] += 1
            if ac == 128 and ec <= 1:
                good[l] += 1
            if ac > best[l][0]:
                best[l] = (ac, d)

    n = len(range(0, 512, step))
    print("\n%s / %s -- %d delay points (step %d)" % (device, block, n, step))
    print("%-6s%10s%10s%18s" % ("link", "good", "any_align", "best(aliCnt@dly)"))
    for l in links:
        print("%-6d%10d%10d%18s" % (l, good[l], seen[l],
                                    "%d@%d" % best[l]))
    print("\naligned links: %d/%d" % (sum(1 for l in links if good[l] > 0),
                                      len(links)))


if __name__ == "__main__":
    uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    dev = sys.argv[1] if len(sys.argv) > 1 else "TOP_A"
    step = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8
    if "--daq" in sys.argv:
        sweep(dev, "link_capture_daq", [0, 1, 4, 5, 8, 9], step)
    else:
        sweep(dev, "link_capture_trg", list(range(12)), step)
