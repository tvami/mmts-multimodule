# MMTS LD Full at UCSB: bring-up step by step (primed bus)

This is the UCSB version of Parts A to C of `ldfull_step_by_step.md`. It is the
command chain that brought the LD Full in slot A up on 2026-11-19 (kria11,
8:02AM PST): 3 of 3 ROCs, board identified as `V3 LD Full HB`, ports 5555 and
6000 listening, and the **GW Instek at 2.1 A**.

The difference from the standard page: on this bench the mux I2C bus only works
after **channel 2 of slot A's switch (0x71) is turned on** ("priming"). That
channel can only be set with the 20 kHz firmware loaded, and every `kconn_pwr`
cycle clears it. Part P does the priming by hand before the bring-up.

Before you start:

* Slot A: LD Full trophy, mezzanine and module, fully cabled.
* **Slots B and C empty.** Selecting slot B's Sgl branch kills a primed bus.
* GW Instek on, output on, settings unchanged (11-17 note: 1.8 V).
* All commands run on the Kria: `ssh daq@10.0.1.44`.

Do not run `i2cdetect` at any point. Never `sudo reboot` kria11; power button only.

---

## Part P. Prime the bus (Kria)

**P1.** Stop any i2c-server and clear stale GPIO holders.

```bash
pkill -f zmq_server
pkill -f 'gpioset -m signal -b'
```

**P2.** Cycle the payload with the **20 kHz** firmware loaded.

```bash
sudo kconn_pwr off
sudo fw-loader load multimodule-hd-tester-trophy-v3-rxeq4-i2ck20
sudo kconn_pwr on
```

Wait about 5 s before P3. The Instek reads 0.0 A from here until the bring-up.
That is correct.

**P3.** Turn on 0x71 channel 2.

First reset the switches once:

```bash
sudo gpioset $(gpiofind I2C_RST)=0
sudo gpioset $(gpiofind I2C_RST)=1
```

Then write `0x04` to 0x71 and read it back:

```bash
i2cset -y 2 0x71 0x04
i2cget -y 2 0x71
```

**Repeat these two lines until `i2cget` prints `0x04`.** `Error: Write failed`,
`Error: Read failed` or any other value just means try again. On 11-19 it took 7
tries. If it has not worked after about 50, do the I2C_RST reset again and keep
going. If it still will not latch, go back to P1.

**P4.** Load the production firmware. **No `kconn_pwr` here**: a payload cycle
would clear the channel you just set.

```bash
sudo fw-loader load multimodule-hd-tester-trophy-v3
ls -l /dev/i2c-2
```

Wait a few seconds before P5.

**P5.** Check the bus is primed. Read the three switches and one empty address:

```bash
i2cget -y 2 0x71
i2cget -y 2 0x73
i2cget -y 2 0x77
i2cget -y 2 0x55
```

**Repeat this block about 5 times.** Primed, every time:

| address | prints |
|---|---|
| 0x71 | `0x04` |
| 0x73 | `0x00` |
| 0x77 | `0x00` |
| 0x55 (nothing there) | `Error: Read failed` |

A single `Error: Read failed` on 0x71, 0x73 or 0x77, or 0x71 showing anything
but `0x04`, means the bus is not primed: go back to P1. An answer from 0x55 is
a fake ACK, and that also means go back to P1.

---

## Part A. Bring up the slot (Kria)

**A1.** Go to the bring-up directory.

```bash
cd ~/multimodule
```

**A2.** Power the module and enable its three ROCs.

```bash
python3 enableROCs.py A --board LD-Full --keep-others
```

`--keep-others` is required here. Without it the script first writes to the
switches of slots B and C, and that kills the primed bus. Do **not** add
`--recover` (it would cycle the payload) or `--no-reset` (the run that reached
2.1 A did the `[rst]` reload).

This one command does, in order:

1. `[pwr]` sets EN_M1 on the power board (0x27, through 0x77's Spare channel). Each write is read back.
2. `[rst]` `sudo fw-loader load multimodule-hd-tester-trophy-v3` with payload power on. Channel 2 survives it.
3. `[mux]` sets slot A's PWR_EN, then releases RSTB. Every write to 0x71 keeps bit 2 (0x04) set.
4. `[roc]` finds 0x08, 0x18, 0x28 and enables each one.

Good output on 11-19:

```
[pwr] power management board 0x27 (via switch 0x77, Spare sub-bus): EN_M1 high
[rst] fw-loader load multimodule-hd-tester-trophy-v3 (resets the PL I2C master, keeps payload power)
[mux] switch 0x71: S*_PWR_EN high
      transient I2C error ([Errno 5] Input/output error), retry 1/5
      transient I2C error ([Errno 5] Input/output error), retry 2/5
      transient I2C error ([Errno 5] Input/output error), retry 3/5
[mux] switch 0x71: S*_RSTB released
[roc] slot A (0x71): ['0x8', '0x18', '0x28']
[roc] enabling 0x08
[roc] enabling 0x18
[roc] enabling 0x28

--- slot A (switch 0x71): 3 ROC(s) enabled ['0x8', '0x18', '0x28']
```

A few `retry n/5` lines are normal. Anything else (`2 ROC(s)`, any `FAILED`,
`retry 5/5`) means **go back to P1**: a retry always starts with a fresh
priming. On 11-19 it took 2 tries (the first gave 1 of 3 ROCs); up to 8 is normal.

---

## Part B. Start the i2c-server (Kria)

**B1.** Start it, detached, for slot A.

```bash
cd ~/multimodule/hexactrl-sw/zmq_i2c
PYTHONUNBUFFERED=1 setsid nohup python3 zmq_server.py --mux --slot A > ~/zmq_srvA.log 2>&1 < /dev/null &
```

**B2.** Wait about 25 s, then check.

```bash
grep -E "Board identification|ERROR|Traceback" ~/zmq_srvA.log | tail -5
ss -ltn | grep ':5555 '
```

Good: `[I2C] Board identification: V3 LD Full HB`, and 5555 listening.

If not: `pkill -f zmq_server`, then B1 and B2 again, up to 3 times. After 3
failures go back to P1.

---

## Part C. Start the daq-server (Kria)

Always after the i2c-server.

**C1.** Stop the old one.

```bash
pkill -f '[d]aq-server'
```

**C2.** Start it.

```bash
source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
setsid /opt/hexactrl/ROCv3-alper-dev/bin/daq-server -f /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml -p 6000 > ~/daq-server.log 2>&1 < /dev/null &
```

**C3.** Wait a few seconds, then check both servers.

```bash
ss -ltn | grep -E ':5555 |:6000 '
```

Two lines: the slot is up. **Read the Instek now: about 2.1 A.**

---

## What the Instek shows

| moment | current |
|---|---|
| P2 to the start of A2 (payload cycled, module off) | 0.0 A |
| payload on, power board only | about 0.1 A |
| after A2 with 3 ROCs enabled | **2.1 A** |

If it reads 0.0 A after A2 printed `3 ROC(s) enabled`, check the supply's output
and range first.

---

## After this

The links and pedestals are Parts D to F of `ldfull_step_by_step.md`. On 11-19
the delay scan right after this bring-up **failed** (daq 5/6, trg 10/12). The
i2c-server logged 13 I2C errors during configure, and then 0x71 read `0xFF`, so
the priming was lost. 2.1 A proves the module is powered and enabled, not that
the DAQ chain works.

Check the priming is still there at any point (0x04 or 0x06 is good, `0xff` or
`EIO` means it is gone, go back to P1):

```bash
i2cget -y 2 0x71
```

## When you are done

```bash
pkill -f zmq_server
pkill -f '[d]aq-server'
pkill -f 'gpioset -m signal -b'
sudo kconn_pwr off
```

The Instek drops back to about 0 A.

## If it fails

| you see | do |
|---|---|
| P3 never reads back `0x04` | back to P1; if it fails 3 times, power-cycle the Kria with its button |
| P5 any read error on 0x71/0x73/0x77, or 0x55 answers | back to P1 |
| A2 `retry 5/5` at `[pwr]` | power board not cabled or the Instek output is off |
| A2 `retry 5/5` at `[mux]` | the priming was lost; back to P1 |
| A2 a different ROC count each try | normal lottery; back to P1, up to 8 tries |
| A2 `no ROCs`, Instek near 0 A | the module is not powered: check the lead into the power board |
| B2 no `Board identification` after 3 restarts | back to P1 |
| any step, `Errno 5` on every try | `sudo shutdown -h now`, wait 20 s, press the Kria's power button, start at P1 |

Do not use the DRIVE 8 (`-i2cx-d8`) or 20 kHz firmware for P4 or A2. On 11-19,
DRIVE 8 failed every bring-up at `[mux]`, and the 20 kHz build only reached 2 of 3 ROCs.
