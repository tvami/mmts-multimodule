##
# please run me from the hexactrl-sw directory:
# python debug_tools/align_link.py -t daq -l link0,link1 -d 100 -s 50
##
import os
from optparse import OptionParser
import uhal
import time
import sys

def getLinkSetting(linktype, settingName, link_name):
    return dev.getNode("link_capture_"+linktype+"."+link_name+"."+settingName).read()

def setLinkSetting(linktype, settingName, data, link_name):
    return dev.getNode("link_capture_"+linktype+"."+link_name+"."+settingName).write(data)

def printStatusLine(label, data, pf = "x"):
    sys.stdout.write("%25s: "%label)
    for datum in data:
        sys.stdout.write(("%10"+pf)%datum)
    sys.stdout.write("\n")
    
def printData(linktype):
    Nlinks = getLinkSetting(linktype, "num_links", "global")
    
    data = []
    for i in range(Nlinks):
        link_name = "link%i"%i
        fifoDepth = getLinkSetting(linktype, "fifo_occupancy", link_name)
        data.append(dev.getNode("bram_"+linktype+"."+link_name).readBlock(fifoDepth))

    print("\nData for link_capture_"+linktype)
    printStatusLine("Link", range(Nlinks), "d")
    print("-"*27+"-"*10*Nlinks)
    for i in range(len(data[0])):
        sys.stdout.write("%25d: "%i)
        for chan_data in data:
            sys.stdout.write("  %08x"%chan_data[i])
        sys.stdout.write("\n")
    
def printLinkSatus(linktype):
    variables = {
        "delay.mode"                : "x",
        "delay.idelay_error_offset" : "d",
        "delay.invert"              : "x",
        "delay.in"                  : "x",
        "delay_out"                 : "d",
        "delay_out_N"               : "d",
        "align_pattern"             : "x",
        "link_aligned_count"        : "d",
        "link_error_count"          : "d",
        "status.link_aligned"       : "x",
        "align_position"            : "d",
        "capture_mode_in"           : "x",
        "walign_state"              : "x",
        "acquire_lock"              : "x",
        "continuous_acquire"        : "x",
        "L1A_offset_or_BX"          : "d",
        "fifo_latency"              : "d",
        "aquire_length"             : "d",
        "total_length"              : "d",
        "fifo_occupancy"            : "d",
        "bit_align_errors"          : "d",
        "word_errors"               : "d",
    }
    
    Nlinks = getLinkSetting(linktype, "num_links", "global")

    results = {}

    for i in range(Nlinks):
        link_name = "link%i"%i

        for var in variables:
            if not var in results:
                results[var] = []
            results[var].append(getLinkSetting(linktype, var, link_name))

    print("Status for link_capture_"+linktype)
    printStatusLine("Link", range(Nlinks), "d")
    print("-"*27+"-"*10*Nlinks)
    for var, result in results.items():
        printStatusLine(var, result, variables[var])
        
def get_comma_separated_args(option, opt, value, parser):
    setattr(parser.values, option.dest, value.split(','))

def resetLinkErrCounters(linktype):

    Nlinks = getLinkSetting(linktype, "num_links", "global")
    includedModules = getLinkSetting(linktype, "modules_included", "global")

    for i in range(Nlinks):
        link_name = "link%i"%i

        setLinkSetting(linktype, "reset_counters", 1, link_name)

def alignLinks(linktype, invert):
    setLinkSetting(linktype, "align_on.linkReset_ROCt", 1, "global")
    
    # configure fast control generator
    dev.getNode("fastcontrol.command.enable_fast_ctrl_stream").write(0x1)
    dev.getNode("fastcontrol.command.enable_orbit_sync").write(0x0)
    dev.getNode("fastcontrol.command.global_l1a_enable").write(0x0)

    Nlinks = getLinkSetting(linktype, "num_links", "global")
    includedModules = getLinkSetting(linktype, "modules_included", "global")

    for i in range(Nlinks):
        link_name = "link%i"%i

        setLinkSetting(linktype, "explicit_resetb", 0, link_name)
        setLinkSetting(linktype, "delay.mode", 0, link_name)
        setLinkSetting(linktype, "delay.mode", 1, link_name)
        setLinkSetting(linktype, "delay.invert", 1 & (invert >> i), link_name)
        if (0x7 & (includedModules >> 2)) == 1:
            #roct
            setLinkSetting(linktype, "align_pattern", 0xaccccccc, link_name)
        elif (0x7 & (includedModules >> 2)) == 3:
            #econt
            setLinkSetting(linktype, "align_pattern", 0x122, link_name)
        elif (0x7 & (includedModules >> 2)) == 4:
            #econd
            setLinkSetting(linktype, "align_pattern", 0x122, link_name)
        else:
            #rocd
            setLinkSetting(linktype, "align_pattern", 0xaccccccc, link_name)

    time.sleep(0.001)

    if (0x7 & (includedModules >> 2)) == 1:
        dev.getNode("fastcontrol.request.link_reset_roct").write(1)
    elif (0x7 & (includedModules >> 2)) == 3:
        dev.getNode("fastcontrol.request.link_reset_econt").write(1)
    elif (0x7 & (includedModules >> 2)) == 4:
        dev.getNode("fastcontrol.request.link_reset_econd").write(1)
    else:
        dev.getNode("fastcontrol.request.link_reset_rocd").write(1)

    time.sleep(0.0010)

    setLinkSetting(linktype, "reset_counters", 1, link_name)

def captureAlignment(linktype, invert):

    Nlinks = getLinkSetting(linktype, "num_links", "global")
    includedModules = getLinkSetting(linktype, "modules_included", "global")
    
    captureDepth = 100
    
    alignLinks(linktype, invert)
    
    for i in range(Nlinks):
        link_name = "link%i"%i

        setLinkSetting(linktype, "total_length", captureDepth, link_name)
        setLinkSetting(linktype, "aquire_length", captureDepth, link_name)
        setLinkSetting(linktype, "capture_linkreset_ROCd", 1, link_name)
        setLinkSetting(linktype, "capture_linkreset_ROCt", 1, link_name)
        setLinkSetting(linktype, "capture_linkreset_ECONd", 1, link_name)
        setLinkSetting(linktype, "capture_linkreset_ECONt", 1, link_name)

        setLinkSetting(linktype, "capture_mode_in", 2, link_name)
        setLinkSetting(linktype, "L1A_offset_or_BX", 0, link_name)
        setLinkSetting(linktype, "fifo_latency", 0, link_name)

    time.sleep(0.001)
    
    setLinkSetting(linktype, "aquire", 1, "global")

    time.sleep(0.010)

    if (0x7 & (includedModules >> 2)) == 1:
        dev.getNode("fastcontrol.request.link_reset_roct").write(1)
    elif (0x7 & (includedModules >> 2)) == 3:
        dev.getNode("fastcontrol.request.link_reset_econt").write(1)
    elif (0x7 & (includedModules >> 2)) == 4:
        dev.getNode("fastcontrol.request.link_reset_econd").write(1)
    else:
        dev.getNode("fastcontrol.request.link_reset_rocd").write(1)

    time.sleep(0.010)

def captureBX0(linktype):

    setLinkSetting(linktype, "align_on.linkReset_ROCt", 0, "global")
    
    # configure fast control generator
    dev.getNode("fastcontrol.command.enable_fast_ctrl_stream").write(0x1)
    dev.getNode("fastcontrol.command.enable_orbit_sync").write(0x1)
    dev.getNode("fastcontrol.command.global_l1a_enable").write(0x0)

    Nlinks = getLinkSetting(linktype, "num_links", "global")

    captureDepth = 50
    
    for i in range(Nlinks):
        link_name = "link%i"%i

        setLinkSetting(linktype, "total_length", captureDepth, link_name)
        setLinkSetting(linktype, "aquire_length", captureDepth, link_name)

        setLinkSetting(linktype, "capture_mode_in", 1, link_name)
        setLinkSetting(linktype, "L1A_offset_or_BX", 0, link_name)
        setLinkSetting(linktype, "fifo_latency", 0, link_name)

    time.sleep(0.001)
    
    setLinkSetting(linktype, "aquire", 1, "global")

    time.sleep(0.010)

def captureImmediate(linktype):

    setLinkSetting(linktype, "align_on.linkReset_ROCt", 0, "global")
    
    # configure fast control generator
    dev.getNode("fastcontrol.command.enable_fast_ctrl_stream").write(0x1)
    dev.getNode("fastcontrol.command.enable_orbit_sync").write(0x0)
    dev.getNode("fastcontrol.command.global_l1a_enable").write(0x0)

    Nlinks = getLinkSetting(linktype, "num_links", "global")

    captureDepth = 50
    
    for i in range(Nlinks):
        link_name = "link%i"%i

        setLinkSetting(linktype, "total_length", captureDepth, link_name)
        setLinkSetting(linktype, "aquire_length", captureDepth, link_name)

        setLinkSetting(linktype, "capture_mode_in", 0, link_name)
        setLinkSetting(linktype, "L1A_offset_or_BX", 0, link_name)
        setLinkSetting(linktype, "fifo_latency", 0, link_name)

    time.sleep(0.001)
    
    setLinkSetting(linktype, "aquire", 1, "global")

    time.sleep(0.010)

def captureL1A(linktype):

    setLinkSetting(linktype, "align_on.linkReset_ROCt", 0, "global")
    
    # configure fast control generator
    dev.getNode("fastcontrol.command.enable_fast_ctrl_stream").write(0x1)
    dev.getNode("fastcontrol.command.enable_orbit_sync").write(0x1)
    dev.getNode("fastcontrol.command.global_l1a_enable").write(0x1)
    dev.getNode("fastcontrol.command.enable_block_sequencer").write(0x1)
    dev.getNode("fastcontrol.periodic0.enable").write(0x0)
    dev.getNode("fastcontrol.periodic0.bx").write(0x04)

    Nlinks = getLinkSetting(linktype, "num_links", "global")

    captureDepth = 100
    
    for i in range(Nlinks):
        link_name = "link%i"%i

        setLinkSetting(linktype, "total_length", captureDepth, link_name)
        setLinkSetting(linktype, "aquire_length", captureDepth, link_name)

        setLinkSetting(linktype, "capture_mode_in", 2, link_name)
        setLinkSetting(linktype, "capture_L1A", 1, link_name)
        setLinkSetting(linktype, "L1A_offset_or_BX", 0, link_name)
        setLinkSetting(linktype, "fifo_latency", 0, link_name)

    time.sleep(0.001)
    
    setLinkSetting(linktype, "aquire", 1, "global")
    dev.getNode("fastcontrol.periodic0.request").write(0x1)

    time.sleep(0.010)

    dev.getNode("fastcontrol.command.global_l1a_enable").write(0x0)
    dev.getNode("fastcontrol.command.enable_block_sequencer").write(0x1)
    dev.getNode("fastcontrol.periodic0.enable").write(0x0)

    
if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-p", "--loglevel", dest="logLevel",type=str,action="store",
                       help="uHAL verbosity level: ERROR, WARNING, NOTICE, DEBUG, INFO (defalut: ERROR)" ,default="ERROR")
    parser.add_option("-l", "--lc_type", dest="lc_type",type=str,action="store",
                       help="uHAL link capture block type (defalut: daq)" ,default="daq")
    parser.add_option("-s", "--status", dest="status",action="store_true",
                       help="Print link Status")
    parser.add_option("-r", "--resetErr", dest="resetErr",action="store_true",
                       help="Reset error counters")
    parser.add_option("-a", "--align", dest="align",action="store_true",
                       help="Align the links")
    parser.add_option("-i", "--captureimmediate", dest="captureImmediate",action="store_true",
                       help="Capture link data immedeatly")
    parser.add_option("-e", "--capturealign", dest="captureAlign",action="store_true",
                       help="Capture during link alignment")
    parser.add_option("-b", "--captureBX0", dest="cbx0",action="store_true",
                       help="Capture on BX0")
    parser.add_option("-t", "--captureL1A", dest="captureL1A",action="store_true",
                       help="Capture on L1A")
    parser.add_option("-d", "--printdata", dest="data",action="store_true",
                       help="Print data")
    parser.add_option("-n", "--invert", dest="invert",action="store", type=int, default=0,
                       help="Invert links")
    (options, args) = parser.parse_args()

    linktype = options.lc_type
    
    if options.logLevel.find("ERROR")==0:
        uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    elif options.logLevel.find("WARNING")==0:
        uhal.setLogLevelTo(uhal.LogLevel.WARNING)
    elif options.logLevel.find("NOTICE")==0:
        uhal.setLogLevelTo(uhal.LogLevel.NOTICE)
    elif options.logLevel.find("DEBUG")==0:
        uhal.setLogLevelTo(uhal.LogLevel.DEBUG)
    elif options.logLevel.find("INFO")==0:
        uhal.setLogLevelTo(uhal.LogLevel.INFO)
    
    man = uhal.ConnectionManager("file:///opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml")
    dev = man.getDevice("TOP_A")

    if(options.resetErr):
        resetLinkErrCounters(linktype)        

    if(options.captureAlign):
        captureAlignment(linktype, options.invert)
    elif(options.align):
        alignLinks(linktype, options.invert)

    if(options.cbx0):
        captureBX0(linktype)

    if(options.captureImmediate):
        captureImmediate(linktype)

    if(options.captureL1A):
        captureL1A(linktype)

    if(options.status):
        printLinkSatus(linktype)

    if(options.data):
        printData(linktype)
