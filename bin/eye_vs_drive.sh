#!/usr/bin/env bash
# Does the measured EYE WIDTH respond to the ROC's e-link drive strength?
#
# WHY THIS AND NOT CRC: CRC pass is saturated at 0.000 on the failing links, so
# it cannot show partial improvement -- which is why every knob tested looked
# equally dead.  delay_out_N (the aligner's own eye width, per the address table)
# is continuous and can show partial response.
#
# WHAT IT DISCRIMINATES:
#   eyes OPEN with more ROC drive  -> analog amplitude on the link/trace (hardware)
#   eyes PINNED at 8 regardless    -> FPGA side (placement/routing/deserialiser)
#
# Uses `configure` (not `initialize`), which rewrites ROC registers without
# hitting the "config only applies on the first initialize" trap, then forces
# re-alignment so the eye is re-measured.  Whole loop is seconds per point.
set -u
SLOT="${1:-B}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
CFG=configs/initLD-trophyV3-3b_mux${SLOT}_ped.yaml
KRIA=daq@10.116.25.124

for clps in "7,7,3" "7,0,3" "5,7,3" "3,7,3" "1,7,3" "0,0,0"; do
    IFS=, read -r EN ENPE S <<< "$clps"
    echo "===== CLPS EN=$EN ENpE=$ENPE S=$S ====="
    docker exec daq bash -lc "cd $SCRIPTS
        export PYTHONPATH=\$PWD:\$PWD/analysis
        python3 -c \"
import zmq_controler as zmqctrl, yaml
i2c = zmqctrl.i2cController('10.116.25.124','5555','$CFG')
for r in ('roc_s0','roc_s1','roc_s2'):
    i2c.yamlConfig[r]['sc']['Top'][0]['EN']   = $EN
    i2c.yamlConfig[r]['sc']['Top'][0]['ENpE'] = $ENPE
    i2c.yamlConfig[r]['sc']['Top'][0]['S']    = $S
i2c.configure()
b = i2c.read_config({'roc_s0':{'sc':{'Top':{0:{'EN':0,'ENpE':0,'S':0}}}}})['roc_s0']
t = b.get('sc', b)['Top'][0]
print('   readback EN=%d ENpE=%d S=%d' % (t['EN'], t['ENpE'], t['S']))
\"" 2>/dev/null | tail -2
    sleep 1
    ssh "$KRIA" "source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh 2>/dev/null
                 cd ~ && python3 eye_map.py TOP_$SLOT --align" 2>/dev/null \
        | sed -n '3,9p'
done
