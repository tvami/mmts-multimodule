#!/usr/bin/env bash
# Does the measured eye width depend on the TRANSMITTED PATTERN?
#
# The ROC sends IdleFrame (default 0xCCCCCCC) and the capture block aligns on
# align_pattern (default 0xACCCCCCC).  0xC = 1100, so the default idle is
# transition-rich and contains no isolated '1' in a long zero run -- exactly the
# pattern the payload failure needs and the idle never provides.
#
# Swap in a hostile idle (long zero runs) and re-measure the eye:
#   good links' eyes COLLAPSE too -> the eye measures ISI tolerance, and the
#                                    good/bad split is signal integrity
#   nothing moves                 -> eye width is structural, not pattern driven
set -u
SLOT="${1:-B}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
CFG=configs/initLD-trophyV3-3b_mux${SLOT}_ped.yaml
KRIA=daq@10.116.25.124

# idle nibbles -> full 32-bit align pattern is 0xA followed by the 7 nibbles
for pair in "0xCCCCCCC:0xACCCCCCC" "0x1111111:0xA1111111" "0x0F0F0F0:0xA0F0F0F0" "0x1000000:0xA1000000"; do
    IDLE="${pair%%:*}"; ALIGN="${pair##*:}"
    echo "===== IdleFrame $IDLE   align_pattern $ALIGN ====="
    docker exec daq bash -lc "cd $SCRIPTS
        export PYTHONPATH=\$PWD:\$PWD/analysis
        python3 -c \"
import zmq_controler as zmqctrl
i2c = zmqctrl.i2cController('10.116.25.124','5555','$CFG')
for r in ('roc_s0','roc_s1','roc_s2'):
    for h in (0,1):
        i2c.yamlConfig[r]['sc']['DigitalHalf'][h]['IdleFrame'] = $IDLE
i2c.configure()
print('   configured')
\"" 2>/dev/null | tail -1
    ssh "$KRIA" "source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh 2>/dev/null
        cd ~ && python3 - <<'PY'
import uhal
uhal.disableLogging()
hw = uhal.ConnectionManager('file:///opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml').getDevice('TOP_$SLOT')
for l in (0,1,4,5,8,9):
    hw.getNode('link_capture_daq.link%d.align_pattern'%l).write($ALIGN); hw.dispatch()
    hw.getNode('link_capture_daq.link%d.explicit_align'%l).write(1);     hw.dispatch()
import time; time.sleep(0.5)
out=[]
for l in (0,1,4,5,8,9):
    e=int(hw.getNode('link_capture_daq.link%d.delay_out_N'%l).read()); hw.dispatch()
    a=int(hw.getNode('link_capture_daq.link%d.status.link_aligned'%l).read()); hw.dispatch()
    out.append('L%d eye=%-3d al=%d'%(l,e,a))
print('   ' + '  '.join(out))
PY" 2>/dev/null | tail -1
done
echo "===== restoring defaults ====="
docker exec daq bash -lc "cd $SCRIPTS
    export PYTHONPATH=\$PWD:\$PWD/analysis
    python3 -c \"
import zmq_controler as zmqctrl
i2c = zmqctrl.i2cController('10.116.25.124','5555','$CFG')
i2c.configure()
print('   ROC config restored')
\"" 2>/dev/null | tail -1
ssh "$KRIA" "source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh 2>/dev/null
    cd ~ && python3 - <<'PY'
import uhal
uhal.disableLogging()
hw = uhal.ConnectionManager('file:///opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml').getDevice('TOP_$SLOT')
for l in (0,1,4,5,8,9):
    hw.getNode('link_capture_daq.link%d.align_pattern'%l).write(0xACCCCCCC); hw.dispatch()
    hw.getNode('link_capture_daq.link%d.explicit_align'%l).write(1); hw.dispatch()
print('   align_pattern restored to 0xACCCCCCC')
PY" 2>/dev/null | tail -1
