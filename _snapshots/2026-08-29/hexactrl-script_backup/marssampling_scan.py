import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep
from nested_dict import nested_dict

import myinotifier,util
import analysis.level0.sampling_scan_analysis as analyzer
import zmq_controler as zmqctrl

def scan(i2csocket, daqsocket, startBX, stopBX, stepBX, startPhase, stopPhase, stepPhase, injectedChannels, odir):
    testName='marssampling_scan'

    index=0
    for BX in range(startBX, stopBX, stepBX):
        daqsocket.yamlConfig['daq']['menus']['marsCalibAndL1A']['bxL1A']=BX
        daqsocket.configure()

        for phase in range(startPhase,stopPhase+1,stepPhase):
            nestedConf = nested_dict()
            for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                    nestedConf[key]['sc']['Top']['all']['phase_strobe']=15-phase
                    # nestedConf[key]['sc']['Top']['all']['phase_ck']=phase
            i2csocket.configure(yamlNode=nestedConf.to_dict())
            i2csocket.resettdc()	# Reset MasterTDCs

            chip_params = { 'BX' : BX-startBX, 'Phase' : phase }
            util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                              runid=index,testName=testName,keepRawData=0,
                              chip_params=chip_params)
            util.acquire_scan(daq=daqsocket)
            index=index+1
    return

def sampling_scan(i2csocket,daqsocket, clisocket, basedir,device_name, injectionConfig,suffix=""):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in marssampling_scan : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return

    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in marssampling_scan : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return

    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in marssampling_scan : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if suffix:
        timestamp = timestamp + "_" + suffix
    odir = "%s/%s/sampling_scan_mars/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)

    startPhase=0
    stopPhase=15
    stepPhase=1


    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "marssampling_scan"
    clisocket.configure()
    
    calibreq = 0x10
    bxoffset = 21
    startBX=calibreq+bxoffset
    stopBX=calibreq+bxoffset+4
    stepBX=1

    daqsocket.yamlConfig['daq']['active_menu']='marsCalibAndL1A'
    daqsocket.yamlConfig['daq']['menus']['marsCalibAndL1A']['bxCalib']=calibreq
    daqsocket.yamlConfig['daq']['menus']['marsCalibAndL1A']['prescale']=0
    daqsocket.yamlConfig['daq']['menus']['marsCalibAndL1A']['repeatOffset']=700

    print("gain = %i" %injectionConfig['gain'])
    print("calib = %i" %injectionConfig['calib'])
    gain = injectionConfig['gain'] # 0 for low range ; 1 for high range
    calib = injectionConfig['calib'] # 
    injectedChannels=injectionConfig['injectedChannels']

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)

    i2csocket.configure_injection(injectedChannels, activate=1, gain=gain, phase=0, calib_dac=calib)

    clisocket.start()
    scan(i2csocket=i2csocket, daqsocket=daqsocket, 
	     startBX=startBX, stopBX=stopBX, stepBX=stepBX, 
	     startPhase=startPhase, stopPhase=stopPhase, stepPhase=stepPhase, 
	     injectedChannels=injectedChannels, odir=odir)
    while True:
        roots = glob.glob(odir+"/*.root")
        yamls = glob.glob(odir+"/*.yaml")
        if len(roots)==len(yamls)-1:
            break
        sleep(0.1)
    clisocket.stop()

    try:
        scan_analyzer = analyzer.sampling_scan_analyzer(odir=odir,treename='mars/mars')
        files = glob.glob(odir+"/"+clisocket.yamlConfig['client']['run_type']+"*.root")
    
        for f in files:
	        scan_analyzer.add(f)
        scan_analyzer.mergeData()
        scan_analyzer.makePlots(injectedChannels)
        scan_analyzer.determine_bestPhase(injectedChannels)

        # return to no injection setting
        i2csocket.configure_injection(injectedChannels,activate=0,calib_dac=0,gain=0) # 14 is the best phase -> might need to extract it from analysis

        with open(odir+'/best_phase.yaml') as fin:
            cfg = yaml.safe_load(fin)
            i2csocket.configure(yamlNode=cfg)
            i2csocket.update_yamlConfig(yamlNode=cfg)
    except Exception as e:
        with open(odir+"crash_report.log","w") as fout:
            fout.write("mars samling scan analysis went wrong and crash\n")
            fout.write("Error {0}\n".format(str(e)))
        
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

    injectionConfig = {
        'gain' : 0,
        'calib' : 900,
        'injectedChannels' : [10,10+18,10+36,10+18+36]
    }
    sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,suffix="")
