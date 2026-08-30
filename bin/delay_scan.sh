#!/usr/bin/env bash
# delay_scan.sh SLOT [CONFIG]
#
# Delay scan with the same by-board output layout as the pedestals and hexmaps:
#   Results/alabama/<serial>/Mux<slot>/delay_scan/<UTC timestamp>/
# The serial comes from Results/alabama/module_ids.json for this slot, now; with
# no registry entry it falls back to the flat Results/alabama/Mux<slot> layout.
#
# Always run this BEFORE a pedestal (instructions, "Order"): it is seconds, and a
# pedestal on an unaligned slot costs a 240 s timeout per run and can take
# daq-server down.  Gate: every listed DAQ and trigger link must read ngood > 0.
set -u
SLOT="${1:?slot A|B|C}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
CFG="${2:-configs/initLD-trophyV3-3b_mux${SLOT}_ped.yaml}"

SERIAL=$(python3 "$ROOT/multimodule/bin/module_of.py" "$SLOT" 2>/dev/null)
if [ -n "$SERIAL" ]; then
    OUTDIR=$ROOT/Results/alabama/$SERIAL
    DUT=Mux${SLOT}
else
    OUTDIR=$ROOT/Results/alabama
    DUT=Mux${SLOT}
fi
echo "# slot $SLOT  board ${SERIAL:-UNKNOWN}  config $CFG"

docker rm -f daq >/dev/null 2>&1
docker run -d --name daq --platform linux/amd64 -p 6001:6001 \
    -v "$ROOT:$ROOT" -w "$SCRIPTS" hexactrl-client:local \
    '/opt/hexactrl/${SUBPATH}/bin/daq-client & wait' >/dev/null || exit 1
sleep 5

docker exec daq bash -lc \
    "python3 delay_scan.py -d $DUT -i 10.116.24.180 -o $OUTDIR -I -f $CFG" \
    >/dev/null 2>&1

python3 - "$OUTDIR/$DUT" <<'EOF'
import json, glob, os, sys
paths = sorted(glob.glob(sys.argv[1] + "/delay_scan/*/summary.json"))
if not paths:
    sys.exit("no summary.json -- the scan did not produce output")
d = paths[-1]
s = json.load(open(d))
print(os.path.dirname(d))
bad = 0
for kind in ("daq", "trg"):
    ks = [k for k in s if kind in k]
    ok = sum(1 for k in ks if s[k]["ngood"] > 0)
    bad += len(ks) - ok
    print(f"  {kind}: {ok}/{len(ks)}  " +
          " ".join(f"{k.split('.')[-1]}={s[k]['ngood']}" for k in ks))
print("GATE: PASS -- safe to run pedestals" if bad == 0 else
      f"GATE: FAIL -- {bad} link(s) at ngood 0; daq-server will refuse START")
EOF
