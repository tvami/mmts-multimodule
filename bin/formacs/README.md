# `formacs/` — native versions of the bench scripts

The scripts in `bin/` run every client command through `docker exec` against a
`hexactrl-client` container. These are the same scripts with the container
removed: they call `daq-client`, `delay_scan.py`, `pedestal_run.py` and the
analyses directly on a client with hexactrl-sw installed natively.

Behaviour is otherwise unchanged: same gate, same retry loops, same CRC scoring,
same by-board output layout. Operating procedure is in
`../../../MMTS_MAC_INSTRUCTIONS.md`.

## Setup

Edit **`site.sh`** and nothing else. Every script sources it.

| variable | what |
|---|---|
| `MMTS_ROOT` | parent of `multimodule/`, where `Results/` is written |
| `KRIA_IP`, `KRIA_USER` | the hexacontroller |
| `HEXACTRL` | native hexactrl-sw prefix on the client |
| `MMTS_VENV` | virtualenv with uproot and friends; empty for system-wide |
| `MMTS_FW` | firmware design the bring-up loads |
| `RESULTS_DIR` | output root |

Any of them can also be overridden per invocation:

```bash
MMTS_FW=multimodule-hd-tester-trophy-v3 ./delay_scan.sh B
```

## Files

| file | what |
|---|---|
| `site.sh` | the only file you edit |
| `lib.sh` | shared setup, the puller, registry lookup. Sourced, not run |
| `bench_up.sh` | cold start: bitstream, payload power, ROC enable |
| `delay_scan.sh` | delay scan plus the PASS/FAIL gate. Run before every pedestal |
| `ped_run.sh` | N pedestal runs scored by CRC |
| `slot_measure.sh` | bring up, gate, N pedestals, common-mode decomposition |
| `remap_all.sh` | regenerate every hexmap under the results root |
| `puller.sh` | restart `daq-client` by hand |
| `gate.py` | read the newest delay scan and print the gate |
| `module_of.py` | serial of the board in a slot, from the registry |

## Typical session

```bash
cd multimodule/bin/formacs

./bench_up.sh B --board LD-Semi --expect 2
./delay_scan.sh B configs/initLD-RL-3b_muxB_ped.yaml     # must print GATE: PASS
PED_BASECFG=$MMTS_ROOT/multimodule/hexactrl-sw/hexactrl-script/configs/initLD-RL-3b_muxB_ped.yaml \
  ./ped_run.sh B 5 LRight 10000
```

Or the whole thing in one command:

```bash
./slot_measure.sh B configs/initLD-RL-3b_muxB_ped.yaml LRight 5
```

## Differences from `bin/`

- The puller is a process, not a container. `lib.sh` restarts `daq-client` and
  waits for it to bind 6001. The rule is unchanged: **once per run**, never
  reused, because a `daq-client` that saw a failed START silently produces data
  that decodes to nothing.
- `PATH` picks up the hexactrl `bin` from `lib.sh`, which is what stops the run
  failing with `unpack: command not found`. In `bin/` that came from the image.
- Site values come from `site.sh` rather than being hardcoded per script.
- `ped_run.sh` takes `PED_BOARD` and honours `PED_EXTPOWER` when it calls
  `up_verified.sh`, and `slot_measure.sh` passes both through, so a partial is
  brought up correctly by the same command that measures it.
