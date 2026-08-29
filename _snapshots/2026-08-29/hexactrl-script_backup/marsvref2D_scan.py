import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.vref2D_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict
import numpy as np

def scan(i2csocket, daqsocket, startvrefinv, stopvrefinv, nstepvrefinv, startvrefnoinv, stopvrefnoinv, nstepvrefnoinv, odir):
    testName = 'vref2D_scan_mars'
    vrefinvs = np.linspace( startvrefinv, stopvrefinv, nstepvrefinv )
    vrefnoinvs = np.linspace( startvrefnoinv, stopvrefnoinv, nstepvrefnoinv )
    vrefs = [ [int(inv),int(noinv)] for inv in vrefinvs for noinv in vrefnoinvs ]
    print(vrefs)

    index=0
    for vref in vrefs:
        vrefinv = vref[0]
        vrefnoinv = vref[1]
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ReferenceVoltage'][0]['Inv_vref']=vrefinv
                nestedConf[key]['sc']['ReferenceVoltage'][1]['Inv_vref']=vrefinv
                nestedConf[key]['sc']['ReferenceVoltage'][0]['Noinv_vref']=vrefnoinv
                nestedConf[key]['sc']['ReferenceVoltage'][1]['Noinv_vref']=vrefnoinv

        i2csocket.configure(yamlNode=nestedConf.to_dict())
        chip_params = {'Inv_vref' : vrefinv, 'Noinv_vref' : vrefnoinv}
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testName,keepRawData=0,
                          chip_params=chip_params)
        util.acquire_scan(daq=daqsocket)
        index=index+1
    return

def vref2D_scan(i2csocket,daqsocket, clisocket, basedir,device_name):
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
    odir = "%s/%s/vref2D_scan_mars/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)

    start_inv=0
    stop_inv=1000
    nstepinv=20

    start_noinv=0
    stop_noinv=500
    nstepnoinv=20

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "vref2D_scan_mars"
    clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
    clisocket.configure()

    daqsocket.yamlConfig['daq']['active_menu']='marsRndL1A'
    daqsocket.yamlConfig['daq']['menus']['marsRndL1A']['log2_rand_bx_period']=0
    daqsocket.yamlConfig['daq']['menus']['marsRndL1A']['bx_min']=45
    daqsocket.configure()

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)

    clisocket.start()
    scan(i2csocket, daqsocket, start_inv, stop_inv, nstepinv, start_noinv, stop_noinv, nstepnoinv, odir)
    while True:
        roots = glob.glob(odir+"/*.root")
        yamls = glob.glob(odir+"/*.yaml")
        if len(roots)>=len(yamls)-1:
            break
        sleep(0.1)
    clisocket.stop()

    try:
        analyzer2d = analyzer.vref2D_scan_analyzer(odir=odir,treename='mars/mars')
        files = glob.glob(odir+"/*.root")

        for f in files:
            analyzer2d.add(f)
    
        analyzer2d.mergeData()
        analyzer2d.makePlots()

        i2csocket.configure() # as the yaml has not been modified, we can return to the original config like that
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
    vref2D_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
