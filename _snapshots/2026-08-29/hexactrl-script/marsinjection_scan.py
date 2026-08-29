import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep
from time import time

import myinotifier,util
import analysis.level0.injection_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict

def scan(i2csocket, daqsocket, injectedChannels, calib_vals, gain, odir, testname):
    index=0

    # pre-configure the injection
    configtime=0
    runtime=0
    
    start = time()
    nestedConf = nested_dict()
    update = lambda conf, chtype, channel, Range, val : conf[chtype][channel].update({Range:val})
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest'] = 1
            if gain==2:
                [update(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',1) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                [update(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',1) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
            elif gain==1:
                [update(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',1) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                [update(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',0) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
            elif gain==0:
                [update(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',0) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                [update(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',1) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
            else:
                pass
    i2csocket.configure(yamlNode=nestedConf.to_dict())
    end = time()
    configtime = configtime + (start-end)
    
    # scanning calDAC values:
    updateCalDAC = lambda conf,val: conf['sc']['ReferenceVoltage']['all'].update({'Calib':val})
    for calibDAC_val in calib_vals:
        start = time()
        nestedConf = nested_dict()
        [ updateCalDAC(nestedConf[key],calibDAC_val) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        end = time()
        configtime = configtime + (start-end)
        chip_params = { 'Inj_gain':gain, 'Calib':calibDAC_val, 'injectedChannels':injectedChannels['ch'] }
        start = time()
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testname,keepRawData=0,
                          chip_params=chip_params)
        util.acquire_scan(daq=daqsocket)
        index+=1
        end = time()
        runtime = runtime + (start-end)

    start = time()
    nestedConf = nested_dict()
    [nestedConf[key]['sc']['ReferenceVoltage']['all'].update({'IntCtest':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
    [nestedConf[key]['sc']['ReferenceVoltage']['all'].update({'Calib':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
    [update(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',0) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
    [update(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',0) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
    i2csocket.configure(yamlNode=nestedConf.to_dict())
    end = time()
    configtime = configtime + (start-end)
    print("Elapsed config time = {0}".format(configtime))
    print("Elapsed start time = {0}".format(runtime))
    return

def injection_scan(i2csocket,daqsocket,clisocket,basedir,device_name,injectionConfig):
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
    
    testname = "injection_scan_mars"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/%s/run_%s/"%( os.path.realpath(basedir), device_name, testname, timestamp ) # a comlete path is needed
    os.makedirs(odir)
        
    calibreqA            = 0x10
    phase				= injectionConfig['phase'] if 'phase' in injectionConfig.keys() else -1
    BXoffset			= injectionConfig['BXoffset']
    calib     			= injectionConfig['calib']
    injectedChannels	= injectionConfig['injectedChannels']
    gain 				= injectionConfig['gain'] # 0 for low range ; 1 for high range
    toa_vref            = injectionConfig['toa_vref'] if 'toa_vref' in injectionConfig.keys() else -1
    tot_vref            = injectionConfig['tot_vref'] if 'tot_vref' in injectionConfig.keys() else -1
    
    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = testname
    clisocket.configure()
    
    daqsocket.yamlConfig['daq']['active_menu']='marsCalibAndL1A'
    daqsocket.yamlConfig['daq']['menus']['marsCalibAndL1A']['prescale']=0
    daqsocket.yamlConfig['daq']['menus']['marsCalibAndL1A']['repeatOffset']=700
    daqsocket.yamlConfig['daq']['menus']['marsCalibAndL1A']['bxCalib']=calibreqA
    daqsocket.yamlConfig['daq']['menus']['marsCalibAndL1A']['bxL1A']=calibreqA+BXoffset
    daqsocket.configure()
    
    # if needed configure the phase for the injection
    if phase>=0:
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['Top']['all']['phase_strobe'] = 15-phase
                if toa_vref!=-1: nestedConf[key]['sc']['ReferenceVoltage']['all']['Toa_vref'] = int(toa_vref)
                if tot_vref!=-1: nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref'] = int(tot_vref)
        i2csocket.configure(yamlNode=nestedConf.to_dict())
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    
    clisocket.start()
    scan(i2csocket=i2csocket, daqsocket=daqsocket, injectedChannels=injectedChannels, calib_vals=calib, gain=gain, odir=odir, testname=testname)
    while True:
        roots = glob.glob(odir+"/*.root")
        yamls = glob.glob(odir+"/*.yaml")
        if len(roots)==len(yamls)-1:
            break
        sleep(0.1)
    clisocket.stop()
    
    try:
        scan_analyzer = analyzer.injection_scan_analyzer(odir=odir,treename='mars/mars')
        files = glob.glob(odir+"/*.root")
        for f in files:
            scan_analyzer.add(f)
        scan_analyzer.mergeData()
        # scan_analyzer.makePlots()
    except Exception as e:
        with open(odir+"crash_report.log","w") as fout:
            fout.write("mars injection scan analysis went wrong and crash\n")
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
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
        daqsocket.initialize()
    else:
        i2csocket.configure()
    injectionConfig = {
        'phase' : 15,
        'BXoffset' : 22,
        'gain' : 0,
        'calib' : list(range(0,3000,50)),
        'toa_vref': 200,
        'tot_vref': 500
    }
    #for ch in range(0,18):
    for ch in range(1):
        injectionConfig['injectedChannels'] = {'ch':[ch,ch+18,ch+36,ch+54], 'calib':[] }
        injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
    # injectionConfig['injectedChannels'] = {'ch':[], 'calib':[0,1] }
    # injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
