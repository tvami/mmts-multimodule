import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.pedestal_run_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict 

def pedestal_run(i2csocket,daqsocket, clisocket, basedir,device_name,suffix="",logging_level='INFO',i2cRead=False):
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
    if suffix:
        timestamp = timestamp + "_" + suffix
    testName = "pedestal_run"
    odir = "%s/%s/pedestal_run/run_%s/"%( os.path.realpath(basedir), device_name, timestamp )
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir,logging_level=logging_level)
    mylittlenotifier.start()
    
    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = testName
    clisocket.configure()
    daqsocket.yamlConfig['daq']['active_menu']='randomL1A'
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['NEvents']=10000
    # L1A rate.  log2 period 0 = the fastest random rate the generator can do;
    # with bx_min=45 that is ~890 kHz, and the fastcontrol counter shows ~960k
    # L1As issued for a 10k-event run (measured 2026-08-25).  On this bench that
    # coincides with ~100 % of half-ROC packets failing the 0x5 header check,
    # which is what an overrun readout looks like.  The default is therefore 10,
    # which is what the config's own randomL1A menus already use; the old default
    # of 0 meant every run launched without MMTS_L1A_LOG2PERIOD reproduced that
    # corruption.  Set MMTS_L1A_LOG2PERIOD=0 to get the old behaviour back.
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['log2_rand_bx_period']=int(
        os.environ.get('MMTS_L1A_LOG2PERIOD', 10))
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['bx_min']=45
    daqsocket.configure()


    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,runid=0,testName=testName,keepRawData=1,chip_params={})

    if i2cRead:
        rocs = [f'roc_s{toread}' for toread in i2cRead]
        print({roc: i2csocket.yamlConfig[roc] for roc in rocs})
        i2csocket.read_loop({roc: i2csocket.yamlConfig[roc] for roc in rocs})
        sleep(2)

    util.acquire(daq=daqsocket, client=clisocket)
    mylittlenotifier.stop()

    if i2cRead:
        i2csocket.break_loop()

    try:
        ped_analyzer = analyzer.pedestal_run_analyzer(odir=odir)
        files = glob.glob(odir+"/*.root")
    	
        for f in files:
    	    ped_analyzer.add(f)

        ped_analyzer.mergeData()
        ped_analyzer.makePlots()

        # ped_analyzer.extractTPGConfig()
        # i2csocket.update_yamlConfig(fname=odir+'/pedestal_thresh_config.yaml')
        # i2csocket.configure(fname=odir+'/pedestal_thresh_config.yaml')
    except Exception as e:
         with open(odir+"crash_report.log","w") as fout:
            fout.write("pedestal_run analysis went wrong and crash\n")
            fout.write("Error {0}\n".format(str(e)))

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
    
    parser.add_option("-s", "--suffix",
                      action="store", dest="suffix",default='',
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

    parser.add_option("--i2cRead",
                      type = str, 
                      action="store", dest="i2cRead",
                      help="set to trigger a i2c reading loop during the acquisition (args: comma separated chip numbers")

    parser.add_option('-L', "--logging_level", dest='logging_level', action='store', default='INFO',
                        help='logging level; choices : NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL')

    (options, args) = parser.parse_args()
    print(options)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile,logging_level=options.logging_level)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile,logging_level=options.logging_level)
    clisocket.yamlConfig['client']['serverIP'] = options.hexaIP
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)

    if options.initialize==True:
        i2csocket.initialize()
        daqsocket.initialize()
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
    else:
        i2csocket.configure()

    i2cRead = None
    if options.i2cRead:
        i2cRead = options.i2cRead.split(",") 

    pedestal_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,suffix=options.suffix,logging_level=options.logging_level,i2cRead=i2cRead)





