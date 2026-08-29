import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.tot_trim_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict

updateVref = lambda conf, half, var, val: conf['sc']['ReferenceVoltage'][half].update({var:val})
updateChan = lambda conf, chtype, channel, var, val : conf[chtype][channel].update({var:val})

def trim_scan(i2csocket, daqsocket, injectedChannels, trim_tot, gain, calib, odir, testname):

    # enable internal injection and set the injection DAC
    nestedConf = nested_dict()
    print("enable internal injection and set the injection DAC")
    [ updateVref(nestedConf[key], 'all', 'IntCtest', 1)  for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
    [ updateVref(nestedConf[key], 'all', 'Calib', calib) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
    print(yaml.dump(nestedConf.to_dict()))
    i2csocket.configure(yamlNode=nestedConf.to_dict())

    index=0
    for chtype in injectedChannels:
        for chgroup in injectedChannels[chtype]:
            if len(chgroup)==0: continue
            
            # enable the injection in injectedChannels
            nestedConf = nested_dict()
            if gain not in [0,1,2]:
                print("gain should be equal to 0, 1 or 2 tot_calib vref_scan will return without running => might expect a crash and need to restart client and servers from scratch")
                return
            if gain==2:
                highrange=1
                lowrange=1
            elif gain==1:
                highrange=1
                lowrange=0
            elif gain==0:
                highrange=0
                lowrange=1
            print("enable the injection in injectedChannels")
            [updateChan(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',highrange) for injectedChannel in chgroup for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0]
            [updateChan(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',lowrange) for injectedChannel in chgroup for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0]
            print(yaml.dump(nestedConf.to_dict()))
            i2csocket.configure(yamlNode=nestedConf.to_dict())

            # scanning trim_tot values:
            for tot in trim_tot:
                nestedConf = nested_dict()
                [updateChan(nestedConf[key]['sc'],chtype,injectedChannel,'trim_tot',tot) for injectedChannel in chgroup for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0]
                print(yaml.dump(nestedConf.to_dict()))
                i2csocket.configure(yamlNode=nestedConf.to_dict())
                util.acquire_scan(daq=daqsocket)
                chip_params = { 'Inj_gain':gain, 'Calib':calib, 'trim_tot':tot, 'injectedChannels': chgroup }
                util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                                  runid=index,testName=testname,keepRawData=0,
                                  chip_params=chip_params)
                index+=1
                
            # disable the injection in injectedChannels
            nestedConf = nested_dict()
            [updateChan(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',0) for injectedChannel in chgroup for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0]
            [updateChan(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',0) for injectedChannel in chgroup for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0]
            print("disable the injection in injectedChannels")
            print(yaml.dump(nestedConf.to_dict()))
            i2csocket.configure(yamlNode=nestedConf.to_dict())

    # disable internal injection and set the injection DAC to 0
    nestedConf = nested_dict()
    [ updateVref(nestedConf[key], 'all', 'IntCtest', 0)  for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
    [ updateVref(nestedConf[key], 'all', 'Calib', 0)     for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
    print("disable internal injection and set the injection DAC to 0")
    print(yaml.dump(nestedConf.to_dict()))
    i2csocket.configure(yamlNode=nestedConf.to_dict())
    return


def tot_trim_scan(i2csocket,daqsocket,clisocket,basedir,device_name,scan_config):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in tot_calib : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return
    
    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in tot_calib : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return
    
    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in tot_calib : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return

    ############# scan of TOT vref ############# 
    testname = "tot_trim_scan"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/%s/run_%s/"%( os.path.realpath(basedir), device_name, testname, timestamp ) # a comlete path is needed
    os.makedirs(odir)

    calibreqA            = 0x10
    phase				= scan_config['phase'] if 'phase' in scan_config.keys() else -1
    BXoffset			= scan_config['BXoffset']
    calib     			= scan_config['calib']
    gain 				= scan_config['gain'] # 0 for low range ; 1 for high range
    tot_vref            = scan_config['tot_vref'] if 'tot_vref' in scan_config.keys() else -1
    tot_vref            = scan_config['tot_vref'] if 'tot_vref' in scan_config.keys() else -1
    trim_tot            = scan_config['trim_tot'] if 'trim_tot' in scan_config.keys() else [i for i in range(0,64,4)]
    injectedChannels    = scan_config['injectedChannels']

    daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']=1000
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreqA
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=calibreqA+BXoffset
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['repeatOffset']=700
    daqsocket.configure()

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = testname
    clisocket.configure()
    
    nestedConf = nested_dict()
    [ nestedConf[key]['sc']['Top']['all'].update({'phase_strobe' : 15-phase}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 if phase>0 ]
    [ updateVref(nestedConf[key], 'all', 'Tot_vref', tot_vref) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 if tot_vref>-1 ]
    [ updateVref(nestedConf[key], 'all', 'Tot_vref', tot_vref) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 if tot_vref>-1 ]
    print( yaml.dump(nestedConf.to_dict()) )
    if len(nestedConf.keys()):
        i2csocket.configure(yamlNode=nestedConf.to_dict())
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()
    clisocket.start()
    trim_scan(i2csocket=i2csocket, daqsocket=daqsocket, injectedChannels=injectedChannels, trim_tot=trim_tot, gain=gain, calib=calib, odir=odir, testname=testname)
    clisocket.stop()
    mylittlenotifier.stop()
    
    try:
        scan_analyzer = analyzer.tot_trim_scan_analyzer(odir=odir)
        files = glob.glob(odir+"/*.root")
        for f in files:
            scan_analyzer.add(f)
        scan_analyzer.mergeData()
        scan_analyzer.makePlots()
        scan_analyzer.findTrim()
        i2csocket.update_yamlConfig(fname=odir+'/trimmed_tot.yaml') #next step keeps the knowledge of what was changed
        i2csocket.configure(fname=odir+'/trimmed_tot.yaml')
    except Exception as e:
        with open(odir+"crash_report.log","w") as fout:
            fout.write("tot trimming analysis went wrong and crash\n")
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

    injectionConfig = {
        'phase' : 14,
        'BXoffset' : 22,
        'gain' : 0,
        'calib' : 800,
        'trim_tot': [i for i in range(0,64,2)],
        'injectedChannels' : {'ch':[ [ch,ch+18,ch+36,ch+54] for ch in range(0,18)], 'calib':[[]] }
    }
    tot_trim_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig)
