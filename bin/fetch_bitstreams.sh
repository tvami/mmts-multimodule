#!/usr/bin/env bash
# Pull the finished firmware builds from uaf-2 to the Mac.
#
#   ./fetch_bitstreams.sh            # all four designs
#   ./fetch_bitstreams.sh rxeq2      # one variant (suffix, or "stock")
#
# Per design the CI 'prep' stage keeps: <design>.bit, device-tree/pl.dtbo,
# uHAL_xml/*.xml (+ modules/), *_summary.txt.  Same set here, so a variant can be
# installed on the Kria exactly like an RPM-delivered build.  Lands in
# firmware_builds/<date>/<design>/.
set -u
HOST=tvami@uaf-2.t2.ucsd.edu
SRC=/home/users/tvami/fwbuild   # each design built in its own copy: $SRC/hgc-test-systems-<design>/<design>/
DEST=/Users/blackmac/Docs/1Research/MMTS/firmware_builds/$(date +%Y%m%d)
BASE=multimodule-hd-tester-trophy-v3

case "${1:-all}" in
  all)   DESIGNS="$BASE $BASE-rxlp $BASE-rxeq2 $BASE-rxeq4" ;;
  stock) DESIGNS="$BASE" ;;
  *)     DESIGNS="$BASE-$1" ;;
esac

mkdir -p "$DEST"
for D in $DESIGNS; do
    echo "== $D"
    # a design with no .bit yet is simply reported, not an error
    if ! ssh "$HOST" "test -f $SRC/hgc-test-systems-$D/$D/$D.bit"; then
        echo "   no $D.bit on uaf-2 yet"
        continue
    fi
    mkdir -p "$DEST/$D"
    rsync -az -e ssh \
        --include="$D.bit" --include="$D.xsa" --include="device-tree/***" --include="uHAL_xml/***" \
        --include="*_summary.txt" --exclude="*" \
        "$HOST:$SRC/hgc-test-systems-$D/$D/" "$DEST/$D/"
    # Vivado's own routed timing report (the ./project report step failed on uaf-2)
    rsync -az -e ssh "$HOST:$SRC/hgc-test-systems-$D/$D/$D.runs/impl_1/" --include="*timing_summary_routed.rpt" --include="*_drc_routed.rpt" --exclude="*" "$DEST/$D/" 2>/dev/null
    ls -la "$DEST/$D" | grep -vE "^total|^d" | awk "{printf \"   %8.1f MB  %s\n\", \$5/1e6, \$NF}"
    grep -m1 -A6 "Design Timing Summary" "$DEST/$D"/*timing_summary_routed.rpt 2>/dev/null | grep -E "^ *-?[0-9]" | awk "{print \"   WNS \"\$1\"  WHS \"\$5\"  WPWS \"\$9\"  pw-fail endpoints \"\$11}"
done
echo "fetched to $DEST"
