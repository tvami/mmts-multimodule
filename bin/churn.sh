#!/usr/bin/env bash
# churn.sh SLOT N -- run N back-to-back bring-ups on SLOT, nothing else.
#
# The 2026-08-30 uptime test came back quiet (ACF1 +0.03 at 14.3 h), so the
# remaining suspect for the 4 kHz pickup is bring-up / kconn_pwr churn: every
# noisy measurement so far followed dozens of cycles.  This isolates the churn
# from the elapsed time -- N cycles take ~1.5 min each, so 12 cycles cost 18 min
# of wall clock, far short of the hours the uptime hypothesis needed.
set -u
SLOT="${1:?slot A|B|C}"
N="${2:-4}"
KRIA=daq@10.116.25.124
FW=${MMTS_FW:-multimodule-hd-tester-trophy-v3-rxeq4}
ROCS=${EXPECT_ROCS:-2}
BOARD=${PED_BOARD:-LD-Semi}

for i in $(seq 1 "$N"); do
    printf '%s cycle %2d/%s ' "$(date -u +%H:%M:%S)" "$i" "$N"
    ssh "$KRIA" "cd ~/multimodule && MMTS_FW=$FW EXPECT_ROCS=$ROCS \
        ~/up_verified.sh $SLOT --external-power --board $BOARD" 2>&1 | tail -1
done
echo "$(date -u +%H:%M:%S) done: $N cycles on slot $SLOT"
