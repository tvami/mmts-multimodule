from smbus2 import SMBus, i2c_msg

from swamp.core import Transport

class smTransport(Transport):
    def __init__(self, name : str="", cfg : dict={}):
        super().__init__(name, cfg)
        self.nwrite = 0
        self.nread  = 0
        self.fout   = open('output.txt', 'w')

    def write_regs(self, address, reg_address_width, reg_address, reg_vals):
        with SMBus(2) as bus:
                msg = i2c_msg.write(address, [0xff&reg_address, 0xff&(reg_address >> 8)] + reg_vals)
                bus.i2c_rdwr(msg)

    def read_regs(self, address, reg_address_width, reg_address, read_len):
        with SMBus(2) as bus:
            msg = i2c_msg.write(address, [0xff&reg_address, 0xff&(reg_address >> 8)])
            bus.i2c_rdwr(msg)

            msg = i2c_msg.read(address, read_len)
            bus.i2c_rdwr(msg)

            return [v for v in msg]

    def read_all(self):
        pass

    def read(self, address):
        pass
