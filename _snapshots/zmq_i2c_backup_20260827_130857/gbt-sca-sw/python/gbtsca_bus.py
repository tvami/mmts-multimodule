import gbtsca as sca
import time
import generic_iic
from glob import glob


class scabus(generic_iic.generic_iic):
    def __init__(self, gbtsca, busId):
        self.busId = busId
        self.gbtsca = gbtsca
        self.gbtsca.setI2CSpeed(self.busId, 3)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def write_byte(self, addr, val):
        self.gbtsca.i2cWrite_single(self.busId, addr,  val)

    def read_byte(self, addr):
        return self.gbtsca.i2cRead_single(self.busId, addr)

    def write(self, addr, vals):
        bvals = sca.ByteVector(len(vals))
        for i in range(0, len(vals)):
            bvals[i] = vals[i]
        self.gbtsca.i2cWrite(self.busId, addr, bvals)

    def read(self, addr, lenread):
        return self.gbtsca.i2cRead(self.busId, addr, lenread)


class gpio:
    def __init__(self, gbtsca, name, mask, inv):
        self.mask = mask
        self.name = name
        self.inv = inv
        self.gbtsca = gbtsca
        direction = self.gbtsca.gpioGetDirection()
        self.gbtsca.gpioSetDirection(direction | mask)

    def set_value(self, val):
        if(self.inv):
            val = val ^ 1
        if val:
            self.gbtsca.gpioWrite(self.mask, self.mask)
        else:
            self.gbtsca.gpioWrite(0, self.mask)

    def get_value():
        # kind of bad, only works if mask is only one bit.
        return bool(gbtsca.gpioRead() & mask)

    def reset_rocs(self):
        self.gbtsca.resethelper.reset_roc()


class GBTSCA(sca.GBT_SCA):
    def __init__(self, baseName, connection=None, device=None, Interface=None):
        if Interface is None:
            super().__init__(baseName, connection, device)
        else:
            super().__init__(baseName, hwInterface=Interface)
        self.reset()
        self.enableAdc(True)
        self.enableDAC(True)
 
    def reset_gbtsca(self):
        self.reset()
        self.enableAdc(True)
        self.enableDAC(True)

    def reset_rocs(self):
        self.reset_roc()

    def scabus(self, ibus):
        return scabus(self, ibus)

    def gpio(self, name, mask, inv):
        return gpio(self, name, mask, inv)
