#!/usr/bin/env bash
# trg_test.sh CFG [TRIES] -- bring up a subset config and report link alignment.
#
# Ordering: enableROCs -> i2c-server -> CONFIGURE (silences the unused chips)
# -> daq-server -> daq-side initialize (this is what runs the aligner).
# mmts_bringup.sh starts daq-server FIRST, which leaves the module at the supply
# ceiling before the silencing config can be written, so it is not used here.
#
# ⚠️  VERIFICATION HISTORY -- this script reported ">>> TRIGGER ALIGNED <<<"
# falsely TWICE on 2026-08-28, both times from grepping ~/daq-server.log:
#   1. the log contains binary bytes, so plain `grep` prints "binary file
#      matches" and NO match lines -- `| wc -l` counted 0 and read as success;
#   2. even with `grep -a`, a freshly started daq-server has an empty log and no
#      START has run, so "no unaligned errors" means "the aligner never ran".
# Alignment is therefore now read from status.link_aligned in the capture
# registers, which is positive evidence, and the run is refused unless the
# configure actually returned ROC(s) CONFIGURED.
set -u

CFG="${1:?config, relative to hexactrl-script/}"
TRIES="${2:-3}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
KRIA=daq@10.116.25.124

INV=$(grep -oE 'in_inv_cmd_rx: [01]' "$SCRIPTS/$CFG" | head -1 | grep -oE '[01]')
NRUN=$(grep -c 'RunL: 1' "$SCRIPTS/$CFG")
LINKS=$(grep -oE "name : 'link[0-9]+'" "$SCRIPTS/$CFG" | grep -oE '[0-9]+' | sort -nu | tr '\n' ' ')
echo "### $CFG"
echo "    in_inv_cmd_rx=$INV  chips_running=$NRUN  links=[$LINKS]"

for try in $(seq 1 "$TRIES"); do
    echo "--- cycle $try/$TRIES"

    ssh "$KRIA" 'cd ~/multimodule
      for i in 1 2 3 4; do
        out=$(timeout 400 python3 enableROCs_alabama.py C --recover --board HD-Full 2>&1)
        echo "    enableROCs try $i: $(echo "$out" | tail -1 | cut -c1-88)"
        echo "$out" | grep -q "6 ROC(s) enabled" && ! echo "$out" | grep -q FAILED && exit 0
      done
      exit 1' || { echo "    bring-up failed"; continue; }

    ssh "$KRIA" '~/start_i2c.sh C' 2>&1 | grep -qE "Board identification" \
        || { echo "    i2c-server did not identify the board"; continue; }

    docker rm -f daq >/dev/null 2>&1
    docker run -d --name daq --platform linux/amd64 -p 6001:6001 \
        -v "$ROOT:$ROOT" -w "$SCRIPTS" hexactrl-client:local \
        '/opt/hexactrl/${SUBPATH}/bin/daq-client & wait' >/dev/null
    sleep 6

    # The ROC-type mis-detect makes this fail while the run still looks fine, so
    # the result is refused unless CONFIGURED actually comes back.
    conf=$(docker exec daq bash -lc "cd $SCRIPTS
        export PYTHONPATH=\$PWD:\$PWD/analysis
        python3 -u -c \"
import zmq_controler as zmqctrl
zmqctrl.i2cController('10.116.25.124','5555','$CFG').initialize()
\"" 2>&1)
    if ! echo "$conf" | grep -q 'ROC(s) CONFIGURED'; then
        echo "    configure FAILED: $(echo "$conf" | grep -oE 'error: [^\\]*' | head -1)"
        continue
    fi
    # The supply cannot be read programmatically, and the configure -> daq-server
    # transition takes about a second, so the current reading was repeatedly
    # missed.  Hold here long enough to catch it.  PAUSE=0 to skip.
    echo "    ROC(s) CONFIGURED  <<< READ THE SUPPLY CURRENT NOW >>>"
    for t in $(seq "${PAUSE:-15}" -5 5); do printf "      %ss...\r" "$t"; sleep 5; done
    echo "      (continuing)          "

    ssh "$KRIA" 'set +u; source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
        setsid /opt/hexactrl/ROCv3-alper-dev/bin/daq-server \
          -f /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml \
          -p 6000 > ~/daq-server.log 2>&1 < /dev/null &
        sleep 5'
    docker exec daq bash -lc "cd $SCRIPTS
        export PYTHONPATH=\$PWD:\$PWD/analysis
        python3 -u -c \"
import zmq_controler as zmqctrl
d = zmqctrl.daqController('10.116.25.124','6000','$CFG'); d.initialize()
c = zmqctrl.daqController('localhost','6001','$CFG')
c.yamlConfig['client']['serverIP'] = d.ip; c.initialize()
\"" >/dev/null 2>&1

    echo
    echo "=== status.link_aligned (from the capture registers, not the log) ==="
    ssh "$KRIA" "source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh 2>/dev/null
                 timeout 180 python3 /home/daq/dump_links.py TOP_C" 2>&1 \
        | awk -v want="$LINKS" '
            /block=/ { blk = ($NF == "link_capture_daq") ? "daq" : "trg"; next }
            /^link[0-9]/ {
                n = substr($1, 5) + 0
                if (index(" " want " ", " " n " ")) printf "  %-4s link%-3d aligned=%d\n", blk, n, $2
            }'
    exit 0
done
echo "FAILED: no cycle produced a verified configure"
exit 1
