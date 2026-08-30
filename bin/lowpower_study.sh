#!/usr/bin/env bash
# lowpower_study.sh [CFG] -- bring up, configure, THEN start daq-server.
#
# Ordering is the whole point.  mmts_bringup.sh starts daq-server before any ROC
# configuration, and daq-server's clocking takes an HD Full straight to ~3 A --
# at or past what the bench supplies can give.  The RunL/RunR=0 "silence the
# chips we do not need" configs can therefore never take effect: the module is
# already at the ceiling before the config is written.
#
# So:  enableROCs -> i2c-server -> CONFIGURE (chips go quiet) -> daq-server.
#
# Measured ladder for reference (2026-08-28):
#     module off 0.08-0.39 A | powered idle 1.08 A | clocking ~2.97-3.23 A
set -u

ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
CFG="${1:-configs/initHD-trophyV3_muxC_run2.yaml}"
DUT="${PED_DUT:-MuxC_HD_lowpower}"
RESULTS=$ROOT/Results/alabama
BIN=/opt/hexactrl/ROC3_dev_docker/bin
KRIA=daq@10.116.24.180
NROC=$(grep -c '^roc_s[0-9_]*:' "$SCRIPTS/$CFG")

say() { echo; echo "=== $* ==="; }

# The first step cycles kconn_pwr.  An abort between the `off` and a
# successful bring-up used to leave the payload rail DOWN, and every later
# probe then reported "no ROCs" against an unpowered module -- which reads
# exactly like a dead board.  Never exit with the rail off.
restore_power() {
    # kconn_pwr on is not enough: `kconn_pwr off` also CLEARS the EN_Mx latch, so
    # the payload rail comes back with the module still switched off (0.00 A on a
    # supply that feeds only the module).  Re-assert EN_Mx as well.
    ssh "$KRIA" 'sudo kconn_pwr on >/dev/null 2>&1; sleep 4
                 sudo fw-loader load multimodule-hd-tester-trophy-v3 >/dev/null 2>&1; sleep 2
                 cd ~/multimodule && python3 modpower.py C on 2>&1 | tail -2' || true
}
trap restore_power EXIT

say "1/5 enableROCs only -- NO daq-server (module powered, idle: expect ~1.1 A)"
ssh "$KRIA" '
  pkill -f "[u]p_verified"; pkill -f "[m]mts_bringup"; pkill -f "[e]nableROCs"
  # [g]pioset, not gpioset: an unbracketed pattern matches THIS ssh command
  # line and pkill kills its own shell -- the ssh then returns non-zero and
  # the caller reports a bring-up failure having run nothing at all.
  pkill -f "[z]mq_server"; pkill -f "[d]aq-server"; pkill -f "[g]pioset -m signal -b"
  sleep 2
  # --recover does kconn_pwr off -> fw-loader -> kconn_pwr on and re-asserts
  # EN_Mx afterwards.  A hand-rolled cycle here left the module unpowered when
  # the script aborted, and WITHOUT --recover enableROCs dies in mux_board_gpio
  # with 5x [Errno 5]: the fw-loader reset alone does not clear that wedge.
  cd ~/multimodule
  for i in 1 2 3 4; do
      out=$(timeout 400 python3 enableROCs_alabama.py C --recover --board HD-Full 2>&1)
      echo "$out" | tail -1
      echo "$out" | grep -q "6 ROC(s) enabled" && ! echo "$out" | grep -q FAILED && exit 0
      echo "  try $i short of 6 ROCs, retrying"
  done
  exit 1' || { echo "ABORT: could not enable all 6 ROCs"; exit 1; }

say "2/5 i2c-server (still no daq-server)"
ssh "$KRIA" '~/start_i2c.sh C' 2>&1 | tail -4
ssh "$KRIA" 'grep -q "Board identification" ~/zmq_srvC.log' \
    || { echo "ABORT: i2c-server did not identify the board"; exit 1; }

say "3/5 CONFIGURE -- silences all but the kept chip.  READ THE CURRENT AFTER THIS"
docker rm -f daq >/dev/null 2>&1
docker run -d --name daq --platform linux/amd64 -p 6001:6001 \
    -v "$ROOT:$ROOT" -w "$SCRIPTS" hexactrl-client:local \
    '/opt/hexactrl/${SUBPATH}/bin/daq-client & wait' >/dev/null
sleep 6
docker exec daq bash -lc "cd $SCRIPTS
export PYTHONPATH=\$PWD:\$PWD/analysis
python3 -u -c \"
import zmq_controler as zmqctrl
i2c = zmqctrl.i2cController('10.116.24.180', '5555', '$CFG')
i2c.initialize()
print('i2c initialize done')
\"" 2>&1 | tail -3
ssh "$KRIA" 'grep -c Configured ~/zmq_srvC.log' | sed 's/^/    ROCs configured: /'

say "4/5 NOW start daq-server (only the kept chip should clock)"
ssh "$KRIA" 'set +u; source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
    setsid /opt/hexactrl/ROCv3-alper-dev/bin/daq-server \
      -f /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml \
      -p 6000 > ~/daq-server.log 2>&1 < /dev/null &
    sleep 4; ss -ltn | grep -c ":6000 "' | sed 's/^/    port 6000 listening: /'

say "5/5 delay scan (no -I: the ROCs are already configured, and a second"
echo "    initialize does a GPIO reset that would undo the silencing)"
docker exec daq bash -lc "cd $SCRIPTS
export PATH=$BIN:\$PATH
export PYTHONPATH=\$PWD/analysis
timeout 900 python3 -u delay_scan.py -d $DUT -i 10.116.24.180 \
    -o $RESULTS -f $CFG" 2>&1 | tail -6

dir=$(ls -dt "$RESULTS/$DUT/delay_scan/"* 2>/dev/null | head -1)
if [ -n "$dir" ] && [ -f "$dir/summary.json" ]; then
    echo; echo "=== eye widths: $dir ==="
    python3 - "$dir/summary.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
def key(n):
    k, l = n.split('.'); return (k, int(l[4:]))
print('%-24s %6s %6s %6s %9s' % ('link', 'wmax', 'ngood', 'nbad', 'nturnon'))
for n in sorted(s, key=key):
    v = s[n]
    print('%-24s %6d %6d %6d %9d' % (n, v['wmax'], v['ngood'], v['nbad'], v['nturnon']))
PY
else
    echo "no summary.json -- scan did not complete"
fi
