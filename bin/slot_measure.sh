#!/usr/bin/env bash
# slot_measure.sh SLOT CFG LABEL [N] -- bring up, gate, N pedestals, decompose.
# The unit of work for the CM investigation: one slot, one config, one number.
set -u
SLOT="${1:?slot}"; CFG="${2:?config}"; LABEL="${3:?label}"; N="${4:-5}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
SERIAL=$(python3 "$ROOT/multimodule/bin/module_of.py" "$SLOT")
echo "# slot $SLOT board $SERIAL label $LABEL"

# Bring up and scan until the gate PASSES.  Alignment is a per-bring-up lottery,
# and daq-server refuses START on any unaligned elink: an ungated pedestal then
# burns the full 240 s timeout per run.  Retry the whole cycle instead.
for try in $(seq 1 "${SM_TRIES:-5}"); do
    ssh daq@10.116.24.180 "cd ~/multimodule && \
        MMTS_FW=multimodule-hd-tester-trophy-v3-rxeq4 EXPECT_ROCS=2 \
        ~/up_verified.sh $SLOT --external-power --board LD-Semi" | tail -1
    ssh daq@10.116.24.180 'cut -d. -f1 /proc/uptime'

    gate=$("$ROOT/multimodule/bin/delay_scan.sh" "$SLOT" "$CFG" | tail -4)
    echo "$gate"
    case "$gate" in *"GATE: PASS"*) break;; esac
    echo "  gate failed, retry $try/${SM_TRIES:-5}"
    [ "$try" = "${SM_TRIES:-5}" ] && { echo "ABORT: gate never passed"; exit 3; }
done

PED_BASECFG=$ROOT/multimodule/hexactrl-sw/hexactrl-script/$CFG \
    PED_DUT=Mux${SLOT}_$LABEL "$ROOT/multimodule/bin/ped_run.sh" "$SLOT" "$N" "$LABEL" 10000
docker exec daq bash -lc \
    "python3 $ROOT/multimodule/debug/cm_analysis.py '$ROOT/Results/alabama/$SERIAL/Mux${SLOT}_$LABEL/pedestal_run/run_*'" \
    | tail -3
