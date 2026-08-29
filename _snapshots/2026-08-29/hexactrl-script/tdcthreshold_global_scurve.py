import zmq, datetime,  os, subprocess, sys, yaml, glob, math, re
from time import sleep

import myinotifier,util
import analysis.level0.tdcthreshold_global_scurve_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict
import numpy as np

def scan(i2csocket, daqsocket, injectedChannels, calib_dac, tdc_vrefs, odir):
    testName='tdcthreshold_global_scurve'

    index=0
    for tdcvref in tdc_vrefs:
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Toa_vref']=int(tdcvref)
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref']=int(tdcvref)
        i2csocket.configure(yamlNode=nestedConf.to_dict())

        util.acquire_scan(daq=daqsocket)
        chip_params = { 'Calib_dac' : calib_dac,
                        'Toa_vref'  : int(tdcvref),
                        'Tot_vref'  : int(tdcvref) }
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testName,keepRawData=0,
                          chip_params=chip_params)
        index=index+1
    return

def tdcthreshold_global_scurve(i2csocket,daqsocket, clisocket, basedir,device_name, injectionConfig):
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
    odir = "%s/%s/tdcthreshold_global_scurve/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()

    clisocket.yamlConfig['global']['outputDirectory'] = odir
    clisocket.yamlConfig['global']['run_type'] = "tdcthreshold_global_scurve"
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.configure()
    
    calibreqA            = 0x10
    calibreqC            = 0x200
    phase				= injectionConfig['phase']
    BXoffset			= injectionConfig['BXoffset']
    calib_dac 			= injectionConfig['calib_dac']
    injectedChannels	= injectionConfig['injectedChannels']
    tdc_vrefs           = injectionConfig['tdc_vrefs']
    gain 				= injectionConfig['gain'] # 0 for low range ; 1 for high range

    daqsocket.yamlConfig['daq']['NEvents']='1000'
    daqsocket.enable_fast_commands(A=1)#,C=1)    
    daqsocket.l1a_generator_settings(name='A',BX=calibreqA,length=1,cmdtype='CALIBREQ',prescale=0,followMode='DISABLE')
    daqsocket.l1a_generator_settings(name='B',BX=calibreqA+BXoffset,length=1,cmdtype='L1A',prescale=0,followMode='A')
    # daqsocket.l1a_generator_settings(name='C',BX=calibreqC,length=1,cmdtype='CALIBREQ',prescale=0,followMode='DISABLE')
    # daqsocket.l1a_generator_settings(name='D',BX=calibreqC+BXoffset,length=1,cmdtype='L1A',prescale=0,followMode='C')
    daqsocket.configure()
    
    i2csocket.configure_injection(injectedChannels, phase=phase, calib_dac=calib_dac, activate=1, gain=gain)
    
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)

    clisocket.start()
    scan(i2csocket=i2csocket, daqsocket=daqsocket, injectedChannels=injectedChannels, calib_dac=calib_dac, tdc_vrefs=tdc_vrefs, odir=odir)
    clisocket.stop()
    mylittlenotifier.stop()

    scurve_analyzer = analyzer.tdcthreshold_global_scurve_analyzer(odir=odir)
    files = glob.glob(odir+"/"+clisocket.yamlConfig['global']['run_type']+"*.root")
    
    for f in files:
	    scurve_analyzer.add(f)
    scurve_analyzer.mergeData()
    scurve_analyzer.makePlots(injectedChannels)

    # return to no injection setting
    i2csocket.configure_injection(injectedChannels,activate=0,calib_dac=0,phase=14,gain=0) 

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
    
    
    (options, args) = parser.parse_args()
    print(options)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    i2csocket.configure()
    injectionConfig = {
        'phase' : 14,
        'BXoffset' : 19,
        'gain' : 0,
        'calib_dac' : 1700,
        'tdc_vrefs' : np.arrange(110,1000,int(1000-110)/45),
        'injectedChannels' : [10,20,30,40,60,70] # [i for i in range(72)]
    }
    tdcthreshold_global_scurve(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
