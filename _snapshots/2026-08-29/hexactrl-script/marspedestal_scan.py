import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.pedestal_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict

# pedestal scan
def scan_pedDAC(i2csocket, daqsocket, start, stop, step, odir):
    testName='pedestal_scan_mars'
    
    index=0
    for ref_val in range(start,stop,step):
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ch']['all']['trim_inv']=ref_val
                nestedConf[key]['sc']['cm']['all']['trim_inv']=ref_val
                nestedConf[key]['sc']['calib']['all']['trim_inv']=ref_val
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        chip_params = {'trim_inv' : ref_val }
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testName,keepRawData=0,
                          chip_params=chip_params)
        util.acquire_scan(daq=daqsocket)
        index=index+1
    return

def pedestal_scan(i2csocket,daqsocket, clisocket, basedir,device_name,suffix=""):
    if type(i2csocket) != zmqctrl.i2cController:
	    print( "ERROR in pedestal_scan_mars : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
	    sleep(1)
	    return

    if type(daqsocket) != zmqctrl.daqController:
	    print( "ERROR in pedestal_scan_mars : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
	    sleep(1)
	    return

    if type(clisocket) != zmqctrl.daqController:
	    print( "ERROR in pedestal_scan_mars : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
	    sleep(1)
	    return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if suffix:
        timestamp = timestamp + "_" + suffix
    odir = "%s/%s/pedestal_scan_mars/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)

    start_val=0
    stop_val=64
    step_val=2

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "pedestal_scan_mars"
    clisocket.configure()
    daqsocket.yamlConfig['daq']['active_menu']='marsRndL1A'
    daqsocket.yamlConfig['daq']['menus']['marsRndL1A']['log2_rand_bx_period']=0
    daqsocket.yamlConfig['daq']['menus']['marsRndL1A']['bx_min']=45
    daqsocket.configure()

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
            
    clisocket.start()
    scan_pedDAC(i2csocket, daqsocket, start_val, stop_val, step_val,odir)
    while True:
        roots = glob.glob(odir+"/*.root")
        yamls = glob.glob(odir+"/*.yaml")
        if len(roots)==len(yamls)-1:
            break
        sleep(0.1)
    clisocket.stop()

    try:
        ped_analyzer = analyzer.pedestal_scan_analyzer(odir=odir,treename='mars/mars')
        files = glob.glob(odir+"/"+clisocket.yamlConfig['client']['run_type']+"*.root")
        for f in files:
	        ped_analyzer.add(f)
        ped_analyzer.mergeData()
        ped_analyzer.determine_pedDAC()
        # ped_analyzer.makePlots()
        ped_analyzer.addSummary()
        ped_analyzer.writeSummary()
    
        i2csocket.update_yamlConfig(fname=odir+'/trimmed_pedestal.yaml') #next step keeps the knowledge of what was changed
        i2csocket.configure(fname=odir+'/trimmed_pedestal.yaml')
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
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
    else:
        i2csocket.configure()
    pedestal_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,suffix="")
