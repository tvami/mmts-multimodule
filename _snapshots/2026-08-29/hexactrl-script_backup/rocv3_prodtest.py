import yaml, datetime, os, paramiko
import numpy as np

import zmq_controler as zmqctrl

import pedestal_run
import vrefinv_scan
import vrefnoinv_scan
import phase_scan
import pedestal_scan
import sampling_scan
import injection_scan
import agilent_ctrl
import inCtest_run
import probeDC_run

# Example: 
# python3 rocv3_prodtest.py -d hb  -i hexactrlIP  -f configs/init1ROC.yaml 
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
    
    parser.add_option("-a", "--agilentPrologixIP",
                      action="store", dest="agilentPrologixIP",
                      help="IP address of the prologix gpib ethernet controller connected to the agilent PSU")

    parser.add_option("-g", "--gpibAddress",default=6,type=int,
                      action="store", dest="gpibAddress",
                      help="gpib address set on the agilent PSU")

    parser.add_option("-k", "--keithleyPrologixIP",
                      action="store", dest="keithleyPrologixIP",
                      help="IP address of the prologix gpib ethernet controller connected to the keithley multimeter")

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
    if options.agilentPrologixIP:
        agilent_ctrler = agilent_ctrl.agilent_ctrl(options.agilentPrologixIP,options.gpibAddress)
        agilent_ctrler.setV("P25V",0,1.)
        agilent_ctrler.setV("N25V",0,1.)
        agilent_ctrler.setV("P6V",3.3,2.0)
        agilent_ctrler.on()
        agilent_ctrler.display("P6V")
        print("agilent set")

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(options.hexaIP, username="root", password="centos")
    stdin, stdout, stderr = ssh_client.exec_command("fw-loader load singleroc-tester-v1p1;")
    print( "stderr: ", stderr.readlines() )
    print( "pwd: ", stdout.readlines() )
    from time import sleep
    sleep(0.5)
    ssh_client.exec_command("systemctl restart zmq-i2c.service")
    ssh_client.exec_command("systemctl restart zmq-server.service")
    ssh_client.close()
    print("hexa-controller servers started")

    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    i2csocket.initialize()
    daqsocket.initialize()
    clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
    clisocket.initialize()
    
    if options.keithleyPrologixIP!=None:
        inCtest_run.inCtest_run(i2csocket, options.odir, options.dut, options.keithleyPrologixIP)
        probeDC_run.probeDC_run(i2csocket, options.odir, options.dut, options.keithleyPrologixIP)

    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    pedestal_scan.pedestal_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    vrefinv_scan.vrefinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    vrefnoinv_scan.vrefnoinv_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    pedestal_run.pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut)
    phase_scan.phase_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)

    injectionConfig = {
       'gain' : 0,
    	'calib' : 1000,
    	'injectedChannels' : [15,30,46,66]
    }
    sampling_scan.sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
     
    injectionConfig = {
        'BXoffset' : 23,
        'gain' : 0,
        'calib' : [i for i in range(0,4096,100)],
    }
    for ch in range(0,9):
        injectionConfig['injectedChannels'] = {'ch':[ch,ch+9,ch+18,ch+27,
                                                     ch+36,ch+45,ch+54,ch+63],
                                                'calib':[] }
        injection_scan.injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)    

    if agilent_ctrler:
        agilent_ctrler.off()
