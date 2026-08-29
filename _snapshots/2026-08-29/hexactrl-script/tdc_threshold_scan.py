import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.tdc_threshold_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict
import numpy as np

# inv_vref scan
def scan(i2csocket, daqsocket, start, stop, nstep, odir):
    testName="tdc_threshold_scan"

    thresholds = np.linspace( start, stop, nstep ).astype(int)
    print(thresholds)

    index=0
    for threshold in thresholds:
        nestedConf = nested_dict()
        toa_threshold = int(threshold)
        tot_threshold = int(threshold)+100 #not sure we need to change it w.r.t toa_vref
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Toa_vref']=toa_threshold
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref']=tot_threshold
        # print(yaml.dump(nestedConf.to_dict()))
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        util.acquire_scan(daq=daqsocket)
        chip_params = { 'Toa_vref' : toa_threshold,
                        'Tot_vref' : tot_threshold }
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testName,keepRawData=0,
                          chip_params=chip_params)
        index=index+1
    return

def tdc_threshold_scan(i2csocket,daqsocket, clisocket, basedir,device_name, start=100, stop=500, nstep=41):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in pedestal_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return
        
    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in pedestal_run : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return

    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in pedestal_run : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/tdc_threshold_scan/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)

    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)

    clisocket.yamlConfig['global']['outputDirectory'] = odir
    clisocket.yamlConfig['global']['run_type'] = "tdc_threshold_scan"
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.configure()
    ## Random L1A
    daqsocket.yamlConfig['daq']['active_menu']='randomL1A'
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['NEvents']=1000
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['log2_rand_bx_period']=0
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['bx_min']=45
    daqsocket.configure()

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)

    clisocket.start()
    mylittlenotifier.start()
    scan(i2csocket, daqsocket, start, stop, nstep, odir)
    clisocket.stop()
    mylittlenotifier.stop()

    scan_analyzer = analyzer.tdc_threshold_scan_analyzer(odir=odir)
    files = glob.glob(odir+"/*.root")

    for f in files:
        scan_analyzer.add(f)
    
    scan_analyzer.mergeData()
    scan_analyzer.makePlots()

    i2csocket.configure() # as the yaml has not been modified, we can return to the original config like that
    return odir


if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    
    parser.add_option("-d", "--dut", dest="dut",
                      help="device under test")
    
    parser.add_option("-n", "--nchips", dest="nchips",type=int,default=1,
                      help="number of chips in the DUT")
    
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
    
    parser.add_option("-I", "--initialize",default=False,
                      action="store_true", dest="initialize",
                      help="set to re-initialize the ROCs and daq-server instead of only configuring")
    
    (options, args) = parser.parse_args()
    print(options)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    if options.initialize==True:
        i2csocket.initialize()
        daqsocket.initialize()
    else:
        i2csocket.configure()
    tdc_threshold_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
