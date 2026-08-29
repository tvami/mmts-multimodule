import yaml, datetime, os  #,paramiko
from time import sleep
import numpy as np

import zmq_controler as zmqctrl

import pedestal_run
import dump_run
import vref2D_scan
import vrefinv_scan
import vrefnoinv_scan
import phase_scan
import pedestal_scan
import sampling_scan
import injection_scan
import toa_threshold_scan
import tot_threshold_scan
import adc_range_setting
import agilent_ctrl
from nested_dict import nested_dict 

# Example: 
#  script to fully calibrate the chip

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
    
    parser.add_option("-s", "--suffix",
                      action="store", dest="suffix",default='',
                      help="output base directory")

    parser.add_option("-p", "--prologixIP",default="",
                      action="store", dest="prologixIP",
                      help="IP address of the prologix gpib ethernet controller, if not defined: the script will skip all agilent related commands")

    parser.add_option("-g", "--gpibAddress",default=5,type=int,
                      action="store", dest="gpibAddress",
                      help="gpib address set on the agilent PSU")

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
    if not options.hexaIP:
        options.hexaIP = '129.104.89.110'
    print(options.hexaIP)

    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)

    i2csocket.initialize()
    
    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    
    ##########    Ref_dac_inv settings
    pedestal_scan.pedestal_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    with open("%s/%s/trimmed_device.yaml" %(os.path.realpath(options.odir), options.dut),'w') as fout:
        yaml.dump(i2csocket.yamlConfig,fout)
    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    
    ##########    Setting Vref_inv to optimize the ADC dynamic range (Vref_noinv = 50)
    vrefinv_scan.vrefinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    with open("%s/%s/trimmed_device.yaml" %(os.path.realpath(options.odir), options.dut),'w') as fout:
        yaml.dump(i2csocket.yamlConfig,fout)
    vrefnoinv_scan.vrefnoinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    with open("%s/%s/trimmed_device.yaml" %(os.path.realpath(options.odir), options.dut),'w') as fout:
        yaml.dump(i2csocket.yamlConfig,fout)

    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    ##########    Re Ref_dac_inv settings
    pedestal_scan.pedestal_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    with open("%s/%s/trimmed_device.yaml" %(os.path.realpath(options.odir), options.dut),'w') as fout:
        yaml.dump(i2csocket.yamlConfig,fout)
    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    
    ##########    Checkinhg phase
    phase_scan.phase_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)    
    injectionConfig = {
       'gain' : 0,
    	'calib' : 700,
    	'injectedChannels' : [10,30,10+36,30+36]
    }
    ##########    Determining the best phase
    output_dir = sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,options.suffix)
    i2csocket.update_yamlConfig(fname=output_dir+'/best_phase.yaml') 
    i2csocket.configure(fname=output_dir+'/best_phase.yaml')
    with open("%s/%s/trimmed_device.yaml" %(os.path.realpath(options.odir), options.dut),'w') as fout:
        yaml.dump(i2csocket.yamlConfig,fout)
    
    ##########    Determining the best Ref_dac_toa settings
    phase = i2csocket.yamlConfig['roc_s0']['sc']['Top']['all']['phase_ck']
    l1a_offset = i2csocket.yamlConfig['roc_s0']['sc']['DigitalHalf']['all']['L1Offset']
    if phase in range(8,15):
        l1_val = 0
    else:
        l1_val = 1
    BXoffset = l1a_offset + 11 + l1_val  ## Calib_offset = 11
    injectionConfig = {
        'BXoffset' : BXoffset
        }
    toa_threshold_scan.toa_threshold_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,suffix=options.suffix)
    with open("%s/%s/trimmed_device.yaml" %(os.path.realpath(options.odir), options.dut),'w') as fout:
        yaml.dump(i2csocket.yamlConfig,fout)
    ##########    Checking Toa_vref at the "lowest" values
    injectionConfig = {
       'gain' : 0,
    	'calib' : 150,
    	'injectedChannels' : [0,20,40,50,60,70]
    }
    sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,"test_min_toa_thr")
    
    ##########    Determining the best Ref_dac_tot values
    i2csocket.configure()
    ############################################    
    phase = i2csocket.yamlConfig['roc_s0']['sc']['Top']['all']['phase_ck']
    l1a_offset = i2csocket.yamlConfig['roc_s0']['sc']['DigitalHalf']['all']['L1Offset']
    if phase in range(8,15):
        l1_val = 0
    else:
        l1_val = 1
    BXoffset = l1a_offset + 11 + l1_val  ## Calib_offset = 11
    injectionConfig = {
        'BXoffset' : BXoffset
        }
    tot_threshold_scan.tot_threshold_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,suffix=options.suffix)
    with open("%s/%s/trimmed_device.yaml" %(os.path.realpath(options.odir), options.dut),'w') as fout:
        yaml.dump(i2csocket.yamlConfig,fout)
    
    ##########    Determining the maximal Calib_dac values of the ADC dynamic range
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['ReferenceVoltage'][int(0)]['Tot_vref']=1000
            nestedConf[key]['sc']['ReferenceVoltage'][int(1)]['Tot_vref']=1000
    i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    i2csocket.configure()
    ############################################
    injectionConfig = {
        'phase' : phase,
        'BXoffset' : BXoffset,
        'gain' : 0,
        'calib' : [i for i in range(0,2000,10)],
        'injectedChannels' : [4,4+18,4+36,4+36+18]
    }
    rundir, max_dict = injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,suffix=options.suffix,keepRawData=1)
    max_calib = min(max_dict.values())

    ##########    Determining the best Tot_vref to optimize the ADC dynamic range
    injectionConfig = {
        'BXoffset' : BXoffset
        }
    adc_range_setting.adc_range_setting(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,max_calib,suffix=options.suffix)
    with open("%s/%s/trimmed_device.yaml" %(os.path.realpath(options.odir), options.dut),'w') as fout:
        yaml.dump(i2csocket.yamlConfig,fout)
    
