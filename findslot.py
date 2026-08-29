#!/usr/bin/env python3
"""Find which multiplexer-board slot the single populated module answers on.

A NACK'd read wedges this bench's PL I2C master, so each slot is probed in its
own attempt and the master is reset with `fw-loader load` (payload power, and
therefore the power management board's EN_Mx latch, is preserved) between them.
"""
import subprocess, sys, time
from smbus2 import SMBus

SWITCH = {"A": 0x71, "B": 0x73, "C": 0x77}
ROC_ADDRS = (0x08, 0x18, 0x28)

def reset_master():
    subprocess.run(["sudo", "fw-loader", "load", "multimodule-hd-tester-trophy-v3"],
                   check=True, stdout=subprocess.DEVNULL)
    time.sleep(2)

def mux_power_all():
    """S1/S2/S3 PWR_EN high and RSTB released (writes only, no reads)."""
    with SMBus(2) as bus:
        bus.write_byte(0x73, 0x20)
        bus.write_byte_data(0x20, 0x07, 0xE3)
        bus.write_byte_data(0x20, 0x03, 0x1C)
        time.sleep(0.3)
        bus.write_byte_data(0x20, 0x06, 0xF1)
        bus.write_byte_data(0x20, 0x02, 0x0E)
        bus.write_byte(0x73, 0x00)

for slot, sw in SWITCH.items():
    reset_master()
    try:
        mux_power_all()
    except OSError as e:
        print(f"slot {slot}: mux GPIO write failed ({e})")
        continue
    time.sleep(0.5)
    found, wedged = [], False
    try:
        with SMBus(2) as bus:
            bus.write_byte(sw, 0x02)          # S1_I2C sub-bus
            for a in ROC_ADDRS:
                try:
                    bus.read_byte(a)
                    found.append(hex(a))
                except OSError:
                    pass
            bus.write_byte(sw, 0x00)
    except OSError as e:
        wedged = True
    print(f"slot {slot} (switch 0x{sw:02x}): "
          f"{found if found else 'no ROCs'}{' [bus wedged during probe]' if wedged else ''}")
