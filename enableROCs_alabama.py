#!/usr/bin/env python3
"""
enableROCs for the **Alabama** MMTS bench (kria4).

Differences from the FNAL bench (`enableROCs.py`, kria10):

1. This bench HAS a **power management board** (TCA9535 @ 0x27, on the "Spare"
   sub-bus 0x10 of any PCA9848 switch). Module power comes from it: nothing on
   the hexaboard powers up until its EN_Mx bit is driven high. On kria10 there
   is no such board and this step wedges the bus, which is why the shared code
   has it disabled.
2. The second mux-board GPIO expander (TCAL6416 @ **0x21**, the S*_I2C_RST
   lines) does **not** answer here. Writing to it wedges the write-mostly PL
   master (every later access EIOs until a `kconn_pwr off/on` + `fw-loader
   load`), so this script never touches 0x21.
3. The port-0 bit mapping used for the RSTB lines follows Link.py's documented
   MUX_GPIO map (dir 0xF1 / out 0x0E = P01..P03), not the 0xF8/0x07 pattern in
   `enableROCs.py`.

Usage:
    python3 enableROCs_alabama.py            # slot B (middle), EN_M2
    python3 enableROCs_alabama.py A          # slot A
    python3 enableROCs_alabama.py B --module 3   # slot B, but EN_M3 on the pwr board
    python3 enableROCs_alabama.py B --scan   # also report which slot the ROCs answer on
"""
import argparse
import os
import sys
import time

from smbus2 import SMBus

MASTER_BUS = 2

# Firmware dir under /opt/cms-hgcal-firmware/hgc-test-systems that every
# fw-loader reset re-points `active` at; MMTS_FW selects a variant build.
FW = os.environ.get("MMTS_FW", "multimodule-hd-tester-trophy-v3")

# PCA9848 1-to-8 I2C bus switch, one per multiplexer-board slot
SWITCH = {"A": 0x71, "B": 0x73, "C": 0x77}

# PCA9848 sub-buses (see Link.py topology comment)
SUB_ROC = 0x02    # "S1_I2C" -- the LD hexaboard's three HGCROCs
SUB_SPARE = 0x10  # "Spare"  -- power management board
SUB_GPIO = 0x20   # "Sgl"    -- TCAL6416 GPIO controllers (0x20, 0x21)
SUB_NONE = 0x00

# --- Power management board (TCA9535) --------------------------------------
# Address is set by the ADDR0/1/2 jumpers; no jumpers = 0x27 on this bench.
PWR_BOARD = 0x27
PWR_BOARD_DIR_P0 = 0x06   # port 0 direction register
PWR_BOARD_OUT_P0 = 0x02   # port 0 output register
PWR_BOARD_DIR_VAL = 0xF8  # P00 EN_M1, P01 EN_M2, P02 EN_M3 as outputs
EN_M = {"A": 0x01, "B": 0x02, "C": 0x04}   # P00 / P01 / P02

# --- Multiplexer board GPIO expander (TCAL6416 @ 0x20) ---------------------
MUX_GPIO = 0x20
DIR_P0, OUT_P0 = 0x06, 0x02
DIR_P1, OUT_P1 = 0x07, 0x03
DIR_P1_VAL, OUT_P1_VAL = 0xE3, 0x1C   # P12/P13/P14 = S1/S2/S3_PWR_EN -> outputs, high
DIR_P0_VAL, OUT_P0_VAL = 0xF1, 0x0E   # P01/P02/P03 = S1/S2/S3_RSTB   -> outputs, high
IN_P1 = 0x01                          # P15/P16/P17 = S1/S2/S3_PWR_PG (inputs)

# All HGCROCs sit on sub-bus S1_I2C; which bases are populated depends on the
# board type. Sets must match zmq_i2c/Link.py i2c_maps, which requires an exact
# set match -- enabling the wrong subset makes zmq_server reject the board.
ROC_ADDR_SETS = {
    "LD-Full":     (0x08, 0x18, 0x28),
    "LD-Five":     (0x48, 0x58, 0x68),
    "LD-Semi":     (0x48, 0x58),          # "V3 LD Semi or Half HB"
    "HD-Semi":     (0x08, 0x18),
    "HD-Bottom":   (0x18, 0x58, 0x28, 0x68),
    "HD-Top":      (0x18, 0x58, 0x28),
    "HD-Full":     (0x08, 0x18, 0x28, 0x48, 0x58, 0x68),  # six chips
    # Probe every V3 base and enable whatever answers -- for an unknown or new
    # board type. Costs a few NACKed reads, which are clean (see probe_rocs).
    "any":         (0x08, 0x18, 0x28, 0x48, 0x58, 0x68),
}
ROC_ADDRS = ROC_ADDR_SETS["LD-Full"]


def _seq(switch, sub_bus, writes, attempts=5):
    """Run `writes` = [(addr, reg, val), ...] behind `sub_bus` of `switch`.

    Accesses to the mux board expanders intermittently EIO at a wandering point
    -- the mark of a transient on this write-mostly PL master, not a dead
    device. Retry the whole open->write->close sequence on a fresh SMBus fd so a
    half-finished sequence always restarts clean (same trick as Link.mux_gpio).
    """
    last = None
    for attempt in range(attempts):
        try:
            with SMBus(MASTER_BUS) as bus:
                bus.write_byte(switch, sub_bus)
                for addr, reg, val in writes:
                    bus.write_byte_data(addr, reg, val)
                bus.write_byte(switch, SUB_NONE)
            return
        except OSError as e:
            last = e
            print(f"      transient I2C error ({e}), retry {attempt + 1}/{attempts}")
            time.sleep(0.2 * (attempt + 1))
    raise last


def _switch(bus, switch, sub_bus, attempts=5):
    """Select `sub_bus` on `switch`, retrying a transient bus error.

    Same rationale as _seq(), but for a switch write on an already-open fd, which
    is what probe_rocs()/enable_rocs() need in order to keep one selection
    standing across a whole ROC loop. A bare write here EIOs often enough on a
    bench whose rails are still settling that it was aborting bring-up outright.
    """
    last = None
    for attempt in range(attempts):
        try:
            bus.write_byte(switch, sub_bus)
            return
        except OSError as e:
            last = e
            print(f"      transient I2C error ({e}) selecting sub-bus "
                  f"0x{sub_bus:02x} on 0x{switch:02x}, retry {attempt + 1}/{attempts}")
            time.sleep(0.2 * (attempt + 1))
    raise last


def power_management_board(slot, via=0x77):
    """Drive EN_Mx on the power management board so the module gets power."""
    print(f"[pwr] power management board 0x{PWR_BOARD:02x} (via switch "
          f"0x{via:02x}, Spare sub-bus): EN_M{'ABC'.index(slot) + 1} high")
    _seq(via, SUB_SPARE, [
        (PWR_BOARD, PWR_BOARD_DIR_P0, PWR_BOARD_DIR_VAL),
        (PWR_BOARD, PWR_BOARD_OUT_P0, EN_M[slot]),
    ])


def reset_master():
    """Reset the PL I2C master with a firmware reload.

    Enabling module power glitches the master into a wedged state (every later
    access EIOs). Reloading the bitstream clears it; because payload power stays
    ON, the power management board keeps its EN_Mx latch, so the module stays
    powered across the reset. A `kconn_pwr off/on` would clear that latch and
    undo step 1.
    """
    import subprocess
    print(f"[rst] fw-loader load {FW} (resets the PL I2C master, keeps payload power)")
    subprocess.run(["sudo", "fw-loader", "load", FW],
                   check=True, stdout=subprocess.DEVNULL)
    wait_i2c_master()


def wait_i2c_master(timeout=20.0):
    """Wait for /dev/i2c-2 to come back writable after a bitstream reload.

    The overlay re-creates the node and udev then fixes its group; after many
    reloads in a session that takes longer than a fixed 3 s sleep, and the next
    access fails with ENOENT or EACCES (seen 2026-08-29, 8 bring-ups in a row).
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.access(f"/dev/i2c-{MASTER_BUS}", os.R_OK | os.W_OK):
            time.sleep(1)      # let the master settle after the node appears
            return
        time.sleep(0.5)
    print(f"      WARNING: /dev/i2c-{MASTER_BUS} not usable {timeout:.0f} s after "
          "the reload; a Kria reboot usually clears this")


def mux_board_gpio(slot, readback=False):
    """Enable the mux board's per-slot power switches and release the ROC resets.

    Only expander 0x20 is touched -- 0x21 (I2C_RST) is absent on this bench and
    writing to it wedges the master. The power-good readback is opt-in for the
    same reason: a read that does not answer wedges the master too.
    """
    sw = SWITCH[slot]
    print(f"[mux] switch 0x{sw:02x}: S*_PWR_EN high")
    _seq(sw, SUB_GPIO, [(MUX_GPIO, DIR_P1, DIR_P1_VAL),
                        (MUX_GPIO, OUT_P1, OUT_P1_VAL)])
    time.sleep(0.5)                     # let the rails come up before RSTB
    print(f"[mux] switch 0x{sw:02x}: S*_RSTB released")
    _seq(sw, SUB_GPIO, [(MUX_GPIO, DIR_P0, DIR_P0_VAL),
                        (MUX_GPIO, OUT_P0, OUT_P0_VAL)])
    if readback:
        try:
            with SMBus(MASTER_BUS) as bus:
                bus.write_byte(sw, SUB_GPIO)
                pg = bus.read_byte_data(MUX_GPIO, IN_P1)
                bus.write_byte(sw, SUB_NONE)
            print(f"[mux] power good S1,S2,S3 = "
                  f"{(pg >> 5) & 1},{(pg >> 6) & 1},{(pg >> 7) & 1}")
        except OSError as e:
            print(f"[mux] power-good readback failed ({e}) -- master likely "
                  f"wedged, re-run with --recover")


def probe_rocs(bus, slot):
    """Return the ROC addresses that ACK on this slot's ROC sub-bus.

    Probe with a single read: a NACK'd read is clean, whereas pushing the config
    write sequence at an absent ROC can wedge the shared master.
    """
    sw = SWITCH[slot]
    found = []
    try:
        _switch(bus, sw, SUB_ROC)
    except OSError as e:
        print(f"[roc] switch 0x{sw:02x} did not ACK ({e}) -- bus wedged?")
        return found
    for addr in ROC_ADDRS:
        try:
            bus.read_byte(addr)
            found.append(addr)
        except OSError:
            pass
    try:
        bus.write_byte(sw, SUB_NONE)
    except OSError:
        pass
    return found


def enable_rocs(bus, slot, addrs):
    """Enable each ROC and set CLPS drive strength + pre-emphasis (0xFF)."""
    sw = SWITCH[slot]
    ok, bad = [], []
    _switch(bus, sw, SUB_ROC)
    for addr in addrs:
        try:
            print(f"[roc] enabling 0x{addr:02x}")
            bus.write_byte(addr + 0x00, 0xa0)
            bus.write_byte(addr + 0x01, 0x05)
            bus.write_byte(addr + 0x02, 0x33)
            # CLPS driver register = Top reg 5 (internal 0x05A5):
            # bits<2:0> EN drive strength, <5:3> ENpE pre-emphasis amplitude,
            # <7:6> S pre-emphasis delay. 0xFF = EN 7, ENpE 7, S 3 (max), the
            # setting the A/B/C pre-emphasis sweep picked as DAQ-safe.
            bus.write_byte(addr + 0x00, 0xa5)
            bus.write_byte(addr + 0x01, 0x05)
            bus.write_byte(addr + 0x02, 0xff)
            # Read back register 0x0000 (R0/R1 = address low/high, then read R2)
            bus.write_byte(addr + 0x00, 0x00)
            bus.write_byte(addr + 0x01, 0x00)
            print(f"[roc] 0x{addr:02x} reg readback: "
                  f"{hex(bus.read_byte(addr + 0x02))}")
            ok.append(addr)
        except OSError as e:
            print(f"[roc] 0x{addr:02x} stopped responding mid-config ({e})")
            bad.append(addr)
    try:
        _switch(bus, sw, SUB_NONE)
    except OSError as e:
        # Every ROC is already enabled by this point; failing to park the switch
        # is not worth throwing a good bring-up away over. The next access
        # re-selects whatever sub-bus it needs anyway.
        print(f"[roc] could not disconnect sub-bus ({e}) -- continuing")
    return ok, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slot", nargs="?", default="B", choices=["A", "B", "C"],
                    help="multiplexer board slot (default: B, the middle one)")
    ap.add_argument("--board", choices=sorted(ROC_ADDR_SETS), default="LD-Full",
                    help="which ROC address set to probe and enable (default: "
                         "LD-Full = 0x08/0x18/0x28). Partials live at different "
                         "bases; 'any' probes every V3 base when the board type "
                         "is not yet known")
    ap.add_argument("--module", type=int, choices=[1, 2, 3], default=None,
                    help="power management board EN_Mx bit to drive "
                         "(default: same index as the slot)")
    ap.add_argument("--external-power", "--no-power", action="store_true",
                    dest="no_power",
                    help="the power management board is NOT in the loop -- the "
                         "module is powered from elsewhere (e.g. the bench "
                         "supply wired straight to the slot). Skips the 0x27 "
                         "EN_Mx step and the fw-loader reset that clears the "
                         "wedge it causes. It does NOT mean 'leave the module "
                         "unpowered'. (--no-power is the old, misleading name)")
    ap.add_argument("--scan", action="store_true",
                    help="after powering, probe all three slots for ROCs "
                         "(each miss wedges the master; use only when hunting "
                         "for the populated slot)")
    ap.add_argument("--readback", action="store_true",
                    help="read the mux board power-good bits (can wedge the "
                         "master -- diagnostics only)")
    ap.add_argument("--no-reset", action="store_true",
                    help="skip the fw-loader master reset after powering")
    ap.add_argument("--recover", action="store_true",
                    help="full power-cycle + firmware reload first, for a "
                         "wedged master (also clears the EN_Mx latch, so the "
                         "power management board step runs again afterwards)")
    args = ap.parse_args()

    slot = args.slot
    pwr_slot = slot if args.module is None else "ABC"[args.module - 1]

    global ROC_ADDRS
    ROC_ADDRS = ROC_ADDR_SETS[args.board]
    print(f"[cfg] board {args.board}: probing "
          f"{[hex(a) for a in ROC_ADDRS]}")

    if args.recover:
        import subprocess
        print("[rec] kconn_pwr off / fw-loader load / kconn_pwr on")
        subprocess.run(["sudo", "kconn_pwr", "off"], check=True)
        time.sleep(3)
        subprocess.run(["sudo", "fw-loader", "load", FW],
                       check=True, stdout=subprocess.DEVNULL)
        wait_i2c_master()
        subprocess.run(["sudo", "kconn_pwr", "on"], check=True)
        time.sleep(5)

    if not args.no_power:
        power_management_board(pwr_slot)
        time.sleep(2)
        # Powering the module wedges the master -- clear it before going on.
        if not args.no_reset:
            reset_master()
    mux_board_gpio(slot, readback=args.readback)
    time.sleep(1)

    with SMBus(MASTER_BUS) as bus:
        slots = ["A", "B", "C"] if args.scan else [slot]
        results = {}
        for s in slots:
            found = probe_rocs(bus, s)
            results[s] = found
            print(f"[roc] slot {s} (0x{SWITCH[s]:02x}): "
                  f"{[hex(a) for a in found] if found else 'no ROCs'}")

        addrs = results.get(slot) or []
        if not addrs:
            other = [s for s, f in results.items() if f]
            if other:
                print(f"\nROCs answer on slot(s) {other}, not on {slot} -- "
                      f"re-run with that slot.")
            else:
                if args.no_power:
                    print("\nNo ROCs anywhere, and the power management board "
                          "is out of the loop (--external-power), so nothing "
                          "here switches the module on. Check the bench supply "
                          "is ON and actually DRAWING current -- 0.0 A at the "
                          "setpoint means an open circuit, not a bench "
                          "problem. Then check module seating.")
                else:
                    print("\nNo ROCs anywhere. Check module seating and that "
                          "the power management board EN_Mx bit matches the "
                          "populated slot (try --module 1/2/3), and that the "
                          "bench supply is on.")
            return 1

        ok, bad = enable_rocs(bus, slot, addrs)
        print(f"\n--- slot {slot} (switch 0x{SWITCH[slot]:02x}): {len(ok)} ROC(s) "
              f"enabled {[hex(a) for a in ok]}"
              + (f", {len(bad)} FAILED {[hex(a) for a in bad]}" if bad else ""))
        return 0 if ok and not bad else 1


if __name__ == "__main__":
    sys.exit(main())
