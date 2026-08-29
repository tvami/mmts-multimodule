import zmq_controler as zmqctrl
from nested_dict import nested_dict
import yaml
import numpy as np

# Example: 
# python3 configure_rocs.py -d hb -n 3 -i hexactrl564610
#

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
                          help="configuration yaml file")

        parser.add_option("--i2cPort",
                          action="store", dest="i2cPort",default='5555',
                          help="output base directory")

        parser.add_option("-I", "--initialize",default=False,
                          action="store_true", dest="initialize",
                          help="initialize the rocs instead of just configuring")


        (options, args) = parser.parse_args()
        print(options)

        i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
        if options.initialize==True:
                i2csocket.initialize()
        else:
                i2csocket.configure()
                #thresholds = np.linspace( 1023, 100, 10 ).astype(int)
                #print(thresholds)
                #for threshold in thresholds:
                #        nestedConf = nested_dict()
                #        for key in i2csocket.yamlConfig.keys():
                #                if key.find('roc_s')==0:
                #                        nestedConf[key]['sc']['ReferenceVoltage']['all']['Toa_vref']=int(threshold)
                #                        nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref']=int(threshold)

                #        print(nestedConf.to_dict())
                #        i2csocket.configure(yamlNode=nestedConf.to_dict())
        print( yaml.dump(i2csocket.read_config()) )
		
