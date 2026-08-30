##
# please run me from the hexactrl-sw directory:
# python debug_tools/align_link.py -t daq -l link0,link1 -d 100 -s 50
##
import os
from optparse import OptionParser
import uhal
import time

def get_comma_separated_args(option, opt, value, parser):
    setattr(parser.values, option.dest, value.split(','))
if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-s", "--bsise", dest="bsize",type=int,action="store",
                       help="size (in unit of 32 bit words) of bram to print out",default=1000)
    (options, args) = parser.parse_args()

    #if options.logLevel.find("ERROR")==0:
    #    uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    #elif options.logLevel.find("WARNING")==0:
    #    uhal.setLogLevelTo(uhal.LogLevel.WARNING)
    #elif options.logLevel.find("NOTICE")==0:
    #    uhal.setLogLevelTo(uhal.LogLevel.NOTICE)
    #elif options.logLevel.find("DEBUG")==0:
    #    uhal.setLogLevelTo(uhal.LogLevel.DEBUG)
    #elif options.logLevel.find("INFO")==0:
    #    uhal.setLogLevelTo(uhal.LogLevel.INFO)
    uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    
    man = uhal.ConnectionManager("file:///opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml")
    dev = man.getDevice("TOP")

    # configure fast control generator
    dev.getNode("fastcontrol.command.enable_fast_ctrl_stream").write(0x1)
    dev.getNode("fastcontrol.command.enable_orbit_sync").write(0x1)
    dev.getNode("fastcontrol.command.global_l1a_enable").write(0x1)
    # enable periodic L1A 
#    dev.getNode("fastcontrol.periodic0.enable").write(0x1)
#    dev.getNode("fastcontrol.periodic0.flavor").write(0x0)
#    dev.getNode("fastcontrol.periodic0.bx").write(1000)
#    dev.getNode("fastcontrol.periodic0.burst_length").write(0x1)
#
#    #configure Sync IO block
#    dev.getNode("ext_trig_IO_blocks.link0.reg0.delay_mode").write(0x1)
#    dev.getNode("ext_trig_IO_blocks.link1.reg0.delay_mode").write(0x1)
#    dev.getNode("ext_trig_IO_blocks.link2.reg0.delay_mode").write(0x1)
#    dev.getNode("ext_trig_IO_blocks.link3.reg0.delay_mode").write(0x1)
#    dev.getNode("ext_trig_IO_blocks.link4.reg0.delay_mode").write(0x1)
#    dev.getNode("ext_trig_IO_blocks.link5.reg0.delay_mode").write(0x1)
#    
#    # send reset to 6b8b encoder
#    dev.getNode("fastcontrol.request.link_reset_econt").write(0x1)
#
#    #configure clock source
#    dev.getNode("clk_FC_mux.clk_int_select").write(0x1)
#    dev.getNode("clk_FC_mux.FC_int_select").write(0x1)
#
#    print("External clk freq:", dev.getNode("clk_mon.rate0").read())
#    print("Sys 320 clk freq:", dev.getNode("clk_mon.rate1").read())
#    print("Sys 40 clk freq:", dev.getNode("clk_mon.rate2").read())
#    print("Sys 160 clk freq:", dev.getNode("clk_mon.rate3").read())
#    print("External clk lock:", dev.getNode("clk_mon.lock0").read())
#    print("Sys 320 clk lock:", dev.getNode("clk_mon.lock1").read())
#    print("Sys 40 clk lock:", dev.getNode("clk_mon.lock2").read())
#    print("Sys 160 clk lock:", dev.getNode("clk_mon.lock3").read())
#    print("External clk active:", dev.getNode("clk_FC_mux.clk_ext_active").read())
#    print("Internal clk select:", dev.getNode("clk_FC_mux.clk_int_select").read())
#    print("Internal cmd select:", dev.getNode("clk_FC_mux.FC_int_select").read())
#    print("clk40_ext_rate:", dev.getNode("clk_FC_mux.clk_ext_rate").read())
#    
#
#    dev.getNode("fastcontrol_recv.command.reset_counters_io").write(0x1)
#    
#    # read fast control counters
#    errors    = dev.getNode("fastcontrol_recv.counters.errors").read()
#    orbitSync = dev.getNode("fastcontrol_recv.counters.orbit_sync").read()
#    l1a       = dev.getNode("fastcontrol_recv.counters.l1a").read()
#
#    print(errors, orbitSync, l1a)
#
#    time.sleep(1)
#
    # read fast control counters
    errors    = dev.getNode("fastcontrol_recv.counters.errors").read()
    orbitSync = dev.getNode("fastcontrol_recv.counters.orbit_sync").read()
    l1a       = dev.getNode("fastcontrol_recv.counters.l1a").read()

    print(errors, orbitSync, l1a)
