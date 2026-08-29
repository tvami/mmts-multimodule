import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier, util
import analysis.level0.tot_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict
import numpy as np

def scan(i2csocket, daqsocket, startthr, stopthr, nstep, injectedChannels,odir,keepRawData=0) :
        testName = 'tot_threshold_scan'
        calib_dac_val=400
        index = 0
        for tot_val in range(startthr, stopthr, nstep) :
                nestedConf = nested_dict()
                for key in i2csocket.yamlConfig.keys() :
                        if key.find('roc_s') == 0 :
                                nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref'] = int(tot_val)
                i2csocket.configure(yamlNode=nestedConf.to_dict())
                i2csocket.configure_injection(injectedChannels, activate=1, gain=0, calib_dac=calib_dac_val)
                util.acquire_scan(daq=daqsocket)
                chip_params = {'Tot_vref' : tot_val,'injectedChannels':injectedChannels[0]}
                util.saveMetaYaml(odir=odir, i2c=i2csocket, daq=daqsocket, runid=index, testName=testName, keepRawData=keepRawData, chip_params=chip_params)
                index = index + 1
        i2csocket.configure_injection(injectedChannels, activate=0, gain=0, calib_dac=0) #maybe we should go back to phase 0
        return

def scan_trimTot(i2csocket, daqsocket, odir,chan,keepRawData=0):
        testName = 'tot_trim_scan'
        calib_dac_val=400
        tot_vals = [i for i in range(0,32,2)] + [31]
        injectedChannels = [chan,chan+18,chan+36,chan+36+18]
        index=0
        for tot_val in tot_vals:
                nestedConf = nested_dict()
                for key in i2csocket.yamlConfig.keys():
                        if key.find('roc_s')==0:
                                nestedConf[key]['sc']['ch'][chan]['trim_tot']=tot_val
                                nestedConf[key]['sc']['ch'][chan+18]['trim_tot']=tot_val
                                nestedConf[key]['sc']['ch'][chan+36]['trim_tot']=tot_val
                                nestedConf[key]['sc']['ch'][chan+36+18]['trim_tot']=tot_val
                i2csocket.configure(yamlNode=nestedConf.to_dict())

                i2csocket.configure_injection(injectedChannels, activate=1, gain=0, calib_dac=calib_dac_val)
                util.acquire_scan(daq=daqsocket)
                chip_params = { 'trim_tot':tot_val, 'injectedChannels':chan}
                util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,runid=index,testName=testName,keepRawData=keepRawData,chip_params=chip_params)
                index+=1
        i2csocket.configure_injection(injectedChannels, activate=0, gain=0, calib_dac=0) #maybe we should go back to phase 0
        return


def tot_threshold_scan(i2csocket, daqsocket, clisocket, basedir, device_name, injectionConfig, suffix=''):
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
        odir = "%s/%s/tot_threshold_scan/run_%s/"%(os.path.realpath(basedir), device_name, timestamp)
        os.makedirs(odir)
        
        #####  Setting trim_tot for all channels to 15
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                        nestedConf[key]['sc']['ch']['all']['trim_tot']=15
                        nestedConf[key]['sc']['cm']['all']['trim_tot']=15
                        nestedConf[key]['sc']['calib']['all']['trim_tot']=15
        i2csocket.configure(yamlNode=nestedConf.to_dict())
	###############################################
        for ch in range(18):
                rundir = odir + "start_chan_%i" %ch
                os.makedirs(rundir)
                mylittlenotifier = myinotifier.mylittleInotifier(odir=rundir)
                mylittlenotifier.start()
                calibreqA            = 0x10
                BXoffset			= injectionConfig['BXoffset']

                clisocket.yamlConfig['global']['outputDirectory'] = rundir
                clisocket.yamlConfig['global']['run_type'] = "tot_threshold_scan"
                clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
                clisocket.configure()

                daqsocket.yamlConfig['daq']['NEvents']='63'
                daqsocket.yamlConfig['daq']['Number_of_events_per_readout'] = '63'
                daqsocket.enable_fast_commands(A=1)
                daqsocket.l1a_generator_settings(name='A',BX=calibreqA,length=1,cmdtype='CALIBREQ',prescale=0,followMode='DISABLE')
                daqsocket.l1a_generator_settings(name='B',BX=calibreqA+BXoffset,length=1,cmdtype='L1A',prescale=0,followMode='A')
                daqsocket.configure()

                util.saveFullConfig(odir=odir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
                clisocket.start()
                chan = ch
                injectedChannels = [chan,chan+18,chan+36,chan+36+18]
                scan(i2csocket, daqsocket, 150, 300, 2, injectedChannels, rundir,keepRawData=0)
                clisocket.stop()
                mylittlenotifier.stop()
	
        tot_threshold_analyzer = analyzer.tot_scan_analyzer(odir=odir)
        folders = glob.glob(odir+"start_chan_*/")
        for folder in folders:
                files = glob.glob(folder+"/*.root")
                for f in files[:]:
                        tot_threshold_analyzer.add(f)
        tot_threshold_analyzer.mergeData()
        tot_threshold_analyzer.makePlot()
        nestedConf = tot_threshold_analyzer.determineTot_vref()
        i2csocket.configure(yamlNode= nestedConf.to_dict())



        ## Trimmed_dac scan ####################################################
        for ch in range(18):
                rundir = odir + "chan_%i" %ch
                os.makedirs(rundir)
                mylittlenotifier = myinotifier.mylittleInotifier(odir=rundir)
                mylittlenotifier.start()
                
                clisocket.yamlConfig['global']['outputDirectory'] = rundir
                clisocket.yamlConfig['global']['run_type'] = "tot_trim_scan"
                clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
                clisocket.configure()

                daqsocket.yamlConfig['daq']['NEvents']='63'
                daqsocket.yamlConfig['daq']['Number_of_events_per_readout'] = '63'
                daqsocket.enable_fast_commands(A=1)
                daqsocket.l1a_generator_settings(name='A',BX=calibreqA,length=1,cmdtype='CALIBREQ',prescale=0,followMode='DISABLE')
                daqsocket.l1a_generator_settings(name='B',BX=calibreqA+BXoffset,length=1,cmdtype='L1A',prescale=0,followMode='A')
                daqsocket.configure()

                util.saveFullConfig(odir=rundir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
                clisocket.start()

                scan_trimTot(i2csocket, daqsocket,rundir,ch,keepRawData=0)
                clisocket.stop()
                mylittlenotifier.stop()


        tot_trim_analyzer = analyzer.tot_scan_analyzer(odir=odir)
        folders = glob.glob(odir+"chan_*/")
        for folder in folders:
                files = glob.glob(folder+"/*.root")
                for f in files[:]:
                        tot_trim_analyzer.add(f)
        tot_trim_analyzer.mergeData()
        tot_trim_analyzer.makePlot_trim()
        tot_trim_analyzer.determineTot_trim()
        i2csocket.update_yamlConfig(fname=odir+'/trimmed_tot.yaml')
        i2csocket.configure(fname=odir+'/trimmed_tot.yaml')


	###############################################
        for ch in range(18):
                rundir = odir + "final_chan_%i" %ch
                os.makedirs(rundir)
                mylittlenotifier = myinotifier.mylittleInotifier(odir=rundir)
                mylittlenotifier.start()

                clisocket.yamlConfig['global']['outputDirectory'] = rundir
                clisocket.yamlConfig['global']['run_type'] = "tot_threshold_scan"
                clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
                clisocket.configure()

                daqsocket.yamlConfig['daq']['NEvents']='63'
                daqsocket.yamlConfig['daq']['Number_of_events_per_readout'] = '63'
                daqsocket.enable_fast_commands(A=1)
                daqsocket.l1a_generator_settings(name='A',BX=calibreqA,length=1,cmdtype='CALIBREQ',prescale=0,followMode='DISABLE')
                daqsocket.l1a_generator_settings(name='B',BX=calibreqA+BXoffset,length=1,cmdtype='L1A',prescale=0,followMode='A')
                daqsocket.configure()

                util.saveFullConfig(odir=rundir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
                clisocket.start()
                chan = ch
                injectedChannels = [chan,chan+18,chan+36,chan+36+18]
                scan(i2csocket, daqsocket, 150, 300, 2, injectedChannels, rundir,keepRawData=0)
                clisocket.stop()
                mylittlenotifier.stop()
	
        tot_threshold_analyzer = analyzer.tot_scan_analyzer(odir=odir)
        folders = glob.glob(odir+"final_chan_*/")
        for folder in folders:
                files = glob.glob(folder+"/*.root")
                for f in files[:]:
                        tot_threshold_analyzer.add(f)
        tot_threshold_analyzer.mergeData()
        tot_threshold_analyzer.makePlot("final")


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
	
