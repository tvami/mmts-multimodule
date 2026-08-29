import zmq, datetime, os, subprocess, sys, yaml, glob
import zmq_controler as zmqctrl
from nested_lookup import nested_delete, nested_update
from nested_dict import nested_dict
from time import sleep

def scan_calibdac(i2csocket, calib_dac_range, keithley_h0=None, keithley_h1=None):
    ret = nested_dict()
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['ReferenceVoltage']['all']['IntCtest'] = 1
            nestedConf[key]['ReferenceVoltage']['all']['ExtCtest'] = 1
            nestedConf[key]['ReferenceVoltage']['all']['Calib'] = 0
    # print(nestedConf)
    for cdac in calib_dac_range:
        if cdac == -1:
            cfg = nested_update(nestedConf.to_dict(), key="IntCtest", value=0)	# measure ground
        else:
            cfg = nested_update(nestedConf.to_dict(), key="Calib", value=cdac)
        print(cfg)
        if keithley_h0 and keithley_h1:
            i2csocket.configure(yamlNode=cfg)
            keithley_h0.trigger()
            keithley_h1.trigger()
            # give keithleys time to measure before reconfiguring ROC.
            sleep(0.3)  # For using one adapter + Multi-con cable (MODE 1)
            # sleep(0.1)  # For using two adapters (MODE 2)
        else:
            ret_cfg = i2csocket.measadc(yamlNode=cfg)
            ret["Calib"][cdac] = ret_cfg

    # single-chip post-process measurement
    if keithley_h0 and keithley_h1:
        keithley_h0.wait_for_buffer()
        keithley_h1.wait_for_buffer()

        # read buffer, fill ret dict
        for (cdac, h0_data_pt, h1_data_pt) in zip(calib_dac_range, keithley_h0.buffer_data, keithley_h1.buffer_data):
            ret["half"][0]["Calib"][cdac]['roc_s0'] = float(h0_data_pt)
            ret["half"][1]["Calib"][cdac]['roc_s0'] = float(h1_data_pt)

    cfg = nested_update(nestedConf.to_dict(), key="IntCtest", value=0)	# back to initial config
    cfg = nested_update(cfg, key="ExtCtest", value=0)		# back to initial config
    cfg = nested_update(cfg, key="Calib", value=0)	    # back to initial config
    i2csocket.configure(yamlNode=cfg)
    return ret.to_dict()

def inCtest_run(i2csocket, basedir, device_name, prologixIP=""):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in inCtest_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    testName = "inCtest_run"
    odir = "%s/%s/inctest_run/run_%s/"%( os.path.realpath(basedir), device_name, timestamp )
    os.makedirs(odir)

    initial_full_config={}
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            initial_full_config[key] = i2csocket.yamlConfig[key]

    calib_dac_range = [-1] + [ (1<<i)-1 for i in range(0,13)]

    roc_config = {k: v for k, v in i2csocket.yamlConfig.items() if k.startswith('roc')}
    single_chip = True if len(roc_config)==1 else False
    if single_chip:
        from PrologixEthernetAdapter import PrologixEthernetAdapter
        from keithley2000_with_scanner_card import Keithley2000WithScannerCard

        ### MODE 1: One GPIB-ETH adapter + Multi-connector cable
        adapter = PrologixEthernetAdapter(prologixIP)
        j4 = Keithley2000WithScannerCard(adapter.gpib(16))
        j7 = Keithley2000WithScannerCard(adapter.gpib(14))

        ### MODE 2: Two GPIB-ETH adapters with separate IPs
        # j4_adapter = PrologixEthernetAdapter('128.141.89.187', address=21)
        # j7_adapter = PrologixEthernetAdapter('128.141.89.204', address=24)
        # j4 = Keithley2000WithScannerCard(j4_adapter)
        # j7 = Keithley2000WithScannerCard(j7_adapter)

        j4.config_buffer(len(calib_dac_range))
        j7.config_buffer(len(calib_dac_range))

        probe_pin = "Ctest"
        j4.channel = probe_pin
        j7.channel = probe_pin
    
        ret = scan_calibdac(i2csocket, calib_dac_range, keithley_h0=j4, keithley_h1=j7)
    else:
        ret = scan_calibdac(i2csocket, calib_dac_range)

    with open(odir + "/inCtest.yaml", "w") as fout:
        yaml.dump(ret, fout)


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
    
    parser.add_option("--prologixIP",
                      action="store", dest="prologixIP",default='0.0.0.0',
                      help="IP address of the prologix GPIB to ethernet connector (mandatory only when running with the Keithley multimeter for v2 single ROC boards)")

    parser.add_option("--i2cPort",
                      action="store", dest="i2cPort",default='5555',
                      help="port of the zynq waiting for I2C config and commands (initialize/configure/read_pwr,read/measadc)")
        
    
    (options, args) = parser.parse_args()
    print(options)
    
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    i2csocket.configure()
    inCtest_run(i2csocket,options.odir,options.dut,options.prologixIP)

if __name__ == "__main__":
    main()
