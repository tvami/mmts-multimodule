#!/usr/bin/env python3
"""Same ROC traffic as i2cstress.py, but the PCA9848 sub-bus is selected ONCE and
left open, instead of being opened and closed around every byte (which is what
Link.mux_i2c does). Tells us whether the switch toggling is what wedges the bus."""
import sys, time
from smbus2 import SMBus

SW, ROCS, N = 0x73, (0x08, 0x18, 0x28), int(sys.argv[1]) if len(sys.argv) > 1 else 300
ok = err = 0
first_err = None
t0 = time.time()
with SMBus(2) as bus:
    bus.write_byte(SW, 0x02)              # open ROC sub-bus once
    for i in range(N):
        roc = ROCS[i % len(ROCS)]
        try:
            bus.write_byte(roc + 0x00, 0x00)
            bus.write_byte(roc + 0x01, 0x00)
            bus.read_byte(roc + 0x02)
            ok += 1
        except OSError as e:
            err += 1
            if first_err is None:
                first_err = (i, hex(roc), str(e))
            break
    try:
        bus.write_byte(SW, 0x00)
    except OSError:
        pass
print(f"{ok} ok, {err} failed out of {N} attempted in {time.time()-t0:.1f}s")
print(f"first failure at transaction {first_err[0]} on ROC {first_err[1]}: {first_err[2]}"
      if first_err else "no failures")
