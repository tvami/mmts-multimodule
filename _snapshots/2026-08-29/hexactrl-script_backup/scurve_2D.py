import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.scurve_2D_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict

def scan(i2csocket, daqsocket, injectedChannels, calib_vals, tdc_vrefs, gain, odir):
    testName = 'scurve_2D'
    index=0
    # pre-configure the injection
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
    # scanning calDAC values:
    updateRef  = lambda conf,ref,val: conf['sc']['ReferenceVoltage']['all'].update({ref:val})
    runs = [ {'calib':int(calib), 'tdc_vref':int(tdc_vref)} for calib in calib_vals for tdc_vref in tdc_vrefs ]
    for run in runs:
        nestedConf = nested_dict()
        [ updateRef(nestedConf[key],'Calib',run['calib'])           for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
        [ updateRef(nestedConf[key],'Toa_vref',run['tdc_vref'])     for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
        [ updateRef(nestedConf[key],'Tot_vref',run['tdc_vref']+100) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        util.acquire_scan(daq=daqsocket)
        chip_params = { 'Inj_gain': gain,
                        'Calib':    run['calib'],
                        'Toa_vref': run['tdc_vref'],
                        'Tot_vref': run['tdc_vref']+100,
                        'injectedChannels':injectedChannels['ch']
        }
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testName,keepRawData=0,
                          chip_params=chip_params)
        index+=1

    nestedConf = nested_dict()
    [nestedConf[key]['sc']['ReferenceVoltage']['all'].update({'IntCtest':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
    [nestedConf[key]['sc']['ReferenceVoltage']['all'].update({'Calib':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
    [update(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',0) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
    [update(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',0) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
    i2csocket.configure(yamlNode=nestedConf.to_dict())
    return

def scurve(i2csocket,daqsocket,clisocket,basedir,device_name,scurve2DConfig):
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
    odir = "%s/%s/scurve2D/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
     # do not run the inotifier if the unpacker is not yet ready to read vectors inside metaData yaml file using key "chip_params"
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    
    calibreqA           = 0x10
    phase				= scurve2DConfig['phase'] if 'phase' in scurve2DConfig.keys() else -1
    BXoffset			= scurve2DConfig['BXoffset']
    calib     			= scurve2DConfig['calib']
    injectedChannels	= scurve2DConfig['injectedChannels']
    gain 				= scurve2DConfig['gain'] # 0 for low range ; 1 for high range
    tdc_vrefs           = scurve2DConfig['tdc_vref']
    
    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "scurve_2D"
    clisocket.configure()
    
    daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']=1000
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreqA
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=calibreqA+BXoffset
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
    daqsocket.configure()
    
    # if needed configure the phase for the injection
    if phase>=0:
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['Top']['all']['phase_strobe'] = 15-phase
        i2csocket.configure(yamlNode=nestedConf.to_dict())
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    
    clisocket.start()
    mylittlenotifier.start()
    scan(i2csocket=i2csocket, daqsocket=daqsocket, injectedChannels=injectedChannels, calib_vals=calib, tdc_vrefs=tdc_vrefs, gain=gain, odir=odir)
    mylittlenotifier.stop()
    clisocket.stop()
    
    try:
        scan_analyzer = analyzer.scurve_2D_analyzer(odir=odir)
        files = glob.glob(odir+"/*.root")
        for f in files:
            scan_analyzer.add(f)
        scan_analyzer.mergeData()
        scan_analyzer.makePlots()
        scan_analyzer.addSummary()
        scan_analyzer.writeSummary()
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
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
        daqsocket.initialize()
    else:
        i2csocket.configure()

    scurve2DConfig = {
        'phase' : 14,
        'BXoffset' : 22,
        'gain' : 0,
        'calib' : list(range(0,1000,50)),
        'tdc_vref': list(range(110,300,20))
    }
    #for ch in range(0,18):
    for ch in range(0,1):
        scurve2DConfig['injectedChannels'] = {'ch':[ch,ch+18,ch+36,ch+54], 'calib':[] }
        scurve(i2csocket,daqsocket,clisocket,options.odir,options.dut,scurve2DConfig)
