import sca
import time

def rocSetAddress(gbtsca, i2cbus, i2cAddr, addr):
   addr_low = addr&((1<<8)-1)
   addr_high = addr>>8
   gbtsca.i2cWrite_single(i2cbus, i2cAddr | 0x0, addr_low)
   gbtsca.i2cWrite_single(i2cbus, i2cAddr | 0x1, addr_high)

gbtsca = sca.GBT_SCA("file://address_table/connection.xml")

gbtsca.enableAdc(True)
gbtsca.enableI2C(0xffff)
gbtsca.enableGPIO(True)

gbtsca.gpioSetDirection(0x03c)

devId = gbtsca.readDeviceID()
print("Device ID: " + str(devId))

gbtsca.gpioWrite(0x0c, 0x3c)
time.sleep(0.1)
gbtsca.gpioWrite(0x08, 0x3c)
time.sleep(0.1)
gbtsca.gpioWrite(0x0c, 0x3c)
time.sleep(0.1)
gbtsca.gpioWrite(0x1c, 0x3c)
time.sleep(0.1)
gbtsca.gpioWrite(0x0c, 0x3c)
time.sleep(0.1)
gbtsca.gpioWrite(0x04, 0x3c)
time.sleep(0.1)
gbtsca.gpioWrite(0x0c, 0x3c)
time.sleep(0.1)

#read status values
gpioStatus = gbtsca.gpioRead()

print("Error: " + str((gpioStatus & 0x2) != 0x2) + " lock: " + str((gpioStatus & 0x1) == 0x1))

i2cBus = 0;
i2cAddr = 0x28;

gbtsca.setI2CSpeed(i2cBus, 3);

#ROC "Top" register 3, setting BIAS_I_PLL_D: 63
rocSetAddress(gbtsca, i2cBus, i2cAddr, 44 << 5 | 3)
gbtsca.i2cWrite_single(i2cBus, i2cAddr | 2, 0x7f)

#ROC "Top" register 1, setting EN_HIGH_CAPA: 1
rocSetAddress(gbtsca, i2cBus, i2cAddr, 44 << 5 | 1)
gbtsca.i2cWrite_single(i2cBus, i2cAddr | 2, 0x19)

#ROC "Top" register 0, EN_LOCK_CONTROL: 0 and ERROR_LIMIT_SC: 0
rocSetAddress(gbtsca, i2cBus, i2cAddr, 44 << 5 | 0)
gbtsca.i2cWrite_single(i2cBus, i2cAddr | 2, 0x3e)

