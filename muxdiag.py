#!/usr/bin/env python3
"""Read-only-ish diagnostic of the MMTS multiplexer board state.

For each PCA9848 switch (A=0x71, B=0x73, C=0x77) open the "Sgl" sub-bus (0x20)
and dump the two TCAL6416 GPIO expanders (0x20/0x21): input, output and config
registers. Decode the per-slot power-enable / power-good bits.
No writes other than the switch select byte and no probing of absent devices.
"""
from smbus2 import SMBus

SW = {"A": 0x71, "B": 0x73, "C": 0x77}
BITS20_P0 = {1: "s1_rstb", 2: "s2_rstb", 3: "s3_rstb", 4: "fmc_error",
             5: "s2_error_l", 6: "s3_error_l", 7: "s1_error_r"}
BITS20_P1 = {0: "s2_error_r", 1: "s3_error_r", 2: "s1_pwr_en", 3: "s2_pwr_en",
             4: "s3_pwr_en", 5: "s1_pwr_pg", 6: "s2_pwr_pg", 7: "s3_pwr_pg"}
BITS21_P0 = {0: "adc_rdy_pwr", 1: "adc_rdy_s1", 2: "adc_rdy_s2", 3: "adc_rdy_s3",
             4: "s1_i2c_rst", 5: "s2_i2c_rst", 6: "s3_i2c_rst"}
BITS21_P1 = {2: "pg_dcdc"}

def decode(val, names):
    return " ".join(f"{n}={ (val>>b)&1 }" for b, n in sorted(names.items()))

with SMBus(2) as bus:
    for slot, sw in SW.items():
        print(f"=== switch 0x{sw:02x} (slot {slot}) ===")
        try:
            bus.write_byte(sw, 0x20)   # Sgl sub-bus (GPIO controllers)
        except OSError as e:
            print(f"  switch did not ACK: {e}")
            continue
        for addr, p0, p1 in ((0x20, BITS20_P0, BITS20_P1), (0x21, BITS21_P0, BITS21_P1)):
            try:
                in0, in1 = bus.read_byte_data(addr, 0x00), bus.read_byte_data(addr, 0x01)
                ou0, ou1 = bus.read_byte_data(addr, 0x02), bus.read_byte_data(addr, 0x03)
                cf0, cf1 = bus.read_byte_data(addr, 0x06), bus.read_byte_data(addr, 0x07)
            except OSError as e:
                print(f"  0x{addr:02x}: no answer ({e})")
                continue
            print(f"  0x{addr:02x} in=0x{in0:02x},0x{in1:02x} "
                  f"out=0x{ou0:02x},0x{ou1:02x} cfg=0x{cf0:02x},0x{cf1:02x}")
            print(f"       P0 in : {decode(in0, p0)}")
            print(f"       P1 in : {decode(in1, p1)}")
        try:
            bus.write_byte(sw, 0x00)
        except OSError:
            pass

    # Is there a power management board on the "Spare" sub-bus (0x10)?
    print("=== power management board probe (Spare sub-bus 0x10, via 0x73) ===")
    bus.write_byte(0x73, 0x10)
    for addr in range(0x20, 0x28):
        try:
            bus.read_byte(addr)
            print(f"  ACK at 0x{addr:02x}")
        except OSError:
            pass
    bus.write_byte(0x73, 0x00)
    print("  (no ACK lines above = no power management board GPIO found)")
