import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.phase_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict

# phase scan
def scan(i2csocket, daqsocket, start, stop, step, odir):
    testName='phase_scan'

    index=0
    for phase in range(start,stop,step):
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['Top']['all']['phase_ck']=phase
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        i2csocket.resettdc()	# Reset MasterTDCs
        util.acquire_scan(daq=daqsocket)
        chip_params = {'Phase' : phase }
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testName,keepRawData=1,
                          chip_params=chip_params)
        index=index+1
    return

def phase_scan(i2csocket,daqsocket, clisocket, basedir,device_name,suffix="",logging_level='INFO'):
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
    if suffix:
        timestamp = timestamp + "_" + suffix
    odir = "%s/%s/phase_scan/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)

    start_val=0
    stop_val=16
    step_val=1

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "phase_scan"
    clisocket.configure()

    # ## Random L1A
    # daqsocket.enable_fast_commands(random=1)
    # daqsocket.l1a_settings(bx_spacing=45)
    # daqsocket.yamlConfig['daq']['NEvents']='500'
    # daqsocket.configure()

    daqsocket.yamlConfig['daq']['active_menu']='randomL1A'
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['NEvents']=1000
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['log2_rand_bx_period']=0
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['bx_min']=45
    daqsocket.configure()

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)

    mylittlenotifier.start()
    clisocket.start()
    scan(i2csocket, daqsocket, start_val, stop_val, step_val,odir)
    clisocket.stop()
    mylittlenotifier.stop()

    try:
        scan_analyzer = analyzer.phase_scan_analyzer(odir=odir)
        files = glob.glob(odir+"/*.root")
    
        for f in files:
	        scan_analyzer.add(f)
        scan_analyzer.mergeData()
        scan_analyzer.makePlots()
        scan_analyzer.addSummary()
        scan_analyzer.writeSummary()

        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['Top']['all']['phase_ck']=0
        i2csocket.configure(yamlNode=nestedConf.to_dict()) # configure back to Phase=0
        i2csocket.resettdc()
    except:
        with open(odir+"crash_report.log","w") as fout:
            fout.write("analysis went wrong and crash\n")

    return odir


if __name__ == "__main__":
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
    
    parser.add_option("-s", "--suffix",default="",
                      action="store", dest="suffix",
                      help="suffix")
    
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
    clisocket.yamlConfig['client']['serverIP'] = options.hexaIP
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    if options.initialize==True:
        i2csocket.initialize()
        daqsocket.initialize()
        clisocket.initialize()
    else:
        i2csocket.configure()

    phase_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,suffix="")
