import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.toa_vref_scan_noinj_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict

updateVref = lambda conf, half, var, val: conf['sc']['ReferenceVoltage'][half].update({var:val})

#vref scan without injections
def vref_scan(i2csocket, daqsocket, toa_vref, odir, testname):
    index=0
    # scanning toa_vref values:
    for toa in toa_vref:
        nestedConf = nested_dict()
        [ updateVref(nestedConf[key],'all', 'Toa_vref',toa) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
        print(yaml.dump(nestedConf.to_dict()))
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        util.acquire_scan(daq=daqsocket)
        chip_params = { 'Toa_vref':toa }
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testname,keepRawData=0,
                          chip_params=chip_params)
        index+=1                
    return


def toa_vref_scan_noinj(i2csocket,daqsocket,clisocket,basedir,device_name,scan_config):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in toa_vref_scan_noinj : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return
    
    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in toa_vref_scan_noinj : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return
    
    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in toa_vref_scan_noinj : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return

    ############# scan of TOA vref ############# 
    testname = "toa_vref_scan_noinj"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/%s/run_%s/"%( os.path.realpath(basedir), device_name, testname, timestamp ) # a comlete path is needed
    os.makedirs(odir)

    tot_vref            = scan_config['tot_vref'] if 'tot_vref' in scan_config.keys() else -1
    toa_vref            = scan_config['toa_vref'] if 'toa_vref' in scan_config.keys() else [i for i in range(80,120,1)]

    daqsocket.yamlConfig['daq']['active_menu']='randomL1A'
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['NEvents']=2000
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['log2_rand_bx_period']=0
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['bx_min']=45
    daqsocket.configure()

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = testname
    clisocket.configure()
    
    nestedConf = nested_dict()
    [ updateVref(nestedConf[key], 'all', 'Tot_vref', tot_vref) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 if tot_vref>-1 ]
    if len(nestedConf.keys()):
        i2csocket.configure(yamlNode=nestedConf.to_dict())
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()
    clisocket.start()
    vref_scan(i2csocket=i2csocket, daqsocket=daqsocket, toa_vref=toa_vref, odir=odir, testname=testname)
    clisocket.stop()
    mylittlenotifier.stop()
    
    try:
        scan_analyzer = analyzer.toa_vref_scan_noinj_analyzer(odir=odir)
        files = glob.glob(odir+"/*.root")
        for f in files:
            scan_analyzer.add(f)
        scan_analyzer.mergeData()
        scan_analyzer.makePlots()
        scan_analyzer.findVref()
        i2csocket.update_yamlConfig(fname=odir+'/toa_vref.yaml') #next step keeps the knowledge of what was changed
        i2csocket.configure(fname=odir+'/toa_vref.yaml')
    except Exception as e:
        with open(odir+"crash_report.log","w") as fout:
            fout.write("toa vref noinj analysis went wrong and crash\n")
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
    
    (options, args) = parser.parse_args()
    print(options)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    if options.initialize==True:
        i2csocket.initialize()
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
        daqsocket.initialize()
    else:
        i2csocket.configure()

    scanConfig = {
        'toa_vref' : [i for i in range(70,170,2)],
    }
    scanConfig['toa_vref'].sort(reverse=True)
    toa_vref_scan_noinj(i2csocket,daqsocket,clisocket,options.odir,options.dut,scanConfig)
