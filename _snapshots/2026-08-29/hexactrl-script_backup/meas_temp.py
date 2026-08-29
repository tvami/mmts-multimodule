
import zmq_controler as zmqctrl
from nested_dict import nested_dict
import yaml
import numpy as np

if __name__ == "__main__":
        from optparse import OptionParser
        parser = OptionParser()

        parser.add_option("-i", "--hexaIP",
                          action="store", dest="hexaIP",
                          help="IP address of the zynq on the hexactrl board")

        parser.add_option("-f", "--configFile",default="./configs/init.yaml",
                          action="store", dest="configFile",
                          help="configuration yaml file")

        parser.add_option("-I", "--initialize",default=False,
                          action="store_true", dest="initialize",
                          help="initialize the rocs instead of just configuring")

        parser.add_option("--i2cPort",
                          action="store", dest="i2cPort",default='5555',
                          help="output base directory")

        (options, args) = parser.parse_args()
        i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile) 
  
        nestedConf = nested_dict()

        test_cfg_RTD = {
            "Trophy_version": "TrophyV3",
            "bus": 3,
            "i2c_address": 0x40,
            "conf_registers": [0b0, 0b0, 0b0, 0b0],
        }
        i2csocket.initialize_adc(test_cfg_RTD)

        internal = i2csocket.meas_adc_temp(dict())
        rtd_temp = i2csocket.meas_rtd_temp(dict())
        print('internal :',internal)
        print('RTD      :',rtd_temp)
