#!/usr/bin/env python3
"""Measure how stable ROC I2C traffic is on this bench.

Mimics what Boards.configure does: select the ROC sub-bus, write the register
address (R0/R1), read R2 -- over and over, counting failures and reporting where
the first one lands.
"""
import sys, time
from smbus2 import SMBus

SW, ROCS, N = 0x73, (0x08, 0x18, 0x28), int(sys.argv[1]) if len(sys.argv) > 1 else 200
ok = err = 0
first_err = None
t0 = time.time()
with SMBus(2) as bus:
    for i in range(N):
        roc = ROCS[i % len(ROCS)]
        try:
            bus.write_byte(SW, 0x02)          # open ROC sub-bus
            bus.write_byte(roc + 0x00, 0x00)  # R0 = reg addr low
            bus.write_byte(roc + 0x01, 0x00)  # R1 = reg addr high
            bus.read_byte(roc + 0x02)         # R2 = value
            bus.write_byte(SW, 0x00)          # close
            ok += 1
        except OSError as e:
            err += 1
            if first_err is None:
                first_err = (i, hex(roc), str(e))
            break   # once wedged, everything after fails; stop here
print(f"{ok} ok, {err} failed out of {N} attempted in {time.time()-t0:.1f}s")
if first_err:
    print(f"first failure at transaction {first_err[0]} on ROC {first_err[1]}: {first_err[2]}")
else:
    print("no failures")
