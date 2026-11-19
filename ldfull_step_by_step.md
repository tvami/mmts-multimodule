# MMTS LD Full: run step by step

Before this, finish steps 1 to 4 of `ldfull_quickstart.md` once per bench: the
Kria is flashed, the lab computer is set up, and the boards are registered.
This page replaces its step 5.

This page assumes a **power management board** is fitted (the module's power
comes through it). Each LD Full draws up to 2 A while running. The supply reads
0 A until step A6 runs; that is correct.

You need two terminals:

* **Kria**: `ssh daq@$KRIA_IP`, then everything in parts A, B and C.
* **Lab computer**: everything in parts D, E and F.

Do not run `i2cdetect` on the Kria at any point. It can lock up the I2C bus.

---

## Part A. Bring up the slot (Kria)

**A1.** Stop any i2c-server left from the previous slot. It holds the bus.

```bash
pkill -f zmq_server
```

**A2.** Clear stale GPIO holders left by a killed server.

```bash
pkill -f 'gpioset -m signal -b'
```

**A3.** Power-cycle the payload and reload the firmware. This gives the I2C
master a clean start and switches every slot off.

```bash
sudo kconn_pwr off
sudo fw-loader load multimodule-hd-tester-trophy-v3
sudo kconn_pwr on
```

**A4.** Check the I2C device came back after the reload.

```bash
ls -l /dev/i2c-2
```

**A5.** Go to the bring-up directory.

```bash
cd ~/multimodule
```

**A6.** Power the module and enable its three ROCs.

```bash
python3 enableROCs.py A --board LD-Full --keep-others
```

This one command does, in order:

1. `[pwr]` sets the power board's EN_M bit for this slot (chip 0x27, through switch 0x77).
2. `[rst]` runs `sudo fw-loader load multimodule-hd-tester-trophy-v3` again. Turning the module on glitches the I2C master; a reload with payload power on clears it and keeps the module on.
3. `[mux]` sets the slot's PWR_EN, then releases the ROC resets (RSTB).
4. `[roc]` finds the ROCs at 0x08, 0x18, 0x28 and enables each one.

`--keep-others` is right here because A3 already switched the other slots off.

Good output ends with:

```
--- slot A (switch 0x71): 3 ROC(s) enabled ['0x8', '0x18', '0x28']
```

Anything else (`no ROCs`, `2 ROC(s)`, any `FAILED`) means **go back to A1**.
Bring-up is a lottery and about half the tries fail partway; up to 8 tries is
normal. The supply should now show the module drawing current.

---

## Part B. Start the i2c-server (Kria)

**B1.** Start it, detached, for this slot.

```bash
cd ~/multimodule/hexactrl-sw/zmq_i2c
PYTHONUNBUFFERED=1 setsid nohup python3 zmq_server.py --mux --slot A > ~/zmq_srvA.log 2>&1 < /dev/null &
```

**B2.** Give it about 25 s to identify the board, then check.

```bash
grep -E "Board identification|ERROR|Traceback" ~/zmq_srvA.log | tail -5
ss -ltn | grep ':5555 '
```

Good: a `Board identification` line naming `V3 LD Full HB`, and port 5555
listening.

If not, restart it (up to 3 times):

```bash
pkill -f zmq_server
```

then B1 and B2 again. After 3 failures, go back to A1.

Never use `systemctl start zmq-server@...`: that runs the RPM copy, without the
bench fixes.

---

## Part C. Start the daq-server (Kria)

Always after the i2c-server, never before. A restart also releases the trigger
claim it holds for the previous slot, so it must be restarted on every slot
change.

**C1.** Stop the old one.

```bash
pkill -f '[d]aq-server'
```

**C2.** Start it.

```bash
source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
setsid /opt/hexactrl/ROCv3-alper-dev/bin/daq-server -f /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml -p 6000 > ~/daq-server.log 2>&1 < /dev/null &
```

**C3.** Check both servers are listening.

```bash
ss -ltn | grep -E ':5555 |:6000 '
```

Two lines, one for 5555 and one for 6000: the slot is ready. If 6000 is
missing, read `~/daq-server.log` and repeat C1 and C2.

---

## Part D. Set up the lab computer terminal

**D1.** Load the software environment.

```bash
source $HEXACTRL/etc/env.sh
source $MMTS_VENV/bin/activate
export PATH=$HEXACTRL/bin:$PATH
```

**D2.** Set the names the runs use.

```bash
LABEL=ldfull
SERIAL=$(python3 $MM/module_of.py A)
OUT=$RESULTS_DIR/$SERIAL
CFG=configs/initLD-Full-3b_muxA_ped.yaml
echo "slot A  board $SERIAL"
```

If no serial prints, register the boards first (quickstart step 4).

**D3.** Restart the puller. It receives the data on port 6001. Only one puller
may run per Kria.

```bash
pkill -f '[d]aq-client( -p 6001)?$'
setsid $HEXACTRL/bin/daq-client -p 6001 >> $MMTS_ROOT/daq-client.log 2>&1 < /dev/null &
ss -ltn | grep ':6001 '
```

One line for 6001 means the puller is up.

---

## Part E. Align the links (lab computer)

Always before pedestals. It takes 20 to 40 s.

**E1.** Run the delay scan.

```bash
cd $SCRIPTS
mkdir -p $OUT/MuxA
STARTED=$(date +%s)
timeout 180 python3 delay_scan.py -d MuxA -i $KRIA_IP -o $OUT -I -f $CFG --pullerPort 6001
```

**E2.** Read the verdict.

```bash
python3 $MM/gate.py $OUT/MuxA --since $STARTED
```

Good: `GATE: PASS`, with all 6 DAQ and 12 trigger links aligned.

`GATE: FAIL` means bring the slot up again: Kria A1 to C3, then D3, E1, E2.

---

## Part F. Pedestal runs (lab computer)

**F1.** Take one pedestal first, as a unit test (about 30 s).

```bash
cd $SCRIPTS
PYTHONPATH=$PWD/analysis timeout 240 python3 -u pedestal_run.py -d MuxA_$LABEL -i $KRIA_IP -o $OUT -I -f $CFG --pullerPort 6001
```

**F2.** Find the run directory it wrote and copy the daq-server log into it.
That log holds the link header positions and is overwritten on every restart.

```bash
RUN=$(ls -td $OUT/MuxA_$LABEL/pedestal_run/run_* | head -1)
echo $RUN
ls $RUN/pedestal_run0.root
scp daq@$KRIA_IP:~/daq-server.log $RUN/daq-server.log
```

If `pedestal_run0.root` is missing, the run failed: restart the puller (D3)
and bring the slot up again from A1.

**F3.** Check the header positions. Every link at the same position is healthy.

```bash
grep 'header positions' $RUN/daq-server.log | tail -1
```

**F4.** Check the data: CRC pass rate and noise for each half of each chip.

```bash
python3 - $RUN <<'PY'
import sys, uproot
f = uproot.open(sys.argv[1] + "/pedestal_run0.root")
a = f["unpacker_data/hgcroc"].arrays(["chip", "half", "adc", "corruption"], library="np")
for c in sorted(set(a["chip"].tolist())):
    for h in (0, 1):
        m = (a["chip"] == c) & (a["half"] == h)
        if not m.sum():
            continue
        crc = ((a["corruption"][m].astype(int) & 2) == 0).mean()
        adc = a["adc"][m]
        print(f"chip {c} half {h}: CRC pass {crc:.3f}  adc {adc.mean():.1f} +- {adc.std():.2f}"
              + ("  FROZEN" if adc.std() == 0 else ""))
PY
```

Good: six lines, all `CRC pass 1.000`, none `FROZEN`, 10000 events.

**F5.** Make the hexmaps.

```bash
python3 $MM/hexmap_robust.py $RUN
```

The PNGs land in `$RUN`.

**F6.** If F1 to F5 look good, take the remaining pedestals. Repeat F1 to F5
four more times for 5 in total. Do not bring the slot up again between them.

---

## Next slot

Replace `A` with `B` (then `C`) in the slot commands in both terminals and
start again from A1 on the Kria and D2 on the lab computer. A3 switches the previous slot off,
so only one module is ever powered.

## When you are done

On the Kria:

```bash
pkill -f zmq_server
pkill -f '[d]aq-server'
sudo kconn_pwr off
```

On the lab computer:

```bash
pkill -f '[d]aq-client( -p 6001)?$'
```

Results are in `$RESULTS_DIR/<serial>/Mux<slot>_ldfull/pedestal_run/`, one
directory per run.

## If it fails

| you see | do |
|---|---|
| A6: `no ROCs` on every try, supply near 0 A | the module is not powered. Check the power lead into the power board and that the supply is on |
| A6: a different number of ROCs on each try | normal; go back to A1, up to 8 tries |
| A6: `retry 5/5` at the `[pwr]` step | the power board is not cabled, or its supply is off |
| A6 or B2: `Errno 5` on every try | power-cycle the Kria: `sudo shutdown -h now`, wait 20 s, press its power button, start again at A1 |
| B2: no `Board identification` after 3 restarts | back to A1 |
| E1 hangs, or stuck at `Initializing i2c sockets` | `KRIA_IP` is wrong, or the Kria firewall blocks 5555/6000 (quickstart step 3) |
| E2: `no summary.json` after a scan that ran | port 6001 closed on the lab computer, or 8888 on the Kria (quickstart steps 2 and 3) |
| E2: `GATE: FAIL` | bring the slot up again from A1 |
| F1 ends after 240 s with no `pedestal_run0.root` | restart the puller (D3), bring the slot up from A1, run E1 and E2 again |
| F4: some halves fail CRC or read `FROZEN` | bring the slot up again from A1 and repeat |
