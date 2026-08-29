import zmq, datetime,  os, subprocess, sys, yaml, glob
import myinotifier,util
import dump_run_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict 

def dump_run(i2csocket,daqsocket, clisocket, basedir, device_name, nruns = 1):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in dump_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return
    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in dump_run : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return
    
    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in dump_run : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    testName = "dump_run"
    odir = "%s/%s/dump_run/run_%s/"%( os.path.realpath(basedir), device_name, timestamp )
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()
    
    # client socket configuration
    clisocket.yamlConfig['global']['outputDirectory'] = odir
    clisocket.yamlConfig['global']['run_type'] = testName
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.configure()

    # daq socket configuration
    daqsocket.yamlConfig['daq']['NEvents']= 512
    daqsocket.yamlConfig['daq']['Number_of_events_per_readout'] = '512'
    daqsocket.l1a_generator_settings(name='A', BX = 10, length = 43*512, cmdtype = 'DUMP', prescale = 200, followMode = 'DISABLE')
    daqsocket.enable_fast_commands(A=1)
    daqsocket.l1a_settings(bx_spacing=43)
    daqsocket.configure()

    # i2c socket configuration
    ref_adc = 0x3ff
    L1Offset = 500
    i2csocket.yamlConfig['roc_s0']['sc']['DigitalHalf']['all']['L1Offset'] = L1Offset
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['GlobalAnalog']['all']['SelExtADC'] = 1
            nestedConf[key]['sc']['ch']['all']['ExtData']= ref_adc
            nestedConf[key]['sc']['cm']['all']['ExtData']= ref_adc
            nestedConf[key]['sc']['calib']['all']['ExtData']= ref_adc

    i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    i2csocket.configure()

    util.saveFullConfig(odir = odir,i2c = i2csocket, daq = daqsocket, cli = clisocket)
    
    clisocket.start()

    for run in range(nruns):
        chip_params = {'Ref_adc': ref_adc, 'Run': run}
        util.saveMetaYaml(odir = odir, i2c = i2csocket, daq = daqsocket, runid = run, testName = testName, keepRawData = 1, chip_params = chip_params)
        util.acquire_scan(daq=daqsocket)

    clisocket.stop()
    mylittlenotifier.stop()

    # turn the setting of ADC off
    i2csocket.yamlConfig['roc_s0']['sc']['GlobalAnalog']['all']['SelExtADC'] = 0
    i2csocket.configure()
 
    dump_analyzer = analyzer.dump_run_analyzer(odir=odir, treename = 'unpacker_data/hgcroc')
    files = glob.glob(odir+"/*.root")
    	
    for f in files:
    	dump_analyzer.add(f)
    
    dump_analyzer.mergeData()
    #dump_analyzer.data.to_hdf('temp/new_dump.h5', key = 'dump_run')
    dump_analyzer.add_bit_error_count()
    dump_analyzer.makePlots()

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
    
    
    (options, args) = parser.parse_args()
    print(options)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    i2csocket.configure()
    dump_run(i2csocket,daqsocket,clisocket,options.odir,options.dut, nruns = 10)
