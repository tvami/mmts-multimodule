#!/usr/bin/env bash
# ============================================================================
# ped_matrix.sh -- the empirical test HANDOVER §5 asks for.
#
#   ./ped_matrix.sh SLOT "OFFSETS" N [METHOD] [NEVENTS]
#
#   ./ped_matrix.sh C "13 20" 6 manual      # settles 13-vs-20 on slot C
#   ./ped_matrix.sh C "13" 6 automatic      # settles manual-vs-automatic
#
# Runs N pedestals per configuration and reports PER-HALF-ROC corruption for
# every run, plus the per-configuration median of the six halves.
#
# Entry count is a GATE, never the success metric.  §1: a healthy total-entry
# count coexisted with 100 % broken lanes for two days.  But the converse also
# bites -- corruption is a fraction over the events that decoded, so a run that
# decoded 216 of 10000 reports near-zero corruption and looks perfect.  Runs
# below 90 % yield are rejected outright; the survivors are judged on corruption.
#
# In 'automatic' mode the offset column is the config's value, which the
# BX_or_L1A_OffsetFinder then overrides per link -- it is printed only to say
# which base config was used.
# ============================================================================
set -u

SLOT="${1:?slot A|B|C}"
OFFSETS="${2:-13 20}"
N="${3:-6}"
METHOD="${4:-manual}"
NEV="${5:-10000}"

ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
# PED_BASECFG lets a slot use a variant base.  The old _no6/_trgsafe configs are
# obsolete: slot A's stuck trigger link is redrawn every bring-up, so no fixed
# exclusion list helps, and the patched offset finder no longer refuses the slot.
BASECFG=${PED_BASECFG:-$SCRIPTS/configs/initLD-trophyV3-3b_mux${SLOT}.yaml}
DUT=${PED_DUT:-Mux${SLOT}_matrix}
RESULTS=$ROOT/Results/alabama
BIN=/opt/hexactrl/ROC3_dev_docker/bin
MAXSECS=240

fresh_puller() {
    docker rm -f daq >/dev/null 2>&1
    docker run -d --name daq --platform linux/amd64 -p 6001:6001 \
        -v "$ROOT:$ROOT" -w "$SCRIPTS" hexactrl-client:local \
        '/opt/hexactrl/${SUBPATH}/bin/daq-client & wait' >/dev/null || return 1
    sleep 5
}

# $1 = run dir, $2 = NEvents requested.  Prints "<events> <six corruption values>".
# The event count is not decoration: corruption is a fraction over the events that
# DECODED, so a run that decoded 215 of 10000 reports near-zero corruption and looks
# perfect (slot A, run_20260827_181231).  Caller rejects low-yield runs.
halves() {
    docker exec daq bash -lc "python3 -c \"
import uproot, numpy as np
try:
    f = uproot.open('$1/pedestal_run0.root')
    a = f['runsummary/summary'].arrays(library='np')
    nrows = len(a['chip'])
    nev = f['unpacker_data/hgcroc'].num_entries / max(nrows, 1)
    m = a['channeltype'] == 0
    print('%d ' % round(nev) + ' '.join(
        '%.3f' % np.median(a['corruption'][m & (a['chip']==c) & (a['channel']//36==h)])
        for c in (0,1,2) for h in (0,1)))
except Exception:
    print('-1 READ-ERR')
\"" 2>/dev/null | tail -1
}

docker ps --format '{{.Names}}' | grep -qx daq || fresh_puller

printf '%-6s %-4s  %-8s %-47s %s\n' "off" "run" "events" "per-half corruption c0h0..c2h1" "dir"
printf '%s\n' "---------------------------------------------------------------------------"

for off in $OFFSETS; do
    allvals=""
    for i in $(seq 1 "$N"); do
        cfg="configs/_matrix_${SLOT}_${off}.yaml"
        sed -e "s/    method: 'automatic'/    method: '${METHOD}'/" \
            -e "s/    L1A_offset_or_BX: 13/    L1A_offset_or_BX: ${off}/" \
            -e "s/      NEvents: 10000/      NEvents: ${NEV}/" \
            "$BASECFG" > "$SCRIPTS/$cfg"

        # No retry on a failed i2c initialize.  The ROC-type identify read fails
        # on every initialize after the first, but degrade_test.sh (2026-08-27)
        # showed the six per-half numbers are the same whether the leg reported
        # CONFIGURED or failed -- the ROCs keep the config the first successful
        # initialize gave them.  Retrying only tripled the cost of every run.
        log=$(mktemp)
        docker exec daq bash -lc "cd $SCRIPTS
            export PATH=$BIN:\$PATH
            export PYTHONPATH=\$PWD/analysis
            export MMTS_L1A_LOG2PERIOD=10
            timeout $MAXSECS python3 -u pedestal_run.py -d $DUT -i 10.116.24.180 \
                -o $RESULTS -I -f $cfg" > "$log" 2>&1
        rc=$?
        rm -f "$SCRIPTS/$cfg"

        # daqController.start() is bounded now (20 attempts), so the old destructive
        # spin is impossible; >=6 'configured' lines is just ONE refused START.  Only
        # an unbounded spin (an unpatched client) should abort the batch.
        spin=$(grep -c 'status after start cmd : configured' "$log" 2>/dev/null | head -1)
        if [ "${spin:-0}" -ge 50 ]; then
            printf '%-6s %-4s  %s\n' "$off" "$i" "ABORT: START spin -- slot needs re-bring-up"
            rm -f "$log"; fresh_puller; exit 3
        fi

        dir=$(grep -o "$RESULTS/$DUT/pedestal_run/run_[0-9_]*" "$log" | head -1)
        rm -f "$log"
        if [ -z "$dir" ] || [ ! -f "$dir/pedestal_run0.root" ]; then
            printf '%-6s %-4s  %s\n' "$off" "$i" "RUN-FAILED (rc=$rc)"
            [ $rc -eq 124 ] && fresh_puller
            continue
        fi

        out=$(halves "$dir" "$NEV")
        nev_got=${out%% *}
        res=${out#* }
        # Reject a low-yield run instead of reporting its flattering corruption.
        min_ev=$(( NEV * 90 / 100 ))
        if [ "$nev_got" -lt "$min_ev" ] 2>/dev/null; then
            printf '%-6s %-4s  %-47s %s\n' "$off" "$i" \
                   "LOW-YIELD: only $nev_got/$NEV events decoded -- REJECTED" \
                   "$(basename "$dir")"
            continue
        fi
        printf '%-6s %-4s  %-8s %-47s %s\n' "$off" "$i" "ev=$nev_got" "$res" "$(basename "$dir")"
        [ "$res" != "READ-ERR" ] && allvals="$allvals $res"
    done

    if [ -n "$allvals" ]; then
        echo "$allvals" | tr ' ' '\n' | grep -v '^$' | sort -n | \
        awk -v off="$off" '{v[NR]=$1}
             END{ med = (NR%2) ? v[(NR+1)/2] : (v[NR/2]+v[NR/2+1])/2;
                  good=0; for(i=1;i<=NR;i++) if (v[i] < 0.999) good++;
                  printf "  => offset %-4s median per-half corruption %.3f   halves below 1.0: %d/%d   best %.3f\n\n",
                         off, med, good, NR, v[1] }'
    fi
done
