import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier # needed to trigger unpacker 
import template_scan_analysis as analyzer # analyzer script, it can produce plots and/or new (optmized) configuration
import zmq_controler as zmqctrl # controler objects : it controls the zmq sockets and contains the configurations (ROC config and software config)

from nested_dict import nested_dict # used to generate dictionary with partial ROC config

def scan(i2csocket, daqsocket, start, stop, step, odir): #the options of a scan might be different e.g.: sampling_scan.py, injection_scan.py

    # openning the template meta yaml file
    with open('./configs/meta.yaml') as fin:
        meta_yaml = yaml.safe_load(fin)
    	
    # modifying the meta yaml according to the current test
    meta_yaml['metaData']['hexactrl'] = i2csocket.ip
    meta_yaml['metaData']['NEvents']  = daqsocket.yamlConfig['daq']['NEvents']
    meta_yaml['metaData']['L1Atype']  = daqsocket.yamlConfig['daq']['L1A_type']
    nrocs = len( [key for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ] )
    meta_yaml['metaData']['hw_type']  = 'HD' if nrocs==6 else 'LD' if nrocs==3 else '1ROC' if nrocs==1 else 'unknown'
    ###
    meta_yaml['metaData']['testName'] = 'TESTNAME' ## to be changed accordingly
    meta_yaml['metaData']['keepRawData'] = 0 ## to be decided if 0 or 1 (0 : for having only the pre-analysed ntuple ; 1 : for also having the ntuple with 1 entry per channel per event)
    ###
    metaFileBaseName = odir + "/" + meta_yaml['metaData']['testName']


    ##scanning loop starts here
    index=0
    for param_val in range(start,stop,step): #loop on the values of the ROC params
        # preparing partial config
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                # example for Inv_vref:
                nestedConf[key]['sc']['ReferenceVoltage'][0]['Inv_vref']=param_val
                nestedConf[key]['sc']['ReferenceVoltage'][1]['Inv_vref']=param_val
                # example for new phase setting:
                nestedConf[key]['sc']['Top']['all']['Phase']=PHASE_value
                # example for new injection charge setting:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib_dac']=calibDAC_val
                # example for new tdc threshold values:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Toa_vref']=int(toa_threshold)
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref']=int(tot_threshold)
                # ....
        i2csocket.configure(yamlNode=nestedConf.to_dict()) #configuring the ROCs with the partial config
        daqsocket.start() # starting the data taking run 
        while True:
            if daqsocket.is_done() == True:
                break
            else:
                sleep(0.01)
        daqsocket.stop() # stopping the run (might be useless in fact, the run is actually stopping by itself once it reaches NEvents)

        # save the meta yaml file
        meta_yaml['metaData']['chip_params'] = {'Inv_vref' : param_val}
        # or :
        meta_yaml['metaData']['chip_params'] = {'Calib_dac' : calibDAC_val}
        # or :
        meta_yaml['metaData']['chip_params'] = {'Inv_vref' : vrefinv, 'Noinv_vref' : vrefnoinv} #for a 2D scan
        # .....
        with open(metaFileBaseName+str(index)+'.yaml', 'w') as fout:
            yaml.dump(meta_yaml, fout)

        index=index+1
    
    return

def template_scan(i2csocket,daqsocket, clisocket, basedir,device_name):
    ## check type of the socket objects
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
    
    ## creating output directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/vrefinv_scan/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
    ## starting the inotifier process (it will trigger the unpacker when raw data (.raw) and meta yaml files are saved
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()

    ## setting scan parameter values
    start_val=0
    stop_val=400
    step_val=10

    ##configuring the client software
    clisocket.yamlConfig['global']['outputDirectory'] = odir #it needs to know where to save the data 
    clisocket.yamlConfig['global']['run_type'] = "TESTNAME"  #used by the unpacker to build the name of the output DIR, it MUST be the same name as meta_yaml['metaData']['testName']
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.configure()
    ## DAQ server software configuration
    daqsocket.yamlConfig['daq']['NEvents']='NEVENTS'
    daqsocket.yamlConfig['daq']['L1A_type']='AB' ## could be "A", "B", "AB", "calib", or "rand"
    daqsocket.configure()

    ## saving the full initial configuration (one could restart from it if needed, e.g. for debug)
    initial_full_config={}
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            initial_full_config[key] = i2csocket.yamlConfig[key]
    initial_full_config['daq'] = daqsocket.yamlConfig['daq']
    initial_full_config['global'] = clisocket.yamlConfig['global']
    with open(odir+"/initial_full_config.yaml",'w') as fout:
        yaml.dump(initial_full_config,fout)

    clisocket.start() # starting the client : it starts waiting for data by looking at daqsocket.ip (using ZMQ PUSH/PULL sockets)
    scan(i2csocket, daqsocket, start_val, stop_val, step_val,odir) # running the scan
    clisocket.stop() # stopping the client : it stops waiting for data, but the client is not terminated, it is waiting for new command (start,configure)
    mylittlenotifier.stop() ## stopping inotifier process : after this, all the data should have been unpacked


    ## user needs to create the correspondant template_scan_analysis.py script abd replace template occurence by whatever name in the following lines
    ## these analysis scripts class can inherit from the analyzer class (analyzer.py)
    template_analyzer = analyzer.template_scan_analyzer(odir=odir) ## initializing the analysis
    files = glob.glob(odir+"/*.root")
    for f in files:
        template_analyzer.add(f) ## adding all root files, loading them as pandas data frame
    template_analyzer.mergeData() ## concatenate all dataframe in one


    # only when needed to create new ROC config (e.g.: vref scans)
    # check the method determine_bestVrefInv() of the vrefinv_scan_analysis.py script
    # it is expected that the method determine_bestParams() creates a new config files : "odir+'/template.yaml'"
    template_analyzer.determine_bestParams() 
    template_analyzer.makePlots() #create the output plots: example in the method makePlots() of the vrefinv_scan_analysis.py script
    
    i2csocket.update_yamlConfig(fname=odir+'/template.yaml') #next step keeps the knowledge of what was changed, so if we do: "i2csocket.configure()" it will not go back to the non optiized config
    i2csocket.configure(fname=odir+'/template.yaml') #partial configuration of the with new params (from determine_bestParams() method)
    return odir

######
# Examples: 
# python3 template_scan.py -d DUTNAME -i ZYNQIP -f configs/initLD.yaml
# python3 template_scan.py -d DUTNAME -i ZYNQIP -f configs/initHD.yaml
# python3 template_scan.py -d DUTNAME -i ZYNQIP -f configs/init1ROC.yaml
# python3 -h
######
# instead of calling this scan like in the above command , it can be inserted in the test sequence of full_test.py
######
if __name__ == "__main__":
    ## command line options 
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

    # initializing the zmq controller objects
    # the options.configFile will be loaded in each of them, then the different SWs will only use what they need (DAQ server will use the daq node, the client will use the global node and the I2C server will use the roc_s* nodes
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)

    #configuring the ROCs, it will use the configuration which was loaded just before (i.e. options.configFile)
    i2csocket.configure()

    #running the template_scan test
    template_scan.template_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
