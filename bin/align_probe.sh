#!/usr/bin/env bash
# align_probe.sh -- initialize + configure ONLY, then read the link registers.
#
# The state that matters is after daq-server has run its aligner but before any
# acquisition: that is when delay.mode should read 1 and delay_out should be the
# eye width.  A delay scan cannot answer this because it sweeps the IDELAYs in
# manual mode and leaves mode=0 / delay_out=511 behind as residue, and a dump
# straight after bring-up cannot answer it either because nothing is configured
# yet and every register reads 0.
set -u

ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
CFG=${1:-configs/initHD-trophyV3_muxC.yaml}
BIN=/opt/hexactrl/ROC3_dev_docker/bin
KRIA=daq@10.116.25.124

docker rm -f daq >/dev/null 2>&1
docker run -d --name daq --platform linux/amd64 -p 6001:6001 \
    -v "$ROOT:$ROOT" -w "$SCRIPTS" hexactrl-client:local \
    '/opt/hexactrl/${SUBPATH}/bin/daq-client & wait' >/dev/null || exit 1
sleep 6

docker exec daq bash -lc "cd $SCRIPTS
export PATH=$BIN:\$PATH
export PYTHONPATH=\$PWD:\$PWD/analysis
python3 -u - <<'PY'
import zmq_controler as zmqctrl
cfg = '$CFG'
i2c = zmqctrl.i2cController('10.116.25.124', '5555', cfg)
daq = zmqctrl.daqController('10.116.25.124', '6000', cfg)
cli = zmqctrl.daqController('localhost', '6001', cfg)
print('i2c initialize :', i2c.initialize())
print('daq initialize :', daq.initialize())
cli.yamlConfig['client']['serverIP'] = daq.ip
print('cli initialize :', cli.initialize())
daq.configure()
print('daq configured -- aligner has run')
PY"

echo "=== link registers after configure, before any acquisition ==="
ssh "$KRIA" 'source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh 2>/dev/null
             timeout 180 python3 /home/daq/dump_links.py TOP_C'
