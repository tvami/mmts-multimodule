#!/usr/bin/env python3
"""Power the multiplexer board slots via Link.mux_setup, then report which slot
actually came up (power-good bits) and which ROCs answer there."""
import sys, time
sys.path.insert(0, "/home/daq/multimodule/hexactrl-sw/zmq_i2c")
from smbus2 import SMBus
import Link

slot = sys.argv[1] if len(sys.argv) > 1 else "B"
print(f"--- mux_setup(slot={slot!r}) ---")
Link.mux_setup(slot=slot)
time.sleep(1.0)

SW = {"A": 0x71, "B": 0x73, "C": 0x77}
with SMBus(2) as bus:
    for s, sw in SW.items():
        try:
            bus.write_byte(sw, 0x20)
            p1 = bus.read_byte_data(0x20, 0x01)
            out1 = bus.read_byte_data(0x20, 0x03)
            bus.write_byte(sw, 0x00)
        except OSError as e:
            print(f"  via 0x{sw:02x}: {e}")
            continue
        print(f"  via 0x{sw:02x}: pwr_en(s1,s2,s3)="
              f"{(out1>>2)&1},{(out1>>3)&1},{(out1>>4)&1}  "
              f"pwr_pg(s1,s2,s3)={(p1>>5)&1},{(p1>>6)&1},{(p1>>7)&1}")
        break   # the GPIO chips are shared; one read is enough

    print("--- ROC probe on S1_I2C (sub-bus 1) of every switch ---")
    for s, sw in SW.items():
        try:
            bus.write_byte(sw, 1 << 1)
        except OSError as e:
            print(f"  switch 0x{sw:02x} did not ACK ({e})")
            continue
        found = []
        for addr in (0x08, 0x18, 0x28, 0x48, 0x58, 0x68):
            try:
                bus.read_byte(addr)
                found.append(hex(addr))
            except OSError:
                pass
        print(f"  slot {s} (0x{sw:02x}): ROCs {found if found else 'none'}")
        try:
            bus.write_byte(sw, 0x00)
        except OSError:
            pass
