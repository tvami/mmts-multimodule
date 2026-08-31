#!/usr/bin/env bash
# ped_run.sh SLOT N [LABEL] [NEVENTS] -- N pedestal runs, scored by CRC.
#
# Scores unpacker_data/hgcroc.corruption bit 1, not runsummary/summary.corruption:
# the latter is blind to CRC, so halves reading 0.058 there can be failing CRC on
# 100 % of events.
#
# env knobs:
#   PED_CLPS="EN,ENpE,S"  inject the ROC CLPS driver settings into every roc_s*
#   PED_BRINGUP=1         fresh bring-up + i2c-server restart before EVERY run
#   PED_EXTPOWER=1        bring-up uses --external-power (bench-fed module).
#                         Required for LD partials; must stay 0 with a power
#                         distribution board fitted, or the module never powers.
#   PED_BOARD=LD-Semi     --board for the bring-up; required for anything that
#                         is not an LD Full
#   PED_BASECFG=...       base config (default the slot's _ped.yaml)
#   PED_DUT=...           output subdirectory name
#   PED_METHOD/PED_FIFO/PED_OFFSET   override the l1aOffsetFinder settings
#   PED_EXPECT="path=value[,...]"    verify against the run's hardware readback
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SLOT="${1:?slot A|B|C}"
N="${2:-1}"
LABEL="${3:-base}"
NEV="${4:-10000}"

BASECFG=${PED_BASECFG:-$SCRIPTS/configs/initLD-trophyV3-3b_mux${SLOT}_ped.yaml}

SERIAL="$(module_of "$SLOT")"
if [ -n "$SERIAL" ]; then
    OUT="$RESULTS/$SERIAL"; DUT=${PED_DUT:-Mux${SLOT}}
else
    OUT="$RESULTS";         DUT=${PED_DUT:-Mux${SLOT}_crc}
fi
MAXSECS=240

# Bring-up is a lottery: roughly half wedge partway and a clean re-run is the fix.
# up_verified.sh retries both lotteries and only returns 0 once the ROCs are
# enabled, the board identified, and 5555 and 6000 both listen.
bringup() {
    local ext=""
    [ "${PED_EXTPOWER:-0}" = "1" ] && ext="--external-power"
    ssh "$KRIA" "EXPECT_ROCS=$NROC ${MMTS_FW:+MMTS_FW=$MMTS_FW} \
        ~/up_verified.sh $SLOT $ext ${PED_BOARD:+--board $PED_BOARD}" \
        | tail -1 | grep -q '^READY'
}

# Per-half CRC pass rate and adc_mean. Both are needed: a half whose pedestal has
# been pushed off the bottom of the ADC range reads adc_mean 0 and then scores a
# healthy CRC rate, because an all-zero frame has no `1` bits for the link to drop.
crc_report() {
    python3 - "$1" <<'PY' 2>/dev/null | tail -1
import sys
import numpy as np
import uproot
d = sys.argv[1]
try:
    f = uproot.open(d + '/pedestal_run0.root')
    t = f['unpacker_data/hgcroc']
    a = t.arrays(['chip', 'half', 'corruption'], library='np')
    chip, half, code = a['chip'], a['half'], a['corruption'].astype('int64')
    s = f['runsummary/summary'].arrays(library='np')
    norm = s['channeltype'] == 0
    out, ped = [], []
    for c in sorted(set(chip.tolist())):
        for h in sorted(set(half.tolist())):
            m = (chip == c) & (half == h)
            n = int(m.sum())
            if not n:
                continue
            out.append('%.3f' % (((code[m] & 2) == 0).sum() / n))
            sm = norm & (s['chip'] == c) & (s['channel'] // 36 == h)
            mu = float(np.median(s['adc_mean'][sm])) if sm.sum() else -1
            ped.append('dead' if mu < 1 else '%.0f' % mu)
    bx = t.arrays(['bxcounter'], library='np')['bxcounter']
    print('%d %s | adc_mean %s | badBX %.3f'
          % (t.num_entries, ' '.join(out), ' '.join(ped), (bx > 3563).mean()))
except Exception as e:
    print('-1 READ-ERR %s' % e)
PY
}

# Read EN,ENpE,S back off roc_s0: the end-to-end check that a requested setting
# actually reached the silicon.
verify_clps() {
    ( cd "$SCRIPTS" && PYTHONPATH="$PWD:$PWD/analysis" \
        python3 - "$KRIA_IP" "$BASECFG" <<'PY' 2>/dev/null | tail -1
import sys
import zmq_controler as zmqctrl
i2c = zmqctrl.i2cController(sys.argv[1], '5555', sys.argv[2])
node = {'roc_s0': {'sc': {'Top': {0: {'EN': 0, 'ENpE': 0, 'S': 0}}}}}
b = i2c.read_config(node)['roc_s0']
t = b.get('sc', b)['Top'][0]
print('%d,%d,%d' % (t['EN'], t['ENpE'], t['S']))
PY
    )
}

# A config change only reaches the ROCs on a server's FIRST successful
# initialize, so any run that changes ROC registers needs a fresh bring-up.
[ -n "${PED_CLPS:-}" ] && PED_BRINGUP=${PED_BRINGUP:-1}

puller_alive || puller_restart || exit 1

# CLPS goes in after `BIAS_I_PLL_D: 63`, which occurs exactly once per Top block,
# so it lands at the right indent in every roc_s* with no yaml parser. Expected
# hit count is one per ROC, counted from the config rather than hardcoded.
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

echo "# slot $SLOT  board ${SERIAL:-UNKNOWN}  label=$LABEL  CLPS=${PED_CLPS:-<config default>}  bringup=${PED_BRINGUP:-0}  nev=$NEV  rocs=$NROC"
printf '%-5s %-9s %-41s %-32s %-7s %s\n' "run" "entries" \
    "CRC pass c0h0.. (${NROC} chips x 2 halves)" "adc_mean (dead = pedestal railed)" "badBX" "dir"
printf '%s\n' "------------------------------------------------------------------------------------------"

for i in $(seq 1 "$N"); do
  # A bring-up can leave a trigger e-link unaligned, and the ROC-type identify
  # can fail so the config never applies. Both are cured by another bring-up, so
  # retry the whole cycle rather than reporting a failed run.
  for try in $(seq 1 "${PED_TRIES:-4}"); do
    puller_alive || puller_restart || exit 1

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

    # No background watcher here. An earlier version killed the client as soon as
    # daq-server logged alignment refusals and killed healthy runs instead, via
    # orphaned watchers matching a reused PID. Pay the timeout.
    log=$(mktemp)
    ( cd "$SCRIPTS" \
      && PYTHONPATH="$PWD/analysis" \
         MMTS_L1A_LOG2PERIOD="${PED_L1A:-10}" \
         timeout "$MAXSECS" python3 -u pedestal_run.py -d "$DUT" -i "$KRIA_IP" \
             -o "$OUT" -I -f "$cfg" ) > "$log" 2>&1
    rc=$?

    dir=$(grep -o "$OUT/$DUT/pedestal_run/run_[0-9_]*" "$log" | head -1)
    rm -f "$log" "$SCRIPTS/$cfg"

    # A stale directory is the classic way to report yesterday's number.
    if [ -z "$dir" ] || [ ! -f "$dir/pedestal_run0.root" ]; then
        why=$(ssh "$KRIA" 'tail -40 ~/daq-server.log | grep -oE "elink [a-z_.0-9]+ is not aligned" | tail -1')
        printf '%-5s %s\n' "$i" "RUN-FAILED (rc=$rc) try $try/${PED_TRIES:-4} ${why:+-- $why}"

        # One or two unaligned links is the per-bring-up lottery and is worth
        # another cycle; all of them is a config fault that no retry will fix.
        nun=$(ssh "$KRIA" 'grep -oE "link_capture_trg\.link[0-9]+ is not aligned" ~/daq-server.log \
                            | sort -u | wc -l | tr -d " \n"')
        if [ "${nun:-0}" -ge 6 ]; then
            echo "ABORT: ${nun} distinct trigger e-links unaligned -- that is a config fault,"
            echo "       not the bring-up lottery.  Check in_inv_cmd_rx (v3C = 1, v3D = 0) and"
            echo "       that elinks_trg lists only links that carry a stream."
            exit 7
        fi
        # Not a puller restart on timeout: a cold client makes the next run
        # slower, which makes it time out too.
        [ "${PED_BRINGUP:-0}" = "1" ] && continue
        break
    fi
    if [ -n "${SEEN_DIR:-}" ] && [ "$dir" = "$SEEN_DIR" ]; then
        printf '%-5s %s\n' "$i" "STALE DIR $dir -- no new run appeared, aborting"
        exit 5
    fi
    SEEN_DIR=$dir

    # daq-server.log carries the offset finder's per-link header positions, the
    # BCR-spread measurement, and is overwritten on every restart. Nothing else
    # records it and it cannot be recovered from the root file.
    scp -q "$KRIA:~/daq-server.log" "$dir/daq-server.log" 2>/dev/null \
        || echo "     (warning: could not fetch daq-server.log)"

    # initial_full_config.yaml is a live hardware readback, so any override can
    # be confirmed against it. Guards the failure mode where every initialize
    # after the first silently leaves the ROCs on the previous run's config.
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
                "VOID: asked CLPS=$PED_CLPS, ROC holds $rb -- not applied, try $try/4"
            [ "${PED_BRINGUP:-0}" = "1" ] && continue
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
