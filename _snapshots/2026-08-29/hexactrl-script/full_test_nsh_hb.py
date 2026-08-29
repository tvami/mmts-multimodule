import yaml, datetime, os,paramiko
from time import sleep
import numpy as np

import zmq_controler as zmqctrl

import probeDC_run
import inCtest_run
import pedestal_run
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
# Example: 
# python3 full_test.py -d hb -n 3 -i hexactrl564610 -p pool05550004 -g 6
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

    agilent_ctrler = None
    if options.prologixIP:
        agilent_ctrler = agilent_ctrl.agilent_ctrl(options.prologixIP,options.gpibAddress)
        agilent_ctrler.setV("P25V",0,1.)
        agilent_ctrler.setV("N25V",0,1.)
        agilent_ctrler.setV("P6V",3.3,2.0)
        agilent_ctrler.on()
        agilent_ctrler.display("P6V")
        print("agilent set")

    #ssh_client = paramiko.SSHClient()
    #ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    #ssh_client.connect(options.hexaIP, username="root", password="centos")
    #ssh_client.exec_command("./hexactrl-sw/test_HC1_1.sh trophy")
    #print("hexa-controller servers started")
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    i2csocket.initialize()

    if agilent_ctrler:
        print("agilent power measurement")
        agilent_ctrler.meas(options.dut,options.odir)
        agilent_ctrler.display("P6V")

    #inCtest_run.inCtest_run(i2csocket, options.odir, options.dut)
    #probeDC_run.probeDC_run(i2csocket, options.odir, options.dut)

    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    pedestal_scan.pedestal_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    # vref2D_scan.vref2D_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    vrefinv_scan.vrefinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    vrefnoinv_scan.vrefnoinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    phase_scan.phase_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)


    #
    injectionConfig = {
       'gain' : 0,
    	'calib' : 300,
    	'injectedChannels' : [11,30,46,66]
    }
    sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
    # 
    injectionConfig = {
       'phase' : 14,
       'BXoffset' : 19,
       'gain' : 0,
        'calib' : [i for i in range(0,2048,50)],
        'injectedChannels' : { 'ch': [i for i in range(72)],
                              'calib' : []
                          }
    }
    injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    injectionConfig = {
      'phase' : 14,
      'BXoffset' : 19,
      'gain' : 1,
      'calib' : [i for i in range(0,2048,50)],
      'injectedChannels' : { 'ch': [i for i in range(72)],
                              'calib' : []
                          }
    }
    injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)

    #if agilent_ctrler:
    #    agilent_ctrler.off()
    #ssh_client.exec_command("killall python3")
    #ssh_client.exec_command("killall zmq-server")
    #ssh_client.close()
    
