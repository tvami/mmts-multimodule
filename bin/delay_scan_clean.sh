#!/usr/bin/env bash
# delay_scan_clean.sh SLOT [BOARD] [NTRIES]
#
# A delay scan whose ROC configuration is VERIFIED, not assumed.
#
# The 2026-08-28 HD Full scan had to be thrown away because its i2c initialize
# returned `could not identify ROC type from readBack [...]` -- the ROC-type
# mis-detect.  The scan still ran and still produced a full set of plots, so
# nothing in the output says the ROCs were never configured by that run.  This
# script retries the whole cycle until the initialize actually reports
# `ROC(s) CONFIGURED`, and refuses to report a result otherwise.
set -u

SLOT="${1:?slot A|B|C}"
BOARD="${2:-HD-Full}"
TRIES="${3:-4}"
CFG_IN="${4:-}"

ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
CFG=${CFG_IN:-configs/initHD-trophyV3_muxC_ped.yaml}
DUT=${PED_DUT:-MuxC_HD_Full}
RESULTS=$ROOT/Results/alabama
BIN=/opt/hexactrl/ROC3_dev_docker/bin
KRIA=daq@10.116.24.180
NROC=$(grep -c '^roc_s[0-9_]*:' "$SCRIPTS/$CFG")

# The puller container's main process is `daq-client & wait`: when daq-client
# dies the container exits 0 and delay_scan.py then dies silently at
# clisocket.configure(), leaving an EMPTY timestamped directory behind.  That is
# what killed the first attempt today, so re-create it every cycle.
fresh_puller() {
    docker rm -f daq >/dev/null 2>&1
    docker run -d --name daq --platform linux/amd64 -p 6001:6001 \
        -v "$ROOT:$ROOT" -w "$SCRIPTS" hexactrl-client:local \
        '/opt/hexactrl/${SUBPATH}/bin/daq-client & wait' >/dev/null || return 1
    sleep 6
}

for try in $(seq 1 "$TRIES"); do
    echo "=== cycle $try/$TRIES ==="

    # EXPECT_ROCS or up_verified.sh calls a partial enable READY.
    ssh "$KRIA" "EXPECT_ROCS=$NROC timeout 900 ~/up_verified.sh $SLOT --board $BOARD" \
        | tail -2 | grep -q '^READY' || { echo "  bring-up failed"; continue; }

    fresh_puller || { echo "  puller would not start"; continue; }

    log=$(mktemp)
    docker exec daq bash -lc "cd $SCRIPTS
        export PATH=$BIN:\$PATH
        export PYTHONPATH=\$PWD/analysis
        timeout 900 python3 -u delay_scan.py -d $DUT -i 10.116.24.180 \
            -o $RESULTS -I -f $CFG" > "$log" 2>&1

    # The whole point: only trust a scan whose ROCs were actually configured.
    if ! grep -q 'ROC(s) CONFIGURED' "$log"; then
        echo "  i2c initialize did NOT configure the ROCs:"
        grep -oE 'error: [^\\]*' "$log" | head -1 | sed 's/^/    /'
        rm -f "$log"; continue
    fi

    dir=$(grep -oE "$RESULTS/$DUT/delay_scan/[0-9_]+" "$log" | tail -1)
    rm -f "$log"
    if [ -z "$dir" ] || [ ! -f "$dir/summary.json" ]; then
        echo "  scan produced no summary.json"; continue
    fi

    echo "VERIFIED  $dir"
    python3 - "$dir/summary.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
def key(n):
    k, l = n.split('.'); return (k, int(l[4:]))
print('%-24s %6s %6s %6s %9s' % ('link', 'wmax', 'ngood', 'nbad', 'nturnon'))
for n in sorted(s, key=key):
    v = s[n]
    print('%-24s %6d %6d %6d %9d'
          % (n, v['wmax'], v['ngood'], v['nbad'], v['nturnon']))
PY
    exit 0
done

echo "FAILED: no cycle produced a scan with verified ROC configuration"
exit 1
