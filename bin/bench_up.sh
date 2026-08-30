#!/usr/bin/env bash
# bench_up.sh SLOT [--board NAME] [--expect N]
#
# Bring the bench from "Kria just booted" to "module actually powered", in the
# only order that works, and say when the supply reading means anything.
#
# With the POWER DISTRIBUTION BOARD fitted (LD Fulls) pass --power-board: that
# drops --external-power so the 0x27 EN_Mx write happens.  Note the supply
# reading is meaningless in that configuration -- the Kria sources the node and
# 0 W is normal.  Only the ROC probe proves a module is alive.
#
# 🔑 THE TRAP THIS EXISTS TO PREVENT
# The bench supply does NOT switch the module on. On an --external-power setup it
# only presents a rail at the module input. The hexaboard's rail comes up when
# S1/S2/S3_PWR_EN (bits P12/P13/P14 of the TCAL6416 at 0x20 on the MUX BOARD) are
# driven high, and only enableROCs_alabama.py writes them.
#
#   kconn_pwr on   powers the mux board.  It does NOT assert S*_PWR_EN.
#   fw-loader load loads the bitstream.   It does NOT assert S*_PWR_EN.
#
# So after a boot, before any bring-up, the supply reads 0.00 A and that is
# CORRECT. It is not an open circuit, not a bad lead, not a wrong trophy.
# On 2026-08-30 this cost a round of bench teardown chasing a fault that did not
# exist: leads unscrewed, a module pulled, trophy and mezzanine schematics read.
set -u

SLOT="${1:?usage: bench_up.sh A|B|C [--board NAME] [--expect N] [--power-board]}"; shift || true
BOARD="any"; EXPECT=""; EXT="--external-power"
while [ $# -gt 0 ]; do
    case "$1" in
        --board)  BOARD="$2"; shift 2 ;;
        --expect) EXPECT="$2"; shift 2 ;;
        # power distribution board fitted: the 0x27 EN_Mx write is what powers
        # the module, and --external-power skips it.  Required for LD Fulls.
        --power-board) EXT=""; shift ;;
        *) echo "unknown argument: $1"; exit 2 ;;
    esac
done

KRIA=daq@10.116.24.180
FW=multimodule-hd-tester-trophy-v3-rxeq4

ssh -o ConnectTimeout=5 "$KRIA" true 2>/dev/null || {
    echo "Kria not reachable -- power it on first."; exit 1; }

echo "== 1/3  bitstream =="
ssh "$KRIA" "sudo kconn_pwr off; sudo fw-loader load $FW 2>&1 | tail -1; sudo kconn_pwr on"

echo
echo "== 2/3  S*_PWR_EN  (the step that actually powers the module) =="
# NOTE: no --recover.  We just did kconn_pwr/fw-loader by hand above, and
# --recover would redo it.  There is no --no-recover flag; plain is the default.
out=$(ssh "$KRIA" "cd ~/multimodule && MMTS_FW=$FW \
        python3 enableROCs_alabama.py $SLOT $EXT --board $BOARD 2>&1")
echo "$out" | tail -12

echo
echo "== 3/3  read the meter NOW =="
if [ -z "$EXT" ]; then
    echo "(power distribution board fitted: the supply reading is MEANINGLESS here."
    echo " The Kria sources that node and 0 W is normal.  Judge by the ROC probe.)"
fi
if grep -q "no ROCs" <<< "$out"; then
    cat <<'MSG'
No ROCs, but S*_PWR_EN IS asserted now, so the supply reading is meaningful at
last.  Read it:
  ~1.2 A per live module  -> power is fine, the fault is I2C/seating
  0.0 A                   -> now it really is an open circuit; check leads/pads
Do NOT re-probe repeatedly: reads on a dead bus wedge this I2C master and
recovery is a mains cycle.
MSG
    exit 1
fi
got=$(grep -oE "[0-9]+ ROC\(s\) enabled" <<< "$out" | grep -oE "[0-9]+" | head -1)
echo "ROCs enabled: ${got:-0}${EXPECT:+ (expected $EXPECT)}"
[ -n "$EXT" ] && echo "Supply should now read ~1.2 A per live module at 1.72 V."
[ -n "$EXPECT" ] && [ "${got:-0}" != "$EXPECT" ] && { echo "PARTIAL ENABLE -- not success, re-run."; exit 1; }
exit 0
