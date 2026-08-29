import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.injection_run_analysis as analyzer
import zmq_controler as zmqctrl

def injection_run(i2csocket,daqsocket, clisocket, basedir,device_name, injectionConfig):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in pedestal_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return

    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in pedestal_run : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return

    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in pedestal_run : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    testName="injection_run"
    odir = "%s/%s/injection_run/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()
    
    phase=injectionConfig['phase']
    BXoffset=injectionConfig['BXoffset']
    gain = injectionConfig['gain'] # 0 for low range ; 1 for high range
    globalTotThr = injectionConfig['globalTotThr']
    globalToaThr = injectionConfig['globalToaThr']
    calib_dac = injectionConfig['calib_dac'] # 
    injectedChannels=injectionConfig['injectedChannels']

    clisocket.yamlConfig['global']['outputDirectory'] = odir
    clisocket.yamlConfig['global']['run_type'] = "injection_run"
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.configure()

    daqsocket.yamlConfig['daq']['NEvents']='10000'
    daqsocket.enable_fast_commands(A=1,B=1)
    daqsocket.l1a_generator_settings(name='A',BX=10,length=1,cmdtype='CALIBREQ',prescale=0,followMode='DISABLE')
    daqsocket.l1a_generator_settings(name='B',BX=10+BXoffset,length=1,cmdtype='L1A',prescale=0,followMode='A')
    daqsocket.configure()

    chip_params={}
    chip_params['Phase'] = phase
    chip_params['BXoffset'] = BXoffset
    chip_params['Calib_dac'] = calib_dac
    chip_params['Inj_gain'] = gain
    chip_params['Tot_vref'] = globalTotThr
    chip_params['Toa_vref'] = globalToaThr
    chip_params['injectedChannels'] = injectedChannels
    util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,runid=0,testName=testName,keepRawData=1,chip_params=chip_params)

    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            i2csocket.yamlConfig[key]['sc']['ReferenceVoltage']['all']['IntCtest'] = 1
            i2csocket.yamlConfig[key]['sc']['ReferenceVoltage']['all']['Calib_dac'] = calib_dac
            i2csocket.yamlConfig[key]['sc']['ReferenceVoltage']['all']['Tot_vref'] = globalTotThr
            i2csocket.yamlConfig[key]['sc']['ReferenceVoltage']['all']['Toa_vref'] = globalToaThr
            i2csocket.yamlConfig[key]['sc']['Top']['all']['Phase']=phase
            for injectedChannel in injectedChannels:
                if injectedChannel in i2csocket.yamlConfig[key]['sc']['ch'].keys():
                    if gain==0:
                        i2csocket.yamlConfig[key]['sc']['ch'][injectedChannel]['LowRange'] = 1
                        i2csocket.yamlConfig[key]['sc']['ch'][injectedChannel]['HighRange'] = 0
                    else:
                        i2csocket.yamlConfig[key]['sc']['ch'][injectedChannel]['LowRange'] = 0
                        i2csocket.yamlConfig[key]['sc']['ch'][injectedChannel]['HighRange'] = 1
                else:
                    if gain==0:
                        i2csocket.yamlConfig[key]['sc']['ch'][injectedChannel] = {
                            'LowRange' : 1, 
                            'HighRange' : 0 
                        }
                    else:
                        i2csocket.yamlConfig[key]['sc']['ch'][injectedChannel] = {
                            'LowRange' : 0 ,
                            'HighRange' : 1 
                        }
    i2csocket.configure()
    i2csocket.resettdc()
    
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)    	
    
    util.acquire(daq=daqsocket, client=clisocket)
    mylittlenotifier.stop()
    
    run_analyzer = analyzer.injection_run_analyzer(odir=odir)
    files = glob.glob(odir+"/*.root")

    for f in files:
    	run_analyzer.add(f)

    run_analyzer.mergeData()
    run_analyzer.makePlots(chip_params)

    # return to no injection setting
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            i2csocket.yamlConfig[key]['sc']['Top']['all']['Phase'] = 0
            i2csocket.yamlConfig[key]['sc']['ReferenceVoltage']['all']['IntCtest'] = 0
            i2csocket.yamlConfig[key]['sc']['ReferenceVoltage']['all']['Calib_dac'] = 0
            i2csocket.yamlConfig[key]['sc']['ReferenceVoltage']['all']['Tot_vref'] = 432 # default value
            i2csocket.yamlConfig[key]['sc']['ReferenceVoltage']['all']['Toa_vref'] = 112 # default value
            for injectedChannel in injectedChannels:
                i2csocket.yamlConfig[key]['sc']['ch'][injectedChannel]['LowRange'] = 0
                i2csocket.yamlConfig[key]['sc']['ch'][injectedChannel]['HighRange'] = 0
    i2csocket.configure()
	
    return odir


def main():
	base_directory = "./data/"
	device_name = "test"
	hexactrl = "hexactrl574301"
	print(sys.argv)
	if len(sys.argv) > 1:
		device_name = str(sys.argv[1])
		print("## device %s under test" %device_name)
	if len(sys.argv) > 2:
		hexactrl = str(sys.argv[2])
		print("## hexactrl %s under test" %hexactrl)
		
	daqsocket = zmqctrl.daqController(hexactrl,"6000","./configs/init.yaml")
	clisocket = zmqctrl.daqController("localhost","6001","./configs/init.yaml")
	i2csocket = zmqctrl.i2cController(hexactrl,"5555","./configs/init.yaml")

	i2csocket.initialize()

	injectionConfig = {
		'phase' : 13,
		'BXoffset' : 19,
		'gain' : 0,
		'globalTotThr' : 150,
		'globalToaThr' : 100,
		'calib_dac' : 1000,
		'injectedChannels' : [10,30,49,69]
	}

	injection_run(i2csocket,daqsocket,clisocket,base_directory,device_name,injectionConfig)

if __name__ == "__main__":
		
	main()
