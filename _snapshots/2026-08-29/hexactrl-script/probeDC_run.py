""" References from HGCROCv2 Datasheet:
p.45: ProbeDC1/2 codes and typical values. """

import zmq, datetime,  os, subprocess, sys, yaml, glob
import zmq_controler as zmqctrl
from nested_lookup import nested_delete, nested_update
from itertools import chain
from nested_dict import nested_dict
import numpy as np
from time import sleep
sys.path.append('analysis/level0')
from plot_calib_probedc import plot_calibdac, plot_probeDC

def scan_calibdac(i2csocket, dc_range):
    v = {}
    for val in dc_range:
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib']=val # *4 depending of the loop
        print(nestedConf)
        
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        v[val] = i2csocket.measadc(dict())

    return v
        

def scan_probedc(i2csocket, probe_points, dc_range, dc_names):
    v = {}
    for dc_value, name in zip(dc_range, dc_names):
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc']= dc_value
        print(name, nestedConf)
        
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        v[name] = i2csocket.measadc(dict())

    return v

def scan_channels(i2csocket, ch_ranges, keithley_h0=None, keithley_h1=None):
    ret = nested_dict()
    for ch in ch_ranges:
        val = "ch" + str(ch)
        if keithley_h0 != None:
            keithley_h0.channel = val
            keithley_h0.trigger()
        if keithley_h1 != None:
            keithley_h1.channel = val
            keithley_h1.trigger()
        # give keithleys time to measure before reconfiguring ROC.
        sleep(0.3)  # For using one adapter + Multi-con cable (MODE 1)
        # sleep(0.1)  # For using two adapters (MODE 2)

    return ret.to_dict()


def probeDC_run(i2csocket, basedir, device_name, single_chip=True):

    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in probeDC_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    testName = "calib_probedc_run"
    odir = "%s/%s/calib_probedc_run/run_%s/"%( os.path.realpath(basedir), device_name, timestamp )

    os.makedirs(odir)

    initial_full_config={}
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            initial_full_config[key] = i2csocket.yamlConfig[key]

    # initialize the DAC chip on the trophy board
    test_cfg = {
        "Trophy_version": "TrophyV3",
        "bus": 3,
        "i2c_address": 0x45,
        "conf_registers": [0b0, 0b0, 0b0, 0b0],
    }
    i2csocket.initialize_adc(test_cfg)

    #probe calibDAC on the hexaboard chips
    #the two halves of the three chips are probed sequentially because 
    # they are connected to the same probing point
    ret = nested_dict()
    num_rocs = 0
    for ihalf in range(2):
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():            
            if key.find('roc_s')==0:
                roc_idx = int(key[5])
                if roc_idx > num_rocs:
                    num_rocs = roc_idx
                nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest']=1
                nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc1']=0
                if ihalf==0:
                    nestedConf[key]['sc']['ReferenceVoltage'][0]['probe_dc2']=1
                    nestedConf[key]['sc']['ReferenceVoltage'][1]['probe_dc2']=0
                else:
                    nestedConf[key]['sc']['ReferenceVoltage'][0]['probe_dc2']=0
                    nestedConf[key]['sc']['ReferenceVoltage'][1]['probe_dc2']=1
        print(nestedConf)
        i2csocket.configure(yamlNode=nestedConf.to_dict())

        # run the calibdac scan
        dc_range = [0] + [2**n for n in range(0,12)] + [4095]
        ##########################################
        # TMP
        v = scan_calibdac(i2csocket, dc_range)


        #for each caliddac value we have a measurement in four probe points
        for calibDAC, probed_values in v.items():
            for iprobe in range(num_rocs+1):
                val = probed_values[iprobe+1]
                roclabel = "roc_s%i"%(iprobe)
                ret["node"]["calib"][roclabel]["half"+str(ihalf)][calibDAC] = val
        ##########################################

    #save the results
    ret1 = ret.to_dict()
    plot_calibdac(ret1,odir)
    with open(odir + "/calibdac.yaml", "w") as fout:
        yaml.dump(ret1, fout)
    print('\ncalibdac scan completed\n')
    #reset the probe dc settings 
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc2']=0
            nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest']=0
            nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib']=0
    
    i2csocket.configure(yamlNode=nestedConf.to_dict())
    
    ############################################################################

    #now scan probe_dc1 values
    dc_range = range(32)

    dc1_names = ["vbi_pa", "vbm_pa", "vbm2_pa", "vbm3_pa", "vbo_pa", "vb_inputdac",
                 "vbi_discri_tot", "vbm_discri_tot", "vbo_discri_tot", "vbi_discri_toa",
                 "vcasc_discri_toa", "vbm1_discri_toa", "vbm2_discri_toa", "vbo_discri_toa",
                 "EXT_REF_TDC", "probe_VrefCf", "vcn", "VD_FTDC_P_EXT", "VD_CTDC_P_EXT",
                 "probe_VrefPa", "vcp", "VD_FTDC_N_EXT", "VD_CTDC_N_EXT", "vb_hyst_tot", "vbi_itot_neg",
                 "vbi_itot_pos", "vbiN_sk", "vbiP_sk", "vbFCN_sk", "vbFCP_sk", "vbiN_noinv", "vbiP_noinv"]

    dc2_names = ["vbFCN_noinv", "vbFCP_noinv", "vbiN_inv", "vbip_inv", "vbFCN_inv", "vbFCP_inv", "vbiN_noinv_buf",
                 "vbiP_noinv_buf", "vbFCN_noinv_buf", "vbFCP_noinv_buf", "vbiN_inv_buf", "vbFCP_inv_buf",  
                 "vbiP_inv_buf", "vbFCN_inv_buf", "vb_5bdac_out_inv", "vb_5bdac_tot", "vb_5bdac_toa",
                 "vcm_0p6_inv", "vcm_0p6_noinv", "vref_adc", "vcm_adc", "Vref_sk", "Vref_noinv", "Vref_inv", 
                 "Vref_tot", "Vref_toa", "vbg_1v", "probe_center", "ibi_ref_adc", "ibo_ref_adc", "probe_vddd", 
                 "probe_vdda"]

    # configure rocs of a specific half and run the scan
    ret = nested_dict()
    for ihalf in range(2):
        for idc in range(2):
            nestedConf = nested_dict()
            for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                    if ihalf==0:
                        nestedConf[key]['sc']['ReferenceVoltage'][0]['probe_dc1']=idc+1
                        nestedConf[key]['sc']['ReferenceVoltage'][1]['probe_dc1']=0
                    else:
                        nestedConf[key]['sc']['ReferenceVoltage'][0]['probe_dc1']=0
                        nestedConf[key]['sc']['ReferenceVoltage'][1]['probe_dc1']=idc+1
                    nestedConf[key]['sc']['ch'][10]['probe_inv']=1
                    nestedConf[key]['sc']['ch'][10]['probe_noinv']=1
                    nestedConf[key]['sc']['ch'][46]['probe_inv']=1
                    nestedConf[key]['sc']['ch'][46]['probe_noinv']=1
                    
                    #####################################
                    # TMP to debug vref inv
                    #nestedConf[key]['sc']['ReferenceVoltage']['all']['Noinv_vref']=700
                    #####################################


            print(nestedConf)
            
            i2csocket.configure(yamlNode=nestedConf.to_dict())
            if idc == 0:
                probe_points = dc1_names
            else:
                probe_points = dc2_names

            # take data from probes on the ADC
            v = scan_probedc(i2csocket, probe_points, dc_range, probe_points)

            for name, probed_values in v.items():
                for iprobe in range(num_rocs+1):
                    val = probed_values[iprobe+1]
                    roclabel = "roc_s%i"%(iprobe)
                    ret["node"][name][roclabel]["half"+str(ihalf)] = val
            
    ret1 = ret.to_dict()
    fname = "dc%i_probe" %(idc+1)
    plot_probeDC(ret1,odir)
    with open(odir + "/" + fname  + ".yaml", "w") as fout:
        yaml.dump(ret1, fout)
    print('\nprobeDC scan completed\n')
    exit()

        ## scanning jr and jl channels from 2 to 8
    '''
        jl_names = ["ADCp_L", "ADCn_L", "vddd1", "vddd2_L", "vddd_L", "NC_L", "IN_V"]
        jr_names = ["ADCp_R", "ADCn_R", "vdd_pll", "vdd_sc", "vddd_R", "vddd2_R", "VGN_R"]

        ch_range = range(2,9)
        buf_size = len(ch_range)
        print("buf_size", buf_size)
        jl.config_buffer(buf_size)
        jr.config_buffer(buf_size)
        scan_channels(i2csocket, ch_range, keithley_h0=jl, keithley_h1=jr)

        print("Start waiting for buffer")
        jl.wait_for_buffer()
        jr.wait_for_buffer()
        print("Stop waiting for buffer")
            
        jl_ret = jl.buffer_data
        jr_ret = jr.buffer_data

        ret = nested_dict()
        for name, h0_pt in zip(jl_names, jl_ret):
            ret["node"][str(name)] = float(abs(h0_pt))
        for name, h0_pt in zip(jr_names, jr_ret):
            ret["node"][str(name)] = float(abs(h0_pt))

        ret1 = ret.to_dict()
        fname = "jljr_scan"
        with open(odir + "/" + fname  + ".yaml", "w") as fout:
            yaml.dump(ret1, fout)
    '''
    '''
        ## scanning ja (analog) channels from 1 to 10

        ja_names = ["vdd_tdc_L","vdd_buf_L","vdd_adc_L","vdd_sk_L","vdd_dac_L","vdd_tdc_R","vdd_adc_R","vdd_buf_R","vdd_sk_R","vdd_dac_R"]

        ch_range = range(1,11)
        buf_size = len(ch_range)
        print("buf_size", buf_size)
        ja.config_buffer(buf_size)
        scan_channels(i2csocket, ch_range, keithley_h0=ja, keithley_h1=None)

        print("Start waiting for buffer")
        ja.wait_for_buffer()
        print("Stop waiting for buffer")
            
        ja_ret = ja.buffer_data

        ret = nested_dict()
        for name, h0_pt in zip(ja_names, ja_ret):
            ret["node"][str(name)] = float(abs(h0_pt))

        ret1 = ret.to_dict()
        fname = "ja_scan"
        with open(odir + "/" + fname  + ".yaml", "w") as fout:
            yaml.dump(ret1, fout)
    '''
    '''
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc1']=0
                nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc']=0
                # nestedConf[key]['sc']['ch'][10]['probe_inv']=0
                # nestedConf[key]['sc']['ch'][10]['probe_noinv']=0
                # nestedConf[key]['sc']['ch'][46]['probe_inv']=0
                # nestedConf[key]['sc']['ch'][46]['probe_noinv']=0
            print(nestedConf)
        
        i2csocket.configure(yamlNode=nestedConf.to_dict())

        

    else:  # Multi-chip 
        ret1 = scan_probedc(i2csocket, dc1_names, dc1_range, dc1_name)
        ret2 = scan_probedc(i2csocket, dc2_names, dc2_range, dc2_name)
    '''

def main():
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
    
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    i2csocket.initialize()
    i2csocket.configure()
    probeDC_run(i2csocket,options.odir,options.dut)

if __name__ == "__main__":
    main()
