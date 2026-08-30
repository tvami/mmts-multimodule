#!/usr/bin/env bash
# slot_measure.sh SLOT CFG LABEL [N] -- bring up, gate, N pedestals, decompose.
# The unit of work for the CM investigation: one slot, one config, one number.
#
# Board type comes from the environment; the defaults are the LD PARTIALS
# (Left/Right/Bottom) that this bench ran through 2026-08-30:
#
#   SM_BOARD=LD-Semi   SM_EXPECT=2   SM_EXTPOWER=1      # partials, no power board
#   SM_BOARD=LD-Full   SM_EXPECT=3   SM_EXTPOWER=0      # LD Fulls, power board IN
#
# ⚠️ SM_EXTPOWER=0 is REQUIRED with the power distribution board fitted: the 0x27
# EN_Mx write is what powers the module, and --external-power skips it.  Passing
# --external-power with the board in means the module never comes up.
set -u
SLOT="${1:?slot}"; CFG="${2:?config}"; LABEL="${3:?label}"; N="${4:-5}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
BOARD="${SM_BOARD:-LD-Semi}"; EXPECT="${SM_EXPECT:-2}"
EXT=""; [ "${SM_EXTPOWER:-1}" = "1" ] && EXT="--external-power"
SERIAL=$(python3 "$ROOT/multimodule/bin/module_of.py" "$SLOT")
echo "# slot $SLOT board $SERIAL label $LABEL  (--board $BOARD, expect $EXPECT ROCs${EXT:+, $EXT})"

# Bring up and scan until the gate PASSES.  Alignment is a per-bring-up lottery,
# and daq-server refuses START on any unaligned elink: an ungated pedestal then
# burns the full 240 s timeout per run.  Retry the whole cycle instead.
for try in $(seq 1 "${SM_TRIES:-5}"); do
    ssh daq@10.116.24.180 "cd ~/multimodule && \
        MMTS_FW=multimodule-hd-tester-trophy-v3-rxeq4 EXPECT_ROCS=$EXPECT \
        ~/up_verified.sh $SLOT $EXT --board $BOARD" | tail -1
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
