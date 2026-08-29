import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

from level0.analyzer import *
import myinotifier, util
import analysis.level0.tot_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict
import numpy as np

def scan(i2csocket, daqsocket, startthr, stopthr, nstep, injectedChannels,max_calib,odir,keepRawData=0) :
        testName = 'adc_range_setting'
        calib_dac_val=int(max_calib)
        index = 0
        for tot_val in range(startthr, stopthr, nstep) :
                nestedConf = nested_dict()
                for key in i2csocket.yamlConfig.keys() :
                        if key.find('roc_s') == 0 :
                                nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref'] = int(tot_val)
                i2csocket.configure(yamlNode=nestedConf.to_dict())
                i2csocket.configure_injection(injectedChannels, activate=1, gain=0, calib=calib_dac_val)
                util.acquire_scan(daq=daqsocket)
                chip_params = {'Tot_vref' : tot_val,'injectedChannels':injectedChannels[0]}
                util.saveMetaYaml(odir=odir, i2c=i2csocket, daq=daqsocket, runid=index, testName=testName, keepRawData=keepRawData, chip_params=chip_params)
                index = index + 1
        i2csocket.configure_injection(injectedChannels, activate=0, gain=0, calib=0) #maybe we should go back to phase 0
        return


def adc_range_setting(i2csocket, daqsocket, clisocket, basedir, device_name, injectionConfig, max_calib,suffix=''):
        if type(i2csocket) != zmqctrl.i2cController :
                print("ERROR in pedestal_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)))
                sleep(1)
                return

        if type(daqsocket) != zmqctrl.daqController :
                print("ERROR in pedestal_run : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)))
                sleep(1)
                return	

        if type(clisocket) != zmqctrl.daqController :
                print("ERROR in pedestal_run : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)))
                sleep(1)
                return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if suffix:
                timestamp = timestamp + "_" + suffix
        odir = "%s/%s/adc_range_setting/run_%s/"%(os.path.realpath(basedir), device_name, timestamp)
        os.makedirs(odir)
        
        mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
        mylittlenotifier.start()
        calibreqA            = 0x10
        BXoffset			= injectionConfig['BXoffset']

        clisocket.yamlConfig['global']['outputDirectory'] = odir
        clisocket.yamlConfig['global']['run_type'] = "adc_range_setting"
        clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
        clisocket.configure()
        
        daqsocket.yamlConfig['daq']['NEvents']='500' # 1000 by default
        daqsocket.enable_fast_commands(0,0,0) ## disable all non-periodic gen L1A sources 
        daqsocket.l1a_generator_settings(name='A',enable=1,BX=calibreqA,length=1,flavor='CALPULINT',prescale=0,followMode='DISABLE')
        daqsocket.l1a_generator_settings(name='B',enable=1,BX=calibreqA+BXoffset,length=1,flavor='L1A',prescale=0,followMode='A')
        daqsocket.configure()

        util.saveFullConfig(odir=odir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
        clisocket.start()
        chan = 5
        injectedChannels = [chan,chan+18,chan+36,chan+36+18]
        scan(i2csocket, daqsocket, 350, 650, 2, injectedChannels,max_calib, odir,keepRawData=1)
        clisocket.stop()
        mylittlenotifier.stop()
	
        tot_threshold_analyzer = analyzer.tot_scan_analyzer(odir=odir)
        files = glob.glob(odir+"/*.root")
        for f in files[:]:
                r_summary = reader(f)
                r_raw = rawroot_reader(f)
                r_raw.df['Tot_vref'] = r_summary.df.Tot_vref.unique()[0]
                r_raw.df['injectedChannels'] = r_summary.df.injectedChannels.unique()[0]
                tot_threshold_analyzer.dataFrames.append(r_raw.df)
        tot_threshold_analyzer.mergeData()
        tot_threshold_analyzer.makePlot()
        nestedConf = tot_threshold_analyzer.determineTot_vref()
        with open(odir+'/trimmed_adc_range.yaml','w') as fout:
                yaml.dump(nestedConf.to_dict(),fout)
        i2csocket.update_yamlConfig(fname=odir+'/trimmed_adc_range.yaml')
        i2csocket.configure(yamlNode= nestedConf.to_dict())


        return odir

if __name__ == "__main__" :
	from optparse import OptionParser
	parser = OptionParser()

	parser.add_option("-d", "--dut", dest="dut", help="device under test")

	parser.add_option("-i", "--hexaIP", action="store", dest="hexaIP", help="IP addres of the zynq on the hexactrl board")

	parser.add_option("-f", "--configFile", default="./configs/init.yaml", action="store", dest="configFile", help="initial configuration yaml file")	

	parser.add_option("-o", "--odir", action="store", dest="odir", default='./data', help="output bas directory")

	parser.add_option("--daqPort", action="store", dest="daqPort", default='6000', help="port of the zynq waiting for daq config and commands (configure/start/stop/is_done)")

	parser.add_option("--i2cPort", action="store", dest="i2cPort", default='5555', help="port of the zynq waiting for I2C config and commands (initialize/configure/read_pwr,read/measadc)")

	parser.add_option("--pullerPort", action="store", dest="pullerPort", default='6001', help="port of the client PC (loccalhost for the moment) waiting for daq config and commands (configure/start/stop)")

	(options, args) = parser.parser_args()
	print (options)

	daqsocket = zmqctrl.daqController(options.hexaIP, options.daqPort, options.configFile)
	clisocket = zmqctrl.daqController("localhost", options.pullerPort, options.configFile)
	i2csocket = zmqctrl.i2cController(options.hexaIP, options.i2cPort, options.configFile)

	i2csocket.configure()
	toa_threshold_scan(i2csocket, daqsocket, clisocket, options.odir, options.dut)
	
