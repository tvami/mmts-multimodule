# MMTS: the other board types

Sections 4 to 10 of [mmts_instructions.md](mmts_instructions.md), one per board type.
Read that document first: 0 installs the bench, 1 powers up, 2 runs a board and
3 is the LD Full. Section numbers outside 4 to 10 below (1.0, 2.3, 11.3, 12.3, ...)
refer to it.

## Contents

- [4. LD Five (L5)](#4-ld-five-l5)
- [5. LD Left and LD Right (LL, LR)](#5-ld-left-and-ld-right-ll-lr)
- [6. LD Bottom and LD Top (LB, LT)](#6-ld-bottom-and-ld-top-lb-lt)
- [7. HD Full (HF)](#7-hd-full-hf)
- [8. HD Top (HT)](#8-hd-top-ht)
- [9. HD Bottom (HB)](#9-hd-bottom-hb)
- [10. HD Semi (HL, HR)](#10-hd-semi-hl-hr)

---

# 4. LD Five (L5)

| | |
|---|---|
| `--board` | `LD-Five` |
| ROCs | 3, at `0x48 0x58 0x68` |
| power distribution board | none, so `--external-power` |
| DAQ links | 5, links `0 1 4 5 9` on every slot, idcodes `0 1 36 37 72` |
| trigger links | 10 of 12 live; the shipped configs keep two per slot: A `0 4`, B `1 4`, C `1 6` |
| halves in the pedestal output | five |
| delay scan gate | 5/5 and 2/2 |
| run configs | `configs/initLD-Five-3b_mux{A,B,C}_ped.yaml` |
| `EdgeSel_T1` | per slot, in the shipped configs: A 1, B 1, C 0 |
| entries per 10 000-event run | 1 956 240 |

**A 2-of-3 enable with `0x58` missing is a known bad-board signature**, not
a bench problem. `enableROCs.py` exits 1 on an incomplete set; trust it.

**A stall at 64 events behind a clean gate and a perfect finder line is a
wrong `idcode`, not a link fault.** An `idcode` names the chip and half a link
carries; `77` on `link9` claimed a fourth chip on a three-chip board and
`daq-server` halted eleven events after that link stopped. The shipped
configs carry the right codes; before spending a bring-up on a stall, unpack
the kept `.raw` per 11.5 and read the chip ids.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Five-3b LD-Five 3 ldfive 5
```

## 4.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --external-power --board LD-Five"
"$MM/delay_scan.sh" A configs/initLD-Five-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" A 5 ldfive 10000
```

## 4.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh B --external-power --board LD-Five"
"$MM/delay_scan.sh" B configs/initLD-Five-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" B 5 ldfive 10000
```

## 4.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh C --external-power --board LD-Five"
"$MM/delay_scan.sh" C configs/initLD-Five-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" C 5 ldfive 10000
```

---

# 5. LD Left and LD Right (LL, LR)

| | |
|---|---|
| `--board` | `LD-Semi` |
| ROCs | 2, at `0x48 0x58` |
| power distribution board | none, so `--external-power` |
| DAQ links | 3, links `0 1 4`, idcodes `0 1 36` |
| trigger links | 6 live: `0 1 2 3 5 6` on A and B, `0 1 2 4 5 11` on C; the shipped configs keep two per slot: A `5 6`, B `0 3`, C `1 4` |
| halves in the pedestal output | three |
| delay scan gate | 3/3 and 2/2 |
| run configs | `configs/initLD-Left-3b_mux{A,B,C}_ped.yaml` |
| `EdgeSel_T1` | per slot, in the shipped configs: A 1, B 1, C 0 |
| entries per 10 000-event run | 1 173 744 |

Both geometries use the `LD-Left` config family. Three bonded halves give one
DAQ and two trigger links each, so six trigger links are live; the config
lists two, and the gate counts what the config lists. Measured 2026-09-02 on
three LD Lefts: every slot passed first time once the probe was taken out of
the bring-up, per 11.3.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Left-3b LD-Semi 2 ldleft 5
```

The `bench_up.sh` cold start of 1.3 in its partial form. Every LD partial takes
this line, so section 6 uses it unchanged. No `--power-board`:

**(on the lab computer, when driving a cold start by hand, not in a normal run)**

```bash
"$MM/bench_up.sh" A --board LD-Semi --expect 2
```

## 5.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board LD-Semi"
"$MM/delay_scan.sh" A configs/initLD-Left-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" A 5 ldleft 10000
```

## 5.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board LD-Semi"
"$MM/delay_scan.sh" B configs/initLD-Left-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" B 5 ldleft 10000
```

## 5.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board LD-Semi"
"$MM/delay_scan.sh" C configs/initLD-Left-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" C 5 ldleft 10000
```

---

# 6. LD Bottom and LD Top (LB, LT)

| | |
|---|---|
| `--board` | `LD-Semi` |
| ROCs | 2, at `0x48 0x58` |
| power distribution board | none, so `--external-power` |
| DAQ links | 3, links `0 1 4`, idcodes `0 1 36` |
| trigger links | **3** on an LD Bottom: A `1 2 6`, B `1 2 5`; C carries two, `1 5` |
| halves in the pedestal output | three |
| delay scan gate | 3/3 and 3/3 on A and B; 3/3 and 2/2 on C |
| run configs | `configs/initLD-Bottom-3b_mux{A,B,C}_ped.yaml` |
| `EdgeSel_T1` | per slot, in the shipped configs: A 1, B 1, C 0 |
| entries per 10 000-event run | 1 173 744 |

**An LD Bottom drives THREE trigger links, not six. That is the board type,
not a fault.** Measured 2026-09-02 on three LD Bottoms, ten runs each: gate
PASS, CRC 1.000 on all three halves, finder at 23 everywhere. Slot C's `link2`
gated `ngood 0` and was dropped from that slot's config.

A pedestal does not test the link count. `randomL1A` barely exercises the
trigger path. Use a TPG run for that.

An **LD Top** has the same two ROCs and electrical setup, but its link map is
not measured. Probe one with `run_slot.sh` and no `SKIP_PROBE=1`, per 11.3,
before trusting the LD Bottom map on it.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Bottom-3b LD-Semi 2 ldbottom 5
```

## 6.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board LD-Semi"
"$MM/delay_scan.sh" A configs/initLD-Bottom-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" A 5 ldbottom 10000
```

## 6.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board LD-Semi"
"$MM/delay_scan.sh" B configs/initLD-Bottom-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" B 5 ldbottom 10000
```

## 6.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board LD-Semi"
"$MM/delay_scan.sh" C configs/initLD-Bottom-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" C 5 ldbottom 10000
```

---

# 7. HD Full (HF)

| | |
|---|---|
| `--board` | `HD-Full` |
| ROCs | **6**, at `0x08 0x18 0x28 0x48 0x58 0x68` |
| power distribution board | **fitted**, so no `--external-power` |
| DAQ links | 12 |
| trigger links | 12, so **24 e-links**, double an LD Full |
| halves in the pedestal output | twelve, not six |
| run configs | `configs/initHD-Full-trophyV3_mux{A,B,C}_ped.yaml` |
| draw, all chips running | **4.43 A at 1.72 V** |

**Check the supply first, per 1.0.** Six chips draw more than one channel
of a 3.2 A bench supply. At the limit the rail sags to 1.35 V and all 24
e-links die.

**A partial enable is not success.** Require `EXPECT_ROCS=6` **and** no
`FAILED` in the log.

**If some trigger links will not align, drop *those* links and keep the
rest.** Do **not** set `elinks_trg: []`: with no trigger links `daq-server`
starts and hangs forever. Eight good trigger links are ample.

**Expected on a healthy HD Full:**

| | |
|---|---|
| DAQ links | 12/12, `wmax` 42-92 |
| CRC pass | **1.000 on all 12 halves**, `badBX` 0.000 |
| entries per 10 000-event run | 4 694 976 |
| `adc_stdd` median | ~1.24 |

**(on the lab computer)**

```bash
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" A initHD-Full-trophyV3 HD-Full 6 hdfull 5
```

## 7.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh A --board HD-Full"
"$MM/delay_scan.sh" A configs/initHD-Full-trophyV3_muxA_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" A 5 hdfull 10000
```

## 7.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh B --board HD-Full"
"$MM/delay_scan.sh" B configs/initHD-Full-trophyV3_muxB_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" B 5 hdfull 10000
```

## 7.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh C --board HD-Full"
"$MM/delay_scan.sh" C configs/initHD-Full-trophyV3_muxC_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" C 5 hdfull 10000
```

---

# 8. HD Top (HT)

| | |
|---|---|
| `--board` | `HD-Top` |
| ROCs | 3, at `0x18 0x58 0x28` |
| power distribution board | **none** on every HD Top run so far, so `--external-power` |
| DAQ links | 5, links `0 1 4 5 9` on every slot |
| trigger links | per slot: A `0 1 5 9`, B `0 1`, C `0` |
| halves in the pedestal output | five |
| delay scan gate | A 5/5 and 4/4, B 5/5 and 2/2, C 5/5 and 1/1 |
| run configs | `configs/initHD-Top-trophyV3_mux{A,B,C}_ped.yaml` |
| draw, all chips running | ~2.1 A at 1.72 V; 0.4 to 0.5 A per channel with the ROCs idle |

Measured 2026-09-03, three HD Tops, 3 and then 10 runs each through
`run_slot.sh` with `SKIP_PROBE=1`: 39 of 39 runs at CRC 1.000 on all five
halves, `badBX` 0.000. Two more sets by hand later that day gave the same.

**The power flag.** Without `--external-power` the bring-up writes `EN_Mx`
on the `0x27` power board, which is not in the loop on a bench-fed module. The
write fails with `retry 5/5` and a `write_byte` traceback, or the probe reads
`0/3` on all eight attempts, while the supply sits at 0.4 to 0.5 A per
channel. Add the flag; one recover-form bring-up clears it without a power
cycle:

**(on the lab computer)**

```bash
ssh kria "pkill -f '[z]mq_server'; sleep 2; cd ~/multimodule && \
  ./mmts_bringup.sh A --recover --external-power --board HD-Top"
```

**HD trophies swap four P/N pairs per module.** A dead set of trigger links
wants `polarity: 0` per e-link in the yaml, not a different bitstream and not
`in_inv_cmd_rx`. The shipped configs carry the measured sets, per slot; never
copy a trigger map across slots. DAQ is the same five links everywhere.

**`EdgeSel_T1` is per slot:** 1 on A and B, 0 on C, in the shipped configs.
At the wrong edge one half rails at `adc_mean` ~709 with CRC 0.000 while the
other four look perfect. Check `header positions` in `daq-server.log` first;
every link at 23 is right.

One command per slot. `--external-power` is the default, so no `POWER=`:

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initHD-Top-trophyV3 HD-Top 3 hdtop 5
```

Hand-driven, the previous slot's i2c-server must be dead before the bring-up
starts. A stale server holding the bus produced a chip that `stopped
responding mid-config` and a 2 of 3 enable. `up_verified.sh` kills it; a
hand-typed `mmts_bringup.sh` needs the `pkill` above.

## 8.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --external-power --board HD-Top"
"$MM/delay_scan.sh" A configs/initHD-Top-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" A 5 hdtop 10000
```

## 8.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh B --external-power --board HD-Top"
"$MM/delay_scan.sh" B configs/initHD-Top-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" B 5 hdtop 10000
```

## 8.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh C --external-power --board HD-Top"
"$MM/delay_scan.sh" C configs/initHD-Top-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" C 5 hdtop 10000
```

## 8.4 Expected on a healthy HD Top

Per run of 10 000 events:

| | |
|---|---|
| entries | 1 956 240 |
| CRC pass | 1.000 on all five halves, `badBX` 0.000 |
| `adc_mean` per half | 85 to 120 |
| total noise, median over halves | 1.00 to 1.04 ADC |
| after common-mode subtraction | 0.92 to 0.96 ADC |
| common mode | 15 to 18 % of the variance |
| time per run | ~30 s |

The common-mode share is a bench number, not a board number. A bare hexaboard
flat on a metal plate read 55 to 68 % on the same boards; a spacer under it
brought that to 15 to 18 %.

---

# 9. HD Bottom (HB)

| | |
|---|---|
| `--board` | `HD-Bottom` |
| ROCs | 4, at `0x18 0x58 0x28 0x68` |
| power distribution board | not yet seen; every HD partial so far had none, so start with `--external-power` and read the supply per 1.0 |
| link sets | **not yet measured.** The shipped configs list links `4` to `11` for both DAQ and trigger as a template |
| delay scan gate | not yet measured; probe first, per 11.3 |
| run configs | `configs/initHD-Bottom-trophyV3_mux{A,B,C}_ped.yaml` |

No HD Bottom has been run yet. Section 8's trophy P/N warning and power-flag
paragraph apply: `retry 5/5` at the `0x27` write means the module is
bench-fed. Run `run_slot.sh` without `SKIP_PROBE=1` on the first board so the
live links are written into the configs, then use the blocks below.

## 9.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh A --external-power --board HD-Bottom"
"$MM/delay_scan.sh" A configs/initHD-Bottom-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" A 5 hdbottom 10000
```

## 9.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh B --external-power --board HD-Bottom"
"$MM/delay_scan.sh" B configs/initHD-Bottom-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" B 5 hdbottom 10000
```

## 9.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh C --external-power --board HD-Bottom"
"$MM/delay_scan.sh" C configs/initHD-Bottom-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" C 5 hdbottom 10000
```

---

# 10. HD Semi (HL, HR)

| | |
|---|---|
| `--board` | `HD-Semi` |
| ROCs | 2, at `0x08 0x18` |
| power distribution board | not yet seen; every HD partial so far had none, so start with `--external-power` and read the supply per 1.0 |
| link sets | **not yet measured.** The shipped configs list links `0 1 4 5` for both DAQ and trigger as a template |
| delay scan gate | not yet measured; probe first, per 11.3 |
| run configs | `configs/initHD-Semi-trophyV3_mux{A,B,C}_ped.yaml` |

No HD Semi has been run yet. Section 8's trophy P/N warning and power-flag
paragraph apply. Run `run_slot.sh` without `SKIP_PROBE=1` on the first board
so the live links are written into the configs, then use the blocks below.

## 10.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board HD-Semi"
"$MM/delay_scan.sh" A configs/initHD-Semi-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" A 5 hdsemi 10000
```

## 10.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board HD-Semi"
"$MM/delay_scan.sh" B configs/initHD-Semi-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" B 5 hdsemi 10000
```

## 10.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board HD-Semi"
"$MM/delay_scan.sh" C configs/initHD-Semi-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" C 5 hdsemi 10000
```
