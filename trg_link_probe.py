#!/usr/bin/env python3
"""Read the link-capture status registers the delay scan never reports.

WHY THIS EXISTS
---------------
delay_scan.py records only `link_aligned_count` and `link_error_count`, and the
address table says of both: "will NOT increment if the link alignment state
machine is in idle state".  So a link that never locks reads 0/0 whatever the
reason -- which is why an OPEN input (slot A) and a merely INVERTED one
(muxB 20260824_161411 links 1/3/4/6) are indistinguishable in the scan output.

These registers are not subject to that:

  walign_state     0 = idle, 1 = waiting for first alignment word, 2 = counting
  bit_align_errors errors in the DATA words (0xAA / 0x9A for trigger links) --
                   a data-level check that does not require word alignment
  word_errors      word-level errors
  delay_ready      the IDELAY block converged
  delay_out_N      in automatic delay mode, the width of the eye in taps

An input carrying signal should show bit_align_errors accumulating and/or
walign_state != 0.  A truly disconnected input should stay flat at zero.

READ-ONLY: this script issues no writes.  Run it with the module powered and
the ROCs configured (i.e. right after a bring-up + zmq_server for that slot).

Usage:  python3 trg_link_probe.py [TOP_A|TOP_B|TOP_C] [--daq]
"""
import sys

import uhal

CONN = ("file:///opt/cms-hgcal-firmware/hgc-test-systems/active/"
        "uHAL_xml/connections.xml")

PER_LINK = [
    ("aligned",  "status.link_aligned"),
    ("dly_rdy",  "status.delay_ready"),
    ("walign",   "walign_state"),
    ("aliCnt",   "link_aligned_count"),
    ("errCnt",   "link_error_count"),
    ("bitErr",   "bit_align_errors"),
    ("wordErr",  "word_errors"),
    ("dly_out",  "delay_out"),
    ("dly_N",    "delay_out_N"),
    ("fifo",     "fifo_occupancy"),
]


def probe(device, block, nlinks):
    hw = uhal.ConnectionManager(CONN).getDevice(device)
    print("\n===== %s / %s =====" % (device, block))

    glob = {}
    for reg in ("num_links", "bram_size", "modules_included",
                "inter_link_locked"):
        try:
            glob[reg] = hw.getNode("%s.global.%s" % (block, reg)).read()
        except Exception:
            glob[reg] = None
    hw.dispatch()
    print("global: " + "  ".join(
        "%s=%s" % (k, hex(int(v)) if v is not None else "n/a")
        for k, v in glob.items()))

    vals = {}
    for l in nlinks:
        vals[l] = {}
        for label, reg in PER_LINK:
            vals[l][label] = hw.getNode("%s.link%d.%s" % (block, l, reg)).read()
    hw.dispatch()

    print("link  " + "".join("%9s" % lab for lab, _ in PER_LINK))
    for l in nlinks:
        row = "".join("%9d" % int(vals[l][lab]) for lab, _ in PER_LINK)
        print("%-6d%s" % (l, row))


def delay_regs(device, block, nlinks):
    """Read the delay CONTROL registers (rw, but read here only)."""
    hw = uhal.ConnectionManager(CONN).getDevice(device)
    regs = ["delay.in", "delay.mode", "delay.set", "delay.invert",
            "delay.bytes_little_endian", "delay.words_little_endian",
            "align_pattern", "delay_out", "delay_out_N"]
    v = {}
    for l in nlinks:
        v[l] = {r: hw.getNode("%s.link%d.%s" % (block, l, r)).read() for r in regs}
    en = hw.getNode("%s.global.link_enable" % block).read()
    hw.dispatch()
    print("\n--- %s / %s delay control (link_enable=%s) ---" % (device, block, hex(int(en))))
    print("link  " + "".join("%14s" % r.replace("delay.", "") for r in regs))
    for l in nlinks:
        print("%-6d%s" % (l, "".join("%14s" % hex(int(v[l][r])) for r in regs)))


if __name__ == "__main__":
    uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    dev = sys.argv[1] if len(sys.argv) > 1 else "TOP_A"
    probe(dev, "link_capture_trg", list(range(12)))
    if "--delays" in sys.argv:
        delay_regs(dev, "link_capture_trg", list(range(12)))
        delay_regs(dev, "link_capture_daq", [0, 1, 4, 5, 8, 9])
    if "--daq" in sys.argv:
        probe(dev, "link_capture_daq", [0, 1, 4, 5, 8, 9])
