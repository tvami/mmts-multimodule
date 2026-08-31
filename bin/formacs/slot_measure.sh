#!/usr/bin/env bash
# slot_measure.sh SLOT CFG LABEL [N] -- bring up, gate, N pedestals, decompose.
# One slot, one config, one number.
#
# Board type comes from the environment; the defaults are the LD partials:
#   SM_BOARD=LD-Semi  SM_EXPECT=2  SM_EXTPOWER=1   # partials, no power board
#   SM_BOARD=LD-Full  SM_EXPECT=3  SM_EXTPOWER=0   # LD Fulls, power board IN
#
# SM_EXTPOWER=0 is REQUIRED with the power distribution board fitted: the 0x27
# EN_Mx write is what powers the module and --external-power skips it.
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SLOT="${1:?slot}"; CFG="${2:?config}"; LABEL="${3:?label}"; N="${4:-5}"
BOARD="${SM_BOARD:-LD-Semi}"; EXPECT="${SM_EXPECT:-2}"
EXT=""; [ "${SM_EXTPOWER:-1}" = "1" ] && EXT="--external-power"

SERIAL="$(module_of "$SLOT")"
echo "# slot $SLOT board ${SERIAL:-UNKNOWN} label $LABEL  (--board $BOARD, expect $EXPECT ROCs${EXT:+, $EXT})"

# Bring up and scan until the gate PASSES. Alignment is a per-bring-up lottery
# and daq-server refuses START on any unaligned elink, so an ungated pedestal
# burns the full timeout per run. Retry the whole cycle instead.
for try in $(seq 1 "${SM_TRIES:-5}"); do
    ssh "$KRIA" "cd ~/multimodule && MMTS_FW=$MMTS_FW EXPECT_ROCS=$EXPECT \
        ~/up_verified.sh $SLOT $EXT --board $BOARD" | tail -1
    ssh "$KRIA" 'cut -d. -f1 /proc/uptime'

    gate=$("$HERE/delay_scan.sh" "$SLOT" "$CFG" | tail -4)
    echo "$gate"
    case "$gate" in *"GATE: PASS"*) break;; esac
    echo "  gate failed, retry $try/${SM_TRIES:-5}"
    [ "$try" = "${SM_TRIES:-5}" ] && { echo "ABORT: gate never passed"; exit 3; }
done

PED_BASECFG="$SCRIPTS/$CFG" PED_DUT="Mux${SLOT}_$LABEL" \
    PED_EXTPOWER="${SM_EXTPOWER:-1}" PED_BOARD="$BOARD" \
    "$HERE/ped_run.sh" "$SLOT" "$N" "$LABEL" 10000

OUT="$(outdir_for "$SLOT")"
python3 "$DEBUG/cm_analysis.py" "$OUT/Mux${SLOT}_$LABEL/pedestal_run/run_*" | tail -3
