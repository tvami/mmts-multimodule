import zmq, datetime,  os, subprocess, sys, yaml, glob

import myinotifier,util
import analysis.level0.daq_tpg_checker_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict 
import numpy as np

def run(i2csocket,daqsocket, clisocket, basedir,device_name,suffix="",logging_level='INFO'):
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

    daqsocket.yamlConfig['daq']['active_menu']='randomL1AplusTPG'
    daqsocket.yamlConfig['daq']['menus']['randomL1AplusTPG']['NEvents']=10000
    daqsocket.yamlConfig['daq']['menus']['randomL1AplusTPG']['log2_rand_bx_period']=0
    daqsocket.yamlConfig['daq']['menus']['randomL1AplusTPG']['bx_min']=45
    daqsocket.configure()

    nestedConf = nested_dict()
    chip=0

    tc1 = [np.arange(0,4),np.arange(4,8),np.arange(9,13),np.arange(13,17)]
    tc2 = [np.arange(19,23),np.arange(23,27),np.arange(28,32),np.arange(32,36)]
    tc3 = [np.arange(36,40),np.arange(40,44),np.arange(45,49),np.arange(49,53)]
    tc4 = [np.arange(55,59),np.arange(59,63),np.arange(64,68),np.arange(68,72)]

    interesting_paterns = np.array([[16,3072, 160, 36], [9,32, 2560, 16], [2, 2, 2, 2], [0, 0, 2048, 0]])

    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['GlobalAnalog']['all']['SelExtADC'] = 1
            i = 0
            for group in tc1: #A1111111
                for ch in group:
                    nestedConf[key]['sc']['ch'][int(ch)]['ExtData']= int(interesting_paterns[0][i]//4)
                i +=1

            i=0
            for group in tc2: #A0842108
                if i==0:
                    nestedConf[key]['sc']['ch'][19]['ExtData']= 2
                    nestedConf[key]['sc']['ch'][20]['ExtData']= 2
                    nestedConf[key]['sc']['ch'][21]['ExtData']= 2
                    nestedConf[key]['sc']['ch'][22]['ExtData']= 3
                if i>=1:
                    for ch in group:
                        nestedConf[key]['sc']['ch'][int(ch)]['ExtData']= int(interesting_paterns[1][i]//4)
                i +=1

            for group in tc3: #A0204081
                    nestedConf[key]['sc']['ch'][int(group[0])]['ExtData']= 2
                    nestedConf[key]['sc']['ch'][int(group[1])]['ExtData']= 0
                    nestedConf[key]['sc']['ch'][int(group[2])]['ExtData']= 0
                    nestedConf[key]['sc']['ch'][int(group[3])]['ExtData']= 0
            i = 0
            for group in tc4: #A0002000
                if i !=2:
                    for ch in group:
                        nestedConf[key]['sc']['ch'][int(ch)]['ExtData']= 0
                else: 
                    for ch in group:
                        nestedConf[key]['sc']['ch'][int(ch)]['ExtData']= 2048//4

                i+=1


            chip=chip+1
    i2csocket.configure(yamlNode=nestedConf.to_dict())

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,runid=0,testName=testName,keepRawData=1,chip_params={})
    util.acquire(daq=daqsocket, client=clisocket)
    mylittlenotifier.stop()

    try:
        my_analyzer = analyzer.daq_tpg_checker_analyzer(odir=odir,treename = "unpacker_data/triggerhgcroc")
        files = glob.glob(odir+"/*.root")
    	
        my_analyzer.mergeData()
        checker = my_analyzer.check()
        if analyzer.SuccessCode.SUCCESS not in checker:
            print("DAQ_TPG_CHECKER FOUND AN ERROR   ",checker)
            exit(1)
        else:
            print("DAQ_TPG_CHECKER ",checker)
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
    run(i2csocket,daqsocket,clisocket,options.odir,options.dut,suffix=options.suffix,logging_level=options.logging_level)
