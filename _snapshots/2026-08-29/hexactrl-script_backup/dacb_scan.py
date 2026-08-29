#!/usr/bin/python
import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep, time
import pandas as pd
import myinotifier,util
import dacb_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict
from pedestal_run import pedestal_run
from pedestal_scan import pedestal_scan
from pprint import pprint

# dacb scan
def scan(i2csocket, daqsocket, start, stop, step, odir, chtype = 'cm', channels = '1,3'):
    testName = 'dacb_scan'

    index = 0
    # scan over dacb values 
    Sign_dac = 0
    for dacb in range(start, stop, step):
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s') == 0:
                nestedConf[key]['sc'][chtype][channels]['Dacb'] = dacb
                nestedConf[key]['sc'][chtype][channels]['Sign_dac'] = Sign_dac
       
        i2csocket.update_yamlConfig(yamlNode = nestedConf.to_dict())
        i2csocket.configure()
        
        util.acquire_scan(daq = daqsocket)

        chip_params = {'Dacb': dacb, 'Sign_dac': Sign_dac}
        #chip_params = {}
        util.saveMetaYaml(odir = odir, i2c = i2csocket, daq = daqsocket,
                          runid = index, testName = testName, keepRawData = 1,
                          chip_params = chip_params)
        index = index + 1
    return

def dacb_scan(i2csocket, daqsocket, clisocket, basedir, device_name, Gain_conv = 10):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in dacb_scan : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return

    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in dacb_scan : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return

    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in dacb_scan : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return
    # Do a pedestal run to acquire target pedestals
    indir = pedestal_run(i2csocket, daqsocket, clisocket, basedir, device_name)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/dacb_scan/run_%s/" % (os.path.realpath(basedir), device_name, timestamp) 
    os.makedirs(odir)

    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()

    clisocket.yamlConfig['global']['outputDirectory'] = odir
    clisocket.yamlConfig['global']['run_type'] = "dacb_scan"
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.configure()

    daqsocket.enable_fast_commands(random = 1)
    daqsocket.l1a_settings(bx_spacing = 45)
    daqsocket.yamlConfig['daq']['NEvents'] = '500'
    daqsocket.configure()

    i2csocket.yamlConfig['roc_s0']['sc']['GlobalAnalog']['all']['Gain_conv'] = Gain_conv
    i2csocket.configure()

    # Save initial configuration
    util.saveFullConfig(odir = odir, i2c = i2csocket, daq = daqsocket, cli = clisocket)

    # Scan over dacb of CM channels
    clisocket.start()
    
    start_cm_dacb = 0
    stop_cm_dacb = 64 # maximum value is 63
    step_cm_dacb = 1
    scan(i2csocket, daqsocket, start_cm_dacb, stop_cm_dacb, step_cm_dacb, odir, 'cm', '1,3')

    clisocket.stop()
    mylittlenotifier.stop()
    
    # Find and set the best CM dacb values
    dacb_cm_analyzer = analyzer.dacb_scan_analyzer(odir = odir)
    files = glob.glob(odir + "/*.root")
    for f in files:
        dacb_cm_analyzer.add(f)
    dacb_cm_analyzer.mergeData()
    dacb_cm_analyzer.retrieve_ped(indir)
    dacb_cm_analyzer.determine_DACb(channeltype = 100, Gain_conv = Gain_conv)
    dacb_cm_analyzer.makePlots()

    i2csocket.update_yamlConfig(fname = odir + '/trimmed_dacb.yaml') # next step keeps the knowledge of what was changed
    i2csocket.configure(fname = odir + '/trimmed_dacb.yaml')
 
    # Scan over dacb of normal channels 
    clisocket.configure()
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()
    clisocket.start()

    start_ch_dacb = 0
    stop_ch_dacb = 64 # maximum value is 63
    step_ch_dacb = 1
    scan(i2csocket, daqsocket, start_ch_dacb, stop_ch_dacb, step_ch_dacb, odir, 'ch', 'all')

    clisocket.stop()
    mylittlenotifier.stop()
    
    # Find and set the best normal ch dacb values
    dacb_ch_analyzer = analyzer.dacb_scan_analyzer(odir = odir)
    files = glob.glob(odir + "/*.root")
    for f in files:
        dacb_ch_analyzer.add(f)
    dacb_ch_analyzer.mergeData()
    dacb_ch_analyzer.retrieve_ped(indir)
    dacb_ch_analyzer.determine_DACb(channeltype = 0, Gain_conv = Gain_conv)
    dacb_ch_analyzer.makePlots()
    
    i2csocket.update_yamlConfig(fname = odir + '/trimmed_dacb.yaml') # next step keeps the knowledge of what was changed
    i2csocket.configure(fname = odir + '/trimmed_dacb.yaml')

    # Put Gain_conv back to 0 
    i2csocket.yamlConfig['roc_s0']['sc']['GlobalAnalog']['all']['Gain_conv'] = 0
    i2csocket.configure()

def main():
    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option("-d", "--dut", dest="dut",
                      help="device under test")

    parser.add_option("-i", "--hexaIP",
                      action="store", dest="hexaIP",
                      help="IP address of the zynq on the hexactrl board")

    parser.add_option("-f", "--configFile",default="./configs/init.yaml",
                      action="store", dest="configFile",
                      help="initial configuration yaml file")

    parser.add_option("-o", "--odir",
                      action="store", dest="odir",default='./data',
                      help="output base directory")

    parser.add_option("--daqPort",
                      action="store", dest="daqPort",default='6000',
                      help="port of the zynq waiting for daq config and commands (configure/start/stop/is_done)")

    parser.add_option("--i2cPort",
                      action="store", dest="i2cPort",default='5555',
                      help="port of the zynq waiting for I2C config and commands (initialize/configure/read_pwr,read/measadc)")

    parser.add_option("--pullerPort",
                      action="store", dest="pullerPort",default='6001',
                      help="port of the client PC (loccalhost for the moment) waiting for daq config and commands (configure/start/stop)")


    (options, args) = parser.parse_args()
    print(options)

    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)

    i2csocket.configure()
    pedestal_scan(i2csocket, daqsocket, clisocket, options.odir, options.dut)
    dacb_scan(i2csocket, daqsocket, clisocket, options.odir, options.dut, Gain_conv = 5)
    
    print('Finished dacb_scan')
    print(yaml.dump(i2csocket.read_config()))

    pedestal_run(i2csocket, daqsocket, clisocket, options.odir, options.dut)

if __name__ == "__main__":
    main()


