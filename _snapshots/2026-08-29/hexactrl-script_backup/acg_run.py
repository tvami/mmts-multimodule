import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util

import analysis.level0.tdc_scan_analysis as tdc_analyzer

import zmq_controler as zmqctrl
from nested_dict import nested_dict

import numpy as np


class Scan():
    def __init__(self, tdc_name = 'toa', ROCver = 'v3a'):
        self.master = {'CTRL_IN_REF_CTDC_P_D': [   10, 20, 30],     # up
                       'CTRL_IN_SIG_CTDC_P_D': [0, 10, 20, 30]}           # down
        if ROCver=='v3b':
            # CTRL_IN_CTDC_P_D: 5 bits for CTRL_IN_CTDC calibration voltage
            # CTRL_IN_CTDC_P_SIG: sign of the calibration voltage (0->DOWN, 1->UP)
            # will preprocess the negative values in the acquisition loop
            self.master = {'CTRL_IN_CTDC_P_D': [-31, -20, -10, 0,  10, 20, 31]}
        
        #self.individual = {f'DAC_CAL_CTDC_{tdc_name.upper()}': [0,10,20,31,32,40,50,63]}
        self.individual = {f'DAC_CAL_CTDC_{tdc_name.upper()}': [0,31,32,63]}

def acg_channel_scan(i2csocket, daqsocket, channels_per_run, odir, pars = {}, calib = "master", ROCver="v3a"):
    testName='acg_run'

    if calib=="singlerun": #trick to acquire a single run for performance studies without modyfing any tdc setting
        pars={"dummy":[0]}
    
    
    index = 0
    for pname, vals in pars.items():         
        for pval in vals: 
            print(f"Setting {pname} = {pval}")
            #enable 1 every <channels_per_run> channels
            for chindex in range(channels_per_run):
                probed_chs=[]
                nestedConf = nested_dict()
                for key in i2csocket.yamlConfig.keys():
                    if key.find('roc_s')==0:
                        if calib == 'master':
                            if ROCver=="v3a":
                                # -- set to 0 both pars and then set scan value
                                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_REF_CTDC_P_D'] = 0 # up   
                                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_SIG_CTDC_P_D'] = 0 # down
                                nestedConf[key]['sc']['MasterTdc']['all'][pname] = pval
                            else:
                                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_CTDC_P_D'] = abs(pval)
                                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_CTDC_P_SIG'] = int(pval>=0)

                        # -- de-activate all channels
                        nestedConf[key]['sc']['ch']['all']["mask_toa"] = 1
                        nestedConf[key]['sc']['ch']['all']["mask_tot"] = 1
                        
                        # -- activate 1/<channels_per_run> channels
                        for ic in range(72):
                            if (ic - chindex) % channels_per_run == 0:
                                nestedConf[key]['sc']['ch'][ic][f"mask_toa"] = 0
                                nestedConf[key]['sc']['ch'][ic][f"mask_tot"] = 0

                                if calib == 'individual':
                                    nestedConf[key]['sc']['ch'][ic][pname] = pval                             
                        
                                probed_chs.append(ic)
                                
                i2csocket.configure(yamlNode=nestedConf.to_dict())
                util.acquire_scan(daq=daqsocket)

                chip_params = {pname : pval, 'probed_chs' : probed_chs}
                
                util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                                  runid=index,testName=testName,keepRawData=1,
                                  chip_params=chip_params)

                index = index + 1
                if calib == 'master': break                         
            
    return


def acg_run(i2csocket, daqsocket, clisocket, basedir, device_name,
            tdc_name,suffix="", logging_level='INFO', nevents=1000,
            calib="master", pars={}, update_yaml='', ROCver='v3a'):
    if type(i2csocket) != zmqctrl.i2cController:
	    print( "ERROR : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
	    sleep(1)
	    return

    if type(daqsocket) != zmqctrl.daqController:
	    print( "ERROR : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
	    sleep(1)
	    return

    if type(clisocket) != zmqctrl.daqController:
	    print( "ERROR : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
	    sleep(1)
	    return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if suffix:
        timestamp = timestamp + "_" + suffix
    odir = "%s/%s/acg_run_%s/run_%s/"%( os.path.realpath(basedir), device_name, calib,  timestamp ) # a comlete path is needed
    os.makedirs(odir)
    print (odir)
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)

    channels_per_run = 4

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "acg_run"
    clisocket.configure()
    daqsocket.yamlConfig['daq']['active_menu']='randomL1A'
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['NEvents']=nevents
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['log2_rand_bx_period']=0
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['bx_min']=80
    daqsocket.configure()
    
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['DigitalHalf']['all']['L1Offset'] = 10
            nestedConf[key]['sc']['DigitalHalf']['all']['Bx_offset'] = 2

            if ROCver=="v3b":
                # optimal setup for acg run in v3b
                nestedConf[key]['sc']['MasterTdc']['all']['BIAS_FOLLOWER_CAL_P_CTDC_D'] = 4
                nestedConf[key]['sc']['MasterTdc']['all']['BIAS_FOLLOWER_CAL_P_FTDC_D'] = 8
                nestedConf[key]['sc']['MasterTdc']['all']['CTDC_CALIB_FREQUENCY'] = 1
                nestedConf[key]['sc']['MasterTdc']['all']['FTDC_CALIB_FREQUENCY'] = 1
                nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_LATENCY_TIME'] = 9
                nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_SYNC_OUT'] = 1
                # enable calibration voltages for master fine and coarse tdc
                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_CTDC_P_EN'] = 1
                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_FTDC_P_EN'] = 1
                # initialize the calibration voltages for master tdc
                #nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_CTDC_P_D'] = 0
                #nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_FTDC_P_D'] = 0
                #nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_CTDC_P_SIG'] = 0
                #nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_FTDC_P_SIG'] = 0
                # select random clock generator as external trigger
                if tdc_name=="toa":
                    nestedConf[key]['sc']['MasterTdc']['all']['sel_clk_rcg_toa'] = 1
                    nestedConf[key]['sc']['MasterTdc']['all']['sel_clk_rcg_tot'] = 0
                else:
                    nestedConf[key]['sc']['MasterTdc']['all']['sel_clk_rcg_toa'] = 0
                    nestedConf[key]['sc']['MasterTdc']['all']['sel_clk_rcg_tot'] = 1

            elif ROCver=="v3a":
                # optimal setup for acg run in v3a                
                nestedConf[key]['sc']['MasterTdc']['all']['BIAS_FOLLOWER_CAL_P_D'] = 4
                nestedConf[key]['sc']['MasterTdc']['all']['BIAS_FOLLOWER_CAL_P_FTDC_D'] = 8
                nestedConf[key]['sc']['MasterTdc']['all']['CTDC_CALIB_FREQUENCY'] = 1
                nestedConf[key]['sc']['MasterTdc']['all']['FTDC_CALIB_FREQUENCY'] = 1
                nestedConf[key]['sc']['Top']['all']['INIT_DAC_EN'] = 1
                nestedConf[key]['sc']['Top']['all']['in_inv_cmd_rx'] = 1                
                # enable calibration voltages for master fine and coarse tdc
                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_REF_CTDC_P_EN'] = 1
                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_REF_FTDC_P_EN'] = 1                
                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_SIG_CTDC_P_EN'] = 1
                nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_SIG_FTDC_P_EN'] = 1
                # initialize the calibration voltages for master tdc
                #nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_REF_CTDC_P_D'] = 0   ### master tdc par down 
                #nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_REF_FTDC_P_D'] = 0
                #nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_SIG_CTDC_P_D'] = 0   ### master tdc par up
                #nestedConf[key]['sc']['MasterTdc']['all']['CTRL_IN_SIG_FTDC_P_D'] = 0
                # select random clock generator as external trigger
                if tdc_name=="toa":
                    nestedConf[key]['sc']['MasterTdc']['all']['sel_clk_rcg'] = 1
                else:
                    nestedConf[key]['sc']['MasterTdc']['all']['sel_clk_rcg'] = 2 
            else:
                raise ValueError(f"Unknown chip version {ROCver}")
                
            nestedConf[key]['sc']['MasterTdc']['all']['BIAS_CAL_DAC_CTDC_P_D'] = 2
            nestedConf[key]['sc']['MasterTdc']['all']['BIAS_CAL_DAC_CTDC_P_EN'] = 1
            nestedConf[key]['sc']['MasterTdc']['all']['BIAS_FOLLOWER_CAL_P_CTDC_EN'] = 1
            nestedConf[key]['sc']['MasterTdc']['all']['BIAS_FOLLOWER_CAL_P_FTDC_EN'] = 1
            nestedConf[key]['sc']['MasterTdc']['all']['BIAS_I_CTDC_D'] = 31
            nestedConf[key]['sc']['MasterTdc']['all']['BIAS_I_FTDC_D'] = 31
            nestedConf[key]['sc']['MasterTdc']['all']['FOLLOWER_CTDC_EN'] = 1
            nestedConf[key]['sc']['MasterTdc']['all']['FOLLOWER_FTDC_EN'] = 1
            nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_DISABLE_TOT_LIMIT'] = 0 
            nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_EN_BUFFER_CTDC'] = 1
            nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_EN_BUFFER_FTDC'] = 1
            nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_FORCE_EN_CLK'] = 1                
            nestedConf[key]['sc']['MasterTdc']['all']['VD_FTDC_N_FORCE_MAX'] = 0
            nestedConf[key]['sc']['MasterTdc']['all']['VD_FTDC_N_D'] = 15
            nestedConf[key]['sc']['MasterTdc']['all']['VD_FTDC_N_DAC_EN'] = 1
            nestedConf[key]['sc']['MasterTdc']['all']['START_COUNTER'] = 1

            if tdc_name=="toa":
                nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_MODE_NO_TOT_SUB'] = 0
                nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_FORCE_EN_TOT'] = 0
                nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_EN_TOT_PRIORITY'] = 0                 
                nestedConf[key]['sc']['ch']['all']['sel_trig_toa'] = 0
                nestedConf[key]['sc']['ch']['all']['sel_trig_tot'] = 1
                nestedConf[key]['sc']['calib']['all']['sel_trig_toa'] = 0
                nestedConf[key]['sc']['calib']['all']['sel_trig_tot'] = 1
            else: # tot tdc
                nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_MODE_NO_TOT_SUB'] = 1
                nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_FORCE_EN_TOT'] = 1
                nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_EN_TOT_PRIORITY'] = 1
                nestedConf[key]['sc']['ch']['all']['sel_trig_toa'] = 1
                nestedConf[key]['sc']['ch']['all']['sel_trig_tot'] = 0
                nestedConf[key]['sc']['calib']['all']['sel_trig_toa'] = 1
                nestedConf[key]['sc']['calib']['all']['sel_trig_tot'] = 0

            nestedConf[key]['sc']['MasterTdc']['all']['GLOBAL_FORCE_EN_OUTPUT_DATA'] = 1                
            nestedConf[key]['sc']['Top']['all']['EN_RCG'] = 1
            nestedConf[key]['sc']['Top']['all']['BIAS_I_PLL_D'] = 63
            nestedConf[key]['sc']['Top']['all']['DIV_PLL'] = 0
            nestedConf[key]['sc']['Top']['all']['EN_HIGH_CAPA'] = 1
            nestedConf[key]['sc']['Top']['all']['EN_LOCK_CONTROL'] = 1
            nestedConf[key]['sc']['Top']['all']['EN_probe_pll'] = 0
            nestedConf[key]['sc']['Top']['all']['ERROR_LIMIT_SC'] = 2
            nestedConf[key]['sc']['Top']['all']['INIT_D'] = 0
            nestedConf[key]['sc']['Top']['all']['RunL'] = 1
            nestedConf[key]['sc']['Top']['all']['RunR'] = 1
            nestedConf[key]['sc']['Top']['all']['VOUT_INIT_EN'] = 0
            nestedConf[key]['sc']['Top']['all']['VOUT_INIT_EXT_D'] = 0
            nestedConf[key]['sc']['Top']['all']['VOUT_INIT_EXT_EN'] = 0
            nestedConf[key]['sc']['Top']['all']['phase_ck'] = 0
            nestedConf[key]['sc']['Top']['all']['rcg_gain'] = 0

            # set toa and tot thresholds to reasonable values
            nestedConf[key]['sc']['ch']['all']['trim_toa'] = 0
            nestedConf[key]['sc']['ch']['all']['trim_tot'] = 0
            nestedConf[key]['sc']['calib']['all']['trim_toa'] = 0
            nestedConf[key]['sc']['calib']['all']['trim_tot'] = 0
            nestedConf[key]['sc']['ReferenceVoltage']['0']['Toa_vref'] = 250
            nestedConf[key]['sc']['ReferenceVoltage']['1']['Toa_vref'] = 250
            nestedConf[key]['sc']['ReferenceVoltage']['0']['Tot_vref'] = 300
            nestedConf[key]['sc']['ReferenceVoltage']['1']['Tot_vref'] = 300
        
    i2csocket.configure(yamlNode=nestedConf.to_dict())
    if len(update_yaml): i2csocket.update_yamlConfig(update_yaml)
    
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
            
    mylittlenotifier.start()
    clisocket.start()
    
    acg_channel_scan(i2csocket, daqsocket, channels_per_run, odir, pars, calib, ROCver)
    
    for pname, vals in pars.items():
        for pval in vals: 
            sleep(4) #sleep long enough to unpack everything before reading out files
            print("wait for unpacking completion..")

    try:
        analyzer = tdc_analyzer.tdc_raw_analyzer(odir=odir, tdc_name=tdc_name, calib = calib, ROCver = ROCver)
        if calib=="singlerun":
            analyzer.performance_plots()
        else:
            best_pars = analyzer.get_best_parameters()
            analyzer.write_to_yaml(best_pars)

    except Exception as e:
        with open(odir+"crash_report.log","w") as fout:
            fout.write("agc_run analysis went wrong and crash\n")
            fout.write("Error {0}\n".format(str(e)))

    clisocket.stop()
    mylittlenotifier.stop()
    
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

    parser.add_option("--tdc", default="toa",
                      action="store", dest="tdc_name",
                      help="decide if acquiring data from toa or tot TDC")

    parser.add_option("--master", default=False,
                      action="store_true", dest="master",
                      help="acquire data for master calibration")

    parser.add_option("--individual", default=False,
                      action="store_true", dest="individual",
                      help="acquire data for individual calibration")

    parser.add_option("--singlerun", default=False,
                      action="store_true", dest="singlerun",
                      help="acquire data for individual calibration")
    
    parser.add_option("-N", "--nevents", default=1000,
                      action="store", dest="nevents",
                      help="number of events")

    parser.add_option("--ROCversion", default="v3a",
                      action="store", dest="ROCver",
                      help='ROC version: "v3a" or "v3b"')    

    parser.add_option("-y", "--master_yaml",default="",
                      action="store", dest="master_yaml",
                      help="config with master tdc calib best parameters")


    (options, args) = parser.parse_args()
    print(options)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)

    if not(options.tdc_name in ["toa","tot"]):
        raise RuntimeError("tdc name must be either toa or tot")
    
    if options.initialize==True:
        i2csocket.initialize()
        daqsocket.initialize()
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
    else:
        i2csocket.configure()

    scan_pars = Scan(options.tdc_name, options.ROCver)
    calib = {'master': options.master, 
             'individual': options.individual}

    master_yaml = ''

    if calib['master']:
        master_yaml = acg_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,suffix="",tdc_name=options.tdc_name,nevents = options.nevents, calib = 'master', pars = scan_pars.master, ROCver=options.ROCver)            
                
    if calib['individual']:
        if calib ['master']:
            # use the best master parameters just computed
            master_yaml = f'{master_yaml}/{options.tdc_name}_master.yaml'
        elif len(options.master_yaml): 
            master_yaml = options.master_yaml 
            
        ind_yaml = acg_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,suffix="",tdc_name=options.tdc_name,nevents = options.nevents, calib = 'individual', pars = scan_pars.individual, update_yaml = master_yaml, ROCver=options.ROCver)            

    if options.singlerun:
        acg_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,suffix="",tdc_name=options.tdc_name,nevents = options.nevents,calib='singlerun', ROCver=options.ROCver)
