import yaml, datetime, os
import numpy as np

import zmq_controler as zmqctrl

import pedestal_run
import vrefinv_scan
import vrefnoinv_scan
import phase_scan
import pedestal_scan
import sampling_scan
import injection_scan
from nested_dict import nested_dict

# Example: 
# python3 hb_prodtest.py -d hb -i hexactrlIP -f configs/initLD.yaml 
#

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
    
    i2csocket.initialize()
    daqsocket.initialize()
    clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
    clisocket.initialize()

    print(" ############## Starting up the MASTER TDCs #################")
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['MasterTdc']['all']['EN_MASTER_CTDC_VOUT_INIT']=1
            nestedConf[key]['sc']['MasterTdc']['all']['VD_CTDC_P_DAC_EN']=1
            nestedConf[key]['sc']['MasterTdc']['all']['VD_CTDC_P_D']=16
            nestedConf[key]['sc']['MasterTdc']['all']['EN_MASTER_FTDC_VOUT_INIT']=1
            nestedConf[key]['sc']['MasterTdc']['all']['VD_FTDC_P_DAC_EN']=1
            nestedConf[key]['sc']['MasterTdc']['all']['VD_FTDC_P_D']=16
    i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    i2csocket.configure()
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['MasterTdc']['all']['EN_MASTER_CTDC_VOUT_INIT']=0
            nestedConf[key]['sc']['MasterTdc']['all']['EN_MASTER_FTDC_VOUT_INIT']=0
    i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    i2csocket.configure()

    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    pedestal_scan.pedestal_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    vrefinv_scan.vrefinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    vrefnoinv_scan.vrefnoinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    phase_scan.phase_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)

    injectionConfig = {
       'gain' : 0,
    	'calib' : 1000,
    	'injectedChannels' : [11,30,46,66]
    }
    sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
     
    injectionConfig = {
        'BXoffset' : 22,
        'gain' : 0,
        'calib' : [i for i in range(0,4096,100)],
        'phase': 14
    }
    for ch in range(0,18):
        injectionConfig['injectedChannels'] = {'ch':[ch,ch+18,ch+36,ch+54],
                                                'calib':[] }
        injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)    
