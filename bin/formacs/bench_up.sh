#!/usr/bin/env bash
# bench_up.sh SLOT [--board NAME] [--expect N] [--power-board]
#
# Bring the bench from "Kria just booted" to "module actually powered", in the
# only order that works.
#
# With the POWER DISTRIBUTION BOARD fitted (LD Fulls) pass --power-board: that
# drops --external-power so the 0x27 EN_Mx write happens, which is what powers
# the module. Only the ROC probe proves a module is alive.
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SLOT="${1:?usage: bench_up.sh A|B|C [--board NAME] [--expect N] [--power-board]}"; shift || true
BOARD="any"; EXPECT=""; EXT="--external-power"
while [ $# -gt 0 ]; do
    case "$1" in
        --board)       BOARD="$2"; shift 2 ;;
        --expect)      EXPECT="$2"; shift 2 ;;
        --power-board) EXT=""; shift ;;
        *) echo "unknown argument: $1"; exit 2 ;;
    esac
done

ssh -o ConnectTimeout=5 "$KRIA" true 2>/dev/null || {
    echo "Kria not reachable -- power it on first."; exit 1; }

echo "== 1/3  bitstream =="
ssh "$KRIA" "sudo kconn_pwr off; sudo fw-loader load $MMTS_FW 2>&1 | tail -1; sudo kconn_pwr on"

echo
echo "== 2/3  S*_PWR_EN  (the step that actually powers the module) =="
# No --recover: kconn_pwr and fw-loader were just done by hand above, and
# --recover would redo them. Plain is the default; there is no --no-recover flag.
out=$(ssh "$KRIA" "cd ~/multimodule && MMTS_FW=$MMTS_FW \
        python3 enableROCs_alabama.py $SLOT $EXT --board $BOARD 2>&1")
echo "$out" | tail -12

echo
echo "== 3/3  result =="
if grep -q "no ROCs" <<< "$out"; then
    echo "No ROCs. Check the loopback and the cables you last unplugged before"
    echo "spending more bring-ups. Do NOT re-probe repeatedly: reads on a dead"
    echo "bus wedge this I2C master and recovery is a mains cycle."
    exit 1
fi
got=$(grep -oE "[0-9]+ ROC\(s\) enabled" <<< "$out" | grep -oE "[0-9]+" | head -1)
echo "ROCs enabled: ${got:-0}${EXPECT:+ (expected $EXPECT)}"
[ -n "$EXPECT" ] && [ "${got:-0}" != "$EXPECT" ] && { echo "PARTIAL ENABLE -- not success, re-run."; exit 1; }
exit 0
