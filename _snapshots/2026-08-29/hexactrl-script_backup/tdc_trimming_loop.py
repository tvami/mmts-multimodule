import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util

import analysis.level0.tdc_scan_analysis as tdc_analyzer

import zmq_controler as zmqctrl
from nested_dict import nested_dict

import numpy as np
from acg_run import acg_run

class Scan():
    def __init__(self, tdc_name = 'toa', ROCver = 'v3a'):
        self.master = {'CTRL_IN_REF_CTDC_P_D': [10, 15,  20, 25, 30],     # up
                       'CTRL_IN_SIG_CTDC_P_D': [0, 10, 20, 30]}           # down
        if ROCver=='v3b':
            # CTRL_IN_CTDC_P_D: 5 bits for CTRL_IN_CTDC calibration voltage
            # CTRL_IN_CTDC_P_SIG: sign of the calibration voltage (0->DOWN, 1->UP)
            # will preprocess the negative values in the acquisition loop
            self.master = {'CTRL_IN_CTDC_P_D': [-31, -20, -10, 0,  10, 20, 31]}
        
        #self.individual = {f'DAC_CAL_CTDC_{tdc_name.upper()}': [0,10,20,31,32,40,50,63]}
        self.individual = {f'DAC_CAL_CTDC_{tdc_name.upper()}': [0,31,32,63]}


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

    parser.add_option("--ROCversion", default="v3a",
                      action="store", dest="ROCver",
                      help='ROC version: "v3a" or "v3b"')    

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

    scan_pars = Scan("toa", options.ROCver)

    # check initial timing performance
    acg_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, suffix="",
            tdc_name="toa", nevents = 20000, calib='singlerun', ROCver=options.ROCver)

    # trim master tdc using the toa
    master_trim_odir = acg_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, suffix="",
                               tdc_name="toa", nevents = 75000, ROCver=options.ROCver,
                               calib='master', pars=scan_pars.master)

    # check timing performance after master tdc trim
    master_yaml = f'{master_trim_odir}/toa_master.yaml'
    i2csocket.update_yamlConfig(master_yaml)
    i2csocket.configure()    
    acg_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, suffix="",
            tdc_name="toa", nevents = 20000, calib='singlerun', ROCver=options.ROCver)

    # trim invidual channels toa tdc 
    ind_trim_odir = acg_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, suffix="",
                            tdc_name="toa", nevents=100000, ROCver=options.ROCver,
                            calib='individual', pars = scan_pars.individual)

    # check toa timing performance after master and individual toa tdc trim
    ind_yaml = f'{ind_trim_odir}/toa_individual.yaml'
    i2csocket.update_yamlConfig(ind_yaml)
    i2csocket.configure()        
    acg_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, suffix="",
            tdc_name="toa", nevents = 20000, calib='singlerun', ROCver=options.ROCver)

    # check tot timing performance
    acg_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, suffix="",
            tdc_name="tot", nevents = 100000, calib='singlerun', ROCver=options.ROCver)

    # trim invidual channels tot tdc
    scan_pars = Scan("tot", options.ROCver)
    ind_tottrim_odir = acg_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, suffix="",
                            tdc_name="tot", nevents=100000, ROCver=options.ROCver,
                            calib='individual', pars = scan_pars.individual)

    # check tot timing performance after master and individual tot tdc trim
    ind_totyaml = f'{ind_tottrim_odir}/tot_individual.yaml'
    i2csocket.update_yamlConfig(ind_totyaml)
    i2csocket.configure()        
    acg_run(i2csocket, daqsocket, clisocket, options.odir, options.dut, suffix="",
            tdc_name="tot", nevents = 100000, calib='singlerun', ROCver=options.ROCver)

    # merge all cfgs together
    masteryaml = open(master_yaml,'r')
    outconfig = yaml.safe_load(masteryaml)
    toayaml = open(ind_yaml,'r')
    toaconfig = yaml.safe_load(toayaml)
    totyaml = open(ind_totyaml,'r')
    totconfig = yaml.safe_load(totyaml)
    outconfig = zmqctrl.merge(outconfig,toaconfig)
    #outconfig = zmqctrl.merge(outconfig,totconfig)
    print("Below is the TDC configuration")
    print("-----------------------------------------------------------------")
    print("-----------------------------------------------------------------")
    print( yaml.dump(outconfig) )
    print("-----------------------------------------------------------------")
    print("-----------------------------------------------------------------")
