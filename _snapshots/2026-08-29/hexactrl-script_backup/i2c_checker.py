import zmq_controler as zmqctrl
from nested_dict import nested_dict
import yaml,json
from deepdiff import DeepDiff
import os, time, datetime
import myinotifier
from enum import Enum
# Example: 
# python3 i2c_checker.py -d hb -n 3 -i hexactrl640259 -f configs/toto.yaml
#

class I2CCheckerSuccess(Enum):
    SUCCESS = 0
    FAILURE = 1

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def i2c_checker(i2csocket, basedir, device_name, config=""):

    testname = "i2c_checker"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/%s/run_%s/"%( os.path.realpath(basedir), device_name, testname, timestamp ) # a comlete path is needed
    os.makedirs(odir)

    if config=="":
        config = i2csocket.yamlConfig

    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()

    readDict = i2csocket.read_config(config)

    with open("%s/read_config_default.yaml" % odir, "w") as fout:
        yaml.dump(readDict,fout)
	
    defaultDict = config
    diffDict = {}
    for key in defaultDict.keys():
        if key.startswith('roc_s'):
            diffDict[key] = DeepDiff(defaultDict[key]['sc'], readDict[key], ignore_order=True)

    print("Differences between read/write default")
    number_of_rocs_with_error = 0
    for key in diffDict.keys():
        if not len(diffDict[key])==0:
            number_of_rocs_with_error = number_of_rocs_with_error + 1
    print(f'Number of ROCs with error = {number_of_rocs_with_error}')

    with open("%s/diff_config_default.json"%(odir), "w") as fout:
        json.dump(diffDict, fout, indent=4)
    
    mylittlenotifier.stop()
    return I2CCheckerSuccess.SUCCESS if number_of_rocs_with_error==0 else I2CCheckerSuccess.FAILURE

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option("-d", "--dut", dest="dut",
                      help="device under test")
    
    parser.add_option("-i", "--hexaIP", default="129.104.89.114",
                      action="store", dest="hexaIP",
                      help="IP address of the zynq on the hexactrl board")
    
    parser.add_option("-f", "--configFile",default="./configs/full_default_config.yaml",
                      action="store", dest="configFile",
                      help="initial configuration yaml file")
    
    parser.add_option("-o", "--odir",
                      action="store", dest="odir",default='./data',
                      help="output base directory")
    
    parser.add_option("--i2cPort",
                      action="store", dest="i2cPort",default='5555',
                      help="port of the zynq waiting for I2C config and commands (initialize/configure/read_pwr,read/measadc)")

    (options, args) = parser.parse_args()
    print(options)

    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    i2c_checker(i2csocket,options.odir,options.dut)
