import sys
from smbus2 import SMBus, i2c_msg

def enable_module(bus, muxAddr, ROCAddrs):
    """
    Power up and enable the ROCs of ONE module, reached through its PCA9848
    switch `muxAddr` (A=0x71, B=0x73, C=0x77). Writes the module's own TCAL6416
    GPIO expanders (0x20/0x21, on sub-bus 5) to enable the DCDC and release the
    ROC + I2C resets, then does the per-ROC enable on the ROC sub-bus.
    """
    print(f"=== Enabling module at switch {hex(muxAddr)} ===")

    # --- Enable DCDC + release resets via the module's TCAL6416 expanders ---
    # Wrapped so a module whose expander doesn't answer (absent board, or a
    # momentarily wedged bus) is reported and skipped instead of crashing the run.
    try:
        # connect sub-bus 5 (TCAL6416 GPIO expanders)
        bus.write_byte(muxAddr, 0x20)
        # 0x20: dir bits, dir bits, enable DCDC ctrl, rstb high
        for reg, val in [(0x06, 0xf8), (0x07, 0xe3), (0x03, 0x1c), (0x02, 0x07)]:
            bus.i2c_rdwr(i2c_msg.write(0x20, [reg, val]))
        # 0x21: i2c-reset dir, i2c-reset bits high
        for reg, val in [(0x06, 0x8f), (0x02, 0x70)]:
            bus.i2c_rdwr(i2c_msg.write(0x21, [reg, val]))
    except OSError as e:
        print(f"  [WARN] GPIO expander on switch 0x{muxAddr:02x} did not respond "
              f"({e}); skipping this module")
        try:
            bus.write_byte(muxAddr, 0x00)
        except OSError:
            pass
        return [], []

    ok, bad = [], []
    for muxport, rocaddrs in ROCAddrs.items():
        print("Setting mux port:", hex(muxport))
        bus.write_byte(muxAddr, muxport)
        for rocaddr in rocaddrs:
            # PROBE FIRST, then configure. A single NACK'd read is clean, but
            # pushing the whole write sequence at an absent / unpowered ROC (e.g.
            # a module that isn't seated) can WEDGE the shared master bus and take
            # down the healthy module too. So skip any ROC that doesn't ACK a probe.
            try:
                bus.read_byte(rocaddr)
            except OSError:
                print(f"  [skip] no ROC at 0x{rocaddr:02x} on switch 0x{muxAddr:02x} "
                      f"(not present / unpowered)")
                bad.append(rocaddr)
                continue
            try:
                print("Enabling ROC at addr:", hex(rocaddr))
                bus.write_byte(rocaddr + 0x00, 0xa0)
                bus.write_byte(rocaddr + 0x01, 0x05)
                bus.write_byte(rocaddr + 0x02, 0x33)
                # CLPS driver register = Top reg 5 (internal 0x05A5). Byte decodes
                # (HGCROC3b WD p.56-57): bits<2:0> EN drive strength, <5:3> ENpE
                # pre-emphasis amplitude, <7:6> S pre-emphasis delay.
                #   was 0x07 = EN 7 (max), ENpE 0 (off), S 0 -> pre-emphasis OFF.
                #   now 0xFF = EN 7,      ENpE 7,        S 3 -> pre-emphasis MAX.
                # From the 32-point ENpExS sweep on modules A/B/C (Results/
                # mmts_preemph_*, talk backup): 0xFF is DAQ-safe on all three and
                # rescues each module's one marginal trigger link (A:7, B:2, C:0).
                # NB avoid ENpE=7,S=0 (0x3F) -- on C it drops DAQ links 4/5/8/9.
                print("Setting CLPS drive strength + pre-emphasis at addr:", hex(rocaddr))
                bus.write_byte(rocaddr + 0x00, 0xa5)
                bus.write_byte(rocaddr + 0x01, 0x05)
                bus.write_byte(rocaddr + 0x02, 0xff)
                bus.write_byte(rocaddr + 0x00, 0x00)  # R0 = reg addr low
                bus.write_byte(rocaddr + 0x01, 0x00)  # R1 = reg addr high
                print("ROC reg readback:", hex(bus.read_byte(rocaddr + 0x02)))  # R2
                ok.append(rocaddr)
            except OSError as e:
                print(f"  [WARN] ROC 0x{rocaddr:02x} on switch 0x{muxAddr:02x} "
                      f"stopped responding mid-config ({e}); skipping")
                bad.append(rocaddr)
    # leave this module's switch disconnected before moving to the next one
    bus.write_byte(muxAddr, 0x00)
    print(f"--- switch 0x{muxAddr:02x}: {len(ok)} ROC(s) enabled "
          f"{[hex(a) for a in ok]}"
          + (f", {len(bad)} FAILED {[hex(a) for a in bad]}" if bad else ""))
    return ok, bad


def main():
    # Which modules to bring up, by their PCA9848 switch address (A=0x71, B=0x73,
    # C=0x77). Pass the switch(es) on the command line so you don't edit this file
    # every time the loopback moves, e.g.:
    #     python enableROCs.py 71          # hexaboard on A
    #     python enableROCs.py 73          # hexaboard on B
    #     python enableROCs.py 71 73       # two real hexaboards
    # Args are parsed as hex ("71" == "0x71"). Default = 0x71.
    #
    # List ONLY switches that carry a real LD/HD hexaboard. A V3D loopback board
    # has NO HGCROCs; do not list its switch -- probing its absent ROC addresses
    # NACKs and can WEDGE the shared master bus for the real module.
    modules = [int(a, 16) for a in sys.argv[1:]] or [0x71]
    print("Bringing up module switch(es):", [hex(m) for m in modules])

    # LD hexaboard: all 3 HGCROCs are on the same ROC sub-bus (port 0x02).
    ROCAddrs = {
        0x02: (0x08, 0x18, 0x28),
    }

    with SMBus(2) as bus:
        for muxAddr in modules:
            enable_module(bus, muxAddr, ROCAddrs)


if __name__ == "__main__":
    main()

