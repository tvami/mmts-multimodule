import yaml, datetime, os, sys #,paramiko
from time import sleep, time
import numpy as np

import zmq_controler as zmqctrl

import probeDC_run
import inCtest_run
import pedestal_run
import dump_run
import vref2D_scan
import vrefinv_scan
import vrefnoinv_scan
import phase_scan
import pedestal_scan
import sampling_scan
import injection_scan
import tdc_threshold_scan
import tdcthreshold_global_scurve
import agilent_ctrl
from nested_dict import nested_dict 
import dacb_scan

# Example: 
# python3 sipm_full_test.py -d hb -n 3 -i hexactrl564610 -p pool05550004 -g 6
#

if __name__ == "__main__":    
    from optparse import OptionParser
    parser = OptionParser()
    
    parser.add_option("-d", "--dut", dest="dut",
                      help="device under test")

    parser.add_option("-i", "--hexaIP", default = "10.220.0.109",
                      action="store", dest="hexaIP",
                      help="IP address of the zynq on the hexactrl board")
    
    parser.add_option("-f", "--configFile",default="./configs/init.yaml",
                      action="store", dest="configFile",
                      help="initial configuration yaml file")
    
    parser.add_option("-o", "--odir",
                      action="store", dest="odir",default='./data',
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

    start = time()    
    (options, args) = parser.parse_args()    
    print(options)
    
    '''
    agilent_ctrler = None
    if options.prologixIP:
        agilent_ctrler = agilent_ctrl.agilent_ctrl(options.prologixIP,options.gpibAddress)
        agilent_ctrler.setV("P25V",0,1.)
        agilent_ctrler.setV("N25V",0,1.)
        agilent_ctrler.setV("P6V",3.3,2.0)
        agilent_ctrler.on()
        agilent_ctrler.display("P6V")
        print("agilent set")

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(options.hexaIP, username="root", password="centos")
    ssh_client.exec_command("./hexactrl-sw/test_HC1_1.sh rocchar")
    print("hexa-controller servers started")
    '''
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)


    i2csocket.initialize()
    
    ##########
    # Probing
    #inCtest_run.inCtest_run(i2csocket, options.odir, options.dut)
    #probeDC_run.probeDC_run(i2csocket, options.odir, options.dut)
    
    # Pedestal adjustment
    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    pedestal_scan.pedestal_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    #vref2D_scan.vref2D_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.suffix)
    #vrefinv_scan.vrefinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    #vrefnoinv_scan.vrefnoinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    pedestal_run.pedestal_run(i2csocket, daqsocket, clisocket, options.odir, options.dut)
   
    ############
    # SiPM specific 
    dacb_scan.dacb_scan(i2csocket, daqsocket, clisocket, options.odir, options.dut, Gain_conv = 6)
    dacb_scan.dacb_scan(i2csocket, daqsocket, clisocket, options.odir, options.dut, Gain_conv = 12)
    
    ###########
    # Memory
    dump_nruns = 1
    dump_run.dump_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, dump_nruns)
    
    ###########
    # Phase & injection
    phase_scan.phase_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)

    injectionConfig = {
       'gain' : 0,
    	'calib_dac' : 500,
    	'injectedChannels' : [10,12] #[0,10,20,30,40,50,60,70]
    }
    sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
    
    injectionConfig = {
       'gain' : 1,
    	'calib_dac' : 1000,
    	'injectedChannels' : [10,12,46,48] #[0,10,20,30,40,50,60,70]
    }
    sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
     
    injectionConfig = {
       'gain' : 0,
    	'calib_dac' : 500,
    	'injectedChannels' : [i for i in range(72)]
    }
    #sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    injectionConfig = {
       'gain' : 1,
    	'calib_dac' : 1000,
    	'injectedChannels' : [i for i in range(72)]
    }
    #sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    injectionConfig = {
       'phase' : 14,
       'BXoffset' : 19,
       'gain' : 0,
       'calib_dac' : [-1]+[i for i in range(0,2048,20)],
        'injectedChannels' :  [10,12,46,48] #[0,10,20,30,40,50,60,70] #[i for i in range(72)]
    }
    #injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    injectionConfig = {
       'phase' : 14,
       'BXoffset' : 19,
       'gain' : 1,
       'calib_dac' : [-1]+[i for i in range(0,2048,20)],
        'injectedChannels' :  [10,12,46,48] #[0,10,20,30,40,50,60,70] #[i for i in range(72)]
    }
    #injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    injectionConfig = {
       'phase' : 14,
       'BXoffset' : 19,
       'gain' : 0,
        'calib_dac' : [i for i in range(0,2048,20)],
       'injectedChannels' : [i for i in range(72)]
    }
    injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    injectionConfig = {
       'phase' : 14,
       'BXoffset' : 19,
       'gain' : 1,
        'calib_dac' : [i for i in range(0,2048,20)],
       'injectedChannels' : [i for i in range(72)]
    }
    injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    injectionConfig = {
       'phase' : 10,
       'BXoffset' : 19,
       'gain' : 0,
       'calib_dac' : 300,
       'tdc_vrefs' : np.arange(110,500,int(500-110)/45),
       'injectedChannels' : [i*10 for i in range(8)]
    }
    #tdcthreshold_global_scurve.tdcthreshold_global_scurve(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    injectionConfig = {
      'phase' : 10,
      'BXoffset' : 19,
      'gain' : 0,
      'calib_dac' : 2000,
      'tdc_vrefs' : np.arange(110,1000,int(1000-110)/45),
      'injectedChannels' : [i*10 for i in range(8)]
    }
    #tdcthreshold_global_scurve.tdcthreshold_global_scurve(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
    end = time()
    print('Total test time: %f' %(end-start))
