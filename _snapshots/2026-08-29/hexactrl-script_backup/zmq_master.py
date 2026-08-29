from time import sleep
import zmq_controler as zmqctrl
 


myzync   = zmqctrl.zmqController("hexactrl564610","6000")
datapull = zmqctrl.zmqController("localhost","6001")

yaml_file = "config_files/LD_HB.yaml"

myzync.configure(yaml_file)
datapull.configure(yaml_file)


sleep(1)

datapull.start()

for i in range(10):
    myzync.start()
    sleep(2)
    myzync.stop()


datapull.stop()
