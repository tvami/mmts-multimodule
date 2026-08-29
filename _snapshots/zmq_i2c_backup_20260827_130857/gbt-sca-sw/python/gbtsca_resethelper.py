import time
from glob import glob
import gpiod


class gbtsca_resethelper():
    def __init__(self, ipbushw, baseName):
        # check if gpio is supported by linux gpio driver
        # find reset gpio
        resetGPIOName = baseName+"_axi_gpio_0"
        gpioLabel = ""
        for gpiopath in glob("/sys/class/gpio/*"):
            try:
                with open(gpiopath + "/device/of_node/label") as f:
                    if resetGPIOName in f.read():
                        with open(gpiopath + "/label") as f_label:
                            gpioLabel = f_label.read().strip()
                            break
            except(IOError):
                pass
       
        if len(gpioLabel) > 0:
            j=0
            for gpio in gpiod.chip_iter():
                if gpioLabel in gpio.label:
                    self.gpio_pin = gpio.get_line(0)
                    config = gpiod.line_request()
                    config.request_type = gpiod.line_request.DIRECTION_OUTPUT
                    self.gpio_pin.request(config, default_val=1)
                    self.reset_impl = self.reset_gpiod
                if j==2:
                   self.hgcrstb = gpio.get_line(1)
                   config = gpiod.line_request()
                   config.request_type = gpiod.line_request.DIRECTION_OUTPUT
                   self.hgcrstb.request(config, default_val=1)
                   self.hgci2crstb = gpio.get_line(2)
                   config2 = gpiod.line_request()
                   config2.request_type = gpiod.line_request.DIRECTION_OUTPUT
                   self.hgci2crstb.request(config2, default_val=1)
                j=j+1
                    #break
        else:
            NODE_NAME = "_gpio"
            self.node = ipbushw.getNode(baseName+NODE_NAME)
            self.reset_impl = self.reset_uhal

    def reset(self):
        self.reset_impl()

    def reset_uhal(self):
        self.node.getNode("reset").write(0)
        self.node.getClient().dispatch()
        self.node.getNode("reset").write(1)
        self.node.getClient().dispatch()

    def reset_gpiod(self):
        self.gpio_pin.set_value(0)
        self.gpio_pin.set_value(1)
 
    def reset_roc(self):
        self.hgcrstb.set_value(0)
        self.hgci2crstb.set_value(0)
        self.hgcrstb.set_value(1)
        self.hgci2crstb.set_value(1)
