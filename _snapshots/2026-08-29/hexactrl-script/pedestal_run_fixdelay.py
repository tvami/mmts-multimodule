"""Pedestal run that pauses between configure and start, so the DAQ link
IDELAYs can be programmed by hand.

🛑 UPDATE 2026-08-28: THIS SCRIPT'S PAUSE IS IN THE WRONG PLACE AND ITS
   PREMISE IS DISPROVED. Prefer scratchpad/delay_midrun.sh.

   * The pause sits between `configure` and `start`, but daq-server re-runs the
     FULL link alignment inside `start` (zmq_controler.py:242) -- so anything
     written during the pause is overwritten before a single event is taken.
     Proved by readback: programmed 63/227/61/292/144/350, read back
     36/6/37/264/125/4 with L1A_off=14 (the offset finder had run after us).
   * It also hardcodes log2_rand_bx_period = 0 -- the ~890 kHz overrun condition
     that pedestal_run.py:47 exists to avoid. Any result taken with this script
     is confounded by that too.
   * And the premise is dead: a CRC-scored sweep of all 512 taps found no
     sampling position at which links 0/1/4/9 yield valid data
     (RESULTS_2026-08-28 §4e). Delay is not the cause.

   scratchpad/delay_midrun.sh instead slows the L1A rate so the acquisition
   lasts ~16 s and writes the delays DURING it, which is the only window where
   they survive; the run then contains its own before/after control.

WHY THIS EXISTS (superseded -- see above)
---------------
daq-server leaves the DAQ links in automatic delay mode, and on the Alabama
bench its aligner settles on 8-tap eyes -- four of them parked at delay 3-5 --
while the delay scan measures 44-89 tap eyes at completely different positions
(centres 153/307/173/212/49/250 for links 0/1/4/5/8/9).  Sampling that close to
an edge corrupts occasional events, which inflates adc_stdd on chips 0 and 2
(9.7 and 27.7, against a robust width of ~3 ADC).

The links cannot simply be programmed beforehand: `initialize` re-runs the
alignment and overwrites anything set earlier, and skipping `-I` is not an
option -- daq-server then never leaves the 'created' state and `start` loops
forever.  So the delays have to be written in the window between the run's
configure and its start, which is what the pause below provides.

USAGE
  1. run this script; it configures, then waits for a sentinel file
  2. meanwhile, on kria4:
         source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
         cd ~/multimodule && python3 set_daq_delays.py TOP_B
  3. touch the sentinel file it names; acquisition proceeds immediately

Same arguments as pedestal_run.py, plus --sentinel (default /tmp/GO_ACQUIRE
inside the container -- put it on the bind mount so the host can create it).
"""
import datetime
import errno
import glob
import os
import sys
from time import sleep

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'analysis'))

import analysis.level0.pedestal_run_analysis as analyzer  # noqa: E402
import myinotifier  # noqa: E402
import util  # noqa: E402
import zmq_controler as zmqctrl  # noqa: E402


def wait_for(sentinel, timeout=600):
    print("\n" + "=" * 70)
    print("CONFIGURE DONE -- links are aligned by daq-server's own aligner now.")
    print("Program the delays on kria4, then release the acquisition with:")
    print("    touch %s" % sentinel)
    print("=" * 70 + "\n", flush=True)
    waited = 0.0
    while not os.path.exists(sentinel):
        sleep(0.2)
        waited += 0.2
        if waited > timeout:
            print("timed out waiting for %s -- acquiring anyway" % sentinel)
            return
    os.remove(sentinel)
    print("sentinel seen, acquiring", flush=True)


if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-d", "--dut", dest="dut")
    parser.add_option("-i", "--hexaIP", action="store", dest="hexaIP")
    parser.add_option("-f", "--configFile", default="./configs/init.yaml",
                      action="store", dest="configFile")
    parser.add_option("-o", "--odir", action="store", dest="odir",
                      default='./data')
    parser.add_option("--daqPort", action="store", dest="daqPort",
                      default='6000')
    parser.add_option("--i2cPort", action="store", dest="i2cPort",
                      default='5555')
    parser.add_option("--pullerPort", action="store", dest="pullerPort",
                      default='6001')
    parser.add_option("--sentinel", action="store", dest="sentinel",
                      default='/tmp/GO_ACQUIRE')
    parser.add_option("-I", "--initialize", default=False,
                      action="store_true", dest="initialize")
    (opt, args) = parser.parse_args()

    daqsocket = zmqctrl.daqController(opt.hexaIP, opt.daqPort, opt.configFile)
    clisocket = zmqctrl.daqController("localhost", opt.pullerPort,
                                      opt.configFile)
    i2csocket = zmqctrl.i2cController(opt.hexaIP, opt.i2cPort, opt.configFile)

    # -I is required: without it daq-server stays in 'created' and start loops.
    if opt.initialize:
        i2csocket.initialize()
        daqsocket.initialize()
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
    else:
        i2csocket.configure()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/pedestal_run/run_%s/" % (os.path.realpath(opt.odir),
                                           opt.dut, timestamp)
    try:
        os.makedirs(odir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    notifier = myinotifier.mylittleInotifier(odir=odir)
    notifier.start()

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "pedestal_run"
    clisocket.configure()
    daqsocket.yamlConfig['daq']['active_menu'] = 'randomL1A'
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['NEvents'] = 10000
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['log2_rand_bx_period'] = 0
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['bx_min'] = 45
    daqsocket.configure()

    util.saveFullConfig(odir=odir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
    util.saveMetaYaml(odir=odir, i2c=i2csocket, daq=daqsocket, runid=0,
                      testName="pedestal_run", keepRawData=1, chip_params={})

    # ---- the whole point of this script ----
    wait_for(opt.sentinel)

    util.acquire(daq=daqsocket, client=clisocket)
    notifier.stop()

    print("Pedestal run saved to: %s" % odir)
    print("Now unpack and analyse offline (see runbook 3.3).")
