#!/usr/bin/env bash
# ============================================================================
# ped_run.sh -- pedestal runs scored by CRC, per PLAN_2026-08-28_chip0_corruption.md
#
#   ./ped_run.sh SLOT N [LABEL] [NEVENTS]
#
# Replaces ped_matrix.sh for this investigation.  The difference that matters:
# ped_matrix.sh reports `runsummary/summary.corruption`, which is BLIND TO CRC
# (runanalyzer.cc checks head/tail/Hamming only).  Halves reading 0.058 there
# fail CRC on 100 % of events.  This script scores
# `unpacker_data/hgcroc.corruption` bit 1 instead.  Bar: 99.2 % (LD Full slot C
# chip1half1).
#
# env knobs:
#   PED_CLPS="EN,ENpE,S"  inject the ROC CLPS driver settings into every roc_s*
#                         Top block, so they survive configure (enableROCs writes
#                         0xFF = 7,7,3 at bring-up but the run config overrides it)
#   PED_BRINGUP=1         fresh bring-up + i2c-server restart before EVERY run
#   PED_EXTPOWER=1        bring-up uses --external-power (bench-fed module).
#                         Default OFF: with 3x LD Full every slot runs through
#                         the power management board and the 0x27 EN_Mx step is
#                         REQUIRED, or bring-up finds no ROCs.
#   PED_BASECFG=...       base config (default the slot's _ped.yaml)
#   PED_DUT=...           output subdirectory name
#   PED_METHOD=...        l1aOffsetFinder method (default: leave the config alone)
#   PED_FIFO=n            manual fifo_latency for ALL daq links
#   PED_OFFSET=n          manual L1A_offset_or_BX for ALL daq links
#                         Motivated by the 2026-08-28 log capture: with
#                         method 'automatic' on slot C the finder splits the six
#                         links into header position 24 -> fifo_latency 0 and
#                         23 -> 1, and EVERY link it puts at latency 0 fails
#                         100 % of CRCs while both CRC-passing links are at 1.
# ============================================================================
set -u

SLOT="${1:?slot A|B|C}"
N="${2:-1}"
LABEL="${3:-base}"
NEV="${4:-10000}"

ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
BASECFG=${PED_BASECFG:-$SCRIPTS/configs/initLD-trophyV3-3b_mux${SLOT}_ped.yaml}

# Output is grouped BY BOARD, matching the hexmaps:
#   Results/alabama/<serial>/Mux<slot>/pedestal_run/run_<UTC>/
# The serial comes from Results/alabama/module_ids.json for this slot, now.
# With no registry entry (unknown board) it falls back to the flat old layout so
# nothing breaks.  PED_DUT still overrides the leaf name.
SERIAL=$(python3 "$ROOT/multimodule/bin/module_of.py" "$SLOT" 2>/dev/null)
if [ -n "$SERIAL" ]; then
    RESULTS=$ROOT/Results/alabama/$SERIAL
    DUT=${PED_DUT:-Mux${SLOT}}
else
    RESULTS=$ROOT/Results/alabama
    DUT=${PED_DUT:-Mux${SLOT}_crc}
fi
BIN=/opt/hexactrl/ROC3_dev_docker/bin
KRIA=daq@10.116.25.124
MAXSECS=240

fresh_puller() {
    docker rm -f daq >/dev/null 2>&1
    docker run -d --name daq --platform linux/amd64 -p 6001:6001 \
        -v "$ROOT:$ROOT" -w "$SCRIPTS" hexactrl-client:local \
        '/opt/hexactrl/${SUBPATH}/bin/daq-client & wait' >/dev/null || return 1
    sleep 5
}

# Bring-up is on the Kria and is a lottery -- roughly half wedge partway and a
# clean re-run is the fix (runbook 1.1).  Retry up to 5x, then give up loudly.
# ~/up_verified.sh retries BOTH bring-up lotteries (enableROCs wedging, and the
# i2c-server's mux discovery serving a partial map or dying) and only returns 0
# once 3 ROCs are enabled, the board identified, and 5555+6000 both listen.
# PED_BOARD is required for anything that is not an LD Full: enableROCs probes
# ROC_ADDR_SETS[LD-Full] by default, so on the HD Full it would enable 3 of the 6
# ROCs and Link.py would then identify the board as "V3 LD Full HB".
bringup() {
    local ext=""
    [ "${PED_EXTPOWER:-0}" = "1" ] && ext="--external-power"
    # EXPECT_ROCS or up_verified.sh defaults to 3 and calls a partial enable
    # READY -- which is how the first in_inv_cmd_rx test ran against 4 of 6 ROCs
    # and produced a meaningless answer.  NROC comes from the base config.
    # MMTS_FW=<dir> makes the bring-up's fw-loader reset load a variant bitstream
    # PED_MODULE: which power-board output feeds the module, when it is not the
    # slot's index.  Without it the default EN_Mx bit leaves the module unpowered
    # and every ROC probe comes back empty.
    ssh "$KRIA" "EXPECT_ROCS=$NROC ${MMTS_FW:+MMTS_FW=$MMTS_FW} ~/up_verified.sh $SLOT $ext ${PED_MODULE:+--module $PED_MODULE} ${PED_BOARD:+--board $PED_BOARD}" \
        | tail -1 | grep -q '^READY'
}

# Per-half CRC pass rate from the unpacker tree.  ntupler.cc packs an additive
# code into unpacker_data/hgcroc.corruption: +1 head, +2 CRC32, +4/8/16 Hamming,
# +32 tail.  Bit 1 (value 2) is the only one that means "the payload is wrong".
# Reports CRC pass AND adc_mean per half.  Both are needed: a half whose pedestal
# has been pushed off the bottom of the ADC range reads adc_mean 0 and then
# scores a HEALTHY CRC pass rate, because an all-zero frame has no `1` bits for
# the link to drop (seen 2026-08-28 at Inv_vref 500: c0h1 went 0.000 -> 0.438
# CRC with adc_mean 181 -> 0.00).  A CRC-only metric has the mirror-image blind
# spot of the CRC-blind summary metric.  `dead` marks any half at adc_mean ~0.
crc_report() {
    docker exec daq bash -lc "python3 -c \"
import uproot, numpy as np
try:
    f = uproot.open('$1/pedestal_run0.root')
    t = f['unpacker_data/hgcroc']
    a = t.arrays(['chip','half','corruption'], library='np')
    chip, half, code = a['chip'], a['half'], a['corruption'].astype('int64')
    s = f['runsummary/summary'].arrays(library='np')
    norm = s['channeltype'] == 0
    out, ped = [], []
    for c in sorted(set(chip.tolist())):
        for h in sorted(set(half.tolist())):
            m = (chip==c) & (half==h)
            n = int(m.sum())
            if not n: continue
            out.append('%.3f' % (((code[m] & 2) == 0).sum() / n))
            sm = norm & (s['chip']==c) & (s['channel']//36==h)
            mu = float(np.median(s['adc_mean'][sm])) if sm.sum() else -1
            ped.append('dead' if mu < 1 else '%.0f' % mu)
    bx = t.arrays(['bxcounter'], library='np')['bxcounter']
    print('%d %s | adc_mean %s | badBX %.3f'
          % (t.num_entries, ' '.join(out), ' '.join(ped), (bx > 3563).mean()))
except Exception as e:
    print('-1 READ-ERR %s' % e)
\"" 2>/dev/null | tail -1
}

# Read EN,ENpE,S back off roc_s0 as "EN,ENpE,S" -- the end-to-end check that a
# requested setting actually reached the silicon.
verify_clps() {
    docker exec daq bash -lc "cd $SCRIPTS
        export PYTHONPATH=\$PWD:\$PWD/analysis
        python3 -c \"
import zmq_controler as zmqctrl
i2c = zmqctrl.i2cController('10.116.25.124', '5555', '$BASECFG')
node = {'roc_s0': {'sc': {'Top': {0: {'EN': 0, 'ENpE': 0, 'S': 0}}}}}
b = i2c.read_config(node)['roc_s0']
t = b.get('sc', b)['Top'][0]
print('%d,%d,%d' % (t['EN'], t['ENpE'], t['S']))
\"" 2>/dev/null | tail -1
}

# A config change only reaches the ROCs on a server's FIRST successful
# initialize (§5), so any run that changes ROC registers needs a fresh
# bring-up + server restart.  Default it on rather than leave it to the caller.
[ -n "${PED_CLPS:-}" ] && PED_BRINGUP=${PED_BRINGUP:-1}

docker ps --format '{{.Names}}' | grep -qx daq || fresh_puller

# CLPS goes in AFTER `BIAS_I_PLL_D: 63`, which occurs exactly once per Top block
# and nowhere else -- so this lands at the right indent inside every roc_s* Top,
# with no yaml parser and no lost comments.  The expected hit count is one per
# ROC: 3 on an LD Full, 6 on an HD Full -- counted from the base config rather
# than hardcoded, or an HD run aborts on a correct injection.
# awk, not `sed a\`: BSD sed's append takes its text as a backslash-continued
# line and mangled the three-line insert into a no-op -- the run then executed at
# the bring-up values with nothing reporting a problem (plan rule 2).
NROC=$(grep -c '^roc_s[0-9_]*:' "$BASECFG")
inject() {
    if [ -z "${PED_CLPS:-}" ]; then cat; return; fi
    IFS=, read -r EN ENPE S <<< "$PED_CLPS"
    awk -v en="$EN" -v enpe="$ENPE" -v s="$S" -v want="$NROC" '
        {print}
        /^        BIAS_I_PLL_D: 63$/ {
            printf "        EN: %s\n        ENpE: %s\n        S: %s\n", en, enpe, s
            n++
        }
        END { if (n != want) print "INJECT-FAILED: hit " n+0 " Top blocks, expected " want > "/dev/stderr" }'
}

echo "# slot $SLOT  label=$LABEL  CLPS=${PED_CLPS:-<config default>}  bringup=${PED_BRINGUP:-0}  nev=$NEV  rocs=$NROC"
printf '%-5s %-9s %-41s %-32s %-7s %s\n' "run" "entries" \
    "CRC pass c0h0.. (${NROC} chips x 2 halves)" "adc_mean (dead = pedestal railed)" "badBX" "dir"
printf '%s\n' "------------------------------------------------------------------------------------------"

for i in $(seq 1 "$N"); do
  # A bring-up is a lottery in two independent ways: it can leave a trigger
  # e-link unaligned (daq-server then refuses START and the client sits until
  # the timeout), and the ROC-type identify can fail so the config never
  # applies (§5).  Both are cured by another bring-up, so retry the whole
  # bring-up+run cycle rather than reporting a failed run.
  for try in $(seq 1 "${PED_TRIES:-4}"); do
    # The puller container's main process is `daq-client & wait`, so if
    # daq-client dies the container exits 0 and every later `docker exec` in this
    # invocation returns 137.  Re-check per attempt, not just at startup.
    docker ps --format '{{.Names}}' | grep -qx daq || fresh_puller

    if [ "${PED_BRINGUP:-0}" = "1" ]; then
        bringup || { printf '%-5s %s\n' "$i" "BRINGUP-FAILED -- aborting"; exit 4; }
    fi

    cfg="configs/_crc_${SLOT}_${LABEL}.yaml"
    sed -e "s/      NEvents: 10000/      NEvents: ${NEV}/" \
        ${PED_METHOD:+-e "s/    method: 'automatic'/    method: '${PED_METHOD}'/"} \
        ${PED_FIFO:+-e "s/    fifo_latency: 0 #/    fifo_latency: ${PED_FIFO} #/"} \
        ${PED_OFFSET:+-e "s/    L1A_offset_or_BX: 13/    L1A_offset_or_BX: ${PED_OFFSET}/"} \
        "$BASECFG" | inject > "$SCRIPTS/$cfg"

    if [ -n "${PED_CLPS:-}" ]; then
        got=$(grep -c '^        ENpE: ' "$SCRIPTS/$cfg")
        [ "$got" = "$NROC" ] || { echo "ABORT: CLPS injected into $got/$NROC Top blocks"; exit 6; }
    fi

    # Rule 2: the config must be verified from the run's own initial_full_config.yaml,
    # not from what we wrote here -- pedestal_run.py silently overrides some keys.
    # daq-server refuses START unless every listed e-link aligns, and the client
    # then spins until the timeout.  It logs the refusal within a second, so
    # watch for it and kill the client instead of paying the full MAXSECS --
    # a stuck trigger link is a per-bring-up lottery and we retry a lot.
    base_unaligned=$(ssh "$KRIA" "grep -c 'is not aligned' ~/daq-server.log 2>/dev/null | tr -d ' \n'")
    base_unaligned=${base_unaligned:-0}

    # NO background watcher here.  An earlier version killed the client as soon as
    # daq-server logged three alignment refusals, to avoid paying the full
    # timeout on a stuck trigger link.  It killed healthy runs instead: each
    # loop iteration spawned a watcher, and an orphan from a previous iteration
    # would kill a later client whose PID had been reused (seen as rc=137 on runs
    # that were fine when re-run by hand).  Pay the timeout; it is only wrong
    # sometimes, whereas the watcher was wrong unpredictably.
    log=$(mktemp)
    docker exec daq bash -lc "cd $SCRIPTS
        export PATH=$BIN:\$PATH
        export PYTHONPATH=\$PWD/analysis
        export MMTS_L1A_LOG2PERIOD=${PED_L1A:-10}   # PED_L1A: log2 random L1A period in BX
        timeout $MAXSECS python3 -u pedestal_run.py -d $DUT -i 10.116.25.124 \
            -o $RESULTS -I -f $cfg" > "$log" 2>&1
    rc=$?

    dir=$(grep -o "$RESULTS/$DUT/pedestal_run/run_[0-9_]*" "$log" | head -1)
    rm -f "$log" "$SCRIPTS/$cfg"

    # Rule 3: a stale directory is the classic way to report yesterday's number.
    if [ -z "$dir" ] || [ ! -f "$dir/pedestal_run0.root" ]; then
        why=$(ssh "$KRIA" 'tail -40 ~/daq-server.log | grep -oE "elink [a-z_.0-9]+ is not aligned" | tail -1')
        printf '%-5s %s\n' "$i" "RUN-FAILED (rc=$rc) try $try/${PED_TRIES:-4} ${why:+-- $why}"

        # ABORT rather than retry when the whole trigger side is down.  One or
        # two unaligned links is the per-bring-up lottery and is worth another
        # cycle; ALL of them is a config fault (in_inv_cmd_rx is the documented
        # cause -- runbook: 1 -> 0 takes slot C from 0/12 to 6/12) and no number
        # of retries will fix it.  Retrying it cost 4x240 s on 2026-08-28.
        nun=$(ssh "$KRIA" 'grep -oE "link_capture_trg\.link[0-9]+ is not aligned" ~/daq-server.log \
                            | sort -u | wc -l | tr -d " \n"')
        if [ "${nun:-0}" -ge 6 ]; then
            echo "ABORT: ${nun} distinct trigger e-links unaligned -- that is a config fault,"
            echo "       not the bring-up lottery.  Check in_inv_cmd_rx (0 on this bench) and"
            echo "       that elinks_trg lists only links that carry a stream."
            exit 7
        fi
        # NOT fresh_puller on timeout: a cold container makes the next run
        # slower, which makes it time out too -- the self-sustaining failure
        # loop the 2026-08-27 handover paid for twice.
        [ "${PED_BRINGUP:-0}" = "1" ] && continue      # retry the whole cycle
        break
    fi
    if [ -n "${SEEN_DIR:-}" ] && [ "$dir" = "$SEEN_DIR" ]; then
        printf '%-5s %s\n' "$i" "STALE DIR $dir -- no new run appeared, aborting"
        exit 5
    fi
    SEEN_DIR=$dir

    # Step 1c: daq-server.log carries the offset finder's per-link header
    # positions -- the BCR-spread measurement -- and is overwritten on every
    # restart.  Nothing else records it, and it cannot be recovered from the
    # root file (only aligned links decode, so the spread is invisible there).
    scp -q "$KRIA:~/daq-server.log" "$dir/daq-server.log" 2>/dev/null \
        || echo "     (warning: could not fetch daq-server.log)"

    # 🛑 HANDOVER §5.  After the FIRST initialize of a server's life, the ROC-type
    # identify read returns [0, 253, 104] and the HexaBoard object is never
    # rebuilt -- so every later `initialize` fails while port 5555 keeps
    # listening and the ROCs silently retain the PREVIOUS run's config.  The run
    # completes and reports a perfectly plausible number for a setting that was
    # never applied.  Read the CLPS back from the hardware and void the row
    # unless it is what we asked for.
    # Generic check: initial_full_config.yaml is a LIVE hardware readback
    # (util.py saveFullConfig -> i2c.read_config()), so any override can be
    # confirmed against it.  PED_EXPECT="path=value[,path=value...]" using the
    # same dotted paths as mkcfg.py.
    if [ -n "${PED_EXPECT:-}" ]; then
        bad=$(python3 - "$dir/initial_full_config.yaml" "$PED_EXPECT" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
bad = []
for item in sys.argv[2].split(','):
    path, want = item.split('=')
    node = cfg
    try:
        for k in path.split('.'):
            node = node[int(k) if k.lstrip('-').isdigit() else k]
    except (KeyError, TypeError):
        bad.append(f'{path}=<missing>'); continue
    if str(node) != want:
        bad.append(f'{path}={node} (wanted {want})')
print(';'.join(bad))
PY
)
        if [ -n "$bad" ]; then
            printf '%-5s %s\n' "$i" "VOID: ROC readback disagrees -- $bad"
            [ "${PED_BRINGUP:-0}" = "1" ] && continue
            break
        fi
    fi

    if [ -n "${PED_CLPS:-}" ]; then
        rb=$(verify_clps)
        if [ "$rb" != "${PED_CLPS}" ]; then
            printf '%-5s %s\n' "$i" \
                "VOID: asked CLPS=$PED_CLPS, ROC holds $rb -- not applied (§5), try $try/4"
            [ "${PED_BRINGUP:-0}" = "1" ] && continue   # a fresh server may take it
            break
        fi
    fi

    out=$(crc_report "$dir")
    printf '%-5s %-9s %-41s %-32s %-7s %s\n' "$i" "${out%% *}" \
        "$(echo "$out" | sed 's/^[^ ]* //; s/ | adc_mean.*//')" \
        "$(echo "$out" | sed 's/.*| adc_mean //; s/ | badBX.*//')" \
        "$(echo "$out" | sed 's/.*badBX //')" "$(basename "$dir")"
    break
  done
done
