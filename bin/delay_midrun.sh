#!/usr/bin/env bash
# Program the DAQ IDELAYs DURING an acquisition, so the run contains its own control.
#
# WHY: the delays cannot be set before acquisition -- daq-server re-runs the full
# link alignment inside `start` (zmq_controler.py:242), which is the last thing
# before data flows, so pedestal_run_fixdelay.py's pause is too early and its
# writes are overwritten (proved 2026-08-28).  Instead: slow the L1A rate so the
# acquisition lasts ~16 s, then write the delays partway through.  Events before
# the write are the control, events after are the test -- same run, same
# bring-up, same configure.
#
#   ./delay_midrun.sh SLOT "0:63 1:227 4:61 5:292 8:144 9:350" [LOG2PERIOD] [LABEL]
set -u
SLOT="${1:?slot}"; DELAYS="${2:?delays}"; PERIOD="${3:-16}"; LABEL="${4:-midrun}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
KRIA=daq@10.116.25.124
DUT=Mux${SLOT}_${LABEL}

log=$(mktemp)
docker exec daq bash -lc "cd $SCRIPTS
    export PATH=/opt/hexactrl/ROC3_dev_docker/bin:\$PATH
    export PYTHONPATH=\$PWD/analysis
    export MMTS_L1A_LOG2PERIOD=$PERIOD
    timeout 400 python3 -u pedestal_run.py -d $DUT -i 10.116.25.124 \
        -o $ROOT/Results/alabama -I -f configs/initLD-trophyV3-3b_mux${SLOT}_ped.yaml" > "$log" 2>&1 &
client=$!

# wait for the acquisition to actually be running, then write the delays
for _ in $(seq 1 400); do
    grep -q 'status after start cmd : running' "$log" && break
    kill -0 $client 2>/dev/null || break
    sleep 0.25
done
if grep -q 'status after start cmd : running' "$log"; then
    echo "[$(date +%T)] acquisition running -- programming delays"
    ssh "$KRIA" "source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh 2>/dev/null
                 cd ~/multimodule && python3 set_daq_delays.py TOP_$SLOT $DELAYS" 2>&1 | tail -7
    echo "[$(date +%T)] delays written"
else
    echo "never reached 'running'"
fi
wait $client
dir=$(grep -o "$ROOT/Results/alabama/$DUT/pedestal_run/run_[0-9_]*" "$log" | head -1)
echo "run dir: $dir"
echo "--- delays as left after the run ---"
ssh "$KRIA" 'source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh 2>/dev/null; cd ~ && python3 dump_links.py TOP_'"$SLOT"' 2>&1 | tail -7'
rm -f "$log"
