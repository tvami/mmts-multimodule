#!/usr/bin/env bash
# delay_scan.sh SLOT [CONFIG] -- scan, then print the PASS/FAIL gate.
#
# Always run this BEFORE a pedestal. It takes seconds and is harmless when it
# fails; a pedestal on an unaligned slot costs a 240 s timeout per run and can
# take daq-server and the puller down with it.
#
# Output: <results>/<serial>/Mux<slot>/delay_scan/<UTC>/ when the registry knows
# the board, else the flat <results>/Mux<slot>/.
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SLOT="${1:?usage: delay_scan.sh A|B|C [config]}"
CFG="${2:-configs/initLD-trophyV3-3b_mux${SLOT}_ped.yaml}"

SERIAL="$(module_of "$SLOT")"
OUTDIR="$(outdir_for "$SLOT")"
DUT="Mux${SLOT}"
echo "# slot $SLOT  board ${SERIAL:-UNKNOWN}  config $CFG"

puller_restart || exit 1

( cd "$SCRIPTS" && python3 delay_scan.py -d "$DUT" -i "$KRIA_IP" \
    -o "$OUTDIR" -I -f "$CFG" ) >/dev/null 2>&1

python3 "$HERE/gate.py" "$OUTDIR/$DUT"
